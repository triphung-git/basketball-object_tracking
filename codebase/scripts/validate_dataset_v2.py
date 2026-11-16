"""Fail-closed validation and separate tooling/data/locked gates for dataset v2."""
from __future__ import annotations
import argparse
from collections import Counter
import csv
from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from basketball_scoreboard.video import compute_file_sha256
from basketball_scoreboard.dataset_schema import ANNOTATION_HEADERS, ID_COLUMNS


@dataclass
class ValidationV2Result:
    is_structurally_valid: bool = False
    is_tooling_ready: bool = False
    is_data_ready: bool = False
    is_locked_ready: bool = False
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    readiness_notes: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    file_hashes: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def validate_dataset_v2(codebase_root, v2_subdir="data/v2", require_data_ready=False, require_locked=False):
    root = Path(codebase_root).resolve()
    data = (root / v2_subdir).resolve()
    result = ValidationV2Result()
    if not data.is_relative_to(root):
        result.errors.append("Dataset directory escapes codebase")
        return result

    def error(message):
        result.errors.append(message)

    def read_csv(path, columns):
        if not path.is_file():
            error(f"Missing required file: {path.name}")
            return []
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames) or not set(columns).issubset(reader.fieldnames):
                error(f"{path.name}: missing/duplicate schema columns")
                return []
            rows = []
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    error(f"{path.name}: malformed CSV row")
                    continue
                rows.append({k: v.strip() for k, v in row.items()})
            return rows

    def read_json(path):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError
            return value
        except (OSError, ValueError):
            error(f"{path.name}: missing or invalid JSON object")
            return {}

    def number(value, label):
        try:
            parsed = float(value)
            if not math.isfinite(parsed):
                raise ValueError
            return parsed
        except (TypeError, ValueError):
            error(f"{label}: non-finite/non-numeric timestamp or coordinate")
            return None

    def index(rows, column, table):
        indexed = {}
        for row in rows:
            key = row.get(column, "")
            if not key or key in indexed:
                error(f"{table}: missing/duplicate {column}")
            else:
                indexed[key] = row
        return indexed

    manifest_rows = read_csv(data / "manifest.csv",
        ["video_id", "relative_path", "sha256", "width", "height", "fps", "duration_s", "session_id", "camera_group"])
    manifest = index(manifest_rows, "video_id", "manifest.csv")
    durations = {}
    for vid, row in manifest.items():
        path = (root / row["relative_path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            error(f"manifest.csv {vid}: media missing/path escapes root")
        else:
            sha = row["sha256"]
            if len(sha) != 64 or compute_file_sha256(path) != sha:
                error(f"manifest.csv {vid}: sha256 mismatch or missing")
        duration = number(row["duration_s"], f"manifest.csv {vid}")
        durations[vid] = duration if duration is not None and duration > 0 else 0
        if not durations[vid]:
            error(f"manifest.csv {vid}: invalid duration_s")
        for field_name in ("width", "height", "fps"):
            value = number(row[field_name], f"manifest.csv {vid}/{field_name}")
            if value is None or value <= 0:
                error(f"manifest.csv {vid}: invalid {field_name}")

    roster = index(read_csv(data / "roster.csv", ["team_id", "player_id", "jersey_number", "name", "is_active"]), "player_id", "roster.csv")
    teams = {r["team_id"] for r in roster.values()}
    jerseys = set()
    for player, row in roster.items():
        key = (row["team_id"], row["jersey_number"])
        if not all(key) or key in jerseys or row["is_active"].lower() not in {"true", "false"}:
            error(f"roster.csv {player}: empty/duplicate team-jersey or invalid is_active")
        jerseys.add(key)

    rules = read_json(data / "ruleset.json")
    split = read_json(data / "splits.json")
    if not rules.get("rule_profile") or rules.get("point_values") != {"inside_arc": 1, "outside_arc": 2, "free_throw": 1}:
        error("ruleset.json: missing profile or invalid 3x3 point_values")
    status = split.get("status", "draft")
    if status not in {"draft", "proposed", "locked"}:
        error("splits.json: invalid status")
    partitions = split.get("proposed_split", {})
    if not isinstance(partitions, dict):
        error("splits.json: invalid partitions")
        partitions = {}
    membership, owners = {}, {}
    for name, partition in partitions.items():
        ids = partition.get("video_ids", []) if isinstance(partition, dict) else None
        if not isinstance(ids, list) or not all(isinstance(v, str) for v in ids):
            error(f"splits.json {name}: invalid video IDs")
            continue
        for vid in ids:
            if vid not in manifest or vid in membership:
                error(f"splits.json: unknown/duplicate video '{vid}'")
                continue
            membership[vid] = name
            row = manifest[vid]
            for key in ("session_id", "camera_group", "source_group", "sha256"):
                value = row.get(key)
                if value and value != "unknown":
                    owner_key = (key, value)
                    if owner_key in owners and owners[owner_key] != name:
                        error(f"splits.json leakage: {key} '{value}' crosses partitions")
                    owners[owner_key] = name
    # Preserve v1 holdout by content, even if video IDs or names are changed.
    v1_split_path = root / "data/splits.json"
    v1_manifest_path = root / "data/manifest.csv"
    if v1_split_path.is_file() and v1_manifest_path.is_file():
        v1 = read_json(v1_split_path)
        protected_ids = set(v1.get("proposed_split", {}).get("test", {}).get("video_ids", []))
        protected = {r["sha256"] for r in read_csv(v1_manifest_path, ["video_id", "sha256"]) if r["video_id"] in protected_ids}
        for vid, name in membership.items():
            if name in {"calibration", "validation"} and manifest[vid]["sha256"] in protected:
                error(f"splits.json: preserved v1 holdout {vid} cannot enter development without reviewed revision")

    tables = {name: read_csv(data / "annotations" / (name + ".csv"), header.split(","))
              for name, header in ANNOTATION_HEADERS.items()}
    indices = {name: index(rows, ID_COLUMNS[name], name + ".csv") for name, rows in tables.items() if name != "reviews"}
    reviews = {}
    for row in tables["reviews"]:
        key = (row["table_name"], row["record_id"])
        if key in reviews or key[0] not in indices or key[1] not in indices.get(key[0], {}):
            error(f"reviews.csv: duplicate or dangling review {key}")
        state = row["review_status"]
        if state not in {"draft", "approved", "rejected", "needs_review"}:
            error(f"reviews.csv: invalid review_status for {key}")
        if state == "approved":
            try:
                stamp = datetime.fromisoformat(row["reviewed_utc"].replace("Z", "+00:00"))
                if not row["reviewer"] or stamp.tzinfo is None:
                    raise ValueError
            except ValueError:
                error(f"reviews.csv: approved event missing reviewer or reviewed_utc for {key}")
        reviews[key] = state

    times = {}
    def actor(row, field, label, optional=False):
        pid = row.get(field, "")
        if optional and pid in {"", "unresolved"}:
            return
        if pid not in roster:
            error(f"{label}: {field} not in roster")
        elif row.get("team_id") != roster[pid]["team_id"]:
            error(f"{label}: actor/team mismatch")

    def linked(row, field, target, label):
        ref = row.get(field)
        if not ref or ref not in indices[target]:
            error(f"{label}: {field} '{ref}' not in {target}.csv")
            return None
        other = indices[target][ref]
        if other["video_id"] != row["video_id"]:
            error(f"{label}: cross-video {field}")
        return other

    for table, rows in indices.items():
        for rid, row in rows.items():
            vid = row["video_id"]
            label = f"{table}.csv {rid}"
            if vid not in manifest:
                error(f"{label}: video_id not in manifest")
            parsed = {}
            for name, value in row.items():
                if name.endswith("_s") and value:
                    parsed[name] = number(value, label + "/" + name)
                    if parsed[name] is not None and not (0 <= parsed[name] <= durations.get(vid, 0) + 0.01):
                        error(f"{label}: out-of-range timestamp {name}")
            times[(table, rid)] = parsed
            for first, last in (("start_time_s", "end_time_s"), ("release_time_s", "receive_time_s"), ("release_time_s", "outcome_time_s")):
                if first in row and last in row:
                    if not row[first] or not row[last] or parsed.get(first) is None or parsed.get(last) is None or parsed[last] < parsed[first]:
                        error(f"{label}: invalid release/outcome timing or interval")
                    elif first == "start_time_s" and parsed[last] <= parsed[first]:
                        error(f"{label}: invalid interval")
            required_times = {"rebounds": "rebound_time_s", "assists": "assist_time_s", "player_positions": "time_s"}
            if table in required_times and not row[required_times[table]]:
                error(f"{label}: missing event timestamp")

            if table == "shots":
                actor(row, "shooter_id", label, optional=row.get("shooter_id") == "unresolved")
                if row["team_id"] not in teams:
                    error(f"{label}: unknown team")
                if row["shot_type"] not in {"1pt", "2pt", "free_throw"} or row["result"] not in {"made", "miss", "uncertain"}:
                    error(f"{label}: invalid shot_type/result")
                if row["result"] == "made":
                    score = parsed.get("score_time_s")
                    release, outcome = parsed.get("release_time_s"), parsed.get("outcome_time_s")
                    if score is None or release is None or outcome is None or not (release <= score <= outcome):
                        error(f"{label}: made shot requires score_time_s within release/outcome")
                elif row["score_time_s"]:
                    error(f"{label}: non-made shot has score_time_s")
            elif table == "rebounds":
                shot = linked(row, "shot_id", "shots", label)
                rtype = row["rebound_type"]
                if rtype not in {"offensive", "defensive", "team_rebound"}:
                    error(f"{label}: invalid rebound_type")
                if row["team_id"] not in teams:
                    error(f"{label}: unknown team")
                if rtype == "team_rebound":
                    if row["actor_id"]:
                        error(f"{label}: team_rebound must not have individual actor_id")
                else:
                    actor(row, "actor_id", label)
                if shot:
                    if shot["result"] != "miss":
                        error(f"{label}: rebound linked to non-missed shot")
                    if row["team_id"] == shot["team_id"] and rtype == "defensive" or row["team_id"] != shot["team_id"] and rtype == "offensive":
                        error(f"{label}: rebound subtype/team contradicts shooter")
                    reb_t = parsed.get("rebound_time_s")
                    shot_t = times.get(("shots", row["shot_id"]), {}).get("outcome_time_s")
                    if reb_t is not None and shot_t is not None and reb_t < shot_t:
                        error(f"{label}: rebound precedes shot outcome")
            elif table == "passes":
                actor(row, "passer_id", label)
                actor(row, "receiver_id", label, optional=row["outcome"] != "completed")
                if row["passer_id"] == row["receiver_id"] or row["outcome"] not in {"completed", "deflected", "turnover", "uncertain"}:
                    error(f"{label}: invalid pass actors/outcome")
            elif table == "assists":
                passed = linked(row, "pass_id", "passes", label)
                shot = linked(row, "shot_id", "shots", label)
                actor(row, "passer_id", label)
                actor(row, "scorer_id", label)
                if row["passer_id"] == row["scorer_id"]:
                    error(f"{label}: passer and scorer cannot be the same")
                if row["eligibility"] not in {"eligible", "ineligible", "uncertain"}:
                    error(f"{label}: invalid eligibility")
                if shot and passed:
                    if row["passer_id"] != passed["passer_id"] or row["scorer_id"] != passed["receiver_id"] or row["scorer_id"] != shot["shooter_id"]:
                        error(f"{label}: assist/pass/shot actor mismatch")
                    if row["team_id"] != passed["team_id"] or row["team_id"] != shot["team_id"]:
                        error(f"{label}: assist/pass/shot team mismatch")
                    if row["eligibility"] == "eligible" and shot["result"] != "made":
                        error(f"{label}: eligible assist linked to non-made shot")
                    pass_t = times.get(("passes", row["pass_id"]), {})
                    shot_t = times.get(("shots", row["shot_id"]), {})
                    if pass_t.get("receive_time_s") is not None and shot_t.get("release_time_s") is not None and pass_t["receive_time_s"] > shot_t["release_time_s"]:
                        error(f"{label}: pass occurs after shot")
                    if parsed.get("assist_time_s") is not None and pass_t.get("release_time_s") is not None and abs(parsed["assist_time_s"] - pass_t["release_time_s"]) > 0.01:
                        error(f"{label}: assist_time_s must reference pass release")
            elif table == "coverage":
                if row["status"] not in {"fully_reviewed", "excluded", "needs_review", "unreviewed", "uncertain"}:
                    error(f"{label}: invalid coverage status")
            elif table in {"player_positions", "identities", "ball_control"}:
                optional = table == "ball_control" and row["state"] != "controlled"
                actor(row, "player_id", label, optional=optional)
                if table == "player_positions":
                    coordinates = {}
                    for coordinate in ("x_image", "y_image"):
                        coordinates[coordinate] = number(row[coordinate], label + "/" + coordinate)
                    if vid in manifest:
                        for coordinate, dimension in (("x_image", "width"), ("y_image", "height")):
                            limit = number(manifest[vid][dimension], label + "/" + dimension)
                            value = coordinates[coordinate]
                            if value is not None and limit is not None and not 0 <= value <= limit:
                                error(f"{label}: image coordinate outside original frame")
                    if bool(row["x_court"]) != bool(row["y_court"]):
                        error(f"{label}: court coordinates require both x and y")
                    for coordinate in ("x_court", "y_court"):
                        if row[coordinate]:
                            number(row[coordinate], label + "/" + coordinate)
                if table == "ball_control" and row["state"] not in {"controlled", "free", "pass", "shot", "loose", "unknown"}:
                    error(f"{label}: invalid control state")

    spans = {}
    for rid, row in indices["coverage"].items():
        parsed = times[("coverage", rid)]
        start, end = parsed.get("start_time_s"), parsed.get("end_time_s")
        if start is not None and end is not None:
            spans.setdefault(row["video_id"], []).append((start, end, row["status"]))
    for vid, intervals in spans.items():
        intervals.sort()
        if any(left[1] > right[0] + 1e-6 for left, right in zip(intervals, intervals[1:])):
            error(f"coverage.csv: overlapping intervals for {vid}")

    approved = {table: [r for rid, r in indexed.items() if reviews.get((table, rid)) == "approved"]
                for table, indexed in indices.items()}
    counts = {table: len(rows) for table, rows in approved.items()}
    eligible_assists = sum(r["eligibility"] == "eligible" for r in approved["assists"])
    result.stats = {"videos_count": len(manifest), "players_count": len(roster), "teams_count": len(teams),
                    "shots_count": len(indices["shots"]), "approved_shots_count": counts["shots"],
                    "rebounds_count": len(indices["rebounds"]), "approved_rebounds_count": counts["rebounds"],
                    "assists_count": len(indices["assists"]), "approved_assists_count": eligible_assists,
                    "split_status": status, "approved_by_table": counts}
    for table, target in (("shots", 50), ("rebounds", 30), ("assists", 30)):
        positives = eligible_assists if table == "assists" else counts[table]
        if positives < target:
            result.warnings.append(f"Pilot {table}: {positives} approved rows < collection target {target}")

    notes = result.readiness_notes
    if len(teams) < 2 or not roster or rules.get("roster_status") != "approved":
        notes.append("Real dual-team roster is not approved; sample rows are not identity ground truth")
    if rules.get("review_status") != "approved" or rules.get("applicability_status") != "confirmed":
        notes.append("Rules/protocol applicability for the competition awaits user confirmation")
    if rules.get("protocol_status") != "approved":
        notes.append("Evaluation protocol awaits explicit approval before holdout evaluation")
    for table in ("player_positions", "identities", "ball_control", "passes", "shots", "rebounds"):
        if not counts[table]:
            notes.append(f"Zero approved {table} in dataset v2")
    if not eligible_assists:
        notes.append("Zero approved eligible assists in dataset v2")
    if not any(r["eligibility"] == "ineligible" for r in approved["assists"]):
        notes.append("No approved assist-negative controls")
    for table, fields in (("rebounds", {"shot_id": "shots"}),
                          ("assists", {"shot_id": "shots", "pass_id": "passes"})):
        for row in approved[table]:
            for ref, target in fields.items():
                if reviews.get((target, row[ref])) != "approved":
                    notes.append(f"Approved {table} depends on unapproved {target}/{row[ref]}")
    for split_name in ("calibration", "test"):
        ids = {vid for vid, name in membership.items() if name == split_name}
        if not ids:
            notes.append(f"{split_name} split is empty")
        selected = [r for r in approved["shots"] if r["video_id"] in ids]
        if not {"made", "miss"}.issubset({r["result"] for r in selected}):
            notes.append(f"{split_name} requires approved made/miss shots")
        for table in ("rebounds", "assists"):
            if not any(r["video_id"] in ids and (table != "assists" or r["eligibility"] == "eligible") for r in approved[table]):
                notes.append(f"{split_name} has no approved positive {table}")
        for vid in ids:
            row = manifest[vid]
            if (row["session_id"] in {"", "unknown"} or row["camera_group"] in {"", "unknown"}
                    or row.get("source_group", "unknown") in {"", "unknown"}
                    or row.get("provenance_status") != "confirmed"):
                notes.append(f"{vid}: provenance not confirmed")
            cursor = 0.0
            for start, end, state in sorted(spans.get(vid, [])):
                if start > cursor + 0.01 or state in {"unreviewed", "needs_review", "uncertain"}:
                    notes.append(f"{vid}: incomplete reviewed/excluded coverage")
                cursor = max(cursor, end)
            if any(r["video_id"] == vid and r["status"] in {"fully_reviewed", "excluded"}
                   and reviews.get(("coverage", rid)) != "approved" for rid, r in indices["coverage"].items()):
                notes.append(f"{vid}: reviewed/excluded coverage lacks approved review ledger entry")
            if cursor < durations[vid] - 0.01:
                notes.append(f"{vid}: coverage does not reach video end")
            for table in ("shots", "rebounds", "assists"):
                for rid, event in indices[table].items():
                    if event["video_id"] != vid:
                        continue
                    if reviews.get((table, rid)) != "approved":
                        notes.append(f"{table}/{rid}: unapproved event in selected split")
                    values = list(times[(table, rid)].values())
                    if values and all(v is not None for v in values) and not any(s <= min(values) and e >= max(values) and st == "fully_reviewed" for s, e, st in spans.get(vid, [])):
                        notes.append(f"{table}/{rid}: event outside fully reviewed coverage")

    files = [data / "manifest.csv", data / "roster.csv", data / "ruleset.json", data / "splits.json",
             *[(data / "annotations" / (name + ".csv")) for name in ANNOTATION_HEADERS]]
    for path in files:
        if path.is_file():
            result.file_hashes[path.relative_to(root).as_posix()] = compute_file_sha256(path)
    if status == "locked":
        lock = read_json(data / "lock.json")
        hashes = lock.get("files", {})
        for path in files:
            expected = hashes.get(path.relative_to(data).as_posix())
            if not expected or not path.is_file() or compute_file_sha256(path) != expected:
                error(f"Locked fingerprint mismatch/missing: {path.name}")
    else:
        notes.append("Dataset split is not locked")
    result.is_structurally_valid = not result.errors
    result.is_tooling_ready = result.is_structurally_valid and bool(manifest)
    result.is_data_ready = result.is_structurally_valid and not any(n != "Dataset split is not locked" for n in notes)
    result.is_locked_ready = result.is_data_ready and status == "locked"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codebase-root", type=Path, default=ROOT)
    parser.add_argument("--v2-subdir", type=str, default="data/v2", help="Subdirectory relative to codebase root containing dataset")
    parser.add_argument("--require-tooling-ready", action="store_true")
    parser.add_argument("--require-data-ready", action="store_true")
    parser.add_argument("--require-locked", action="store_true")
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    result = validate_dataset_v2(args.codebase_root, v2_subdir=args.v2_subdir)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        with args.output_json.open("w", encoding="utf-8") as handle:
            json.dump(result.to_dict(), handle, indent=2)
    print(json.dumps(result.to_dict(), indent=2))
    if not result.is_structurally_valid:
        return 1
    if args.require_tooling_ready and not result.is_tooling_ready:
        return 4
    if args.require_locked and not result.is_locked_ready:
        return 3
    if args.require_data_ready and not result.is_data_ready:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
