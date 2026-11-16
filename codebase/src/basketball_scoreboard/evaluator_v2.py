"""Shared production evaluator for PTS, REB, and AST (Task08/Task13/PRA protocol).

Provides:
  1. Maximum cardinality one-to-one matching with deterministic min-cost tie-breaking
     across all three core metrics:
       - PTS: release and basket timestamps, shooter, scoring team, point value.
       - REB: recovery timestamp, rebounder actor, team, subtype (offensive/defensive/team).
       - AST: pass release timestamp, passer, scorer, team, linked shot.
  2. Ground-truth isolation: predictions are immutable and evaluated without leaking GT.
  3. Strict vs Detection-only metrics:
       - Detection-only: event matched within time tolerance window.
       - Strict: event matched AND all attributions (actors, teams, values/subtypes, links) correct.
       - Any attribution mismatch produces a strict failure (strict FP + strict FN).
  4. Mathematical handling of edge cases (zero denominators return None/N/A with explicit reason codes).
  5. Comprehensive error indexing (error_index.json), match table (matched_events.csv, match_table.json),
     and summary reports (evaluation_summary.json).
  6. Shared across CLI (scripts/evaluate_v2.py), test suites, and pipelines.
"""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class EvaluatorV2Protocol:
    """Evaluation protocol tolerances and configuration."""
    protocol_version: str = "pra-production-evaluator-v2"
    shot_release_tolerance_s: float = 0.50
    shot_basket_tolerance_s: float = 0.50
    rebound_time_tolerance_s: float = 1.00
    assist_time_tolerance_s: float = 1.00
    require_both_release_and_basket: bool = True
    greedy_trap_resolution: str = "maximum_cardinality_min_cost"

    def __post_init__(self):
        for value in (self.shot_release_tolerance_s, self.shot_basket_tolerance_s,
                      self.rebound_time_tolerance_s, self.assist_time_tolerance_s):
            if not math.isfinite(value) or value < 0:
                raise ValueError("Evaluation tolerances must be finite and nonnegative")


def same_video(prediction: Dict[str, Any], truth: Dict[str, Any]) -> bool:
    """Explicit video identities must agree; callers normalize clip offsets first."""
    pred_video, gt_video = prediction.get("video_id"), truth.get("video_id")
    return not (pred_video and gt_video) or pred_video == gt_video


@dataclass
class MetricCount:
    """Precision / Recall / F1 metrics container with fail-safe zero-handling."""
    tp: int = 0
    fp: int = 0
    fn: int = 0
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1: Optional[float] = None
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def calculate_metric_rates(tp: int, fp: int, fn: int) -> MetricCount:
    """Calculate P, R, F1 with mathematical zero-denominator handling."""
    if (tp + fp) == 0 and (tp + fn) == 0:
        return MetricCount(tp=tp, fp=fp, fn=fn, precision=None, recall=None, f1=None, reason="no_events")
    
    precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else None
    recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else None
    
    f1 = None
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = round(2.0 * precision * recall / (precision + recall), 4)
    
    reason = None
    if precision is None and recall is None:
        reason = "no_events"
    elif precision is None:
        reason = "zero_predictions"
    elif recall is None:
        reason = "zero_gt_events"
    
    return MetricCount(
        tp=tp,
        fp=fp,
        fn=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        reason=reason,
    )


def solve_max_cardinality_min_cost_bipartite(
    n_preds: int,
    n_gts: int,
    candidate_edges: List[Tuple[int, int, float]],
    tie_break_keys: Optional[List[Tuple[str, str]]] = None,
) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
    """Solve maximum cardinality bipartite matching with deterministic minimum cost.

    Parameters:
      n_preds: Number of predicted items (0..n_preds-1).
      n_gts: Number of ground-truth items (0..n_gts-1).
      candidate_edges: List of (pred_idx, gt_idx, cost).
      tie_break_keys: Optional list of (pred_id, gt_id) per candidate edge for deterministic tie-breaking.

    Returns:
      matched_pairs: List of (pred_idx, gt_idx).
      unmatched_preds: List of pred_idx with no match.
      unmatched_gts: List of gt_idx with no match.
    """
    if n_preds == 0 or n_gts == 0 or not candidate_edges:
        return [], list(range(n_preds)), list(range(n_gts))

    # Build adjacency and cost mapping
    cost_matrix: Dict[Tuple[int, int], float] = {}
    valid_edges: Dict[int, List[int]] = {i: [] for i in range(n_preds)}

    for idx, (p_i, g_j, cost) in enumerate(candidate_edges):
        rounded_cost = round(cost, 5)
        cost_matrix[(p_i, g_j)] = rounded_cost
        valid_edges[p_i].append(g_j)

    # Sort edges deterministically: cost first, then gt_id / indices
    for p_i in range(n_preds):
        valid_edges[p_i].sort(key=lambda g_j: (cost_matrix[(p_i, g_j)], g_j))

    # Min-Cost Max-Flow via Successive Shortest Path (Bellman-Ford / SPFA)
    # Node indexing:
    #   Source = 0
    #   Pred_i = 1 .. n_preds
    #   GT_j   = n_preds + 1 .. n_preds + n_gts
    #   Sink   = n_preds + n_gts + 1
    source = 0
    sink = n_preds + n_gts + 1
    total_nodes = sink + 1

    edges_u: List[int] = []
    edges_v: List[int] = []
    edges_cap: List[int] = []
    edges_flow: List[int] = []
    edges_cost: List[float] = []
    edges_orig: List[Tuple[int, int]] = []
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

    for i in range(n_preds):
        add_edge(source, 1 + i, 1, 0.0)

    for j in range(n_gts):
        add_edge(n_preds + 1 + j, sink, 1, 0.0)

    for i in range(n_preds):
        for j in valid_edges[i]:
            c = cost_matrix[(i, j)]
            add_edge(1 + i, n_preds + 1 + j, 1, c, orig=(i, j))

    # Augment paths using SPFA
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
    matched_pairs: List[Tuple[int, int]] = []
    matched_pred: Set[int] = set()
    matched_gt: Set[int] = set()

    for e_idx in range(len(edges_u)):
        if edges_orig[e_idx] != (-1, -1) and edges_flow[e_idx] == 1:
            p_i, g_j = edges_orig[e_idx]
            matched_pairs.append((p_i, g_j))
            matched_pred.add(p_i)
            matched_gt.add(g_j)

    # Sort matches deterministically
    matched_pairs.sort(key=lambda pair: (pair[0], pair[1]))
    unmatched_preds = [i for i in range(n_preds) if i not in matched_pred]
    unmatched_gts = [j for j in range(n_gts) if j not in matched_gt]

    return matched_pairs, unmatched_preds, unmatched_gts


@dataclass
class ProductionEvaluatorV2:
    """Shared production evaluator for PTS, REB, and AST."""
    protocol: EvaluatorV2Protocol = field(default_factory=EvaluatorV2Protocol)

    def evaluate_pts(
        self,
        predicted_shots: List[Dict[str, Any]],
        gt_shots: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Evaluate PTS (scoring / made shot) predictions against ground truth."""
        # Filter: only made shots can produce points/score
        pred_made = []
        for s in predicted_shots:
            outcome = str(s.get("outcome") or s.get("result") or "").lower()
            ev = s.get("evidence") or {}
            ev_refs = ev.get("evidence_refs") or {}
            shot_ev = ev.get("shot_evidence") or ev_refs.get("shot_evidence") or {}
            is_made = (
                outcome == "made"
                or s.get("event_type") == "point"
                or ev.get("is_made") is True
                or shot_ev.get("is_made") is True
            )
            if is_made:
                pred_made.append(s)
        
        # Ground truth: only made shots (or scoring plays)
        valid_gt: List[Dict[str, Any]] = []
        for g in gt_shots:
            if g.get("uncertain") is True or g.get("status") == "excluded":
                continue
            res = str(g.get("result") or g.get("outcome") or "made").lower()
            if res in ("made", "confirmed_clear"):
                valid_gt.append(g)

        n_preds = len(pred_made)
        n_gts = len(valid_gt)

        # Candidate edges
        candidate_edges: List[Tuple[int, int, float]] = []
        for i, p in enumerate(pred_made):
            p_rel = p.get("release_time_s")
            p_bsk = p.get("outcome_time_s")
            if p_bsk is None:
                p_bsk = p.get("source_time_s")
            if p_bsk is None:
                p_bsk = p.get("basket_time_s")
            if p_rel is None and "source_time_s" in p:
                p_rel = p["source_time_s"]
            if p_bsk is None and p_rel is not None:
                p_bsk = p_rel

            if p_rel is None or p_bsk is None:
                continue

            for j, g in enumerate(valid_gt):
                if not same_video(p, g):
                    continue
                # Extract GT times
                g_rel = g.get("release_time_s")
                if g_rel is None:
                    g_rel = g.get("release_s")
                g_bsk = g.get("outcome_time_s")
                if g_bsk is None:
                    g_bsk = g.get("basket_s") or g.get("score_time_s")
                if g_rel is None and "times" in g:
                    g_rel = g["times"].get("release", {}).get("source_s")
                if g_bsk is None and "times" in g:
                    g_bsk = g["times"].get("basket", {}).get("source_s")

                if g_rel is None or g_bsk is None:
                    continue

                rel_err = abs(float(p_rel) - float(g_rel))
                bsk_err = abs(float(p_bsk) - float(g_bsk))

                if (bsk_err <= self.protocol.shot_basket_tolerance_s and
                        (not self.protocol.require_both_release_and_basket or
                         rel_err <= self.protocol.shot_release_tolerance_s)):
                    # Basket-primary is an explicit protocol revision, not a
                    # change to strict team/player/value attribution rules.
                    cost = (rel_err + bsk_err if self.protocol.require_both_release_and_basket
                            else bsk_err + 1e-6 * min(rel_err, 1000.0))
                    candidate_edges.append((i, j, cost))

        matched_pairs_idx, unmatched_pred_idx, unmatched_gt_idx = solve_max_cardinality_min_cost_bipartite(
            n_preds, n_gts, candidate_edges
        )

        matched_records: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        tp_team = 0
        tp_player = 0
        tp_value = 0
        tp_strict_all = 0

        for p_i, g_j in matched_pairs_idx:
            p = pred_made[p_i]
            g = valid_gt[g_j]

            p_id = p.get("shot_id") or p.get("event_id") or f"pred_pts_{p_i:03d}"
            g_id = g.get("shot_id") or g.get("event_id") or f"gt_pts_{g_j:03d}"

            p_rel = p.get("release_time_s") or p.get("source_time_s") or 0.0
            p_bsk = p.get("outcome_time_s") or p.get("source_time_s") or 0.0
            g_rel = g.get("release_time_s") or g.get("release_s") or (g.get("times", {}).get("release", {}).get("source_s", 0.0))
            g_bsk = g.get("outcome_time_s") or g.get("basket_s") or (g.get("times", {}).get("basket", {}).get("source_s", 0.0))

            p_team = p.get("shooter_team_id") or p.get("team_id") or p.get("scoring_team_id")
            g_team = g.get("team_id") or (g.get("target", {}).get("scoring_team_proposed_from_scoreboard"))

            p_shooter = p.get("shooter_player_id") or p.get("player_id") or p.get("scoring_player_id")
            g_shooter = g.get("shooter_id") or (g.get("review", {}).get("shooter_id"))

            p_val = p.get("point_value")
            g_val = g.get("point_value") or (g.get("target", {}).get("points_proposed_from_scoreboard"))
            if g_val is not None:
                try:
                    g_val = int(g_val)
                except (ValueError, TypeError):
                    pass
            if p_val is not None:
                try:
                    p_val = int(p_val)
                except (ValueError, TypeError):
                    pass

            team_match = bool(p_team and g_team and p_team == g_team)
            # Strict player match requires non-null, resolved player id
            player_match = bool(
                p_shooter and g_shooter and p_shooter not in ("", "unresolved", "null", None) and p_shooter == g_shooter
            )
            value_match = bool(p_val is not None and g_val is not None and p_val == g_val)
            strict_all = team_match and player_match and value_match

            if team_match:
                tp_team += 1
            else:
                errors.append({
                    "error_type": "attribution_error_team",
                    "stat": "pts",
                    "pred_id": p_id,
                    "gt_id": g_id,
                    "pred_value": p_team,
                    "gt_value": g_team,
                    "time_s": p_bsk,
                })

            if player_match:
                tp_player += 1
            else:
                errors.append({
                    "error_type": "attribution_error_player",
                    "stat": "pts",
                    "pred_id": p_id,
                    "gt_id": g_id,
                    "pred_value": p_shooter,
                    "gt_value": g_shooter,
                    "time_s": p_bsk,
                })

            if value_match:
                tp_value += 1
            else:
                errors.append({
                    "error_type": "attribution_error_value",
                    "stat": "pts",
                    "pred_id": p_id,
                    "gt_id": g_id,
                    "pred_value": p_val,
                    "gt_value": g_val,
                    "time_s": p_bsk,
                })

            if strict_all:
                tp_strict_all += 1

            matched_records.append({
                "stat": "pts",
                "pred_id": p_id,
                "gt_id": g_id,
                "pred_release_s": round(float(p_rel), 4),
                "pred_basket_s": round(float(p_bsk), 4),
                "gt_release_s": round(float(g_rel), 4),
                "gt_basket_s": round(float(g_bsk), 4),
                "release_delta_s": round(abs(float(p_rel) - float(g_rel)), 4),
                "basket_delta_s": round(abs(float(p_bsk) - float(g_bsk)), 4),
                "pred_team": p_team,
                "gt_team": g_team,
                "team_match": team_match,
                "pred_actor": p_shooter,
                "gt_actor": g_shooter,
                "actor_match": player_match,
                "pred_value": p_val,
                "gt_value": g_val,
                "value_match": value_match,
                "strict_all_match": strict_all,
            })

        unmatched_preds: List[Dict[str, Any]] = []
        for p_i in unmatched_pred_idx:
            p = pred_made[p_i]
            pid = p.get("shot_id") or p.get("event_id") or f"pred_pts_{p_i:03d}"
            unmatched_preds.append({
                "stat": "pts",
                "pred_id": pid,
                "time_s": p.get("outcome_time_s") or p.get("source_time_s"),
                "team_id": p.get("shooter_team_id") or p.get("team_id"),
                "player_id": p.get("shooter_player_id") or p.get("player_id"),
            })
            errors.append({
                "error_type": "unmatched_prediction",
                "stat": "pts",
                "pred_id": pid,
                "gt_id": None,
                "time_s": p.get("outcome_time_s") or p.get("source_time_s"),
                "details": "Predicted made shot has no matching ground-truth event within tolerance",
            })

        unmatched_gts: List[Dict[str, Any]] = []
        for g_j in unmatched_gt_idx:
            g = valid_gt[g_j]
            gid = g.get("shot_id") or g.get("event_id") or f"gt_pts_{g_j:03d}"
            g_bsk = g.get("outcome_time_s") or g.get("basket_s") or g.get("score_time_s") or (g.get("times", {}).get("basket", {}).get("source_s"))
            unmatched_gts.append({
                "stat": "pts",
                "gt_id": gid,
                "time_s": g_bsk,
                "team_id": g.get("team_id") or g.get("target", {}).get("scoring_team_proposed_from_scoreboard"),
                "player_id": g.get("shooter_id") or g.get("review", {}).get("shooter_id"),
            })
            errors.append({
                "error_type": "unmatched_ground_truth",
                "stat": "pts",
                "pred_id": None,
                "gt_id": gid,
                "time_s": g_bsk,
                "details": "Ground-truth made shot was not detected by recognition pipeline",
            })

        tp_event = len(matched_pairs_idx)
        fp_event = len(unmatched_preds)
        fn_event = len(unmatched_gts)

        # Strict: matched predictions with attribution failures count as strict FP and FN
        attr_errors_count = tp_event - tp_strict_all
        strict_tp = tp_strict_all
        strict_fp = fp_event + attr_errors_count
        strict_fn = fn_event + attr_errors_count

        detection_metrics = calculate_metric_rates(tp_event, fp_event, fn_event)
        strict_metrics = calculate_metric_rates(strict_tp, strict_fp, strict_fn)

        team_acc = round(tp_team / tp_event, 4) if tp_event > 0 else None
        player_acc = round(tp_player / tp_event, 4) if tp_event > 0 else None
        val_acc = round(tp_value / tp_event, 4) if tp_event > 0 else None
        strict_acc = round(tp_strict_all / tp_event, 4) if tp_event > 0 else None

        status = "evaluated" if (n_gts > 0 or n_preds > 0) else "no_events"
        if n_gts == 0 and n_preds > 0:
            status = "no_gt_events"
        elif n_preds == 0 and n_gts > 0:
            status = "no_predictions"

        return {
            "stat": "pts",
            "status": status,
            "n_gt": n_gts,
            "n_pred": n_preds,
            "detection": detection_metrics.to_dict(),
            "strict": strict_metrics.to_dict(),
            "attribution": {
                "tp_team": tp_team,
                "tp_actor": tp_player,
                "tp_value": tp_value,
                "tp_strict_all": tp_strict_all,
                "team_accuracy": team_acc,
                "player_accuracy": player_acc,
                "value_accuracy": val_acc,
                "strict_all_accuracy": strict_acc,
            },
            "matched_pairs": matched_records,
            "unmatched_predictions": unmatched_preds,
            "unmatched_gt": unmatched_gts,
            "errors": errors,
        }

    def evaluate_reb(
        self,
        predicted_rebounds: List[Dict[str, Any]],
        gt_rebounds: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Evaluate REB (rebound) predictions against ground truth."""
        valid_preds = [
            r for r in predicted_rebounds
            if r.get("event_type") in ("rebound", None)
            and not r.get("is_void")
        ]

        valid_gt: List[Dict[str, Any]] = []
        for g in gt_rebounds:
            if g.get("uncertain") is True or g.get("status") == "excluded":
                continue
            valid_gt.append(g)

        n_preds = len(valid_preds)
        n_gts = len(valid_gt)

        candidate_edges: List[Tuple[int, int, float]] = []
        for i, p in enumerate(valid_preds):
            p_time = p.get("rebound_time_s") or p.get("recovery_time_s") or p.get("source_time_s")
            if p_time is None:
                continue

            for j, g in enumerate(valid_gt):
                if not same_video(p, g):
                    continue
                g_time = g.get("rebound_time_s") or g.get("recovery_time_s") or g.get("time_s")
                if g_time is None:
                    continue

                delta = abs(float(p_time) - float(g_time))
                if delta <= self.protocol.rebound_time_tolerance_s:
                    candidate_edges.append((i, j, delta))

        matched_pairs_idx, unmatched_pred_idx, unmatched_gt_idx = solve_max_cardinality_min_cost_bipartite(
            n_preds, n_gts, candidate_edges
        )

        matched_records: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        tp_team = 0
        tp_rebounder = 0
        tp_subtype = 0
        tp_parent_shot = 0
        tp_strict_all = 0

        for p_i, g_j in matched_pairs_idx:
            p = valid_preds[p_i]
            g = valid_gt[g_j]

            p_id = p.get("rebound_id") or p.get("event_id") or f"pred_reb_{p_i:03d}"
            g_id = g.get("rebound_id") or g.get("event_id") or f"gt_reb_{g_j:03d}"

            p_time = float(p.get("rebound_time_s") or p.get("recovery_time_s") or p.get("source_time_s") or 0.0)
            g_time = float(g.get("rebound_time_s") or g.get("recovery_time_s") or g.get("time_s") or 0.0)

            p_team = p.get("team_id")
            g_team = g.get("team_id")

            p_actor = p.get("actor_id") or p.get("player_id") or p.get("rebounder_id")
            g_actor = g.get("actor_id") or g.get("player_id") or g.get("rebounder_id")

            p_type = str(p.get("rebound_type") or p.get("subtype") or "").lower()
            g_type = str(g.get("rebound_type") or g.get("subtype") or "").lower()

            p_shot = p.get("parent_event_id") or p.get("shot_id")
            g_shot = g.get("parent_event_id") or g.get("shot_id")

            team_match = bool(p_team and g_team and p_team == g_team)
            subtype_match = bool(p_type and g_type and p_type == g_type)

            if g_type == "team_rebound":
                actor_match = (p_type == "team_rebound" and team_match)
            else:
                actor_match = bool(
                    p_actor and g_actor and p_actor not in ("", "unresolved", "null", None) and p_actor == g_actor
                )

            parent_match = True
            if g_shot:
                parent_match = bool(p_shot and p_shot == g_shot)

            strict_all = team_match and subtype_match and actor_match and parent_match

            if team_match:
                tp_team += 1
            else:
                errors.append({
                    "error_type": "attribution_error_team",
                    "stat": "reb",
                    "pred_id": p_id,
                    "gt_id": g_id,
                    "pred_value": p_team,
                    "gt_value": g_team,
                    "time_s": p_time,
                })

            if subtype_match:
                tp_subtype += 1
            else:
                errors.append({
                    "error_type": "attribution_error_subtype",
                    "stat": "reb",
                    "pred_id": p_id,
                    "gt_id": g_id,
                    "pred_value": p_type,
                    "gt_value": g_type,
                    "time_s": p_time,
                })

            if actor_match:
                tp_rebounder += 1
            else:
                errors.append({
                    "error_type": "attribution_error_player",
                    "stat": "reb",
                    "pred_id": p_id,
                    "gt_id": g_id,
                    "pred_value": p_actor,
                    "gt_value": g_actor,
                    "time_s": p_time,
                })

            if parent_match:
                tp_parent_shot += 1
            else:
                errors.append({
                    "error_type": "attribution_error_parent_link",
                    "stat": "reb",
                    "pred_id": p_id,
                    "gt_id": g_id,
                    "pred_value": p_shot,
                    "gt_value": g_shot,
                    "time_s": p_time,
                })

            if strict_all:
                tp_strict_all += 1

            matched_records.append({
                "stat": "reb",
                "pred_id": p_id,
                "gt_id": g_id,
                "pred_time_s": round(p_time, 4),
                "gt_time_s": round(g_time, 4),
                "delta_s": round(abs(p_time - g_time), 4),
                "pred_team": p_team,
                "gt_team": g_team,
                "team_match": team_match,
                "pred_subtype": p_type,
                "gt_subtype": g_type,
                "subtype_match": subtype_match,
                "pred_actor": p_actor,
                "gt_actor": g_actor,
                "actor_match": actor_match,
                "pred_parent_shot": p_shot,
                "gt_parent_shot": g_shot,
                "parent_link_match": parent_match,
                "strict_all_match": strict_all,
            })

        unmatched_preds: List[Dict[str, Any]] = []
        for p_i in unmatched_pred_idx:
            p = valid_preds[p_i]
            pid = p.get("rebound_id") or p.get("event_id") or f"pred_reb_{p_i:03d}"
            t = p.get("rebound_time_s") or p.get("recovery_time_s") or p.get("source_time_s")
            unmatched_preds.append({
                "stat": "reb",
                "pred_id": pid,
                "time_s": t,
                "team_id": p.get("team_id"),
                "actor_id": p.get("actor_id") or p.get("player_id"),
            })
            errors.append({
                "error_type": "unmatched_prediction",
                "stat": "reb",
                "pred_id": pid,
                "gt_id": None,
                "time_s": t,
                "details": "Predicted rebound has no matching ground-truth rebound within tolerance",
            })

        unmatched_gts: List[Dict[str, Any]] = []
        for g_j in unmatched_gt_idx:
            g = valid_gt[g_j]
            gid = g.get("rebound_id") or g.get("event_id") or f"gt_reb_{g_j:03d}"
            t = g.get("rebound_time_s") or g.get("recovery_time_s") or g.get("time_s")
            unmatched_gts.append({
                "stat": "reb",
                "gt_id": gid,
                "time_s": t,
                "team_id": g.get("team_id"),
                "actor_id": g.get("actor_id") or g.get("player_id"),
            })
            errors.append({
                "error_type": "unmatched_ground_truth",
                "stat": "reb",
                "pred_id": None,
                "gt_id": gid,
                "time_s": t,
                "details": "Ground-truth rebound was not detected by recognition pipeline",
            })

        tp_event = len(matched_pairs_idx)
        fp_event = len(unmatched_preds)
        fn_event = len(unmatched_gts)

        attr_errors_count = tp_event - tp_strict_all
        strict_tp = tp_strict_all
        strict_fp = fp_event + attr_errors_count
        strict_fn = fn_event + attr_errors_count

        detection_metrics = calculate_metric_rates(tp_event, fp_event, fn_event)
        strict_metrics = calculate_metric_rates(strict_tp, strict_fp, strict_fn)

        team_acc = round(tp_team / tp_event, 4) if tp_event > 0 else None
        actor_acc = round(tp_rebounder / tp_event, 4) if tp_event > 0 else None
        subtype_acc = round(tp_subtype / tp_event, 4) if tp_event > 0 else None
        parent_acc = round(tp_parent_shot / tp_event, 4) if tp_event > 0 else None
        strict_acc = round(tp_strict_all / tp_event, 4) if tp_event > 0 else None

        status = "evaluated" if (n_gts > 0 or n_preds > 0) else "no_events"
        if n_gts == 0 and n_preds > 0:
            status = "no_gt_events"
        elif n_preds == 0 and n_gts > 0:
            status = "no_predictions"

        return {
            "stat": "reb",
            "status": status,
            "n_gt": n_gts,
            "n_pred": n_preds,
            "detection": detection_metrics.to_dict(),
            "strict": strict_metrics.to_dict(),
            "attribution": {
                "tp_team": tp_team,
                "tp_actor": tp_rebounder,
                "tp_subtype": tp_subtype,
                "tp_parent_shot": tp_parent_shot,
                "tp_strict_all": tp_strict_all,
                "team_accuracy": team_acc,
                "actor_accuracy": actor_acc,
                "subtype_accuracy": subtype_acc,
                "parent_shot_accuracy": parent_acc,
                "strict_all_accuracy": strict_acc,
            },
            "matched_pairs": matched_records,
            "unmatched_predictions": unmatched_preds,
            "unmatched_gt": unmatched_gts,
            "errors": errors,
        }

    def evaluate_ast(
        self,
        predicted_assists: List[Dict[str, Any]],
        gt_assists: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Evaluate AST (assist) predictions against ground truth."""
        valid_preds = [
            a for a in predicted_assists
            if a.get("event_type") in ("assist", None)
            and not a.get("is_void")
        ]

        # Only eligible ground truth assists are evaluated as positives
        valid_gt: List[Dict[str, Any]] = []
        for g in gt_assists:
            if g.get("uncertain") is True or g.get("status") == "excluded":
                continue
            elig = str(g.get("eligibility") or "eligible").lower()
            if elig == "eligible":
                valid_gt.append(g)

        n_preds = len(valid_preds)
        n_gts = len(valid_gt)

        candidate_edges: List[Tuple[int, int, float]] = []
        for i, p in enumerate(valid_preds):
            p_time = p.get("assist_time_s") or p.get("pass_release_time_s") or p.get("source_time_s")
            if p_time is None:
                continue

            for j, g in enumerate(valid_gt):
                if not same_video(p, g):
                    continue
                g_time = g.get("assist_time_s") or g.get("pass_release_time_s") or g.get("time_s")
                if g_time is None:
                    continue

                delta = abs(float(p_time) - float(g_time))
                if delta <= self.protocol.assist_time_tolerance_s:
                    candidate_edges.append((i, j, delta))

        matched_pairs_idx, unmatched_pred_idx, unmatched_gt_idx = solve_max_cardinality_min_cost_bipartite(
            n_preds, n_gts, candidate_edges
        )

        matched_records: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        tp_team = 0
        tp_passer = 0
        tp_scorer = 0
        tp_parent_shot = 0
        tp_strict_all = 0

        for p_i, g_j in matched_pairs_idx:
            p = valid_preds[p_i]
            g = valid_gt[g_j]

            p_id = p.get("assist_id") or p.get("event_id") or f"pred_ast_{p_i:03d}"
            g_id = g.get("assist_id") or g.get("event_id") or f"gt_ast_{g_j:03d}"

            p_time = float(p.get("assist_time_s") or p.get("pass_release_time_s") or p.get("source_time_s") or 0.0)
            g_time = float(g.get("assist_time_s") or g.get("pass_release_time_s") or g.get("time_s") or 0.0)

            p_team = p.get("team_id")
            g_team = g.get("team_id")

            p_passer = p.get("passer_id")
            g_passer = g.get("passer_id")

            p_scorer = p.get("scorer_id")
            g_scorer = g.get("scorer_id")

            p_shot = p.get("parent_event_id") or p.get("shot_id")
            g_shot = g.get("parent_event_id") or g.get("shot_id")

            team_match = bool(p_team and g_team and p_team == g_team)
            passer_match = bool(p_passer and g_passer and p_passer not in ("", "unresolved", "null", None) and p_passer == g_passer)
            scorer_match = bool(p_scorer and g_scorer and p_scorer not in ("", "unresolved", "null", None) and p_scorer == g_scorer)
            
            parent_match = True
            if g_shot:
                parent_match = bool(p_shot and p_shot == g_shot)

            strict_all = team_match and passer_match and scorer_match and parent_match

            if team_match:
                tp_team += 1
            else:
                errors.append({
                    "error_type": "attribution_error_team",
                    "stat": "ast",
                    "pred_id": p_id,
                    "gt_id": g_id,
                    "pred_value": p_team,
                    "gt_value": g_team,
                    "time_s": p_time,
                })

            if passer_match:
                tp_passer += 1
            else:
                errors.append({
                    "error_type": "attribution_error_passer",
                    "stat": "ast",
                    "pred_id": p_id,
                    "gt_id": g_id,
                    "pred_value": p_passer,
                    "gt_value": g_passer,
                    "time_s": p_time,
                })

            if scorer_match:
                tp_scorer += 1
            else:
                errors.append({
                    "error_type": "attribution_error_scorer",
                    "stat": "ast",
                    "pred_id": p_id,
                    "gt_id": g_id,
                    "pred_value": p_scorer,
                    "gt_value": g_scorer,
                    "time_s": p_time,
                })

            if parent_match:
                tp_parent_shot += 1
            else:
                errors.append({
                    "error_type": "attribution_error_parent_link",
                    "stat": "ast",
                    "pred_id": p_id,
                    "gt_id": g_id,
                    "pred_value": p_shot,
                    "gt_value": g_shot,
                    "time_s": p_time,
                })

            if strict_all:
                tp_strict_all += 1

            matched_records.append({
                "stat": "ast",
                "pred_id": p_id,
                "gt_id": g_id,
                "pred_time_s": round(p_time, 4),
                "gt_time_s": round(g_time, 4),
                "delta_s": round(abs(p_time - g_time), 4),
                "pred_team": p_team,
                "gt_team": g_team,
                "team_match": team_match,
                "pred_passer": p_passer,
                "gt_passer": g_passer,
                "passer_match": passer_match,
                "pred_scorer": p_scorer,
                "gt_scorer": g_scorer,
                "scorer_match": scorer_match,
                "pred_parent_shot": p_shot,
                "gt_parent_shot": g_shot,
                "parent_link_match": parent_match,
                "strict_all_match": strict_all,
            })

        unmatched_preds: List[Dict[str, Any]] = []
        for p_i in unmatched_pred_idx:
            p = valid_preds[p_i]
            pid = p.get("assist_id") or p.get("event_id") or f"pred_ast_{p_i:03d}"
            t = p.get("assist_time_s") or p.get("pass_release_time_s") or p.get("source_time_s")
            unmatched_preds.append({
                "stat": "ast",
                "pred_id": pid,
                "time_s": t,
                "team_id": p.get("team_id"),
                "passer_id": p.get("passer_id"),
                "scorer_id": p.get("scorer_id"),
            })
            errors.append({
                "error_type": "unmatched_prediction",
                "stat": "ast",
                "pred_id": pid,
                "gt_id": None,
                "time_s": t,
                "details": "Predicted assist has no matching ground-truth assist within tolerance",
            })

        unmatched_gts: List[Dict[str, Any]] = []
        for g_j in unmatched_gt_idx:
            g = valid_gt[g_j]
            gid = g.get("assist_id") or g.get("event_id") or f"gt_ast_{g_j:03d}"
            t = g.get("assist_time_s") or g.get("pass_release_time_s") or g.get("time_s")
            unmatched_gts.append({
                "stat": "ast",
                "gt_id": gid,
                "time_s": t,
                "team_id": g.get("team_id"),
                "passer_id": g.get("passer_id"),
                "scorer_id": g.get("scorer_id"),
            })
            errors.append({
                "error_type": "unmatched_ground_truth",
                "stat": "ast",
                "pred_id": None,
                "gt_id": gid,
                "time_s": t,
                "details": "Ground-truth eligible assist was not detected by recognition pipeline",
            })

        tp_event = len(matched_pairs_idx)
        fp_event = len(unmatched_preds)
        fn_event = len(unmatched_gts)

        attr_errors_count = tp_event - tp_strict_all
        strict_tp = tp_strict_all
        strict_fp = fp_event + attr_errors_count
        strict_fn = fn_event + attr_errors_count

        detection_metrics = calculate_metric_rates(tp_event, fp_event, fn_event)
        strict_metrics = calculate_metric_rates(strict_tp, strict_fp, strict_fn)

        team_acc = round(tp_team / tp_event, 4) if tp_event > 0 else None
        passer_acc = round(tp_passer / tp_event, 4) if tp_event > 0 else None
        scorer_acc = round(tp_scorer / tp_event, 4) if tp_event > 0 else None
        parent_acc = round(tp_parent_shot / tp_event, 4) if tp_event > 0 else None
        strict_acc = round(tp_strict_all / tp_event, 4) if tp_event > 0 else None

        status = "evaluated" if (n_gts > 0 or n_preds > 0) else "no_events"
        if n_gts == 0 and n_preds > 0:
            status = "no_gt_events"
        elif n_preds == 0 and n_gts > 0:
            status = "no_predictions"

        return {
            "stat": "ast",
            "status": status,
            "n_gt": n_gts,
            "n_pred": n_preds,
            "detection": detection_metrics.to_dict(),
            "strict": strict_metrics.to_dict(),
            "attribution": {
                "tp_team": tp_team,
                "tp_passer": tp_passer,
                "tp_scorer": tp_scorer,
                "tp_parent_shot": tp_parent_shot,
                "tp_strict_all": tp_strict_all,
                "team_accuracy": team_acc,
                "passer_accuracy": passer_acc,
                "scorer_accuracy": scorer_acc,
                "parent_shot_accuracy": parent_acc,
                "strict_all_accuracy": strict_acc,
            },
            "matched_pairs": matched_records,
            "unmatched_predictions": unmatched_preds,
            "unmatched_gt": unmatched_gts,
            "errors": errors,
        }

    def evaluate_all(
        self,
        predictions: Dict[str, List[Dict[str, Any]]],
        ground_truth: Dict[str, List[Dict[str, Any]]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Evaluate PTS, REB, and AST, and compile full PRA evaluation summary."""
        pts_res = self.evaluate_pts(
            predictions.get("pts", predictions.get("shots", [])),
            ground_truth.get("pts", ground_truth.get("shots", [])),
        )
        reb_res = self.evaluate_reb(
            predictions.get("reb", predictions.get("rebounds", [])),
            ground_truth.get("reb", ground_truth.get("rebounds", [])),
        )
        ast_res = self.evaluate_ast(
            predictions.get("ast", predictions.get("assists", [])),
            ground_truth.get("ast", ground_truth.get("assists", [])),
        )

        # Combined PRA totals
        combined_tp_det = pts_res["detection"]["tp"] + reb_res["detection"]["tp"] + ast_res["detection"]["tp"]
        combined_fp_det = pts_res["detection"]["fp"] + reb_res["detection"]["fp"] + ast_res["detection"]["fp"]
        combined_fn_det = pts_res["detection"]["fn"] + reb_res["detection"]["fn"] + ast_res["detection"]["fn"]

        combined_det = calculate_metric_rates(combined_tp_det, combined_fp_det, combined_fn_det)

        combined_tp_strict = pts_res["strict"]["tp"] + reb_res["strict"]["tp"] + ast_res["strict"]["tp"]
        combined_fp_strict = pts_res["strict"]["fp"] + reb_res["strict"]["fp"] + ast_res["strict"]["fp"]
        combined_fn_strict = pts_res["strict"]["fn"] + reb_res["strict"]["fn"] + ast_res["strict"]["fn"]

        combined_strict = calculate_metric_rates(combined_tp_strict, combined_fp_strict, combined_fn_strict)

        all_matched_pairs = pts_res["matched_pairs"] + reb_res["matched_pairs"] + ast_res["matched_pairs"]
        all_unmatched_preds = pts_res["unmatched_predictions"] + reb_res["unmatched_predictions"] + ast_res["unmatched_predictions"]
        all_unmatched_gt = pts_res["unmatched_gt"] + reb_res["unmatched_gt"] + ast_res["unmatched_gt"]
        all_errors = pts_res["errors"] + reb_res["errors"] + ast_res["errors"]

        # Assign unique error IDs
        for idx, err in enumerate(all_errors):
            err["error_id"] = f"err_{idx + 1:04d}"

        return {
            "schema_version": "pra-evaluation-summary-v2",
            "evaluated_utc": datetime.now(timezone.utc).isoformat(),
            "protocol_version": self.protocol.protocol_version,
            "protocol_config": asdict(self.protocol),
            "metadata": metadata or {},
            "combined_pra": {
                "detection": combined_det.to_dict(),
                "strict": combined_strict.to_dict(),
                "total_events_gt": pts_res["n_gt"] + reb_res["n_gt"] + ast_res["n_gt"],
                "total_events_pred": pts_res["n_pred"] + reb_res["n_pred"] + ast_res["n_pred"],
            },
            "stats": {
                "pts": pts_res,
                "reb": reb_res,
                "ast": ast_res,
            },
            "matched_pairs": all_matched_pairs,
            "unmatched_predictions": all_unmatched_preds,
            "unmatched_gt": all_unmatched_gt,
            "error_index": all_errors,
        }


# ==============================================================================
# Helper functions for reading predictions and GT files
# ==============================================================================

def load_predictions_from_bundle(path: Path) -> Dict[str, List[Dict[str, Any]]]:
    """Load predictions from a bundle directory or jsonl file."""
    path = Path(path).resolve()
    preds: Dict[str, List[Dict[str, Any]]] = {"pts": [], "reb": [], "ast": []}

    def read_jsonl(fpath: Path) -> List[Dict[str, Any]]:
        items = []
        if fpath.is_file():
            with fpath.open(encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if line:
                        try:
                            items.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        return items

    if path.is_file():
        # Single file
        if path.suffix.lower() == ".json":
            try:
                with path.open(encoding="utf-8") as handle:
                    data = json.load(handle)
                if "predictions" in data and isinstance(data["predictions"], dict):
                    return {
                        "pts": data["predictions"].get("pts", []),
                        "reb": data["predictions"].get("reb", []),
                        "ast": data["predictions"].get("ast", []),
                    }
            except Exception:
                pass
        records = read_jsonl(path)
        for r in records:
            etype = r.get("event_type")
            if etype in ("shot", "point"):
                preds["pts"].append(r)
            elif etype == "rebound":
                preds["reb"].append(r)
            elif etype == "assist":
                preds["ast"].append(r)
            else:
                # Default by keys
                if "shot_id" in r or "shooter_id" in r or "point_value" in r:
                    preds["pts"].append(r)
                elif "rebound_type" in r or "recovery_time_s" in r:
                    preds["reb"].append(r)
                elif "passer_id" in r or "assist_time_s" in r:
                    preds["ast"].append(r)
        return preds

    # Directory
    events_file = path / "events_auto.jsonl"
    shots_file = path / "shots_auto.jsonl"
    points_file = path / "points_auto.jsonl"
    rebounds_file = path / "rebound_candidates.jsonl"
    assists_file = path / "assist_candidates.jsonl"

    if events_file.is_file():
        records = read_jsonl(events_file)
        # Enrich from shots_auto.jsonl if present
        shots_by_id = {}
        if shots_file.is_file():
            for s in read_jsonl(shots_file):
                sid = s.get("shot_id") or s.get("event_id")
                if sid:
                    shots_by_id[sid] = s

        for r in records:
            etype = r.get("event_type")
            if etype in ("shot", "point"):
                sid = r.get("event_id") or r.get("parent_event_id")
                if sid in shots_by_id:
                    s_orig = shots_by_id[sid]
                    if "release_time_s" not in r and "release_time_s" in s_orig:
                        r["release_time_s"] = s_orig["release_time_s"]
                    if "outcome_time_s" not in r and "outcome_time_s" in s_orig:
                        r["outcome_time_s"] = s_orig["outcome_time_s"]
                    if "outcome" not in r and "outcome" in s_orig:
                        r["outcome"] = s_orig["outcome"]
                preds["pts"].append(r)
            elif etype == "rebound":
                preds["reb"].append(r)
            elif etype == "assist":
                preds["ast"].append(r)
    else:
        if shots_file.is_file():
            preds["pts"].extend(read_jsonl(shots_file))
        elif points_file.is_file():
            preds["pts"].extend(read_jsonl(points_file))

        if rebounds_file.is_file():
            preds["reb"].extend(read_jsonl(rebounds_file))

        if assists_file.is_file():
            preds["ast"].extend(read_jsonl(assists_file))

    return preds


def load_ground_truth(path: Path) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
    """Load ground truth from dataset v2 annotations or review JSON.

    Returns:
      (gt_by_stat, provenance_meta)
    """
    path = Path(path).resolve()
    gt: Dict[str, List[Dict[str, Any]]] = {"pts": [], "reb": [], "ast": []}
    meta: Dict[str, Any] = {"gt_source": str(path), "data_status": "unknown"}

    if path.is_file():
        # JSON review packet or single CSV
        if path.suffix.lower() == ".json":
            with path.open(encoding="utf-8") as handle:
                data = json.load(handle)

            meta["schema_version"] = data.get("schema_version")
            meta["review_status"] = data.get("review_status")
            meta["reviewer"] = data.get("reviewer")
            meta["is_synthetic"] = data.get("is_synthetic", False)

            if "ground_truth" in data and isinstance(data["ground_truth"], dict):
                gt["pts"].extend(data["ground_truth"].get("pts", []))
                gt["reb"].extend(data["ground_truth"].get("reb", []))
                gt["ast"].extend(data["ground_truth"].get("ast", []))
                meta["data_status"] = "synthetic_fixture" if meta["is_synthetic"] else "reviewed_fixture"
                return gt, meta

            # Check if Task08 scoring intake packet
            if "events" in data and isinstance(data["events"], list):
                for ev in data["events"]:
                    gt["pts"].append(ev)
            elif "shots" in data:
                gt["pts"].extend(data.get("shots", []))
                gt["reb"].extend(data.get("rebounds", []))
                gt["ast"].extend(data.get("assists", []))
            elif "passes" in data:
                # Task07 packet: passes might inform assists if positive
                for p in data.get("passes", []):
                    if p.get("is_assist") or p.get("assist"):
                        gt["ast"].append(p)
            return gt, meta

    # Directory with annotations CSVs
    annotations_dir = path / "annotations" if (path / "annotations").is_dir() else path
    shots_csv = annotations_dir / "shots.csv"
    reb_csv = annotations_dir / "rebounds.csv"
    ast_csv = annotations_dir / "assists.csv"

    def read_csv_rows(csv_path: Path) -> List[Dict[str, Any]]:
        rows = []
        if csv_path.is_file():
            with csv_path.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                for r in reader:
                    rows.append({k: v.strip() for k, v in r.items() if v is not None})
        return rows

    if shots_csv.is_file():
        shot_rows = read_csv_rows(shots_csv)
        rules_path = annotations_dir.parent / "ruleset.json"
        values = {}
        if rules_path.is_file():
            rules = json.loads(rules_path.read_text(encoding="utf-8"))
            configured = rules.get("point_values", {})
            values = {"1pt": configured.get("inside_arc"), "2pt": configured.get("outside_arc"),
                      "free_throw": configured.get("free_throw")}
        for row in shot_rows:
            # Canonical CSV encodes value via shot_type and the dataset rules,
            # not a point_value column. Never infer a missing/unknown shot type.
            value = values.get(row.get("shot_type"))
            if value is not None and not row.get("point_value"):
                row["point_value"] = value
        gt["pts"].extend(shot_rows)
    if reb_csv.is_file():
        gt["reb"].extend(read_csv_rows(reb_csv))
    if ast_csv.is_file():
        gt["ast"].extend(read_csv_rows(ast_csv))

    meta["data_status"] = "canonical_v2_csv"
    return gt, meta


def export_evaluation_bundle(
    eval_summary: Dict[str, Any],
    output_dir: Path,
) -> Dict[str, Path]:
    """Export evaluation summary, match table, and error index."""
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_file = out_dir / "evaluation_summary.json"
    match_table_json = out_dir / "match_table.json"
    matched_events_csv = out_dir / "matched_events.csv"
    error_index_file = out_dir / "error_index.json"

    # 1. Summary JSON
    with summary_file.open("w", encoding="utf-8") as handle:
        json.dump(eval_summary, handle, indent=2)

    # 2. Match table JSON
    match_table_data = {
        "schema_version": "match-table-v2",
        "matched_pairs": eval_summary.get("matched_pairs", []),
        "unmatched_predictions": eval_summary.get("unmatched_predictions", []),
        "unmatched_gt": eval_summary.get("unmatched_gt", []),
    }
    with match_table_json.open("w", encoding="utf-8") as handle:
        json.dump(match_table_data, handle, indent=2)

    # 3. Matched events CSV
    matched_rows = eval_summary.get("matched_pairs", [])
    csv_fields = [
        "stat", "pred_id", "gt_id",
        "pred_time_s", "gt_time_s", "delta_s",
        "pred_team", "gt_team", "team_match",
        "pred_actor", "gt_actor", "actor_match",
        "pred_value_or_subtype", "gt_value_or_subtype", "value_or_subtype_match",
        "parent_link_match", "strict_all_match",
    ]

    with matched_events_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for m in matched_rows:
            pred_time = m.get("pred_basket_s", m.get("pred_time_s"))
            gt_time = m.get("gt_basket_s", m.get("gt_time_s"))
            delta = m.get("basket_delta_s", m.get("delta_s"))
            val_match = m.get("value_match", m.get("subtype_match", True))
            pred_val = m.get("pred_value", m.get("pred_subtype", ""))
            gt_val = m.get("gt_value", m.get("gt_subtype", ""))
            link_match = m.get("parent_link_match", True)

            writer.writerow({
                "stat": m.get("stat"),
                "pred_id": m.get("pred_id"),
                "gt_id": m.get("gt_id"),
                "pred_time_s": pred_time,
                "gt_time_s": gt_time,
                "delta_s": delta,
                "pred_team": m.get("pred_team"),
                "gt_team": m.get("gt_team"),
                "team_match": m.get("team_match"),
                "pred_actor": m.get("pred_actor", m.get("pred_passer")),
                "gt_actor": m.get("gt_actor", m.get("gt_passer")),
                "actor_match": m.get("actor_match", m.get("passer_match")),
                "pred_value_or_subtype": pred_val,
                "gt_value_or_subtype": gt_val,
                "value_or_subtype_match": val_match,
                "parent_link_match": link_match,
                "strict_all_match": m.get("strict_all_match"),
            })

    # 4. Error index JSON
    error_data = {
        "schema_version": "error-index-v2",
        "error_count": len(eval_summary.get("error_index", [])),
        "errors": eval_summary.get("error_index", []),
    }
    with error_index_file.open("w", encoding="utf-8") as handle:
        json.dump(error_data, handle, indent=2)

    return {
        "evaluation_summary": summary_file,
        "match_table": match_table_json,
        "matched_events": matched_events_csv,
        "error_index": error_index_file,
    }
