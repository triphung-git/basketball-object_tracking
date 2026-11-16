#!/usr/bin/env python3
"""Generate real detection, ball, and player tracking observation caches for negative cohort.

Reads:
  - codebase/assets_test/vietnam-tonga.mp4
  - codebase/scripts/mine_negative_cohort.py (NEGATIVE_COHORT_SPECS)
  - codebase/models/checkpoints/task07a-original/best.pt
Outputs:
  - codebase/outputs/task08-temporal-engine-20261109/negative_cohort/<nid>/
      * raw_detections.jsonl
      * ball_tracks.jsonl
      * tracked_observations.jsonl
      * metadata.json
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from basketball_scoreboard.ball import BallConfig, BallTracker, center
from basketball_scoreboard.config import APPROVED_MODEL_ID
from basketball_scoreboard.identity import RosterConfig, TeamColorClassifier
from basketball_scoreboard.players import PlayerTracker

from mine_negative_cohort import NEGATIVE_COHORT_SPECS


def sanitize_json(val: Any) -> Any:
    if isinstance(val, float):
        return val if math.isfinite(val) else None
    if isinstance(val, dict):
        return {k: sanitize_json(v) for k, v in val.items()}
    if isinstance(val, list):
        return [sanitize_json(v) for v in val]
    return val


def write_jsonl(path: Path | str, rows: List[Dict[str, Any]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(sanitize_json(r), ensure_ascii=False) + "\n")


def write_json(path: Path | str, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sanitize_json(data), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def process_negative_cohort(
    video_path: Path,
    roster_path: Path,
    model_path: Path,
    output_dir: Path,
    limit: Optional[int] = None,
    device: str = "cuda:0",
) -> None:
    from ultralytics import YOLO

    print(f"Loading YOLO model: {model_path} on {device}")
    model = YOLO(str(model_path))

    roster_data = json.loads(roster_path.read_text(encoding="utf-8"))
    roster = RosterConfig.from_dict(roster_data)
    classifier = TeamColorClassifier(
        roster.team_a_id, roster.team_b_id,
        roster.team_a_color_rgb, roster.team_b_color_rgb,
    )

    cap = cv2.VideoCapture(str(video_path))
    video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    video_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920)
    video_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080)
    cap.release()

    specs = NEGATIVE_COHORT_SPECS if limit is None else NEGATIVE_COHORT_SPECS[:limit]
    total_specs = len(specs)
    print(f"Processing {total_specs} negative situations from {video_path.name} (FPS: {video_fps}, {video_w}x{video_h})")

    t_start = time.perf_counter()

    for idx, spec in enumerate(specs, 1):
        nid = spec["negative_id"]
        cat = spec["primary_category"]
        t_bounds = spec["source_time_bounds_s"]
        start_s, end_s = t_bounds[0], t_bounds[1]

        target_dir = output_dir / nid
        raw_det_path = target_dir / "raw_detections.jsonl"
        ball_tr_path = target_dir / "ball_tracks.jsonl"
        track_obs_path = target_dir / "tracked_observations.jsonl"
        meta_path = target_dir / "metadata.json"

        if raw_det_path.is_file() and ball_tr_path.is_file() and track_obs_path.is_file():
            print(f"[{idx}/{total_specs}] {nid} ({cat}): Cache already exists, skipping.")
            continue

        print(f"[{idx}/{total_specs}] {nid} ({cat}): [{start_s:.1f}s - {end_s:.1f}s]...")
        t0 = time.perf_counter()

        # 1. Decode frames
        cap = cv2.VideoCapture(str(video_path))
        start_frame = int(start_s * video_fps)
        end_frame = int(end_s * video_fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        frames = []
        frame_timestamps = []
        f_idx = start_frame
        while f_idx < end_frame:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
            frame_timestamps.append(round(f_idx / video_fps, 4))
            f_idx += 1
        cap.release()

        n_frames = len(frames)
        if n_frames == 0:
            print(f"  Warning: No frames decoded for {nid}")
            continue

        # 2. Run batched YOLO inference
        batch_size = 16
        yolo_results = []
        for b_start in range(0, n_frames, batch_size):
            batch = frames[b_start:b_start + batch_size]
            res = model.predict(batch, device=device, imgsz=640, verbose=False)
            yolo_results.extend(res)

        # 3. Format raw detections
        raw_detections = []
        for loc_idx, (ts, res) in enumerate(zip(frame_timestamps, yolo_results)):
            det_list = []
            for box in res.boxes:
                cls_id = int(box.cls.item())
                cls_name = model.names[cls_id]
                conf = float(box.conf.item())
                xyxy = [round(float(v), 2) for v in box.xyxy[0].tolist()]
                det_list.append({
                    "xyxy": xyxy,
                    "class_id": cls_id,
                    "class_name": cls_name,
                    "confidence": round(conf, 4),
                })
            raw_detections.append({
                "local_frame_index": loc_idx,
                "source_frame_index": start_frame + loc_idx,
                "source_time_s": ts,
                "detections": det_list,
            })

        # 4. Ball Tracking
        ball_config = BallConfig()
        tracker = BallTracker((video_w, video_h), namespace=f"neg:{nid}", config=ball_config)
        ball_tracks = []

        # Simple player tracking
        player_tracker = PlayerTracker(
            video_id=f"neg_{nid}",
            segment_id=nid,
            camera_id="cam_main",
            court_model=None,
            min_hits_to_activate=2,
            max_age_s=1.0,
            original_wh=(video_w, video_h),
        )

        all_player_obs = []

        for loc_idx, (ts, frame, det_rec) in enumerate(zip(frame_timestamps, frames, raw_detections)):
            # Update players
            human_dets = [d for d in det_rec["detections"] if d["class_name"] == "human" and d["confidence"] >= 0.25]
            obs_list = player_tracker.update_frame(loc_idx, ts, "valid", human_dets)
            p_obs = [o.to_dict() for o in obs_list]
            # Classify team colors
            for o in p_obs:
                o["role"] = "player"
                bbox = o.get("bbox", [0, 0, 10, 10])
                x1, y1, x2, y2 = map(int, [max(0, bbox[0]), max(0, bbox[1]), min(video_w, bbox[2]), min(video_h, bbox[3])])
                if x2 > x1 and y2 > y1:
                    crop = frame[y1:y2, x1:x2]
                    ch, cw = crop.shape[:2]
                    torso = crop[int(ch * 0.2):int(ch * 0.6), int(cw * 0.2):int(cw * 0.8)]
                    if torso.size > 0:
                        rgb = (float(np.mean(torso[:, :, 2])), float(np.mean(torso[:, :, 1])), float(np.mean(torso[:, :, 0])))
                        try:
                            tid, tconf, _ = classifier.classify_rgb(rgb)
                            o["team_id"] = tid
                            o["confidence"] = round(tconf, 3)
                        except Exception:
                            o["team_id"] = None
                            o["confidence"] = 0.5
            all_player_obs.extend(p_obs)

            # Update ball
            ball_dets = [d for d in det_rec["detections"] if d["class_name"] == "ball"]
            human_boxes = [o["bbox"] for o in p_obs if o.get("sample_type") == "observed"]
            ball_sample = tracker.update(
                frame_index=loc_idx,
                time_s=ts,
                detections=ball_dets,
                segment=nid,
                human_boxes=human_boxes,
            )
            ball_tracks.append({
                "frame_index": loc_idx,
                "source_time_s": ts,
                "sample_type": ball_sample.get("sample_type", "missing"),
                "confidence": round(ball_sample["confidence"], 4) if ball_sample.get("confidence") is not None else None,
                "center_image": [round(c, 2) for c in ball_sample["center_image"]] if ball_sample.get("center_image") else None,
                "xyxy": [round(v, 2) for v in ball_sample["xyxy"]] if ball_sample.get("xyxy") else None,
            })

        # 5. Write artifacts
        write_jsonl(raw_det_path, raw_detections)
        write_jsonl(ball_tr_path, ball_tracks)
        write_jsonl(track_obs_path, all_player_obs)
        write_json(meta_path, {
            "negative_id": nid,
            "category": cat,
            "time_bounds_s": [start_s, end_s],
            "frames_processed": n_frames,
            "elapsed_seconds": round(time.perf_counter() - t0, 2),
            "created_utc": datetime.now(timezone.utc).isoformat(),
        })

        elapsed = time.perf_counter() - t0
        print(f"    Done {n_frames} frames in {elapsed:.2f}s ({n_frames/elapsed:.1f} FPS)")

    total_time = time.perf_counter() - t_start
    print(f"\nCompleted processing in {total_time:.2f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", default=str(ROOT / "assets_test/vietnam-tonga.mp4"))
    parser.add_argument("--roster", default=str(ROOT / "configs/rosters/vietnam_tonga.json"))
    parser.add_argument("--model", default=str(ROOT / "models/checkpoints/task07a-original/best.pt"))
    parser.add_argument("--output", default=str(ROOT / "outputs/task08-temporal-engine-20261109/negative_cohort"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()

    process_negative_cohort(
        video_path=Path(args.video),
        roster_path=Path(args.roster),
        model_path=Path(args.model),
        output_dir=Path(args.output),
        limit=args.limit,
        device=args.device,
    )
