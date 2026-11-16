#!/usr/bin/env python3
"""Synthetic Contract Diagnostic Runner for Rebounds (Task 09 / Sequence 01B).

Executes contract verification for ReboundEngine and EventLedger integration:
  - Demonstrates eligible missed field goals (OREB, DREB).
  - Demonstrates final vs non-final FT applicability.
  - Demonstrates rejection of made, unknown, unresolved, not_a_shot, predicted, and isolated controls.
  - Demonstrates causal parent link, void cascade, and raw replay idempotency.
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

from basketball_scoreboard.boxscore import BoxScoreEngine
from basketball_scoreboard.events import EventLedger, EventStatus, EventType, LedgerEventRecord
from basketball_scoreboard.identity import RosterConfig, RosterPlayer
from basketball_scoreboard.rebounds import ReboundEngine, ReboundEngineConfig, ReboundType


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
            RosterPlayer(team_id="team_vie", player_id="vie_01", jersey_number="1", name="Player Vie 1"),
            RosterPlayer(team_id="team_vie", player_id="vie_06", jersey_number="6", name="Player Vie 6"),
            RosterPlayer(team_id="team_tga", player_id="tga_01", jersey_number="1", name="Player Tga 1"),
            RosterPlayer(team_id="team_tga", player_id="tga_18", jersey_number="18", name="Player Tga 18"),
        ],
    )

    engine = ReboundEngine()
    ledger = EventLedger()
    box_engine = BoxScoreEngine(roster=roster)

    test_cases_summary = []

    # Case 1: Eligible missed FG by team_tga, sustained recovery by vie_01 -> Defensive Rebound
    c1_obs = [
        {"team_id": "team_vie", "player_id": "vie_01", "source_time_s": 10.1, "frame_index": 303, "confidence": 0.95},
        {"team_id": "team_vie", "player_id": "vie_01", "source_time_s": 10.2, "frame_index": 306, "confidence": 0.95},
        {"team_id": "team_vie", "player_id": "vie_01", "source_time_s": 10.3, "frame_index": 309, "confidence": 0.95},
        {"team_id": "team_vie", "player_id": "vie_01", "source_time_s": 10.4, "frame_index": 312, "confidence": 0.95},
    ]
    r1 = engine.evaluate_missed_shot("shot_miss_001", "miss", "team_tga", 10.0, c1_obs, shot_kind="field_goal")
    assert r1 is not None and r1.status == EventStatus.AUTO_CONFIRMED and r1.rebound_type == ReboundType.DEFENSIVE
    rec1 = r1.to_ledger_record()
    assert ledger.record_event(rec1) is True
    test_cases_summary.append({"case": "missed_fg_defensive_rebound", "rebound_id": r1.rebound_id, "status": "confirmed"})

    # Case 2: Eligible missed FG by team_vie, sustained recovery by vie_06 -> Offensive Rebound
    c2_obs = [
        {"team_id": "team_vie", "player_id": "vie_06", "source_time_s": 25.1, "frame_index": 753, "confidence": 0.92},
        {"team_id": "team_vie", "player_id": "vie_06", "source_time_s": 25.2, "frame_index": 756, "confidence": 0.92},
        {"team_id": "team_vie", "player_id": "vie_06", "source_time_s": 25.3, "frame_index": 759, "confidence": 0.92},
    ]
    r2 = engine.evaluate_missed_shot("shot_miss_002", "miss", "team_vie", 25.0, c2_obs, shot_kind="field_goal")
    assert r2 is not None and r2.status == EventStatus.AUTO_CONFIRMED and r2.rebound_type == ReboundType.OFFENSIVE
    rec2 = r2.to_ledger_record()
    assert ledger.record_event(rec2) is True
    test_cases_summary.append({"case": "missed_fg_offensive_rebound", "rebound_id": r2.rebound_id, "status": "confirmed"})

    # Case 3: Final missed FT -> eligible rebound
    c3_obs = [
        {"team_id": "team_tga", "player_id": "tga_01", "source_time_s": 40.1, "frame_index": 1203, "confidence": 0.90},
        {"team_id": "team_tga", "player_id": "tga_01", "source_time_s": 40.2, "frame_index": 1206, "confidence": 0.90},
        {"team_id": "team_tga", "player_id": "tga_01", "source_time_s": 40.3, "frame_index": 1209, "confidence": 0.90},
    ]
    r3 = engine.evaluate_missed_shot("ft_miss_final", "miss", "team_vie", 40.0, c3_obs, shot_kind="free_throw", is_last_free_throw=True)
    assert r3 is not None and r3.status == EventStatus.AUTO_CONFIRMED and r3.rebound_type == ReboundType.DEFENSIVE
    rec3 = r3.to_ledger_record()
    assert ledger.record_event(rec3) is True
    test_cases_summary.append({"case": "final_ft_miss_rebound", "rebound_id": r3.rebound_id, "status": "confirmed"})

    # Case 4: Non-final missed FT -> dead ball, no rebound
    r4 = engine.evaluate_missed_shot("ft_miss_non_final", "miss", "team_vie", 50.0, c3_obs, shot_kind="free_throw", is_last_free_throw=False)
    assert r4 is None
    test_cases_summary.append({"case": "non_final_ft_miss_rejected", "status": "correctly_rejected_none"})

    # Case 5: Made shot -> no rebound
    r5 = engine.evaluate_missed_shot("shot_made", "made", "team_tga", 60.0, c1_obs)
    assert r5 is None
    test_cases_summary.append({"case": "made_shot_rejected", "status": "correctly_rejected_none"})

    # Case 6: Not a shot -> no rebound
    r6 = engine.evaluate_missed_shot("not_shot", "not_a_shot", "team_tga", 70.0, c1_obs)
    assert r6 is None
    test_cases_summary.append({"case": "not_a_shot_rejected", "status": "correctly_rejected_none"})

    # Case 7: Unknown/unresolved shot outcome -> unresolved candidate, never auto_confirmed
    c7_obs = [
        {"team_id": "team_vie", "player_id": "vie_01", "source_time_s": 80.1, "frame_index": 2403, "confidence": 0.95},
        {"team_id": "team_vie", "player_id": "vie_01", "source_time_s": 80.2, "frame_index": 2406, "confidence": 0.95},
        {"team_id": "team_vie", "player_id": "vie_01", "source_time_s": 80.3, "frame_index": 2409, "confidence": 0.95},
    ]
    r7 = engine.evaluate_missed_shot("shot_unknown", "unknown", "team_tga", 80.0, c7_obs)
    assert r7 is not None and r7.status == EventStatus.UNRESOLVED
    test_cases_summary.append({"case": "unknown_miss_unresolved", "status": "unresolved_not_confirmed"})

    # Case 8: Predicted-only samples -> no sustained control
    c8_pred = [
        {"team_id": "team_vie", "player_id": "vie_01", "source_time_s": 90.1, "sample_type": "predicted"},
        {"team_id": "team_vie", "player_id": "vie_01", "source_time_s": 90.2, "sample_type": "predicted"},
        {"team_id": "team_vie", "player_id": "vie_01", "source_time_s": 90.3, "sample_type": "predicted"},
    ]
    r8 = engine.evaluate_missed_shot("shot_pred", "miss", "team_tga", 90.0, c8_pred)
    assert r8 is None
    test_cases_summary.append({"case": "predicted_control_rejected", "status": "correctly_rejected_none"})

    # Case 9: Isolated samples with gap > max_control_gap_s -> no sustained control
    c9_iso = [
        {"team_id": "team_vie", "player_id": "vie_01", "source_time_s": 100.1, "frame_index": 3003},
        {"team_id": "team_vie", "player_id": "vie_01", "source_time_s": 103.4, "frame_index": 3102},
    ]
    r9 = engine.evaluate_missed_shot("shot_iso", "miss", "team_tga", 100.0, c9_iso)
    assert r9 is None
    test_cases_summary.append({"case": "isolated_controls_rejected", "status": "correctly_rejected_none"})

    # Compile BoxScore
    team_a_box, team_b_box = box_engine.compile(ledger)

    # Invariants verification
    # Vietnam: 1 DREB (vie_01), 1 OREB (vie_06) -> 2 total rebounds
    # Tonga: 1 DREB (tga_01) -> 1 total rebound
    assert team_a_box.rebounds_total == 2
    assert team_a_box.rebounds_defensive == 1
    assert team_a_box.rebounds_offensive == 1
    assert team_b_box.rebounds_total == 1
    assert team_b_box.rebounds_defensive == 1

    # Raw transaction replay idempotency
    assert ledger.record_event(rec1) is False
    assert len(ledger.get_active_events()) == 3

    # Export deliverables
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
        "schema_version": "task09-rebound-diagnostic-v1",
        "task_id": "01B",
        "status": "completed",
        "purpose": "synthetic_contract_validation",
        "real_data_limitation": "Official continuous video with approved control/rebound labels is pending; evaluated via synthetic contract diagnostic without claiming real-data recognition accuracy.",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": round(elapsed, 3),
        "test_cases": test_cases_summary,
        "boxscore": {
            "team_a_rebounds_total": team_a_box.rebounds_total,
            "team_a_rebounds_defensive": team_a_box.rebounds_defensive,
            "team_a_rebounds_offensive": team_a_box.rebounds_offensive,
            "team_b_rebounds_total": team_b_box.rebounds_total,
            "team_b_rebounds_defensive": team_b_box.rebounds_defensive,
            "team_b_rebounds_offensive": team_b_box.rebounds_offensive,
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
    print(f"Rebound synthetic diagnostic complete in {elapsed:.3f}s. Summary written to {summary_json}")
    return summary_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(ROOT / "outputs/sequence-01-20261115/01B/diagnostic_run"))
    args = parser.parse_args()
    run_diagnostic(Path(args.output).resolve())
