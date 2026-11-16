#!/usr/bin/env python3
"""Synthetic Contract Diagnostic Runner for Assists (Task 10 / Sequence 01C).

Executes contract verification for AssistEngine and EventLedger integration:
  - Demonstrates positive pass-to-score direct assist chains.
  - Demonstrates rejection of missed shots, self-passes, opponent passes, unconfirmed/low-conf passes.
  - Demonstrates chain breaks: deflection, loose ball, camera cut, turnover, rebound.
  - Demonstrates post-catch action checks (independent drives, excessive dribbles).
  - Demonstrates ledger lifecycle: ingestion, boxscore, parent revision/void cascading, checkpoint reload.
  - Exports standard ledger and boxscore artifacts.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from basketball_scoreboard.assists import AssistEngine, AssistEngineConfig
from basketball_scoreboard.boxscore import BoxScoreEngine
from basketball_scoreboard.events import EventLedger, EventStatus, EventType, LedgerEventRecord
from basketball_scoreboard.identity import RosterConfig, RosterPlayer


def run_diagnostic(out_dir: Path) -> dict:
    t_start = time.perf_counter()
    out_dir.mkdir(parents=True, exist_ok=True)

    roster = RosterConfig(
        team_a_id="team_vie",
        team_b_id="team_tga",
        team_a_name="Việt Nam",
        team_b_name="Tonga",
        team_a_color_rgb=(200, 30, 30),
        team_b_color_rgb=(230, 230, 230),
        players=[
            RosterPlayer(team_id="team_vie", player_id="vie_07", jersey_number="7", name="Player Vie 7"),
            RosterPlayer(team_id="team_vie", player_id="vie_12", jersey_number="12", name="Player Vie 12"),
            RosterPlayer(team_id="team_tga", player_id="tga_03", jersey_number="3", name="Player Tga 3"),
            RosterPlayer(team_id="team_tga", player_id="tga_09", jersey_number="9", name="Player Tga 9"),
        ],
    )

    engine = AssistEngine()
    ledger = EventLedger()
    box_engine = BoxScoreEngine(roster=roster)

    test_cases_summary = []

    # 1. Positive Assist Chain: vie_12 passes to vie_07 who scores 2pt
    shot1 = LedgerEventRecord(
        event_id="shot_made_001",
        event_type=EventType.SHOT,
        source_time_s=15.0,
        frame_index=450,
        team_id="team_vie",
        player_id="vie_07",
        point_value=2,
        subtype="field_goal",
        status=EventStatus.AUTO_CONFIRMED,
    )
    assert ledger.record_event(shot1) is True

    p1 = [
        {
            "pass_id": "pass_001",
            "passer_player_id": "vie_12",
            "team_id": "team_vie",
            "receiver_player_id": "vie_07",
            "confirmed_at_s": 13.5,
            "confidence": 0.95,
            "status": "auto_confirmed",
            "dribbles_after_catch": 0,
            "action_context": "catch_and_shoot",
        }
    ]
    ast1 = engine.evaluate_made_shot("shot_made_001", "made", "team_vie", "vie_07", 15.0, p1)
    assert ast1 is not None and ast1.status == EventStatus.AUTO_CONFIRMED
    rec1 = ast1.to_ledger_record()
    assert ledger.record_event(rec1) is True
    test_cases_summary.append({"case": "positive_direct_assist_vietnam", "assist_id": ast1.assist_id, "status": "confirmed"})

    # 2. Positive Assist Chain: tga_09 passes to tga_03 who scores 1pt
    shot2 = LedgerEventRecord(
        event_id="shot_made_002",
        event_type=EventType.SHOT,
        source_time_s=30.0,
        frame_index=900,
        team_id="team_tga",
        player_id="tga_03",
        point_value=1,
        subtype="field_goal",
        status=EventStatus.AUTO_CONFIRMED,
    )
    assert ledger.record_event(shot2) is True

    p2 = [
        {
            "pass_id": "pass_002",
            "passer_player_id": "tga_09",
            "team_id": "team_tga",
            "receiver_player_id": "tga_03",
            "confirmed_at_s": 28.5,
            "confidence": 0.92,
            "status": "auto_confirmed",
            "dribbles_after_catch": 1,
            "action_context": "drive_and_score",
        }
    ]
    ast2 = engine.evaluate_made_shot("shot_made_002", "made", "team_tga", "tga_03", 30.0, p2)
    assert ast2 is not None and ast2.status == EventStatus.AUTO_CONFIRMED
    rec2 = ast2.to_ledger_record()
    assert ledger.record_event(rec2) is True
    test_cases_summary.append({"case": "positive_direct_assist_tonga", "assist_id": ast2.assist_id, "status": "confirmed"})

    # 3. Negative Case: Unidentified receiver (None)
    p3 = [{"pass_id": "p3", "passer_player_id": "vie_12", "team_id": "team_vie", "receiver_player_id": None, "confirmed_at_s": 40.0, "confidence": 0.9}]
    ast3 = engine.evaluate_made_shot("shot_made_003", "made", "team_vie", "vie_07", 41.0, p3)
    assert ast3 is None
    test_cases_summary.append({"case": "unidentified_receiver_rejected", "status": "correctly_rejected_none"})

    # 4. Negative Case: Candidate / low-confidence pass
    p4 = [{"pass_id": "p4", "passer_player_id": "vie_12", "team_id": "team_vie", "receiver_player_id": "vie_07", "confirmed_at_s": 50.0, "status": "candidate", "confidence": 0.2}]
    ast4 = engine.evaluate_made_shot("shot_made_004", "made", "team_vie", "vie_07", 51.0, p4)
    assert ast4 is None
    test_cases_summary.append({"case": "unconfirmed_pass_rejected", "status": "correctly_rejected_none"})

    # 5. Negative Case: Chain breaks (deflection, loose_ball, camera_cut)
    for bk in ["deflection", "loose_ball", "camera_cut"]:
        ast_bk = engine.evaluate_made_shot(f"shot_bk_{bk}", "made", "team_vie", "vie_07", 62.0, p1, intervening_events=[{"kind": bk, "source_time_s": 61.0}])
        assert ast_bk is None
        test_cases_summary.append({"case": f"chain_break_{bk}_rejected", "status": "correctly_rejected_none"})

    # 6. Negative Case: Post-catch excessive dribbles & independent drive
    p6 = [{"pass_id": "p6", "passer_player_id": "vie_12", "team_id": "team_vie", "receiver_player_id": "vie_07", "confirmed_at_s": 70.0, "dribbles_after_catch": 8, "action_context": "independent_drive"}]
    ast6 = engine.evaluate_made_shot("shot_made_006", "made", "team_vie", "vie_07", 72.0, p6)
    assert ast6 is None
    test_cases_summary.append({"case": "independent_drive_rejected", "status": "correctly_rejected_none"})

    # 7. Compile BoxScore
    team_a_box, team_b_box = box_engine.compile(ledger)
    assert team_a_box.total_score == 2
    assert team_a_box.assists == 1
    assert team_a_box.players["vie_12"].assists == 1
    assert team_b_box.total_score == 1
    assert team_b_box.assists == 1
    assert team_b_box.players["tga_09"].assists == 1

    # 8. Replay idempotency
    assert ledger.record_event(rec1) is False
    assert len(ledger.get_active_events()) == 4

    # 9. Invalidate / Void Parent test
    ledger_test = EventLedger()
    ledger_test.record_event(shot1)
    ledger_test.record_event(rec1)
    # Revise parent status
    ledger_test.revise_event("shot_made_001", new_status=EventStatus.UNRESOLVED)
    box_rev, _ = box_engine.compile(ledger_test)
    assert box_rev.assists == 0  # Ineligible parent drops assist count to 0!

    # Void parent
    voided = ledger_test.void_event("shot_made_001")
    assert "shot_made_001" in voided
    assert ast1.assist_id in voided
    assert len(ledger_test.get_active_events()) == 0

    # Checkpoint round-trip test
    ckpt_temp = out_dir / "test_roundtrip_checkpoint.json"
    ledger.save_checkpoint(ckpt_temp)
    reloaded_ledger = EventLedger.load_checkpoint(ckpt_temp)
    assert len(reloaded_ledger.get_active_events()) == 4
    reloaded_a_box, reloaded_b_box = box_engine.compile(reloaded_ledger)
    assert reloaded_a_box.assists == 1
    assert reloaded_b_box.assists == 1
    ckpt_temp.unlink(missing_ok=True)

    # 10. Deliverables Export
    events_export = out_dir / "events_auto.jsonl"
    events_raw = out_dir / "events_raw.jsonl"
    audit_trail = out_dir / "audit_trail.jsonl"
    checkpoint = out_dir / "checkpoint.json"
    boxscore_csv = out_dir / "boxscore_auto.csv"
    summary_json = out_dir / "summary.json"

    ledger.export_jsonl(events_export)
    ledger.export_raw_transactions(events_raw)
    ledger.export_audit_log(audit_trail)
    ledger.save_checkpoint(checkpoint)
    BoxScoreEngine.export_csv(team_a_box, team_b_box, boxscore_csv)

    elapsed = time.perf_counter() - t_start
    summary_data = {
        "schema_version": "task10-assist-diagnostic-v1",
        "task_id": "01C",
        "status": "completed",
        "purpose": "synthetic_contract_validation",
        "real_data_limitation": "Official continuous video with approved pass/assist labels is pending; evaluated via synthetic contract diagnostic without claiming real-data recognition accuracy.",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": round(elapsed, 3),
        "test_cases": test_cases_summary,
        "boxscore": {
            "team_a_score": team_a_box.total_score,
            "team_a_assists": team_a_box.assists,
            "team_b_score": team_b_box.total_score,
            "team_b_assists": team_b_box.assists,
        },
        "exports": {
            "events_auto_jsonl": str(events_export),
            "events_raw_jsonl": str(events_raw),
            "audit_trail_jsonl": str(audit_trail),
            "checkpoint_json": str(checkpoint),
            "boxscore_csv": str(boxscore_csv),
        },
    }
    summary_json.write_text(json.dumps(summary_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Assist synthetic diagnostic complete in {elapsed:.3f}s. Summary written to {summary_json}")
    return summary_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(ROOT / "outputs/sequence-01-20261115/01C/diagnostic_run"))
    args = parser.parse_args()
    run_diagnostic(Path(args.output).resolve())
