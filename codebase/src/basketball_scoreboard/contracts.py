"""Data contracts for video decoding, timestamps, and detection outputs (v2)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
from typing import Any, Dict, List, Optional, Tuple

CLASS_MAPPING: Dict[int, str] = {
    0: "ball",
    1: "human",
    2: "rim",
}
EXPECTED_CLASSES = set(CLASS_MAPPING.values())


@dataclass
class DetectionRecord:
    """Detection bounding box and class classification in original frame coordinates."""
    xyxy: List[float]
    class_id: int
    class_name: str
    confidence: float
    class_mapping: Optional[Dict[int, str]] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not math.isfinite(self.class_id) or not float(self.class_id).is_integer():
            raise ValueError(f"Invalid class_id: {self.class_id}")
        self.class_id = int(self.class_id)
        mapping = self.class_mapping if self.class_mapping is not None else CLASS_MAPPING
        if self.class_id not in mapping:
            raise ValueError(f"Unknown class_id: {self.class_id}")
        expected_name = mapping[self.class_id]
        if self.class_name != expected_name:
            raise ValueError(f"Class name mismatch: {self.class_name} != {expected_name}")
        if not math.isfinite(self.confidence) or not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Invalid confidence: {self.confidence}")
        if len(self.xyxy) != 4 or not all(math.isfinite(float(v)) for v in self.xyxy):
            raise ValueError(f"Invalid bbox coordinates: {self.xyxy}")
        self.xyxy = [float(v) for v in self.xyxy]
        x1, y1, x2, y2 = self.xyxy
        if x2 <= x1 or y2 <= y1:
            raise ValueError(f"Degenerate or reversed bbox: [{x1}, {y1}, {x2}, {y2}]")

    def validate_bounds(self, original_wh: Tuple[int, int]) -> None:
        width, height = original_wh
        x1, y1, x2, y2 = self.xyxy
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            raise ValueError(
                f"Bbox [{x1}, {y1}, {x2}, {y2}] exceeds image boundaries {original_wh}"
            )

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("class_mapping", None)
        return data


@dataclass
class FrameRecord:
    """Metadata and normalized presentation timestamp for a single video frame."""
    video_id: str
    frame_index: int
    source_time_s: float
    original_wh: Tuple[int, int]
    raw_pts: Optional[int] = None
    time_base: Optional[str] = None
    timestamp_status: str = "valid"
    timestamp_policy: str = "pts_normalized"

    def __post_init__(self) -> None:
        if not self.video_id or not isinstance(self.video_id, str):
            raise ValueError("video_id must be a non-empty string")
        if self.frame_index < 0:
            raise ValueError(f"frame_index must be >= 0: {self.frame_index}")
        if not math.isfinite(self.source_time_s) or self.source_time_s < 0.0:
            raise ValueError(f"source_time_s must be a finite non-negative float: {self.source_time_s}")
        if len(self.original_wh) != 2 or any(dim <= 0 for dim in self.original_wh):
            raise ValueError(f"original_wh must be positive dimensions: {self.original_wh}")
        if self.timestamp_status not in {"valid", "repaired", "estimated", "irregular"}:
            raise ValueError(f"Unknown timestamp_status: {self.timestamp_status}")

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["original_wh"] = list(self.original_wh)
        return data


@dataclass
class FrameDetectionsRecord:
    """Combined frame metadata and model detection results."""
    video_id: str
    frame_index: int
    source_time_s: float
    original_wh: Tuple[int, int]
    detections: List[DetectionRecord] = field(default_factory=list)
    raw_pts: Optional[int] = None
    time_base: Optional[str] = None
    timestamp_status: str = "valid"
    model_call_ms: Optional[float] = None
    timestamp_policy: str = "pts_normalized"

    def __post_init__(self) -> None:
        if self.frame_index < 0:
            raise ValueError(f"frame_index must be >= 0: {self.frame_index}")
        if not math.isfinite(self.source_time_s) or self.source_time_s < 0.0:
            raise ValueError(f"source_time_s must be finite and >= 0: {self.source_time_s}")
        width, height = self.original_wh
        for det in self.detections:
            det.validate_bounds((width, height))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "video_id": self.video_id,
            "frame_index": self.frame_index,
            "source_time_s": round(self.source_time_s, 6),
            "original_wh": list(self.original_wh),
            "raw_pts": self.raw_pts,
            "time_base": self.time_base,
            "timestamp_status": self.timestamp_status,
            "timestamp_policy": self.timestamp_policy,
            "model_call_ms": round(self.model_call_ms, 3) if self.model_call_ms is not None else None,
            "detections": [d.to_dict() for d in self.detections],
        }

    def to_jsonl(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class VideoMetadata:
    """Stream properties and container metadata extracted during probing."""
    video_id: str
    relative_path: str
    width: int
    height: int
    fps: float
    nb_frames: int
    duration_s: float
    time_base: str
    is_vfr: bool
    sha256: str
    codec: str = "h264"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RunMetadata:
    """Provenance, configuration, execution telemetry, and outcome of a pipeline run."""
    run_id: str
    status: str
    video_path: str
    video_id: str
    source_fingerprint_sha256: str
    video_metadata: Dict[str, Any]
    config: Dict[str, Any]
    runtime: Dict[str, Any]
    class_mapping: Dict[str, str]
    counts: Dict[str, Any]
    timings: Dict[str, Any]
    timing_scope: str
    export: Dict[str, Any]
    created_utc: str
    completed_utc: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
