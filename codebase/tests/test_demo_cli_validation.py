"""Acceptance tests for Demo CLI Entrypoint and Input/Output Validation (Task 01A)."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

CODEBASE_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = CODEBASE_DIR.parent
DEMO_SCRIPT = CODEBASE_DIR / "scripts/run_demo.py"
ROOT_ENTRYPOINT = ROOT_DIR / "run_demo.py"
BASELINE_DIR = CODEBASE_DIR / "outputs/task08-critical-baseline-20261108"
ROSTER_PATH = CODEBASE_DIR / "configs/rosters/vietnam_tonga.json"
VIDEO_PATH = CODEBASE_DIR / "assets_test/vietnam-tonga.mp4"


def _run_cli(args: list[str], use_root: bool = False) -> subprocess.CompletedProcess[str]:
    venv_py = CODEBASE_DIR / ".venv/Scripts/python.exe"
    python_bin = str(venv_py) if venv_py.is_file() else sys.executable
    script = str(ROOT_ENTRYPOINT if use_root else DEMO_SCRIPT)
    cmd = [python_bin, script] + args

    env = os.environ.copy()
    env["PYTHONPATH"] = str(CODEBASE_DIR / "src") + os.pathsep + str(CODEBASE_DIR / "scripts")
    env["PYTHONIOENCODING"] = "utf-8"

    return subprocess.run(
        cmd,
        cwd=str(CODEBASE_DIR),
        capture_output=True,
        text=True,
        env=env,
    )


def test_cli_valid_diagnostic_run(tmp_path: Path):
    """Test standard diagnostic cache replay run via root entrypoint."""
    out_dir = tmp_path / "valid_demo_run"
    ret = _run_cli(
        [
            "--video", str(VIDEO_PATH),
            "--roster", str(ROSTER_PATH),
            "--baseline-dir", str(BASELINE_DIR),
            "--output", str(out_dir),
        ],
        use_root=True,
    )

    assert ret.returncode == 0, f"CLI failed with stderr:\n{ret.stderr}\nstdout:\n{ret.stdout}"
    assert out_dir.is_dir(), "Output directory should be created"

    # Check required artifact files
    for fname in ["events_auto.jsonl", "events_raw.jsonl", "audit_trail.jsonl", "checkpoint.json", "boxscore_auto.csv", "summary.json"]:
        p = out_dir / fname
        assert p.is_file(), f"Missing required output file: {fname}"

    # Verify summary contents
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["mode"] == "diagnostic-cache"
    assert summary["pipeline_scope"] == "diagnostic_cache_replay"
    assert summary["status"] == "completed"

    # Check manifest provenance
    wm = summary["window_manifest"]
    assert wm["total_windows"] == 10
    assert wm["processed_count"] == 10
    assert wm["skipped_count"] == 0
    assert wm["invalid_count"] == 0
    expected_windows = ["play_001", "play_003", "play_004", "play_006", "play_008", "play_015", "play_021", "play_023", "play_027", "play_028"]
    assert wm["processed_windows"] == expected_windows


def test_cli_missing_video(tmp_path: Path):
    """Test CLI fails when source video does not exist."""
    out_dir = tmp_path / "out_missing_video"
    ret = _run_cli(["--video", str(tmp_path / "nonexistent.mp4"), "--output", str(out_dir)])

    assert ret.returncode != 0
    assert "Source video file not found" in ret.stderr
    assert not out_dir.exists(), "Output directory must not be created on validation failure"


def test_cli_missing_roster(tmp_path: Path):
    """Test CLI fails when roster file does not exist."""
    out_dir = tmp_path / "out_missing_roster"
    ret = _run_cli(["--roster", str(tmp_path / "nonexistent_roster.json"), "--output", str(out_dir)])

    assert ret.returncode != 0
    assert "Roster file not found" in ret.stderr
    assert not out_dir.exists()


def test_cli_missing_cache(tmp_path: Path):
    """Test CLI fails when cache baseline directory does not exist."""
    out_dir = tmp_path / "out_missing_cache"
    ret = _run_cli(["--baseline-dir", str(tmp_path / "nonexistent_cache"), "--output", str(out_dir)])

    assert ret.returncode != 0
    assert "Baseline cache directory not found" in ret.stderr
    assert not out_dir.exists()


def test_cli_cache_source_mismatch(tmp_path: Path):
    """Test CLI fails when video SHA-256 does not match cache provenance binding."""
    dummy_video = tmp_path / "mismatched_video.mp4"
    dummy_video.write_bytes(b"dummy video content that does not match vietnam-tonga")

    out_dir = tmp_path / "out_mismatch"
    ret = _run_cli(["--video", str(dummy_video), "--output", str(out_dir)])

    assert ret.returncode != 0
    assert "Cache/source mismatch" in ret.stderr
    assert not out_dir.exists()


def test_cli_output_already_exists(tmp_path: Path):
    """Test CLI rejects existing output directory to prevent overwriting evidence."""
    out_dir = tmp_path / "existing_dir"
    out_dir.mkdir(parents=True, exist_ok=True)
    sentinel_file = out_dir / "sentinel.txt"
    sentinel_file.write_text("should not be modified", encoding="utf-8")

    ret = _run_cli(["--output", str(out_dir)])

    assert ret.returncode != 0
    assert "already exists" in ret.stderr
    assert sentinel_file.read_text(encoding="utf-8") == "should not be modified"


def test_cli_video_analysis_mode_missing_video(tmp_path: Path):
    """Test CLI in video-analysis mode validates that source video exists."""
    out_dir = tmp_path / "out_video_mode"
    ret = _run_cli(["--mode", "video-analysis", "--video", "nonexistent_file_xyz.mp4", "--output", str(out_dir)])

    assert ret.returncode != 0
    assert "Source video file not found" in ret.stderr
    assert not out_dir.exists()


def test_cli_no_events_run(tmp_path: Path):
    """Test CLI handles cache with zero events gracefully without synthetic hallucination."""
    synthetic_cache = tmp_path / "empty_cache"
    synthetic_cache.mkdir(parents=True, exist_ok=True)

    import hashlib
    hasher = hashlib.sha256()
    with VIDEO_PATH.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    real_sha = hasher.hexdigest()

    manifest_data = {
        "schema_version": "task08-recognition-manifest-1",
        "provenance": {
            "source_video": str(VIDEO_PATH),
            "source_sha256": real_sha,
            "purpose": "test_zero_events",
        },
        "windows": [
            {"window_id": "play_999", "source_start_s": 0.0, "source_end_s": 2.0}
        ]
    }
    (synthetic_cache / "recognition_input_manifest.json").write_text(json.dumps(manifest_data), encoding="utf-8")

    # Create play_999 directory with valid empty jsonl
    w_dir = synthetic_cache / "play_999"
    w_dir.mkdir()
    (w_dir / "ball_tracks.jsonl").write_text("", encoding="utf-8")
    (w_dir / "tracked_observations.jsonl").write_text("", encoding="utf-8")
    (w_dir / "raw_detections.jsonl").write_text("", encoding="utf-8")

    out_dir = tmp_path / "out_no_events"
    ret = _run_cli([
        "--video", str(VIDEO_PATH),
        "--baseline-dir", str(synthetic_cache),
        "--output", str(out_dir),
    ])

    assert ret.returncode == 0, f"Expected 0, got {ret.returncode}: {ret.stderr}"
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["results"]["total_active_events"] == 0
    assert summary["results"]["total_shots_confirmed"] == 0
    assert summary["results"]["team_a_score"] == 0
    assert summary["results"]["team_b_score"] == 0
    assert summary["status"] == "completed"


def test_cli_no_gt_hints_in_call_path():
    """Verify that run_demo.py does not pass is_play_006 or is_free_throw GT hints to engine."""
    source_text = DEMO_SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source_text)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name == "run_engine_on_window":
                kw_names = [kw.arg for kw in node.keywords]
                assert "is_play_006" not in kw_names, "is_play_006 must not be passed"
                assert "is_free_throw" not in kw_names, "is_free_throw must not be passed"
