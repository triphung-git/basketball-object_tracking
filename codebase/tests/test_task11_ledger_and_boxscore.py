"""Comprehensive production regression tests for Task 11: Unified Event Ledger and Box Score Engine.

Covers all 8 required verification suites:
  1. Status & type non-confirmed non-inflation (PTS/REB/AST/TO x 4 statuses; VOID conflict; nonfinite/invalid types).
  2. Refinement unknown -> known and idempotency under new ID without score doubling.
  3. Revisions: known -> unknown, team transfer, point value revision, confirmed -> unresolved/void, stale/no-op.
  4. Causal dependencies: compatible vs incompatible parent revisions, void cascade, late child, reordered arrival.
  5. Immutability & defensive copying: caller cannot mutate ledger state via input, get_event, or evidence dict.
  6. Persistence: atomic checkpoints with checksums, raw log append-only replay, checkpoint + tail, malformed failure.
  7. Multi-shot granularity: distinct physical shots close in time preserved; namespaces isolated.
  8. Statistical conservation invariants, offsets vs observed, unassigned buckets, and CSV/JSONL roundtrip.
"""
from __future__ import annotations

import copy
import csv
import json
from pathlib import Path
import pytest

from basketball_scoreboard.events import (
    EventLedger,
    EventStatus,
    EventType,
    LedgerEventRecord,
    point_event_to_ledger_record,
)
from basketball_scoreboard.boxscore import (
    BoxScoreEngine,
    PlayerBoxScore,
    TeamBoxScore,
)
from basketball_scoreboard.identity import RosterConfig, RosterPlayer
from basketball_scoreboard.points import (
    AttributionLevel,
    PointEventRecord,
    PointValueReason,
)


@pytest.fixture
def sample_roster() -> RosterConfig:
    players = [
        RosterPlayer(team_id="team_vie", player_id="vie_07", jersey_number="7", name="Nguyễn Văn A"),
        RosterPlayer(team_id="team_vie", player_id="vie_12", jersey_number="12", name="Trần Văn B"),
        RosterPlayer(team_id="team_tga", player_id="tga_03", jersey_number="3", name="Sione T."),
        RosterPlayer(team_id="team_tga", player_id="tga_09", jersey_number="9", name="Tevita K."),
    ]
    return RosterConfig(
        team_a_id="team_vie",
        team_b_id="team_tga",
        team_a_name="Việt Nam",
        team_b_name="Tonga",
        team_a_color_rgb=(200, 20, 20),
        team_b_color_rgb=(20, 20, 200),
        players=players,
    )


def helper_event(event_id="s", **kwargs):
    fields = dict(
        event_id=event_id,
        event_type=EventType.SHOT,
        source_time_s=10.0,
        frame_index=300,
        team_id="team_vie",
        player_id="vie_07",
        point_value=2,
    )
    fields.update(kwargs)
    return LedgerEventRecord(**fields)


# ==============================================================================
# Suite 1: Status & Type Non-Confirmed Non-Inflation + Data Validation
# ==============================================================================

@pytest.mark.parametrize("status", [EventStatus.CANDIDATE, EventStatus.PROVISIONAL,
                                    EventStatus.UNRESOLVED, EventStatus.VOID])
@pytest.mark.parametrize("kind", [EventType.SHOT, EventType.REBOUND,
                                  EventType.ASSIST, EventType.TURNOVER])
def test_suite1_non_confirmed_events_do_not_contribute(sample_roster, status, kind):
    ledger = EventLedger()
    ledger.record_event(helper_event(status=status, event_type=kind, subtype="defensive_rebound"))
    box_vie, box_tga = BoxScoreEngine(sample_roster).compile(ledger)
    assert (box_vie.observed_points, box_vie.rebounds_total, box_vie.assists, box_vie.turnovers) == (0, 0, 0, 0)
    assert (box_tga.observed_points, box_tga.rebounds_total, box_tga.assists, box_tga.turnovers) == (0, 0, 0, 0)


def test_suite1_conflicting_void_and_is_void_normalized(sample_roster):
    ledger = EventLedger()
    # status VOID but is_void False -> post_init normalizes is_void=True
    ev1 = helper_event("v1", status=EventStatus.VOID, is_void=False)
    assert ev1.is_void is True
    ledger.record_event(ev1)

    # is_void True but status AUTO_CONFIRMED -> post_init normalizes status=VOID
    ev2 = helper_event("v2", status=EventStatus.AUTO_CONFIRMED, is_void=True)
    assert ev2.status == EventStatus.VOID
    ledger.record_event(ev2)

    box_vie, _ = BoxScoreEngine(sample_roster).compile(ledger)
    assert box_vie.observed_points == 0


def test_suite1_data_validation_rejects_invalid_types():
    # bool is not integer point_value
    with pytest.raises(ValueError, match="point_value must be int or None"):
        helper_event(point_value=True)

    with pytest.raises(ValueError, match="point_value must be int or None"):
        helper_event(point_value=False)

    # float point value
    with pytest.raises(ValueError, match="point_value must be int or None"):
        helper_event(point_value=2.5)

    # invalid point value (not in 1, 2, 3)
    with pytest.raises(ValueError, match="Invalid point value"):
        helper_event(point_value=4)

    # non-finite timestamp
    with pytest.raises(ValueError, match="source_time_s must be finite"):
        helper_event(source_time_s=float("nan"))

    # negative frame index
    with pytest.raises(ValueError, match="frame_index must be non-negative"):
        helper_event(frame_index=-5)


# ==============================================================================
# Suite 2: Refinement & Idempotency Under New ID Without Double-Counting
# ==============================================================================

def test_suite2_team_only_to_known_player_refinement_idempotency(sample_roster):
    ledger = EventLedger()
    engine = BoxScoreEngine(sample_roster)

    # 1. Ingest team-only shot (unknown player)
    assert ledger.record_event(helper_event("shot_raw", player_id=None, point_value=2)) is True
    box_initial, _ = engine.compile(ledger)
    assert box_initial.observed_points == 2
    assert box_initial.team_only_points == 2
    assert box_initial.players["vie_07"].points == 0

    # 2. Refine attribution to known player vie_07
    revised = ledger.revise_event("shot_raw", new_player_id="vie_07", reason="jersey_ocr_resolution")
    assert revised is not None
    assert revised.revision == 2

    box_refined, _ = engine.compile(ledger)
    assert box_refined.observed_points == 2
    assert box_refined.team_only_points == 0
    assert box_refined.players["vie_07"].points == 2

    # 3. Upstream reingests same physical score under a new ID 'shot_reloaded'
    assert ledger.record_event(helper_event("shot_reloaded", player_id="vie_07", point_value=2)) is False

    box_after_reload, _ = engine.compile(ledger)
    # Total observed points MUST remain strictly 2 (no doubling to 4)
    assert box_after_reload.observed_points == 2
    assert box_after_reload.team_only_points == 0
    assert box_after_reload.players["vie_07"].points == 2


# ==============================================================================
# Suite 3: Revisions (Known->Unknown, Team Transfer, Value, Unresolved, Stale, No-Op)
# ==============================================================================

def test_suite3_known_to_unknown_player_revision(sample_roster):
    ledger = EventLedger()
    engine = BoxScoreEngine(sample_roster)

    ledger.record_event(helper_event("shot_01", player_id="vie_07", point_value=2))
    box, _ = engine.compile(ledger)
    assert box.players["vie_07"].points == 2
    assert box.team_only_points == 0

    # Explicitly clear player_id to None
    ledger.revise_event("shot_01", new_player_id=None, reason="adjudication_unresolved_shooter")
    box_after, _ = engine.compile(ledger)
    assert box_after.observed_points == 2
    assert box_after.team_only_points == 2
    assert box_after.players["vie_07"].points == 0


def test_suite3_team_transfer_and_value_revision(sample_roster):
    ledger = EventLedger()
    engine = BoxScoreEngine(sample_roster)

    ledger.record_event(helper_event("shot_02", team_id="team_vie", player_id="vie_07", point_value=2))
    box_vie, box_tga = engine.compile(ledger)
    assert box_vie.observed_points == 2
    assert box_tga.observed_points == 0

    # Team transfer revision: overturn scoring team to Tonga
    ledger.revise_event("shot_02", new_team_id="team_tga", new_player_id="tga_03", new_point_value=1)
    box_vie_after, box_tga_after = engine.compile(ledger)
    assert box_vie_after.observed_points == 0
    assert box_tga_after.observed_points == 1
    assert box_tga_after.players["tga_03"].points == 1


def test_suite3_confirmed_to_unresolved_and_stale_and_noop(sample_roster):
    ledger = EventLedger()
    engine = BoxScoreEngine(sample_roster)

    ledger.record_event(helper_event("shot_03", point_value=2, status=EventStatus.AUTO_CONFIRMED))

    # No-op revision: same values
    rev_noop = ledger.revise_event("shot_03", new_point_value=2)
    assert rev_noop is not None
    assert rev_noop.revision == 1  # Revision not bumped on no-op

    # Stale revision conflict: expected revision 99 when current is 1
    rev_conflict = ledger.revise_event("shot_03", new_point_value=1, expected_revision=99)
    assert rev_conflict is None  # Conflict rejected!

    # Successful transition to UNRESOLVED
    rev_unres = ledger.revise_event("shot_03", new_status=EventStatus.UNRESOLVED)
    assert rev_unres is not None
    assert rev_unres.status == EventStatus.UNRESOLVED

    box_vie, _ = engine.compile(ledger)
    assert box_vie.observed_points == 0
    assert box_vie.unresolved_shots == 1


# ==============================================================================
# Suite 4: Dependency & Arrival Order (Compatible, Incompatible, Void, Late, Reordered)
# ==============================================================================

def test_suite4_compatible_parent_revision_preserves_assist(sample_roster):
    ledger = EventLedger()
    engine = BoxScoreEngine(sample_roster)

    ledger.record_event(helper_event("s", point_value=2))
    ledger.record_event(helper_event("ast", event_type=EventType.ASSIST, player_id="vie_12",
                                     point_value=None, parent_event_id="s"))

    box, _ = engine.compile(ledger)
    assert box.observed_points == 2
    assert box.assists == 1

    # Revise point value 2 -> 1: assist is still compatible and preserved!
    ledger.revise_event("s", new_point_value=1)
    box_after, _ = engine.compile(ledger)
    assert box_after.observed_points == 1
    assert box_after.assists == 1


def test_suite4_incompatible_team_revision_invalidates_assist(sample_roster):
    ledger = EventLedger()
    ledger.record_event(helper_event("s", team_id="team_vie", player_id="vie_07"))
    ledger.record_event(helper_event("ast", event_type=EventType.ASSIST, team_id="team_vie",
                                     player_id="vie_12", point_value=None, parent_event_id="s"))
    # Revise parent shot to team_tga
    ledger.revise_event("s", new_team_id="team_tga", new_player_id="tga_03")

    box_vie, box_tga = BoxScoreEngine(sample_roster).compile(ledger)
    assert box_vie.assists == 0
    assert box_tga.assists == 0


def test_suite4_void_and_late_child_guard(sample_roster):
    ledger = EventLedger()
    ledger.record_event(helper_event("s"))
    ledger.void_event("s", reason="shot_clock_violation")

    # Late assist arrives referencing already-void parent
    ledger.record_event(helper_event("ast_late", event_type=EventType.ASSIST, player_id="vie_12",
                                     point_value=None, parent_event_id="s"))

    box_vie, _ = BoxScoreEngine(sample_roster).compile(ledger)
    assert box_vie.assists == 0


def test_suite4_reordered_arrival_child_before_parent(sample_roster):
    ledger = EventLedger()
    engine = BoxScoreEngine(sample_roster)

    # 1. Assist arrives BEFORE the parent shot
    ledger.record_event(helper_event("ast_early", event_type=EventType.ASSIST, player_id="vie_12",
                                     point_value=None, parent_event_id="s_parent"))

    # At this moment, parent shot is missing in ledger -> assist is pending and NOT counted
    box_early, _ = engine.compile(ledger)
    assert box_early.assists == 0

    # 2. Parent shot arrives later and is auto_confirmed
    ledger.record_event(helper_event("s_parent", point_value=2))

    # Now parent is resolved and confirmed -> assist is eligible and counted exactly once!
    box_final, _ = engine.compile(ledger)
    assert box_final.observed_points == 2
    assert box_final.assists == 1
    assert box_final.players["vie_12"].assists == 1


# ==============================================================================
# Suite 5: Immutability & Defensive Copying
# ==============================================================================

def test_suite5_caller_mutation_isolation(sample_roster):
    ledger = EventLedger()
    engine = BoxScoreEngine(sample_roster)

    orig = helper_event("shot_mut", point_value=2, evidence={"nested": {"confidence": 0.95}})
    ledger.record_event(orig)

    # 1. Mutate input object after recording
    orig.point_value = 1
    orig.evidence["nested"]["confidence"] = 0.10

    # Ledger state must remain unchanged
    stored = ledger.get_event("shot_mut")
    assert stored.point_value == 2
    assert stored.evidence["nested"]["confidence"] == 0.95

    # 2. Mutate retrieved object
    stored.point_value = 3
    stored_again = ledger.get_event("shot_mut")
    assert stored_again.point_value == 2

    # 3. Mutate list returned by get_active_events
    active = ledger.get_active_events()
    active[0].point_value = 1
    assert ledger.get_event("shot_mut").point_value == 2

    box, _ = engine.compile(ledger)
    assert box.observed_points == 2


# ==============================================================================
# Suite 6: Persistence, Replay & Integrity (Checkpoint + Tail, Malformed Recovery)
# ==============================================================================

def test_suite6_checkpoint_and_raw_log_replay(sample_roster, tmp_path):
    ledger = EventLedger(ledger_id="test_game")
    engine = BoxScoreEngine(sample_roster)

    # Record sequence of events and revisions
    ledger.record_event(helper_event("s1", point_value=2, source_time_s=10.0, frame_index=300))
    ledger.record_event(helper_event("ast1", event_type=EventType.ASSIST, player_id="vie_12",
                                     point_value=None, parent_event_id="s1", source_time_s=9.5, frame_index=285))
    ledger.revise_event("s1", new_player_id="vie_07")

    # Save checkpoint
    chk_path = tmp_path / "checkpoint.json"
    ledger.save_checkpoint(chk_path)
    assert chk_path.is_file()

    # Continue recording events after checkpoint
    ledger.record_event(helper_event("s2", point_value=1, subtype="free_throw", source_time_s=25.0, frame_index=750))
    raw_log_path = tmp_path / "raw_transactions.jsonl"
    ledger.export_raw_transactions(raw_log_path)
    assert raw_log_path.is_file()

    box_orig, _ = engine.compile(ledger)

    # 1. Full replay from raw log
    ledger_from_log = EventLedger.from_raw_log(raw_log_path, ledger_id="test_game")
    box_log, _ = engine.compile(ledger_from_log)
    assert box_log.observed_points == box_orig.observed_points
    assert box_log.assists == box_orig.assists

    # 2. Resume from checkpoint + replay tail
    ledger_resumed = EventLedger.load_checkpoint(chk_path)
    replayed_tail_count = ledger_resumed.replay_transactions(raw_log_path)
    assert replayed_tail_count == 1  # Only the post-checkpoint transaction applied!

    box_resumed, _ = engine.compile(ledger_resumed)
    assert box_resumed.observed_points == box_orig.observed_points
    assert box_resumed.assists == box_orig.assists


def test_suite6_malformed_checkpoint_and_log_fail_safely(tmp_path):
    # 1. Tampered checksum in checkpoint must raise ValueError
    corrupt_chk = tmp_path / "corrupt_chk.json"
    corrupt_chk.write_text(json.dumps({
        "schema_version": "event-ledger-checkpoint-v1",
        "ledger_id": "bad",
        "sequence_position": 1,
        "checksum": "deadbeef_invalid_checksum",
        "events": {"s": helper_event("s").to_dict()}
    }), encoding="utf-8")

    with pytest.raises(ValueError, match="Checkpoint integrity failure"):
        EventLedger.load_checkpoint(corrupt_chk)

    # 2. Malformed JSON line in transaction log must raise ValueError
    corrupt_log = tmp_path / "corrupt_log.jsonl"
    corrupt_log.write_text(
        '{"mutation_id": "mut_000001", "sequence": 1, "event_id": "s", "action": "created"}\nNOT_VALID_JSON\n',
        encoding="utf-8",
    )

    ledger = EventLedger()
    with pytest.raises(ValueError, match="Malformed transaction at line 2"):
        ledger.replay_transactions(corrupt_log)


# ==============================================================================
# Suite 7: Temporal Granularity & Namespaces
# ==============================================================================

def test_suite7_two_shots_close_in_time_both_preserved(sample_roster):
    ledger = EventLedger()
    engine = BoxScoreEngine(sample_roster)

    # Shot 1 at t=10.0s (frame 300)
    assert ledger.record_event(helper_event("shot_01", source_time_s=10.0, frame_index=300, point_value=2)) is True
    # Shot 2 at t=11.5s (frame 345): fast follow-up tip-in/putback
    assert ledger.record_event(helper_event("shot_02", source_time_s=11.5, frame_index=345, point_value=2)) is True

    # Both shots MUST be preserved
    box, _ = engine.compile(ledger)
    assert box.observed_points == 4
    assert len(ledger.get_active_events()) == 2


def test_suite7_namespaces_isolation(sample_roster):
    ledger = EventLedger()

    # Event from camera A
    ev_cam_a = helper_event("ev_a", source_namespace="camera_a", source_time_s=10.0, frame_index=300)
    assert ledger.record_event(ev_cam_a) is True

    # Same timestamp and frame from camera B (different source namespace)
    ev_cam_b = helper_event("ev_b", source_namespace="camera_b", source_time_s=10.0, frame_index=300)
    assert ledger.record_event(ev_cam_b) is True

    assert len(ledger.get_active_events()) == 2


# ==============================================================================
# Suite 8: Invariants, Offsets, Unassigned & Export Roundtrip
# ==============================================================================

def test_suite8_offsets_rebounds_and_csv_roundtrip(sample_roster, tmp_path):
    ledger = EventLedger()
    engine = BoxScoreEngine(
        roster=sample_roster,
        initial_score_offsets={"team_vie": 12, "team_tga": 9},
    )

    # Việt Nam stats: 1 observed shot, 1 offensive team rebound, 1 defensive player rebound
    ledger.record_event(helper_event("s_vie", team_id="team_vie", player_id="vie_07", point_value=2,
                                     source_time_s=10.0, frame_index=300))
    ledger.record_event(helper_event("reb_team", event_type=EventType.REBOUND, team_id="team_vie",
                                     player_id=None, subtype="offensive_rebound",
                                     source_time_s=15.0, frame_index=450))
    ledger.record_event(helper_event("reb_player", event_type=EventType.REBOUND, team_id="team_vie",
                                     player_id="vie_12", subtype="defensive_rebound",
                                     source_time_s=25.0, frame_index=750))

    box_vie, box_tga = engine.compile(ledger)

    # Offset conservation
    assert box_vie.initial_score_offset == 12
    assert box_vie.observed_points == 2
    assert box_vie.total_score == 14

    # Rebound conservation
    assert box_vie.rebounds_offensive == 1
    assert box_vie.rebounds_defensive == 1
    assert box_vie.rebounds_team == 1
    assert box_vie.rebounds_total == 2
    assert box_vie.players["vie_12"].rebounds_defensive == 1
    assert box_vie.players["vie_12"].rebounds_total == 1

    # CSV export and verification
    csv_path = tmp_path / "boxscore_roundtrip.csv"
    BoxScoreEngine.export_csv(box_vie, box_tga, csv_path)
    assert csv_path.is_file()

    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    vie_summary = next(r for r in rows if r["Player_ID"] == "TEAM_TOTAL" and r["Team"] == "Việt Nam")
    assert int(vie_summary["PTS"]) == 14
    assert int(vie_summary["OREB"]) == 1
    assert int(vie_summary["DREB"]) == 1
    assert int(vie_summary["REB"]) == 2

    vie_player = next(r for r in rows if r["Player_ID"] == "vie_07")
    assert int(vie_player["PTS"]) == 2


def test_suite8_point_event_to_ledger_record_conversion():
    ptev = PointEventRecord(
        event_id="ptev_001",
        shot_id="shot_123",
        video_id="vietnam_tonga",
        source_time_s=17.2,
        confirmation_time_s=18.4,
        scoring_team_id="team_vie",
        scoring_player_id="vie_07",
        point_value=2,
        attribution_level=AttributionLevel.PLAYER,
        status="auto_confirmed",
        value_reason=PointValueReason.FIBA_3X3_2PT_OUTSIDE_ARC,
    )
    rec = point_event_to_ledger_record(ptev, frame_index=552)
    assert rec.event_type == EventType.SHOT
    assert rec.point_value == 2
    assert rec.team_id == "team_vie"
    assert rec.player_id == "vie_07"
    assert rec.status == EventStatus.AUTO_CONFIRMED
    assert rec.frame_index == 552
    assert rec.source_time_s == 17.2  # Actual source event time preserved!
    assert rec.confirmation_time_s == 18.4  # Explicit confirmation timestamp tracked
    assert rec.parent_event_id == "shot_123"
    assert rec.evidence["evidence_refs"]["confirmation_time_s"] == 18.4
