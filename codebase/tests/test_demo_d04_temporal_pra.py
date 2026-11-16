"""Comprehensive tests for Task D04: Continuous Shot Release/Made/Miss & Continuity Ball/Control/Pass."""
from __future__ import annotations

import json
import math
from pathlib import Path
import pytest

from basketball_scoreboard.shots import (
    TemporalShotFSM,
    ShotEngineConfig,
    ShotPhase,
    RimApertureGeometry,
)
from basketball_scoreboard.points import (
    PointsEngine,
    PointValueReason,
    AttributionLevel,
)
from basketball_scoreboard.continuous_orchestration import run_continuous_orchestration
from basketball_scoreboard.identity import RosterConfig


def make_mock_rim(source_time_s: float = 0.0) -> RimApertureGeometry:
    return RimApertureGeometry(
        xyxy=[900.0, 480.0, 960.0, 520.0],
        confidence=0.92,
        frame_index=0,
        source_time_s=source_time_s,
    )


def test_fsm_gap_boundary_exceeded_aborts_flight():
    """Verify max allowable continuous gap of 0.35s in flight arc strictly aborts shot."""
    fsm = TemporalShotFSM(
        config=ShotEngineConfig(max_flight_gap_seconds=0.35),
        video_id="test_vid",
    )
    rim_det = [{"xyxy": [900.0, 480.0, 960.0, 520.0], "confidence": 0.9, "class_name": "rim", "class_id": 2}]
    player_obs = [{"bbox": [500.0, 600.0, 540.0, 750.0], "sample_type": "observed", "role": "player", "track_id": "trk_1"}]

    # 1. Ready phase with ball in player hand
    fsm.step(0, 0.0, {"sample_type": "observed", "center_image": [520.0, 620.0], "confidence": 0.8}, rim_det, player_obs)
    fsm.step(1, 0.033, {"sample_type": "observed", "center_image": [520.0, 620.0], "confidence": 0.8}, rim_det, player_obs)
    # Release upward
    fsm.step(2, 0.066, {"sample_type": "observed", "center_image": [520.0, 610.0], "confidence": 0.8}, rim_det, player_obs)
    fsm.step(3, 0.100, {"sample_type": "observed", "center_image": [525.0, 595.0], "confidence": 0.8}, rim_det, player_obs)
    assert fsm.current_phase in {ShotPhase.RELEASE, ShotPhase.FLIGHT_ARC}

    # Advance to flight arc
    fsm.step(4, 0.133, {"sample_type": "observed", "center_image": [540.0, 560.0], "confidence": 0.8}, rim_det, player_obs)
    fsm.current_phase = ShotPhase.FLIGHT_ARC
    fsm.last_observed_ball_time_s = 0.133

    # Large gap: next frame at 0.500s (gap = 0.367s > 0.35s)
    rec = fsm.step(15, 0.500, {"sample_type": "missing"}, rim_det, player_obs)
    assert rec is not None
    assert rec.status == "unresolved"
    assert rec.phase == ShotPhase.ABORTED
    assert "gap_exceeded" in rec.reason_codes[0]


def test_points_engine_geometry_and_rule_profile():
    """Verify points calculation: 1PT inside arc, 2PT outside arc, unresolved if distance missing."""
    roster_dict = {
        "team_a_id": "VIE",
        "team_b_id": "TGA",
        "team_a_name": "Vietnam",
        "team_b_name": "Tonga",
        "team_a_color_rgb": [200, 20, 20],
        "team_b_color_rgb": [20, 20, 200],
        "players": [],
    }
    roster = RosterConfig.from_dict(roster_dict)
    engine = PointsEngine(roster=roster, rule_profile="fiba_3x3_standard")

    class MockShot:
        shot_id = "shot_01"
        video_id = "vid"
        outcome = "made"
        status = "auto_confirmed"
        shooter_track_id = "trk_1"
        shooter_player_id = None
        shooter_team_id = "VIE"
        release_time_s = 10.0
        outcome_time_s = 11.5
        evidence_details = {}

    # 1. Inside arc (distance = 4.5m <= 6.75m) -> 1 PT
    ev_1pt = engine.process_shot(MockShot(), player_observations=[], jersey_evidence=[], court_distance_m=4.5)
    assert ev_1pt is not None
    assert ev_1pt.point_value == 1
    assert ev_1pt.value_reason == PointValueReason.FIBA_3X3_1PT_INSIDE_ARC
    assert ev_1pt.scoring_team_id == "VIE"

    # 2. Outside arc (distance = 7.1m > 6.75m) -> 2 PT
    class MockShot2(MockShot):
        shot_id = "shot_02"
    ev_2pt = engine.process_shot(MockShot2(), player_observations=[], jersey_evidence=[], court_distance_m=7.1)
    assert ev_2pt is not None
    assert ev_2pt.point_value == 2
    assert ev_2pt.value_reason == PointValueReason.FIBA_3X3_2PT_OUTSIDE_ARC

    # 3. Missing court distance -> unresolved_geometry, NO fabricated points!
    class MockShot3(MockShot):
        shot_id = "shot_03"
    ev_missing = engine.process_shot(MockShot3(), player_observations=[], jersey_evidence=[], court_distance_m=None)
    assert ev_missing is not None
    assert ev_missing.point_value is None
    assert ev_missing.status == "unresolved_geometry"
    assert ev_missing.value_reason == PointValueReason.UNRESOLVED_GEOMETRY


def test_rim_miss_creates_eligible_missed_shot():
    """Verify rim bounce upward deflection is auto_confirmed as miss and preserves parent identity."""
    fsm = TemporalShotFSM(video_id="test_miss")
    rim_det = [{"xyxy": [900.0, 200.0, 1020.0, 250.0], "confidence": 0.85, "class_name": "rim"}]
    player_obs = [{"bbox": [400.0, 500.0, 500.0, 750.0], "sample_type": "observed", "track_id": "trk_shooter", "role": "player", "team_id": "TGA"}]

    # 1. Ready & Release
    fsm.step(0, 1.000, {"sample_type": "observed", "confidence": 0.8, "center_image": [450.0, 520.0], "xyxy": [435.0, 505.0, 465.0, 535.0]}, rim_det, player_obs)
    fsm.step(1, 1.033, {"sample_type": "observed", "confidence": 0.8, "center_image": [450.0, 520.0], "xyxy": [435.0, 505.0, 465.0, 535.0]}, rim_det, player_obs)
    fsm.step(2, 1.067, {"sample_type": "observed", "confidence": 0.8, "center_image": [460.0, 450.0], "xyxy": [445.0, 435.0, 475.0, 465.0]}, rim_det, player_obs)
    fsm.step(3, 1.100, {"sample_type": "observed", "confidence": 0.8, "center_image": [600.0, 300.0], "xyxy": [585.0, 285.0, 615.0, 315.0]}, rim_det, player_obs)

    # 2. Flight & Descent to rim iron: y moves downward (180 -> 205 -> 220)
    fsm.step(4, 1.300, {"sample_type": "observed", "confidence": 0.8, "center_image": [920.0, 180.0], "xyxy": [905.0, 165.0, 935.0, 195.0]}, rim_det, player_obs)
    fsm.step(5, 1.400, {"sample_type": "observed", "confidence": 0.8, "center_image": [920.0, 205.0], "xyxy": [905.0, 190.0, 935.0, 220.0]}, rim_det, player_obs)
    fsm.step(6, 1.450, {"sample_type": "observed", "confidence": 0.8, "center_image": [920.0, 220.0], "xyxy": [905.0, 205.0, 935.0, 235.0]}, rim_det, player_obs)

    # 3. Upward rebound deflection: y jumps from 220 back up to 195 (deflection away)
    rec = fsm.step(7, 1.500, {"sample_type": "observed", "confidence": 0.8, "center_image": [920.0, 195.0], "xyxy": [905.0, 180.0, 935.0, 210.0]}, rim_det, player_obs)

    assert rec is not None
    assert rec.status == "auto_confirmed"
    assert rec.outcome == "miss"
    assert rec.phase == ShotPhase.MISS
    assert rec.shooter_track_id == "trk_shooter"
    assert rec.shooter_team_id == "TGA"
    assert "rim_bounce_upward_deflection" in rec.reason_codes


def test_continuous_orchestration_play003_real_shot(tmp_path):
    """Test continuous pipeline on play_003 window (163.0s - 167.0s) yielding genuine shot candidate."""
    root = Path(__file__).resolve().parents[1]
    court_path = root / "configs/courts/vt_development_court.json"
    roster_path = root / "configs/rosters/vietnam_tonga.json"
    video_path = root / "assets_test/vietnam-tonga.mp4"
    cache_path = root / "outputs/quality-revision-20261116/full-match-01/video-run/detections.jsonl"
    out_dir = tmp_path / "play003_run"

    res = run_continuous_orchestration(
        video_path=video_path,
        output_dir=out_dir,
        roster_config_path=roster_path,
        court_config_path=court_path,
        detections_cache_path=cache_path,
        enable_ocr=False,
        allow_uncalibrated=True,
        start_time_s=163.0,
        end_time_s=166.5,
    )

    assert res["status"] == "completed"
    assert (out_dir / "shots_auto.jsonl").is_file()
    assert (out_dir / "events_auto.jsonl").is_file()
    assert (out_dir / "audit_trail.jsonl").is_file()
    assert (out_dir / "boxscore_auto.csv").is_file()
