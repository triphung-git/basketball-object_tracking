#!/usr/bin/env python3
"""Render real annotated video overlay with bounding boxes, tracking, and telemetry (Task D08)."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import sys
import time

import av
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from basketball_scoreboard.video import VideoReader, VideoWriter, probe_video
from basketball_scoreboard.contracts import DetectionRecord, FrameRecord
from basketball_scoreboard.overlay import draw_detections_overlay


def render_overlay_video(
    video_path: Path | str,
    output_path: Path | str,
    run_dir: Path | str,
    start_time_s: float = 300.0,
    end_time_s: float = 305.0,
    max_frames: int = 150,
) -> Path:
    vid_file = Path(video_path).resolve()
    out_file = Path(output_path).resolve()
    run_p = Path(run_dir).resolve()

    if not vid_file.is_file():
        raise FileNotFoundError(f"Source video not found: {vid_file}")
    if out_file.exists():
        raise FileExistsError(f"Output already exists; overwrite prohibited: {out_file}")
    if end_time_s < start_time_s or max_frames <= 0:
        raise ValueError("Invalid rendering time range or frame limit")

    meta = probe_video(vid_file)

    # Load detections and tracks from run_dir
    detections_by_frame = {}
    dets_file = run_p / "detections.jsonl"
    if dets_file.is_file():
        for line in dets_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            f_idx = rec.get("frame_index")
            t_s = rec.get("source_time_s", 0.0)
            if start_time_s <= t_s <= end_time_s:
                dets = []
                for d in rec.get("detections", []):
                    dets.append(DetectionRecord(
                        xyxy=tuple(d["xyxy"]),
                        confidence=float(d["confidence"]),
                        class_name=d["class_name"],
                        class_id=int(d["class_id"]),
                    ))
                detections_by_frame[round(t_s, 6)] = dets

    # Load events from run_dir for telemetry badge
    events_summary = []
    events_file = run_p / "events_auto.jsonl"
    if events_file.is_file():
        for line in events_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events_summary.append(json.loads(line))

    # Read and render frames
    container = av.open(str(vid_file))
    stream = container.streams.video[0]
    fps = float(stream.average_rate or stream.guessed_rate or 30.0)
    time_base = stream.time_base or av.time_base

    start_pts = int(round(start_time_s / float(time_base)))
    end_pts = int(round(end_time_s / float(time_base)))

    container.seek(start_pts, stream=stream)

    frames_written = 0
    with VideoWriter(out_file, meta.width, meta.height, fps) as writer:
        for packet in container.demux(stream):
            for frame in packet.decode():
                if frame.pts is None:
                    continue
                t_s = float(frame.pts * time_base)
                if t_s < start_time_s:
                    continue
                if t_s > end_time_s or frames_written >= max_frames:
                    container.close()
                    return out_file

                frame_idx = int(round(t_s * fps))
                bgr = frame.to_ndarray(format="bgr24")
                dets = detections_by_frame.get(round(t_s, 6), [])

                frame_rec = FrameRecord(
                    video_id=meta.video_id,
                    frame_index=frame_idx,
                    source_time_s=t_s,
                    original_wh=(meta.width, meta.height),
                    raw_pts=frame.pts,
                    time_base=str(time_base),
                    timestamp_status="valid",
                    timestamp_policy="repair_with_audit",
                )

                annotated = draw_detections_overlay(
                    bgr_frame=bgr,
                    detections=dets,
                    frame_record=frame_rec,
                    show_telemetry=True,
                )

                # Draw Event Badge if event occurs nearby
                for ev in events_summary:
                    ev_t = ev.get("source_time_s", 0.0)
                    if abs(t_s - ev_t) <= 1.0:
                        ev_text = f"EVENT: {ev.get('event_type').upper()} ({ev.get('subtype')}) [{ev.get('team_id')}]"
                        cv2.putText(
                            annotated,
                            ev_text,
                            (12, meta.height - 30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7,
                            (0, 255, 255),
                            2,
                            cv2.LINE_AA,
                        )

                # Standalone clips must start at zero; event/source clocks stay
                # absolute in run.json and are mapped by the dashboard.
                writer.write_frame(annotated, t_s - start_time_s)
                frames_written += 1

    container.close()
    return out_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", default="codebase/assets_test/vietnam-tonga.mp4", help="Video path")
    parser.add_argument("--run-dir", default="codebase/outputs/demo-completion-20261116/D05/run", help="Run directory")
    parser.add_argument("--output", default="codebase/outputs/demo-completion-20261116/D08/annotated.mp4", help="Output MP4")
    parser.add_argument("--start", type=float, default=300.0, help="Start time in seconds")
    parser.add_argument("--end", type=float, default=305.0, help="End time in seconds")
    parser.add_argument("--max-frames", type=int, default=150, help="Max frames to render")
    args = parser.parse_args()

    out = render_overlay_video(
        video_path=args.video,
        output_path=args.output,
        run_dir=args.run_dir,
        start_time_s=args.start,
        end_time_s=args.end,
        max_frames=args.max_frames,
    )
    print(f"Annotated video successfully rendered to: {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
