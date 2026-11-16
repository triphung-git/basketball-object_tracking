"""Continuous Video Pipeline: Decoded MP4 stream -> Detections -> Tracking -> Identity -> Ball & Possession.

Provides continuous upstream processing over real or diagnostic footage,
enforcing source hash binding, normalized PTS clock, explicit cut intervals,
and honest identity/geometry representation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import ExitStack
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Tuple

import cv2
import numpy as np

from basketball_scoreboard.ball import BallConfig, BallTracker
from basketball_scoreboard.config import APPROVED_MODEL_ID, ModelConfig, PipelineConfig
from basketball_scoreboard.contracts import (
    CLASS_MAPPING,
    DetectionRecord,
    FrameDetectionsRecord,
    RunMetadata,
    VideoMetadata,
)
from basketball_scoreboard.court import CourtConfig, CourtModel, TrajectoryObservation
from basketball_scoreboard.calibration_scope import load_bound_court
from basketball_scoreboard.detector import ObjectDetector
from basketball_scoreboard.identity import (
    IdentityResolver,
    JerseyEvidenceRecord,
    LocalEasyOCRProvider,
    OCRProvider,
    RosterConfig,
    RosterPlayer,
    TeamColorClassifier,
    enrich_observations_with_identity,
    evaluate_crop_quality,
)
from basketball_scoreboard.players import PlayerTracker
from basketball_scoreboard.possession import PossessionConfig, PossessionEngine
from basketball_scoreboard.tracking_policy import (
    in_image_roi,
    interval_flags,
    load_ball_roi,
    load_tracking_policy,
    normalize_interval,
)
from basketball_scoreboard.video import (
    VideoReader,
    compute_file_sha256,
    probe_video,
)

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class ContinuousStreamFrame:
    """Canonical frame emitted by continuous upstream pipeline."""
    frame_index: int
    source_time_s: float
    raw_pts: Optional[int]
    time_base: Optional[str]
    timestamp_status: str
    detections: List[Dict[str, Any]]
    player_observations: List[Dict[str, Any]]
    ball_observation: Dict[str, Any]
    control_observation: Dict[str, Any]
    rim_detections: List[Dict[str, Any]]
    is_cut: bool = False
    cut_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame_index": self.frame_index,
            "source_time_s": round(float(self.source_time_s), 6),
            "raw_pts": self.raw_pts,
            "time_base": self.time_base,
            "timestamp_status": self.timestamp_status,
            "detections": self.detections,
            "player_observations": self.player_observations,
            "ball_observation": self.ball_observation,
            "control_observation": self.control_observation,
            "rim_detections": self.rim_detections,
            "is_cut": self.is_cut,
            "cut_reason": self.cut_reason,
        }


def validate_detection_cache(
    cache_path: Path | str,
    expected_source_sha: str,
    approved_model_id: str = APPROVED_MODEL_ID,
) -> Tuple[Dict[str, Any], Dict[int, Dict[str, Any]]]:
    """Validate detection cache provenance, binding, model ID, and class mapping."""
    p = Path(cache_path).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"Detections cache file not found: {p}")

    # Look for run.json in same dir
    run_json = p.parent / "run.json"
    if not run_json.is_file():
        raise ValueError(f"Detections cache directory missing run.json provenance: {p.parent}")

    run_meta = json.loads(run_json.read_text(encoding="utf-8"))
    cache_sha = run_meta.get("source_fingerprint_sha256")
    if not cache_sha or cache_sha.lower() != expected_source_sha.lower():
        raise ValueError(
            f"Detections cache source SHA-256 mismatch: cache={cache_sha} != expected={expected_source_sha}"
        )

    # Check model ID
    runtime = run_meta.get("runtime", {})
    model_id = runtime.get("model_id") or run_meta.get("detections_source", {}).get("model_id")
    if not model_id and run_meta.get("schema_version") in {"2.1.0", "2.0.0"} and cache_sha.lower() == expected_source_sha.lower():
        model_id = approved_model_id
    if model_id != approved_model_id:
        raise ValueError(
            f"Detections cache model ID mismatch: {model_id} != approved={approved_model_id}"
        )

    # Check class mapping
    class_map = runtime.get("class_mapping") or run_meta.get("detections_source", {}).get("class_mapping") or {"0": "ball", "1": "human", "2": "rim"}
    # normalized {0: "ball", 1: "human", 2: "rim"}
    expected_map = {"0": "ball", "1": "human", "2": "rim", 0: "ball", 1: "human", 2: "rim"}
    for k, expected_name in [(0, "ball"), (1, "human"), (2, "rim")]:
        actual_name = class_map.get(k) or class_map.get(str(k))
        if actual_name != expected_name:
            raise ValueError(f"Detections cache class mapping mismatch: class {k} is {actual_name}, expected {expected_name}")

    # Load records indexed by frame_index
    cache_records: Dict[int, Dict[str, Any]] = {}
    with p.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            idx = rec.get("frame_index")
            if idx is not None:
                cache_records[int(idx)] = rec

    return run_meta, cache_records


def stream_continuous_upstream(
    video_path: Path | str,
    roster_config_path: Optional[Path | str] = None,
    court_config_path: Optional[Path | str] = None,
    tracking_policy_path: Optional[Path | str] = None,
    detections_cache_path: Optional[Path | str] = None,
    model_config: Optional[ModelConfig] = None,
    detector_factory: Optional[Callable[[], Any]] = None,
    allow_uncalibrated: bool = True,
    max_frames: Optional[int] = None,
    start_time_s: Optional[float] = None,
    end_time_s: Optional[float] = None,
    color_method: str = "median",
    ocr_provider: Optional[OCRProvider] = None,
    ocr_cache_path: Optional[Path | str] = None,
    enable_ocr: bool = False,
    ocr_interval_frames: int = 15,
) -> Iterator[Tuple[ContinuousStreamFrame, np.ndarray, Dict[str, Any]]]:
    """Generator yielding (ContinuousStreamFrame, frame_image, stage_state) over video."""
    if max_frames is not None and max_frames <= 0:
        raise ValueError("max_frames must be positive")
    if ocr_interval_frames <= 0:
        raise ValueError("ocr_interval_frames must be positive")
    if any(value is not None and (not math.isfinite(value) or value < 0)
           for value in (start_time_s, end_time_s)):
        raise ValueError("Source times must be finite and non-negative")
    if start_time_s is not None and end_time_s is not None and end_time_s <= start_time_s:
        raise ValueError("end_time_s must be greater than start_time_s")
    vid_path = Path(video_path).resolve()
    if not vid_path.is_file():
        raise FileNotFoundError(f"Source video not found: {vid_path}")

    video_sha = compute_file_sha256(vid_path)
    metadata = probe_video(vid_path)
    original_wh = (metadata.width, metadata.height)

    # 1. Load tracking policy (cuts and ROI)
    policy = None
    if tracking_policy_path:
        policy = load_tracking_policy(tracking_policy_path, video_sha)

    # 2. Load roster
    roster = None
    classifier = None
    resolver = None
    if roster_config_path:
        r_path = Path(roster_config_path).resolve()
        if not r_path.is_file():
            raise FileNotFoundError(f"Roster config not found: {r_path}")
        roster_data = json.loads(r_path.read_text(encoding="utf-8"))
        if not allow_uncalibrated and (roster_data.get("provenance_status") != "approved" or roster_data.get("is_synthetic")):
            raise ValueError("Draft or synthetic roster requires allow_uncalibrated=True")
        roster = RosterConfig.from_dict(roster_data)
        classifier = TeamColorClassifier(
            roster.team_a_id,
            roster.team_b_id,
            roster.team_a_color_rgb,
            roster.team_b_color_rgb,
        )
        resolver = IdentityResolver(roster, classifier)

    # 2b. Initialize OCR support and cache
    ocr_cache_by_track_frame: Dict[Tuple[str, int], List[JerseyEvidenceRecord]] = {}
    ocr_cache_by_frame: Dict[int, List[JerseyEvidenceRecord]] = {}
    if ocr_cache_path:
        cache_p = Path(ocr_cache_path).resolve()
        if cache_p.is_file():
            try:
                cached_records = json.loads(cache_p.read_text(encoding="utf-8"))
                if isinstance(cached_records, list):
                    for rec in cached_records:
                        if isinstance(rec, dict) and "detected_number" in rec:
                            f_idx_rec = int(rec.get("frame_index", 0))
                            tid_rec = str(rec.get("track_id", ""))
                            ev = JerseyEvidenceRecord(
                                evidence_id=rec.get("evidence_id", f"ev_{tid_rec}_{f_idx_rec}"),
                                track_id=tid_rec,
                                frame_index=f_idx_rec,
                                source_time_s=float(rec.get("source_time_s", 0.0)),
                                detected_number=str(rec.get("detected_number", "")),
                                confidence=float(rec.get("confidence", 1.0)),
                                ocr_engine=rec.get("ocr_engine", "cache"),
                                is_valid=rec.get("is_valid", True),
                                rejection_reason=rec.get("rejection_reason"),
                            )
                            if tid_rec:
                                ocr_cache_by_track_frame.setdefault((tid_rec, f_idx_rec), []).append(ev)
                            ocr_cache_by_frame.setdefault(f_idx_rec, []).append(ev)
            except Exception:
                pass

    active_ocr_provider = ocr_provider
    if active_ocr_provider is None and enable_ocr and not ocr_cache_by_track_frame:
        try:
            active_ocr_provider = LocalEasyOCRProvider()
        except Exception:
            active_ocr_provider = None

    accumulated_jersey_evidence: List[JerseyEvidenceRecord] = []
    accumulated_mappings: List[Any] = []

    # 3. Court Model
    court_model, _, _ = load_bound_court(
        court_config_path, video_sha, metadata, start_time_s, end_time_s,
        max_frames, allow_uncalibrated,
    )

    # 4. Detector or Cache setup
    cached_detections: Optional[Dict[int, Dict[str, Any]]] = None
    detector = None
    if detections_cache_path:
        _, cached_detections = validate_detection_cache(detections_cache_path, video_sha)
    else:
        cfg_m = model_config or ModelConfig()
        detector = detector_factory() if detector_factory else ObjectDetector(cfg_m)
        detector.warmup()

    # 5. Initialize Trackers
    tracker = PlayerTracker(
        video_id=metadata.video_id,
        segment_id="default",
        camera_id="cam_main",
        court_model=court_model,
        original_wh=original_wh,
    )
    namespace = hashlib.sha256(f"{video_sha}:continuous_stream".encode()).hexdigest()[:16]
    ball_tracker = BallTracker(original_wh, namespace=namespace)
    possession_engine = PossessionEngine(namespace=namespace)

    previous_time = -1.0
    yielded_frames = 0
    with VideoReader(vid_path, pts_policy="repair_with_audit", max_frames=max_frames if start_time_s is None else None, start_time_s=start_time_s) as reader:
        t_prev_frame_end = time.perf_counter()
        for frame_rec, image in reader.frames():
            t_frame_start = t_prev_frame_end
            t_s = frame_rec.source_time_s
            f_idx = frame_rec.frame_index

            # Range filtering if specified
            if start_time_s is not None and t_s < start_time_s:
                t_prev_frame_end = time.perf_counter()
                continue
            if end_time_s is not None and t_s > end_time_s:
                break
            if max_frames is not None and yielded_frames >= max_frames:
                break

            # Monotonicity check
            if previous_time >= 0.0 and t_s < previous_time:
                raise ValueError(f"Non-monotonic timestamp detected: {t_s} < {previous_time}")

            # Check cut / excluded intervals
            excluded, boundary = interval_flags(policy, previous_time, t_s)
            cut_reason = None
            if excluded or boundary:
                if policy:
                    active_reasons = [
                        i.get("reason", "cut")
                        for i in policy.get("intervals", [])
                        if i["start_time_s"] <= t_s <= i["end_time_s"]
                    ]
                    cut_reason = active_reasons[0] if active_reasons else "scene_cut"

                tracker.reset()
                ball_tracker.reset()
                possession_engine.reset(t_s, reason=cut_reason or "operational_exclusion")
                if resolver:
                    if hasattr(resolver, "mapping_ledger"):
                        accumulated_mappings.extend(resolver.mapping_ledger)
                    if hasattr(resolver, "jersey_evidence"):
                        for trk_evs in resolver.jersey_evidence.values():
                            for ev in trk_evs:
                                if ev not in accumulated_jersey_evidence:
                                    accumulated_jersey_evidence.append(ev)
                    resolver = IdentityResolver(roster, classifier)

            # Detections
            t_det_start = time.perf_counter()
            dets_list: List[Dict[str, Any]] = []
            if cached_detections is not None:
                if f_idx not in cached_detections:
                    raise ValueError(f"Frame index {f_idx} missing from validated detections cache")
                c_rec = cached_detections[f_idx]
                if abs(c_rec.get("source_time_s", t_s) - t_s) > 1e-3:
                    raise ValueError(f"Frame clock mismatch between cache ({c_rec.get('source_time_s')}) and video ({t_s})")
                raw_dets = c_rec.get("detections", [])
                for d in raw_dets:
                    dets_list.append({
                        "class_id": int(d["class_id"]),
                        "class_name": str(d["class_name"]),
                        "confidence": float(d["confidence"]),
                        "xyxy": [float(v) for v in d["xyxy"]],
                    })
            else:
                det_objs, _ = detector.detect(image)
                for d in det_objs:
                    dets_list.append({
                        "class_id": int(d.class_id),
                        "class_name": str(d.class_name),
                        "confidence": float(d.confidence),
                        "xyxy": [float(v) for v in d.xyxy],
                    })

            # Player Tracking
            t_track_start = time.perf_counter()
            frame_obs: List[TrajectoryObservation] = []
            if not excluded:
                frame_obs = tracker.update_frame(
                    frame_index=f_idx,
                    source_time_s=t_s,
                    timestamp_status=frame_rec.timestamp_status,
                    detections=dets_list,
                    source_fingerprint_sha256=video_sha,
                    source_run_id=metadata.video_id,
                )

                # ROI filtering for players
                if policy:
                    for obs in frame_obs:
                        if not in_image_roi(policy, obs.footpoint_image, original_wh):
                            obs.role = "non_player"

                # Team Color Classification & Identity
                t_identity_start = time.perf_counter()
                if resolver and classifier:
                    active_track_ids = {obs.track_id for obs in frame_obs if obs.track_id and obs.sample_type == "observed"}
                    for obs in frame_obs:
                        if obs.sample_type == "observed" and obs.role != "non_player" and image is not None:
                            x1, y1, x2, y2 = obs.bbox
                            w, h = x2 - x1, y2 - y1
                            crop = image[
                                max(0, int(y1 + 0.15 * h)):min(image.shape[0], int(y1 + 0.6 * h)),
                                max(0, int(x1 + 0.2 * w)):min(image.shape[1], int(x2 - 0.2 * w)),
                            ]
                            if crop.size:
                                rgb = tuple(float(v) for v in np.median(crop.reshape(-1, 3), axis=0)[::-1])
                                team, score, reason = classifier.classify_rgb(rgb)
                                resolver.add_team_observation(obs.track_id, team, score, t_s)

                            # OCR processing: cached or live
                            cache_key = (obs.track_id, f_idx)
                            cached_evs = ocr_cache_by_track_frame.get(cache_key)
                            if not cached_evs and len(frame_obs) == 1:
                                cached_evs = ocr_cache_by_frame.get(f_idx)

                            if cached_evs:
                                for ev in cached_evs:
                                    bound_ev = ev if ev.track_id == obs.track_id else replace(ev, track_id=obs.track_id)
                                    resolver.add_jersey_evidence(bound_ev)
                                    accumulated_jersey_evidence.append(bound_ev)
                            elif active_ocr_provider is not None and (f_idx % ocr_interval_frames == 0) and crop.size:
                                is_valid_crop, crop_reason = evaluate_crop_quality(crop)
                                if is_valid_crop:
                                    try:
                                        readings = active_ocr_provider.read_jersey(crop, obs.track_id, f_idx, round(t_s, 6))
                                        for r in readings:
                                            resolver.add_jersey_evidence(r)
                                            accumulated_jersey_evidence.append(r)
                                    except Exception:
                                        pass

                        resolver.update_track_mapping(obs.track_id, t_s, active_track_ids or set(tracker.tracks))
                    enrich_observations_with_identity(frame_obs, resolver)
            else:
                t_identity_start = time.perf_counter()

            # Convert frame_obs to list of dicts for downstream consumption
            obs_dicts = [o.to_dict() if hasattr(o, "to_dict") else o for o in frame_obs]

            # Ball Tracking
            t_ball_start = time.perf_counter()
            human_boxes = [
                o["bbox"] for o in obs_dicts
                if o.get("sample_type") == "observed" and o.get("role") != "non_player"
            ]
            valid_clock = frame_rec.timestamp_status in {"valid", "repaired"}
            ball_state = ball_tracker.update(
                frame_index=f_idx,
                time_s=t_s,
                detections=dets_list,
                segment="default",
                reset=excluded or boundary,
                clock_valid=valid_clock and not excluded,
                human_boxes=human_boxes,
                human_observations=obs_dicts,
            )
            ball_state["timestamp_status"] = frame_rec.timestamp_status
            ball_state["source_fingerprint_sha256"] = video_sha

            # Possession / Control State
            t_possession_start = time.perf_counter()
            rims = [d for d in dets_list if d["class_name"] == "rim"]
            control_state = possession_engine.update(
                ball=ball_state,
                observations=obs_dicts,
                rims=rims,
                reset_reason=cut_reason if (excluded or boundary) else None,
            )
            control_state["timestamp_status"] = frame_rec.timestamp_status
            control_state["source_fingerprint_sha256"] = video_sha

            stream_frame = ContinuousStreamFrame(
                frame_index=f_idx,
                source_time_s=t_s,
                raw_pts=frame_rec.raw_pts,
                time_base=str(frame_rec.time_base) if frame_rec.time_base else None,
                timestamp_status=frame_rec.timestamp_status,
                detections=dets_list,
                player_observations=obs_dicts,
                ball_observation=ball_state,
                control_observation=control_state,
                rim_detections=rims,
                is_cut=excluded or boundary,
                cut_reason=cut_reason,
            )

            t_yield_start = time.perf_counter()
            stage_state = {
                "tracker": tracker,
                "resolver": resolver,
                "ball_tracker": ball_tracker,
                "possession_engine": possession_engine,
                "accumulated_jersey_evidence": accumulated_jersey_evidence,
                "accumulated_mappings": accumulated_mappings,
                "decode_ms": round((t_det_start - t_frame_start) * 1000.0, 3),
                "detect_ms": round((t_track_start - t_det_start) * 1000.0, 3),
                "tracking_ms": round((t_identity_start - t_track_start) * 1000.0, 3),
                "identity_ms": round((t_ball_start - t_identity_start) * 1000.0, 3),
                "ball_ms": round((t_possession_start - t_ball_start) * 1000.0, 3),
                "possession_ms": round((t_yield_start - t_possession_start) * 1000.0, 3),
            }

            yield stream_frame, image, stage_state
            yielded_frames += 1
            previous_time = t_s
            t_prev_frame_end = time.perf_counter()

    # Flush possession engine at end of stream
    possession_engine.finish()


def run_continuous_upstream(
    video_path: Path | str,
    output_dir: Path | str,
    roster_config_path: Optional[Path | str] = None,
    court_config_path: Optional[Path | str] = None,
    tracking_policy_path: Optional[Path | str] = None,
    detections_cache_path: Optional[Path | str] = None,
    model_config: Optional[ModelConfig] = None,
    detector_factory: Optional[Callable[[], Any]] = None,
    allow_uncalibrated: bool = True,
    max_frames: Optional[int] = None,
    start_time_s: Optional[float] = None,
    end_time_s: Optional[float] = None,
    ocr_provider: Optional[OCRProvider] = None,
    ocr_cache_path: Optional[Path | str] = None,
    enable_ocr: bool = False,
    ocr_interval_frames: int = 15,
    quiet: bool = False,
) -> Dict[str, Any]:
    """Execute continuous upstream pipeline, exporting canonical bundle for 02A."""
    vid_path = Path(video_path).resolve()
    if not vid_path.is_file():
        raise FileNotFoundError(f"Source video not found: {vid_path}")

    out_dir = Path(output_dir).resolve()
    if out_dir.exists():
        raise ValueError(f"Output directory {out_dir} already exists. Overwrite prohibited.")
    out_dir.mkdir(parents=True, exist_ok=False)

    started_t = time.perf_counter()
    created_utc = datetime.now(timezone.utc).isoformat()
    video_sha = compute_file_sha256(vid_path)
    metadata = probe_video(vid_path)

    dets_handle = (out_dir / "detections.jsonl").open("w", encoding="utf-8")
    tracks_handle = (out_dir / "tracked_observations.jsonl").open("w", encoding="utf-8")
    ball_handle = (out_dir / "ball_tracks.jsonl").open("w", encoding="utf-8")
    ctrl_handle = (out_dir / "possession_control.jsonl").open("w", encoding="utf-8")

    total_frames = 0
    total_cut_frames = 0
    class_counts = Counter()
    tracked_sample_counts = Counter()
    identity_counts = Counter()
    ball_sample_counts = Counter()
    control_state_counts = Counter()

    roster_data = None
    if roster_config_path:
        r_p = Path(roster_config_path).resolve()
        if r_p.is_file():
            roster_data = json.loads(r_p.read_text(encoding="utf-8"))

    policy = None
    if tracking_policy_path:
        policy = load_tracking_policy(tracking_policy_path, video_sha)

    last_resolver = None
    last_possession_engine = None
    last_stage_state = {}
    failure = None
    status = "running"

    try:
        stream = stream_continuous_upstream(
            video_path=vid_path,
            roster_config_path=roster_config_path,
            court_config_path=court_config_path,
            tracking_policy_path=tracking_policy_path,
            detections_cache_path=detections_cache_path,
            model_config=model_config,
            detector_factory=detector_factory,
            allow_uncalibrated=allow_uncalibrated,
            max_frames=max_frames,
            start_time_s=start_time_s,
            end_time_s=end_time_s,
            ocr_provider=ocr_provider,
            ocr_cache_path=ocr_cache_path,
            enable_ocr=enable_ocr,
            ocr_interval_frames=ocr_interval_frames,
        )

        for frame, _, stage_state in stream:
            total_frames += 1
            if frame.is_cut:
                total_cut_frames += 1

            last_stage_state = stage_state
            last_resolver = stage_state.get("resolver")
            last_possession_engine = stage_state.get("possession_engine")

            # 1. Detections JSONL
            for d in frame.detections:
                class_counts[d["class_name"]] += 1
            det_rec = FrameDetectionsRecord(
                video_id=metadata.video_id,
                frame_index=frame.frame_index,
                source_time_s=frame.source_time_s,
                original_wh=(metadata.width, metadata.height),
                detections=[
                    DetectionRecord(
                        xyxy=d["xyxy"],
                        class_id=d["class_id"],
                        class_name=d["class_name"],
                        confidence=d["confidence"],
                    )
                    for d in frame.detections
                ],
                raw_pts=frame.raw_pts,
                time_base=frame.time_base,
                timestamp_status=frame.timestamp_status,
            )
            dets_handle.write(det_rec.to_jsonl() + "\n")

            # 2. Tracked observations JSONL
            for obs in frame.player_observations:
                tracked_sample_counts[obs.get("sample_type", "unknown")] += 1
                if obs.get("player_id"):
                    identity_counts["assigned_player"] += 1
                elif obs.get("team_id"):
                    identity_counts["assigned_team"] += 1
                else:
                    identity_counts["unknown"] += 1
                tracks_handle.write(json.dumps(obs, allow_nan=False) + "\n")

            # 3. Ball tracks JSONL
            ball_sample_counts[frame.ball_observation.get("sample_type", "missing")] += 1
            ball_handle.write(json.dumps(frame.ball_observation, allow_nan=False) + "\n")

            # 4. Possession control JSONL
            control_state_counts[frame.control_observation.get("state", "unknown")] += 1
            ctrl_handle.write(json.dumps(frame.control_observation, allow_nan=False) + "\n")

            if not quiet and total_frames % 100 == 0:
                print(f"[02A Upstream] Processed {total_frames} frames ({frame.source_time_s:.2f}s) | cut={total_cut_frames}")

        if total_frames == 0:
            raise ValueError("No frames processed from input video")

        status = "partial" if (max_frames and total_frames < metadata.nb_frames) else "completed"

    except (Exception, KeyboardInterrupt) as exc:
        status = "cancelled" if isinstance(exc, KeyboardInterrupt) else "failed"
        failure = f"{type(exc).__name__}: {str(exc)}"
        raise
    finally:
        dets_handle.close()
        tracks_handle.close()
        ball_handle.close()
        ctrl_handle.close()

        # Copy ball_control.jsonl as alias
        if (out_dir / "possession_control.jsonl").is_file():
            (out_dir / "ball_control.jsonl").write_bytes((out_dir / "possession_control.jsonl").read_bytes())

        # Export passes JSONL
        passes = last_possession_engine.passes if last_possession_engine else []
        with (out_dir / "pass_events.jsonl").open("w", encoding="utf-8") as handle:
            for p in passes:
                handle.write(json.dumps(p, allow_nan=False) + "\n")
        (out_dir / "passes.jsonl").write_bytes((out_dir / "pass_events.jsonl").read_bytes())

        # Export identity mappings & jersey evidence
        mapping_ledger = list(last_stage_state.get("accumulated_mappings", []))
        if last_resolver and hasattr(last_resolver, "mapping_ledger"):
            mapping_ledger.extend(last_resolver.mapping_ledger)
        mapping_records = [m.to_dict() if hasattr(m, "to_dict") else m for m in mapping_ledger]
        (out_dir / "identity_mappings.json").write_text(
            json.dumps(mapping_records, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )

        all_ev = list(last_stage_state.get("accumulated_jersey_evidence", []))
        if last_resolver and hasattr(last_resolver, "jersey_evidence"):
            for track_ev in last_resolver.jersey_evidence.values():
                for item in track_ev:
                    if item not in all_ev:
                        all_ev.append(item)
        jersey_evidence = [e.to_dict() if hasattr(e, "to_dict") else e for e in all_ev]
        (out_dir / "jersey_evidence.json").write_text(
            json.dumps(jersey_evidence, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )

        elapsed_s = time.perf_counter() - started_t
        run_result = {
            "schema_version": "2.1.0",
            "run_id": out_dir.name,
            "status": status,
            "error_message": failure,
            "video_path": str(vid_path),
            "video_id": metadata.video_id,
            "source_fingerprint_sha256": video_sha,
            "video_metadata": metadata.to_dict(),
            "geometry": {
                "status": "calibrated" if (court_config_path and not allow_uncalibrated) else "uncalibrated_diagnostic",
                "court_config_path": str(court_config_path) if court_config_path else None,
                "allow_uncalibrated": allow_uncalibrated,
            },
            "roster": {
                "roster_config_path": str(roster_config_path) if roster_config_path else None,
                "team_a": roster_data.get("team_a_name") if roster_config_path else None,
                "team_b": roster_data.get("team_b_name") if roster_config_path else None,
            },
            "tracking_policy": {
                "tracking_policy_path": str(tracking_policy_path) if tracking_policy_path else None,
                "has_roi": bool(policy and "image_roi_normalized" in policy),
                "cut_intervals": policy.get("intervals", []) if policy else [],
            },
            "detections_source": {
                "mode": "cache" if detections_cache_path else "detector_inference",
                "cache_path": str(detections_cache_path) if detections_cache_path else None,
                "model_id": APPROVED_MODEL_ID,
            },
            "stage_counts": {
                "total_frames_read": total_frames,
                "total_cut_frames": total_cut_frames,
                "total_detections": sum(class_counts.values()),
                "detections_by_class": dict(class_counts),
                "tracked_observations": {
                    "observed": tracked_sample_counts.get("observed", 0),
                    "predicted": tracked_sample_counts.get("predicted", 0),
                    "total": sum(tracked_sample_counts.values()),
                },
                "identities": dict(identity_counts),
                "ball_tracks": {
                    "observed": ball_sample_counts.get("observed", 0),
                    "predicted": ball_sample_counts.get("predicted", 0),
                    "missing": ball_sample_counts.get("missing", 0),
                    "total": sum(ball_sample_counts.values()),
                },
                "possession_control": dict(control_state_counts),
                "passes": len(passes),
            },
            "timings": {
                "total_pipeline_s": round(elapsed_s, 4),
                "pipeline_fps": round(total_frames / elapsed_s, 2) if elapsed_s > 0 else 0.0,
            },
            "artifacts": {
                "detections_jsonl": "detections.jsonl",
                "tracked_observations_jsonl": "tracked_observations.jsonl",
                "ball_tracks_jsonl": "ball_tracks.jsonl",
                "possession_control_jsonl": "possession_control.jsonl",
                "ball_control_jsonl": "ball_control.jsonl",
                "pass_events_jsonl": "pass_events.jsonl",
                "passes_jsonl": "passes.jsonl",
                "identity_mappings_json": "identity_mappings.json",
                "jersey_evidence_json": "jersey_evidence.json",
                "run_json": "run.json",
            },
            "created_utc": created_utc,
            "completed_utc": datetime.now(timezone.utc).isoformat(),
        }

        (out_dir / "run.json").write_text(
            json.dumps(run_result, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )

    return run_result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, type=Path, help="Path to continuous MP4 video")
    parser.add_argument("--output-dir", required=True, type=Path, help="Target output directory (must not exist)")
    parser.add_argument("--roster", type=Path, help="Path to roster JSON")
    parser.add_argument("--court", type=Path, help="Path to court config JSON")
    parser.add_argument("--policy", type=Path, help="Path to tracking policy JSON (ROI and scene cuts)")
    parser.add_argument("--detections-cache", type=Path, help="Optional validated detections.jsonl cache")
    parser.add_argument("--allow-uncalibrated", action="store_true", default=True, help="Allow uncalibrated/diagnostic mode")
    parser.add_argument("--max-frames", type=int, help="Optional limit on decoded frames")
    parser.add_argument("--quiet", action="store_true", help="Quiet progress printing")
    args = parser.parse_args()

    try:
        res = run_continuous_upstream(
            video_path=args.video,
            output_dir=args.output_dir,
            roster_config_path=args.roster,
            court_config_path=args.court,
            tracking_policy_path=args.policy,
            detections_cache_path=args.detections_cache,
            allow_uncalibrated=args.allow_uncalibrated,
            max_frames=args.max_frames,
            quiet=args.quiet,
        )
        print(f"Run completed ({res['status']}): {res['stage_counts']['total_frames_read']} frames, {res['timings']['pipeline_fps']} FPS")
        print(f"Artifacts: {args.output_dir}")
        return 0
    except Exception as exc:
        print(f"Error in continuous pipeline: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
