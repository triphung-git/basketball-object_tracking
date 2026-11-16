"""Unit tests for Temporal Shot Engine, Basket Confirmation, and Bounded Shooter History."""
from __future__ import annotations

import pytest

from basketball_scoreboard.identity import RosterConfig, RosterPlayer
from basketball_scoreboard.points import (
    AttributionLevel,
    BoundedShooterHistoryResolver,
    PointEventRecord,
    PointsEngine,
    PointValueReason,
)
from basketball_scoreboard.shots import (
    RimApertureGeometry,
    ShotCandidateRecord,
    ShotEngineConfig,
    ShotPhase,
    TemporalShotFSM,
)


@pytest.fixture
def mock_roster() -> RosterConfig:
    return RosterConfig(
        team_a_id="team_a",
        team_b_id="team_b",
        team_a_name="Vietnam",
        team_b_name="Tonga",
        team_a_color_rgb=(200, 30, 30),
        team_b_color_rgb=(230, 230, 230),
        players=[
            RosterPlayer(player_id="a_01", team_id="team_a", jersey_number="1", name="Nguyen Huynh Phu Vinh"),
            RosterPlayer(player_id="a_06", team_id="team_a", jersey_number="6", name="Nguyen Phuc Vinh"),
            RosterPlayer(player_id="a_13", team_id="team_a", jersey_number="13", name="Nguyen Anh Kiet"),
            RosterPlayer(player_id="b_01", team_id="team_b", jersey_number="1", name="Marcus Christian"),
            RosterPlayer(player_id="b_18", team_id="team_b", jersey_number="18", name="Tonga Player 18"),
        ],
    )


def test_full_ordered_shot_sequence(mock_roster: RosterConfig) -> None:
    """Test standard progression: READY -> RELEASE -> FLIGHT_ARC -> OUTCOME (BASKET)."""
    fsm = TemporalShotFSM(video_id="test_play")
    rim_det = [{"xyxy": [900.0, 200.0, 1020.0, 250.0], "confidence": 0.85, "class_name": "rim"}]

    # 1. Player holds ball (READY)
    player_obs = [{"bbox": [400.0, 500.0, 500.0, 750.0], "sample_type": "observed", "track_id": "trk_01", "role": "player", "team_id": "team_a"}]
    ball_obs_ready = {"sample_type": "observed", "confidence": 0.8, "center_image": [450.0, 520.0], "xyxy": [435.0, 505.0, 465.0, 535.0]}

    fsm.step(0, 10.0, ball_obs_ready, rim_det, player_obs)
    fsm.step(1, 10.033, ball_obs_ready, rim_det, player_obs)
    assert fsm.current_phase == ShotPhase.READY

    # 2. Upward release motion
    ball_release_1 = {"sample_type": "observed", "confidence": 0.8, "center_image": [460.0, 480.0], "xyxy": [445.0, 465.0, 475.0, 495.0]}
    ball_release_2 = {"sample_type": "observed", "confidence": 0.8, "center_image": [470.0, 430.0], "xyxy": [455.0, 415.0, 485.0, 445.0]}
    fsm.step(2, 10.067, ball_release_1, rim_det, player_obs)
    fsm.step(3, 10.100, ball_release_2, rim_det, player_obs)
    assert fsm.current_phase in {ShotPhase.RELEASE, ShotPhase.FLIGHT_ARC}

    # 3. Flight towards rim
    fsm.step(4, 10.200, {"sample_type": "observed", "confidence": 0.8, "center_image": [600.0, 300.0], "xyxy": [585.0, 285.0, 615.0, 315.0]}, rim_det, player_obs)
    fsm.step(5, 10.300, {"sample_type": "observed", "confidence": 0.8, "center_image": [800.0, 210.0], "xyxy": [785.0, 195.0, 815.0, 225.0]}, rim_det, player_obs)
    assert fsm.current_phase == ShotPhase.FLIGHT_ARC

    # 4. Ball crosses rim downwards: enters upper entry band, passes ring, exits below
    # Rim is at x=[900, 1020], center=(960, 225), height=50
    # Entry: (960, 210) -> (960, 230) -> (960, 255)
    res_confirmed = None
    for step_i, (t_s, pos) in [
        (6, (10.400, [960.0, 210.0])),
        (7, (10.433, [960.0, 230.0])),
        (8, (10.467, [960.0, 260.0])),
    ]:
        b_obs = {"sample_type": "observed", "confidence": 0.8, "center_image": pos, "xyxy": [pos[0]-15, pos[1]-15, pos[0]+15, pos[1]+15]}
        r = fsm.step(step_i, t_s, b_obs, rim_det, player_obs)
        if r is not None:
            res_confirmed = r

    assert res_confirmed is not None
    assert res_confirmed.outcome == "made"
    assert res_confirmed.status == "auto_confirmed"
    assert res_confirmed.phase == ShotPhase.BASKET
    assert res_confirmed.shooter_track_id == "trk_01"


def test_single_frame_overlap_rejected(mock_roster: RosterConfig) -> None:
    """Test that a single frame overlap with rim bbox does NOT confirm made basket."""
    fsm = TemporalShotFSM(video_id="test_overlap")
    rim_det = [{"xyxy": [900.0, 200.0, 1020.0, 250.0], "confidence": 0.85, "class_name": "rim"}]
    player_obs = [{"bbox": [400.0, 500.0, 500.0, 750.0], "sample_type": "observed", "track_id": "trk_01", "role": "player", "team_id": "team_a"}]

    # Ready and release
    fsm.step(0, 1.0, {"sample_type": "observed", "confidence": 0.8, "center_image": [450.0, 520.0], "xyxy": [435.0, 505.0, 465.0, 535.0]}, rim_det, player_obs)
    fsm.step(1, 1.033, {"sample_type": "observed", "confidence": 0.8, "center_image": [460.0, 450.0], "xyxy": [445.0, 435.0, 475.0, 465.0]}, rim_det, player_obs)
    fsm.step(2, 1.100, {"sample_type": "observed", "confidence": 0.8, "center_image": [700.0, 300.0], "xyxy": [685.0, 285.0, 715.0, 315.0]}, rim_det, player_obs)

    # Only one point near rim, then ball disappears
    res = fsm.step(3, 1.200, {"sample_type": "observed", "confidence": 0.8, "center_image": [960.0, 225.0], "xyxy": [945.0, 210.0, 975.0, 240.0]}, rim_det, player_obs)
    assert res is None
    assert fsm.current_phase == ShotPhase.FLIGHT_ARC


def test_upward_below_to_above_motion_rejected() -> None:
    """Test that ball moving from below the rim to above does NOT confirm basket."""
    fsm = TemporalShotFSM(video_id="test_upward")
    rim_det = [{"xyxy": [900.0, 200.0, 1020.0, 250.0], "confidence": 0.85, "class_name": "rim"}]
    player_obs = [{"bbox": [900.0, 400.0, 1000.0, 700.0], "sample_type": "observed", "track_id": "trk_02", "role": "player", "team_id": "team_b"}]

    fsm.step(0, 1.0, {"sample_type": "observed", "confidence": 0.8, "center_image": [950.0, 450.0], "xyxy": [935.0, 435.0, 965.0, 465.0]}, rim_det, player_obs)
    fsm.step(1, 1.033, {"sample_type": "observed", "confidence": 0.8, "center_image": [950.0, 380.0], "xyxy": [935.0, 365.0, 965.0, 395.0]}, rim_det, player_obs)

    # Ball moves upward past rim: y: 260 -> 230 -> 190 (upward, vy < 0)
    fsm.step(2, 1.100, {"sample_type": "observed", "confidence": 0.8, "center_image": [960.0, 260.0], "xyxy": [945.0, 245.0, 975.0, 275.0]}, rim_det, player_obs)
    fsm.step(3, 1.133, {"sample_type": "observed", "confidence": 0.8, "center_image": [960.0, 230.0], "xyxy": [945.0, 215.0, 975.0, 245.0]}, rim_det, player_obs)
    res = fsm.step(4, 1.167, {"sample_type": "observed", "confidence": 0.8, "center_image": [960.0, 190.0], "xyxy": [945.0, 175.0, 975.0, 205.0]}, rim_det, player_obs)

    assert res is None  # Upward motion cannot score!


def test_prediction_only_crossing_rejected() -> None:
    """Test that Kalman predicted samples alone without observed sample cannot confirm basket."""
    fsm = TemporalShotFSM(video_id="test_pred_only")
    rim_det = [{"xyxy": [900.0, 200.0, 1020.0, 250.0], "confidence": 0.85, "class_name": "rim"}]
    player_obs = [{"bbox": [400.0, 500.0, 500.0, 750.0], "sample_type": "observed", "track_id": "trk_01", "role": "player", "team_id": "team_a"}]

    fsm.step(0, 1.0, {"sample_type": "observed", "confidence": 0.8, "center_image": [450.0, 520.0], "xyxy": [435.0, 505.0, 465.0, 535.0]}, rim_det, player_obs)
    fsm.step(1, 1.033, {"sample_type": "observed", "confidence": 0.8, "center_image": [460.0, 450.0], "xyxy": [445.0, 435.0, 475.0, 465.0]}, rim_det, player_obs)

    # Downward crossing sequence, but all samples are PREDICTED
    fsm.step(2, 1.100, {"sample_type": "predicted", "confidence": None, "center_image": [960.0, 210.0]}, rim_det, player_obs)
    fsm.step(3, 1.133, {"sample_type": "predicted", "confidence": None, "center_image": [960.0, 230.0]}, rim_det, player_obs)
    res = fsm.step(4, 1.167, {"sample_type": "predicted", "confidence": None, "center_image": [960.0, 260.0]}, rim_det, player_obs)

    assert res is None  # Rejects prediction-only basket


def test_bounded_causal_shooter_history(mock_roster: RosterConfig) -> None:
    """Test that OCR readings within 2s before release resolve player, while OCR after release is ignored."""
    resolver = BoundedShooterHistoryResolver(roster=mock_roster, history_window_seconds=2.0)
    release_t = 10.0

    player_obs = [
        {"track_id": "trk_10", "source_time_s": 8.5, "team_id": "team_a", "confidence": 0.95},
        {"track_id": "trk_10", "source_time_s": 9.5, "team_id": "team_a", "confidence": 0.95},
    ]

    # Valid causal OCR readings before release
    jersey_ev = [
        {"track_id": "trk_10", "source_time_s": 9.0, "detected_number": "1", "confidence": 0.95},
        # Future OCR after release (must be ignored)
        {"track_id": "trk_10", "source_time_s": 11.0, "detected_number": "18", "confidence": 0.99},
    ]

    player_id, team_id, attr_level, meta = resolver.resolve_shooter(
        shooter_track_id="trk_10",
        release_time_s=release_t,
        player_observations=player_obs,
        jersey_evidence=jersey_ev,
    )

    assert player_id == "a_01"  # Matches Nguyen Huynh Phu Vinh (#1)
    assert team_id == "team_a"
    assert attr_level == AttributionLevel.PLAYER
    assert "18" not in meta["candidate_votes"]  # Future reading at 11.0s strictly ignored!


def test_team_fallback_attribution(mock_roster: RosterConfig) -> None:
    """Test that when jersey OCR is unavailable, system falls back to TEAM attribution."""
    resolver = BoundedShooterHistoryResolver(roster=mock_roster, history_window_seconds=2.0)
    release_t = 15.0

    # Solid team observations, but zero OCR readings
    player_obs = [
        {"track_id": "trk_20", "source_time_s": 13.5, "team_id": "team_b", "confidence": 0.90},
        {"track_id": "trk_20", "source_time_s": 14.5, "team_id": "team_b", "confidence": 0.92},
    ]
    jersey_ev: list[dict] = []

    player_id, team_id, attr_level, meta = resolver.resolve_shooter(
        shooter_track_id="trk_20",
        release_time_s=release_t,
        player_observations=player_obs,
        jersey_evidence=jersey_ev,
    )

    assert player_id is None
    assert team_id == "team_b"
    assert attr_level == AttributionLevel.TEAM


def test_points_engine_idempotency(mock_roster: RosterConfig) -> None:
    """Test that processing the same shot multiple times does NOT double-count points."""
    engine = PointsEngine(roster=mock_roster)

    shot = ShotCandidateRecord(
        shot_id="shot_test_0001",
        video_id="test_play",
        segment_id="test_play",
        camera_id="cam_main",
        status="auto_confirmed",
        outcome="made",
        phase=ShotPhase.BASKET,
        release_time_s=10.0,
        outcome_time_s=11.2,
        shooter_track_id="trk_01",
    )

    player_obs = [
        {"track_id": "trk_01", "source_time_s": 9.0, "team_id": "team_a", "confidence": 0.95},
    ]
    jersey_ev = [
        {"track_id": "trk_01", "source_time_s": 9.2, "detected_number": "1", "confidence": 0.92},
    ]

    ev1 = engine.process_shot(shot, player_obs, jersey_ev, court_distance_m=5.0)
    assert ev1 is not None
    assert ev1.point_value == 1
    assert engine.team_points["team_a"] == 1

    # Second processing with same shot_id (e.g. seek / reload)
    ev2 = engine.process_shot(shot, player_obs, jersey_ev, court_distance_m=5.0)
    assert ev2 is None  # Suppressed by idempotency!
    assert engine.team_points["team_a"] == 1  # Still 1, no duplicate counting!


def test_fiba_3x3_point_values(mock_roster: RosterConfig) -> None:
    """Test 1 point inside arc and 2 points outside arc (6.75m threshold)."""
    engine = PointsEngine(roster=mock_roster)

    shot_inside = ShotCandidateRecord(
        shot_id="shot_in",
        video_id="test",
        segment_id="test",
        camera_id="cam",
        status="auto_confirmed",
        outcome="made",
        phase=ShotPhase.BASKET,
        release_time_s=5.0,
        shooter_track_id="trk_01",
    )
    obs = [{"track_id": "trk_01", "source_time_s": 4.5, "team_id": "team_a", "confidence": 0.9}]
    ev_in = engine.process_shot(shot_inside, obs, [], court_distance_m=4.5)
    assert ev_in is not None
    assert ev_in.point_value == 1
    assert ev_in.value_reason == PointValueReason.FIBA_3X3_1PT_INSIDE_ARC

    shot_outside = ShotCandidateRecord(
        shot_id="shot_out",
        video_id="test",
        segment_id="test",
        camera_id="cam",
        status="auto_confirmed",
        outcome="made",
        phase=ShotPhase.BASKET,
        release_time_s=15.0,
        shooter_track_id="trk_01",
    )
    ev_out = engine.process_shot(shot_outside, obs, [], court_distance_m=7.2)
    assert ev_out is not None
    assert ev_out.point_value == 2
    assert ev_out.value_reason == PointValueReason.FIBA_3X3_2PT_OUTSIDE_ARC


def test_rim_bounce_miss() -> None:
    """Test that ball hitting rim and deflecting upward is recognized as MISS."""
    fsm = TemporalShotFSM(video_id="test_miss")
    rim_det = [{"xyxy": [900.0, 200.0, 1020.0, 250.0], "confidence": 0.85, "class_name": "rim"}]
    player_obs = [{"bbox": [400.0, 500.0, 500.0, 750.0], "sample_type": "observed", "track_id": "trk_01", "role": "player", "team_id": "team_a"}]

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
    res = fsm.step(7, 1.500, {"sample_type": "observed", "confidence": 0.8, "center_image": [920.0, 195.0], "xyxy": [905.0, 180.0, 935.0, 210.0]}, rim_det, player_obs)

    assert res is not None
    assert res.outcome == "miss"
    assert res.phase == ShotPhase.MISS
    assert "rim_bounce_upward_deflection" in res.reason_codes


def test_cooldown_replay_suppression() -> None:
    """Test that a repeated shot within the cooldown window is suppressed (anti-duplication)."""
    fsm = TemporalShotFSM(video_id="test_cooldown")
    rim_det = [{"xyxy": [900.0, 200.0, 1020.0, 250.0], "confidence": 0.85, "class_name": "rim"}]
    player_obs = [{"bbox": [400.0, 500.0, 500.0, 750.0], "sample_type": "observed", "track_id": "trk_01", "role": "player", "team_id": "team_a"}]

    # First shot succeeds at t=10.4
    fsm.last_confirmed_shot_time_s = 10.4

    # New ball motion begins at t=11.0 (only 0.6s later, within 2.0s cooldown)
    res = fsm.step(10, 11.0, {"sample_type": "observed", "confidence": 0.8, "center_image": [450.0, 520.0]}, rim_det, player_obs)
    assert res is None  # Suppressed by cooldown


def test_continuous_predicted_centers_cannot_bridge_observation_gap() -> None:
    """Gap of 0.8s must be blocked even when tracker continuously emits predicted centers."""
    fsm = TemporalShotFSM(video_id="test_pred_bridge", config=ShotEngineConfig(max_flight_gap_seconds=0.35))
    fsm.current_phase = ShotPhase.FLIGHT_ARC
    fsm.current_shot_id = "s_bridge"
    fsm.release_time_s = 5.0
    fsm.release_frame_idx = 150
    fsm.last_observed_ball_time_s = 5.0

    rim_det = [{"xyxy": [90.0, 90.0, 110.0, 110.0], "confidence": 0.9, "class_name": "rim"}]

    # Real observation at 5.1s
    res0 = fsm.step(151, 5.1, {"sample_type": "observed", "confidence": 0.9, "center_image": [100.0, 85.0]}, rim_det, [])
    assert res0 is None
    assert fsm.current_phase == ShotPhase.FLIGHT_ARC

    # Continuous predicted samples from 5.2s to 5.8s (gap between observations reaches 0.7s)
    # At 5.5s (5.5 - 5.1 = 0.4s > 0.35s), FSM must abort despite predicted center present!
    res1 = fsm.step(152, 5.2, {"sample_type": "predicted", "center_image": [100.0, 90.0]}, rim_det, [])
    assert res1 is None
    res2 = fsm.step(153, 5.3, {"sample_type": "predicted", "center_image": [100.0, 93.0]}, rim_det, [])
    assert res2 is None
    res3 = fsm.step(154, 5.4, {"sample_type": "predicted", "center_image": [100.0, 96.0]}, rim_det, [])
    assert res3 is None
    res4 = fsm.step(155, 5.5, {"sample_type": "predicted", "center_image": [100.0, 99.0]}, rim_det, [])
    # At 5.5s, gap is 0.40s > 0.35s -> aborted!
    assert res4 is not None
    assert res4.outcome == "unresolved"
    assert res4.phase == ShotPhase.ABORTED
    assert fsm.current_phase == ShotPhase.READY


def test_duplicate_and_reversed_pts_handling() -> None:
    """Duplicate frame index is ignored; reversed timestamp resets FSM."""
    fsm = TemporalShotFSM(video_id="test_dup")
    rim_det = [{"xyxy": [900.0, 200.0, 1020.0, 250.0], "confidence": 0.85, "class_name": "rim"}]
    player_obs = [{"bbox": [400.0, 500.0, 500.0, 750.0], "sample_type": "observed", "track_id": "trk_01", "role": "player", "team_id": "team_a"}]

    ball_obs = {"sample_type": "observed", "confidence": 0.8, "center_image": [450.0, 520.0]}
    fsm.step(10, 1.0, ball_obs, rim_det, player_obs)
    assert len(fsm.ball_trajectory) == 1

    # Duplicate frame 10: must not increment trajectory or change state
    fsm.step(10, 1.0, ball_obs, rim_det, player_obs)
    assert len(fsm.ball_trajectory) == 1

    # Reversed timestamp: frame 11 with t=0.5s < 1.0s -> resets
    fsm.current_phase = ShotPhase.FLIGHT_ARC
    fsm.step(11, 0.5, ball_obs, rim_det, player_obs)
    assert fsm.current_phase == ShotPhase.READY


def test_stale_rim_detection_prevents_made_confirmation() -> None:
    """Rim detection older than 1.5s is considered stale and cannot confirm made basket."""
    fsm = TemporalShotFSM(video_id="test_stale_rim", config=ShotEngineConfig(enable_net_cue=False))
    fsm.current_phase = ShotPhase.FLIGHT_ARC
    fsm.current_shot_id = "s_stale"
    fsm.release_time_s = 5.0
    fsm.last_observed_ball_time_s = 5.0

    # Old rim detection at t=3.0s
    old_rim = [{"xyxy": [90.0, 90.0, 110.0, 110.0], "confidence": 0.9, "class_name": "rim"}]
    fsm.step(100, 3.0, None, old_rim, [])

    # Flight reaches rim at t=5.5s (gap from rim sample is 2.5s > 1.5s, rim is stale!)
    res1 = fsm.step(151, 5.4, {"sample_type": "observed", "confidence": 0.9, "center_image": [100.0, 85.0]}, [], [])
    res2 = fsm.step(152, 5.5, {"sample_type": "observed", "confidence": 0.9, "center_image": [100.0, 105.0]}, [], [])
    assert res2 is None or res2.outcome != "made"


def test_conflicting_ball_tracks_during_crossing_rejected() -> None:
    """Observations belonging to two different ball tracks during crossing cannot confirm made."""
    fsm = TemporalShotFSM(video_id="test_conflicting_tracks", config=ShotEngineConfig(enable_net_cue=False))
    fsm.current_phase = ShotPhase.FLIGHT_ARC
    fsm.current_shot_id = "s_tracks"
    fsm.release_time_s = 5.0
    fsm.last_observed_ball_time_s = 5.0

    rim = [{"xyxy": [90.0, 90.0, 110.0, 110.0], "confidence": 0.9, "class_name": "rim"}]

    # Entry with track_id = ball_track_1
    fsm.step(151, 5.1, {"sample_type": "observed", "confidence": 0.9, "center_image": [100.0, 85.0], "track_id": "ball_track_1"}, rim, [])
    # Exit with track_id = ball_track_2 (swapped or conflicting track)
    res = fsm.step(152, 5.2, {"sample_type": "observed", "confidence": 0.9, "center_image": [100.0, 105.0], "track_id": "ball_track_2"}, rim, [])
    assert res is None or res.outcome != "made"

