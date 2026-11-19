"""Validate demo evidence and derive presentation fields from actual run outputs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
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


DEMO_FILES = {
    "input.mp4", "job.json", "roster.json", "match_config.json",
    "spatial_map.json", "spatial_map_status.json", "analysis/run.json",
    "analysis/web_overlay.json", "analysis/automatic_geometry.json",
    "analysis/detection/detections.jsonl",
    "analysis/tracking/tracked_observations.jsonl",
    "analysis/tracking/tracking_summary.json",
}


def verify_dashboard_demo(source: Path) -> dict[str, Any]:
    manifest = verify_bundle_manifest(source)
    if manifest is None:
        raise ValueError(f"Demo manifest missing: {source}")
    entries = {item["path"]: item for item in manifest["files"]}
    for name in sorted(DEMO_FILES):
        if name not in entries or not entries[name]["bytes"]:
            raise ValueError(f"Demo manifest missing a nonempty {name}")
    job = json.loads((source / "job.json").read_text(encoding="utf-8"))
    if (not re.fullmatch(r"[0-9a-f]{32}", job["id"])
            or job["status"] != "completed"
            or job["source_sha256"] != entries["input.mp4"]["sha256"]):
        raise ValueError("Demo job does not match the bundled video")
    return manifest


def install_dashboard_demo(source: Path, uploads: Path) -> str:
    """Install a verified editable copy once, preserving an existing demo job."""
    manifest = verify_dashboard_demo(source)
    job_id = json.loads((source / "job.json").read_text(encoding="utf-8"))["id"]
    uploads.mkdir(parents=True, exist_ok=True)
    target = uploads / job_id
    if not target.exists():
        with tempfile.TemporaryDirectory(prefix=".demo-", dir=uploads) as scratch:
            staging = Path(scratch) / job_id
            for entry in manifest["files"]:
                name = entry["path"]
                item = staging / name
                item.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / name, item)
            try:
                staging.rename(target)
            except FileExistsError:
                pass  # Another setup process installed the same demo.
    for name in sorted(DEMO_FILES):
        item = target / name
        if not item.is_file() or not item.stat().st_size:
            raise ValueError(f"Local demo is incomplete: {item}. Move {target} aside and rerun setup.bat.")
    with (target / "input.mp4").open("rb") as handle:
        video_hash = hashlib.file_digest(handle, "sha256").hexdigest()
    video_entry = next(item for item in manifest["files"] if item["path"] == "input.mp4")
    if video_hash != video_entry["sha256"]:
        raise ValueError(f"Local demo video is damaged. Move {target} aside and rerun setup.bat.")
    pointer = uploads / "demo.json"
    try:
        with pointer.open("x", encoding="utf-8") as handle:
            json.dump({"job_id": job_id}, handle)
    except FileExistsError:
        selected = json.loads(pointer.read_text(encoding="utf-8"))["job_id"]
        if not re.fullmatch(r"[0-9a-f]{32}", selected) or not (uploads / selected / "job.json").is_file():
            raise ValueError(f"Invalid demo selection: {pointer}. Move it aside and rerun setup.bat.")
    return job_id


def summarize_run(run: dict[str, Any], heatmap: dict[str, Any]) -> dict[str, Any]:
    """Expose only video, tracking and spatial run metadata."""
    counts = run.get("counts", run.get("stage_counts", {}))
    summary = {
        "status": run.get("status", "unavailable"),
        "video": Path(run.get("video_path", "")).name,
        "source_fps": run.get("video_metadata", {}).get("fps"),
        "duration_s": run.get("video_metadata", {}).get("duration_s",0),
        "pipeline_fps": run.get("timings", {}).get("pipeline_fps"),
        "frames_processed": counts.get("total_frames_read", 0),
        "court_calibrated": run.get("geometry", {}).get("status") == "calibrated",
        "heatmap_status": heatmap.get("status", "unavailable"),
        "quality_gate": run.get("quality_gate", "NOT_ACCEPTED"),
        "demo_verdict": run.get("demo_verdict", "DEMO_PARTIAL"),
    }
    return summary
