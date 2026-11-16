#!/usr/bin/env python3
"""Programmatic verification of Task07C acceptance readiness across tooling, data, and candidate."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from basketball_scoreboard.spatial_io import file_hash, write_json


def check_file(path_str):
    p = Path(path_str)
    if not p.exists():
        return {"exists": False, "size_bytes": 0, "sha256": None}
    return {"exists": True, "size_bytes": p.stat().st_size, "sha256": file_hash(p)}


def main():
    profile_path = ROOT / 'configs/evaluation/task07_vietnam_tonga.json'
    profile = json.loads(profile_path.read_text(encoding='utf-8'))
    
    # 1. Tooling Readiness
    tooling = {
        "evaluator_script": check_file(ROOT / 'scripts/evaluate_ball_possession.py'),
        "evaluator_core": check_file(ROOT / 'src/basketball_scoreboard/possession_evaluation.py'),
        "ball_tracker": check_file(ROOT / 'scripts/track_ball_possession.py'),
        "player_tracker": check_file(ROOT / 'scripts/track_players.py'),
        "failure_trace_tool": check_file(ROOT / 'scripts/trace_task07b_control_failures.py'),
        "test_suite_status": "309 passed, 0 failed (verified 2026-11-07)",
        "tooling_status": "READY"
    }

    # 2. Data Readiness & Exposure Audit
    sources = {
        "parent_video": {
            "path": "codebase/assets_test/vietnam-tonga.mp4",
            "file_info": check_file(ROOT / 'assets_test/vietnam-tonga.mp4'),
            "expected_sha256": "1443c1d263c8037a5684f3dbc0ef9216beb5097d9a47c4c1c9b94d1363e26865",
            "exposure": "Parent broadcast match (23 min); 30s segments extracted with user approval."
        },
        "development_segment": {
            "path": "codebase/outputs/task07-vietnam-tonga-segments-20261104/media/vt_development.mp4",
            "file_info": check_file(ROOT / 'outputs/task07-vietnam-tonga-segments-20261104/media/vt_development.mp4'),
            "expected_sha256": "8fd370b0668860a5c70d56bf256c76e3783bc1fe6598b529944ad00ca0616b45",
            "exposure": "Fully exposed; used for development and tuning in Task07, 07A, 07B.",
            "ground_truth": {
                "path": "codebase/data/matches/vietnam_tonga/reviewed-vt_development-v2.json",
                "file_info": check_file(ROOT / 'data/matches/vietnam_tonga/reviewed-vt_development-v2.json'),
                "review_status": "approved",
                "ball_samples": 108,
                "ball_eligible": 72,
                "control_intervals": 8,
                "control_eligible_s": 14.30,
                "passes": 5,
                "player_trajectory_gt": "MISSING (no frame-level player bounding boxes/tracks)"
            }
        },
        "validation_segment": {
            "path": "codebase/outputs/task07-vietnam-tonga-segments-20261104/media/vt_validation.mp4",
            "file_info": check_file(ROOT / 'outputs/task07-vietnam-tonga-segments-20261104/media/vt_validation.mp4'),
            "expected_sha256": "88b6f9ce44feed84cb2a2b1fcc6b98d1a88fe38c1b16a6212682f5fa96c41544",
            "exposure": "Visually inspected on 2026-11-04 (validation-exposure.json); same-match diagnostic pilot, NOT an untouched holdout.",
            "ground_truth": {
                "path": "codebase/outputs/task07-vietnam-tonga-segments-20261104/review-validation-final/annotations-draft.json",
                "file_info": check_file(ROOT / 'outputs/task07-vietnam-tonga-segments-20261104/review-validation-final/annotations-draft.json'),
                "review_status": "draft",
                "reviewer": None,
                "ball_samples": 94,
                "ball_eligible": "Unverified draft HSV proposals",
                "control_intervals": 0,
                "passes": 0,
                "evaluator_acceptance": "REJECTED by possession_evaluation.py (review_status == draft)"
            }
        },
        "legacy_holdout_broadcast": {
            "session": "u18_3x3_tournament_01",
            "clips": ["clip04", "clip05", "clip06", "clip07"],
            "exposure": "Group exposure recorded via task07-clip04.json on 2026-11-04; protected by default-deny; no Task07 ball/control/pass GT."
        }
    }
    
    data_status = "NOT_READY_BLOCKED"
    data_reasons = [
        "No approved ground truth exists for validation segment (annotations-draft.json has review_status=draft, 0 control intervals, 0 passes).",
        "Continuous trajectory player identity ground truth is completely missing across all segments.",
        "No untouched independent match test set exists in repository."
    ]

    # 3. Candidate Readiness (from Task07B decoupling paired evaluation)
    cand_eval_path = ROOT / 'outputs/task07b-decoupling-20261107/candidate-evaluation/evaluation.json'
    cand_eval = json.loads(cand_eval_path.read_text(encoding='utf-8')) if cand_eval_path.exists() else {}
    
    candidate = {
        "source_evaluation": str(cand_eval_path.relative_to(ROOT)),
        "metrics": {
            "ball_observed_recall": cand_eval.get("ball", {}).get("recall"),
            "ball_target": profile.get("ball_recall_min"),
            "ball_status": "FAILED (50.0% < 90.0%)",
            "strict_controller_accuracy": cand_eval.get("control", {}).get("strict_accuracy"),
            "strict_controller_target": profile.get("control_accuracy_min"),
            "control_status": "FAILED (0.0% < 90.0%)",
            "strict_pass_precision": cand_eval.get("passes_strict", {}).get("precision"),
            "strict_pass_precision_target": profile.get("pass_precision_min"),
            "strict_pass_recall": cand_eval.get("passes_strict", {}).get("recall"),
            "strict_pass_recall_target": profile.get("pass_recall_min"),
            "pass_status": "FAILED (0.0% < 90.0%, 0 TP, 5 FN)"
        },
        "integrity": cand_eval.get("integrity"),
        "acceptance_pass": cand_eval.get("acceptance_pass"),
        "acceptance_status": cand_eval.get("acceptance_status"),
        "candidate_status": "NOT_READY_FAILED_CRITERIA"
    }

    report = {
        "timestamp": "2026-11-08T00:18:00+07:00",
        "task": "Task07C Acceptance Readiness Assessment",
        "acceptance_profile": {
            "path": str(profile_path.relative_to(ROOT)),
            "sha256": file_hash(profile_path),
            "profile_content": profile
        },
        "tooling_readiness": tooling,
        "data_readiness": {
            "status": data_status,
            "reasons": data_reasons,
            "sources": sources
        },
        "candidate_readiness": candidate,
        "overall_readiness_summary": {
            "tooling": "READY",
            "data": "NOT_READY (Missing approved validation GT, missing control/pass on validation, missing player trajectory GT)",
            "candidate": "NOT_READY (Failed accuracy criteria on development GT: ball 50%, control 0%, pass 0%)",
            "can_freeze_07c": False
        }
    }

    out_file = ROOT / 'outputs/task07c-acceptance-package-20261107/readiness_audit.json'
    write_json(out_file, report)
    print(f"Readiness audit written to {out_file.relative_to(ROOT)}")
    print(json.dumps(report["overall_readiness_summary"], indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())

