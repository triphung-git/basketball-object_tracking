"""Unit tests for Task D06: Near-rim Data Review Prep & GPU Training Readiness."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import pytest

root_dir = Path(__file__).resolve().parents[1]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from scripts.ingest_near_rim_review import validate_and_ingest_review


def test_ingest_near_rim_review_validation(tmp_path):
    """Verify validation logic for near-rim review labels."""
    # 1. Valid review payload
    valid_payload = {
        "schema_version": "near-rim-review-v1",
        "reviewed_frames": [
            {
                "sample_id": "near_rim_108",
                "visibility": "visible",
                "ball_bbox_xyxy": [920.0, 490.0, 950.0, 520.0],
                "rim_reviewed": True,
                "human_reviewed": True,
                "review_status": "reviewed",
            },
            {
                "sample_id": "near_rim_115",
                "visibility": "fully_occluded",
                "ball_bbox_xyxy": None,  # Correct: fully occluded has no bbox
                "rim_reviewed": True,
                "human_reviewed": True,
                "review_status": "reviewed",
            },
            {
                "sample_id": "near_rim_123",
                "visibility": "uncertain",
                "ball_bbox_xyxy": None,  # Quarantined
                "rim_reviewed": True,
                "human_reviewed": True,
                "review_status": "reviewed",
            },
        ],
    }
    json_path = tmp_path / "valid_review.json"
    json_path.write_text(json.dumps(valid_payload), encoding="utf-8")

    res = validate_and_ingest_review(json_path, validate_only=True)
    assert res["valid"] is True
    assert res["visible_count"] == 1
    assert res["fully_occluded_count"] == 1
    assert res["uncertain_quarantined_count"] == 1
    assert res["errors"] == []

    # 2. Invalid: fully occluded with invented bbox
    invalid_payload = {
        "schema_version": "near-rim-review-v1",
        "reviewed_frames": [
            {
                "sample_id": "near_rim_bad",
                "visibility": "fully_occluded",
                "ball_bbox_xyxy": [920.0, 490.0, 950.0, 520.0],  # Invalid!
                "review_status": "reviewed",
            }
        ],
    }
    bad_path = tmp_path / "bad_review.json"
    bad_path.write_text(json.dumps(invalid_payload), encoding="utf-8")

    res_bad = validate_and_ingest_review(bad_path, validate_only=True)
    assert res_bad["valid"] is False
    assert any("Fully occluded frame cannot have bbox" in err for err in res_bad["errors"])


def test_gpu_training_smoke_report_structure():
    """Verify that the D06 GPU smoke test report is present, valid, and exhibits finite gradients."""
    root = Path(__file__).resolve().parents[1]
    smoke_report_path = root / "outputs/demo-completion-20261116/D06/gpu-training-smoke.json"
    assert smoke_report_path.is_file(), f"Smoke report missing: {smoke_report_path}"

    data = json.loads(smoke_report_path.read_text(encoding="utf-8"))
    assert data["status"] == "gpu_training_smoke_passed"
    assert data["cuda_available"] is True
    assert "GeForce" in data["device"]["name"]
    assert data["finite_gradients"] is True
    assert data["nonzero_gradients"] is True
    assert data["optimizer_step_executed"] is True
    assert data["weight_updated_in_memory"] is True
    assert data["vram_headroom_mb"] > 2000.0  # Safe headroom


def test_real_user_approved_review_labels():
    """Verify that the real user-approved review labels for R01 are ingested and evaluated."""
    root = Path(__file__).resolve().parents[1]
    ingested_manifest_path = root / "outputs/demo-completion-20261116/D06/ingested-review/ingested_manifest.json"
    assert ingested_manifest_path.is_file(), f"Ingested manifest missing: {ingested_manifest_path}"

    ingested = json.loads(ingested_manifest_path.read_text(encoding="utf-8"))
    assert ingested["valid"] is True
    assert ingested["total_frames"] == 8
    assert ingested["reviewed_count"] == 8
    assert ingested["visible_count"] == 3
    assert ingested["fully_occluded_count"] == 5
    assert ingested["uncertain_quarantined_count"] == 0
    assert ingested["errors"] == []

    # Verify paired evaluation output on the near-rim packet
    eval_path = root / "outputs/demo-completion-20261116/D06/near_rim_candidate_evaluation.json"
    assert eval_path.is_file(), f"Evaluation report missing: {eval_path}"
    eval_data = json.loads(eval_path.read_text(encoding="utf-8"))
    assert eval_data["total_frames"] == 8
    assert eval_data["metrics"]["baseline"]["fp"] == 0
    assert eval_data["metrics"]["baseline"]["tn"] == 5

