"""Unit and Regression tests for Task 10 / Sequence 01C: Assists Engine."""
from __future__ import annotations

import pytest

from basketball_scoreboard.assists import AssistEngine, AssistEngineConfig
from basketball_scoreboard.boxscore import BoxScoreEngine
from basketball_scoreboard.events import EventLedger, EventStatus, EventType, LedgerEventRecord
from basketball_scoreboard.identity import RosterConfig, RosterPlayer


@pytest.fixture
def mock_roster() -> RosterConfig:
    return RosterConfig(
        team_a_id="team_vie",
        team_b_id="team_tga",
        team_a_name="Việt Nam",
        team_b_name="Tonga",
        team_a_color_rgb=(200, 30, 30),
        team_b_color_rgb=(230, 230, 230),
        players=[
            RosterPlayer(team_id="team_vie", player_id="vie_07", jersey_number="7", name="Vie 7"),
            RosterPlayer(team_id="team_vie", player_id="vie_12", jersey_number="12", name="Vie 12"),
            RosterPlayer(team_id="team_tga", player_id="tga_03", jersey_number="3", name="Tga 3"),
            RosterPlayer(team_id="team_tga", player_id="tga_09", jersey_number="9", name="Tga 9"),
        ],
    )


def test_valid_direct_assist_creation():
    engine = AssistEngine()
    passes = [
        {
            "pass_id": "pass_01",
            "passer_player_id": "vie_12",
            "team_id": "team_vie",
            "receiver_player_id": "vie_07",
            "confirmed_at_s": 14.0,
            "confidence": 0.95,
        }
    ]
    ast = engine.evaluate_made_shot(
        shot_id="shot_001",
        shot_outcome="made",
        scorer_team_id="team_vie",
        scorer_player_id="vie_07",
        release_time_s=15.5,  # 1.5s after pass catch
        pass_events=passes,
    )
    assert ast is not None
    assert ast.passer_player_id == "vie_12"
    assert ast.scorer_player_id == "vie_07"
    assert ast.passer_team_id == "team_vie"
    assert ast.shot_id == "shot_001"
    assert ast.status == EventStatus.AUTO_CONFIRMED


def test_missed_shot_never_creates_assist():
    engine = AssistEngine()
    passes = [
        {
            "pass_id": "pass_02",
            "passer_player_id": "vie_12",
            "team_id": "team_vie",
            "receiver_player_id": "vie_07",
            "confirmed_at_s": 20.0,
        }
    ]
    ast = engine.evaluate_made_shot(
        shot_id="shot_missed",
        shot_outcome="miss",
        scorer_team_id="team_vie",
        scorer_player_id="vie_07",
        release_time_s=21.0,
        pass_events=passes,
    )
    assert ast is None


def test_self_pass_and_opponent_pass_rejected():
    engine = AssistEngine()

    # Self-pass (dribble / fumble recovery)
    self_passes = [
        {
            "pass_id": "pass_self",
            "passer_player_id": "vie_07",
            "team_id": "team_vie",
            "receiver_player_id": "vie_07",
            "confirmed_at_s": 25.0,
        }
    ]
    assert engine.evaluate_made_shot(
        shot_id="shot_002",
        shot_outcome="made",
        scorer_team_id="team_vie",
        scorer_player_id="vie_07",
        release_time_s=26.0,
        pass_events=self_passes,
    ) is None

    # Pass from opponent (steal and score)
    opp_passes = [
        {
            "pass_id": "pass_opp",
            "passer_player_id": "tga_03",
            "team_id": "team_tga",
            "receiver_player_id": "tga_09",
            "confirmed_at_s": 30.0,
        }
    ]
    assert engine.evaluate_made_shot(
        shot_id="shot_003",
        shot_outcome="made",
        scorer_team_id="team_vie",
        scorer_player_id="vie_07",
        release_time_s=31.0,
        pass_events=opp_passes,
    ) is None


def test_intervening_turnover_or_rebound_breaks_assist_chain():
    engine = AssistEngine()
    passes = [
        {
            "pass_id": "pass_03",
            "passer_player_id": "vie_12",
            "team_id": "team_vie",
            "receiver_player_id": "vie_07",
            "confirmed_at_s": 40.0,
        }
    ]
    intervening = [
        {"kind": "offensive_rebound", "source_time_s": 41.5}
    ]
    ast = engine.evaluate_made_shot(
        shot_id="shot_004",
        shot_outcome="made",
        scorer_team_id="team_vie",
        scorer_player_id="vie_07",
        release_time_s=42.0,
        pass_events=passes,
        intervening_events=intervening,
    )
    assert ast is None  # Chain broken by offensive rebound!


def test_assist_to_ledger_record():
    ledger = EventLedger()
    engine = AssistEngine()
    passes = [
        {
            "pass_id": "pass_04",
            "passer_player_id": "tga_09",
            "team_id": "team_tga",
            "receiver_player_id": "tga_03",
            "confirmed_at_s": 50.0,
            "confidence": 0.92,
        }
    ]
    ast = engine.evaluate_made_shot(
        shot_id="shot_005",
        shot_outcome="made",
        scorer_team_id="team_tga",
        scorer_player_id="tga_03",
        release_time_s=51.2,
        pass_events=passes,
    )
    assert ast is not None

    record = ast.to_ledger_record()
    assert ledger.record_event(record) is True
    active = ledger.get_active_events()
    assert len(active) == 1
    assert active[0].event_type == EventType.ASSIST
    assert active[0].player_id == "tga_09"
    assert active[0].parent_event_id == "shot_005"


# --- Regression Tests for 01C ---

def test_regression_assist_requires_identified_receiver():
    """Verify that a pass with unknown/missing receiver cannot confirm an assist."""
    engine = AssistEngine()
    passes = [
        {
            "pass_id": "p_no_rec",
            "passer_player_id": "vie_12",
            "team_id": "team_vie",
            "receiver_player_id": None,
            "confirmed_at_s": 9.0,
            "confidence": 0.90,
        }
    ]
    res = engine.evaluate_made_shot(
        "shot_no_rec", "made", "team_vie", "vie_07", 10.0, passes
    )
    assert res is None or res.status != EventStatus.AUTO_CONFIRMED


@pytest.mark.parametrize("status,conf", [("candidate", 0.95), ("auto_confirmed", 0.2), ("provisional", 0.85)])
def test_regression_assist_requires_confirmed_pass(status: str, conf: float):
    """Verify that unconfirmed or low-confidence passes cannot produce an assist."""
    engine = AssistEngine()
    passes = [
        {
            "pass_id": "p_unconfirmed",
            "passer_player_id": "vie_12",
            "team_id": "team_vie",
            "receiver_player_id": "vie_07",
            "confirmed_at_s": 9.0,
            "status": status,
            "confidence": conf,
        }
    ]
    res = engine.evaluate_made_shot(
        "shot_unconfirmed", "made", "team_vie", "vie_07", 10.0, passes
    )
    assert res is None or res.status != EventStatus.AUTO_CONFIRMED


@pytest.mark.parametrize("break_kind", ["deflection", "loose_ball", "camera_cut", "turnover", "possession_reset", "steal"])
def test_regression_assist_chain_breaks(break_kind: str):
    """Verify that all chain break event kinds invalidate the assist chain."""
    engine = AssistEngine()
    passes = [
        {
            "pass_id": "p_break",
            "passer_player_id": "vie_12",
            "team_id": "team_vie",
            "receiver_player_id": "vie_07",
            "confirmed_at_s": 9.0,
            "confidence": 0.95,
        }
    ]
    intervening = [{"kind": break_kind, "source_time_s": 9.5}]
    res = engine.evaluate_made_shot(
        "shot_break", "made", "team_vie", "vie_07", 10.0, passes, intervening_events=intervening
    )
    assert res is None or res.status != EventStatus.AUTO_CONFIRMED


def test_regression_assist_checks_post_catch_action():
    """Verify that excessive dribbles or independent drive moves reject assist credit."""
    engine = AssistEngine()
    # 12 dribbles + independent drive
    passes_iso = [
        {
            "pass_id": "p_iso",
            "passer_player_id": "vie_12",
            "team_id": "team_vie",
            "receiver_player_id": "vie_07",
            "confirmed_at_s": 9.0,
            "dribbles_after_catch": 12,
            "action_context": "independent_drive",
        }
    ]
    res_iso = engine.evaluate_made_shot(
        "shot_iso", "made", "team_vie", "vie_07", 10.0, passes_iso
    )
    assert res_iso is None or res_iso.status != EventStatus.AUTO_CONFIRMED

    # Direct catch and shoot (0 dribbles) -> confirms assist
    passes_direct = [
        {
            "pass_id": "p_direct",
            "passer_player_id": "vie_12",
            "team_id": "team_vie",
            "receiver_player_id": "vie_07",
            "confirmed_at_s": 9.0,
            "dribbles_after_catch": 0,
            "action_context": "catch_and_shoot",
            "confidence": 0.95,
        }
    ]
    res_direct = engine.evaluate_made_shot(
        "shot_direct", "made", "team_vie", "vie_07", 10.0, passes_direct
    )
    assert res_direct is not None
    assert res_direct.status == EventStatus.AUTO_CONFIRMED


def test_regression_assist_timeout():
    """Verify that passes preceding release by more than max_catch_to_release_s are excluded."""
    engine = AssistEngine(config=AssistEngineConfig(max_catch_to_release_s=3.0))
    passes = [
        {
            "pass_id": "p_old",
            "passer_player_id": "vie_12",
            "team_id": "team_vie",
            "receiver_player_id": "vie_07",
            "confirmed_at_s": 10.0,
            "confidence": 0.95,
        }
    ]
    # dt = 14.5 - 10.0 = 4.5s > 3.0s
    res = engine.evaluate_made_shot(
        "shot_late", "made", "team_vie", "vie_07", 14.5, passes
    )
    assert res is None


def test_regression_assist_single_shot_idempotency():
    """Verify that a single shot_id cannot receive two assist evaluations."""
    engine = AssistEngine()
    passes = [
        {
            "pass_id": "p_idem",
            "passer_player_id": "vie_12",
            "team_id": "team_vie",
            "receiver_player_id": "vie_07",
            "confirmed_at_s": 10.0,
            "confidence": 0.95,
        }
    ]
    a1 = engine.evaluate_made_shot("shot_idem", "made", "team_vie", "vie_07", 11.0, passes)
    assert a1 is not None

    # Second call returns None
    a2 = engine.evaluate_made_shot("shot_idem", "made", "team_vie", "vie_07", 11.0, passes)
    assert a2 is None
    assert len(engine.assist_events) == 1


def test_regression_assist_ledger_lifecycle(mock_roster: RosterConfig):
    """Test full assist lifecycle in ledger: ingestion -> boxscore -> revision -> void cascade -> reload."""
    ledger = EventLedger()
    engine = AssistEngine()
    box_engine = BoxScoreEngine(roster=mock_roster)

    # 1. Parent made shot
    shot = LedgerEventRecord(
        event_id="s_parent",
        event_type=EventType.SHOT,
        source_time_s=12.0,
        frame_index=360,
        team_id="team_vie",
        player_id="vie_07",
        point_value=2,
        status=EventStatus.AUTO_CONFIRMED,
    )
    assert ledger.record_event(shot) is True

    # 2. Child assist
    passes = [
        {
            "pass_id": "p_life",
            "passer_player_id": "vie_12",
            "team_id": "team_vie",
            "receiver_player_id": "vie_07",
            "confirmed_at_s": 10.5,
            "confidence": 0.95,
        }
    ]
    ast = engine.evaluate_made_shot("s_parent", "made", "team_vie", "vie_07", 12.0, passes)
    assert ast is not None
    assert ledger.record_event(ast.to_ledger_record()) is True

    # Box score verification: 2 points for vie_07, 1 assist for vie_12
    team_a_box, _ = box_engine.compile(ledger)
    assert team_a_box.total_score == 2
    assert team_a_box.assists == 1
    assert team_a_box.players["vie_12"].assists == 1

    # 3. Revise parent shot status to UNRESOLVED -> Assist becomes ineligible!
    ledger.revise_event("s_parent", new_status=EventStatus.UNRESOLVED)
    team_a_box2, _ = box_engine.compile(ledger)
    assert team_a_box2.assists == 0  # Ineligible assist must not count!

    # 4. Void parent shot -> Assist is cascaded to VOID
    voided = ledger.void_event("s_parent")
    assert "s_parent" in voided
    assert ast.assist_id in voided

    # 5. Checkpoint export and reload
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmpdir:
        ckpt_path = Path(tmpdir) / "checkpoint.json"
        ledger.save_checkpoint(ckpt_path)

        reloaded_ledger = EventLedger.load_checkpoint(ckpt_path)
        assert len(reloaded_ledger.get_active_events()) == 0
        all_events = reloaded_ledger.get_all_events()
        assert len(all_events) == 2
        for ev in all_events:
            assert ev.is_void is True
