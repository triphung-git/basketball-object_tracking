#!/usr/bin/env python3
"""Generate canonical Task07C acceptance manifest."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from basketball_scoreboard.spatial_io import file_hash, write_json


def main():
    profile_path = ROOT / 'configs/evaluation/task07_vietnam_tonga.json'
    profile = json.loads(profile_path.read_text(encoding='utf-8'))
    
    manifest = {
        "schema_version": "2.1.0",
        "task_id": "Task07C",
        "generated_at_utc": "2026-11-08T00:19:00+07:00",
        "protocol": {
            "name": "task07-vietnam-tonga-20261104",
            "approval_status": "approved_by_user",
            "acceptance_profile_path": "codebase/configs/evaluation/task07_vietnam_tonga.json",
            "acceptance_profile_sha256": file_hash(profile_path),
            "profile_criteria": profile
        },
        "evaluator": {
            "cli_script": {
                "path": "codebase/scripts/evaluate_ball_possession.py",
                "sha256": file_hash(ROOT / 'scripts/evaluate_ball_possession.py')
            },
            "core_module": {
                "path": "codebase/src/basketball_scoreboard/possession_evaluation.py",
                "sha256": file_hash(ROOT / 'src/basketball_scoreboard/possession_evaluation.py')
            }
        },
        "sources": {
            "parent_source": {
                "video_id": "vietnam_tonga_parent",
                "relative_path": "codebase/assets_test/vietnam-tonga.mp4",
                "sha256": file_hash(ROOT / 'assets_test/vietnam-tonga.mp4'),
                "resolution": [1920, 1080],
                "fps": 30.0,
                "exposure_status": "approved_source_parent"
            },
            "development_segment": {
                "video_id": "vt_development",
                "relative_path": "codebase/outputs/task07-vietnam-tonga-segments-20261104/media/vt_development.mp4",
                "sha256": file_hash(ROOT / 'outputs/task07-vietnam-tonga-segments-20261104/media/vt_development.mp4'),
                "parent_time_range_s": [300.0, 330.0],
                "duration_s": 30.0,
                "frames": 900,
                "camera_policy": {
                    "path": "codebase/outputs/task07-vietnam-tonga-segments-20261104/vt_development-policy-ball-roi-v4.json",
                    "sha256": file_hash(ROOT / 'outputs/task07-vietnam-tonga-segments-20261104/vt_development-policy-ball-roi-v4.json')
                },
                "exposure_status": "development_tuned_100_percent_exposed"
            },
            "validation_segment": {
                "video_id": "vt_validation",
                "relative_path": "codebase/outputs/task07-vietnam-tonga-segments-20261104/media/vt_validation.mp4",
                "sha256": file_hash(ROOT / 'outputs/task07-vietnam-tonga-segments-20261104/media/vt_validation.mp4'),
                "parent_time_range_s": [165.0, 195.0],
                "duration_s": 30.0,
                "frames": 900,
                "camera_policy": {
                    "path": "codebase/outputs/task07-vietnam-tonga-segments-20261104/vt_validation-policy-masked.json",
                    "sha256": file_hash(ROOT / 'outputs/task07-vietnam-tonga-segments-20261104/vt_validation-policy-masked.json')
                },
                "exposure_status": "same_match_diagnostic_visually_inspected_not_independent_holdout"
            }
        },
        "roster": {
            "path": "codebase/configs/rosters/vietnam_tonga.json",
            "sha256": file_hash(ROOT / 'configs/rosters/vietnam_tonga.json'),
            "approval_status": "approved_by_user"
        },
        "ball_possession_config": {
            "path": "codebase/configs/ball-possession-vietnam-tonga-spatial.json",
            "sha256": file_hash(ROOT / 'configs/ball-possession-vietnam-tonga-spatial.json')
        },
        "ground_truth": {
            "development_canonical": {
                "path": "codebase/data/matches/vietnam_tonga/reviewed-vt_development-v2.json",
                "sha256": file_hash(ROOT / 'data/matches/vietnam_tonga/reviewed-vt_development-v2.json'),
                "review_status": "approved",
                "reviewer": "user_reviewed_v2",
                "protocol_status": "approved",
                "ball_samples": 108,
                "ball_eligible": 72,
                "control_intervals": 8,
                "control_eligible_seconds": 14.30,
                "passes": 5,
                "player_trajectory_gt": "NOT_AVAILABLE"
            },
            "validation_candidate": {
                "path": "codebase/outputs/task07-vietnam-tonga-segments-20261104/review-validation-final/annotations-draft.json",
                "sha256": file_hash(ROOT / 'outputs/task07-vietnam-tonga-segments-20261104/review-validation-final/annotations-draft.json'),
                "review_status": "draft",
                "reviewer": None,
                "protocol_status": "approved",
                "ball_samples": 94,
                "control_intervals": 0,
                "passes": 0,
                "player_trajectory_gt": "NOT_AVAILABLE",
                "status": "BLOCKED_UNREVIEWED"
            }
        },
        "denominators_and_thresholds": {
            "ball_recall": {
                "minimum_samples": profile["minimum_visible_ball_samples"],
                "iou_threshold": profile["ball_iou_threshold"],
                "target_threshold": profile["ball_recall_min"],
                "development_eligible_samples": 72,
                "validation_eligible_samples": "PENDING_REVIEW"
            },
            "strict_control_accuracy": {
                "target_threshold": profile["control_accuracy_min"],
                "development_eligible_seconds": 14.30,
                "validation_eligible_seconds": "PENDING_ANNOTATION (0 intervals currently)"
            },
            "strict_pass_precision": {
                "target_threshold": profile["pass_precision_min"],
                "tolerance_s": profile["pass_tolerance_s"]
            },
            "strict_pass_recall": {
                "minimum_gt_passes": profile["minimum_completed_pass_gt"],
                "target_threshold": profile["pass_recall_min"],
                "development_gt_passes": 5,
                "validation_gt_passes": "PENDING_ANNOTATION (0 passes currently)"
            },
            "integrity_guards": {
                "prediction_only_control_allowed": 0,
                "completed_passes_crossing_cut_allowed": 0,
                "max_pts_error_s": profile["max_pts_error_s"]
            }
        },
        "readiness_summary": {
            "tooling": "READY",
            "data": "BLOCKED_PENDING_VALIDATION_GT",
            "candidate": "BLOCKED_ACCURACY_CRITERIA_UNMET",
            "freeze_07c_eligible": False
        }
    }

    out_file = ROOT / 'outputs/task07c-acceptance-package-20261107/acceptance_manifest.json'
    write_json(out_file, manifest)
    print(f"Acceptance manifest written to {out_file.relative_to(ROOT)}")
    return 0


if __name__ == '__main__':
    sys.exit(main())

