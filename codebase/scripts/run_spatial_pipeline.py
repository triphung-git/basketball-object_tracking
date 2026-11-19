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
from basketball_scoreboard.court import CourtConfig, CourtModel
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

    continuity = {}
    with tracking_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            time_s = record["source_time_s"]
            tid, index = record.get("track_id"), record.get("frame_index")
            prior = continuity.get(tid)
            observed = record.get("sample_type") == "observed"
            continuous = (observed and prior and prior["observed"] and index is not None
                          and prior["index"] is not None and index == prior["index"] + 1
                          and record.get("segment_id") == prior["segment"])
            start = prior["start"] if continuous else time_s
            continuity[tid] = dict(start=start, index=index, observed=observed, segment=record.get("segment_id"))
            frame = selected.get(int(time_s * 5 + 1e-8))
            if frame is None or frame["time"] != time_s:
                continue
            if record.get("sample_type") == "observed" and record.get("role") != "non_player":
                box_entry = {"box": record["bbox"], "id": record.get("track_id", "")}
                box_entry.update(continuity_start_s=start, sample_type="observed")
                if record.get("segment_id"):
                    box_entry["segment_id"] = record["segment_id"]
                if record.get("role"):
                    box_entry["role"] = record["role"]
                if record.get("team_id"):
                    box_entry["team_id"] = record["team_id"]
                if record.get("player_id"):
                    box_entry["player_id"] = record["player_id"]
                frame["boxes"].append(box_entry)

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
    court_format: str = '3x3',
    automatic_court: bool = True,
) -> dict:
    """Write independent detection/tracking artifacts without event recognition."""
    video = Path(video_path).resolve()
    if not video.is_file():
        raise FileNotFoundError(f"Source video not found: {video}")
    if court_config_path:
        supplied_court = CourtConfig.from_json_file(str(court_config_path))
        # Validate real calibration before expensive inference; diagnostic fixture
        # geometry remains labelled as synthetic in downstream artifacts.
        CourtModel(supplied_court).calibrate(allow_uncalibrated=supplied_court.is_synthetic)

    config = PipelineConfig.default()
    config.model.confidence_threshold = 0.20
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
    timeline = None
    if automatic_court and not court_config_path:
        from basketball_scoreboard.automatic_court import AutomaticCourtTimeline
        timeline = AutomaticCourtTimeline(court_format)
    detection_options = dict(frame_callback=timeline.consume) if timeline else {}

    detection = run_pipeline(
        video,
        detection_dir,
        config=config,
        export_video=False,
        quiet=True,
        progress_callback=progress_callback,
        **detection_options,
    )
    if detection["status"] not in {"completed", "partial"}:
        raise RuntimeError(f"Detection stopped with status {detection['status']}")
    geometry_path = None
    if timeline:
        metadata = detection['video_metadata']
        geometry_path = output / 'automatic_geometry.json'
        geometry_path.write_text(json.dumps(timeline.artifact(detection['source_fingerprint_sha256'],
            metadata['width'], metadata['height'], metadata['fps'])), encoding='utf-8')

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
        **(dict(automatic_geometry_path=geometry_path, team_aware_association=True) if geometry_path else {}),
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
            "geometry_mode": 'automatic' if timeline else 'legacy_manual' if court_config_path else 'unavailable',
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
    if geometry_path:
        from basketball_scoreboard.spatial_analysis import default_config, validate_config, build_spatial_analysis
        from basketball_scoreboard.identity import RosterConfig
        metadata = detection['video_metadata']
        roster = (json.loads(Path(roster_config_path).read_text(encoding='utf-8')) if roster_config_path else
                  RosterConfig('team_a','team_b','Đội A','Đội B',(128,128,128),(128,128,128)).to_dict())
        spatial_config = default_config(dict(source_sha256=detection['source_fingerprint_sha256'], **metadata), roster)
        spatial_config.update(format=court_format, geometry_mode='automatic')
        spatial_config = validate_config(spatial_config,dict(source_sha256=detection['source_fingerprint_sha256'], **metadata))
        (output/'spatial_config.json').write_text(json.dumps(spatial_config),encoding='utf-8')
        spatial = build_spatial_analysis(output, spatial_config, analysis_dir=output, source_video_path=video)
        (output/'spatial_map.json').write_text(json.dumps(spatial), encoding='utf-8')
        (output/'spatial_map_status.json').write_text(json.dumps({k: spatial[k] for k in
            ['status','revision','calibration_segments']}), encoding='utf-8')
        result['spatial']['heatmap_status'] = 'generated' if spatial['quality']['projection_fraction'] else 'unavailable'
        result['outputs']['heatmap'] = 'spatial_map.json' if spatial['quality']['projection_fraction'] else None
        result['outputs']['spatial_map'] = 'spatial_map.json'
        result['outputs']['automatic_geometry'] = 'automatic_geometry.json'
        result['timings']['total_pipeline_s'] = perf_counter()-started
        result['timings']['pipeline_fps'] = detection['counts']['total_frames_read']/result['timings']['total_pipeline_s']
        (output/'run.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result
