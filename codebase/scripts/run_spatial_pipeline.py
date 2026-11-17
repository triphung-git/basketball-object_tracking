"""Run detection, human tracking and optional court heatmap generation."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from time import perf_counter

CODEBASE_ROOT = Path(__file__).resolve().parents[1]
if str(CODEBASE_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(CODEBASE_ROOT / "src"))
if str(CODEBASE_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(CODEBASE_ROOT / "scripts"))

from basketball_scoreboard.app import run_pipeline
from basketball_scoreboard.config import PipelineConfig
from generate_heatmap import generate_heatmap_pipeline
from track_players import track_players_pipeline


def _build_tracking_overlay(detections_path: Path, tracking_path: Path, output_path: Path) -> None:
    selected = {}
    # Select on the source frame clock, including frames without human tracks.
    # Otherwise an old box can linger into an empty frame or a prediction can
    # select a different source frame than the ball/rim detections.
    with detections_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            time_s = record["source_time_s"]
            bucket = int(time_s * 5 + 1e-8)
            frame = selected.setdefault(bucket, {"time": time_s, "boxes": []})
            if frame["time"] != time_s:
                continue
            for detection in record.get("detections", []):
                if detection.get("class_name") in {"ball", "rim"}:
                    frame["boxes"].append({"box": detection["xyxy"], "kind": detection["class_name"]})

    with tracking_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            time_s = record["source_time_s"]
            frame = selected.get(int(time_s * 5 + 1e-8))
            if frame is None or frame["time"] != time_s:
                continue
            if record.get("sample_type") == "observed" and record.get("role") != "non_player":
                frame["boxes"].append({"box": record["bbox"], "id": record.get("track_id", "")})

    frames = sorted(selected.values(), key=lambda frame: frame["time"])
    output_path.write_text(json.dumps({"frames": frames}), encoding="utf-8")


def run_spatial_pipeline(
    video_path: Path | str,
    output_dir: Path | str,
    *,
    court_config_path: Path | str | None = None,
    tracking_policy_path: Path | str | None = None,
    roster_config_path: Path | str | None = None,
    max_frames: int | None = None,
    progress_callback=None,
) -> dict:
    """Write independent detection/tracking artifacts without event recognition."""
    video = Path(video_path).resolve()
    if not video.is_file():
        raise FileNotFoundError(f"Source video not found: {video}")

    config = PipelineConfig.default()
    config.video.max_frames = max_frames
    config.validate()
    output = Path(output_dir).resolve()
    for source in (video, court_config_path, tracking_policy_path, roster_config_path):
        if source and Path(source).resolve().is_relative_to(output):
            raise ValueError("Output cannot contain input sources")
    output.mkdir(parents=True, exist_ok=False)
    started = perf_counter()
    detection_dir = output / "detection"
    tracking_dir = output / "tracking"

    detection = run_pipeline(
        video,
        detection_dir,
        config=config,
        export_video=False,
        quiet=True,
        progress_callback=progress_callback,
    )
    if detection["status"] not in {"completed", "partial"}:
        raise RuntimeError(f"Detection stopped with status {detection['status']}")

    tracking_code = track_players_pipeline(
        detection_dir / config.export.detections_filename,
        tracking_dir,
        court_config_path=court_config_path,
        roster_config_path=roster_config_path,
        run_json_path=detection_dir / config.export.run_filename,
        allow_uncalibrated=True,
        video_path=video if roster_config_path else None,
        tracking_policy=tracking_policy_path,
        enable_ocr=False,
        progress_callback=progress_callback,
    )
    if tracking_code != 0:
        raise RuntimeError(f"Human tracking failed with exit code {tracking_code}")
    _build_tracking_overlay(
        detection_dir / config.export.detections_filename,
        tracking_dir / "tracked_observations.jsonl",
        output / "web_overlay.json",
    )

    heatmap_status = "unavailable"
    if court_config_path:
        heatmap_dir = output / "heatmap"
        heatmap_code = generate_heatmap_pipeline(
            court_config_path,
            tracking_dir / "tracked_observations.jsonl",
            heatmap_dir,
            run_json_path=detection_dir / config.export.run_filename,
            allow_uncalibrated=True,
        )
        if heatmap_code != 0:
            raise RuntimeError(f"Heatmap generation failed with exit code {heatmap_code}")
        heatmap_status = "generated"

    tracking = json.loads((tracking_dir / "tracking_summary.json").read_text(encoding="utf-8"))
    result = {
        "status": detection["status"],
        "video_path": str(video),
        "video_id": detection["video_id"],
        "source_fingerprint_sha256": detection["source_fingerprint_sha256"],
        "video_metadata": detection["video_metadata"],
        "counts": detection["counts"],
        "timings": detection["timings"],
        "spatial": {
            "tracking_status": tracking["status"],
            "tracks": tracking["total_tracks_initiated"],
            "observations": tracking["total_observations_generated"],
            "heatmap_status": heatmap_status,
        },
        "outputs": {
            "detections": "detection/detections.jsonl",
            "tracking": "tracking/tracked_observations.jsonl",
            "heatmap": "heatmap" if heatmap_status == "generated" else None,
        },
    }
    elapsed = perf_counter() - started
    result["timings"] = {
        **detection["timings"],
        "detection_pipeline_s": detection["timings"].get("total_pipeline_s"),
        "total_pipeline_s": elapsed,
        "pipeline_fps": detection["counts"]["total_frames_read"] / elapsed,
    }
    (output / "run.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
