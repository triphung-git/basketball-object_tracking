"""Shared production evaluator for Task08 Shot Recognition & Points Engine.

Provides:
  1. Maximum cardinality one-to-one matching between predicted made shots and ground-truth events.
  2. Deterministic min-cost tie-breaking (minimizing release + basket time deltas, then stable IDs).
  3. Ground-truth isolation: recognition predictions are evaluated without leaking GT into runtime.
  4. Explicit metric views: detection-only, team-attribution, strict-player, point-value, and strict all-correct.
  5. Mathematical handling of edge cases (zero denominators return None/NA with reason codes).
  6. Shared across runners, CLI, and test suites.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import math
from typing import Any, Dict, List, Optional, Set, Tuple

from basketball_scoreboard.points import AttributionLevel, PointEventRecord
from basketball_scoreboard.shots import ShotCandidateRecord


@dataclass(frozen=True)
class EvaluationProtocolConfig:
    """Protocol thresholds and configuration for Task08 evaluation."""
    release_tolerance_s: float = 0.50
    basket_tolerance_s: float = 0.50
    protocol_version: str = "task08-production-evaluator-v1"
    require_both_release_and_basket_within_tolerance: bool = True
    greedy_trap_resolution: str = "maximum_cardinality_min_cost"


@dataclass
class GroundTruthPlay:
    """Standardized representation of a ground truth scoring play."""
    event_id: str
    release_s: float
    basket_s: float
    shooter_id: Optional[str] = None
    team_id: Optional[str] = None
    point_value: Optional[int] = None
    shot_kind: Optional[str] = None
    source_frame_release: Optional[int] = None
    source_frame_basket: Optional[int] = None

    @classmethod
    def from_review_meta(cls, event_id: str, meta: Dict[str, Any]) -> Optional[GroundTruthPlay]:
        """Extract GT play from adjudicated review dictionary."""
        # Check if times are available
        times = meta.get("times") or meta.get("evaluation_times") or {}
        rel_obj = times.get("release") or {}
        bsk_obj = times.get("basket") or {}

        rel_s = rel_obj.get("source_s") if isinstance(rel_obj, dict) else None
        bsk_s = bsk_obj.get("source_s") if isinstance(bsk_obj, dict) else None

        if rel_s is None and "release_s" in meta:
            rel_s = meta["release_s"]
        if bsk_s is None and "basket_s" in meta:
            bsk_s = meta["basket_s"]

        if rel_s is None or bsk_s is None:
            return None

        rev = meta.get("review") or {}
        target = meta.get("target") or {}

        shooter_id = rev.get("shooter_id") or meta.get("reviewed_shooter_id") or meta.get("shooter_id")
        team_id = (
            target.get("scoring_team_proposed_from_scoreboard")
            or meta.get("scoring_team_proposed_from_scoreboard")
            or meta.get("team_id")
        )
        val = (
            meta.get("point_value")
            or target.get("point_value")
            or target.get("points_proposed_from_scoreboard")
        )

        return cls(
            event_id=event_id,
            release_s=float(rel_s),
            basket_s=float(bsk_s),
            shooter_id=shooter_id,
            team_id=team_id,
            point_value=int(val) if val is not None else None,
            shot_kind=meta.get("shot_kind") or target.get("shot_kind"),
            source_frame_release=rel_obj.get("source_frame_index") if isinstance(rel_obj, dict) else None,
            source_frame_basket=bsk_obj.get("source_frame_index") if isinstance(bsk_obj, dict) else None,
        )


@dataclass
class EventMatch:
    """One-to-one matched pair between a predicted made shot and a GT play."""
    pred_shot_id: str
    gt_event_id: str
    pred_release_s: float
    pred_basket_s: float
    gt_release_s: float
    gt_basket_s: float
    release_delta_s: float
    basket_delta_s: float
    total_delta_s: float
    pred_team_id: Optional[str]
    gt_team_id: Optional[str]
    team_match: bool
    pred_player_id: Optional[str]
    gt_player_id: Optional[str]
    strict_player_match: bool
    pred_point_value: Optional[int]
    gt_point_value: Optional[int]
    value_match: bool
    matched_point_event_id: Optional[str]

    @property
    def is_strict_all_correct(self) -> bool:
        return self.team_match and self.strict_player_match and self.value_match

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def solve_max_cardinality_min_cost_matching(
    pred_shots: List[ShotCandidateRecord],
    gt_plays: List[GroundTruthPlay],
    protocol: EvaluationProtocolConfig,
) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
    """Solve maximum cardinality bipartite matching with deterministic min-cost tie breaking.

    Returns:
      matched_indices: List of (pred_idx, gt_idx) pairs.
      unmatched_pred_indices: List of pred_idx with no match.
      unmatched_gt_indices: List of gt_idx with no match.
    """
    m = len(pred_shots)
    n = len(gt_plays)
    if m == 0 or n == 0:
        return [], list(range(m)), list(range(n))

    # Build valid edges
    valid_edges: Dict[int, List[int]] = {i: [] for i in range(m)}
    cost_matrix: Dict[Tuple[int, int], float] = {}

    for i, p in enumerate(pred_shots):
        p_rel = p.release_time_s
        p_bsk = p.outcome_time_s
        if p_rel is None or p_bsk is None:
            continue

        for j, g in enumerate(gt_plays):
            rel_err = abs(p_rel - g.release_s)
            bsk_err = abs(p_bsk - g.basket_s)
            if rel_err <= protocol.release_tolerance_s and bsk_err <= protocol.basket_tolerance_s:
                valid_edges[i].append(j)
                cost_matrix[(i, j)] = round(rel_err + bsk_err, 5)

    # Sort edges deterministically by cost, then by GT event ID
    for i in range(m):
        valid_edges[i].sort(key=lambda j: (cost_matrix[(i, j)], gt_plays[j].event_id))

    # Min-Cost Max-Flow via Successive Shortest Path on Bipartite Network:
    # Nodes:
    #   Source = 0
    #   P_i = 1 .. m
    #   G_j = m + 1 .. m + n
    #   Sink = m + n + 1
    # Capacity 1 everywhere.
    source = 0
    sink = m + n + 1
    total_nodes = sink + 1

    # Graph representation for residual network
    # adj[u] = list of edge indices
    edges_u: List[int] = []
    edges_v: List[int] = []
    edges_cap: List[int] = []
    edges_flow: List[int] = []
    edges_cost: List[float] = []
    edges_orig: List[Tuple[int, int]] = []  # (p_idx, g_idx) or (-1, -1)
    head: List[List[int]] = [[] for _ in range(total_nodes)]

    def add_edge(u: int, v: int, cap: int, cost: float, orig: Tuple[int, int] = (-1, -1)) -> None:
        idx = len(edges_u)
        edges_u.append(u)
        edges_v.append(v)
        edges_cap.append(cap)
        edges_flow.append(0)
        edges_cost.append(cost)
        edges_orig.append(orig)
        head[u].append(idx)

        # Reverse residual edge
        edges_u.append(v)
        edges_v.append(u)
        edges_cap.append(0)
        edges_flow.append(0)
        edges_cost.append(-cost)
        edges_orig.append((-1, -1))
        head[v].append(idx + 1)

    for i in range(m):
        add_edge(source, 1 + i, 1, 0.0)

    for j in range(n):
        add_edge(m + 1 + j, sink, 1, 0.0)

    for i in range(m):
        for j in valid_edges[i]:
            c = cost_matrix[(i, j)]
            add_edge(1 + i, m + 1 + j, 1, c, orig=(i, j))

    # Augment paths using SPFA / Bellman-Ford
    matched_pairs: List[Tuple[int, int]] = []

    while True:
        dist = [float("inf")] * total_nodes
        parent_edge = [-1] * total_nodes
        in_queue = [False] * total_nodes
        dist[source] = 0.0
        queue = [source]
        in_queue[source] = True

        while queue:
            u = queue.pop(0)
            in_queue[u] = False

            for e_idx in head[u]:
                if edges_cap[e_idx] - edges_flow[e_idx] > 0:
                    v = edges_v[e_idx]
                    cost = edges_cost[e_idx]
                    new_dist = dist[u] + cost
                    if new_dist < dist[v] - 1e-9:
                        dist[v] = new_dist
                        parent_edge[v] = e_idx
                        if not in_queue[v]:
                            queue.append(v)
                            in_queue[v] = True

        if dist[sink] == float("inf"):
            # No more augmenting paths: maximum cardinality reached!
            break

        # Augment 1 unit along shortest path
        curr = sink
        while curr != source:
            e_idx = parent_edge[curr]
            edges_flow[e_idx] += 1
            edges_flow[e_idx ^ 1] -= 1
            curr = edges_u[e_idx]

    # Collect matched pairs
    matched_pred: Set[int] = set()
    matched_gt: Set[int] = set()

    for e_idx in range(len(edges_u)):
        if edges_orig[e_idx] != (-1, -1) and edges_flow[e_idx] == 1:
            p_i, g_j = edges_orig[e_idx]
            matched_pairs.append((p_i, g_j))
            matched_pred.add(p_i)
            matched_gt.add(g_j)

    # Sort matches deterministically
    matched_pairs.sort(key=lambda pair: (pred_shots[pair[0]].shot_id, gt_plays[pair[1]].event_id))
    unmatched_preds = [i for i in range(m) if i not in matched_pred]
    unmatched_gts = [j for j in range(n) if j not in matched_gt]

    return matched_pairs, unmatched_preds, unmatched_gts


class ShotEvaluator:
    """Production evaluator implementing Task08 protocol with maximum-cardinality matching."""

    def __init__(self, protocol: Optional[EvaluationProtocolConfig] = None):
        self.protocol = protocol or EvaluationProtocolConfig()

    def evaluate_positive_plays(
        self,
        predicted_shots: List[ShotCandidateRecord],
        predicted_points: List[PointEventRecord],
        gt_plays: List[Any],
        gt_events: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """Evaluate predicted shots and points against ground-truth plays."""
        # Support gt_events keyword argument for compatibility
        raw_gt = gt_events if gt_events is not None else gt_plays

        standardized_gt: List[GroundTruthPlay] = []
        for idx, g in enumerate(raw_gt):
            if isinstance(g, GroundTruthPlay):
                standardized_gt.append(g)
            elif isinstance(g, dict):
                play = GroundTruthPlay.from_review_meta(g.get("event_id") or f"gt_{idx:03d}", g)
                if play is not None:
                    standardized_gt.append(play)
                else:
                    standardized_gt.append(
                        GroundTruthPlay(
                            event_id=g.get("event_id") or f"gt_{idx:03d}",
                            release_s=float(g.get("release_s", 0.0)),
                            basket_s=float(g.get("basket_s", 0.0)),
                            shooter_id=g.get("shooter_id"),
                            team_id=g.get("team_id"),
                            point_value=g.get("point_value"),
                            shot_kind=g.get("shot_kind"),
                        )
                    )

        # 1. Filter made shots only (only made basket predictions can match scoring plays)
        made_shots = [s for s in predicted_shots if s.outcome == "made"]

        # 2. Maximum cardinality min-cost matching
        matched_indices, unmatched_pred_indices, unmatched_gt_indices = solve_max_cardinality_min_cost_matching(
            made_shots, standardized_gt, self.protocol
        )

        matched_pairs: List[EventMatch] = []
        tp_event = len(matched_indices)
        fp_event = len(unmatched_pred_indices)
        fn_event = len(unmatched_gt_indices)

        tp_team = 0
        tp_strict_player = 0
        tp_value = 0
        tp_strict_all = 0

        for p_idx, g_idx in matched_indices:
            pred = made_shots[p_idx]
            gt = standardized_gt[g_idx]

            # Find corresponding PointEventRecord
            pt_ev = next((p for p in predicted_points if p.shot_id == pred.shot_id), None)
            pred_team = pt_ev.scoring_team_id if pt_ev else pred.shooter_team_id
            pred_player = pt_ev.scoring_player_id if pt_ev else pred.shooter_player_id
            attr_lvl = pt_ev.attribution_level if pt_ev else pred.attribution_level
            pred_val = pt_ev.point_value if pt_ev else pred.point_value

            team_match = bool(pred_team and gt.team_id and pred_team == gt.team_id)
            player_match = bool(
                attr_lvl == AttributionLevel.PLAYER
                and pred_player
                and gt.shooter_id
                and pred_player == gt.shooter_id
            )
            value_match = bool(pred_val is not None and gt.point_value is not None and pred_val == gt.point_value)

            if team_match:
                tp_team += 1
            if player_match:
                tp_strict_player += 1
            if value_match:
                tp_value += 1
            if team_match and player_match and value_match:
                tp_strict_all += 1

            rel_delta = round(abs((pred.release_time_s or 0.0) - gt.release_s), 4)
            bsk_delta = round(abs((pred.outcome_time_s or 0.0) - gt.basket_s), 4)

            matched_pairs.append(
                EventMatch(
                    pred_shot_id=pred.shot_id,
                    gt_event_id=gt.event_id,
                    pred_release_s=pred.release_time_s or 0.0,
                    pred_basket_s=pred.outcome_time_s or 0.0,
                    gt_release_s=gt.release_s,
                    gt_basket_s=gt.basket_s,
                    release_delta_s=rel_delta,
                    basket_delta_s=bsk_delta,
                    total_delta_s=round(rel_delta + bsk_delta, 4),
                    pred_team_id=pred_team,
                    gt_team_id=gt.team_id,
                    team_match=team_match,
                    pred_player_id=pred_player,
                    gt_player_id=gt.shooter_id,
                    strict_player_match=player_match,
                    pred_point_value=pred_val,
                    gt_point_value=gt.point_value,
                    value_match=value_match,
                    matched_point_event_id=pt_ev.event_id if pt_ev else None,
                )
            )

        n_gt = len(gt_plays)
        n_pred = len(made_shots)

        recall_event = round(tp_event / n_gt, 4) if n_gt > 0 else None
        precision_event = round(tp_event / (tp_event + fp_event), 4) if (tp_event + fp_event) > 0 else None
        f1_event = (
            round(2 * precision_event * recall_event / (precision_event + recall_event), 4)
            if precision_event and recall_event and (precision_event + recall_event) > 0
            else None
        )

        strict_player_acc = round(tp_strict_player / tp_event, 4) if tp_event > 0 else None
        team_acc = round(tp_team / tp_event, 4) if tp_event > 0 else None
        value_acc = round(tp_value / tp_event, 4) if tp_event > 0 else None
        strict_all_acc = round(tp_strict_all / tp_event, 4) if tp_event > 0 else None

        return {
            "protocol_version": self.protocol.protocol_version,
            "n_gt": n_gt,
            "n_pred_made": n_pred,
            "tp_event": tp_event,
            "fp_event": fp_event,
            "fn_event": fn_event,
            "recall_event": recall_event,
            "precision_event": precision_event,
            "f1_event": f1_event,
            "tp_team": tp_team,
            "tp_strict_player": tp_strict_player,
            "tp_value": tp_value,
            "tp_strict_all": tp_strict_all,
            "team_accuracy": team_acc,
            "strict_player_accuracy": strict_player_acc,
            "value_accuracy": value_acc,
            "strict_all_accuracy": strict_all_acc,
            "matched_pairs": [m.to_dict() for m in matched_pairs],
            "unmatched_predictions": [made_shots[i].shot_id for i in unmatched_pred_indices],
            "unmatched_gt": [standardized_gt[j].event_id for j in unmatched_gt_indices],
        }

    def evaluate_negative_cohort(
        self,
        cohort_predictions: List[Dict[str, Any]],
        manifest_status: str = "reviewed",
    ) -> Dict[str, Any]:
        """Evaluate false positive rate and specificity across negative events.

        Strictly distinguishes official reviewed specificity from draft diagnostics.
        """
        n_neg = len(cohort_predictions)
        if n_neg == 0:
            return {
                "n_neg": 0,
                "false_positives": 0,
                "true_negatives": 0,
                "specificity": None,
                "official_specificity": None,
                "draft_specificity": None,
                "review_status": manifest_status,
                "reason": "empty_negative_cohort",
            }

        fp_count = sum(
            1 for c in cohort_predictions
            if c.get("predicted_made_baskets", 0) > 0
            or c.get("points_awarded", 0) > 0
            or c.get("false_positive", False)
        )
        tn_count = n_neg - fp_count
        raw_specificity = round(tn_count / n_neg, 4)

        is_draft = (manifest_status == "draft_unreviewed") or any(
            c.get("status") == "draft_unreviewed" for c in cohort_predictions
        )

        official_spec = None if is_draft else raw_specificity
        draft_spec = raw_specificity if is_draft else None

        return {
            "n_neg": n_neg,
            "false_positives": fp_count,
            "true_negatives": tn_count,
            "specificity": raw_specificity,
            "official_specificity": official_spec,
            "draft_specificity": draft_spec,
            "review_status": "draft_unreviewed" if is_draft else "reviewed",
            "false_positive_rate": round(fp_count / n_neg, 4),
            "official_status_note": (
                "Official specificity is N/A because cohort status is draft_unreviewed; pending authorized independent review."
                if is_draft
                else "Official specificity calculated on reviewed cohort."
            ),
        }


def evaluate_positive_window(
    window_id: str,
    shots: List[ShotCandidateRecord],
    points: List[PointEventRecord],
    review_meta: Dict[str, Any],
    protocol: Optional[EvaluationProtocolConfig] = None,
) -> Dict[str, Any]:
    """Compatibility and single-window evaluation function calling the shared production evaluator."""
    evaluator = ShotEvaluator(protocol=protocol)
    gt_play = GroundTruthPlay.from_review_meta(window_id, review_meta)
    gt_list = [gt_play] if gt_play is not None else []

    eval_summary = evaluator.evaluate_positive_plays(
        predicted_shots=shots,
        predicted_points=points,
        gt_plays=gt_list,
    )

    # Extract single window fields
    matched = eval_summary["matched_pairs"][0] if eval_summary["matched_pairs"] else None
    made_shots = [s for s in shots if s.outcome == "made"]

    rel_s = gt_play.release_s if gt_play else None
    bsk_s = gt_play.basket_s if gt_play else None
    gt_shooter = gt_play.shooter_id if gt_play else None
    gt_team = gt_play.team_id if gt_play else None
    gt_val = gt_play.point_value if gt_play else None

    best_shot = made_shots[0] if made_shots else (shots[0] if shots else None)
    score_ev = points[0] if points else None

    # Timing errors
    if matched:
        rel_err = matched["release_delta_s"]
        bsk_err = matched["basket_delta_s"]
        pred_team = matched["pred_team_id"]
        pred_player = matched["pred_player_id"]
        team_match = matched["team_match"]
        player_match = matched["strict_player_match"]
        points_val = matched["pred_point_value"]
    else:
        rel_err = (
            round(abs(best_shot.release_time_s - rel_s), 4)
            if (best_shot and best_shot.release_time_s is not None and rel_s is not None)
            else None
        )
        bsk_err = (
            round(abs(best_shot.outcome_time_s - bsk_s), 4)
            if (best_shot and best_shot.outcome_time_s is not None and bsk_s is not None)
            else None
        )
        pred_team = score_ev.scoring_team_id if score_ev else (best_shot.shooter_team_id if best_shot else None)
        pred_player = score_ev.scoring_player_id if score_ev else (best_shot.shooter_player_id if best_shot else None)
        team_match = False
        player_match = False
        points_val = score_ev.point_value if score_ev else (best_shot.point_value if best_shot else None)

    attr_level = (
        score_ev.attribution_level.value
        if score_ev
        else (best_shot.attribution_level.value if best_shot else "none")
    )
    points_status = score_ev.status if score_ev else "none"

    return {
        "window_id": window_id,
        "gt_release_s": rel_s,
        "gt_basket_s": bsk_s,
        "gt_shooter_id": gt_shooter,
        "gt_team_id": gt_team,
        "gt_point_value": gt_val,
        "shot_detected": len(shots) > 0,
        "basket_confirmed": eval_summary["tp_event"] > 0,
        "release_timing_error_s": rel_err,
        "basket_timing_error_s": bsk_err,
        "predicted_team_id": pred_team,
        "predicted_player_id": pred_player,
        "attribution_level": attr_level,
        "team_match": team_match,
        "strict_player_match": player_match,
        "points_awarded": points_val,
        "points_status": points_status,
        "shots_count": len(shots),
        "score_events_count": len(points),
        "tp_event": eval_summary["tp_event"],
        "fp_event": eval_summary["fp_event"],
        "fn_event": eval_summary["fn_event"],
        "matched_pairs": eval_summary["matched_pairs"],
        "unmatched_predictions": eval_summary["unmatched_predictions"],
        "unmatched_gt": eval_summary["unmatched_gt"],
    }


# Backward-compatibility alias
EvaluatorMetrics = ShotEvaluator

