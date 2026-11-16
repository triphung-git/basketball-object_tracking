"""CLI video/PTS/detection pipeline. No ground-truth inputs or cloud inference."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import ExitStack
import csv
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import statistics
import sys
import time

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from basketball_scoreboard.config import PipelineConfig
from basketball_scoreboard.contracts import FrameDetectionsRecord, RunMetadata
from basketball_scoreboard.detector import ObjectDetector
from basketball_scoreboard.overlay import draw_detections_overlay
from basketball_scoreboard.video import VideoReader, VideoWriter, probe_video

ROOT = Path(__file__).resolve().parents[2]
logger = logging.getLogger("basketball_scoreboard")


def assert_development_video_allowed(video_sha, root=ROOT, authorization_path=None):
    """Protect reserved footage by content hash, including renamed copies."""
    for data in (root / "data", root / "data/v2"):
        split_path, manifest_path = data / "splits.json", data / "manifest.csv"
        if not split_path.is_file() or not manifest_path.is_file():
            continue
        split = json.loads(split_path.read_text(encoding="utf-8"))
        partitions = split.get("proposed_split", {})
        reserved = {vid for name, partition in partitions.items()
                    if name in {"test", "validation", "reserve", "holdout_v1_preserved"}
                    for vid in partition.get("video_ids", [])}
        with manifest_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
            for row in rows:
                if row["video_id"] in reserved and row.get("sha256") == video_sha:
                    if authorization_path:
                        decision = json.loads(Path(authorization_path).read_text(encoding="utf-8"))
                        siblings = {r.get("sha256") for r in rows if r.get("session_id") == row.get("session_id")}
                        if (decision.get("review_status") == "approved" and decision.get("approved_by") == "user"
                                and decision.get("scope") == "task07_development_only"
                                and decision.get("allowed_video_sha256") == video_sha
                                and decision.get("independent_holdout_eligible") is False
                                and decision.get("decision_id") and decision.get("user_decision")
                                and siblings <= set(decision.get("exposed_group_sha256", []))):
                            continue
                    raise ValueError("Reserved footage cannot be used by the development pipeline")


def run_pipeline(video_path, output_dir, config=None, export_video=True, quiet=False, development_authorization=None, detector_factory=None):
    cfg = config or PipelineConfig.default()
    cfg.validate()  # Revalidate dataclasses after CLI/programmatic overrides.
    input_path = Path(video_path).resolve()
    if not input_path.is_file():
        raise FileNotFoundError("Input video does not exist")
    out_dir = Path(output_dir).resolve()
    if out_dir == input_path.parent or input_path.is_relative_to(out_dir):
        raise ValueError("Output cannot contain the input source")
    out_dir.mkdir(parents=True, exist_ok=False)

    started = time.perf_counter()
    created = datetime.now(timezone.utc).isoformat()
    status, error_code, stage = "running", None, "probe"
    metadata, runtime = None, {}
    frame_count = written = total_detections = 0
    class_counts, timestamp_counts = Counter(), Counter()
    model_times = []
    timings = {"decode_s": 0.0, "detection_total_s": 0.0, "draw_total_s": 0.0, "write_total_s": 0.0}
    failure = None
    authorization_snapshot = None
    try:
        metadata = probe_video(input_path)
        assert_development_video_allowed(metadata.sha256, authorization_path=development_authorization)
        if development_authorization:
            authorization_snapshot = json.loads(Path(development_authorization).read_text(encoding="utf-8"))
        stage = "model_init"
        env_file = Path(cfg.credentials.env_file)
        if not env_file.is_absolute():
            env_file = ROOT / env_file
        detector = (detector_factory or ObjectDetector)(cfg.model, env_path=env_file)
        detector.warmup()
        runtime = detector.get_runtime_info()
        stage = "processing"
        with ExitStack() as stack:
            reader = stack.enter_context(VideoReader(input_path, cfg.video.pts_policy, cfg.video.max_frames))
            writer = stack.enter_context(VideoWriter(
                out_dir / cfg.export.video_filename, metadata.width, metadata.height, metadata.fps,
                codec=cfg.export.codec, pix_fmt=cfg.export.pixel_format, preset=cfg.export.encoder_preset)) if export_video else None
            handle = stack.enter_context((out_dir / cfg.export.detections_filename).open("x", encoding="utf-8"))
            previous = time.perf_counter()
            for frame, image in reader.frames():
                timings["decode_s"] += time.perf_counter() - previous
                begin = time.perf_counter()
                detections, model_ms = detector.detect(image, cfg.model.confidence_threshold)
                timings["detection_total_s"] += time.perf_counter() - begin
                model_times.append(model_ms)
                total_detections += len(detections)
                class_counts.update(d.class_name for d in detections)
                timestamp_counts.update([frame.timestamp_status])
                record = FrameDetectionsRecord(
                    video_id=frame.video_id, frame_index=frame.frame_index, source_time_s=frame.source_time_s,
                    original_wh=frame.original_wh, detections=detections, raw_pts=frame.raw_pts,
                    time_base=frame.time_base, timestamp_status=frame.timestamp_status,
                    timestamp_policy=frame.timestamp_policy, model_call_ms=model_ms)
                handle.write(record.to_jsonl() + "\n")
                if writer is not None:
                    begin = time.perf_counter()
                    annotated = draw_detections_overlay(image, detections, frame) if cfg.video.draw_overlay else image
                    timings["draw_total_s"] += time.perf_counter() - begin
                    begin = time.perf_counter()
                    writer.write_frame(annotated, source_time_s=frame.source_time_s)
                    timings["write_total_s"] += time.perf_counter() - begin
                    written += 1
                frame_count += 1
                if not quiet and frame_count % 50 == 0:
                    logger.info("Processed %d frames | elapsed %.1fs", frame_count, time.perf_counter() - started)
                previous = time.perf_counter()
        if frame_count == 0:
            raise ValueError("No frames decoded")
        status = "partial" if cfg.video.max_frames is not None and frame_count < metadata.nb_frames else "completed"
    except (Exception, KeyboardInterrupt) as exc:
        status = "cancelled" if isinstance(exc, KeyboardInterrupt) else "failed"
        # No exception messages/chained tracebacks: SDK URLs may contain API keys.
        error_code = type(exc).__name__
        failure = error_code
        logger.error("Run stopped at %s (%s)", stage, error_code)

    elapsed = time.perf_counter() - started
    mean_ms = statistics.mean(model_times) if model_times else 0.0
    result = RunMetadata(
        run_id=out_dir.name, status=status, video_path=str(input_path),
        video_id=metadata.video_id if metadata else input_path.stem,
        source_fingerprint_sha256=metadata.sha256 if metadata else "",
        video_metadata=metadata.to_dict() if metadata else {}, config=cfg.to_dict(), runtime=runtime,
        class_mapping=runtime.get("class_mapping", {}),
        counts={"total_frames_read": frame_count, "total_frames_written": written,
                "total_detections": total_detections, "detections_by_class": dict(class_counts),
                "timestamp_status": dict(timestamp_counts)},
        timings={**{k: round(v, 4) for k, v in timings.items()}, "total_pipeline_s": round(elapsed, 4),
                 "init_s": runtime.get("init_s"), "model_call_median_ms": statistics.median(model_times) if model_times else 0.0,
                 "model_call_mean_ms": mean_ms, "pipeline_fps": frame_count / elapsed if elapsed else 0.0},
        timing_scope="Model call includes runtime pre/postprocessing. Pipeline includes probe, model init/warmup, decode, resize, drawing, JSONL, encoding and encoder flush.",
        export={"video_output_path": str(out_dir / cfg.export.video_filename) if export_video else None,
                "detections_jsonl_path": str(out_dir / cfg.export.detections_filename),
                "run_json_path": str(out_dir / cfg.export.run_filename), "nominal_fps": metadata.fps if metadata else None,
                "timestamp_policy": "explicit_normalized_source_timestamps", "time_base": "1/1000000",
                "preserved_vfr_mapping": bool(export_video and status in {"completed", "partial"}
                    and not any(timestamp_counts.get(s, 0) for s in ("estimated", "repaired", "irregular")))},
        created_utc=created, completed_utc=datetime.now(timezone.utc).isoformat(),
        error_message=f"{stage}:{error_code}" if error_code else None).to_dict()
    if authorization_snapshot:
        result["development_authorization"] = authorization_snapshot
    (out_dir / cfg.export.run_filename).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if failure:
        raise RuntimeError(f"Pipeline failed at {stage} ({failure}); see run.json") from None
    return result


def main():
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--confidence", type=float)
    parser.add_argument("--max-edge", type=int)
    parser.add_argument("--pts-policy", choices=["repair_with_audit", "strict_reject", "flag_only"])
    parser.add_argument("--max-frames", type=int)
    parser.add_argument("--no-video-export", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--development-authorization", type=Path)
    args = parser.parse_args()
    try:
        cfg = PipelineConfig.from_yaml(args.config or ROOT / "configs/default.yaml")
        if args.confidence is not None:
            cfg.model.confidence_threshold = args.confidence
        if args.max_edge is not None:
            cfg.model.max_edge = args.max_edge
        if args.pts_policy is not None:
            cfg.video.pts_policy = args.pts_policy
        if args.max_frames is not None:
            cfg.video.max_frames = args.max_frames
        cfg.validate()
        output = args.output_dir or ROOT / "outputs" / ("run-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
        result = run_pipeline(args.video, output, cfg, export_video=not args.no_video_export, quiet=args.quiet,
                              development_authorization=args.development_authorization)
        print(f"Run {result['status']}: {result['counts']['total_frames_read']} frames; {result['timings']['pipeline_fps']:.2f} pipeline FPS")
        print(f"Artifacts: {output}")
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        print(f"Pipeline failed ({type(exc).__name__}); inspect sanitized run metadata if created", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
