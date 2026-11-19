"""Object detection model loader, inference wrapper, and coordinate normalizer."""
from __future__ import annotations

import hashlib
import importlib.metadata
import math
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import onnxruntime as ort

from .config import APPROVED_MODEL_ID, ModelConfig
from .contracts import CLASS_MAPPING, DetectionRecord


APPROVED_WEIGHTS_SHA256 = "07044f5d08f37848f7d61f49d16b03407daad025919d63f0dfe195cd30f56b33"


def get_weights_path(project_root: Optional[Path] = None) -> Path:
    """Return the approved ONNX weights distributed with the project."""
    root = project_root or Path(__file__).resolve().parents[2]
    return (root / "models" / "detector" / "weights.onnx").resolve()


class ObjectDetector:
    """Wrapper for the approved YOLO26 ONNX CPU detector using local onnxruntime."""

    def __init__(
        self,
        config: Optional[ModelConfig] = None,
        api_key: Optional[str] = None,
        env_path: Optional[Path] = None,
        weights_path: Optional[Path | str] = None,
    ) -> None:
        self.config = config or ModelConfig()
        if self.config.model_id != APPROVED_MODEL_ID:
            raise ValueError(f"Unauthorized model ID: {self.config.model_id}")

        self.weights_path = Path(weights_path).resolve() if weights_path else get_weights_path()
        if not self.weights_path.is_file():
            raise FileNotFoundError(f"Model weights not found: {self.weights_path}. Restore the file and run setup.bat.")

        with open(self.weights_path, "rb") as f:
            self.weights_sha256 = hashlib.file_digest(f, "sha256").hexdigest()
        if self.weights_sha256 != APPROVED_WEIGHTS_SHA256:
            raise ValueError(
                f"Model weights checksum mismatch: expected {APPROVED_WEIGHTS_SHA256}, got {self.weights_sha256}"
            )

        start = time.perf_counter()
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = max(1, self.config.cpu_threads)
        opts.inter_op_num_threads = 1
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.session = ort.InferenceSession(
            str(self.weights_path),
            sess_options=opts,
            providers=["CPUExecutionProvider"],
        )
        self.input_name = self.session.get_inputs()[0].name
        self.init_s = time.perf_counter() - start

        self.runtime_class = "YOLO26ForObjectDetectionOnnx"
        self.classes = list(CLASS_MAPPING.values())
        self.class_mapping = dict(CLASS_MAPPING)
        self.warmup_times_ms: List[float] = []

        # Compatibility wrapper for callers expecting detector.model
        class _ModelWrapper:
            def __init__(wrapper, outer_instance):
                wrapper._outer = outer_instance
                wrapper.class_names = outer_instance.classes
                wrapper._session = outer_instance.session

        self.model = _ModelWrapper(self)

    def warmup(self, sample_image: Optional[np.ndarray] = None) -> List[float]:
        """Perform warmup inferences to stabilize CPU execution provider state."""
        if sample_image is None:
            sample_image = np.zeros((640, 640, 3), dtype=np.uint8)

        times: List[float] = []
        for _ in range(self.config.warmup_runs):
            t0 = time.perf_counter()
            self.detect(sample_image)
            times.append((time.perf_counter() - t0) * 1000.0)
        self.warmup_times_ms = times
        return times

    def detect(
        self,
        bgr_frame: np.ndarray,
        confidence_threshold: Optional[float] = None,
        image_size: Optional[Tuple[int, int]] = None,
    ) -> Tuple[List[DetectionRecord], float]:
        """Run detection on a single BGR frame, returning coordinates scaled to original resolution."""
        thresh = confidence_threshold if confidence_threshold is not None else self.config.confidence_threshold
        if image_size is not None and (
            not isinstance(image_size, (tuple, list))
            or len(image_size) != 2
            or any(
                isinstance(x, bool) or not isinstance(x, int) or not 320 <= x <= 2048 or x % 32
                for x in image_size
            )
        ):
            raise ValueError("Network image_size must be WH integers divisible by 32, in [320, 2048]")

        height, width = bgr_frame.shape[:2]

        scale = min(1.0, self.config.max_edge / max(width, height))
        input_w = max(1, round(width * scale))
        input_h = max(1, round(height * scale))

        if scale < 1.0:
            resized_frame = cv2.resize(bgr_frame, (input_w, input_h), interpolation=cv2.INTER_LINEAR)
        else:
            resized_frame = bgr_frame

        target_w, target_h = (image_size[0], image_size[1]) if image_size else (640, 640)
        net_in = cv2.resize(resized_frame, (target_w, target_h))
        # BGR -> RGB
        net_in = net_in[:, :, [2, 1, 0]]
        # Normalize to float32 [0, 1] in NCHW format
        blob = (net_in.astype(np.float32) / 255.0).transpose(2, 0, 1)[np.newaxis, ...]

        # Support dynamic session replacement (e.g. from TiledBallDetector)
        active_session = getattr(self.model, "_session", self.session)
        input_name = active_session.get_inputs()[0].name

        t0 = time.perf_counter()
        outputs = active_session.run(None, {input_name: blob})
        model_call_ms = (time.perf_counter() - t0) * 1000.0

        predictions = outputs[0][0]  # shape (300, 6)
        records: List[DetectionRecord] = []

        for row in predictions:
            x1, y1, x2, y2, score, cid = row
            score_f = float(score)
            cid_f = float(cid)

            if not math.isfinite(score_f) or not (0.0 <= score_f <= 1.0):
                raise ValueError(f"Invalid detection score: {score}")
            if not math.isfinite(cid_f) or not cid_f.is_integer():
                raise ValueError(f"Invalid class ID: {cid}")

            cid_int = int(cid_f)
            if cid_int not in self.class_mapping:
                raise ValueError(f"Class ID {cid_int} not in class mapping")

            if score_f < thresh:
                continue

            # Scale to input dimensions and round to integer grid (matching baseline Roboflow postprocessing)
            rx1 = float(np.round(np.clip(x1 * (input_w / target_w), 0, input_w)))
            rx2 = float(np.round(np.clip(x2 * (input_w / target_w), 0, input_w)))
            ry1 = float(np.round(np.clip(y1 * (input_h / target_h), 0, input_h)))
            ry2 = float(np.round(np.clip(y2 * (input_h / target_h), 0, input_h)))

            if rx2 <= rx1 or ry2 <= ry1:
                continue

            # Scale back to original image dimensions
            orig_x1 = min(float(width), max(0.0, rx1 * width / input_w))
            orig_x2 = min(float(width), max(0.0, rx2 * width / input_w))
            orig_y1 = min(float(height), max(0.0, ry1 * height / input_h))
            orig_y2 = min(float(height), max(0.0, ry2 * height / input_h))

            if orig_x2 <= orig_x1 or orig_y2 <= orig_y1:
                continue

            class_name = self.class_mapping[cid_int]
            record = DetectionRecord(
                xyxy=[orig_x1, orig_y1, orig_x2, orig_y2],
                class_id=cid_int,
                class_name=class_name,
                confidence=score_f,
                class_mapping=self.class_mapping,
            )
            record.validate_bounds((width, height))
            records.append(record)

        return records, model_call_ms

    def get_runtime_info(self) -> Dict[str, Any]:
        """Collect runtime package versions and execution provider details."""
        packages = ("onnxruntime", "opencv-python", "torch")
        versions = {}
        for pkg in packages:
            try:
                versions[pkg] = importlib.metadata.version(pkg)
            except Exception:
                versions[pkg] = "unknown"

        return {
            "model_id": self.config.model_id,
            "weights_path": str(self.weights_path),
            "weights_sha256": self.weights_sha256,
            "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "runtime_class": self.runtime_class,
            "backend": self.config.backend,
            "device": self.config.device,
            "class_mapping": self.class_mapping,
            "init_s": round(self.init_s, 4),
            "warmup_ms": [round(t, 2) for t in self.warmup_times_ms],
            "versions": versions,
        }
