"""Explicit, immutable clip-to-parent normalization for diagnostic evaluation."""
from __future__ import annotations

import copy
import math


TIME_FIELDS = {
    "release_time_s", "outcome_time_s", "score_time_s", "source_time_s",
    "rebound_time_s", "recovery_time_s", "assist_time_s", "pass_release_time_s",
    "basket_time_s", "basket_s", "release_s", "time_s", "confirmation_time_s",
}


def normalize_scope(events, scope, *, predictions=False):
    """Return new records in one declared parent timeline, with exclusion counts.

    Transformations come from media provenance, not matching results. Records
    outside the scope stay counted in the audit; no claim of exhaustive GT is made.
    """
    start, end = float(scope["start_time_s"]), float(scope["end_time_s"])
    if not all(math.isfinite(t) for t in (start, end)) or not 0 <= start < end:
        raise ValueError("Invalid evaluation interval")
    target = scope["video_id"]
    mappings = scope.get("video_mappings", {})
    normalized = {stat: [] for stat in ("pts", "reb", "ast")}
    audit = {"included": 0, "outside_interval": 0, "other_video": 0}
    for stat, rows in events.items():
        if stat not in normalized:
            continue
        for original in rows:
            row = copy.deepcopy(original)
            source_video = row.get("video_id")
            if source_video == target:
                offset = 0.0
            elif source_video in mappings:
                mapping = mappings[source_video]
                if mapping["parent_video_id"] != target:
                    raise ValueError("Mapping parent does not match evaluation source")
                offset = float(mapping["offset_s"])
                if not math.isfinite(offset):
                    raise ValueError("Invalid clip offset")
            elif predictions and not source_video:
                # Allowed only after caller checks the run's source SHA-256.
                offset = 0.0
            else:
                audit["other_video"] += 1
                continue
            row["video_id"] = target
            for key in TIME_FIELDS:
                value = row.get(key)
                if value is not None and value != "":
                    t = float(value)
                    if not math.isfinite(t):
                        raise ValueError("Nonfinite event timestamp")
                    row[key] = t + offset
            keys = ({"pts": ("outcome_time_s", "score_time_s", "basket_time_s", "source_time_s"),
                     "reb": ("rebound_time_s", "recovery_time_s", "source_time_s"),
                     "ast": ("assist_time_s", "pass_release_time_s", "source_time_s")})[stat]
            time = next((row[k] for k in keys if row.get(k) is not None and row[k] != ""), None)
            if time is None:
                raise ValueError("Event lacks an occurrence timestamp")
            if not start <= time <= end:
                audit["outside_interval"] += 1
                continue
            normalized[stat].append(row)
            audit["included"] += 1
    return normalized, audit


def validate_prediction_binding(run, scope):
    if run.get("source_fingerprint_sha256") != scope["source_sha256"]:
        raise ValueError("Prediction source hash does not match evaluation scope")
    coverage = run.get("source_coverage")
    if not coverage:
        raise ValueError("Predictions have no explicit processed source coverage")
    if (float(coverage["first_time_s"]) > float(scope["start_time_s"]) + 0.05 or
            float(coverage["last_time_s"]) < float(scope["end_time_s"]) - 0.05):
        raise ValueError("Prediction coverage is shorter than the requested evaluation interval")
