"""Unit tests for Task 09 / Sequence 01B: Rebounds Engine."""
from __future__ import annotations

import pytest

from basketball_scoreboard.events import EventLedger, EventStatus, EventType, LedgerEventRecord
from basketball_scoreboard.rebounds import ReboundEngine, ReboundType


def test_made_shot_never_creates_rebound():
    engine = ReboundEngine()
    control_obs = [
        {"team_id": "team_vie", "player_id": "vie_07", "source_time_s": 15.5, "frame_index": 465},
        {"team_id": "team_vie", "player_id": "vie_07", "source_time_s": 15.6, "frame_index": 468},
        {"team_id": "team_vie", "player_id": "vie_07", "source_time_s": 15.7, "frame_index": 471},
        {"team_id": "team_vie", "player_id": "vie_07", "source_time_s": 15.8, "frame_index": 474},
    ]
    # On made shot, evaluate_missed_shot returns None
    res = engine.evaluate_missed_shot(
        shot_id="shot_made_001",
        shot_outcome="made",
        shooting_team_id="team_tga",
        miss_time_s=15.2,
        control_observations=control_obs,
    )
    assert res is None
    assert len(engine.rebound_events) == 0


def test_defensive_and_offensive_rebound_classification():
    engine = ReboundEngine()

    # 1. Tonga shoots and misses; Vietnam recovers with sustained control (Defensive Rebound)
    defensive_obs = [
        {"team_id": "team_vie", "player_id": "vie_12", "source_time_s": 20.3, "frame_index": 609},
        {"team_id": "team_vie", "player_id": "vie_12", "source_time_s": 20.4, "frame_index": 612},
        {"team_id": "team_vie", "player_id": "vie_12", "source_time_s": 20.5, "frame_index": 615},
        {"team_id": "team_vie", "player_id": "vie_12", "source_time_s": 20.6, "frame_index": 618},
    ]
    reb1 = engine.evaluate_missed_shot(
        shot_id="shot_miss_001",
        shot_outcome="miss",
        shooting_team_id="team_tga",
        miss_time_s=20.0,
        control_observations=defensive_obs,
    )
    assert reb1 is not None
    assert reb1.rebound_type == ReboundType.DEFENSIVE
    assert reb1.player_id == "vie_12"
    assert reb1.team_id == "team_vie"
    assert reb1.status == EventStatus.AUTO_CONFIRMED

    # 2. Vietnam shoots and misses; Vietnam recovers (Offensive Rebound)
    offensive_obs = [
        {"team_id": "team_vie", "player_id": "vie_07", "source_time_s": 35.3, "frame_index": 1059},
        {"team_id": "team_vie", "player_id": "vie_07", "source_time_s": 35.4, "frame_index": 1062},
        {"team_id": "team_vie", "player_id": "vie_07", "source_time_s": 35.5, "frame_index": 1065},
        {"team_id": "team_vie", "player_id": "vie_07", "source_time_s": 35.6, "frame_index": 1068},
    ]
    reb2 = engine.evaluate_missed_shot(
        shot_id="shot_miss_002",
        shot_outcome="miss",
        shooting_team_id="team_vie",
        miss_time_s=35.0,
        control_observations=offensive_obs,
    )
    assert reb2 is not None
    assert reb2.rebound_type == ReboundType.OFFENSIVE
    assert reb2.player_id == "vie_07"
    assert reb2.team_id == "team_vie"


def test_glancing_brush_rejected_by_multi_frame_guard():
    engine = ReboundEngine()
    # Single frame brush (consecutive_count = 1, duration = 0.0)
    single_touch_obs = [
        {"team_id": "team_vie", "player_id": "vie_12", "source_time_s": 50.2, "frame_index": 1506},
    ]
    res = engine.evaluate_missed_shot(
        shot_id="shot_miss_003",
        shot_outcome="miss",
        shooting_team_id="team_tga",
        miss_time_s=50.0,
        control_observations=single_touch_obs,
    )
    assert res is None


def test_ledger_integration():
    ledger = EventLedger()
    engine = ReboundEngine()

    obs = [
        {"team_id": "team_tga", "player_id": "tga_03", "source_time_s": 12.2, "frame_index": 366},
        {"team_id": "team_tga", "player_id": "tga_03", "source_time_s": 12.3, "frame_index": 369},
        {"team_id": "team_tga", "player_id": "tga_03", "source_time_s": 12.4, "frame_index": 372},
        {"team_id": "team_tga", "player_id": "tga_03", "source_time_s": 12.5, "frame_index": 375},
    ]
    reb = engine.evaluate_missed_shot(
        shot_id="shot_miss_010",
        shot_outcome="miss",
        shooting_team_id="team_vie",
        miss_time_s=12.0,
        control_observations=obs,
    )
    assert reb is not None

    record = reb.to_ledger_record()
    assert ledger.record_event(record) is True
    active = ledger.get_active_events()
    assert len(active) == 1
    assert active[0].event_type == EventType.REBOUND
    assert active[0].player_id == "tga_03"
    assert active[0].subtype == "defensive_rebound"


# --- Regression Tests for 01B ---

@pytest.mark.parametrize("outcome", ["unknown", "unresolved", "not_a_shot"])
def test_regression_rebound_requires_eligible_miss(outcome: str):
    """Verify that unknown, unresolved, or not_a_shot never produces an auto-confirmed rebound."""
    engine = ReboundEngine()
    obs = [
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.1, "frame_index": 100},
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.2, "frame_index": 103},
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.3, "frame_index": 106},
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.4, "frame_index": 109},
    ]
    res = engine.evaluate_missed_shot("shot_test", outcome, "team_b", 10.0, obs)
    assert res is None or res.status != EventStatus.AUTO_CONFIRMED


def test_regression_rebound_observed_vs_predicted():
    """Verify that predicted-only control samples cannot generate an auto-confirmed rebound."""
    engine = ReboundEngine()
    obs_pred = [
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.1, "sample_type": "predicted"},
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.2, "sample_type": "predicted"},
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.3, "sample_type": "predicted"},
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.4, "sample_type": "predicted"},
    ]
    res = engine.evaluate_missed_shot("shot_pred", "miss", "team_b", 10.0, obs_pred)
    assert res is None or res.status != EventStatus.AUTO_CONFIRMED


def test_regression_two_isolated_controls_rejected():
    """Verify that two observations with a large gap cannot be stitched into sustained control."""
    engine = ReboundEngine()
    obs_isolated = [
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.1, "frame_index": 300},
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 13.4, "frame_index": 400},
    ]
    res = engine.evaluate_missed_shot("shot_iso", "miss", "team_b", 10.0, obs_isolated)
    assert res is None or res.status != EventStatus.AUTO_CONFIRMED


def test_regression_ft_series_applicability():
    """Verify that non-final free throws do not generate rebounds, whereas final free throws do."""
    engine = ReboundEngine()
    obs = [
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.1, "frame_index": 100},
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.2, "frame_index": 103},
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.3, "frame_index": 106},
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.4, "frame_index": 109},
    ]
    # Non-final FT miss -> dead ball, no rebound
    res_non_final = engine.evaluate_missed_shot(
        shot_id="ft_non_final",
        shot_outcome="miss",
        shooting_team_id="team_b",
        miss_time_s=10.0,
        control_observations=obs,
        shot_kind="free_throw",
        is_last_free_throw=False,
    )
    assert res_non_final is None

    # Final FT miss -> live ball rebound
    res_final = engine.evaluate_missed_shot(
        shot_id="ft_final",
        shot_outcome="miss",
        shooting_team_id="team_b",
        miss_time_s=10.0,
        control_observations=obs,
        shot_kind="free_throw",
        is_last_free_throw=True,
    )
    assert res_final is not None
    assert res_final.status == EventStatus.AUTO_CONFIRMED


def test_regression_actor_switch_resets_chain():
    """Verify that actor switching resets consecutive control count."""
    engine = ReboundEngine()
    obs_switch = [
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.1, "frame_index": 100},
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.15, "frame_index": 102},
        # Switch to p2 for 1 frame
        {"team_id": "team_a", "player_id": "p2", "source_time_s": 10.2, "frame_index": 104},
        # Switch back to p1 for 1 frame
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.25, "frame_index": 106},
    ]
    # No single actor has >= 3 frames
    res = engine.evaluate_missed_shot("shot_switch", "miss", "team_b", 10.0, obs_switch)
    assert res is None or res.status != EventStatus.AUTO_CONFIRMED


def test_regression_dead_ball_and_cuts_break_chain():
    """Verify that camera cuts, replays, or dead-ball flags break the control chain."""
    engine = ReboundEngine()
    obs_cut = [
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.1, "frame_index": 100},
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.15, "frame_index": 102, "is_cut": True},
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.2, "frame_index": 104},
    ]
    res = engine.evaluate_missed_shot("shot_cut", "miss", "team_b", 10.0, obs_cut)
    assert res is None or res.status != EventStatus.AUTO_CONFIRMED


def test_regression_non_monotonic_breaks_chain():
    """Verify that duplicate or non-monotonic timestamps reset control chain."""
    engine = ReboundEngine()
    obs_dup = [
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.1, "frame_index": 100},
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.1, "frame_index": 100},  # duplicate
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.05, "frame_index": 98},  # non-monotonic
    ]
    res = engine.evaluate_missed_shot("shot_dup", "miss", "team_b", 10.0, obs_dup)
    assert res is None or res.status != EventStatus.AUTO_CONFIRMED


def test_regression_physical_miss_idempotency():
    """Verify that the same physical miss shot_id cannot produce two rebounds."""
    engine = ReboundEngine()
    obs = [
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.1, "frame_index": 100},
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.2, "frame_index": 103},
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.3, "frame_index": 106},
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.4, "frame_index": 109},
    ]
    reb1 = engine.evaluate_missed_shot("shot_single", "miss", "team_b", 10.0, obs)
    assert reb1 is not None

    # Second invocation with same shot_id must return None
    reb2 = engine.evaluate_missed_shot("shot_single", "miss", "team_b", 10.0, obs)
    assert reb2 is None
    assert len(engine.rebound_events) == 1


def test_regression_ledger_causal_parent_invalidation():
    """Verify ledger causal invariants: voiding parent shot cascades to child rebound."""
    ledger = EventLedger()
    engine = ReboundEngine()
    obs = [
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.1, "frame_index": 100},
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.2, "frame_index": 103},
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.3, "frame_index": 106},
        {"team_id": "team_a", "player_id": "p1", "source_time_s": 10.4, "frame_index": 109},
    ]
    reb = engine.evaluate_missed_shot("shot_parent_01", "miss", "team_b", 10.0, obs)
    assert reb is not None

    # Create parent shot record in ledger
    shot_record = LedgerEventRecord(
        event_id="shot_parent_01",
        event_type=EventType.SHOT,
        source_time_s=10.0,
        frame_index=95,
        team_id="team_b",
        player_id=None,
        point_value=None,
        subtype="field_goal",
        status=EventStatus.AUTO_CONFIRMED,
    )
    assert ledger.record_event(shot_record) is True

    reb_record = reb.to_ledger_record()
    assert ledger.record_event(reb_record) is True
    assert len(ledger.get_active_events()) == 2

    # Void parent shot -> rebound is cascaded
    voided = ledger.void_event("shot_parent_01", reason="shot_disallowed_on_review")
    assert "shot_parent_01" in voided
    assert reb.rebound_id in voided
    assert len(ledger.get_active_events()) == 0
