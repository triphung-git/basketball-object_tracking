"""Install the versioned full match demo while preserving editable job state."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from urllib.request import urlopen
from zipfile import ZipFile

from .demo_bundle import verify_bundle_manifest


FULL_MATCH_JOB_ID = "d21759aefdd948ff967fc5fe2dadd2a8"
FULL_MATCH_VIDEO_SHA256 = "ae83eb316347e0925263c93ca00d8a145ebbc961857415904ffd7fd049c1d99e"
FULL_MATCH_VIDEO_BYTES = 858151732
FULL_MATCH_FILES = {
    "input.mp4", "job.json", "roster.json", "match_config.json",
    "spatial_map.json", "spatial_map_status.json", "analysis/run.json",
    "analysis/web_overlay.json", "analysis/heatmap_summary.json",
    "analysis/detections.jsonl", "analysis/tracked_observations.jsonl",
}


def full_match_present(directory: Path) -> bool:
    """Check the files needed to open the demo, without hashing on web requests."""
    try:
        job = json.loads((directory / "job.json").read_text(encoding="utf-8"))
        return (
            job["id"] == FULL_MATCH_JOB_ID
            and job["status"] == "completed"
            and job["source_sha256"] == FULL_MATCH_VIDEO_SHA256
            and (directory / "input.mp4").stat().st_size == FULL_MATCH_VIDEO_BYTES
            and all((directory / name).is_file() and (directory / name).stat().st_size
                    for name in FULL_MATCH_FILES)
        )
    except (OSError, ValueError, KeyError, TypeError):
        return False


def download_full_match(release: dict, destination: Path) -> None:
    size = release["bytes"]
    digest = hashlib.sha256()
    received = 0
    report_at = 0
    with urlopen(release["url"], timeout=60) as response, destination.open("wb") as out:
        while chunk := response.read(1024 * 1024):
            received += len(chunk)
            if received > size:
                raise ValueError("Full match download exceeds the expected size")
            digest.update(chunk)
            out.write(chunk)
            if received >= report_at:
                print(f"  [*] Full match download: {received * 100 // size}%", flush=True)
                report_at = received + 128 * 1024 * 1024
    if received != size or digest.hexdigest() != release["sha256"]:
        raise ValueError("Full match download failed size or SHA-256 verification")


def install_full_match_demo(uploads: Path, release: dict) -> str:
    target = uploads / FULL_MATCH_JOB_ID
    if not target.exists():
        uploads.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".full-match-", dir=uploads) as scratch:
            archive_path = Path(scratch) / "download.zip"
            staging = Path(scratch) / FULL_MATCH_JOB_ID
            download_full_match(release, archive_path)
            with ZipFile(archive_path) as archive:
                names = archive.namelist()
                expected = FULL_MATCH_FILES | {"manifest.json"}
                if len(names) != len(expected) or set(names) != expected:
                    raise ValueError("Unexpected files in the full match archive")
                for name in names:
                    item = staging / name
                    item.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(name) as source, item.open("xb") as out:
                        shutil.copyfileobj(source, out, length=1024 * 1024)
            manifest = verify_bundle_manifest(staging)
            if (not manifest or {item["path"] for item in manifest["files"]} != FULL_MATCH_FILES
                    or not full_match_present(staging)):
                raise ValueError("Full match archive does not contain the expected job")
            video_entry = next(item for item in manifest["files"] if item["path"] == "input.mp4")
            if video_entry["sha256"] != FULL_MATCH_VIDEO_SHA256:
                raise ValueError("Full match archive contains a different video")
            (staging / "manifest.json").unlink()  # The installed job is editable.
            try:
                staging.rename(target)
                return FULL_MATCH_JOB_ID
            except OSError:
                if not target.exists():
                    raise

    # The saved roster and projections may have been edited after installation.
    if full_match_present(target):
        with (target / "input.mp4").open("rb") as video:
            if hashlib.file_digest(video, "sha256").hexdigest() == FULL_MATCH_VIDEO_SHA256:
                return FULL_MATCH_JOB_ID
    raise ValueError(f"Local full match demo is incomplete or damaged. Move {target} aside and rerun setup.bat.")
