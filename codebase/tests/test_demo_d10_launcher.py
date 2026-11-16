import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

CODEBASE_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = CODEBASE_DIR.parent
BUNDLE_DIR = CODEBASE_DIR / "outputs/demo-completion-20261116/demo-bundle"
DEMO_SCRIPT = CODEBASE_DIR / "scripts/run_demo.py"
PYTHON_BIN = CODEBASE_DIR / ".venv/Scripts/python.exe"


def test_d10_manifest_integrity():
    assert BUNDLE_DIR.is_dir(), f"Bundle dir does not exist: {BUNDLE_DIR}"
    manifest_path = BUNDLE_DIR / "manifest.json"
    assert manifest_path.is_file(), f"Manifest missing at {manifest_path}"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["schema_version"] == "demo-bundle-manifest-v1"
    assert manifest["total_files"] >= 25
    assert manifest["total_bytes"] > 0
    assert len(manifest["files"]) == manifest["total_files"]

    # Verify each bundled file exists on disk and matches checksum
    for entry in manifest["files"]:
        rel_path = entry["path"]
        fpath = BUNDLE_DIR / rel_path
        assert fpath.is_file(), f"Bundled file missing: {rel_path}"
        assert fpath.stat().st_size == entry["bytes"], f"Size mismatch for {rel_path}"

        # Sample check sha256
        hasher = hashlib.sha256()
        with open(fpath, "rb") as bf:
            while chunk := bf.read(65536):
                hasher.update(chunk)
        assert hasher.hexdigest() == entry["sha256"], f"SHA256 mismatch for {rel_path}"


def test_d10_bundle_critical_artifacts():
    required_names = [
        "annotated.mp4",
        "heatmap.png",
        "heatmap_team_a.png",
        "heatmap_team_b.png",
        "heatmap_raw_grid.json",
        "heatmap_summary.json",
        "boxscore_auto.csv",
        "events_auto.jsonl",
        "events_raw.jsonl",
        "audit_trail.jsonl",
        "shots_auto.jsonl",
        "ball_tracks.jsonl",
        "ball_control.jsonl",
        "trajectories.jsonl",
        "identity_mappings.json",
        "jersey_evidence.json",
        "summary.json",
        "run.json",
        "evaluation_summary.json",
        "benchmark.json",
    ]
    for fname in required_names:
        p = BUNDLE_DIR / fname
        assert p.is_file(), f"Critical demo artifact {fname} missing from bundle"
        assert p.stat().st_size > 0, f"Critical demo artifact {fname} is empty"


def test_d10_launcher_cli_view_preflight_nonexistent_bundle():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(CODEBASE_DIR / "src") + os.pathsep + str(CODEBASE_DIR / "scripts")
    cmd = [
        str(PYTHON_BIN),
        str(DEMO_SCRIPT),
        "--mode", "view",
        "--bundle", "nonexistent_bundle_directory_xyz"
    ]
    proc = subprocess.run(cmd, cwd=str(CODEBASE_DIR), capture_output=True, text=True, env=env)
    assert proc.returncode != 0
    assert "Demo bundle directory not found" in proc.stderr


def test_d10_launcher_bat_script():
    bat_file = ROOT_DIR / "run_demo.bat"
    assert bat_file.is_file(), f"run_demo.bat missing at {bat_file}"
    content = bat_file.read_text(encoding="utf-8")
    assert "codebase\\.venv\\Scripts\\python.exe" in content
    assert "run_demo.py" in content
    assert "%*" in content


def test_d10_port_utilities():
    sys.path.insert(0, str(CODEBASE_DIR / "scripts"))
    from run_demo import is_port_in_use, find_available_port

    # Port checking function returns boolean
    res = is_port_in_use("127.0.0.1", 65530)
    assert isinstance(res, bool)

    # find_available_port returns integer
    port = find_available_port("127.0.0.1", 18080)
    assert isinstance(port, int)
    assert port >= 18080
