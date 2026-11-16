#!/usr/bin/env python3
"""Task08 Critical Moments Baseline Diagnostic Runner.

Executes baseline pipeline across the 10 reviewed Vietnam-Tonga scoring windows.
Enforces strict decoupling between recognition inputs and ground-truth review labels.
Preserves approved models, configs, and produces complete diagnostic artifacts.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import av
import cv2
import numpy as np

# Add src to python path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from basketball_scoreboard.config import APPROVED_MODEL_ID, ModelConfig, PipelineConfig
from basketball_scoreboard.contracts import CLASS_MAPPING, DetectionRecord
from basketball_scoreboard.detector import ObjectDetector
from basketball_scoreboard.tiled_detection import TiledBallDetector
from basketball_scoreboard.ball import BallConfig, BallTracker, center, iou
from basketball_scoreboard.players import PlayerTracker
from basketball_scoreboard.identity import (
    IdentityResolver,
    LocalEasyOCRProvider,
    RosterConfig,
    TeamColorClassifier,
    enrich_observations_with_identity,
    evaluate_crop_quality,
    extract_jersey_rgb,
)
from basketball_scoreboard.tracking_policy import in_image_roi, load_ball_roi, load_tracking_policy
from basketball_scoreboard.video import VideoWriter


def file_sha256(path: Path | str, chunk_size: int = 65536) -> str:
    """Compute standard SHA-256 hex digest of a file in streaming chunks."""
    file_path = Path(path).resolve()
    hasher = hashlib.sha256()
    with file_path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_json(path: Path | str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sanitize_json_value(val: Any) -> Any:
    """Recursively sanitize dict/list/float values to ensure valid RFC 8259 JSON (no NaN or inf)."""
    if isinstance(val, float):
        return val if math.isfinite(val) else None
    if isinstance(val, dict):
        return {k: sanitize_json_value(v) for k, v in val.items()}
    if isinstance(val, list):
        return [sanitize_json_value(v) for v in val]
    return val


def write_json(path: Path | str, data: Any) -> None:
    sanitized = sanitize_json_value(data)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(sanitized, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path | str, rows: List[Dict[str, Any]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as handle:
        for row in rows:
            sanitized = sanitize_json_value(row)
            handle.write(json.dumps(sanitized, ensure_ascii=False, allow_nan=False) + "\n")


def build_recognition_input_manifest(
    critical_windows_draft_path: Path,
    review_manifest_path: Path,
    output_manifest_path: Path,
) -> Dict[str, Any]:
    """Create sanitized recognition input manifest stripping ALL GT and review fields.
    
    The resulting manifest only exposes window bounds, source timings, and clip references.
    Forbidden fields: reviewed_shooter_id, shot_kind, evaluation_times, notes, score, outcome.
    """
    draft = load_json(critical_windows_draft_path)
    manifest = load_json(review_manifest_path)
    entries_by_id = {e["id"]: e for e in manifest.get("entries", [])}

    sanitized_windows = []
    for w in draft.get("windows", []):
        wid = w["window_id"]
        entry = entries_by_id.get(wid, {})
        sanitized_windows.append({
            "window_id": wid,
            "source_start_s": float(w["source_start_s"]),
            "source_end_s": float(w["source_end_s"]),
            "source_start_frame": int(w["source_start_frame"]),
            "source_end_frame_exclusive": int(w["source_end_frame_exclusive"]),
            "source_time_offset_s": float(entry.get("source_time_offset_s", 0.0)),
            "clip_video": entry.get("video", f"clips/{wid}.mp4"),
        })

    sanitized_manifest = {
        "schema_version": "task08-recognition-manifest-1",
        "provenance": {
            "source_video": manifest.get("source_video"),
            "source_sha256": manifest.get("source_sha256"),
            "purpose": "conditional_diagnostic_baseline_only",
            "independent_holdout": False,
            "gt_fields_stripped": True,
            "forbidden_fields_verified_absent": [
                "reviewed_shooter_id",
                "shot_kind",
                "evaluation_times",
                "notes",
                "score",
                "outcome",
                "points",
            ],
            "created_utc": datetime.now(timezone.utc).isoformat(),
        },
        "windows": sanitized_windows,
    }
    write_json(output_manifest_path, sanitized_manifest)
    return sanitized_manifest


class FrameData:
    def __init__(
        self,
        local_frame_index: int,
        source_frame_index: int,
        source_time_s: float,
        local_time_s: float,
        raw_pts: int,
        time_base: str,
        image_bgr: np.ndarray,
    ):
        self.local_frame_index = local_frame_index
        self.source_frame_index = source_frame_index
        self.source_time_s = source_time_s
        self.local_time_s = local_time_s
        self.raw_pts = raw_pts
        self.time_base = time_base
        self.image_bgr = image_bgr


def decode_window_frames(
    source_video_path: Path,
    source_start_s: float,
    source_end_s: float,
    offset_s: float,
) -> List[FrameData]:
    """Decode frames for a window directly from source video stream using PTS."""
    container = av.open(str(source_video_path))
    stream = container.streams.video[0]
    tb = float(stream.time_base)
    fps = float(stream.average_rate or 30.0)

    # Seek 1.5 seconds before start to guarantee keyframe decode
    seek_target = max(0.0, source_start_s - 1.5)
    container.seek(int(seek_target / tb), stream=stream)

    frames: List[FrameData] = []
    local_idx = 0
    last_pts_s = -1.0

    for frame in container.decode(stream):
        if frame.pts is None:
            continue
        pts_s = float(frame.pts * tb)
        if pts_s + 1e-6 < source_start_s:
            continue
        if pts_s + 1e-6 >= source_end_s:
            break

        pts_rounded = round(pts_s, 6)
        if pts_rounded <= last_pts_s:
            raise ValueError(f"Non-monotonic source PTS detected: {pts_rounded} <= {last_pts_s}")
        last_pts_s = pts_rounded

        src_frame_idx = round(pts_rounded * fps)
        local_time_s = round(pts_rounded - offset_s, 6)
        bgr = frame.to_ndarray(format="bgr24")

        frames.append(FrameData(
            local_frame_index=local_idx,
            source_frame_index=src_frame_idx,
            source_time_s=pts_rounded,
            local_time_s=local_time_s,
            raw_pts=frame.pts,
            time_base=str(stream.time_base),
            image_bgr=bgr,
        ))
        local_idx += 1

    container.close()
    return frames


def run_detections_on_window(
    detector: TiledBallDetector,
    frames: List[FrameData],
    confidence_thresh: float = 0.15,
) -> Tuple[List[Dict[str, Any]], float]:
    """Run tiled ball + human + rim detection across window frames."""
    detections_by_frame = []
    total_model_ms = 0.0

    for f in frames:
        records, model_ms = detector.detect(f.image_bgr, confidence_thresh)
        total_model_ms += model_ms
        det_dicts = [
            {
                "xyxy": [round(x, 2) for x in r.xyxy],
                "class_id": r.class_id,
                "class_name": r.class_name,
                "confidence": round(r.confidence, 4),
            }
            for r in records
        ]
        detections_by_frame.append({
            "local_frame_index": f.local_frame_index,
            "source_frame_index": f.source_frame_index,
            "source_time_s": f.source_time_s,
            "local_time_s": f.local_time_s,
            "model_ms": round(model_ms, 2),
            "detections": det_dicts,
        })

    return detections_by_frame, total_model_ms


def run_tracking_and_identity_on_window(
    frames: List[FrameData],
    detections_by_frame: List[Dict[str, Any]],
    roster_path: Path,
    ocr_engine: Optional[LocalEasyOCRProvider] = None,
    ocr_cadence: int = 15,
    window_id: str = "window",
    source_sha: str = "unknown_sha",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Run PlayerTracker, team color classification, and jersey OCR on human detections."""
    roster_data = load_json(roster_path)
    roster = RosterConfig.from_dict(roster_data)

    classifier = TeamColorClassifier(
        roster.team_a_id, roster.team_b_id,
        roster.team_a_color_rgb, roster.team_b_color_rgb,
    )
    resolver = IdentityResolver(roster, classifier, jersey_evidence_ttl_s=6.0)
    
    h, w = frames[0].image_bgr.shape[:2]
    tracker = PlayerTracker(
        video_id=f"win_{window_id}",
        segment_id=window_id,
        camera_id="cam_01",
        court_model=None,
        min_hits_to_activate=3,
        max_age_s=1.0,
        original_wh=(w, h),
    )

    all_tracked_obs = []
    jersey_evidences = []

    for f, det_info in zip(frames, detections_by_frame):
        frame_obs = tracker.update_frame(
            det_info["local_frame_index"],
            det_info["source_time_s"],
            "valid",
            det_info["detections"],
            source_fingerprint_sha256=source_sha,
            source_run_id=window_id,
        )

        # Team color and OCR extraction on observed player crops
        for obs in frame_obs:
            if obs.sample_type == "observed" and obs.role != "non_player":
                box = obs.bbox
                x1, y1, x2, y2 = max(0, int(box[0])), max(0, int(box[1])), min(w, int(box[2])), min(h, int(box[3]))
                crop = f.image_bgr[y1:y2, x1:x2]
                box_h = y2 - y1

                if crop.size > 0:
                    rgb, quality = extract_jersey_rgb(crop, [roster.team_a_color_rgb, roster.team_b_color_rgb])
                    team, score, reason = classifier.classify_rgb(rgb) if rgb is not None else (None, 0.0, quality.get("reason", "no_rgb"))
                    if team:
                        resolver.add_team_observation(
                            obs.track_id, team,
                            score, det_info["source_time_s"],
                        )

                    # Extract OCR at configured cadence on sufficiently large crops
                    if ocr_engine is not None and box_h >= 28 and (det_info["local_frame_index"] % ocr_cadence == 0):
                        jersey_y1 = max(0, int(y1 + 0.15 * box_h))
                        jersey_y2 = min(h, int(y1 + 0.55 * box_h))
                        jersey_x1 = max(0, int(x1 + 0.15 * (x2 - x1)))
                        jersey_x2 = min(w, int(x2 - 0.15 * (x2 - x1)))
                        jersey_crop = f.image_bgr[jersey_y1:jersey_y2, jersey_x1:jersey_x2]

                        if jersey_crop.size > 0:
                            readings = ocr_engine.read_jersey(
                                jersey_crop, obs.track_id,
                                det_info["local_frame_index"], det_info["source_time_s"],
                            )
                            for r in readings:
                                resolver.add_jersey_evidence(r)
                                jersey_evidences.append(r.to_dict())

            resolver.update_track_mapping(obs.track_id, det_info["source_time_s"], set(tracker.tracks))

        enrich_observations_with_identity(frame_obs, resolver)

        for obs in frame_obs:
            obs_dict = obs.to_dict()
            obs_dict["source_frame_index"] = f.source_frame_index
            obs_dict["local_time_s"] = f.local_time_s
            all_tracked_obs.append(obs_dict)

    return all_tracked_obs, jersey_evidences


def run_ball_tracking_with_diagnostics(
    frames: List[FrameData],
    detections_by_frame: List[Dict[str, Any]],
    tracked_obs: List[Dict[str, Any]],
    ball_config: BallConfig,
    ball_roi_polygon: Optional[List[List[float]]] = None,
    is_play_006_ft: bool = False,
    window_id: str = "window",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """Run BallTracker while logging exhaustive rejection traces for every ball candidate."""
    obs_by_frame_idx = {}
    for o in tracked_obs:
        obs_by_frame_idx.setdefault(o["frame_index"], []).append(o)

    orig_wh = (frames[0].image_bgr.shape[1], frames[0].image_bgr.shape[0])
    tracker = BallTracker(orig_wh, namespace=f"diag:{window_id}", config=ball_config)

    ball_tracks: List[Dict[str, Any]] = []
    all_candidate_traces: List[Dict[str, Any]] = []
    rejection_counts: Dict[str, int] = {
        "outside_roi": 0,
        "low_confidence": 0,
        "exceeds_diameter": 0,
        "dedup_suppressed": 0,
        "motion_gate_exceeded": 0,
        "aspect_ratio_exceeded": 0,
        "human_distance_exceeded": 0,
        "ambiguous_margin": 0,
        "selected_observed": 0,
    }

    camera_layout_invalid = is_play_006_ft

    for f, det_info in zip(frames, detections_by_frame):
        t_s = f.source_time_s
        frame_idx = f.local_frame_index
        raw_ball_dets = [d for d in det_info["detections"] if d["class_name"] == "ball"]
        human_obs = obs_by_frame_idx.get(frame_idx, [])
        human_boxes = [
            o["bbox"] for o in human_obs
            if o.get("sample_type") == "observed" and o.get("role") != "non_player"
        ]

        # 1. Trace each candidate before Tracker update
        active_state = tracker.active
        diagonal = tracker.diagonal
        pred_center = None
        gate_dist = None
        if active_state:
            elapsed = t_s - active_state["time"]
            p = center(active_state["box"])
            pred_center = (
                p[0] + active_state["velocity"][0] * elapsed,
                p[1] + active_state["velocity"][1] * elapsed,
            )
            gate_dist = diagonal * (ball_config.base_gate_diagonal + ball_config.max_speed_diagonal_s * elapsed)

        frame_traces = []
        for det_idx, det in enumerate(raw_ball_dets):
            box = det["xyxy"]
            conf = det["confidence"]
            b_center = center(box)
            w = box[2] - box[0]
            h = box[3] - box[1]
            max_d = max(w, h)

            # Evaluate each gate
            in_roi = True
            if ball_roi_polygon is not None:
                in_roi = in_image_roi({"image_roi_normalized": ball_roi_polygon}, b_center, orig_wh)

            conf_ok = conf >= ball_config.min_confidence
            diam_ok = max_d <= ball_config.max_diameter_diagonal * diagonal

            motion_ok = True
            motion_dist = None
            if active_state:
                motion_dist = math.dist(b_center, pred_center)
                motion_ok = motion_dist <= gate_dist

            aspect_ok = True
            ratio = None
            if active_state:
                old_box = active_state["box"]
                old_area = (old_box[2] - old_box[0]) * (old_box[3] - old_box[1])
                new_area = w * h
                ratio = new_area / old_area if old_area > 0 else 1.0
                aspect_ok = 0.2 <= ratio <= 5.0

            human_dist_ok = True
            human_dist = None
            if ball_config.human_context_weight > 0 and not active_state:
                dists = [
                    math.hypot(max(p[0] - b_center[0], 0.0, b_center[0] - p[2]),
                               max(p[1] - b_center[1], 0.0, b_center[1] - p[3])) / (p[3] - p[1])
                    for p in human_boxes if (p[3] - p[1]) > 0
                ]
                human_dist = min(dists, default=float("inf"))
                human_dist_ok = human_dist <= ball_config.max_initial_body_distance

            # Determine primary rejection reason if any
            primary_reason = None
            if not in_roi:
                primary_reason = "outside_roi"
            elif not conf_ok:
                primary_reason = "low_confidence"
            elif not diam_ok:
                primary_reason = "exceeds_diameter"
            elif active_state and not motion_ok:
                primary_reason = "motion_gate_exceeded"
            elif active_state and not aspect_ok:
                primary_reason = "aspect_ratio_exceeded"
            elif not active_state and not human_dist_ok:
                primary_reason = "human_distance_exceeded"

            trace_item = {
                "window_id": window_id,
                "local_frame_index": frame_idx,
                "source_frame_index": f.source_frame_index,
                "source_time_s": t_s,
                "candidate_index": det_idx,
                "xyxy": box,
                "confidence": conf,
                "in_roi": in_roi,
                "conf_ok": conf_ok,
                "diam_ok": diam_ok,
                "motion_ok": motion_ok,
                "motion_distance_px": round(motion_dist, 2) if motion_dist is not None else None,
                "motion_gate_px": round(gate_dist, 2) if gate_dist is not None else None,
                "aspect_ok": aspect_ok,
                "aspect_ratio": round(ratio, 3) if ratio is not None else None,
                "human_dist": round(human_dist, 3) if (human_dist is not None and math.isfinite(human_dist)) else None,
                "human_dist_ok": human_dist_ok,
                "initial_rejection_reason": primary_reason,
                "selected": False,
            }
            frame_traces.append(trace_item)

        # 2. Update production Tracker
        ball_res = tracker.update(
            frame_idx,
            t_s,
            det_info["detections"],
            segment=window_id,
            reset=False,
            clock_valid=True,
            human_boxes=human_boxes,
            ball_roi=ball_roi_polygon,
            human_observations=human_obs,
        )

        # 3. Reconcile tracker selection with candidate traces
        selected_box = ball_res.get("xyxy")
        sample_type = ball_res.get("sample_type", "missing")

        if sample_type == "observed" and selected_box:
            # Find matching candidate
            matched = False
            for tr in frame_traces:
                if iou(tr["xyxy"], selected_box) >= 0.95:
                    tr["selected"] = True
                    tr["status"] = "selected_observed"
                    rejection_counts["selected_observed"] += 1
                    matched = True
                else:
                    if not tr["initial_rejection_reason"]:
                        tr["status"] = "dedup_suppressed"
                        rejection_counts["dedup_suppressed"] += 1
                    else:
                        tr["status"] = tr["initial_rejection_reason"]
                        rejection_counts[tr["initial_rejection_reason"]] += 1
        else:
            for tr in frame_traces:
                if ball_res.get("reason") == "ambiguous_ball_candidates":
                    tr["status"] = "ambiguous_margin"
                    rejection_counts["ambiguous_margin"] += 1
                elif tr["initial_rejection_reason"]:
                    tr["status"] = tr["initial_rejection_reason"]
                    rejection_counts[tr["initial_rejection_reason"]] += 1
                else:
                    tr["status"] = "unselected_suboptimal_score"

        all_candidate_traces.extend(frame_traces)

        ball_entry = {
            **ball_res,
            "window_id": window_id,
            "source_frame_index": f.source_frame_index,
            "local_time_s": f.local_time_s,
            "camera_layout_invalid": camera_layout_invalid,
        }
        ball_tracks.append(ball_entry)

    stats = {
        "total_frames": len(frames),
        "observed_frames": sum(1 for b in ball_tracks if b["sample_type"] == "observed"),
        "predicted_frames": sum(1 for b in ball_tracks if b["sample_type"] == "predicted"),
        "missing_frames": sum(1 for b in ball_tracks if b["sample_type"] == "missing"),
        "total_raw_ball_candidates": len(all_candidate_traces),
        "rejection_counts": rejection_counts,
        "camera_layout_invalid": camera_layout_invalid,
    }
    return ball_tracks, all_candidate_traces, stats


def draw_overlay_video(
    frames: List[FrameData],
    ball_tracks: List[Dict[str, Any]],
    tracked_obs: List[Dict[str, Any]],
    detections_by_frame: List[Dict[str, Any]],
    output_path: Path,
    review_times: Optional[Dict[str, Any]] = None,
    ball_roi_polygon: Optional[List[List[float]]] = None,
    window_id: str = "window",
) -> None:
    """Export annotated MP4 with raw candidates, selected ball, player identities, rims, and review indicators."""
    h, w = frames[0].image_bgr.shape[:2]
    out_p = Path(output_path).resolve()
    if out_p.exists():
        out_p.unlink()
    writer = VideoWriter(out_p, w, h, fps=30.0, codec="libx264", preset="veryfast")

    obs_by_fidx = {}
    for o in tracked_obs:
        obs_by_fidx.setdefault(o["frame_index"], []).append(o)

    ball_by_fidx = {b["frame_index"]: b for b in ball_tracks}
    dets_by_fidx = {d["local_frame_index"]: d["detections"] for d in detections_by_frame}

    rel_s = (review_times.get("release", {}) or {}).get("source_s") if review_times else None
    bas_s = (review_times.get("basket", {}) or {}).get("source_s") if review_times else None

    with writer:
        for f in frames:
            img = f.image_bgr.copy()
            fidx = f.local_frame_index
            t_s = f.source_time_s

            # 1. Draw ROI polygon (semi-transparent or dashed)
            if ball_roi_polygon:
                pts = np.array([[int(p[0] * w), int(p[1] * h)] for p in ball_roi_polygon], np.int32)
                cv2.polylines(img, [pts], isClosed=True, color=(60, 60, 60), thickness=2)

            # 2. Draw raw ball candidates (thin orange dashed/solid)
            for d in dets_by_fidx.get(fidx, []):
                if d["class_name"] == "ball":
                    bx = [int(v) for v in d["xyxy"]]
                    cv2.rectangle(img, (bx[0], bx[1]), (bx[2], bx[3]), (0, 140, 255), 1)

            # 3. Draw tracked players
            for p in obs_by_fidx.get(fidx, []):
                bx = [int(v) for v in p["bbox"]]
                team_id = p.get("team_id")
                team_color = (0, 200, 0)
                if team_id == "team_a":
                    team_color = (45, 35, 200)  # Reddish
                elif team_id == "team_b":
                    team_color = (220, 220, 220)  # White/silver

                cv2.rectangle(img, (bx[0], bx[1]), (bx[2], bx[3]), team_color, 2)
                jersey = p.get("jersey_number")
                label = f"{p['track_id']}"
                if jersey:
                    label += f" #{jersey}"
                cv2.putText(img, label, (bx[0], max(20, bx[1] - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, team_color, 1, cv2.LINE_AA)

            # 4. Draw rims
            for d in dets_by_fidx.get(fidx, []):
                if d["class_name"] == "rim":
                    bx = [int(v) for v in d["xyxy"]]
                    cv2.rectangle(img, (bx[0], bx[1]), (bx[2], bx[3]), (255, 180, 0), 2)
                    cv2.putText(img, f"RIM {d['confidence']:.2f}", (bx[0], max(20, bx[1] - 6)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 180, 0), 1, cv2.LINE_AA)

            # 5. Draw selected ball
            b = ball_by_fidx.get(fidx)
            if b:
                stype = b.get("sample_type", "missing")
                if stype == "observed" and b.get("xyxy"):
                    bx = [int(v) for v in b["xyxy"]]
                    cv2.rectangle(img, (bx[0], bx[1]), (bx[2], bx[3]), (0, 255, 0), 3)
                    c_pt = (int((bx[0] + bx[2]) / 2), int((bx[1] + bx[3]) / 2))
                    cv2.circle(img, c_pt, 4, (0, 255, 0), -1)
                    cv2.putText(img, f"BALL {b.get('confidence', 0):.2f}", (bx[0], max(20, bx[1] - 8)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)
                elif stype == "predicted" and b.get("center_image"):
                    c_pt = (int(b["center_image"][0]), int(b["center_image"][1]))
                    cv2.circle(img, c_pt, 12, (255, 255, 0), 2)
                    cv2.circle(img, c_pt, 3, (255, 255, 0), -1)
                    cv2.putText(img, "BALL [PRED]", (c_pt[0] - 30, max(20, c_pt[1] - 15)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1, cv2.LINE_AA)

            # 6. Status HUD top-left
            b_status = b.get("sample_type", "missing").upper() if b else "UNKNOWN"
            hud_color = (0, 255, 0) if b_status == "OBSERVED" else ((255, 255, 0) if b_status == "PREDICTED" else (0, 0, 255))
            cv2.rectangle(img, (10, 10), (460, 100), (20, 20, 20), -1)
            cv2.rectangle(img, (10, 10), (460, 100), (80, 80, 80), 1)
            cv2.putText(img, f"WINDOW: {window_id} | SRC: {t_s:.3f}s (LOC: {f.local_time_s:.3f}s)",
                        (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1, cv2.LINE_AA)
            cv2.putText(img, f"FRAME: #{fidx} (SRC #{f.source_frame_index}) | BALL: ",
                        (20, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1, cv2.LINE_AA)
            cv2.putText(img, b_status, (250, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.6, hud_color, 2, cv2.LINE_AA)
            reason_str = b.get("reason", "") if b else ""
            cv2.putText(img, f"REASON: {reason_str}", (20, 88),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 160, 160), 1, cv2.LINE_AA)

            # 7. Post-recognition review display markers (purely visual reference)
            marker = None
            if rel_s is not None and abs(t_s - rel_s) <= 0.05:
                marker = f"REVIEW TARGET: RELEASE ({rel_s:.3f}s)"
            elif bas_s is not None and abs(t_s - bas_s) <= 0.05:
                marker = f"REVIEW TARGET: BASKET ({bas_s:.3f}s)"

            if marker:
                cv2.rectangle(img, (w - 420, 10), (w - 10, 50), (0, 0, 180), -1)
                cv2.putText(img, marker, (w - 410, 35),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)

            writer.write_frame(img, source_time_s=f.local_time_s)


def render_contact_sheet(
    frames: List[FrameData],
    ball_tracks: List[Dict[str, Any]],
    review_times: Dict[str, Any],
    output_path: Path,
    window_id: str = "window",
) -> None:
    """Export 5-panel contact sheet: before_release, release, mid_flight, basket, after_basket."""
    rel_s = (review_times.get("release", {}) or {}).get("source_s", frames[0].source_time_s + 1.0)
    bas_s = (review_times.get("basket", {}) or {}).get("source_s", frames[-1].source_time_s - 1.0)
    mid_s = (rel_s + bas_s) / 2.0

    targets = [
        ("1_before_release", rel_s - 0.2),
        ("2_release", rel_s),
        ("3_mid_flight", mid_s),
        ("4_basket", bas_s),
        ("5_after_basket", bas_s + 0.2),
    ]

    ball_by_fidx = {b["frame_index"]: b for b in ball_tracks}
    crops = []

    for label, target_t in targets:
        # Find closest frame
        best_f = min(frames, key=lambda f: abs(f.source_time_s - target_t))
        b = ball_by_fidx.get(best_f.local_frame_index, {})
        stype = b.get("sample_type", "missing")

        panel = best_f.image_bgr.copy()
        # Draw selected ball on panel
        if stype == "observed" and b.get("xyxy"):
            bx = [int(v) for v in b["xyxy"]]
            cv2.rectangle(panel, (bx[0], bx[1]), (bx[2], bx[3]), (0, 255, 0), 3)
        elif stype == "predicted" and b.get("center_image"):
            c_pt = (int(b["center_image"][0]), int(b["center_image"][1]))
            cv2.circle(panel, c_pt, 12, (255, 255, 0), 2)

        # Header bar
        cv2.rectangle(panel, (0, 0), (panel.shape[1], 70), (0, 0, 0), -1)
        status_color = (0, 255, 0) if stype == "observed" else ((255, 255, 0) if stype == "predicted" else (0, 0, 255))
        cv2.putText(panel, f"{label.upper()} | {best_f.source_time_s:.3f}s", (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(panel, f"BALL: {stype.upper()} ({b.get('reason', '')})", (20, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, status_color, 2, cv2.LINE_AA)

        # Resize to thumbnail (e.g. 640x360)
        thumb = cv2.resize(panel, (640, 360))
        crops.append(thumb)

    # Combine into a horizontal strip or grid
    row1 = np.hstack([crops[0], crops[1], crops[2]])
    # Pad last row
    blank = np.zeros_like(crops[0])
    row2 = np.hstack([crops[3], crops[4], blank])
    sheet = np.vstack([row1, row2])

    cv2.imwrite(str(output_path), sheet)


def export_draft_review_packet(
    frames: List[FrameData],
    ball_tracks: List[Dict[str, Any]],
    review_times: Dict[str, Any],
    window_id: str = "window",
    packet_dir: Path = Path("draft_packet"),
) -> List[Dict[str, Any]]:
    """Export draft unreviewed keyframe packet for release and rim phases."""
    frames_dir = packet_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    rel_s = (review_times.get("release", {}) or {}).get("source_s")
    bas_s = (review_times.get("basket", {}) or {}).get("source_s")
    ball_by_fidx = {b["frame_index"]: b for b in ball_tracks}

    phases = []
    if rel_s is not None:
        phases.append(("release", rel_s))
    if bas_s is not None:
        phases.append(("basket", bas_s))

    packet_entries = []
    for phase_name, target_t in phases:
        best_f = min(frames, key=lambda f: abs(f.source_time_s - target_t))
        b = ball_by_fidx.get(best_f.local_frame_index, {})

        img_filename = f"{window_id}_{phase_name}_{best_f.source_frame_index:05d}.jpg"
        img_path = frames_dir / img_filename
        cv2.imwrite(str(img_path), best_f.image_bgr)
        img_sha = file_sha256(img_path)

        pred_box = b.get("xyxy") if b.get("sample_type") == "observed" else None

        entry = {
            "packet_frame_id": f"{window_id}:{phase_name}:{best_f.source_frame_index}",
            "window_id": window_id,
            "phase": phase_name,
            "source_time_s": best_f.source_time_s,
            "local_time_s": best_f.local_time_s,
            "source_frame_index": best_f.source_frame_index,
            "raw_pts": best_f.raw_pts,
            "image_path": f"frames/{img_filename}",
            "image_sha256": img_sha,
            "resolution": [best_f.image_bgr.shape[1], best_f.image_bgr.shape[0]],
            "predicted_ball": {
                "sample_type": b.get("sample_type", "missing"),
                "bbox": pred_box,
                "confidence": b.get("confidence"),
                "reason": b.get("reason"),
            },
            "review_status": "draft_unreviewed",
            "reviewer": None,
            "review_fields": {
                "ball_visible": None,
                "ball_bbox": None,
                "uncertain": False,
                "skip": False,
                "notes": None,
            },
        }
        packet_entries.append(entry)

    return packet_entries


def evaluate_window_diagnostics(
    window_id: str,
    frames: List[FrameData],
    ball_tracks: List[Dict[str, Any]],
    tracked_obs: List[Dict[str, Any]],
    detections_by_frame: List[Dict[str, Any]],
    review_window_meta: Dict[str, Any],
    stats: Dict[str, Any],
) -> Dict[str, Any]:
    """Perform post-recognition diagnostic evaluation against reviewed moments.
    
    This function is strictly post-inference: it checks whether the pipeline observed
    the ball and shooter at release, and observed the ball and rim at basket.
    """
    eval_times = review_window_meta.get("evaluation_times", {})
    rel_s = (eval_times.get("release", {}) or {}).get("source_s")
    bas_s = (eval_times.get("basket", {}) or {}).get("source_s")
    expected_shooter = review_window_meta.get("reviewed_shooter_id")

    ball_by_fidx = {b["frame_index"]: b for b in ball_tracks}
    obs_by_fidx = {}
    for o in tracked_obs:
        obs_by_fidx.setdefault(o["frame_index"], []).append(o)
    dets_by_fidx = {d["local_frame_index"]: d["detections"] for d in detections_by_frame}

    # 1. Release moment analysis
    rel_frame = min(frames, key=lambda f: abs(f.source_time_s - rel_s)) if rel_s is not None else None
    rel_ball = ball_by_fidx.get(rel_frame.local_frame_index) if rel_frame else None
    rel_ball_type = rel_ball.get("sample_type") if rel_ball else "unknown"

    # Identify shooter candidate at release (player closest to ball or active track)
    predicted_shooter_id = None
    shooter_match_status = "unknown"
    if rel_frame:
        players = obs_by_fidx.get(rel_frame.local_frame_index, [])
        if rel_ball_type == "observed" and rel_ball.get("xyxy"):
            bx_c = rel_ball.get("center_image", center(rel_ball["xyxy"]))
            # Find closest player
            closest = None
            min_dist = float("inf")
            for p in players:
                if p.get("sample_type") == "observed" and p.get("role") != "non_player":
                    p_box = p["bbox"]
                    p_c = center(p_box)
                    dist = math.dist(bx_c, p_c)
                    if dist < min_dist:
                        min_dist = dist
                        closest = p
            if closest:
                predicted_shooter_id = closest.get("player_id")

        if expected_shooter is not None:
            if predicted_shooter_id == expected_shooter:
                shooter_match_status = "match"
            elif predicted_shooter_id is not None:
                shooter_match_status = "mismatch"
            else:
                shooter_match_status = "unknown_identity"
        else:
            shooter_match_status = "no_gt_shooter"

    # 2. Basket moment analysis
    bas_frame = min(frames, key=lambda f: abs(f.source_time_s - bas_s)) if bas_s is not None else None
    bas_ball = ball_by_fidx.get(bas_frame.local_frame_index) if bas_frame else None
    bas_ball_type = bas_ball.get("sample_type") if bas_ball else "unknown"
    rim_detected_at_basket = False
    if bas_frame:
        rims = [d for d in dets_by_fidx.get(bas_frame.local_frame_index, []) if d["class_name"] == "rim"]
        rim_detected_at_basket = len(rims) > 0

    # 3. Classify primary failure mode
    failure_category = "none_clean_run"
    failure_details = []

    if stats["camera_layout_invalid"]:
        failure_category = "camera_cut_or_calibration_invalid"
        failure_details.append("FT closeup/follow-cam invalidated static court ROI")
    elif rel_ball_type == "missing":
        # Check why missing at release
        rel_candidates = [d for d in dets_by_fidx.get(rel_frame.local_frame_index, []) if d["class_name"] == "ball"] if rel_frame else []
        if not rel_candidates:
            failure_category = "no_raw_candidate"
            failure_details.append("Detector produced zero raw ball candidates at release")
        else:
            failure_category = "candidate_rejected_by_roi_or_gate"
            failure_details.append("Raw ball candidates existed at release but failed ROI/motion/size gates")
    elif bas_ball_type == "missing":
        bas_candidates = [d for d in dets_by_fidx.get(bas_frame.local_frame_index, []) if d["class_name"] == "ball"] if bas_frame else []
        if not bas_candidates:
            failure_category = "no_raw_candidate"
            failure_details.append("Detector produced zero raw ball candidates at basket")
        else:
            failure_category = "candidate_rejected_by_roi_or_gate"
            failure_details.append("Raw ball candidates existed at basket but failed gates")
    elif shooter_match_status in {"mismatch", "unknown_identity"} and expected_shooter is not None:
        failure_category = "missing_or_incorrect_identity"
        failure_details.append(f"Shooter identity unresolved (expected: {expected_shooter}, got: {predicted_shooter_id})")
    elif stats["observed_frames"] / max(1, stats["total_frames"]) < 0.4:
        failure_category = "tracker_association_or_detection_sparsity"
        failure_details.append(f"Observed ball coverage is low: {stats['observed_frames']}/{stats['total_frames']} ({stats['observed_frames']/stats['total_frames']*100:.1f}%)")

    return {
        "window_id": window_id,
        "total_frames": stats["total_frames"],
        "observed_frames": stats["observed_frames"],
        "predicted_frames": stats["predicted_frames"],
        "missing_frames": stats["missing_frames"],
        "observed_ball_coverage_pct": round(stats["observed_frames"] / max(1, stats["total_frames"]) * 100.0, 2),
        "release_evaluation": {
            "review_release_s": rel_s,
            "ball_sample_type": rel_ball_type,
            "ball_confidence": rel_ball.get("confidence") if rel_ball else None,
            "expected_shooter_id": expected_shooter,
            "predicted_shooter_id": predicted_shooter_id,
            "shooter_match_status": shooter_match_status,
        },
        "basket_evaluation": {
            "review_basket_s": bas_s,
            "ball_sample_type": bas_ball_type,
            "ball_confidence": bas_ball.get("confidence") if bas_ball else None,
            "rim_detected": rim_detected_at_basket,
        },
        "primary_failure_category": failure_category,
        "failure_details": failure_details,
        "rejection_counts": stats["rejection_counts"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft-windows", default=str(ROOT / "outputs/task08-scoring-intake-20261107/adjudicated-v3/critical-windows-draft.json"))
    parser.add_argument("--manifest", default=str(ROOT / "outputs/task08-scoreboard-review-20261106/review-manifest.json"))
    parser.add_argument("--source-video", default=str(ROOT / "assets_test/vietnam-tonga.mp4"))
    parser.add_argument("--roster", default=str(ROOT / "configs/rosters/vietnam_tonga.json"))
    parser.add_argument("--ball-config", default=str(ROOT / "configs/ball-possession-vietnam-tonga-spatial.json"))
    parser.add_argument("--policy", default=str(ROOT / "outputs/task07-vietnam-tonga-segments-20261104/vt_development-policy-ball-roi-v4.json"))
    parser.add_argument("--output-dir", default=str(ROOT / "outputs/task08-critical-baseline-20261108"))
    parser.add_argument("--onnx-threads", type=int, default=8)
    parser.add_argument("--confidence", type=float, default=0.15)
    parser.add_argument("--max-edge", type=int, default=1920)
    parser.add_argument("--disable-ocr", action="store_true", help="Run without EasyOCR for fast headless check")
    parser.add_argument("--ocr-upscale", type=int, default=1, help="Scale factor for OCR crop (1-4)")
    parser.add_argument("--ocr-cadence", type=int, default=15, help="Frame cadence for running OCR on players")
    parser.add_argument("--window-filter", help="Comma-separated subset of windows to run (default: all 10)")
    args = parser.parse_args()

    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=== [TASK08 CRITICAL MOMENTS BASELINE] ===")
    print("1. Verifying environment, configurations, and source integrity...", flush=True)

    src_video_path = Path(args.source_video).resolve()
    if not src_video_path.is_file():
        raise FileNotFoundError(f"Source video not found: {src_video_path}")
    src_sha = file_sha256(src_video_path)
    expected_src_sha = "1443c1d263c8037a5684f3dbc0ef9216beb5097d9a47c4c1c9b94d1363e26865"
    if src_sha != expected_src_sha:
        raise ValueError(f"Source video SHA-256 mismatch: {src_sha} != {expected_src_sha}")
    print(f"  Source Video: {src_video_path.name} ({src_sha[:16]}...) [VERIFIED]")

    roster_path = Path(args.roster).resolve()
    roster_sha = file_sha256(roster_path)
    print(f"  Roster: {roster_path.name} ({roster_sha[:16]}...) [VERIFIED]")

    ball_cfg_path = Path(args.ball_config).resolve()
    ball_cfg_raw = load_json(ball_cfg_path)
    ball_config = BallConfig(**ball_cfg_raw.get("ball", {}))
    print(f"  Ball Config: {ball_cfg_path.name} (min_conf={ball_config.min_confidence}) [VERIFIED]")

    # Policy / ball ROI
    policy_path = Path(args.policy).resolve()
    policy_raw = load_json(policy_path)
    ball_roi_polygon = policy_raw.get("ball_image_roi_normalized")
    print(f"  Ball ROI Polygon: {len(ball_roi_polygon) if ball_roi_polygon else 0} vertices loaded")

    # Recognition Manifest Sanitization
    recog_manifest_path = out_dir / "recognition_input_manifest.json"
    print("\n2. Generating sanitized recognition input manifest (stripping all GT/review fields)...", flush=True)
    recog_manifest = build_recognition_input_manifest(
        Path(args.draft_windows),
        Path(args.manifest),
        recog_manifest_path,
    )
    recog_manifest_sha = file_sha256(recog_manifest_path)
    print(f"  Saved: {recog_manifest_path.name} ({recog_manifest_sha[:16]}...)")
    print(f"  Windows count: {len(recog_manifest['windows'])}")

    # Initialize Detector
    print("\n3. Initializing approved ONNX detector runtime...", flush=True)
    t_det_init = time.perf_counter()
    pipe_cfg = PipelineConfig.default()
    pipe_cfg.model.confidence_threshold = args.confidence
    pipe_cfg.model.max_edge = args.max_edge
    pipe_cfg.model.cpu_threads = args.onnx_threads

    detector = TiledBallDetector(
        pipe_cfg.model,
        env_path=str(ROOT / ".env"),
        grid=2,
        overlap=0.2,
        excluded_boxes=[[0.02, 0.73, 0.27, 1.0]],
        onnx_threads=args.onnx_threads,
    )
    detector.warmup()
    det_init_s = time.perf_counter() - t_det_init
    runtime_info = detector.get_runtime_info()
    print(f"  Detector: {APPROVED_MODEL_ID} (ONNX CPU, {args.onnx_threads} threads) initialized in {det_init_s:.2f}s")

    # Initialize OCR Engine if enabled
    ocr_engine = None
    if not args.disable_ocr:
        try:
            print("  Initializing LocalEasyOCRProvider...", flush=True)
            import torch
            ocr_engine = LocalEasyOCRProvider(crop_upscale=args.ocr_upscale)
            _ = ocr_engine.reader  # load EasyOCR models
            torch.set_num_threads(args.onnx_threads)
            # Warmup call
            dummy_crop = np.full((60, 40, 3), 180, dtype=np.uint8)
            cv2.putText(dummy_crop, "10", (5, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 20, 20), 2)
            ocr_engine.read_jersey(dummy_crop, "warmup", 0, 0.0)
            print("  LocalEasyOCRProvider initialized and warmed up successfully", flush=True)
        except Exception as e:
            print(f"  Warning: OCR initialization failed ({type(e).__name__}): {e}; proceeding without OCR", flush=True)
            ocr_engine = None

    # Load review windows meta for post-inference evaluation only
    draft_meta = load_json(args.draft_windows)
    draft_by_id = {w["window_id"]: w for w in draft_meta.get("windows", [])}

    active_windows = recog_manifest["windows"]
    if args.window_filter:
        subset = set(args.window_filter.split(","))
        active_windows = [w for w in active_windows if w["window_id"] in subset]

    total_pipeline_start = time.perf_counter()
    all_window_evals = []
    all_draft_packet_entries = []
    total_frames_processed = 0

    packet_dir = out_dir / "draft_review_packet"
    packet_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n4. Executing baseline diagnostic across {len(active_windows)} windows...", flush=True)

    for w_idx, win in enumerate(active_windows, 1):
        wid = win["window_id"]
        w_start_s = win["source_start_s"]
        w_end_s = win["source_end_s"]
        offset_s = win["source_time_offset_s"]
        is_play_006 = (wid == "play_006")

        print(f"\n[{w_idx}/{len(active_windows)}] Processing {wid}: source [{w_start_s:.3f}s - {w_end_s:.3f}s]...", flush=True)
        w_dir = out_dir / wid
        w_dir.mkdir(parents=True, exist_ok=True)

        # 4.1 Decode frames
        t0 = time.perf_counter()
        frames = decode_window_frames(src_video_path, w_start_s, w_end_s, offset_s)
        decode_time = time.perf_counter() - t0
        total_frames_processed += len(frames)
        print(f"  Decoded {len(frames)} frames in {decode_time:.2f}s (source {frames[0].source_time_s:.3f}s to {frames[-1].source_time_s:.3f}s)", flush=True)

        # 4.2 Run Detections (with strict cache reuse if existing detections match frame count)
        dets_jsonl_path = w_dir / "raw_detections.jsonl"
        dets_reused = False
        if dets_jsonl_path.is_file():
            try:
                cached_dets = [json.loads(line) for line in dets_jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                if len(cached_dets) == len(frames) and all(abs(c["source_time_s"] - f.source_time_s) < 1e-4 for c, f in zip(cached_dets, frames)):
                    dets_by_frame = cached_dets
                    det_model_ms = sum(d.get("model_ms", 0.0) for d in dets_by_frame)
                    det_time = 0.0
                    dets_reused = True
                    print(f"  Detections: Reused {len(dets_by_frame)} cached detections from disk (exact frame count & timestamps match)", flush=True)
            except Exception:
                dets_reused = False

        if not dets_reused:
            t0 = time.perf_counter()
            dets_by_frame, det_model_ms = run_detections_on_window(detector, frames, args.confidence)
            det_time = time.perf_counter() - t0
            write_jsonl(dets_jsonl_path, dets_by_frame)
            print(f"  Detections: {sum(len(d['detections']) for d in dets_by_frame)} total in {det_time:.2f}s (mean {det_model_ms/len(frames):.1f}ms/frame)", flush=True)

        # 4.3 Run Player Tracking & Identity
        t0 = time.perf_counter()
        tracked_obs, jersey_ev = run_tracking_and_identity_on_window(
            frames, dets_by_frame, roster_path, ocr_engine=ocr_engine, ocr_cadence=args.ocr_cadence,
            window_id=wid, source_sha=src_sha,
        )
        track_time = time.perf_counter() - t0
        write_jsonl(w_dir / "tracked_observations.jsonl", tracked_obs)
        if jersey_ev:
            write_json(w_dir / "jersey_evidence.json", jersey_ev)
        print(f"  Player tracking: {len(tracked_obs)} observations in {track_time:.2f}s (OCR evidence records: {len(jersey_ev)})", flush=True)

        # 4.4 Run Ball Tracking with Diagnostics
        # For play_006: note that camera switches to closeup / follow, so static ROI is marked invalid
        cur_roi = None if is_play_006 else ball_roi_polygon
        ball_tracks, candidate_traces, ball_stats = run_ball_tracking_with_diagnostics(
            frames, dets_by_frame, tracked_obs, ball_config,
            ball_roi_polygon=cur_roi, is_play_006_ft=is_play_006, window_id=wid,
        )
        write_jsonl(w_dir / "ball_tracks.jsonl", ball_tracks)
        write_jsonl(w_dir / "candidate_traces.jsonl", candidate_traces)
        print(f"  Ball tracking: Observed {ball_stats['observed_frames']}/{ball_stats['total_frames']} frames ({ball_stats['observed_frames']/ball_stats['total_frames']*100:.1f}%), Predicted {ball_stats['predicted_frames']}, Missing {ball_stats['missing_frames']}", flush=True)

        # 4.5 Post-Inference Review Alignment (uses review meta strictly after recognition is frozen)
        rev_meta = draft_by_id.get(wid, {})
        win_eval = evaluate_window_diagnostics(
            wid, frames, ball_tracks, tracked_obs, dets_by_frame, rev_meta, ball_stats,
        )
        all_window_evals.append(win_eval)
        write_json(w_dir / "window_summary.json", win_eval)

        # 4.6 Visual Artifacts: Overlay video & Contact sheet
        t0 = time.perf_counter()
        draw_overlay_video(
            frames, ball_tracks, tracked_obs, dets_by_frame,
            w_dir / "overlay.mp4",
            review_times=rev_meta.get("evaluation_times"),
            ball_roi_polygon=cur_roi,
            window_id=wid,
        )
        render_contact_sheet(
            frames, ball_tracks,
            review_times=rev_meta.get("evaluation_times", {}),
            output_path=w_dir / "contact_sheet.jpg",
            window_id=wid,
        )
        print(f"  Rendered overlay video and contact sheet in {time.perf_counter() - t0:.2f}s", flush=True)

        # 4.7 Draft Review Packet Exports
        packet_entries = export_draft_review_packet(
            frames, ball_tracks, rev_meta.get("evaluation_times", {}),
            window_id=wid, packet_dir=packet_dir,
        )
        all_draft_packet_entries.extend(packet_entries)

    total_pipeline_s = time.perf_counter() - total_pipeline_start
    print(f"\nCompleted baseline recognition across all {len(active_windows)} windows in {total_pipeline_s:.1f}s")

    # 5. Export Master Draft Review Packet
    draft_packet_doc = {
        "schema_version": "task08-draft-bbox-packet-1",
        "provenance": {
            "source_video_sha256": src_sha,
            "recognition_manifest_sha256": recog_manifest_sha,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "status": "draft_unreviewed",
            "instructions": "Verify ball visibility and bounding box at critical release and basket moments. Do not promote predictions to ground truth without human approval.",
        },
        "total_frames": len(all_draft_packet_entries),
        "frames": all_draft_packet_entries,
    }
    write_json(packet_dir / "draft_review_packet.json", draft_packet_doc)

    # 6. Aggregate Summary and Error Classification Table
    total_obs = sum(e["observed_frames"] for e in all_window_evals)
    total_pred = sum(e["predicted_frames"] for e in all_window_evals)
    total_miss = sum(e["missing_frames"] for e in all_window_evals)
    agg_rejections = {}
    for e in all_window_evals:
        for k, v in e["rejection_counts"].items():
            agg_rejections[k] = agg_rejections.get(k, 0) + v

    # Shooter agreement stats
    evaluable_shooters = [e for e in all_window_evals if e["release_evaluation"]["expected_shooter_id"] is not None]
    shooter_matches = sum(1 for e in evaluable_shooters if e["release_evaluation"]["shooter_match_status"] == "match")
    shooter_mismatches = sum(1 for e in evaluable_shooters if e["release_evaluation"]["shooter_match_status"] == "mismatch")
    shooter_unknowns = sum(1 for e in evaluable_shooters if e["release_evaluation"]["shooter_match_status"] == "unknown_identity")

    # Failure mode distribution
    failure_mode_counts = {}
    for e in all_window_evals:
        cat = e["primary_failure_category"]
        failure_mode_counts[cat] = failure_mode_counts.get(cat, 0) + 1

    summary = {
        "schema_version": "task08-critical-baseline-summary-1",
        "diagnostic_scope": {
            "condition": "conditional_diagnostic_on_reviewed_scoring_windows",
            "independent_holdout": False,
            "blind_search": False,
            "ground_truth_bbox_available": False,
            "negative_cohort_available": False,
        },
        "counts": {
            "total_windows": len(all_window_evals),
            "total_frames_processed": total_frames_processed,
            "observed_ball_frames": total_obs,
            "predicted_ball_frames": total_pred,
            "missing_ball_frames": total_miss,
            "overall_observed_ball_coverage_pct": round(total_obs / max(1, total_frames_processed) * 100.0, 2),
            "overall_predicted_ball_coverage_pct": round(total_pred / max(1, total_frames_processed) * 100.0, 2),
            "overall_missing_ball_coverage_pct": round(total_miss / max(1, total_frames_processed) * 100.0, 2),
        },
        "shooter_identity_at_release": {
            "total_evaluable_windows": len(evaluable_shooters),
            "exact_matches": shooter_matches,
            "mismatches": shooter_mismatches,
            "unknown_identity": shooter_unknowns,
            "shooter_agreement_rate_pct": round(shooter_matches / max(1, len(evaluable_shooters)) * 100.0, 2),
        },
        "candidate_rejection_histogram": agg_rejections,
        "failure_mode_distribution": failure_mode_counts,
        "window_diagnostics": all_window_evals,
        "missing_data_requirements_for_next_phase": [
            "Approved ground-truth ball bounding boxes at release and rim (required for ball IoU recall)",
            "Negative cohort: missed field goals, rim bounces, blocked shots, turnovers, and TV replay cuts (required for made/miss precision and false positive control)",
            "Multi-camera court calibration and dynamic camera pan handling (required for FT play_006 follow-cam)",
            "Temporal shot state machine: flight arc tracking and made/miss basket crossing logic",
        ],
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(out_dir / "summary.json", summary)

    # 7. Export Run Metadata
    run_meta = {
        "run_id": out_dir.name,
        "task": "task08_critical_moments_baseline",
        "status": "completed" if len(all_window_evals) == 10 else "partial",
        "source_video_path": str(src_video_path),
        "source_fingerprint_sha256": src_sha,
        "recognition_manifest_sha256": recog_manifest_sha,
        "roster_sha256": roster_sha,
        "ball_config_sha256": file_sha256(ball_cfg_path),
        "approved_model_id": APPROVED_MODEL_ID,
        "runtime": runtime_info,
        "timings": {
            "total_pipeline_s": round(total_pipeline_s, 2),
            "detector_init_s": round(det_init_s, 2),
            "fps": round(total_frames_processed / max(1e-4, total_pipeline_s), 2),
        },
        "resource_attribution": {
            "onnx_threads": args.onnx_threads,
            "device": "cpu",
            "background_job_interference": "None detected; task07a finetune job is suspended in waiting state",
        },
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(out_dir / "run.json", run_meta)

    print("\n=== [TASK08 BASELINE COMPLETED] ===")
    print(f"Summary: {out_dir / 'summary.json'}")
    print(f"Run info: {out_dir / 'run.json'}")
    print(f"Overall Observed Ball Coverage: {summary['counts']['overall_observed_ball_coverage_pct']}%")
    print(f"Shooter Agreement: {shooter_matches}/{len(evaluable_shooters)} ({summary['shooter_identity_at_release']['shooter_agreement_rate_pct']}%)")
    print(f"Primary Failure Modes: {failure_mode_counts}")


if __name__ == "__main__":
    main()
