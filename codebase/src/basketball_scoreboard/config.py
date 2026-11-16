"""Configuration parsing, validation, and defaults for the scoreboard pipeline."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml

APPROVED_MODEL_ID = "phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1"
VALID_PTS_POLICIES = {"repair_with_audit", "strict_reject", "flag_only"}


@dataclass
class ModelConfig:
    model_id: str = APPROVED_MODEL_ID
    confidence_threshold: float = 0.25
    max_edge: int = 1280
    device: str = "cpu"
    backend: str = "onnx"
    warmup_runs: int = 2
    cpu_threads: int = 1

    def __post_init__(self) -> None:
        if self.model_id != APPROVED_MODEL_ID:
            raise ValueError(
                f"Model ID '{self.model_id}' does not match the approved model '{APPROVED_MODEL_ID}'."
            )
        if not (0.0 < self.confidence_threshold <= 1.0):
            raise ValueError(f"confidence_threshold must be in (0, 1]: {self.confidence_threshold}")
        if not (320 <= self.max_edge <= 4096):
            raise ValueError(f"max_edge must be in [320, 4096]: {self.max_edge}")
        if self.device != "cpu":
            raise ValueError(f"Approved baseline device is 'cpu', got '{self.device}'")
        if self.backend != "onnx":
            raise ValueError(f"Approved baseline backend is 'onnx', got '{self.backend}'")
        if not isinstance(self.warmup_runs, int) or self.warmup_runs < 0:
            raise ValueError("warmup_runs must be a non-negative integer")
        if not isinstance(self.cpu_threads, int) or self.cpu_threads < 1:
            raise ValueError("cpu_threads must be positive")


@dataclass
class VideoConfig:
    pts_policy: str = "repair_with_audit"
    max_frames: Optional[int] = None
    draw_overlay: bool = True

    def __post_init__(self) -> None:
        if self.pts_policy not in VALID_PTS_POLICIES:
            raise ValueError(
                f"pts_policy '{self.pts_policy}' invalid; must be one of {VALID_PTS_POLICIES}"
            )
        if self.max_frames is not None and self.max_frames <= 0:
            raise ValueError(f"max_frames must be positive if specified: {self.max_frames}")


@dataclass
class ExportConfig:
    video_filename: str = "annotated.mp4"
    detections_filename: str = "detections.jsonl"
    run_filename: str = "run.json"
    codec: str = "libx264"
    pixel_format: str = "yuv420p"
    encoder_preset: str = "veryfast"

    def __post_init__(self):
        names = (self.video_filename, self.detections_filename, self.run_filename)
        if len(set(names)) != 3 or any(not n or Path(n).name != n or n in {".", ".."} for n in names):
            raise ValueError("Export filenames must be distinct local basenames")


@dataclass
class CredentialsConfig:
    env_file: str = ".env"


@dataclass
class PipelineConfig:
    model: ModelConfig = field(default_factory=ModelConfig)
    video: VideoConfig = field(default_factory=VideoConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    credentials: CredentialsConfig = field(default_factory=CredentialsConfig)

    def validate(self):
        self.model.__post_init__()
        self.video.__post_init__()
        self.export.__post_init__()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_yaml(cls, path: Path | str) -> PipelineConfig:
        config_path = Path(path).resolve()
        if not config_path.is_file():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        return cls(
            model=ModelConfig(**raw.get("model", {})),
            video=VideoConfig(**raw.get("video", {})),
            export=ExportConfig(**raw.get("export", {})),
            credentials=CredentialsConfig(**raw.get("credentials", {})),
        )

    @classmethod
    def default(cls) -> PipelineConfig:
        return cls()
