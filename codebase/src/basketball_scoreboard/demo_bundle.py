"""Validate demo evidence and derive presentation fields from actual run outputs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def verify_bundle_manifest(run_dir: Path) -> dict[str, Any] | None:
    """Reject missing, changed or unsafe manifest entries before serving a bundle."""
    root = Path(run_dir).resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return None  # Plain pipeline output directories do not have a manifest.
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest["files"]
    if not isinstance(entries, list) or len(entries) != manifest["total_files"]:
        raise ValueError("Bundle manifest file count mismatch")
    seen = set()
    total_bytes = 0
    for entry in entries:
        path = (root / entry["path"]).resolve()
        if path == root or not path.is_relative_to(root) or path in seen:
            raise ValueError(f"Unsafe or duplicate bundle path: {entry['path']}")
        seen.add(path)
        if not path.is_file() or path.stat().st_size != entry["bytes"]:
            raise ValueError(f"Bundle missing file or size mismatch: {entry['path']}")
        with path.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        if digest != entry["sha256"]:
            raise ValueError(f"Bundle SHA-256 mismatch: {entry['path']}")
        total_bytes += entry["bytes"]
    if total_bytes != manifest["total_bytes"]:
        raise ValueError("Bundle manifest byte count mismatch")
    return manifest


def summarize_run(run: dict[str, Any], heatmap: dict[str, Any]) -> dict[str, Any]:
    """Keep provenance intact; expose only measured/compiled statistics."""
    summary = dict(run)
    totals = run.get("boxscore_totals", {}).get("match_totals", {})
    counts = run.get("stage_counts", {})
    summary.update({
        "video": Path(run.get("video_path", "")).name,
        "source_fps": run.get("video_metadata", {}).get("fps"),
        "pipeline_fps": run.get("timings", {}).get("pipeline_fps"),
        "frames_processed": counts.get("total_frames_read", 0),
        "shots_confirmed": counts.get("confirmed_shots", 0),
        "points_total": totals.get("points", 0),
        "rebounds_total": totals.get("rebounds", 0),
        "assists_total": totals.get("assists", 0),
        "boxscore": run.get("boxscore_totals", {}),
        "court_calibrated": run.get("geometry", {}).get("status") == "calibrated",
        "heatmap_mass_person_seconds": heatmap.get("total_player_seconds", 0.0),
    })
    summary.setdefault("quality_gate", "NOT_ACCEPTED")
    summary.setdefault("demo_verdict", "DEMO_PARTIAL")
    return summary
