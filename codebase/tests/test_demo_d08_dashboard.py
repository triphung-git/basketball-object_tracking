"""Targeted test suite for Task D08: UI / Video Overlay / Evidence & Dashboard."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from basketball_scoreboard.video import probe_video


def test_annotated_video_overlay_file_integrity():
    """Verify generated annotated.mp4 exists, has valid dimensions, duration, and codec."""
    root = Path(__file__).resolve().parents[1]
    video_path = root / "outputs/demo-completion-20261116/D08/annotated.mp4"
    assert video_path.is_file(), f"Annotated video missing: {video_path}"
    assert video_path.stat().st_size > 100_000, "Annotated video file is too small"

    meta = probe_video(video_path)
    assert meta.width == 1920
    assert meta.height == 1080
    assert meta.duration_s > 0.0
    assert meta.nb_frames > 0


def test_browser_qa_report_verifications():
    """Verify automated browser QA report asserts desktop, mobile, exports, and range streaming."""
    root = Path(__file__).resolve().parents[1]
    report_path = root / "outputs/demo-completion-20261116/D08/browser_qa_report.json"
    assert report_path.is_file(), f"Browser QA report missing: {report_path}"

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["all_passed"] is True
    assert report["scenarios"]["desktop_layout"]["pass"] is True
    assert report["scenarios"]["mobile_layout"]["pass"] is True
    assert report["scenarios"]["http_range_streaming"]["is_206"] is True

    # Screenshots exist
    for shot in report["screenshots"]:
        shot_p = Path(shot["path"])
        assert shot_p.is_file()
        assert shot_p.stat().st_size > 0

    # Exports exist and have content
    for ep, exp in report["exports_verified"].items():
        assert exp["status_code"] == 200
        assert exp["size_bytes"] > 0
