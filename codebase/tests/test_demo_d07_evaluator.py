"""Targeted test suite for Task D07: Production Evaluator, Scope Validation & Matching Invariants."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import pytest

from basketball_scoreboard.evaluation_scope import normalize_scope, validate_prediction_binding
from basketball_scoreboard.evaluator_v2 import (
    EvaluatorV2Protocol,
    ProductionEvaluatorV2,
    calculate_metric_rates,
)


def test_scope_validation_guards():
    """Verify scope validation rejects source hash mismatch, short coverage, and nonfinite timestamps."""
    scope = {
        "video_id": "vietnam-tonga",
        "source_sha256": "correct_hash_12345678",
        "start_time_s": 300.0,
        "end_time_s": 330.0,
    }

    # 1. Source hash mismatch rejected
    bad_run = {
        "source_fingerprint_sha256": "mismatched_hash_99999",
        "source_coverage": {"first_time_s": 300.0, "last_time_s": 330.0},
    }
    with pytest.raises(ValueError, match="Prediction source hash does not match evaluation scope"):
        validate_prediction_binding(bad_run, scope)

    # 2. Coverage shorter than interval rejected
    short_run = {
        "source_fingerprint_sha256": "correct_hash_12345678",
        "source_coverage": {"first_time_s": 305.0, "last_time_s": 320.0},  # Shorter than 300-330
    }
    with pytest.raises(ValueError, match="Prediction coverage is shorter"):
        validate_prediction_binding(short_run, scope)

    # 3. Nonfinite timestamp rejected
    events = {
        "pts": [
            {
                "video_id": "vietnam-tonga",
                "score_time_s": float("nan"),
                "release_time_s": 301.0,
                "team_id": "VIE",
            }
        ]
    }
    with pytest.raises(ValueError, match="Nonfinite event timestamp"):
        normalize_scope(events, scope)


def test_greedy_trap_resolved_by_max_cardinality():
    """Verify maximum cardinality bipartite matching avoids greedy tie traps."""
    proto = EvaluatorV2Protocol(
        shot_release_tolerance_s=0.50,
        shot_basket_tolerance_s=0.50,
        require_both_release_and_basket=False,
    )
    evaluator = ProductionEvaluatorV2(proto)

    preds = [
        {"shot_id": "p1", "video_id": "v", "release_time_s": 9.5, "outcome_time_s": 10.0, "team_id": "A", "shooter_player_id": "pA", "point_value": 2, "outcome": "made"},
        {"shot_id": "p2", "video_id": "v", "release_time_s": 9.2, "outcome_time_s": 9.7, "team_id": "A", "shooter_player_id": "pA", "point_value": 2, "outcome": "made"},
    ]
    gts = [
        {"shot_id": "g1", "video_id": "v", "release_time_s": 9.1, "outcome_time_s": 9.6, "team_id": "A", "shooter_id": "pA", "point_value": 2, "result": "made"},
        {"shot_id": "g2", "video_id": "v", "release_time_s": 9.8, "outcome_time_s": 10.3, "team_id": "A", "shooter_id": "pA", "point_value": 2, "result": "made"},
    ]

    res = evaluator.evaluate_pts(preds, gts)
    assert res["detection"]["tp"] == 2
    assert res["strict"]["tp"] == 2
    assert res["detection"]["fp"] == 0
    assert res["detection"]["fn"] == 0


def test_strict_attribution_mismatch_creates_strict_fp_and_fn():
    """Verify wrong player or wrong point value counts as detection TP but strict failure (FP+FN)."""
    proto = EvaluatorV2Protocol(
        shot_release_tolerance_s=0.50,
        shot_basket_tolerance_s=0.50,
        require_both_release_and_basket=False,
    )
    evaluator = ProductionEvaluatorV2(proto)

    preds = [
        {"shot_id": "p1", "video_id": "v", "release_time_s": 9.5, "outcome_time_s": 10.0, "team_id": "A", "shooter_id": "player_WRONG", "point_value": 2, "outcome": "made"}
    ]
    gts = [
        {"shot_id": "g1", "video_id": "v", "release_time_s": 9.5, "outcome_time_s": 10.0, "team_id": "A", "shooter_id": "player_RIGHT", "point_value": 2, "result": "made"}
    ]

    res = evaluator.evaluate_pts(preds, gts)
    # Detection TP (matched in time)
    assert res["detection"]["tp"] == 1
    assert res["detection"]["fp"] == 0
    assert res["detection"]["fn"] == 0

    # Strict TP is 0 because shooter attribution failed
    assert res["strict"]["tp"] == 0
    assert res["strict"]["fp"] == 1
    assert res["strict"]["fn"] == 1


def test_zero_denominator_metric_rate_reasons():
    """Verify zero denominator produces None with mathematical reason codes."""
    m_empty = calculate_metric_rates(tp=0, fp=0, fn=0)
    assert m_empty.precision is None
    assert m_empty.recall is None
    assert m_empty.reason == "no_events"

    m_zero_preds = calculate_metric_rates(tp=0, fp=0, fn=5)
    assert m_zero_preds.precision is None
    assert m_zero_preds.recall == 0.0
    assert m_zero_preds.reason == "zero_predictions"

    m_zero_gt = calculate_metric_rates(tp=0, fp=3, fn=0)
    assert m_zero_gt.precision == 0.0
    assert m_zero_gt.recall is None
    assert m_zero_gt.reason == "zero_gt_events"


def test_evaluate_v2_cli_execution(tmp_path):
    """Verify scripts/evaluate_v2.py runs correctly and exports complete evaluation bundle."""
    root = Path(__file__).resolve().parents[1]
    eval_script = root / "scripts/evaluate_v2.py"
    gt_file = root / "outputs/quality-revision-20261116/full-match-01/normalized-ground-truth.json"
    pred_dir = root / "outputs/quality-revision-20261116/full-match-01/video-run"
    out_dir = tmp_path / "eval_out"

    cmd = [
        sys.executable,
        str(eval_script),
        "--predictions", str(pred_dir),
        "--ground-truth", str(gt_file),
        "--output-dir", str(out_dir),
        "--diagnostic",
        "--quiet",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(root))
    assert res.returncode == 0, f"evaluate_v2 failed: {res.stderr}\n{res.stdout}"

    # Verify generated bundle files
    assert (out_dir / "evaluation_summary.json").is_file()
    assert (out_dir / "match_table.json").is_file()
    assert (out_dir / "matched_events.csv").is_file()
    assert (out_dir / "error_index.json").is_file()

    summary = json.loads((out_dir / "evaluation_summary.json").read_text(encoding="utf-8"))
    assert "stats" in summary
    assert "pts" in summary["stats"]
    assert "reb" in summary["stats"]
    assert "ast" in summary["stats"]
    assert "combined_pra" in summary
