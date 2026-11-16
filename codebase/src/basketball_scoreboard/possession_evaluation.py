"""Independent Task07 evaluator. This module is never imported by recognition."""
from __future__ import annotations

import math
import numpy as np
from scipy.optimize import linear_sum_assignment

from .ball import iou


def rates(tp, fp, fn):
    return dict(tp=tp, fp=fp, fn=fn,
                precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/(tp+fn) if tp+fn else None,
                f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)


def match_passes(predictions, labels, tolerance_s, strict=True):
    """Maximum-cardinality one-to-one matching, then minimum timestamp error."""
    if not math.isfinite(tolerance_s) or tolerance_s <= 0:
        raise ValueError("Positive finite pass tolerance required")
    predictions = sorted(predictions, key=lambda p: (p["release_time_s"], p["pass_id"]))
    labels = sorted(labels, key=lambda p: (p["release_time_s"], p["pass_id"]))
    n, m = len(predictions), len(labels)
    cost = np.full((n, m+n), n+1., dtype=float)
    cost[:, :m] = (n+1.)*3
    for i, pred in enumerate(predictions):
        for j, gt in enumerate(labels):
            delta = abs(pred["release_time_s"]-gt["release_time_s"])
            if delta > tolerance_s:
                continue
            if gt.get("receive_time_s") is not None and (pred.get("receive_time_s") is None or abs(pred["receive_time_s"]-gt["receive_time_s"]) > tolerance_s):
                continue
            if strict:
                if any(not (pred.get(side) or {}).get(key) or
                       (pred.get(side) or {}).get(key) != gt[side][key]
                       for side in ("passer", "receiver") for key in ("player_id", "team_id")):
                    continue
            cost[i, j] = delta/tolerance_s
    selected = []
    if n:
        ri, ci = linear_sum_assignment(cost)
        selected = [(int(i), int(j)) for i,j in zip(ri,ci) if j < m and cost[i,j] <= 1.]
    result = rates(len(selected), n-len(selected), m-len(selected))
    result["matches"] = [dict(prediction_id=predictions[i]["pass_id"], gt_id=labels[j]["pass_id"],
                              release_error_s=abs(predictions[i]["release_time_s"]-labels[j]["release_time_s"])) for i,j in selected]
    return result


def validate_packet(packet, source_hash, diagnostic=False):
    if packet.get("schema_version") != "task07-evaluation-1" or packet.get("source_video_sha256") != source_hash:
        raise ValueError("Evaluation packet schema/source mismatch")
    synthetic = packet.get("is_synthetic") is True
    if synthetic and not diagnostic:
        raise ValueError("Synthetic GT requires diagnostic evaluation")
    if not synthetic and (packet.get("review_status") != "approved" or not packet.get("reviewer") or
                          packet.get("protocol_status") != "approved" or not packet.get("protocol_version")):
        raise ValueError("Reviewed GT and approved protocol required")
    tolerance, threshold = packet["pass_tolerance_s"], packet["ball_iou_threshold"]
    if not math.isfinite(tolerance) or tolerance <= 0 or not math.isfinite(threshold) or not 0 < threshold <= 1:
        raise ValueError("Invalid evaluation thresholds")
    coverage = sorted(packet.get("coverage", []), key=lambda x: x["start_time_s"])
    if not coverage:
        raise ValueError("Reviewed coverage required even when there are no events")
    end = -1.
    for interval in coverage:
        a,b = interval["start_time_s"], interval["end_time_s"]
        if not all(math.isfinite(x) for x in (a,b)) or not 0 <= a < b or a < end:
            raise ValueError("Invalid or overlapping evaluation coverage")
        end = b
    control_end = -1.
    for interval in sorted(packet.get("control_intervals", []), key=lambda x: x["start_time_s"]):
        a,b = interval["start_time_s"], interval["end_time_s"]
        if not all(math.isfinite(x) for x in (a,b)) or not 0 <= a < b or a < control_end:
            raise ValueError("Invalid or overlapping control GT")
        if not any(c["start_time_s"] <= a and b <= c["end_time_s"] for c in coverage):
            raise ValueError("Control GT lies outside reviewed coverage")
        control_end = b
        if not interval.get("uncertain") and (not interval.get("player_id") or not interval.get("team_id")):
            raise ValueError("Eligible control GT must identify team and player")
    ids = set()
    for event in packet.get("passes", []):
        if not event.get("pass_id") or event["pass_id"] in ids:
            raise ValueError("Duplicate/missing pass GT ID")
        ids.add(event["pass_id"])
        a,b = event["release_time_s"], event["receive_time_s"]
        if not all(math.isfinite(x) for x in (a,b)) or not 0 <= a <= b:
            raise ValueError("Invalid pass GT timing")
        if not any(c["start_time_s"] <= a <= b < c["end_time_s"] for c in coverage):
            raise ValueError("Pass GT outside coverage")
        if not event.get("uncertain") and any(not event.get(side, {}).get(key) for side in ("passer", "receiver") for key in ("player_id", "team_id")):
            raise ValueError("Eligible pass GT requires actors")
    return coverage


def evaluate(result, packet, source_hash, max_gap_s=.25, diagnostic=False):
    coverage = validate_packet(packet, source_hash, diagnostic)
    inside = lambda t: any(c["start_time_s"] <= t < c["end_time_s"] for c in coverage)
    controls = result["controls"]
    denominator = correct = assigned = 0.
    for gt in packet.get("control_intervals", []):
        if gt.get("uncertain"):
            continue
        denominator += gt["end_time_s"]-gt["start_time_s"]
        for left, right in zip(controls, controls[1:]):
            if right["source_time_s"]-left["source_time_s"] > max_gap_s:
                continue
            overlap = max(0., min(right["source_time_s"], gt["end_time_s"])-max(left["source_time_s"], gt["start_time_s"]))
            current = left.get("controller") or {}
            if overlap and left["certainty"] == "confirmed" and current.get("player_id"):
                assigned += overlap
                if current["player_id"] == gt["player_id"] and current.get("team_id") == gt["team_id"]:
                    correct += overlap
    tolerance = packet["pass_tolerance_s"]
    uncertain_times = [p["release_time_s"] for p in packet.get("passes", []) if p.get("uncertain")]
    ignored = lambda t: any(abs(t-u) <= tolerance for u in uncertain_times)
    predicted = [p for p in result["passes"] if p["outcome"] == "completed" and inside(p["release_time_s"]) and not ignored(p["release_time_s"])]
    labels = [p for p in packet.get("passes", []) if not p.get("uncertain")]
    if any(ignored(p["release_time_s"]) for p in labels):
        raise ValueError("Eligible pass overlaps an uncertain evaluation window")
    ball_by_frame = {b["frame_index"]: b for b in result["balls"]}
    ball_total = ball_found = 0
    seen_frames = set()
    for label in packet.get("ball_samples", []):
        if label["frame_index"] in seen_frames:
            raise ValueError("Duplicate ball GT frame")
        seen_frames.add(label["frame_index"])
        if not inside(label["source_time_s"]):
            raise ValueError("Ball sample outside reviewed coverage")
        if label.get("uncertain") or not label.get("visible", True):
            continue
        box = label["xyxy"]
        if len(box) != 4 or not all(math.isfinite(x) for x in box) or not (box[0] < box[2] and box[1] < box[3]):
            raise ValueError("Invalid ball GT box")
        ball_total += 1
        pred = ball_by_frame.get(label["frame_index"])
        ball_found += int(bool(pred and abs(pred["source_time_s"]-label["source_time_s"]) <= 1e-6 and
                              pred["sample_type"] == "observed" and iou(pred["xyxy"], box) >= packet["ball_iou_threshold"]))
    return dict(scope="synthetic_fixture" if packet.get("is_synthetic") else "reviewed_development_evaluation",
                reviewed_seconds=sum(c["end_time_s"]-c["start_time_s"] for c in coverage),
                control=dict(eligible_seconds=denominator, correct_seconds=correct,
                             unknown_or_missed_seconds=max(0., denominator-assigned),
                             strict_accuracy=correct/denominator if denominator else None),
                ball=dict(eligible_samples=ball_total, observed_matches=ball_found,
                          recall=ball_found/ball_total if ball_total else None),
                passes_event_only=match_passes(predicted, labels, tolerance, strict=False),
                passes_strict=match_passes(predicted, labels, tolerance, strict=True),
                unresolved_pass_predictions=sum(p["outcome"] != "completed" and inside(p["release_time_s"]) for p in result["passes"]),
                uncertain_pass_gt=sum(bool(p.get("uncertain")) for p in packet.get("passes", [])),
                ignored_predictions_at_uncertain_pass=sum(p["outcome"] == "completed" and inside(p["release_time_s"]) and ignored(p["release_time_s"]) for p in result["passes"]),
                acceptance_pass=None, note="No acceptance profile supplied to this generic evaluator")


def apply_acceptance_profile(metrics, profile, run, packet, result):
    """Apply explicitly approved, source-bound pilot criteria after GT review."""
    if (profile.get('review_status')!='approved' or profile.get('approved_by')!='user' or
            packet.get('is_synthetic') or packet.get('review_status')!='approved' or not packet.get('reviewer') or
            packet.get('protocol_version')!=profile.get('protocol_version') or
            run.get('source_fingerprint_sha256') not in profile.get('allowed_video_sha256',[])):
        raise ValueError('Acceptance requires approved, source-bound real GT/protocol')
    if any(packet.get(key)!=profile.get(key) or profile.get(key) is None
           for key in ('ball_iou_threshold','pass_tolerance_s')):
        raise ValueError('GT matching parameters differ from approved protocol')
    observed={b['frame_index']:b['sample_type']=='observed' for b in result['balls']}
    prediction_only=sum(c['certainty']=='confirmed' and not observed.get(c['frame_index'],False) for c in result['controls'])
    crossings=sum(any(p['release_time_s']<edge<=p['confirmed_at_s']
                      for interval in run.get('exclusions',[]) for edge in (interval['start_time_s'],interval['end_time_s']))
                  for p in result['passes'] if p['outcome']=='completed')
    strict=metrics['passes_strict'];ball=metrics['ball'];control=metrics['control']
    enough=(ball['eligible_samples']>=profile['minimum_visible_ball_samples'] and
            strict['tp']+strict['fn']>=profile['minimum_completed_pass_gt'] and control['eligible_seconds']>0)
    export=run.get('video_export') or {}
    pts_error=export.get('max_pts_error_s')
    checks=dict(ball_recall=ball['recall'] is not None and ball['recall']>=profile['ball_recall_min'],
                strict_control_accuracy=control['strict_accuracy'] is not None and control['strict_accuracy']>=profile['control_accuracy_min'],
                strict_pass_precision=strict['precision'] is not None and strict['precision']>=profile['pass_precision_min'],
                strict_pass_recall=strict['recall'] is not None and strict['recall']>=profile['pass_recall_min'],
                no_prediction_only_control=prediction_only==0,no_pass_crossing_cut=crossings==0,
                pts_export=pts_error is not None and pts_error<=profile['max_pts_error_s'])
    metrics.update(acceptance_pass=bool(enough and all(checks.values())),
                   acceptance_status='insufficient_samples' if not enough else 'passed_pilot' if all(checks.values()) else 'failed_criteria',
                   acceptance_checks=checks,minimum_samples_met=enough,
                   integrity=dict(prediction_only_control_frames=prediction_only,completed_passes_crossing_cut=crossings),
                   acceptance_scope='same_match_pilot_not_independent_match_test',
                   note='Approved project criteria; raw automatic predictions, no manual correction')
    return metrics
