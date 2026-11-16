"""Bind physical court geometry to its reviewed video and segment scope."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .court import CourtConfig, CourtModel, UncalibratedCourtError

ROOT = Path(__file__).resolve().parents[2]


def load_bound_court(
    path, source_sha, metadata, start_time_s=None, end_time_s=None,
    max_frames=None, allow_uncalibrated=True,
):
    """Return a physical model only when the entire requested range is bound.

    Parent-video reuse follows the existing segment manifest and dataset source
    hash; nearby timestamps alone never authorize a calibration.
    """
    if not path:
        return None, None, "none"
    config = CourtConfig.from_json_file(str(path))
    model = CourtModel(config)
    model.calibrate(allow_uncalibrated=allow_uncalibrated)
    valid = (
        model._is_calibrated and not config.is_synthetic
        and config.status == "validated"
        and config.original_image_wh == (metadata.width, metadata.height)
        and bool(config.source_video_hash)
    )
    if valid and config.source_video_hash != source_sha:
        valid = False
        manifest_path = ROOT / "data/v2/manifest.csv"
        if manifest_path.is_file():
            with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
                segment_ids = {row["video_id"] for row in csv.DictReader(handle)
                               if row["sha256"] == config.source_video_hash}
            start = start_time_s if start_time_s is not None else 0.0
            end = end_time_s if end_time_s is not None else metadata.duration_s
            if max_frames is not None:
                end = min(end, start + max_frames / metadata.fps)
            for segment_path in (ROOT / "configs/segments").glob("*.json"):
                data = json.loads(segment_path.read_text(encoding="utf-8"))
                if data.get("parent_sha256") != source_sha:
                    continue
                for segment in data.get("segments", []):
                    if segment["segment_id"] in segment_ids:
                        valid = segment["start_s"] <= start <= end <= segment["start_s"] + segment["duration_s"]
                        if valid:
                            break
                if valid:
                    break
    if not valid:
        if not allow_uncalibrated:
            raise UncalibratedCourtError("Court calibration does not match source, dimensions or requested time scope")
        return None, config, "uncalibrated_diagnostic"
    return model, config, "calibrated"
