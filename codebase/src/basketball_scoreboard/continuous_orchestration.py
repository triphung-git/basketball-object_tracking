"""Continuous Event Orchestration Pipeline: Upstream Stream -> FSM Shots -> PTS/REB/AST -> Ledger -> BoxScore.

Orchestrates real continuous video frames through:
  - TemporalShotFSM: recognizes shot releases, flight arcs, and rim crossings.
  - PointsEngine: calculates point values (1PT/2PT) and shooter attribution.
  - ReboundEngine: evaluates ball control following missed field goals.
  - AssistEngine: adjudicates causal teammate passes leading to made field goals.
  - EventLedger: versioned append-only transaction ledger with causal dependency tracking.
  - BoxScoreEngine: compiles team and player statistics upholding mathematical conservation.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np

from basketball_scoreboard.assists import AssistCandidate, AssistEngine, AssistEngineConfig
from basketball_scoreboard.boxscore import BoxScoreEngine, PlayerBoxScore, TeamBoxScore
from basketball_scoreboard.config import APPROVED_MODEL_ID, ModelConfig
from basketball_scoreboard.continuous_stream import (
    ContinuousStreamFrame,
    stream_continuous_upstream,
)
from basketball_scoreboard.contracts import (
    DetectionRecord,
    FrameDetectionsRecord,
)
from basketball_scoreboard.calibration_scope import load_bound_court
from basketball_scoreboard.court import (
    CourtConfig,
    CourtModel,
    TrajectoryObservation,
    UncalibratedCourtError,
)
from basketball_scoreboard.heatmap import (
    ExclusionInterval,
    HeatmapAccumulator,
    compute_court_region_stats,
)
from basketball_scoreboard.events import (
    EventLedger,
    EventStatus,
    EventType,
    LedgerEventRecord,
    point_event_to_ledger_record,
)
from basketball_scoreboard.identity import (
    IdentityResolver,
    OCRProvider,
    RosterConfig,
    RosterPlayer,
)
from basketball_scoreboard.points import (
    AttributionLevel,
    PointEventRecord,
    PointsEngine,
    PointValueReason,
)
from basketball_scoreboard.rebounds import ReboundCandidate, ReboundEngine, ReboundEngineConfig
from basketball_scoreboard.shots import (
    RimApertureGeometry,
    ShotCandidateRecord,
    ShotEngineConfig,
    ShotPhase,
    TemporalShotFSM,
)
from basketball_scoreboard.tracking_policy import load_tracking_policy
from basketball_scoreboard.video import compute_file_sha256, probe_video

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class OrchestrationResult:
    """Canonical execution result for continuous end-to-end video analysis."""
    status: str
    run_id: str
    output_dir: Path
    video_sha256: str
    total_frames: int
    shots_count: int
    points_total: int
    rebounds_total: int
    assists_total: int
    ledger_events_count: int
    boxscore_summary: Dict[str, Any]
    run_metadata: Dict[str, Any]


def run_continuous_orchestration(
    video_path: Path | str,
    output_dir: Path | str,
    roster_config_path: Path | str,
    court_config_path: Optional[Path | str] = None,
    tracking_policy_path: Optional[Path | str] = None,
    detections_cache_path: Optional[Path | str] = None,
    model_config: Optional[ModelConfig] = None,
    detector_factory: Optional[Callable[[], Any]] = None,
    shot_config: Optional[ShotEngineConfig] = None,
    rebound_config: Optional[ReboundEngineConfig] = None,
    assist_config: Optional[AssistEngineConfig] = None,
    allow_uncalibrated: bool = True,
    max_frames: Optional[int] = None,
    start_time_s: Optional[float] = None,
    end_time_s: Optional[float] = None,
    ocr_provider: Optional[OCRProvider] = None,
    ocr_cache_path: Optional[Path | str] = None,
    enable_ocr: bool = True,
    ocr_interval_frames: int = 15,
    quiet: bool = False,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """Execute complete continuous video pipeline from MP4 to BoxScore."""
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

    # 1. Load Roster
    r_path = Path(roster_config_path).resolve()
    if not r_path.is_file():
        raise FileNotFoundError(f"Roster config not found: {r_path}")
    roster_data = json.loads(r_path.read_text(encoding="utf-8"))
    for req_field in ["team_a_id", "team_b_id", "team_a_name", "team_b_name", "team_a_color_rgb", "team_b_color_rgb", "players"]:
        if req_field not in roster_data:
            raise ValueError(f"Missing required field '{req_field}' in roster JSON")
    if not allow_uncalibrated and (roster_data.get("provenance_status") != "approved" or roster_data.get("is_synthetic")):
        raise ValueError("Draft or synthetic roster requires allow_uncalibrated=True")
    roster = RosterConfig.from_dict(roster_data)

    # 2. Tracking policy
    policy = None
    if tracking_policy_path:
        policy = load_tracking_policy(tracking_policy_path, video_sha)

    # 3. Court geometry
    court_model, court_cfg, geometry_status = load_bound_court(
        court_config_path, video_sha, metadata, start_time_s, end_time_s,
        max_frames, allow_uncalibrated,
    )
    court_dist_m: Optional[float] = None

    # 4. Heatmap accumulator setup if calibrated
    accumulator: Optional[HeatmapAccumulator] = None
    if geometry_status == "calibrated" and court_cfg is not None:
        team_a_name = roster.team_a_id if roster else "team_a"
        team_b_name = roster.team_b_id if roster else "team_b"
        excl_list: List[ExclusionInterval] = []
        if tracking_policy_path:
            tp_p = Path(tracking_policy_path).resolve()
            if tp_p.is_file():
                try:
                    tp_data = json.loads(tp_p.read_text(encoding="utf-8"))
                    for item in tp_data.get("intervals", []):
                        excl_list.append(ExclusionInterval(
                            start_s=float(item["start_time_s"]),
                            end_s=float(item["end_time_s"]),
                            reason=item.get("reason", "cut"),
                        ))
                except Exception:
                    pass
        accumulator = HeatmapAccumulator(
            court_bounds=court_cfg.court_coordinate_system.court_bounds,
            grid_shape=(50, 50),
            units=court_cfg.court_coordinate_system.units,
            team_a_id=team_a_name,
            team_b_id=team_b_name,
            max_gap_s=1.0,
            timestamp_policy="allow_repaired_with_warning",
            exclusions=excl_list,
            allow_unknown_role=allow_uncalibrated,
        )

    # 5. Initialize Engines
    s_cfg = shot_config or ShotEngineConfig(
        enable_net_cue=True,
        shot_cooldown_seconds=2.0,
        replay_suppression_enabled=True,
    )
    shot_fsm = TemporalShotFSM(config=s_cfg, video_id=metadata.video_id)
    points_engine = PointsEngine(roster=roster)
    reb_cfg = rebound_config or ReboundEngineConfig()
    rebound_engine = ReboundEngine(config=reb_cfg)
    ast_cfg = assist_config or AssistEngineConfig()
    assist_engine = AssistEngine(config=ast_cfg)
    ledger = EventLedger(ledger_id=out_dir.name)
    box_engine = BoxScoreEngine(roster=roster)

    # File writers for intermediate streaming artifacts
    dets_handle = (out_dir / "detections.jsonl").open("w", encoding="utf-8")
    tracks_handle = (out_dir / "tracked_observations.jsonl").open("w", encoding="utf-8")
    ball_handle = (out_dir / "ball_tracks.jsonl").open("w", encoding="utf-8")
    ctrl_handle = (out_dir / "possession_control.jsonl").open("w", encoding="utf-8")

    total_frames = 0
    total_cut_frames = 0
    confirmed_shots: List[ShotCandidateRecord] = []
    pending_missed_shots: List[ShotCandidateRecord] = []
    recent_player_obs: List[Dict[str, Any]] = []
    all_player_obs: List[TrajectoryObservation] = []
    recent_controls: List[Dict[str, Any]] = []
    intervening_events: List[Dict[str, Any]] = []
    all_passes: List[Dict[str, Any]] = []

    last_resolver = None
    status = "running"
    failure = None
    first_source_time_s = None
    last_source_time_s = None

    last_stage_state = {}
    try:
        upstream_gen = stream_continuous_upstream(
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

        for frame, image, stage_state in upstream_gen:
            total_frames += 1
            t_s = frame.source_time_s
            f_idx = frame.frame_index
            last_stage_state = stage_state
            if first_source_time_s is None:
                first_source_time_s = t_s
            last_source_time_s = t_s
            if progress_callback and (total_frames == 1 or total_frames % 30 == 0):
                progress_callback({"frames_processed": total_frames,
                                   "source_time_s": t_s,
                                   "elapsed_s": time.perf_counter() - started_t})

            if frame.is_cut:
                total_cut_frames += 1
                intervening_events.append({
                    "event_type": "cut",
                    "reason": frame.cut_reason or "scene_cut",
                    "source_time_s": t_s,
                })

            last_resolver = stage_state.get("resolver")
            possession_engine = stage_state.get("possession_engine")
            if possession_engine and possession_engine.passes:
                all_passes = possession_engine.passes

            # Write upstream records
            det_rec = FrameDetectionsRecord(
                video_id=metadata.video_id,
                frame_index=f_idx,
                source_time_s=t_s,
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

            for obs in frame.player_observations:
                tracks_handle.write(json.dumps(obs, allow_nan=False) + "\n")
                if court_model is not None:
                    t_obs = TrajectoryObservation(
                        schema_version=obs.get("schema_version", "2.0.0"),
                        observation_id=str(obs["observation_id"]),
                        source_run_id=str(obs.get("source_run_id", metadata.video_id)),
                        video_id=str(obs.get("video_id", metadata.video_id)),
                        source_fingerprint_sha256=str(obs.get("source_fingerprint_sha256", video_sha)),
                        frame_index=int(obs.get("frame_index", f_idx)),
                        source_time_s=float(obs.get("source_time_s", t_s)),
                        timestamp_status=str(obs.get("timestamp_status", frame.timestamp_status)),
                        segment_id=str(obs.get("segment_id", "default")),
                        camera_id=str(obs.get("camera_id", "cam_main")),
                        bbox=list(obs["bbox"]),
                        footpoint_image=tuple(obs["footpoint_image"]) if obs.get("footpoint_image") is not None else (0.0, 0.0),
                        position_method=str(obs.get("position_method", "bbox_bottom_center")),
                        projected_court_xy=tuple(obs["projected_court_xy"]) if obs.get("projected_court_xy") is not None else None,
                        court_units=str(obs.get("court_units", "meters")),
                        validity_status=str(obs.get("validity_status", "valid")),
                        validity_reason=obs.get("validity_reason"),
                        calibration_version=obs.get("calibration_version"),
                        track_id=str(obs["track_id"]) if obs.get("track_id") is not None else None,
                        player_id=str(obs["player_id"]) if obs.get("player_id") is not None else None,
                        team_id=str(obs["team_id"]) if obs.get("team_id") is not None else None,
                        role=str(obs.get("role", "unknown")),
                        sample_type=str(obs.get("sample_type", "observed")),
                        confidence=float(obs.get("confidence", 1.0)),
                    )
                    all_player_obs.append(t_obs)
            recent_player_obs.extend(frame.player_observations)
            # Maintain a rolling window of recent player observations (~4.0s)
            cutoff_t = t_s - 4.5
            recent_player_obs = [o for o in recent_player_obs if o.get("source_time_s", 0.0) >= cutoff_t]

            ball_handle.write(json.dumps(frame.ball_observation, allow_nan=False) + "\n")
            ctrl_handle.write(json.dumps(frame.control_observation, allow_nan=False) + "\n")
            recent_controls.append(frame.control_observation)
            recent_controls = [c for c in recent_controls if c.get("source_time_s", 0.0) >= cutoff_t]

            # Track chain breaks for assists
            ctrl_state = frame.control_observation.get("state")
            if ctrl_state in {"loose", "contested"}:
                intervening_events.append({
                    "event_type": "loose_ball" if ctrl_state == "loose" else "deflection",
                    "source_time_s": t_s,
                })

            # 5. Feed into TemporalShotFSM
            shot_res = shot_fsm.step(
                frame_idx=f_idx,
                source_time_s=t_s,
                ball_obs=frame.ball_observation,
                rim_detections=frame.rim_detections,
                player_observations=frame.player_observations,
                camera_layout_invalid=frame.is_cut,
            )

            if shot_res is not None:
                confirmed_shots.append(shot_res)

                # Process Made Basket
                if shot_res.outcome == "made":
                    # Project shooter distance using calibrated court model if available
                    shooter_dist_m: Optional[float] = None
                    court_xy: Optional[tuple[float, float]] = None
                    if court_model is not None and shot_res.shooter_track_id:
                        rel_t = shot_res.release_time_s or (t_s - 1.0)
                        matching_obs = [
                            o for o in recent_player_obs
                            if o.get("track_id") == shot_res.shooter_track_id
                            and abs(o.get("source_time_s", 0.0) - rel_t) <= 1.0
                        ]
                        if matching_obs:
                            best_obs = min(matching_obs, key=lambda o: abs(o.get("source_time_s", 0.0) - rel_t))
                            fp = best_obs.get("footpoint_image") or (
                                [(best_obs["bbox"][0] + best_obs["bbox"][2]) / 2.0, best_obs["bbox"][3]]
                                if "bbox" in best_obs else None
                            )
                            if fp:
                                court_xy = court_model.project_image_to_court(fp)
                                if court_xy is not None:
                                    shooter_dist_m = math.dist(court_xy, (0.0, 1.575))

                    track_jersey_ev = []
                    if last_resolver and hasattr(last_resolver, "jersey_evidence"):
                        ev_list = last_resolver.jersey_evidence.get(shot_res.shooter_track_id, [])
                        track_jersey_ev = [
                            e.to_dict() if hasattr(e, "to_dict") else e
                            for e in ev_list
                            if getattr(e, "is_valid", True) and getattr(e, "source_time_s", 0.0) <= t_s
                        ]
                    point_event = points_engine.process_shot(
                        shot=shot_res,
                        player_observations=recent_player_obs,
                        jersey_evidence=track_jersey_ev,
                        is_free_throw=False,
                        court_distance_m=shooter_dist_m if shooter_dist_m is not None else court_dist_m,
                    )
                    if point_event is not None:
                        ledger_rec = point_event_to_ledger_record(point_event, frame_index=f_idx)
                        ledger_rec.event_id = shot_res.shot_id
                        if court_xy is not None:
                            ledger_rec.evidence["court_x_m"] = round(float(court_xy[0]), 3)
                            ledger_rec.evidence["court_y_m"] = round(float(court_xy[1]), 3)
                            if shooter_dist_m is not None:
                                ledger_rec.evidence["court_distance_m"] = round(float(shooter_dist_m), 3)
                        ledger.record_event(ledger_rec)

                        # Evaluate Assist for made basket
                        scorer_tid = point_event.scoring_team_id
                        scorer_pid = point_event.scoring_player_id
                        ast_candidate = assist_engine.evaluate_made_shot(
                            shot_id=shot_res.shot_id,
                            shot_outcome="made",
                            scorer_team_id=scorer_tid,
                            scorer_player_id=scorer_pid,
                            release_time_s=shot_res.release_time_s or t_s,
                            pass_events=all_passes,
                            intervening_events=intervening_events,
                        )
                        if ast_candidate is not None:
                            ast_ledger_rec = ast_candidate.to_ledger_record()
                            ledger.record_event(ast_ledger_rec)

                # Process Missed Shot (queue for subsequent rebound recovery)
                elif shot_res.outcome in {"miss", "rim_hit", "rim_bounce", "airball"}:
                    pending_missed_shots.append(shot_res)

            # Evaluate any pending missed shots against accumulated recovery controls
            remaining_pending: List[ShotCandidateRecord] = []
            for m_shot in pending_missed_shots:
                miss_t = m_shot.outcome_time_s if m_shot.outcome_time_s is not None else m_shot.release_time_s or t_s
                reb_candidate = rebound_engine.evaluate_missed_shot(
                    shot_id=m_shot.shot_id,
                    shot_outcome=m_shot.outcome,
                    shooting_team_id=m_shot.shooter_team_id,
                    miss_time_s=miss_t,
                    control_observations=recent_controls,
                    is_last_free_throw=False,
                )
                if reb_candidate is not None:
                    reb_ledger_rec = reb_candidate.to_ledger_record()
                    ledger.record_event(reb_ledger_rec)
                elif t_s <= miss_t + reb_engine_window(rebound_engine):
                    remaining_pending.append(m_shot)
            pending_missed_shots = remaining_pending

            if not quiet and total_frames % 100 == 0:
                print(f"[02B Orchestration] Processed {total_frames} frames ({t_s:.2f}s) | shots={len(confirmed_shots)}")

        if total_frames == 0:
            raise ValueError("No frames processed from input video")

        requested_end = end_time_s if end_time_s is not None else metadata.duration_s
        reached_end = last_source_time_s is not None and last_source_time_s + 1.5 / metadata.fps >= requested_end
        status = "partial" if max_frames and total_frames >= max_frames and not reached_end else "completed"

    except (Exception, KeyboardInterrupt) as exc:
        status = "cancelled" if isinstance(exc, KeyboardInterrupt) else "failed"
        failure = f"{type(exc).__name__}: {str(exc)}"
        raise
    finally:
        dets_handle.close()
        tracks_handle.close()
        ball_handle.close()
        ctrl_handle.close()

        # Copy alias
        if (out_dir / "possession_control.jsonl").is_file():
            (out_dir / "ball_control.jsonl").write_bytes((out_dir / "possession_control.jsonl").read_bytes())

        # Export passes
        with (out_dir / "pass_events.jsonl").open("w", encoding="utf-8") as handle:
            for p in all_passes:
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

        # Export Shots
        with (out_dir / "shots_auto.jsonl").open("w", encoding="utf-8") as handle:
            for s in confirmed_shots:
                handle.write(json.dumps(s.to_dict(), allow_nan=False) + "\n")

        # Compile and export BoxScore
        team_a_box, team_b_box = box_engine.compile(ledger)
        box_engine.export_csv(team_a_box, team_b_box, out_dir / "boxscore_auto.csv")

        # Export Ledger views
        ledger.export_jsonl(out_dir / "events_auto.jsonl")
        ledger.export_raw_transactions(out_dir / "events_raw.jsonl")
        ledger.export_audit_log(out_dir / "audit_trail.jsonl")
        ledger_chk = ledger.save_checkpoint(out_dir / "checkpoint.json")

        # Export trajectories for spatial validation
        with (out_dir / "trajectories.jsonl").open("w", encoding="utf-8") as handle:
            for to in all_player_obs:
                handle.write(to.to_json() + "\n")

        # Spatial / Heatmap Accumulation
        total_mass = 0.0
        comp_sum = 0.0
        conserved = True
        region_stats: Dict[str, Any] = {}

        if accumulator is not None and all_player_obs:
            accumulator.process_observations_batch(all_player_obs, track_grouped=True, final_time_s=last_source_time_s)
            conserved, total_mass, comp_sum = accumulator.verify_mass_conservation()
            accumulator.export_raw_grid(str(out_dir / "heatmap_raw_grid.json"))
            accumulator.render_png(str(out_dir / "heatmap.png"), title="Observed Player Court Occupancy")
            accumulator.render_png(str(out_dir / "heatmap_total.png"), title="Observed Player Court Occupancy")
            if accumulator.metadata.team_a_player_seconds > 0:
                accumulator.render_png(str(out_dir / "heatmap_team_a.png"), grid_type="team_a", title=f"Court Occupancy - {accumulator.team_a_id}")
            if accumulator.metadata.team_b_player_seconds > 0:
                accumulator.render_png(str(out_dir / "heatmap_team_b.png"), grid_type="team_b", title=f"Court Occupancy - {accumulator.team_b_id}")
            region_stats = compute_court_region_stats(accumulator)

        heatmap_summary = {
            "status": "generated" if geometry_status == "calibrated" else "unavailable",
            "reason": (
                "Generated from calibrated court homography" if geometry_status == "calibrated"
                else "Court geometry is uncalibrated / diagnostic mode; physical court heatmap generation suspended to prevent fabricated coordinates"
            ),
            "acceptance_scope": "technical" if geometry_status == "calibrated" else "diagnostic",
            "geometry_status": geometry_status,
            "calibration_version": court_model.calibration_version if court_model else None,
            "court_config_path": str(court_config_path) if court_config_path else None,
            "court_bounds": court_cfg.court_coordinate_system.court_bounds if court_cfg else None,
            "units": court_cfg.court_coordinate_system.units if court_cfg else "meters",
            "total_player_seconds": round(float(total_mass), 6),
            "team_a_player_seconds": round(float(accumulator.metadata.team_a_player_seconds), 6) if accumulator else 0.0,
            "team_b_player_seconds": round(float(accumulator.metadata.team_b_player_seconds), 6) if accumulator else 0.0,
            "unknown_team_player_seconds": round(float(accumulator.metadata.unknown_team_player_seconds), 6) if accumulator else 0.0,
            "outside_bounds_player_seconds": round(float(accumulator.metadata.outside_bounds_player_seconds), 6) if accumulator else 0.0,
            "excluded_player_seconds": round(float(accumulator.metadata.excluded_player_seconds), 6) if accumulator else 0.0,
            "stale_gap_discarded_seconds": round(float(accumulator.metadata.stale_gap_discarded_seconds), 6) if accumulator else 0.0,
            "observations_count": len(all_player_obs),
            "valid_court_observations": sum(1 for o in all_player_obs if o.validity_status == "valid"),
            "mass_conservation": {
                "is_conserved": conserved,
                "total_mass_player_seconds": round(float(total_mass), 6),
                "components_sum_player_seconds": round(float(comp_sum), 6),
            },
            "region_stats": region_stats,
        }
        (out_dir / "heatmap_summary.json").write_text(
            json.dumps(heatmap_summary, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        elapsed_s = time.perf_counter() - started_t
        active_events = ledger.get_active_events()
        pts_total = team_a_box.total_score + team_b_box.total_score
        reb_total = team_a_box.rebounds_total + team_b_box.rebounds_total
        ast_total = team_a_box.assists + team_b_box.assists

        run_artifacts = {
            "run_json": "run.json",
            "shots_auto_jsonl": "shots_auto.jsonl",
            "events_auto_jsonl": "events_auto.jsonl",
            "events_raw_jsonl": "events_raw.jsonl",
            "audit_trail_jsonl": "audit_trail.jsonl",
            "checkpoint_json": "checkpoint.json",
            "boxscore_auto_csv": "boxscore_auto.csv",
            "heatmap_summary_json": "heatmap_summary.json",
            "detections_jsonl": "detections.jsonl",
            "tracked_observations_jsonl": "tracked_observations.jsonl",
            "trajectories_jsonl": "trajectories.jsonl",
            "ball_tracks_jsonl": "ball_tracks.jsonl",
            "possession_control_jsonl": "possession_control.jsonl",
            "ball_control_jsonl": "ball_control.jsonl",
            "pass_events_jsonl": "pass_events.jsonl",
            "passes_jsonl": "passes.jsonl",
            "identity_mappings_json": "identity_mappings.json",
            "jersey_evidence_json": "jersey_evidence.json",
        }
        if accumulator is not None:
            run_artifacts["heatmap_raw_grid_json"] = "heatmap_raw_grid.json"
            run_artifacts["heatmap_png"] = "heatmap.png"
            run_artifacts["heatmap_total_png"] = "heatmap_total.png"
            if accumulator.metadata.team_a_player_seconds > 0:
                run_artifacts["heatmap_team_a_png"] = "heatmap_team_a.png"
            if accumulator.metadata.team_b_player_seconds > 0:
                run_artifacts["heatmap_team_b_png"] = "heatmap_team_b.png"

        run_result = {
            "schema_version": "2.1.0",
            "run_id": out_dir.name,
            "status": status,
            "error_message": failure,
            "video_path": str(vid_path),
            "video_id": metadata.video_id,
            "source_fingerprint_sha256": video_sha,
            "source_coverage": {
                "first_time_s": first_source_time_s,
                "last_time_s": last_source_time_s,
                "requested_start_s": start_time_s,
                "requested_end_s": end_time_s,
            },
            "video_metadata": metadata.to_dict(),
            "geometry": {
                "status": geometry_status,
                "court_config_path": str(court_config_path) if court_config_path else None,
                "allow_uncalibrated": allow_uncalibrated,
            },
            "roster": {
                "roster_config_path": str(roster_config_path),
                "team_a": team_a_box.team_name,
                "team_b": team_b_box.team_name,
            },
            "boxscore_totals": {
                "team_a": team_a_box.to_dict(),
                "team_b": team_b_box.to_dict(),
                "match_totals": {
                    "points": pts_total,
                    "rebounds": reb_total,
                    "assists": ast_total,
                },
            },
            "stage_counts": {
                "total_frames_read": total_frames,
                "total_cut_frames": total_cut_frames,
                "confirmed_shots": len(confirmed_shots),
                "active_ledger_events": len(active_events),
                "points_events": len([e for e in active_events if e.event_type == EventType.SHOT]),
                "rebound_events": len([e for e in active_events if e.event_type == EventType.REBOUND]),
                "assist_events": len([e for e in active_events if e.event_type == EventType.ASSIST]),
                "passes": len(all_passes),
            },
            "timings": {
                "total_pipeline_s": round(elapsed_s, 4),
                "pipeline_fps": round(total_frames / elapsed_s, 2) if elapsed_s > 0 else 0.0,
            },
            "runtime": {
                "model_id": APPROVED_MODEL_ID,
                "class_mapping": {"0": "ball", "1": "human", "2": "rim"},
            },
            "artifacts": run_artifacts,
            "created_utc": created_utc,
            "completed_utc": datetime.now(timezone.utc).isoformat(),
        }

        (out_dir / "run.json").write_text(
            json.dumps(run_result, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )

    return run_result


def reb_engine_window(engine: ReboundEngine) -> float:
    return getattr(engine.config, "max_recovery_window_s", 3.5)
