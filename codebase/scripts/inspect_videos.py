"""Inspect local MP4s with FFmpeg; originals are never modified or uploaded."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess


def run(command):
    result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError(f"{command[0]} failed: {result.stderr[-1200:]}")
    return result.stdout


def inspect(source, output):
    # Refuse an existing run directory to prevent overwriting previous evidence.
    output.mkdir(parents=True, exist_ok=False)
    reports = []
    videos = sorted(source.glob("*.mp4"))
    if not videos:
        raise ValueError(f"No MP4 files found in {source}")
    for index, video in enumerate(videos, 1):
        metadata = json.loads(run([
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration,size:stream=index,codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate,duration,nb_frames",
            "-of", "json", str(video.resolve()),
        ]))
        stream = next(s for s in metadata["streams"] if s["codec_type"] == "video")
        duration = float(metadata["format"]["duration"])
        folder = output / f"clip{index:02d}"
        folder.mkdir()
        # Decode sequentially; exclude audio; reduced images only for visual review.
        interval = max(duration / 12, 0.1)
        run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(video.resolve()),
             "-an", "-vf", f"fps=1/{interval},scale=480:480:force_original_aspect_ratio=decrease,tile=4x3",
             "-frames:v", "1", str((folder / "contact_sheet.jpg").resolve())])
        # Full decode verifies video integrity without producing a new video.
        run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(video.resolve()),
             "-map", "0:v:0", "-an", "-f", "null", "-"])
        reports.append({"video": video.name, "metadata": metadata,
                        "duration_s": duration, "video_stream": stream,
                        "full_decode": "passed", "contact_sheet": f"clip{index:02d}/contact_sheet.jpg",
                        "sheet_sample_interval_s": interval,
                        "note": "Sampling is not proof of no camera cuts, misses, or replays."})
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "videos": reports}
    (output / "inspection.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = inspect(args.source, args.output)
    except (OSError, ValueError, RuntimeError, StopIteration, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"Inspection failed: {error}\n")
    for entry in report["videos"]:
        stream = entry["video_stream"]
        print(f"{entry['video']}: {stream['width']}x{stream['height']}, "
              f"{stream['avg_frame_rate']} fps, {entry['duration_s']:.2f}s, decode passed")
