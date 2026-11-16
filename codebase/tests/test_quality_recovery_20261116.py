"""Independent cases for user-authorized timing revision and source scope."""
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from basketball_scoreboard.evaluation_scope import normalize_scope, validate_prediction_binding
from basketball_scoreboard.evaluator_v2 import EvaluatorV2Protocol, ProductionEvaluatorV2, load_ground_truth


def shot(time=10.0, basket=11.0, **kwargs):
    return dict(shot_id="s", release_time_s=time, outcome_time_s=basket,
                outcome="made", team_id="A", shooter_id="a1", player_id="a1", point_value=1, **kwargs)


def test_basket_primary_revision_does_not_change_default_or_strict_attribution():
    pred, gt = shot(time=9.4333), shot()
    original = ProductionEvaluatorV2().evaluate_pts([pred], [gt])
    assert original["detection"]["tp"] == 0
    revised = ProductionEvaluatorV2(EvaluatorV2Protocol(require_both_release_and_basket=False))
    result = revised.evaluate_pts([pred], [gt])
    assert result["detection"]["tp"] == result["strict"]["tp"] == 1
    assert result["matched_pairs"][0]["release_delta_s"] == 0.5667
    wrong_actor = {**pred, "player_id": "a2"}
    assert revised.evaluate_pts([wrong_actor], [gt])["strict"]["tp"] == 0


def test_basket_primary_still_rejects_outside_basket_window_and_duplicates():
    evaluator = ProductionEvaluatorV2(EvaluatorV2Protocol(require_both_release_and_basket=False))
    assert evaluator.evaluate_pts([shot(basket=11.501)], [shot()])["detection"]["tp"] == 0
    result = evaluator.evaluate_pts([shot(), shot()], [shot()])
    assert result["detection"]["tp"] == 1
    assert result["detection"]["fp"] == 1


@pytest.mark.parametrize("tolerance", [-1, float("nan"), float("inf")])
def test_invalid_protocol_rejected(tolerance):
    with pytest.raises(ValueError):
        EvaluatorV2Protocol(shot_basket_tolerance_s=tolerance)


@pytest.mark.parametrize("stat,time_key", [("pts", "outcome_time_s"), ("reb", "rebound_time_s"), ("ast", "assist_time_s")])
def test_records_cannot_match_another_video(stat, time_key):
    evaluator = ProductionEvaluatorV2()
    pred = {**shot(video_id="one"), time_key: 11.0}
    gt = {**shot(video_id="two"), time_key: 11.0}
    result = getattr(evaluator, f"evaluate_{stat}")([pred], [gt])
    assert result["detection"]["tp"] == 0


def scope():
    return {"video_id": "parent", "source_sha256": "hash", "start_time_s": 300,
            "end_time_s": 330, "video_mappings": {"child": {"parent_video_id": "parent", "offset_s": 300}}}


def test_clip_offsets_immutable_scope_and_outside_gt_audit():
    data = {"pts": [shot(time=9, basket=10, video_id="child"), shot(time=50, basket=51, video_id="parent")]}
    before = copy.deepcopy(data)
    normalized, audit = normalize_scope(data, scope())
    assert data == before
    assert len(normalized["pts"]) == 1
    assert normalized["pts"][0]["release_time_s"] == 309
    assert normalized["pts"][0]["outcome_time_s"] == 310
    assert normalized["pts"][0]["video_id"] == "parent"
    assert audit["outside_interval"] == 1


def test_final_event_995_3_needs_more_than_995_seconds():
    short = {**scope(), "start_time_s": 0, "end_time_s": 995}
    data = {"pts": [shot(time=994.03, basket=995.3, video_id="parent")]}
    assert normalize_scope(data, short)[1]["outside_interval"] == 1
    assert normalize_scope(data, {**short, "end_time_s": 1000})[1]["included"] == 1


def test_short_prediction_run_cannot_claim_full_match_evaluation():
    full = {**scope(), "start_time_s": 0, "end_time_s": 1000}
    run = {"source_fingerprint_sha256": "hash", "source_coverage": {"first_time_s": 0, "last_time_s": 29.9667}}
    with pytest.raises(ValueError, match="shorter"):
        validate_prediction_binding(run, full)
    with pytest.raises(ValueError, match="source hash"):
        validate_prediction_binding({**run, "source_fingerprint_sha256": "other"}, full)


def test_canonical_point_values_use_explicit_rules_without_modifying_csv(tmp_path):
    annotations = tmp_path / "annotations"
    annotations.mkdir()
    csv_text = "shot_id,shot_type,result\ns,1pt,made\nt,free_throw,made\nu,unknown,made\n"
    (annotations / "shots.csv").write_text(csv_text)
    (tmp_path / "ruleset.json").write_text(json.dumps({"point_values": {"inside_arc": 1, "free_throw": 1}}))
    data, _ = load_ground_truth(tmp_path)
    assert data["pts"][0]["point_value"] == data["pts"][1]["point_value"] == 1
    assert "point_value" not in data["pts"][2]
    assert (annotations / "shots.csv").read_text() == csv_text


def test_cli_rejects_missing_requested_protocol(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts/evaluate_v2.py"
    proc = subprocess.run([sys.executable, str(script), "--predictions", str(tmp_path),
                           "--ground-truth", str(tmp_path), "--protocol-config", str(tmp_path / "missing.json")],
                          capture_output=True, text=True)
    assert proc.returncode == 1
    assert "Error loading protocol config" in proc.stderr
