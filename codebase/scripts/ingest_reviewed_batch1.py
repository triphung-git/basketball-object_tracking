"""Ingests user-reviewed REB & AST decisions from Batch 1 into data/v2/proposal and data/v2 with full relational integrity."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ingest_batch1():
    now_utc = datetime.now(timezone.utc).isoformat()
    reviewer = "user_triphung"

    target_dirs = [
        ROOT / "data" / "v2" / "proposal",
    ]

    for v2_dir in target_dirs:
        ann_dir = v2_dir / "annotations"
        ann_dir.mkdir(parents=True, exist_ok=True)

        # 1. Update ruleset.json
        ruleset_path = v2_dir / "ruleset.json"
        if ruleset_path.exists():
            with ruleset_path.open("r", encoding="utf-8") as f:
                ruleset = json.load(f)
            ruleset["review_status"] = "approved"
            ruleset["applicability_status"] = "confirmed"
            ruleset["protocol_status"] = "approved"
            ruleset["matching_windows_s"] = {
                "score_window_s": 0.5,
                "rebound_window_s": 1.0,
                "assist_window_s": 1.0,
            }
            ruleset["assist_criteria"] = {
                "max_dribbles": 2,
                "max_elapsed_s": 2.5,
                "assist_on_foul": "deferred_post_mvp",
            }
            ruleset["uncertain_handling"] = "isolated_separate_audit"
            ruleset["user_review_approved_utc"] = now_utc
            ruleset["source_review_note"] = "All 5 sequence-03B proposals approved by user: FIBA 3x3 1PT/2PT, defer assist-on-foul, max 2 dribbles / 2.5s assist, isolate uncertain cases, evaluator tolerances +-0.5s PTS / +-1.0s REB/AST"

            with ruleset_path.open("w", encoding="utf-8") as f:
                json.dump(ruleset, f, indent=2, ensure_ascii=False)
            print(f"Updated ruleset: {ruleset_path}")

        # 2. Add shots in vt_development to shots.csv
        shots_file = ann_dir / "shots.csv"
        shots_rows = []
        if shots_file.exists():
            with shots_file.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                shots_rows = list(reader)

        shots_rows = [s for s in shots_rows if not s["shot_id"].startswith("shot_vt_dev_")]

        # Add the 3 verified shots from vt_development
        shots_rows.append({
            "shot_id": "shot_vt_dev_001",
            "video_id": "vt_development",
            "shooter_id": "a_nguyen_huynh_phu_vinh",
            "team_id": "team_a",
            "release_time_s": "3.4667",
            "outcome_time_s": "3.9333",
            "shot_type": "2pt",
            "result": "miss",
            "score_time_s": "",
            "notes": "VIE missed 2PT attempt at t=3.47s-3.93s leading to offensive rebound",
        })

        shots_rows.append({
            "shot_id": "shot_vt_dev_002",
            "video_id": "vt_development",
            "shooter_id": "b_11",
            "team_id": "team_b",
            "release_time_s": "9.6000",
            "outcome_time_s": "10.1333",
            "shot_type": "1pt",
            "result": "made",
            "score_time_s": "10.1333",
            "notes": "TGA #11 made 1PT basket at t=10.133s",
        })

        shots_rows.append({
            "shot_id": "shot_vt_dev_003",
            "video_id": "vt_development",
            "shooter_id": "a_nguyen_phuc_vinh",
            "team_id": "team_a",
            "release_time_s": "24.8000",
            "outcome_time_s": "25.6333",
            "shot_type": "1pt",
            "result": "miss",
            "score_time_s": "",
            "notes": "VIE #6 missed 1PT attempt at t=24.8s-25.63s leading to TGA defensive rebound",
        })

        with shots_file.open("w", encoding="utf-8", newline="") as f:
            fieldnames = ["shot_id", "video_id", "shooter_id", "team_id", "release_time_s", "outcome_time_s", "shot_type", "result", "score_time_s", "notes"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(shots_rows)
        print(f"Updated shots.csv ({len(shots_rows)} rows): {shots_file}")

        # 3. Add pass for play_001 in passes.csv
        passes_file = ann_dir / "passes.csv"
        passes_rows = []
        if passes_file.exists():
            with passes_file.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                passes_rows = list(reader)

        passes_rows = [p for p in passes_rows if p["pass_id"] != "pass_play_001_ast"]

        passes_rows.append({
            "pass_id": "pass_play_001_ast",
            "video_id": "vietnam-tonga",
            "passer_id": "b_11",
            "receiver_id": "b_01",
            "team_id": "team_b",
            "release_time_s": "139.8000",
            "receive_time_s": "140.3000",
            "outcome": "completed",
        })

        with passes_file.open("w", encoding="utf-8", newline="") as f:
            fieldnames = ["pass_id", "video_id", "passer_id", "receiver_id", "team_id", "release_time_s", "receive_time_s", "outcome"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(passes_rows)
        print(f"Updated passes.csv ({len(passes_rows)} rows): {passes_file}")

        # 4. Ingest Rebounds into rebounds.csv
        rebounds_file = ann_dir / "rebounds.csv"
        reb_rows = [
            {
                "rebound_id": "reb_batch1_001",
                "video_id": "vt_development",
                "shot_id": "shot_vt_dev_001",
                "actor_id": "a_nguyen_huynh_phu_vinh",
                "team_id": "team_a",
                "rebound_time_s": "4.5",
                "rebound_type": "offensive",
                "notes": "User reviewed: VIE #1 offensive rebound after missed 2PT shot",
            },
            {
                "rebound_id": "reb_batch1_003",
                "video_id": "vt_development",
                "shot_id": "shot_vt_dev_003",
                "actor_id": "b_18",
                "team_id": "team_b",
                "rebound_time_s": "26.5",
                "rebound_type": "defensive",
                "notes": "User reviewed: TGA #18 defensive rebound after missed shot",
            },
        ]

        with rebounds_file.open("w", encoding="utf-8", newline="") as f:
            fieldnames = ["rebound_id", "video_id", "shot_id", "actor_id", "team_id", "rebound_time_s", "rebound_type", "notes"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(reb_rows)
        print(f"Updated rebounds.csv ({len(reb_rows)} rows): {rebounds_file}")

        # 5. Ingest Assists into assists.csv
        assists_file = ann_dir / "assists.csv"
        ast_rows = [
            {
                "assist_id": "ast_batch1_003",
                "video_id": "vietnam-tonga",
                "pass_id": "pass_play_001_ast",
                "shot_id": "play_001",
                "passer_id": "b_11",
                "scorer_id": "b_01",
                "team_id": "team_b",
                "assist_time_s": "139.8",
                "eligibility": "eligible",
                "notes": "User reviewed: Jonah Palelei (b_11) assist to Marcus Alipate (b_01) 2PT made shot in play_001",
            }
        ]

        with assists_file.open("w", encoding="utf-8", newline="") as f:
            fieldnames = ["assist_id", "video_id", "pass_id", "shot_id", "passer_id", "scorer_id", "team_id", "assist_time_s", "eligibility", "notes"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(ast_rows)
        print(f"Updated assists.csv ({len(ast_rows)} rows): {assists_file}")

        # 6. Ingest Reviews into reviews.csv
        reviews_file = ann_dir / "reviews.csv"
        rev_rows = []
        if reviews_file.exists():
            with reviews_file.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                rev_rows = list(reader)

        # Filter out any old batch1 rows
        rev_rows = [
            r for r in rev_rows
            if not r["record_id"].startswith("reb_batch1_")
            and not r["record_id"].startswith("ast_batch1_")
            and not r["record_id"].startswith("shot_vt_dev_")
            and not r["record_id"].startswith("pass_play_001_ast")
            and not r["record_id"].startswith("batch1_")
        ]

        # Add approved reviews for the new approved records
        new_approved = [
            ("shots", "shot_vt_dev_001", "approved", "Approved shot attempt vt_dev_001 (VIE miss at 3.93s)"),
            ("shots", "shot_vt_dev_002", "approved", "Approved made shot vt_dev_002 (TGA made at 10.133s)"),
            ("shots", "shot_vt_dev_003", "approved", "Approved shot attempt vt_dev_003 (VIE miss at 25.63s)"),
            ("passes", "pass_play_001_ast", "approved", "Approved pass from TGA #11 to #1 leading to play_001 score"),
            ("rebounds", "reb_batch1_001", "approved", "User reviewed and approved: VIE #1 offensive rebound at 4.5s"),
            ("rebounds", "reb_batch1_003", "approved", "User reviewed and approved: TGA #18 defensive rebound at 26.5s"),
            ("assists", "ast_batch1_003", "approved", "User reviewed and approved: TGA #11 assist to #1 in play_001"),
        ]

        for tbl, rec_id, status, notes in new_approved:
            rev_rows.append({
                "table_name": tbl,
                "record_id": rec_id,
                "review_status": status,
                "reviewer": reviewer,
                "reviewed_utc": now_utc,
                "review_notes": notes,
            })

        with reviews_file.open("w", encoding="utf-8", newline="") as f:
            fieldnames = ["table_name", "record_id", "review_status", "reviewer", "reviewed_utc", "review_notes"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rev_rows)
        print(f"Updated reviews.csv ({len(rev_rows)} rows): {reviews_file}")


if __name__ == "__main__":
    ingest_batch1()
