"""Tests for Task08 Shared Production Evaluator integrity and validation rules.

Verifies:
1. Injected false positive: a broken/biased fixture engine that emits false scores
   on negative events causes the evaluator's FP count to increase and specificity/precision to degrade.
2. Zero predicted positives does NOT report 100% precision; precision must be N/A (None).
3. 0 predictions with low recall is reported as failed coverage, not high quality.
4. One-to-one matching tolerances on temporal release/basket timestamps.
5. Strict player vs team fallback vs unresolved point values are evaluated independently.
6. Maximum cardinality bipartite matching resolves the greedy trap.
7. Exact boundary conditions for release and basket tolerances (<= 0.50s match, > 0.50s reject).
8. Duplicate predictions for the same ground truth play are counted as FP.
9. Determinism under input permutation.
10. Official specificity is None (N/A) when cohort is draft_unreviewed.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional
import pytest

from basketball_scoreboard.identity import RosterConfig, RosterPlayer
from basketball_scoreboard.points import (
    AttributionLevel,
    PointEventRecord,
    PointValueReason,
)
from basketball_scoreboard.shot_evaluator import (
    EvaluationProtocolConfig,
    EvaluatorMetrics,
    EventMatch,
    GroundTruthPlay,
    ShotEvaluator,
    evaluate_positive_window,
)
from basketball_scoreboard.shots import (
    ShotCandidateRecord,
    ShotEngineConfig,
    ShotPhase,
)


@pytest.fixture
def eval_roster() -> RosterConfig:
    return RosterConfig(
        team_a_id="team_a",
        team_b_id="team_b",
        team_a_name="Vietnam",
        team_b_name="Tonga",
        team_a_color_rgb=(200, 30, 30),
        team_b_color_rgb=(230, 230, 230),
        players=[
            RosterPlayer(player_id="a_01", team_id="team_a", jersey_number="1", name="Phu Vinh"),
            RosterPlayer(player_id="b_01", team_id="team_b", jersey_number="1", name="Marcus Christian"),
        ],
    )


def test_injected_false_positive_fixture() -> None:
    """Test that an engine intentionally emitting false scores causes evaluator FP to increase."""
    evaluator = ShotEvaluator()

    # Normal clean predictions on 10 negative situations: 0 false positives
    clean_cohort = [
        {"negative_id": f"neg_{i:03d}", "category": "clean_miss", "predicted_made_baskets": 0, "points_awarded": 0, "status": "reviewed"}
        for i in range(10)
    ]
    res_clean = evaluator.evaluate_negative_cohort(clean_cohort, manifest_status="reviewed")
    assert res_clean["false_positives"] == 0
    assert res_clean["specificity"] == 1.0
    assert res_clean["official_specificity"] == 1.0

    # Biased/flawed engine that falsely predicts a made shot on neg_003 and neg_007
    broken_cohort = list(clean_cohort)
    broken_cohort[3] = {"negative_id": "neg_003", "category": "clean_miss", "predicted_made_baskets": 1, "points_awarded": 1, "status": "reviewed"}
    broken_cohort[7] = {"negative_id": "neg_007", "category": "clean_miss", "predicted_made_baskets": 1, "points_awarded": 1, "status": "reviewed"}

    res_broken = evaluator.evaluate_negative_cohort(broken_cohort, manifest_status="reviewed")
    assert res_broken["false_positives"] == 2
    assert res_broken["true_negatives"] == 8
    assert res_broken["specificity"] == 0.80
    assert res_broken["official_specificity"] == 0.80
    assert res_broken["false_positive_rate"] == 0.20


def test_zero_predictions_reports_none_precision_not_100() -> None:
    """When engine predicts 0 events, precision must be None (N/A), not 1.0."""
    evaluator = ShotEvaluator()
    gt = [
        {"release_s": 10.0, "basket_s": 11.2, "shooter_id": "a_01", "team_id": "team_a", "point_value": 1},
        {"release_s": 25.0, "basket_s": 26.1, "shooter_id": "b_01", "team_id": "team_b", "point_value": 2},
    ]

    # Engine predicts nothing
    metrics = evaluator.evaluate_positive_plays(
        predicted_shots=[],
        predicted_points=[],
        gt_plays=gt,
    )

    assert metrics["tp_event"] == 0
    assert metrics["fn_event"] == 2
    assert metrics["fp_event"] == 0
    assert metrics["recall_event"] == 0.0
    # Precision must be None / N/A, NEVER 100%!
    assert metrics["precision_event"] is None


def test_team_fallback_does_not_count_as_strict_player_tp() -> None:
    """Test that Team Attribution fallback increments team accuracy but NOT strict-player accuracy."""
    evaluator = ShotEvaluator()
    gt = [
        {"release_s": 10.0, "basket_s": 11.2, "shooter_id": "a_01", "team_id": "team_a", "point_value": 1},
    ]

    shot = ShotCandidateRecord(
        shot_id="shot_001",
        video_id="test",
        segment_id="test",
        camera_id="cam",
        status="auto_confirmed",
        outcome="made",
        phase=ShotPhase.BASKET,
        release_time_s=10.1,
        outcome_time_s=11.3,
        shooter_track_id="trk_01",
    )

    # Point event has team_a, but player_id is None (attribution_level = TEAM)
    pt = PointEventRecord(
        event_id="score_001",
        shot_id="shot_001",
        video_id="test",
        source_time_s=11.3,
        confirmation_time_s=11.3,
        status="auto_confirmed",
        scoring_team_id="team_a",
        scoring_player_id=None,
        attribution_level=AttributionLevel.TEAM,
        point_value=1,
        value_reason=PointValueReason.FIBA_3X3_1PT_INSIDE_ARC,
    )

    metrics = evaluator.evaluate_positive_plays([shot], [pt], gt)
    assert metrics["tp_event"] == 1
    assert metrics["tp_team"] == 1  # Team matched
    assert metrics["tp_strict_player"] == 0  # Strict player did NOT match!
    assert metrics["strict_player_accuracy"] == 0.0
    assert metrics["team_accuracy"] == 1.0


def test_unresolved_geometry_point_value_does_not_claim_value_tp() -> None:
    """Test that point_value=None (unresolved_geometry) does NOT match GT point value."""
    evaluator = ShotEvaluator()
    gt = [
        {"release_s": 10.0, "basket_s": 11.2, "shooter_id": "a_01", "team_id": "team_a", "point_value": 1},
    ]

    shot = ShotCandidateRecord(
        shot_id="shot_001",
        video_id="test",
        segment_id="test",
        camera_id="cam",
        status="auto_confirmed",
        outcome="made",
        phase=ShotPhase.BASKET,
        release_time_s=10.1,
        outcome_time_s=11.3,
        shooter_track_id="trk_01",
    )

    # Point event with unresolved geometry (point_value is None)
    pt = PointEventRecord(
        event_id="score_001",
        shot_id="shot_001",
        video_id="test",
        source_time_s=11.3,
        confirmation_time_s=11.3,
        status="unresolved_geometry",
        scoring_team_id="team_a",
        scoring_player_id="a_01",
        attribution_level=AttributionLevel.PLAYER,
        point_value=None,  # Unresolved geometry!
        value_reason=PointValueReason.UNRESOLVED_GEOMETRY,
    )

    metrics = evaluator.evaluate_positive_plays([shot], [pt], gt)
    assert metrics["tp_event"] == 1
    assert metrics["tp_strict_player"] == 1
    assert metrics["tp_value"] == 0  # Point value was unresolved, cannot claim value TP!
    assert metrics["value_accuracy"] == 0.0


def test_production_evaluator_rejects_out_of_tolerance() -> None:
    """Made shot outside release or basket tolerance must be rejected as FP."""
    evaluator = ShotEvaluator()
    shot = ShotCandidateRecord(
        shot_id="s_out",
        video_id="v",
        segment_id="seg",
        camera_id="cam",
        status="auto_confirmed",
        outcome="made",
        phase=ShotPhase.BASKET,
        release_time_s=1.0,
        outcome_time_s=2.0,
    )
    gt = [GroundTruthPlay(event_id="gt_1", release_s=10.0, basket_s=11.0)]

    res = evaluator.evaluate_positive_plays([shot], [], gt)
    assert res["tp_event"] == 0
    assert res["fp_event"] == 1
    assert res["fn_event"] == 1
    assert res["recall_event"] == 0.0
    assert res["precision_event"] == 0.0


def test_production_evaluator_exact_boundary() -> None:
    """Tests exact 0.50s boundary: <= 0.50s matches, > 0.50s rejects."""
    evaluator = ShotEvaluator(EvaluationProtocolConfig(release_tolerance_s=0.50, basket_tolerance_s=0.50))
    gt = [GroundTruthPlay(event_id="gt_bound", release_s=10.0, basket_s=11.0)]

    # Shot 1: exactly on the 0.50s boundary
    shot_match = ShotCandidateRecord(
        shot_id="s_bound_in",
        video_id="v",
        segment_id="seg",
        camera_id="cam",
        status="auto_confirmed",
        outcome="made",
        phase=ShotPhase.BASKET,
        release_time_s=10.50,
        outcome_time_s=11.50,
    )
    res_in = evaluator.evaluate_positive_plays([shot_match], [], gt)
    assert res_in["tp_event"] == 1
    assert res_in["fp_event"] == 0

    # Shot 2: 0.51s (just outside tolerance)
    shot_reject = ShotCandidateRecord(
        shot_id="s_bound_out",
        video_id="v",
        segment_id="seg",
        camera_id="cam",
        status="auto_confirmed",
        outcome="made",
        phase=ShotPhase.BASKET,
        release_time_s=10.51,
        outcome_time_s=11.50,
    )
    res_out = evaluator.evaluate_positive_plays([shot_reject], [], gt)
    assert res_out["tp_event"] == 0
    assert res_out["fp_event"] == 1


def test_production_evaluator_counts_duplicate_as_fp() -> None:
    """Multiple predictions for the same GT play must count 1 TP and remaining as FP."""
    evaluator = ShotEvaluator()
    gt = [GroundTruthPlay(event_id="gt_single", release_s=10.0, basket_s=11.0)]

    shot1 = ShotCandidateRecord(
        shot_id="s1",
        video_id="v",
        segment_id="seg",
        camera_id="cam",
        status="auto_confirmed",
        outcome="made",
        phase=ShotPhase.BASKET,
        release_time_s=10.05,
        outcome_time_s=11.05,
    )
    shot2 = ShotCandidateRecord(
        shot_id="s2",
        video_id="v",
        segment_id="seg",
        camera_id="cam",
        status="auto_confirmed",
        outcome="made",
        phase=ShotPhase.BASKET,
        release_time_s=10.15,
        outcome_time_s=11.15,
    )

    res = evaluator.evaluate_positive_plays([shot1, shot2], [], gt)
    assert res["tp_event"] == 1
    assert res["fp_event"] == 1
    assert res["fn_event"] == 0
    assert res["recall_event"] == 1.0
    assert res["precision_event"] == 0.5


def test_production_evaluator_greedy_trap_resolved_by_max_cardinality() -> None:
    """Fixture where greedy matching on GT order loses a match, but maximum cardinality matches both.

    Scenario:
      GT1: rel=10.0, bsk=11.0
      GT2: rel=10.3, bsk=11.3
      Pred A: rel=10.1, bsk=11.1 (diff to GT1: 0.2; diff to GT2: 0.4 - valid for both)
      Pred B: rel=9.6, bsk=10.6 (diff to GT1: 0.8 <= 0.5 each -> valid for GT1; diff to GT2: 1.4 > 0.5 -> INVALID for GT2)

    A greedy matcher taking the closest match for GT1 would match Pred A (cost 0.2 < 0.8),
    leaving Pred B for GT2 which is INVALID (diff > 0.5), resulting in only 1 match.
    Maximum cardinality matching correctly matches Pred B -> GT1 and Pred A -> GT2, giving 2 matches!
    """
    evaluator = ShotEvaluator(EvaluationProtocolConfig(release_tolerance_s=0.50, basket_tolerance_s=0.50))

    gt = [
        GroundTruthPlay(event_id="gt1", release_s=10.0, basket_s=11.0),
        GroundTruthPlay(event_id="gt2", release_s=10.3, basket_s=11.3),
    ]

    pred_a = ShotCandidateRecord(
        shot_id="pred_a",
        video_id="v",
        segment_id="seg",
        camera_id="cam",
        status="auto_confirmed",
        outcome="made",
        phase=ShotPhase.BASKET,
        release_time_s=10.1,
        outcome_time_s=11.1,
    )
    pred_b = ShotCandidateRecord(
        shot_id="pred_b",
        video_id="v",
        segment_id="seg",
        camera_id="cam",
        status="auto_confirmed",
        outcome="made",
        phase=ShotPhase.BASKET,
        release_time_s=9.6,
        outcome_time_s=10.6,
    )

    res = evaluator.evaluate_positive_plays([pred_a, pred_b], [], gt)
    assert res["tp_event"] == 2
    assert res["fp_event"] == 0
    assert res["fn_event"] == 0
    assert res["recall_event"] == 1.0
    assert res["precision_event"] == 1.0


def test_production_evaluator_deterministic_under_permutation() -> None:
    """Permuting the order of predictions or GT must yield identical matches and metrics."""
    evaluator = ShotEvaluator()

    gt = [
        GroundTruthPlay(event_id="gt_a", release_s=5.0, basket_s=6.0, team_id="team_a", shooter_id="a_01", point_value=1),
        GroundTruthPlay(event_id="gt_b", release_s=15.0, basket_s=16.0, team_id="team_b", shooter_id="b_01", point_value=2),
        GroundTruthPlay(event_id="gt_c", release_s=25.0, basket_s=26.0, team_id="team_a", shooter_id="a_01", point_value=2),
    ]

    shots = [
        ShotCandidateRecord(shot_id="s_a", video_id="v", segment_id="s", camera_id="c", status="auto_confirmed", outcome="made", phase=ShotPhase.BASKET, release_time_s=5.1, outcome_time_s=6.1, shooter_team_id="team_a", shooter_player_id="a_01", attribution_level=AttributionLevel.PLAYER, point_value=1),
        ShotCandidateRecord(shot_id="s_b", video_id="v", segment_id="s", camera_id="c", status="auto_confirmed", outcome="made", phase=ShotPhase.BASKET, release_time_s=15.2, outcome_time_s=16.2, shooter_team_id="team_b", shooter_player_id="b_01", attribution_level=AttributionLevel.PLAYER, point_value=2),
        ShotCandidateRecord(shot_id="s_c", video_id="v", segment_id="s", camera_id="c", status="auto_confirmed", outcome="made", phase=ShotPhase.BASKET, release_time_s=25.05, outcome_time_s=26.05, shooter_team_id="team_a", shooter_player_id="a_01", attribution_level=AttributionLevel.PLAYER, point_value=2),
    ]

    res_forward = evaluator.evaluate_positive_plays(shots, [], gt)

    # Reverse order of shots and GT
    res_reverse = evaluator.evaluate_positive_plays(list(reversed(shots)), [], list(reversed(gt)))

    assert res_forward["tp_event"] == res_reverse["tp_event"] == 3
    assert res_forward["fp_event"] == res_reverse["fp_event"] == 0
    assert res_forward["fn_event"] == res_reverse["fn_event"] == 0
    assert res_forward["matched_pairs"] == res_reverse["matched_pairs"]


def test_production_evaluator_empty_sets() -> None:
    """Empty predictions or empty GT must produce valid math with None where undefined."""
    evaluator = ShotEvaluator()

    # Empty GT with predictions -> all predictions are FP, recall is None
    res1 = evaluator.evaluate_positive_plays(
        predicted_shots=[ShotCandidateRecord(shot_id="s1", video_id="v", segment_id="s", camera_id="c", status="auto_confirmed", outcome="made", phase=ShotPhase.BASKET, release_time_s=1.0, outcome_time_s=2.0)],
        predicted_points=[],
        gt_plays=[],
    )
    assert res1["tp_event"] == 0
    assert res1["fp_event"] == 1
    assert res1["fn_event"] == 0
    assert res1["recall_event"] is None
    assert res1["precision_event"] == 0.0

    # GT with 0 predictions -> recall is 0, precision is None
    res2 = evaluator.evaluate_positive_plays(
        predicted_shots=[],
        predicted_points=[],
        gt_plays=[GroundTruthPlay(event_id="gt1", release_s=1.0, basket_s=2.0)],
    )
    assert res2["tp_event"] == 0
    assert res2["fp_event"] == 0
    assert res2["fn_event"] == 1
    assert res2["recall_event"] == 0.0
    assert res2["precision_event"] is None


def test_negative_cohort_draft_unreviewed_official_specificity_is_none() -> None:
    """When negative cohort status is draft_unreviewed, official_specificity must be None."""
    evaluator = ShotEvaluator()
    cohort = [
        {"negative_id": f"neg_{i}", "predicted_made_baskets": 0, "status": "draft_unreviewed"}
        for i in range(30)
    ]

    res = evaluator.evaluate_negative_cohort(cohort, manifest_status="draft_unreviewed")
    assert res["n_neg"] == 30
    assert res["false_positives"] == 0
    assert res["true_negatives"] == 30
    # Raw/draft diagnostic is 1.0 (0 FP)
    assert res["draft_specificity"] == 1.0
    # Official specificity MUST be None because cohort is unreviewed!
    assert res["official_specificity"] is None
    assert "draft_unreviewed" in res["official_status_note"]
