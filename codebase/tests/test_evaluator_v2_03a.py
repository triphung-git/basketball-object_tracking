"""Comprehensive test suite for shared production evaluator (03A).

Tests independent mathematical correctness:
  1. Empty sets and zero-denominator handling (None/NA + reason code).
  2. Bipartite matching greedy-trap resolution (maximum cardinality guaranteed).
  3. Time tolerance boundary conditions (inclusive vs exclusive).
  4. One-to-one matching and duplicate prediction suppression.
  5. Strict attribution failures for PTS (wrong player, wrong team, wrong value).
  6. Strict attribution failures for REB (wrong subtype, wrong actor, wrong parent shot).
  7. Strict attribution failures for AST (wrong passer, wrong scorer, wrong parent shot).
  8. Unknown/unresolved actor handling (detection TP, strict fail).
  9. Hand-calculated multi-event PRA combined rate verification.
  10. CLI execution, output bundle generation, and error index cataloging.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]

from basketball_scoreboard.evaluator_v2 import (
    EvaluatorV2Protocol,
    ProductionEvaluatorV2,
    calculate_metric_rates,
    export_evaluation_bundle,
    load_ground_truth,
    load_predictions_from_bundle,
    solve_max_cardinality_min_cost_bipartite,
)


def test_zero_denominator_rates():
    """Verify mathematical handling of zero denominators."""
    # 0 GT, 0 Pred
    c0 = calculate_metric_rates(tp=0, fp=0, fn=0)
    assert c0.precision is None
    assert c0.recall is None
    assert c0.f1 is None
    assert c0.reason == "no_events"

    # 0 GT, 3 Pred (all FP)
    c1 = calculate_metric_rates(tp=0, fp=3, fn=0)
    assert c1.precision == 0.0
    assert c1.recall is None
    assert c1.f1 is None
    assert c1.reason == "zero_gt_events"

    # 2 GT, 0 Pred (all FN)
    c2 = calculate_metric_rates(tp=0, fp=0, fn=2)
    assert c2.precision is None
    assert c2.recall == 0.0
    assert c2.f1 is None
    assert c2.reason == "zero_predictions"


def test_greedy_trap_resolution():
    """Verify maximum cardinality is strictly preferred over local greedy min-cost."""
    # Graph where greedy choice traps the solver:
    # Pred 0 can match GT 0 (cost 0.1) or GT 1 (cost 0.15)
    # Pred 1 can ONLY match GT 0 (cost 0.2)
    # If Pred 0 greedily takes GT 0 (cost 0.1), Pred 1 is blocked -> cardinality 1.
    # Optimal max cardinality matches Pred 1 -> GT 0 and Pred 0 -> GT 1 -> cardinality 2!
    edges = [
        (0, 0, 0.10),
        (0, 1, 0.15),
        (1, 0, 0.20),
    ]
    matched, un_p, un_g = solve_max_cardinality_min_cost_bipartite(
        n_preds=2, n_gts=2, candidate_edges=edges
    )
    assert len(matched) == 2, f"Expected 2 matches, got {len(matched)}"
    assert (0, 1) in matched
    assert (1, 0) in matched
    assert len(un_p) == 0
    assert len(un_g) == 0


def test_time_tolerance_boundary():
    """Verify exact time tolerance boundary enforcement."""
    evaluator = ProductionEvaluatorV2(
        protocol=EvaluatorV2Protocol(
            shot_release_tolerance_s=0.50,
            shot_basket_tolerance_s=0.50,
        )
    )

    # Exactly at boundary: delta = 0.50s -> should match
    p_exact = [{"shot_id": "p1", "release_time_s": 10.0, "outcome_time_s": 11.0, "outcome": "made", "team_id": "A"}]
    g_exact = [{"shot_id": "g1", "release_time_s": 10.5, "outcome_time_s": 11.5, "result": "made", "team_id": "A"}]
    res_exact = evaluator.evaluate_pts(p_exact, g_exact)
    assert res_exact["detection"]["tp"] == 1
    assert res_exact["detection"]["fp"] == 0

    # Outside boundary: delta = 0.51s -> no match
    p_out = [{"shot_id": "p2", "release_time_s": 10.0, "outcome_time_s": 11.0, "outcome": "made", "team_id": "A"}]
    g_out = [{"shot_id": "g2", "release_time_s": 10.51, "outcome_time_s": 11.0, "result": "made", "team_id": "A"}]
    res_out = evaluator.evaluate_pts(p_out, g_out)
    assert res_out["detection"]["tp"] == 0
    assert res_out["detection"]["fp"] == 1
    assert res_out["detection"]["fn"] == 1


def test_duplicate_prediction_suppression():
    """Verify one-to-one matching suppresses duplicate predictions."""
    evaluator = ProductionEvaluatorV2()

    # Two predictions at exactly the same time for one GT
    preds = [
        {"shot_id": "p1", "release_time_s": 10.0, "outcome_time_s": 11.0, "outcome": "made", "team_id": "A", "player_id": "p10", "point_value": 2},
        {"shot_id": "p2", "release_time_s": 10.0, "outcome_time_s": 11.0, "outcome": "made", "team_id": "A", "player_id": "p10", "point_value": 2},
    ]
    gt = [
        {"shot_id": "g1", "release_time_s": 10.0, "outcome_time_s": 11.0, "result": "made", "team_id": "A", "shooter_id": "p10", "point_value": 2},
    ]

    res = evaluator.evaluate_pts(preds, gt)
    assert res["detection"]["tp"] == 1
    assert res["detection"]["fp"] == 1
    assert res["detection"]["fn"] == 0
    assert res["detection"]["precision"] == 0.50
    assert res["detection"]["recall"] == 1.00


def test_pts_strict_attribution_failures():
    """Verify PTS strict metric failures on wrong player, wrong team, or wrong point value."""
    evaluator = ProductionEvaluatorV2()

    gt = [
        {"shot_id": "g1", "release_time_s": 5.0, "outcome_time_s": 6.0, "result": "made", "team_id": "VIE", "shooter_id": "p01", "point_value": 2},
        {"shot_id": "g2", "release_time_s": 15.0, "outcome_time_s": 16.0, "result": "made", "team_id": "VIE", "shooter_id": "p02", "point_value": 1},
        {"shot_id": "g3", "release_time_s": 25.0, "outcome_time_s": 26.0, "result": "made", "team_id": "TGA", "shooter_id": "p03", "point_value": 2},
    ]

    # Pred 1: wrong player (p99 instead of p01)
    # Pred 2: wrong value (2 instead of 1)
    # Pred 3: wrong team (VIE instead of TGA)
    preds = [
        {"shot_id": "p1", "release_time_s": 5.0, "outcome_time_s": 6.0, "outcome": "made", "team_id": "VIE", "player_id": "p99", "point_value": 2},
        {"shot_id": "p2", "release_time_s": 15.0, "outcome_time_s": 16.0, "outcome": "made", "team_id": "VIE", "player_id": "p02", "point_value": 2},
        {"shot_id": "p3", "release_time_s": 25.0, "outcome_time_s": 26.0, "outcome": "made", "team_id": "VIE", "player_id": "p03", "point_value": 2},
    ]

    res = evaluator.evaluate_pts(preds, gt)
    # All 3 detected
    assert res["detection"]["tp"] == 3
    assert res["detection"]["fp"] == 0
    assert res["detection"]["fn"] == 0
    assert res["detection"]["precision"] == 1.0
    assert res["detection"]["recall"] == 1.0

    # Strict: 0 all-correct
    assert res["strict"]["tp"] == 0
    assert res["strict"]["fp"] == 3
    assert res["strict"]["fn"] == 3
    assert res["strict"]["precision"] == 0.0
    assert res["strict"]["recall"] == 0.0

    # Specific accuracies
    assert res["attribution"]["tp_team"] == 2  # p1 and p2 team matched
    assert res["attribution"]["tp_actor"] == 2  # p2 and p3 player matched
    assert res["attribution"]["tp_value"] == 2  # p1 and p3 value matched
    assert len(res["errors"]) == 3


def test_reb_strict_attribution_and_subtype():
    """Verify REB strict attribution on subtype (offensive vs defensive) and team rebound."""
    evaluator = ProductionEvaluatorV2()

    gt = [
        {"rebound_id": "gr1", "rebound_time_s": 10.0, "team_id": "VIE", "actor_id": "p01", "rebound_type": "offensive", "shot_id": "s1"},
        {"rebound_id": "gr2", "rebound_time_s": 20.0, "team_id": "TGA", "actor_id": None, "rebound_type": "team_rebound", "shot_id": "s2"},
    ]

    # Pred 1: matched time, but wrong subtype ('defensive')
    # Pred 2: matched time, team_rebound, team_id matches -> correct!
    preds = [
        {"rebound_id": "pr1", "recovery_time_s": 10.1, "team_id": "VIE", "player_id": "p01", "rebound_type": "defensive", "parent_event_id": "s1"},
        {"rebound_id": "pr2", "recovery_time_s": 20.0, "team_id": "TGA", "player_id": None, "rebound_type": "team_rebound", "parent_event_id": "s2"},
    ]

    res = evaluator.evaluate_reb(preds, gt)
    assert res["detection"]["tp"] == 2
    assert res["attribution"]["tp_subtype"] == 1
    assert res["attribution"]["tp_strict_all"] == 1

    assert res["strict"]["tp"] == 1
    assert res["strict"]["fp"] == 1
    assert res["strict"]["fn"] == 1


def test_ast_strict_attribution_and_parent_link():
    """Verify AST strict attribution on passer, scorer, team, and parent shot link."""
    evaluator = ProductionEvaluatorV2()

    gt = [
        {"assist_id": "ga1", "assist_time_s": 12.0, "team_id": "VIE", "passer_id": "p01", "scorer_id": "p02", "shot_id": "shot_10", "eligibility": "eligible"},
        {"assist_id": "ga2", "assist_time_s": 24.0, "team_id": "VIE", "passer_id": "p03", "scorer_id": "p04", "shot_id": "shot_20", "eligibility": "eligible"},
    ]

    # Pred 1: correct passer, scorer, team, shot link
    # Pred 2: wrong passer (p99)
    preds = [
        {"assist_id": "pa1", "assist_time_s": 12.2, "team_id": "VIE", "passer_id": "p01", "scorer_id": "p02", "parent_event_id": "shot_10"},
        {"assist_id": "pa2", "assist_time_s": 24.1, "team_id": "VIE", "passer_id": "p99", "scorer_id": "p04", "parent_event_id": "shot_20"},
    ]

    res = evaluator.evaluate_ast(preds, gt)
    assert res["detection"]["tp"] == 2
    assert res["attribution"]["tp_passer"] == 1
    assert res["attribution"]["tp_scorer"] == 2
    assert res["attribution"]["tp_strict_all"] == 1

    assert res["strict"]["tp"] == 1
    assert res["strict"]["fp"] == 1
    assert res["strict"]["fn"] == 1


def test_unknown_actor_strict_failure():
    """Verify that predictions with unknown/unresolved actors are detections but fail strict attribution."""
    evaluator = ProductionEvaluatorV2()

    gt = [
        {"shot_id": "g1", "release_time_s": 5.0, "outcome_time_s": 6.0, "result": "made", "team_id": "VIE", "shooter_id": "p01", "point_value": 2},
    ]
    preds = [
        {"shot_id": "p1", "release_time_s": 5.0, "outcome_time_s": 6.0, "outcome": "made", "team_id": "VIE", "player_id": None, "point_value": 2},
    ]

    res = evaluator.evaluate_pts(preds, gt)
    assert res["detection"]["tp"] == 1
    assert res["attribution"]["tp_actor"] == 0
    assert res["attribution"]["player_accuracy"] == 0.0
    assert res["strict"]["tp"] == 0
    assert res["strict"]["fp"] == 1
    assert res["strict"]["fn"] == 1


def test_hand_calculated_combined_pra():
    """Verify exact hand-calculated multi-event PRA combined rate."""
    evaluator = ProductionEvaluatorV2()

    # Pre-calculated scenario:
    # PTS: 2 GT, 2 Pred (both 100% correct) -> Event TP=2, FP=0, FN=0; Strict TP=2, FP=0, FN=0
    # REB: 1 GT, 2 Pred (1 matches but wrong player, 1 unmatched FP) ->
    #      Event: TP=1, FP=1, FN=0; Strict: TP=0, FP=2, FN=1
    # AST: 1 GT, 0 Pred -> Event: TP=0, FP=0, FN=1; Strict: TP=0, FP=0, FN=1
    # Combined Totals:
    #   Event:  TP=3, FP=1, FN=1 -> P=0.75, R=0.75, F1=0.75
    #   Strict: TP=2, FP=2, FN=2 -> P=0.50, R=0.50, F1=0.50

    gt_data = {
        "pts": [
            {"shot_id": "gs1", "release_time_s": 5.0, "outcome_time_s": 6.0, "result": "made", "team_id": "A", "shooter_id": "p1", "point_value": 2},
            {"shot_id": "gs2", "release_time_s": 15.0, "outcome_time_s": 16.0, "result": "made", "team_id": "B", "shooter_id": "p2", "point_value": 1},
        ],
        "reb": [
            {"rebound_id": "gr1", "rebound_time_s": 8.0, "team_id": "A", "actor_id": "p1", "rebound_type": "defensive"},
        ],
        "ast": [
            {"assist_id": "ga1", "assist_time_s": 4.5, "team_id": "A", "passer_id": "p3", "scorer_id": "p1", "eligibility": "eligible"},
        ],
    }

    pred_data = {
        "pts": [
            {"shot_id": "ps1", "release_time_s": 5.0, "outcome_time_s": 6.0, "outcome": "made", "team_id": "A", "player_id": "p1", "point_value": 2},
            {"shot_id": "ps2", "release_time_s": 15.0, "outcome_time_s": 16.0, "outcome": "made", "team_id": "B", "player_id": "p2", "point_value": 1},
        ],
        "reb": [
            {"rebound_id": "pr1", "recovery_time_s": 8.1, "team_id": "A", "player_id": "p99", "rebound_type": "defensive"},
            {"rebound_id": "pr2_fp", "recovery_time_s": 25.0, "team_id": "B", "player_id": "p5", "rebound_type": "offensive"},
        ],
        "ast": [],
    }

    summary = evaluator.evaluate_all(pred_data, gt_data)
    comb = summary["combined_pra"]

    det = comb["detection"]
    assert det["tp"] == 3
    assert det["fp"] == 1
    assert det["fn"] == 1
    assert det["precision"] == 0.75
    assert det["recall"] == 0.75
    assert det["f1"] == 0.75

    strict = comb["strict"]
    assert strict["tp"] == 2
    assert strict["fp"] == 2
    assert strict["fn"] == 2
    assert strict["precision"] == 0.50
    assert strict["recall"] == 0.50
    assert strict["f1"] == 0.50


def test_export_bundle(tmp_path: Path):
    """Verify complete export bundle generation."""
    evaluator = ProductionEvaluatorV2()
    summary = evaluator.evaluate_all(
        predictions={"pts": [], "reb": [], "ast": []},
        ground_truth={"pts": [], "reb": [], "ast": []},
    )

    out_bundle = export_evaluation_bundle(summary, tmp_path)
    assert out_bundle["evaluation_summary"].is_file()
    assert out_bundle["match_table"].is_file()
    assert out_bundle["matched_events"].is_file()
    assert out_bundle["error_index"].is_file()

    # Check JSON validity
    with out_bundle["evaluation_summary"].open(encoding="utf-8") as h:
        s_data = json.load(h)
        assert s_data["schema_version"] == "pra-evaluation-summary-v2"
        assert "combined_pra" in s_data
        assert "stats" in s_data


def test_cli_execution_with_synthetic_fixture(tmp_path: Path):
    """Verify scripts/evaluate_v2.py runs cleanly via subprocess on synthetic fixture."""
    fixture_path = ROOT / "tests" / "fixtures" / "pra_synthetic_fixture.json"
    cli_path = ROOT / "scripts" / "evaluate_v2.py"
    out_dir = tmp_path / "cli_run"

    cmd = [
        sys.executable,
        str(cli_path),
        "--predictions", str(fixture_path),
        "--ground-truth", str(fixture_path),
        "--output-dir", str(out_dir),
        "--diagnostic",
    ]

    import os
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT / 'src'};{ROOT / 'scripts'}"

    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    assert proc.returncode == 0, f"CLI failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"

    # Verify generated files
    assert (out_dir / "evaluation_summary.json").is_file()
    assert (out_dir / "match_table.json").is_file()
    assert (out_dir / "matched_events.csv").is_file()
    assert (out_dir / "error_index.json").is_file()

    with (out_dir / "evaluation_summary.json").open(encoding="utf-8") as h:
        summary = json.load(h)
        assert summary["combined_pra"]["detection"]["f1"] == 0.75
        assert summary["combined_pra"]["strict"]["precision"] == 0.50
        assert summary["stats"]["pts"]["detection"]["precision"] == 1.0
        assert summary["stats"]["reb"]["strict"]["precision"] == 0.0
        assert summary["stats"]["ast"]["detection"]["precision"] is None
