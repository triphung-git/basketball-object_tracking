"""Comprehensive integration and unit test suite for Task D05: REB/AST Orchestration, Action Rules & Lifecycle."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from basketball_scoreboard.events import EventLedger, EventStatus, EventType, LedgerEventRecord
from basketball_scoreboard.identity import RosterConfig, RosterPlayer
from basketball_scoreboard.rebounds import (
    ReboundEngine,
    ReboundEngineConfig,
    ReboundType,
    ReboundCandidate,
)
from basketball_scoreboard.assists import (
    AssistEngine,
    AssistEngineConfig,
    AssistCandidate,
)
from basketball_scoreboard.boxscore import (
    BoxScoreEngine,
    TeamBoxScore,
    PlayerBoxScore,
)
from basketball_scoreboard.continuous_orchestration import run_continuous_orchestration


@pytest.fixture
def test_roster() -> RosterConfig:
    return RosterConfig(
        team_a_id="VIE",
        team_a_name="Vietnam",
        team_a_color_rgb=[220, 20, 20],
        team_b_id="TGA",
        team_b_name="Tonga",
        team_b_color_rgb=[20, 20, 220],
        players=[
            RosterPlayer(player_id="vie_09", jersey_number=9, team_id="VIE", name="Player 9"),
            RosterPlayer(player_id="vie_18", jersey_number=18, team_id="VIE", name="Player 18"),
            RosterPlayer(player_id="tga_04", jersey_number=4, team_id="TGA", name="Tonga 4"),
            RosterPlayer(player_id="tga_07", jersey_number=7, team_id="TGA", name="Tonga 7"),
        ],
    )


def test_rebound_offensive_and_defensive_classification():
    """Verify rebound classification into offensive (same team) vs defensive (opposing team)."""
    engine = ReboundEngine(ReboundEngineConfig(min_control_frames=3, min_control_duration_s=0.15))

    # 1. Defensive Rebound (shooter = VIE, recovery = TGA)
    controls_def = [
        {"source_time_s": 10.20, "frame_index": 306, "team_id": "TGA", "player_id": "tga_04", "track_id": "trk_4", "sample_type": "observed", "confidence": 0.85},
        {"source_time_s": 10.25, "frame_index": 307, "team_id": "TGA", "player_id": "tga_04", "track_id": "trk_4", "sample_type": "observed", "confidence": 0.85},
        {"source_time_s": 10.36, "frame_index": 308, "team_id": "TGA", "player_id": "tga_04", "track_id": "trk_4", "sample_type": "observed", "confidence": 0.85},
    ]
    reb_def = engine.evaluate_missed_shot(
        shot_id="shot_001",
        shot_outcome="rim_bounce",
        shooting_team_id="VIE",
        miss_time_s=10.10,
        control_observations=controls_def,
    )
    assert reb_def is not None
    assert reb_def.rebound_type == ReboundType.DEFENSIVE
    assert reb_def.team_id == "TGA"
    assert reb_def.player_id == "tga_04"
    assert reb_def.status == EventStatus.AUTO_CONFIRMED
    assert reb_def.shot_id == "shot_001"

    # Ledger record validation
    ledger_rec = reb_def.to_ledger_record()
    assert ledger_rec.parent_event_id == "shot_001"
    assert ledger_rec.event_type == EventType.REBOUND
    assert ledger_rec.subtype == "defensive_rebound"

    # 2. Offensive Rebound (shooter = VIE, recovery = VIE)
    engine_off = ReboundEngine(ReboundEngineConfig(min_control_frames=3, min_control_duration_s=0.15))
    controls_off = [
        {"source_time_s": 20.20, "frame_index": 606, "team_id": "VIE", "player_id": "vie_18", "track_id": "trk_18", "sample_type": "observed", "confidence": 0.90},
        {"source_time_s": 20.25, "frame_index": 607, "team_id": "VIE", "player_id": "vie_18", "track_id": "trk_18", "sample_type": "observed", "confidence": 0.90},
        {"source_time_s": 20.36, "frame_index": 608, "team_id": "VIE", "player_id": "vie_18", "track_id": "trk_18", "sample_type": "observed", "confidence": 0.90},
    ]
    reb_off = engine_off.evaluate_missed_shot(
        shot_id="shot_002",
        shot_outcome="miss",
        shooting_team_id="VIE",
        miss_time_s=20.10,
        control_observations=controls_off,
    )
    assert reb_off is not None
    assert reb_off.rebound_type == ReboundType.OFFENSIVE
    assert reb_off.team_id == "VIE"
    assert reb_off.player_id == "vie_18"
    assert reb_off.status == EventStatus.AUTO_CONFIRMED


def test_rebound_rejection_guards():
    """Verify guards: made baskets, actor switches, cuts, gaps, and predicted samples rejected."""
    engine = ReboundEngine(ReboundEngineConfig(min_control_frames=3, min_control_duration_s=0.15, max_control_gap_s=0.25))

    # Guard 1: Made basket strictly returns None
    assert engine.evaluate_missed_shot(
        shot_id="shot_made",
        shot_outcome="made",
        shooting_team_id="VIE",
        miss_time_s=5.0,
        control_observations=[{"source_time_s": 5.1, "sample_type": "observed", "confidence": 0.9}],
    ) is None

    # Guard 2: Predicted-only samples rejected
    controls_pred = [
        {"source_time_s": 10.20, "team_id": "TGA", "player_id": "tga_04", "track_id": "trk_4", "sample_type": "predicted", "confidence": 0.85},
        {"source_time_s": 10.25, "team_id": "TGA", "player_id": "tga_04", "track_id": "trk_4", "sample_type": "predicted", "confidence": 0.85},
        {"source_time_s": 10.36, "team_id": "TGA", "player_id": "tga_04", "track_id": "trk_4", "sample_type": "predicted", "confidence": 0.85},
    ]
    assert engine.evaluate_missed_shot(
        shot_id="shot_pred",
        shot_outcome="miss",
        shooting_team_id="VIE",
        miss_time_s=10.0,
        control_observations=controls_pred,
    ) is None

    # Guard 3: Camera cut breaks recovery chain
    controls_cut = [
        {"source_time_s": 10.20, "team_id": "TGA", "player_id": "tga_04", "track_id": "trk_4", "sample_type": "observed", "confidence": 0.85},
        {"source_time_s": 10.25, "team_id": "TGA", "player_id": "tga_04", "track_id": "trk_4", "sample_type": "observed", "confidence": 0.85, "is_cut": True},
        {"source_time_s": 10.36, "team_id": "TGA", "player_id": "tga_04", "track_id": "trk_4", "sample_type": "observed", "confidence": 0.85},
    ]
    assert engine.evaluate_missed_shot(
        shot_id="shot_cut",
        shot_outcome="miss",
        shooting_team_id="VIE",
        miss_time_s=10.0,
        control_observations=controls_cut,
    ) is None

    # Guard 4: Excessive gap between consecutive controls breaks chain (> 0.25s)
    controls_gap = [
        {"source_time_s": 10.20, "team_id": "TGA", "player_id": "tga_04", "track_id": "trk_4", "sample_type": "observed", "confidence": 0.85},
        {"source_time_s": 10.25, "team_id": "TGA", "player_id": "tga_04", "track_id": "trk_4", "sample_type": "observed", "confidence": 0.85},
        {"source_time_s": 10.55, "team_id": "TGA", "player_id": "tga_04", "track_id": "trk_4", "sample_type": "observed", "confidence": 0.85},  # 0.30s gap
    ]
    assert engine.evaluate_missed_shot(
        shot_id="shot_gap",
        shot_outcome="miss",
        shooting_team_id="VIE",
        miss_time_s=10.0,
        control_observations=controls_gap,
    ) is None


def test_assist_lifecycle_and_validation():
    """Verify direct assist adjudication: valid pass, same team, receiver is scorer, and chain breaks."""
    engine = AssistEngine(AssistEngineConfig(max_catch_to_release_s=4.0, allow_dribbles=2))

    # 1. Valid Direct Assist
    valid_passes = [
        {
            "pass_id": "pass_01",
            "passer_player_id": "vie_09",
            "team_id": "VIE",
            "receiver_player_id": "vie_18",
            "confirmed_at_s": 12.0,
            "status": "auto_confirmed",
            "confidence": 0.92,
            "dribbles_after_catch": 1,
            "frame_index": 360,
        }
    ]
    ast = engine.evaluate_made_shot(
        shot_id="shot_made_01",
        shot_outcome="made",
        scorer_team_id="VIE",
        scorer_player_id="vie_18",
        release_time_s=13.5,  # dt = 1.5s <= 4.0s
        pass_events=valid_passes,
    )
    assert ast is not None
    assert ast.passer_player_id == "vie_09"
    assert ast.scorer_player_id == "vie_18"
    assert ast.passer_team_id == "VIE"
    assert ast.status == EventStatus.AUTO_CONFIRMED
    assert ast.shot_id == "shot_made_01"

    rec = ast.to_ledger_record()
    assert rec.parent_event_id == "shot_made_01"
    assert rec.event_type == EventType.ASSIST
    assert rec.player_id == "vie_09"

    # 2. Self-pass rejected
    engine_self = AssistEngine()
    self_passes = [{
        "pass_id": "pass_self",
        "passer_player_id": "vie_18",
        "team_id": "VIE",
        "receiver_player_id": "vie_18",
        "confirmed_at_s": 12.0,
        "status": "auto_confirmed",
        "confidence": 0.95,
    }]
    assert engine_self.evaluate_made_shot(
        shot_id="shot_self",
        shot_outcome="made",
        scorer_team_id="VIE",
        scorer_player_id="vie_18",
        release_time_s=13.0,
        pass_events=self_passes,
    ) is None

    # 3. Intervening turnover breaks chain
    engine_to = AssistEngine()
    intervening = [{"source_time_s": 12.5, "kind": "turnover"}]
    assert engine_to.evaluate_made_shot(
        shot_id="shot_broken",
        shot_outcome="made",
        scorer_team_id="VIE",
        scorer_player_id="vie_18",
        release_time_s=13.5,
        pass_events=valid_passes,
        intervening_events=intervening,
    ) is None

    # 4. Timeout exceeded (> 4.0s)
    engine_timeout = AssistEngine()
    assert engine_timeout.evaluate_made_shot(
        shot_id="shot_late",
        shot_outcome="made",
        scorer_team_id="VIE",
        scorer_player_id="vie_18",
        release_time_s=16.5,  # dt = 4.5s > 4.0s
        pass_events=valid_passes,
    ) is None


def test_boxscore_conservation_and_invariants(test_roster: RosterConfig):
    """Verify that ledger events compile to boxscore satisfying all conservation invariants."""
    ledger = EventLedger()
    box_engine = BoxScoreEngine(roster=test_roster, initial_score_offsets={"VIE": 5, "TGA": 3})

    # Record Shot 1: VIE player 18 makes 2PT shot assisted by VIE player 9
    shot1 = LedgerEventRecord(
        event_id="shot_001",
        event_type=EventType.SHOT,
        source_time_s=10.0,
        frame_index=300,
        team_id="VIE",
        player_id="vie_18",
        point_value=2,
        subtype="2pt_outside_arc",
        status=EventStatus.AUTO_CONFIRMED,
    )
    ast1 = LedgerEventRecord(
        event_id="ast_shot_001_vie_09",
        event_type=EventType.ASSIST,
        source_time_s=9.0,
        frame_index=270,
        team_id="VIE",
        player_id="vie_09",
        subtype="direct_assist",
        status=EventStatus.AUTO_CONFIRMED,
        parent_event_id="shot_001",
    )
    # Record Shot 2: TGA player 4 misses shot, VIE player 9 recovers defensive rebound
    shot2 = LedgerEventRecord(
        event_id="shot_002",
        event_type=EventType.SHOT,
        source_time_s=20.0,
        frame_index=600,
        team_id="TGA",
        player_id="tga_04",
        point_value=None,
        subtype="miss",
        status=EventStatus.AUTO_CONFIRMED,
    )
    reb2 = LedgerEventRecord(
        event_id="reb_shot_002_02020",
        event_type=EventType.REBOUND,
        source_time_s=20.5,
        frame_index=615,
        team_id="VIE",
        player_id="vie_09",
        subtype="defensive_rebound",
        status=EventStatus.AUTO_CONFIRMED,
        parent_event_id="shot_002",
    )
    # Record Shot 3: VIE team-only 1PT made basket (unassigned player)
    shot3 = LedgerEventRecord(
        event_id="shot_003",
        event_type=EventType.SHOT,
        source_time_s=30.0,
        frame_index=900,
        team_id="VIE",
        player_id=None,
        point_value=1,
        subtype="1pt_inside_arc",
        status=EventStatus.AUTO_CONFIRMED,
    )

    ledger.record_event(shot1)
    ledger.record_event(ast1)
    ledger.record_event(shot2)
    ledger.record_event(reb2)
    ledger.record_event(shot3)

    box_a, box_b = box_engine.compile(ledger)

    # 1. Total score conservation: total_score == offset + observed_points
    assert box_a.total_score == 5 + 3  # offset 5 + (2 + 1) = 8
    assert box_a.observed_points == 3
    assert box_b.total_score == 3 + 0  # offset 3 + 0 = 3

    # 2. Player vs Team points: sum(player.points) + team_only == observed_points
    p_pts_a = sum(p.points for p in box_a.players.values())
    assert p_pts_a + box_a.team_only_points == box_a.observed_points
    assert box_a.players["vie_18"].points == 2
    assert box_a.players["vie_18"].fg_made_2pt == 1
    assert box_a.team_only_points == 1

    # 3. Assists conservation: sum(player.assists) + team_only == assists_total
    p_ast_a = sum(p.assists for p in box_a.players.values())
    assert p_ast_a + box_a.assists_team_only == box_a.assists
    assert box_a.players["vie_09"].assists == 1
    assert box_a.assists == 1
    assert box_a.assists <= (box_a.players["vie_18"].fg_made_2pt + box_a.players["vie_18"].fg_made_1pt + 1)

    # 4. Rebounds conservation: offensive + defensive + unclassified == rebounds_total
    assert box_a.rebounds_total == box_a.rebounds_defensive + box_a.rebounds_offensive + box_a.rebounds_unclassified
    assert box_a.rebounds_defensive == 1
    assert box_a.players["vie_09"].rebounds_defensive == 1
    assert box_a.players["vie_09"].rebounds_total == 1
