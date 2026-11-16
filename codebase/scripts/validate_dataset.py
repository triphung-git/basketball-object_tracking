"""Comprehensive validation tool for dataset manifest, events, reviews, coverage, and splits.

Enforces structural schema rules, timebase boundaries, label integrity,
cross-table referential integrity, source-group leakage prevention, and
clearly separates structural errors from dataset evaluation readiness.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Set, Tuple


VALID_RESULTS = {"made", "miss", "uncertain"}
VALID_TEAMS = {"solo", "A", "B", "a", "b"}
VALID_POINTS = {1, 2, 3}
VALID_REVIEW_STATUSES = {"draft", "needs_review", "approved", "rejected"}
VALID_COVERAGE_STATUSES = {"fully_reviewed", "needs_review", "unreviewed", "excluded"}


class ValidationResult:
    def __init__(self) -> None:
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.readiness_notes: List[str] = []
        self.stats: Dict[str, Any] = {
            "videos_count": 0,
            "approved_shots_count": 0,
            "draft_shots_count": 0,
            "approved_by_result": {},
            "draft_by_result": {},
            "split_status": "unknown",
            "calibration_videos": 0,
            "test_videos": 0,
            "split_video_ids": {},
        }

    @property
    def is_valid(self) -> bool:
        """True if there are zero structural/integrity errors."""
        return len(self.errors) == 0

    @property
    def is_ready_for_evaluation(self) -> bool:
        """True if valid AND all readiness criteria for benchmark evaluation are met."""
        return self.is_valid and len(self.readiness_notes) == 0


def compute_file_sha256(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def parse_float_safe(val: Any) -> Optional[float]:
    if val is None or str(val).strip() == "":
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except ValueError:
        return None


def validate_manifest(
    manifest_path: Path,
    codebase_root: Path,
    res: ValidationResult,
) -> Dict[str, Dict[str, Any]]:
    """Validate manifest.csv schema, types, file existence, and stream bounds."""
    if not manifest_path.exists():
        res.errors.append(f"Manifest file missing: {manifest_path}")
        return {}

    required_cols = [
        "video_id",
        "relative_path",
        "width",
        "height",
        "fps",
        "duration_s",
        "frame_count",
        "camera_id",
        "session_id",
        "conditions",
        "scoring_eligibility",
        "notes",
    ]

    manifest: Dict[str, Dict[str, Any]] = {}
    with open(manifest_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            res.errors.append(f"Manifest {manifest_path} is empty or missing headers.")
            return {}

        missing_cols = [c for c in required_cols if c not in reader.fieldnames]
        if missing_cols:
            res.errors.append(f"Manifest {manifest_path} missing mandatory columns: {missing_cols}")
            return {}

        for row_idx, row in enumerate(reader, start=2):
            vid = row.get("video_id", "").strip()
            if not vid:
                res.errors.append(f"Manifest row {row_idx}: empty video_id.")
                continue
            if vid in manifest:
                res.errors.append(f"Manifest row {row_idx}: duplicate video_id '{vid}'.")
                continue

            rel_path = row.get("relative_path", "").strip()
            abs_video_path = (codebase_root / rel_path).resolve()
            if not rel_path or not abs_video_path.is_relative_to(codebase_root.resolve()):
                res.errors.append(f"Manifest video '{vid}': path must stay inside codebase root.")
                continue
            media_exists = abs_video_path.is_file()
            if not media_exists:
                res.warnings.append(
                    f"Manifest video '{vid}': file not found on disk at {abs_video_path} (relative: {rel_path})."
                )
            expected_sha = row.get("sha256", "").strip()
            if len(expected_sha) != 64 or any(c not in "0123456789abcdef" for c in expected_sha):
                res.errors.append(f"Manifest video '{vid}': invalid SHA-256 fingerprint.")
            elif media_exists and compute_file_sha256(abs_video_path) != expected_sha:
                res.errors.append(f"Manifest video '{vid}': media checksum mismatch.")
            for dimension in ("width", "height"):
                try:
                    if int(row.get(dimension, "0")) <= 0:
                        raise ValueError
                except (TypeError, ValueError):
                    res.errors.append(f"Manifest video '{vid}': invalid {dimension}.")

            fps = parse_float_safe(row.get("fps"))
            if fps is None or fps <= 0:
                res.errors.append(f"Manifest video '{vid}': invalid fps '{row.get('fps')}'.")

            duration_s = parse_float_safe(row.get("duration_s"))
            if duration_s is None or duration_s <= 0:
                res.errors.append(f"Manifest video '{vid}': invalid duration_s '{row.get('duration_s')}'.")

            try:
                frame_count = int(row.get("frame_count", 0))
                if frame_count <= 0:
                    res.errors.append(f"Manifest video '{vid}': invalid frame_count '{row.get('frame_count')}'.")
            except ValueError:
                res.errors.append(f"Manifest video '{vid}': non-integer frame_count '{row.get('frame_count')}'.")
                frame_count = 0

            manifest[vid] = {
                "relative_path": rel_path,
                "fps": fps or 0.0,
                "duration_s": duration_s or 0.0,
                "frame_count": frame_count,
                "camera_id": row.get("camera_id", "unknown").strip(),
                "session_id": row.get("session_id", "unknown").strip(),
                "scoring_eligibility": row.get("scoring_eligibility", "").strip(),
                "sha256": row.get("sha256", "").strip(),
                "media_exists": media_exists,
            }

    res.stats["videos_count"] = len(manifest)
    return manifest


def validate_events_table(
    events_path: Path,
    manifest: Dict[str, Dict[str, Any]],
    res: ValidationResult,
    is_draft: bool = False,
) -> List[Dict[str, Any]]:
    """Validate event records (schema, timing, results, scores)."""
    table_name = "events.draft.csv" if is_draft else "events.csv"
    if not events_path.exists():
        if not is_draft:
            res.errors.append(f"Ground truth events file missing: {events_path}")
        return []

    required_cols = [
        "video_id",
        "shot_id",
        "start_s",
        "end_s",
        "result",
        "score_time_s",
        "team",
        "point_value",
        "notes",
    ]

    records: List[Dict[str, Any]] = []
    seen_keys: Set[Tuple[str, str]] = set()
    shots_by_video: Dict[str, List[Dict[str, Any]]] = {}

    with open(events_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            if not is_draft:
                res.errors.append(f"{table_name} is empty or has no header.")
            return []

        missing_cols = [c for c in required_cols if c not in reader.fieldnames]
        if missing_cols:
            res.errors.append(f"{table_name} missing columns: {missing_cols}")
            return []

        for row_idx, row in enumerate(reader, start=2):
            vid = row.get("video_id", "").strip()
            sid = row.get("shot_id", "").strip()
            if not vid or not sid:
                res.errors.append(f"{table_name} row {row_idx}: missing video_id or shot_id.")
                continue

            key = (vid, sid)
            if key in seen_keys:
                res.errors.append(f"{table_name} row {row_idx}: duplicate key ({vid}, {sid}).")
            seen_keys.add(key)

            if vid not in manifest:
                res.errors.append(
                    f"{table_name} row {row_idx}: video_id '{vid}' not declared in manifest.csv."
                )
                vid_duration = None
            else:
                vid_duration = manifest[vid]["duration_s"]

            start_s = parse_float_safe(row.get("start_s"))
            end_s = parse_float_safe(row.get("end_s"))

            if start_s is None or end_s is None:
                res.errors.append(
                    f"{table_name} row {row_idx} ({vid}, {sid}): non-numeric or missing start_s/end_s."
                )
            else:
                if start_s < 0:
                    res.errors.append(
                        f"{table_name} row {row_idx} ({vid}, {sid}): start_s ({start_s}) < 0."
                    )
                if start_s >= end_s:
                    res.errors.append(
                        f"{table_name} row {row_idx} ({vid}, {sid}): start_s ({start_s}) >= end_s ({end_s})."
                    )
                if vid_duration is not None and end_s > (vid_duration + 0.05):
                    res.errors.append(
                        f"{table_name} row {row_idx} ({vid}, {sid}): end_s ({end_s}) exceeds video duration ({vid_duration}s)."
                    )

            result = row.get("result", "").strip().lower()
            if result not in VALID_RESULTS:
                res.errors.append(
                    f"{table_name} row {row_idx} ({vid}, {sid}): invalid result '{row.get('result')}'. "
                    f"Must be one of {sorted(VALID_RESULTS)}."
                )

            score_time_raw = row.get("score_time_s", "").strip()
            score_time_s = parse_float_safe(score_time_raw)

            if result == "made":
                if score_time_s is None:
                    res.errors.append(
                        f"{table_name} row {row_idx} ({vid}, {sid}): result is 'made' but score_time_s is missing or invalid."
                    )
                elif start_s is not None and end_s is not None:
                    # score_time must fall within [start_s, end_s]
                    if not (start_s - 0.05 <= score_time_s <= end_s + 0.05):
                        res.errors.append(
                            f"{table_name} row {row_idx} ({vid}, {sid}): score_time_s ({score_time_s}) is outside "
                            f"shot interval [{start_s}, {end_s}]."
                        )
            elif result in ("miss", "uncertain"):
                if score_time_raw != "":
                    res.errors.append(
                        f"{table_name} row {row_idx} ({vid}, {sid}): result is '{result}' but score_time_s is populated ('{score_time_raw}'). Must be empty."
                    )

            team = row.get("team", "").strip()
            if team not in VALID_TEAMS:
                res.errors.append(
                    f"{table_name} row {row_idx} ({vid}, {sid}): unexpected team '{team}' (recommended: solo, A, B)."
                )

            try:
                pval = int(row.get("point_value", 0))
                if pval not in VALID_POINTS:
                    res.errors.append(
                        f"{table_name} row {row_idx} ({vid}, {sid}): point_value '{pval}' not in {VALID_POINTS}."
                    )
            except ValueError:
                res.errors.append(
                    f"{table_name} row {row_idx} ({vid}, {sid}): point_value '{row.get('point_value')}' is not integer."
                )

            rec = {
                "video_id": vid,
                "shot_id": sid,
                "start_s": start_s or 0.0,
                "end_s": end_s or 0.0,
                "result": result,
                "score_time_s": score_time_s,
                "team": team,
                "point_value": row.get("point_value"),
                "notes": row.get("notes", ""),
            }
            records.append(rec)
            shots_by_video.setdefault(vid, []).append(rec)

    # Check for overlapping shots within the same video -> flag warning
    for vid, shot_list in shots_by_video.items():
        sorted_shots = sorted(shot_list, key=lambda s: s["start_s"])
        for i in range(len(sorted_shots) - 1):
            s1 = sorted_shots[i]
            s2 = sorted_shots[i + 1]
            if s1["end_s"] > s2["start_s"]:
                res.warnings.append(
                    f"{table_name}: Temporal overlap detected in video '{vid}' between shot '{s1['shot_id']}' "
                    f"[{s1['start_s']}, {s1['end_s']}] and '{s2['shot_id']}' [{s2['start_s']}, {s2['end_s']}]. "
                    f"Please review footage."
                )

    counts_by_result: Dict[str, int] = {}
    for r in records:
        counts_by_result[r["result"]] = counts_by_result.get(r["result"], 0) + 1

    if is_draft:
        res.stats["draft_shots_count"] = len(records)
        res.stats["draft_by_result"] = counts_by_result
    else:
        res.stats["approved_shots_count"] = len(records)
        res.stats["approved_by_result"] = counts_by_result

    return records


def validate_reviews(
    reviews_path: Path,
    manifest: Dict[str, Dict[str, Any]],
    draft_records: List[Dict[str, Any]],
    approved_records: List[Dict[str, Any]],
    res: ValidationResult,
) -> None:
    """Validate review ledger and prevent unreviewed draft promotions."""
    if not reviews_path.exists():
        res.errors.append(f"Review ledger missing: {reviews_path}")
        return

    required_cols = [
        "video_id",
        "shot_id",
        "review_status",
        "reviewer",
        "reviewed_at_utc",
        "rejection_or_approval_reason",
    ]

    reviews: Dict[Tuple[str, str], Dict[str, Any]] = {}
    with open(reviews_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            res.errors.append(f"reviews.csv is empty or has no header.")
            return

        missing = [c for c in required_cols if c not in reader.fieldnames]
        if missing:
            res.errors.append(f"reviews.csv missing columns: {missing}")
            return

        for row_idx, row in enumerate(reader, start=2):
            vid = row.get("video_id", "").strip()
            sid = row.get("shot_id", "").strip()
            if not vid or not sid:
                res.errors.append(f"reviews.csv row {row_idx}: empty video_id or shot_id.")
                continue

            key = (vid, sid)
            if vid not in manifest:
                res.errors.append(f"Review {key} references a video not in manifest.")
            if key in reviews:
                res.errors.append(f"reviews.csv row {row_idx}: duplicate review for key {key}.")
            status = row.get("review_status", "").strip().lower()
            if status not in VALID_REVIEW_STATUSES:
                res.errors.append(
                    f"reviews.csv row {row_idx} ({key}): invalid status '{status}'. Must be {sorted(VALID_REVIEW_STATUSES)}."
                )
            reviews[key] = {
                "status": status,
                "reviewer": row.get("reviewer", "").strip(),
                "reviewed_at": row.get("reviewed_at_utc", "").strip(),
                "reason": row.get("rejection_or_approval_reason", "").strip(),
            }
            if status == "approved":
                try:
                    reviewed_at = datetime.fromisoformat(reviews[key]["reviewed_at"].replace("Z", "+00:00"))
                    if reviewed_at.tzinfo is None:
                        raise ValueError
                except ValueError:
                    res.errors.append(f"Approved review {key} lacks a timezone-aware review timestamp.")

    approved_keys = {(r["video_id"], r["shot_id"]) for r in approved_records}
    draft_keys = {(r["video_id"], r["shot_id"]) for r in draft_records}
    if approved_keys & draft_keys:
        res.errors.append(f"Draft and approved tables share keys: {sorted(approved_keys & draft_keys)}.")
    for key, review in reviews.items():
        if review["status"] == "approved" and key not in approved_keys:
            res.errors.append(f"Approved review {key} has no matching events.csv record.")

    # Verify that every approved record has an 'approved' status in reviews.csv with non-empty reviewer
    for app in approved_records:
        key = (app["video_id"], app["shot_id"])
        if key not in reviews:
            res.errors.append(
                f"Approved shot {key} in events.csv has no entry in reviews.csv ledger."
            )
        else:
            rev = reviews[key]
            if rev["status"] != "approved":
                res.errors.append(
                    f"Approved shot {key} in events.csv has review_status '{rev['status']}' in reviews.csv, not 'approved'."
                )
            if not rev["reviewer"]:
                res.errors.append(
                    f"Approved shot {key} in events.csv is missing reviewer in reviews.csv (fake/uncredited approval prohibited)."
                )


def validate_coverage(
    coverage_path: Path,
    manifest: Dict[str, Dict[str, Any]],
    res: ValidationResult,
) -> Dict[str, List[Dict[str, Any]]]:
    """Validate temporal coverage annotations."""
    intervals: Dict[str, List[Dict[str, Any]]] = {}
    if not coverage_path.exists():
        res.errors.append(f"Coverage sidecar missing: {coverage_path}")
        return intervals

    required_cols = ["video_id", "start_s", "end_s", "coverage_status", "reason"]
    with open(coverage_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            res.errors.append("coverage.csv is empty or has no header.")
            return intervals
        missing = [c for c in required_cols if c not in reader.fieldnames]
        if missing:
            res.errors.append(f"coverage.csv missing columns: {missing}")
            return intervals

        for row_idx, row in enumerate(reader, start=2):
            vid = row.get("video_id", "").strip()
            if vid not in manifest:
                res.errors.append(f"coverage.csv row {row_idx}: video_id '{vid}' not in manifest.")
                continue

            start_s = parse_float_safe(row.get("start_s"))
            end_s = parse_float_safe(row.get("end_s"))
            duration_s = manifest[vid]["duration_s"]

            if start_s is None or end_s is None or start_s < 0 or start_s >= end_s:
                res.errors.append(
                    f"coverage.csv row {row_idx} ({vid}): invalid interval [{row.get('start_s')}, {row.get('end_s')}]."
                )
            elif end_s > (duration_s + 0.05):
                res.errors.append(
                    f"coverage.csv row {row_idx} ({vid}): end_s ({end_s}) exceeds video duration ({duration_s}s)."
                )

            status = row.get("coverage_status", "").strip().lower()
            if status not in VALID_COVERAGE_STATUSES:
                res.errors.append(
                    f"coverage.csv row {row_idx} ({vid}): invalid coverage_status '{status}'. "
                    f"Must be {sorted(VALID_COVERAGE_STATUSES)}."
                )
            if start_s is not None and end_s is not None and start_s < end_s:
                intervals.setdefault(vid, []).append({"start_s": start_s, "end_s": end_s, "status": status})
    for vid, spans in intervals.items():
        spans.sort(key=lambda span: span["start_s"])
        for previous, current in zip(spans, spans[1:]):
            if previous["end_s"] > current["start_s"] + 1e-6:
                res.errors.append(f"Coverage overlap in {vid}: interval statuses are ambiguous.")
    return intervals


def validate_splits(
    splits_path: Path,
    manifest_path: Path,
    manifest: Dict[str, Dict[str, Any]],
    res: ValidationResult,
) -> None:
    """Validate data splits for leaks, disjointness, group consistency, and locked hashes."""
    if not splits_path.exists():
        res.errors.append(f"splits.json missing: {splits_path}")
        return

    try:
        data = json.loads(splits_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        res.errors.append(f"splits.json is invalid JSON: {e}")
        return

    status = data.get("status", "").strip().lower()
    res.stats["split_status"] = status
    if status not in ("proposed", "locked"):
        res.errors.append(f"splits.json status must be 'proposed' or 'locked', got '{status}'.")

    proposed = data.get("proposed_split", {})
    for split_name in ("calibration", "test", "detection_only_or_excluded"):
        ids = proposed.get(split_name, {}).get("video_ids", [])
        if len(ids) != len(set(ids)):
            res.errors.append(f"Duplicate video IDs within {split_name} split.")
    calib_vids = set(proposed.get("calibration", {}).get("video_ids", []))
    test_vids = set(proposed.get("test", {}).get("video_ids", []))
    res.stats["calibration_videos"] = len(calib_vids)
    res.stats["test_videos"] = len(test_vids)
    res.stats["split_video_ids"] = {"calibration": sorted(calib_vids), "test": sorted(test_vids)}
    excluded = set(proposed.get("detection_only_or_excluded", {}).get("video_ids", []))
    if excluded & (calib_vids | test_vids):
        res.errors.append("Excluded videos also occur in calibration/test.")

    # 1. Disjointness check between calibration and test
    overlap = calib_vids.intersection(test_vids)
    if overlap:
        res.errors.append(f"Data split leakage: videos {sorted(overlap)} appear in both calibration and test!")

    # 2. Check all split videos exist in manifest
    all_split_vids = calib_vids.union(test_vids)
    for vid in all_split_vids:
        if vid not in manifest:
            res.errors.append(f"splits.json references video_id '{vid}' which is not in manifest.csv.")

    # 3. Source group leakage check (same camera/session or source group in both sets)
    source_groups = data.get("source_groups", {})
    calib_groups: Set[str] = set()
    test_groups: Set[str] = set()
    calib_sessions: Set[str] = set()
    test_sessions: Set[str] = set()

    for gname, ginfo in source_groups.items():
        gvids = set(ginfo.get("video_ids", []))
        if gvids.intersection(calib_vids):
            calib_groups.add(gname)
            if ginfo.get("session_id"):
                calib_sessions.add(ginfo["session_id"])
        if gvids.intersection(test_vids):
            test_groups.add(gname)
            if ginfo.get("session_id"):
                test_sessions.add(ginfo["session_id"])

    group_leak = calib_groups.intersection(test_groups)
    if group_leak:
        res.errors.append(
            f"Source group leakage: groups {sorted(group_leak)} contain videos in both calibration and test sets!"
        )

    session_leak = calib_sessions.intersection(test_sessions)
    if session_leak:
        res.errors.append(
            f"Session leakage: session IDs {sorted(session_leak)} appear in both calibration and test sets!"
        )

    # Derive leakage from manifest too: omitting a JSON group must not bypass it.
    for field in ("camera_id", "session_id", "sha256"):
        left = {manifest[v][field] for v in calib_vids if v in manifest} - {"", "unknown"}
        right = {manifest[v][field] for v in test_vids if v in manifest} - {"", "unknown"}
        if left & right:
            res.errors.append(f"Manifest {field} leakage between calibration and test.")
    grouped_ids = [v for group in source_groups.values() for v in group.get("video_ids", [])]
    for vid in all_split_vids:
        if grouped_ids.count(vid) != 1:
            res.errors.append(f"Split video {vid} must belong to exactly one source group.")
    for group in source_groups.values():
        for vid in group.get("video_ids", []):
            if vid not in manifest:
                res.errors.append(f"Source group references unknown video {vid}.")
                continue
            for field in ("camera_id", "session_id"):
                if group.get(field) != manifest[vid][field]:
                    res.errors.append(f"Source group {field} disagrees with manifest for {vid}.")

    # 4. If status == 'locked', verify checksum integrity
    if status == "locked":
        fingerprints = data.get("integrity_fingerprints", {})
        for label, path in {
            "manifest": manifest_path,
            "events": manifest_path.parent / "annotations/events.csv",
            "coverage": manifest_path.parent / "annotations/coverage.csv",
        }.items():
            expected = fingerprints.get(f"{label}_sha256")
            if not expected:
                res.errors.append(f"Locked split missing {label}_sha256 fingerprint.")
            elif path.is_file() and compute_file_sha256(path) != expected:
                res.errors.append(
                    f"Locked {label} checksum mismatch!"
                )


def evaluate_readiness(
    res: ValidationResult,
    manifest: Dict[str, Dict[str, Any]],
    approved_records: List[Dict[str, Any]],
    draft_records: List[Dict[str, Any]],
    coverage: Dict[str, List[Dict[str, Any]]],
) -> None:
    """Assess whether dataset is ready for benchmark evaluation (independent of structural validity)."""
    # 1. Approved labels check
    if len(approved_records) == 0:
        res.readiness_notes.append(
            "Ground truth events.csv contains 0 approved shots (all candidates remain in events.draft.csv awaiting user review)."
        )

    # 2. Check made and miss classes in approved records
    test_ids = set(res.stats["split_video_ids"].get("test", []))
    test_records = [r for r in approved_records if r["video_id"] in test_ids]
    approved_results = set(r["result"] for r in test_records)
    res.stats["test_by_result"] = {label: sum(r["result"] == label for r in test_records) for label in VALID_RESULTS}
    if "made" not in approved_results:
        res.readiness_notes.append("Approved test split lacks 'made' shots.")
    if "miss" not in approved_results:
        res.readiness_notes.append("Approved test split lacks 'miss' shots.")

    # 3. Check sample size
    if len(approved_records) < 50:
        res.warnings.append(
            f"Small pilot dataset: {len(approved_records)} approved shots, {len(test_records)} in test; recommended 50-100 is a collection target, not a readiness gate."
        )

    # 4. Split status check
    if res.stats["split_status"] != "locked":
        res.readiness_notes.append(
            f"splits.json is '{res.stats['split_status']}', not locked by user."
        )

    # 5. Test set presence
    if res.stats["test_videos"] == 0:
        res.readiness_notes.append(
            "Test split is currently empty (0 videos). Independent holdout test set requires additional video clips."
        )

    # 6. Scoring eligibility
    scoring_eligible_vids = [
        vid for vid, meta in manifest.items() if meta.get("scoring_eligibility") == "scoring_eligible"
    ]
    if len(scoring_eligible_vids) < 2:
        res.readiness_notes.append(
            f"Only {len(scoring_eligible_vids)} video(s) ({scoring_eligible_vids}) are scoring_eligible. "
            f"Cannot split into independent calibration and test sets without additional scoring-eligible footage."
        )
    for split_name, video_ids in res.stats["split_video_ids"].items():
        if not video_ids:
            res.readiness_notes.append(f"{split_name} split is empty.")
        for vid in video_ids:
            if vid not in manifest:
                continue
            meta = manifest[vid]
            if not meta["media_exists"] or meta["scoring_eligibility"] != "scoring_eligible":
                res.readiness_notes.append(f"{split_name}/{vid}: media missing or not scoring eligible.")
            if meta["camera_id"] in ("", "unknown") or meta["session_id"] in ("", "unknown"):
                res.readiness_notes.append(f"{split_name}/{vid}: source provenance unknown.")
            spans = coverage.get(vid, [])
            cursor = 0.0
            for span in spans:
                if span["start_s"] > cursor + 0.05 or span["status"] in {"unreviewed", "needs_review"}:
                    res.readiness_notes.append(f"{split_name}/{vid}: unreviewed temporal coverage.")
                cursor = max(cursor, span["end_s"])
            if cursor < meta["duration_s"] - 0.05 or not any(s["status"] == "fully_reviewed" for s in spans):
                res.readiness_notes.append(f"{split_name}/{vid}: incomplete reviewed/excluded coverage.")
            for event in [r for r in approved_records if r["video_id"] == vid]:
                if not any(s["status"] == "fully_reviewed" and s["start_s"] <= event["start_s"] + 1e-6
                           and s["end_s"] >= event["end_s"] - 1e-6 for s in spans):
                    res.readiness_notes.append(f"{split_name}/{vid}/{event['shot_id']}: shot not contained in reviewed coverage.")
            if not any(r["video_id"] == vid for r in approved_records):
                res.readiness_notes.append(f"{split_name}/{vid}: no approved shots.")
    if any(r["video_id"] in test_ids for r in draft_records):
        res.readiness_notes.append("Test split still has draft shots awaiting review.")


def validate_dataset(
    codebase_root: Path,
    require_ready: bool = False,
) -> ValidationResult:
    """Main validation pipeline returning ValidationResult."""
    res = ValidationResult()
    data_dir = codebase_root / "data"
    manifest_path = data_dir / "manifest.csv"
    events_path = data_dir / "annotations" / "events.csv"
    draft_path = data_dir / "annotations" / "events.draft.csv"
    reviews_path = data_dir / "annotations" / "reviews.csv"
    coverage_path = data_dir / "annotations" / "coverage.csv"
    splits_path = data_dir / "splits.json"

    # Step 1: Validate manifest
    manifest = validate_manifest(manifest_path, codebase_root, res)

    # Step 2: Validate events.csv and events.draft.csv
    approved_records = validate_events_table(events_path, manifest, res, is_draft=False)
    draft_records = validate_events_table(draft_path, manifest, res, is_draft=True)

    # Step 3: Validate reviews ledger
    validate_reviews(reviews_path, manifest, draft_records, approved_records, res)

    # Step 4: Validate coverage
    coverage = validate_coverage(coverage_path, manifest, res)

    # Step 5: Validate splits
    validate_splits(splits_path, manifest_path, manifest, res)

    # Step 6: Evaluate readiness
    evaluate_readiness(res, manifest, approved_records, draft_records, coverage)

    if require_ready and not res.is_ready_for_evaluation:
        res.errors.append(
            "Readiness check failed under --require-ready; review structural errors and pilot-readiness notes."
        )

    return res


def print_report(res: ValidationResult) -> None:
    print("=" * 65)
    print("         BASKETBALL SCOREBOARD DATASET VALIDATION REPORT        ")
    print("=" * 65)

    print(f"\n[1] DATASET STATS:")
    print(f"  - Total Videos in Manifest : {res.stats['videos_count']}")
    print(f"  - Approved Shots (events)  : {res.stats['approved_shots_count']} {res.stats['approved_by_result']}")
    print(f"  - Draft Shots (candidates) : {res.stats['draft_shots_count']} {res.stats['draft_by_result']}")
    print(f"  - Split Status             : {res.stats['split_status']}")
    print(f"  - Calibration Videos       : {res.stats['calibration_videos']}")
    print(f"  - Test Videos              : {res.stats['test_videos']}")

    print(f"\n[2] STRUCTURAL INTEGRITY:")
    if res.errors:
        print(f"  STATUS: FAILED ({len(res.errors)} error(s))")
        for err in res.errors:
            print(f"    [ERROR] {err}")
    else:
        print("  STATUS: PASSED (Schema, keys, intervals, and splits are structurally valid)")

    if res.warnings:
        print(f"\n[3] QUALITY WARNINGS ({len(res.warnings)}):")
        for warn in res.warnings:
            print(f"    [WARN]  {warn}")
    else:
        print("\n[3] QUALITY WARNINGS: None")

    print(f"\n[4] EVALUATION READINESS:")
    if res.is_ready_for_evaluation:
        print("  STATUS: READY FOR PILOT EVALUATION (not evidence of statistical generalization)")
    else:
        print(f"  STATUS: NOT READY ({len(res.readiness_notes)} pending requirement(s))")
        for note in res.readiness_notes:
            print(f"    [PENDING] {note}")

    print("=" * 65)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--codebase-root",
        type=Path,
        default=default_root,
        help="Root path of the codebase directory",
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit nonzero if dataset is not ready for pilot evaluation; sample-size target is a warning",
    )
    args = parser.parse_args()

    codebase_root = args.codebase_root.resolve()
    res = validate_dataset(codebase_root, require_ready=args.require_ready)
    print_report(res)

    return 0 if res.is_valid else 1


if __name__ == "__main__":
    sys.exit(main())
