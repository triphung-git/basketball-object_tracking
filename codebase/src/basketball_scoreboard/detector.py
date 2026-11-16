"""Object detection model loader, inference wrapper, and coordinate normalizer."""
from __future__ import annotations

from contextlib import contextmanager, redirect_stderr, redirect_stdout
import importlib.metadata
import io
import logging
import math
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import cv2
import numpy as np

from .config import APPROVED_MODEL_ID, ModelConfig
from .contracts import CLASS_MAPPING, DetectionRecord

logger = logging.getLogger(__name__)

EXPECTED_CLASSES: Set[str] = set(CLASS_MAPPING.values())


def get_cache_dir(project_root: Optional[Path] = None) -> str:
    """Return local .model-cache directory path, adding Windows long-path prefix if needed."""
    if project_root is None:
        # Default project root: 3 levels up from this file (codebase/src/basketball_scoreboard -> codebase)
        project_root = Path(__file__).resolve().parents[2]
    cache_path = str((project_root / ".model-cache").resolve())
    if os.name == "nt" and not cache_path.startswith("\\\\?\\"):
        cache_path = "\\\\?\\" + cache_path
    return cache_path


def load_roboflow_api_key(env_path: Optional[Path | str] = None) -> str:
    """Read ROBOFLOW_API_KEY from environment or literal assignment in .env file."""
    key = os.environ.get("ROBOFLOW_API_KEY", "").strip()
    if key and key not in {"your_api_key_here", "<your-key>"}:
        return key

    if env_path is None:
        env_path = Path(__file__).resolve().parents[2] / ".env"
    env_file = Path(env_path).resolve()

    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, separator, value = line.partition("=")
            if separator and name.strip() == "ROBOFLOW_API_KEY":
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                key = value.strip()
                break

    if not key or key in {"your_api_key_here", "<your-key>"}:
        raise ValueError(
            "Missing key: set ROBOFLOW_API_KEY locally in environment or in codebase/.env. "
            "Never paste API keys into chat or log files."
        )
    return key


@contextmanager
def private_library_output():
    """Suppress stdout/stderr and critical logging to prevent leaking sensitive URLs/keys."""
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            yield
    finally:
        logging.disable(previous)


def apply_windows_symlink_compat(cache_dir: str) -> None:
    """Enable file copy fallback on Windows when unprivileged symlink creation raises WinError 1314."""
    os.environ["INFERENCE_HOME"] = cache_dir
    os.environ["DEFAULT_DEVICE"] = "cpu"
    try:
        import inference_models.configuration as cfg
        import inference_models.models.auto_loaders.auto_resolution_cache as arc
        import inference_models.models.auto_loaders.core as core
        import inference_models.models.auto_loaders.model_cache_paths as mcp
        import inference_models.weights_providers.offline_registry as ofr

        cfg.INFERENCE_HOME = cache_dir
        mcp.INFERENCE_HOME = cache_dir
        core.INFERENCE_HOME = cache_dir
        arc.INFERENCE_HOME = cache_dir
        ofr.INFERENCE_HOME = cache_dir
    except ImportError:
        return

    if os.name != "nt":
        return

    import shutil

    def safe_handle_symlink_creation(target_path, link_name, **kwargs):
        link_dir = os.path.dirname(os.path.abspath(link_name))
        os.makedirs(link_dir, exist_ok=True)
        try:
            os.symlink(target_path, link_name)
        except OSError as error:
            if getattr(error, "winerror", None) != 1314:
                raise
            with open(target_path, "rb") as source, open(link_name, "xb") as destination:
                shutil.copyfileobj(source, destination)

    def safe_materialize(package_dir, declarations):
        identities = []
        shared_blobs_dir = os.path.abspath(mcp.generate_shared_blobs_path())
        if os.path.islink(shared_blobs_dir):
            raise core.CorruptedModelPackageError("Shared blob directory cannot be a symlink.")
        for declaration in declarations:
            package_path = os.path.join(package_dir, declaration["file_handle"])
            if not Path(os.path.abspath(package_path)).is_relative_to(Path(os.path.abspath(package_dir))):
                raise core.CorruptedModelPackageError("Artifact path escapes model package.")
            md5_hash = declaration["md5_hash"]
            if declaration["storage"] == "shared_blob":
                expected_blob = os.path.join(shared_blobs_dir, md5_hash)
                if os.path.islink(expected_blob) or not os.path.isfile(expected_blob) or core._md5_file(path=expected_blob) != md5_hash:
                    raise core.CorruptedModelPackageError(f"Expected blob {expected_blob} is missing or corrupted.")
                if os.path.islink(package_path) and os.path.realpath(package_path) != os.path.realpath(expected_blob):
                    raise core.CorruptedModelPackageError("Artifact symlink points outside the verified blob.")
                if not os.path.exists(package_path) or core._md5_file(path=package_path) != md5_hash:
                    shutil.copyfile(expected_blob, package_path)
                if core._md5_file(path=package_path) != md5_hash:
                    raise core.CorruptedModelPackageError("Copied artifact checksum mismatch.")
                identities.append({**declaration, "sha256_hash": None})
            else:
                if os.path.islink(package_path) or not os.path.isfile(package_path) or (md5_hash and core._md5_file(path=package_path) != md5_hash):
                    raise core.CorruptedModelPackageError(f"Package artifact {package_path} is invalid.")
                identities.append({**declaration, "sha256_hash": core._sha256_file(path=package_path) if not md5_hash else None})
        return identities

    core.handle_symlink_creation = safe_handle_symlink_creation
    core._materialize_package_artifact_identities = safe_materialize


class ObjectDetector:
    """Wrapper for the approved YOLO26 ONNX CPU detector."""

    def __init__(self, config: Optional[ModelConfig] = None, api_key: Optional[str] = None, env_path: Optional[Path] = None) -> None:
        self.config = config or ModelConfig()
        if self.config.model_id != APPROVED_MODEL_ID:
            raise ValueError(f"Unauthorized model ID: {self.config.model_id}")

        self.cache_dir = get_cache_dir()
        self.api_key = api_key or load_roboflow_api_key(env_path)

        with private_library_output():
            import torch
            torch.set_num_threads(self.config.cpu_threads)
            from inference_models import AutoModel
            apply_windows_symlink_compat(self.cache_dir)

            start = time.perf_counter()
            self.model = AutoModel.from_pretrained(
                self.config.model_id,
                api_key=self.api_key,
                backend=self.config.backend,
                device=self.config.device,
                onnx_execution_providers=["CPUExecutionProvider"],
                allow_untrusted_packages=False,
                allow_local_code_packages=False,
                verify_hash_while_download=True,
                download_files_without_hash=False,
                trt_engine_host_code_allowed=False,
                verbose=False,
            )
            self.init_s = time.perf_counter() - start

        self.runtime_class = type(self.model).__name__
        if "yolo26" not in self.runtime_class.lower():
            raise ValueError(f"Runtime did not load a YOLO26 model: {self.runtime_class}")

        self.classes = list(self.model.class_names)
        if set(self.classes) != EXPECTED_CLASSES or len(self.classes) != 3:
            raise ValueError(f"Model classes differ from {EXPECTED_CLASSES}: {self.classes}")

        self.class_mapping = dict(enumerate(self.classes))
        self.warmup_times_ms: List[float] = []

    def warmup(self, sample_image: Optional[np.ndarray] = None) -> List[float]:
        """Perform warmup inferences to stabilize CPU execution provider state."""
        if sample_image is None:
            sample_image = np.zeros((640, 640, 3), dtype=np.uint8)

        times: List[float] = []
        for _ in range(self.config.warmup_runs):
            t0 = time.perf_counter()
            with private_library_output():
                self.model(sample_image)
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
            not isinstance(image_size, (tuple, list)) or len(image_size) != 2 or
            any(isinstance(x, bool) or not isinstance(x, int) or not 320 <= x <= 2048 or x % 32 for x in image_size)
        ):
            raise ValueError('Network image_size must be WH integers divisible by 32, in [320, 2048]')
        sdk_options = {'confidence': thresh}
        if image_size is not None:
            sdk_options['image_size'] = tuple(image_size)
        height, width = bgr_frame.shape[:2]

        scale = min(1.0, self.config.max_edge / max(width, height))
        input_w = max(1, round(width * scale))
        input_h = max(1, round(height * scale))

        if scale < 1.0:
            resized_frame = cv2.resize(bgr_frame, (input_w, input_h), interpolation=cv2.INTER_LINEAR)
        else:
            resized_frame = bgr_frame

        t0 = time.perf_counter()
        with private_library_output():
            predictions = self.model(resized_frame, **sdk_options)
        model_call_ms = (time.perf_counter() - t0) * 1000.0

        if len(predictions) != 1:
            raise ValueError(f"Expected single image output, got {len(predictions)}")

        detections = predictions[0].to_supervision()
        records: List[DetectionRecord] = []

        boxes = detections.xyxy
        class_ids = detections.class_id
        scores = detections.confidence

        if not (len(boxes) == len(class_ids) == len(scores)):
            raise ValueError("Inconsistent detection array lengths returned from model")

        for box, cid, score in zip(boxes, class_ids, scores):
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

            if len(box) != 4 or not all(math.isfinite(float(v)) for v in box):
                raise ValueError(f"Invalid bounding box: {box}")

            bx1, by1, bx2, by2 = map(float, box)
            if bx2 <= bx1 or by2 <= by1:
                raise ValueError(f"Invalid bounding box order: {box}")

            # Scale back to original image dimensions
            orig_x1 = min(float(width), max(0.0, bx1 * width / input_w))
            orig_x2 = min(float(width), max(0.0, bx2 * width / input_w))
            orig_y1 = min(float(height), max(0.0, by1 * height / input_h))
            orig_y2 = min(float(height), max(0.0, by2 * height / input_h))

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
        packages = ("inference-models", "opencv-python", "onnxruntime", "torch")
        versions = {}
        for pkg in packages:
            try:
                versions[pkg] = importlib.metadata.version(pkg)
            except Exception:
                versions[pkg] = "unknown"

        return {
            "model_id": self.config.model_id,
            "implementation_sha256": __import__('hashlib').sha256(Path(__file__).read_bytes()).hexdigest(),
            "runtime_class": self.runtime_class,
            "backend": self.config.backend,
            "device": self.config.device,
            "class_mapping": self.class_mapping,
            "init_s": round(self.init_s, 4),
            "warmup_ms": [round(t, 2) for t in self.warmup_times_ms],
            "versions": versions,
        }
