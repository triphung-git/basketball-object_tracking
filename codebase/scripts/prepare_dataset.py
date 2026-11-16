"""Prepare dataset manifest and provenance records for basketball tracking evaluation.

Scans raw video sources, probes video stream characteristics using ffprobe/cv2,
computes cryptographic SHA-256 fingerprints, and outputs data/manifest.csv.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List, Optional


KNOWN_METADATA_PRESETS: Dict[str, Dict[str, str]] = {
    "c8e1ac7c23063bb26d238afb76fe0d24900cb7459950b23ccddd5583046a5724": {
        "video_id": "clip01",
        "camera_id": "cam_outdoor_night_01",
        "session_id": "session_night_court_01",
        "conditions": "night_outdoor_multi_occluded",
        "scoring_eligibility": "detection_smoke_only",
        "notes": "Night game, artificial floodlights, multiple players, small ball, severe occlusions. Suitable for detection calibration/stress-test; high risk of occluded trajectory for fixed scoring.",
    },
    "3ed25e1b246ccebbe7904d76a22fbea65ebfcb86701499417cd52962f1fc4c26": {
        "video_id": "clip02",
        "camera_id": "cam_outdoor_day_01",
        "session_id": "session_day_solo_01",
        "conditions": "day_outdoor_solo_static",
        "scoring_eligibility": "scoring_eligible",
        "notes": "Daytime, outdoor court, single player in blue tank top, fixed camera angle, clear view of backboard and rim. Primary candidate for fixed ROI scoring evaluation.",
    },
    "affa310504ee97add6b15b3036d568c7930efb357fc55b40e50c13968b04b1d8": {
        "video_id": "clip03",
        "camera_id": "cam_outdoor_day_handheld_01",
        "session_id": "session_day_courtyard_01",
        "conditions": "day_outdoor_multi_moving_cam",
        "scoring_eligibility": "detection_smoke_only",
        "notes": "Daytime, handheld moving camera with pan/zoom/orbit; hoop position moves significantly across frame and exits frame. Excluded from fixed-ROI scoring evaluation.",
    },
    "ae789418b89cfcf868a546eb0a5ce502497bb6d2b61af252978038d7cf8af3c4": {
        "video_id": "clip04",
        "camera_id": "cam_broadcast_court_01",
        "session_id": "session_u18_3x3_tournament_01",
        "conditions": "indoor_broadcast_fixed_diagonal",
        "scoring_eligibility": "scoring_eligible",
        "notes": "U18 3x3 National Championship broadcast, static high-diagonal court camera with clear backboard/rim. Airball/miss attempt by Blue team at ~8s.",
    },
    "c22c4cd8ecf1ac56a48a4a1e651f88e1b6553e560de443ce9da243c1f15d2efa": {
        "video_id": "clip05",
        "camera_id": "cam_broadcast_court_01",
        "session_id": "session_u18_3x3_tournament_01",
        "conditions": "indoor_broadcast_fixed_diagonal",
        "scoring_eligibility": "scoring_eligible",
        "notes": "U18 3x3 National Championship broadcast, static high-diagonal court camera. Made 2-pt shot by White #11 at t=9.61s; remaining 20s contains active play with 0 shots.",
    },
    "da95d00d3a7efb72dee77eb86e14cb7f748a9006c8fa3a0038a1ed96c7ebb4b9": {
        "video_id": "clip06",
        "camera_id": "cam_broadcast_court_01",
        "session_id": "session_u18_3x3_tournament_01",
        "conditions": "indoor_broadcast_fixed_diagonal",
        "scoring_eligibility": "scoring_eligible",
        "notes": "U18 3x3 National Championship broadcast, 48s duration with 4 made layups (Hanoi s001 at 5.72s, Hanoi s002 at 25.74s, TPHCM s003 at 32.26s, Hanoi s004 at 41.87s).",
    },
    "56437c0518fb9c4ed679a283488bf75478a0e4569ffae8b5e123308a48743e58": {
        "video_id": "clip07",
        "camera_id": "cam_broadcast_court_01",
        "session_id": "session_u18_3x3_tournament_01",
        "conditions": "indoor_broadcast_fixed_diagonal",
        "scoring_eligibility": "scoring_eligible",
        "notes": "U18 3x3 National Championship broadcast. Contested drive and blocked/missed shot under the rim at ~7.28s; post-10s contains player close-up and TV replay.",
    },
}


def compute_sha256(filepath: Path) -> str:
    """Compute cryptographic SHA-256 checksum in 1MB chunks."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def parse_fraction(val: str) -> float:
    """Parse fraction strings like '24/1' or '60/1' to float."""
    if "/" in val:
        num, den = val.split("/", 1)
        den_f = float(den)
        return float(num) / den_f if den_f != 0 else 0.0
    return float(val)


def probe_video_stream_ffprobe(filepath: Path) -> Optional[Dict[str, Any]]:
    """Probe video stream specifically via ffprobe."""
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,avg_frame_rate,r_frame_rate,duration,nb_frames,codec_name",
            "-show_entries", "format=duration",
            "-of", "json",
            str(filepath.resolve()),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=True)
        data = json.loads(res.stdout)
        streams = data.get("streams", [])
        if not streams:
            return None
        st = streams[0]
        width = int(st.get("width", 0))
        height = int(st.get("height", 0))
        fps_str = st.get("avg_frame_rate") or st.get("r_frame_rate") or "0"
        fps = parse_fraction(fps_str)

        # Video stream duration is prioritized over format/container duration
        duration_s = None
        if "duration" in st and st["duration"]:
            try:
                duration_s = float(st["duration"])
            except ValueError:
                duration_s = None

        nb_frames = None
        if "nb_frames" in st and st["nb_frames"]:
            try:
                nb_frames = int(st["nb_frames"])
            except ValueError:
                nb_frames = None

        if duration_s is None and nb_frames is not None and fps > 0:
            duration_s = nb_frames / fps
        elif nb_frames is None and duration_s is not None and fps > 0:
            nb_frames = round(duration_s * fps)

        return {
            "width": width,
            "height": height,
            "fps": round(fps, 3),
            "duration_s": round(duration_s, 6) if duration_s else 0.0,
            "frame_count": nb_frames or 0,
            "codec": st.get("codec_name", "unknown"),
        }
    except Exception:
        return None


def probe_video_stream_cv2(filepath: Path) -> Dict[str, Any]:
    """Fallback probe using OpenCV cv2.VideoCapture."""
    import cv2
    cap = cv2.VideoCapture(str(filepath.resolve()))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video {filepath}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    nb_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_s = nb_frames / fps if fps > 0 else 0.0
    cap.release()
    return {
        "width": width,
        "height": height,
        "fps": round(fps, 3),
        "duration_s": round(duration_s, 6),
        "frame_count": nb_frames,
        "codec": "unknown_cv2",
    }


def probe_video(filepath: Path) -> Dict[str, Any]:
    """Probe video metadata preferring ffprobe with cv2 fallback."""
    meta = probe_video_stream_ffprobe(filepath)
    if meta is None or meta["width"] == 0 or meta["height"] == 0:
        meta = probe_video_stream_cv2(filepath)
    return meta


def collect_manifest(
    video_dirs: List[Path],
    codebase_root: Path,
) -> List[Dict[str, Any]]:
    """Scan video directories and assemble manifest entries."""
    extensions = {".mp4", ".mov", ".mkv", ".avi"}
    found_files: List[Path] = []
    for vdir in video_dirs:
        if not vdir.exists():
            continue
        for p in vdir.rglob("*"):
            if p.is_file() and p.suffix.lower() in extensions:
                found_files.append(p)

    # Sort files deterministically by filename
    found_files = sorted(set(found_files), key=lambda x: x.name)
    if not found_files:
        raise ValueError(f"No video files found in {[str(d) for d in video_dirs]}")

    entries: List[Dict[str, Any]] = []
    used_ids: set[str] = set()
    existing_by_hash = {}
    current_manifest = codebase_root / "data/manifest.csv"
    if current_manifest.is_file():
        with current_manifest.open(newline="", encoding="utf-8") as handle:
            existing_by_hash = {row["sha256"]: row for row in csv.DictReader(handle)}

    for idx, vfile in enumerate(found_files, 1):
        sha = compute_sha256(vfile)
        meta = probe_video(vfile)

        # Relativize path to codebase root
        try:
            rel_path = vfile.resolve().relative_to(codebase_root.resolve()).as_posix()
        except ValueError as error:
            raise ValueError("Video source must stay inside codebase root") from error

        # Check preset metadata by SHA-256
        # Keep curated metadata/IDs when regenerating a proposal, not stale presets.
        preset = existing_by_hash.get(sha, KNOWN_METADATA_PRESETS.get(sha, {}))
        video_id = preset.get("video_id", f"video_{sha[:16]}")
        if video_id in used_ids:
            raise ValueError(f"Duplicate source/ID {video_id}; resolve duplicate media before preparing manifest")
        used_ids.add(video_id)

        camera_id = preset.get("camera_id", "unknown")
        session_id = preset.get("session_id", "unknown")
        conditions = preset.get("conditions", "unknown")
        scoring_eligibility = preset.get("scoring_eligibility", "needs_review")
        notes = preset.get("notes", "Auto-generated manifest entry; awaiting review.")

        entry = {
            "video_id": video_id,
            "relative_path": rel_path,
            "width": meta["width"],
            "height": meta["height"],
            "fps": meta["fps"],
            "duration_s": meta["duration_s"],
            "frame_count": meta["frame_count"],
            "camera_id": camera_id,
            "session_id": session_id,
            "conditions": conditions,
            "scoring_eligibility": scoring_eligibility,
            "notes": notes,
            "sha256": sha,
        }
        entries.append(entry)

    return sorted(entries, key=lambda e: e["video_id"])


def write_manifest_csv(entries: List[Dict[str, Any]], output_file: Path) -> None:
    """Write manifest entries to CSV."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
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
        "sha256",
    ]
    with open(output_file, "x", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for e in entries:
            writer.writerow(e)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--video-dirs",
        nargs="+",
        type=Path,
        default=[Path("assets_test"), Path("data/raw")],
        help="Directories to scan for videos (relative to codebase root)",
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--codebase-root",
        type=Path,
        default=default_root,
        help="Root path of the codebase directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/manifest.csv"),
        help="Output CSV path for manifest",
    )
    args = parser.parse_args()

    codebase_root = args.codebase_root.resolve()
    vdirs = [(codebase_root / d).resolve() if not d.is_absolute() else d for d in args.video_dirs]
    out_file = (codebase_root / args.output).resolve() if not args.output.is_absolute() else args.output

    try:
        if out_file.exists():
            raise FileExistsError("Refusing to overwrite an existing manifest; use --output with a new proposal path")
        entries = collect_manifest(vdirs, codebase_root)
        write_manifest_csv(entries, out_file)
        print(f"Successfully generated manifest with {len(entries)} videos -> {out_file}")
        for e in entries:
            print(f"  [{e['video_id']}] {e['relative_path']} ({e['width']}x{e['height']} @ {e['fps']} fps, "
                  f"{e['duration_s']}s) - {e['scoring_eligibility']}")
        return 0
    except Exception as exc:
        print(f"Error preparing dataset manifest: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
