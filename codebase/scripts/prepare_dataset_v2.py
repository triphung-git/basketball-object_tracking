"""Dataset v2 inventory and preparation script for Automatic Stats."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

# Add src to path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from basketball_scoreboard.video import compute_file_sha256, probe_video
from basketball_scoreboard.dataset_schema import ANNOTATION_HEADERS

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("prepare_dataset_v2")

MANIFEST_HEADERS = [
    "video_id",
    "relative_path",
    "sha256",
    "width",
    "height",
    "fps",
    "nb_frames",
    "duration_s",
    "time_base",
    "is_vfr",
    "camera_group",
    "session_id",
    "source_type",
    "source_group",
    "provenance_status",
    "notes",
]


def inventory_videos(
    source_dirs: List[Path],
    codebase_root: Path,
) -> List[Dict[str, Any]]:
    """Scan directory sources for MP4 files and extract technical stream metadata."""
    found_videos = []
    seen_hashes = set()
    current = codebase_root / "data/v2/manifest.csv"
    curated = {}
    if current.is_file():
        with current.open(newline="", encoding="utf-8") as handle:
            curated = {row["sha256"]: row for row in csv.DictReader(handle)}

    for s_dir in source_dirs:
        if not s_dir.is_dir():
            continue
        for video_file in sorted(s_dir.glob("*.mp4")):
            file_hash = compute_file_sha256(video_file)
            if file_hash in seen_hashes:
                logger.warning("Duplicate content detected for %s; skipping", video_file.name)
                continue
            seen_hashes.add(file_hash)

            rel_path = video_file.resolve().relative_to(codebase_root.resolve())
            meta = probe_video(video_file)

            # Filename alone is not evidence of session, camera or eligibility.
            session_id = camera_group = "unknown"
            source_type = "needs_review"

            previous = curated.get(file_hash, {})

            found_videos.append({
                "video_id": previous.get("video_id", "video_" + file_hash[:16]),
                "relative_path": str(rel_path).replace("\\", "/"),
                "sha256": file_hash,
                "width": meta.width,
                "height": meta.height,
                "fps": round(meta.fps, 4),
                "nb_frames": meta.nb_frames,
                "duration_s": round(meta.duration_s, 4),
                "time_base": meta.time_base,
                "is_vfr": meta.is_vfr,
                "camera_group": previous.get("camera_group", camera_group),
                "session_id": previous.get("session_id", session_id),
                "source_type": previous.get("source_type", source_type),
                "source_group": previous.get("source_group", "unknown"),
                "provenance_status": previous.get("provenance_status", "pending"),
                "notes": previous.get("notes", f"Technical inventory; provenance needs review; {meta.width}x{meta.height}"),
            })

    return found_videos


def write_manifest(manifest_path: Path, rows: List[Dict[str, Any]], force: bool = False) -> None:
    if manifest_path.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing manifest: {manifest_path}. Specify a new proposal --output path."
        )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_HEADERS)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    logger.info("Wrote %d video entries to %s", len(rows), manifest_path)


def initialize_v2_templates(v2_dir: Path) -> None:
    """Create template files for data/v2/ if not already present."""
    v2_dir.mkdir(parents=True, exist_ok=True)
    anno_dir = v2_dir / "annotations"
    anno_dir.mkdir(parents=True, exist_ok=True)

    # 1. roster.csv
    roster_path = v2_dir / "roster.csv"
    if not roster_path.exists():
        roster_path.write_text(
            "team_id,player_id,jersey_number,name,is_active\n",
            encoding="utf-8",
        )

    # 2. ruleset.json
    ruleset_path = v2_dir / "ruleset.json"
    if not ruleset_path.exists():
        ruleset_data = {
            "version": "2.0.0",
            "rule_profile": "FIBA 3x3 Official Rules 2024",
            "statisticians_manual": "FIBA Statisticians' Manual 2024",
            "source_urls": [
                "https://about.fiba.basketball/en/our-sport/3x3-basketball",
                "https://about.fiba.basketball/en/fiba-game-officials/statisticians",
            ],
            "spec_document": "docs/specs/rules-v2.md",
            "point_values": {"inside_arc": 1, "outside_arc": 2, "free_throw": 1},
            "matching_windows_s": {
                "score_window_s": 0.50,
                "rebound_window_s": 0.75,
                "assist_window_s": 0.75,
            },
            "performance_targets": {
                "precision_target": 0.95,
                "recall_target": 0.90,
            },
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "review_status": "draft",
            "applicability_status": "pending",
            "protocol_status": "draft",
            "roster_status": "pending",
        }
        ruleset_path.write_text(json.dumps(ruleset_data, indent=2) + "\n", encoding="utf-8")

    # 3. splits.json
    splits_path = v2_dir / "splits.json"
    if not splits_path.exists():
        splits_data = {
            "version": "2.0.0-draft",
            "status": "draft",
            "description": "V2 dataset split proposal preserving v1 holdout isolation",
            "proposed_split": {
                "calibration": {
                    "video_ids": [],
                    "notes": "Assign stable manifest IDs only after development-source review"
                },
                "holdout_v1_preserved": {
                    "video_ids": [],
                    "notes": "Populate using v1 content-hash mapping after inventory; never tune on preserved holdout"
                },
                "test": {
                    "video_ids": [],
                    "notes": "Reserved for newly provided dual-team footage pending user review"
                }
            },
            "created_utc": datetime.now(timezone.utc).isoformat(),
        }
        splits_path.write_text(json.dumps(splits_data, indent=2) + "\n", encoding="utf-8")

    # 4. Annotation files
    anno_templates = {name + ".csv": header + "\n" for name, header in ANNOTATION_HEADERS.items()}
    for filename, header in anno_templates.items():
        file_path = anno_dir / filename
        if not file_path.exists():
            file_path.write_text(header, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codebase-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=None, help="Custom manifest output path")
    parser.add_argument("--force", action="store_true", help="Deprecated compatibility flag; never permits overwrite")
    args = parser.parse_args()

    cb_root = args.codebase_root.resolve()
    v2_dir = cb_root / "data" / "v2"
    source_dirs = [cb_root / "assets_test", cb_root / "data" / "raw"]

    manifest_out = ((cb_root / args.output).resolve() if args.output else v2_dir / "manifest.csv")
    if not any(manifest_out.is_relative_to(base) for base in (v2_dir, cb_root / "outputs")):
        parser.error("Manifest proposal must be inside data/v2 or outputs; v1 data is protected")
    if manifest_out.exists():
        parser.error("Refusing to overwrite existing manifest, even with --force; use a new proposal path")
    split_file = v2_dir / "splits.json"
    if split_file.exists() and json.loads(split_file.read_text(encoding="utf-8")).get("status") == "locked":
        parser.error("Dataset v2 locked; use a reviewed revision workflow")

    videos = inventory_videos(source_dirs, cb_root)
    write_manifest(manifest_out, videos, force=args.force)
    initialize_v2_templates(v2_dir)
    print(f"Dataset v2 preparation complete. Processed {len(videos)} videos into {v2_dir}")


if __name__ == "__main__":
    main()
