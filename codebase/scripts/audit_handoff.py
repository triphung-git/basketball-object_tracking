"""Read-only audit of locked media, annotations and archived smoke evidence.

Writes a new JSON snapshot; never reads .env, runs models or uploads media.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import subprocess

from validate_dataset import compute_file_sha256, validate_dataset


def audit(root, archived_smoke):
    validation = validate_dataset(root, require_ready=True)
    data = root / "data"
    with (data / "manifest.csv").open(newline="", encoding="utf-8") as handle:
        manifest = list(csv.DictReader(handle))
    with (data / "annotations/events.csv").open(newline="", encoding="utf-8") as handle:
        events = list(csv.DictReader(handle))
    timebases = []
    for row in manifest:
        response = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_packets",
            "-show_entries", "stream=avg_frame_rate,r_frame_rate,start_time,duration,nb_frames:packet=pts_time",
            "-of", "json", str((root / row["relative_path"]).resolve()),
        ], capture_output=True, text=True, check=True, timeout=90)
        probe = json.loads(response.stdout)
        pts = sorted(float(packet["pts_time"]) for packet in probe.get("packets", []) if "pts_time" in packet)
        steps = [b - a for a, b in zip(pts, pts[1:]) if b > a]
        variable = bool(steps) and max(steps) - min(steps) > 0.001
        label_checks = []
        for event in events:
            if event["video_id"] != row["video_id"] or event["result"] != "made":
                continue
            label_time = float(event["score_time_s"])
            # Diagnostic only: labels are never changed by this comparison.
            estimated_index = round(label_time * float(row["fps"]))
            label_checks.append({"shot_id": event["shot_id"], "label_time_s": label_time,
                                 "index_from_average_fps": estimated_index,
                                 "pts_of_that_index_s": pts[estimated_index] - pts[0] if estimated_index < len(pts) else None})
        timebases.append({"video_id": row["video_id"], "streams": probe.get("streams", []),
                          "packet_count": len(pts), "variable_pts_spacing": variable,
                          "min_step_s": min(steps) if steps else None, "max_step_s": max(steps) if steps else None,
                          "timestamp_rule": "Use normalized presentation timestamp; average FPS is not a VFR clock.",
                          "label_frame_diagnostics": label_checks})
    smoke = json.loads((archived_smoke / "smoke.json").read_text(encoding="utf-8"))
    samples = smoke["samples"]
    invalid_detections = 0
    for sample in samples:
        width, height = sample["original_wh"]
        for detection in sample["detections"]:
            x1, y1, x2, y2 = detection["xyxy"]
            invalid_detections += not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height
                                       and smoke["class_mapping"][str(detection["class_id"])] == detection["class_name"])
    return {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_valid": validation.is_valid, "pilot_ready": validation.is_ready_for_evaluation,
        "errors": validation.errors, "warnings": validation.warnings, "readiness_notes": validation.readiness_notes,
        "stats": validation.stats,
        "frozen_file_sha256": {str(path.relative_to(root)): compute_file_sha256(path) for path in
                               [data / "manifest.csv", data / "splits.json", *sorted((data / "annotations").glob("*.csv"))]},
        "timebases": timebases,
        "archived_smoke": {"path": str(archived_smoke), "status": smoke["status"], "model_id": smoke["model_id"],
                           "samples": len(samples), "overlays_present": sum((archived_smoke / s["overlay"]).is_file() for s in samples),
                           "detections": dict(Counter(d["class_name"] for s in samples for d in s["detections"])),
                           "invalid_detections": invalid_detections,
                           "median_model_call_ms_recomputed": statistics.median(s["model_call_ms"] for s in samples)},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codebase-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refusing to overwrite existing audit")
    root = args.codebase_root.resolve()
    report = audit(root, root / "outputs/smoke-20261031-215143")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"dataset_valid": report["dataset_valid"], "pilot_ready": report["pilot_ready"],
                      "variable_pts_videos": [r["video_id"] for r in report["timebases"] if r["variable_pts_spacing"]],
                      "archived_smoke": report["archived_smoke"]}, indent=2))
