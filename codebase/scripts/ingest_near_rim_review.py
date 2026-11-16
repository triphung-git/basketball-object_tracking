#!/usr/bin/env python3
"""Ingest and validate reviewed near-rim labels for YOLO fine-tuning (Task D06 / R01)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional


def validate_and_ingest_review(
    review_json_path: Path | str,
    output_dir: Optional[Path | str] = None,
    validate_only: bool = False,
) -> Dict[str, Any]:
    review_file = Path(review_json_path).resolve()
    if not review_file.is_file():
        raise FileNotFoundError(f"Review JSON file not found: {review_file}")

    data = json.loads(review_file.read_text(encoding="utf-8"))
    frames = data.get("reviewed_frames", [])
    if not frames:
        raise ValueError("No frames found in review data")

    summary = {
        "total_frames": len(frames),
        "reviewed_count": 0,
        "visible_count": 0,
        "partially_occluded_count": 0,
        "fully_occluded_count": 0,
        "uncertain_quarantined_count": 0,
        "valid": True,
        "errors": [],
    }

    for idx, f in enumerate(frames):
        sample_id = f.get("sample_id", f"sample_{idx}")
        vis = f.get("visibility")
        bbox = f.get("ball_bbox_xyxy")

        if vis not in {"visible", "partially_occluded", "fully_occluded", "uncertain"}:
            summary["errors"].append(f"{sample_id}: Invalid visibility '{vis}'")
            summary["valid"] = False
            continue

        if vis == "uncertain":
            summary["uncertain_quarantined_count"] += 1
            if bbox is not None:
                summary["errors"].append(f"{sample_id}: Uncertain frame cannot have bbox")
                summary["valid"] = False
        elif vis == "fully_occluded":
            summary["fully_occluded_count"] += 1
            if bbox is not None:
                summary["errors"].append(f"{sample_id}: Fully occluded frame cannot have bbox")
                summary["valid"] = False
            summary["reviewed_count"] += 1
        elif vis in {"visible", "partially_occluded"}:
            if not bbox or len(bbox) != 4 or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
                summary["errors"].append(f"{sample_id}: Visible frame requires valid bbox [x1, y1, x2, y2]")
                summary["valid"] = False
            else:
                if vis == "visible":
                    summary["visible_count"] += 1
                else:
                    summary["partially_occluded_count"] += 1
                summary["reviewed_count"] += 1

    if not summary["valid"]:
        return summary

    if not validate_only and output_dir:
        out_p = Path(output_dir).resolve()
        out_p.mkdir(parents=True, exist_ok=True)
        (out_p / "ingested_manifest.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return summary


def main():
    parser = argparse.ArgumentParser(description="Ingest near-rim review labels")
    parser.add_argument("review_json", type=str, help="Path to reviewed_near_rim_labels.json")
    parser.add_argument("--output-dir", type=str, default=None, help="Directory to export ingested labels")
    parser.add_argument("--validate-only", action="store_true", help="Only validate without exporting")
    args = parser.parse_args()

    res = validate_and_ingest_review(args.review_json, args.output_dir, args.validate_only)
    print(json.dumps(res, indent=2))
    if not res["valid"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
