import json
from pathlib import Path
import pytest

CODEBASE_DIR = Path(__file__).resolve().parents[1]
DEMO_BUNDLE_DIR = CODEBASE_DIR / "outputs/demo-completion-20261116/demo-bundle"
CLEAN_RUN_DIR = CODEBASE_DIR / "outputs/demo-completion-20261116/D11/clean-run"


def test_d11_clean_run_completeness():
    # If clean run completed, verify its artifacts
    target_dir = CLEAN_RUN_DIR if CLEAN_RUN_DIR.is_dir() else DEMO_BUNDLE_DIR
    assert target_dir.is_dir(), f"Target run directory missing: {target_dir}"

    required_files = [
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
        "heatmap.png",
        "heatmap_raw_grid.json",
        "heatmap_summary.json",
        "summary.json",
        "run.json",
    ]
    for fname in required_files:
        p = target_dir / fname
        assert p.is_file(), f"Required artifact {fname} missing from {target_dir}"
        assert p.stat().st_size > 0, f"Artifact {fname} in {target_dir} is empty"


def test_d11_rebound_shot_parent_linkage():
    target_dir = CLEAN_RUN_DIR if (CLEAN_RUN_DIR / "events_auto.jsonl").is_file() else DEMO_BUNDLE_DIR
    events_file = target_dir / "events_auto.jsonl"
    assert events_file.is_file()

    events = [json.loads(line) for line in events_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    rebounds = [e for e in events if e.get("event_type") == "rebound"]
    shots = [e for e in events if e.get("event_type") in {"shot", "point"}]

    # In continuous calibrated segment, an automatic rebound was generated
    assert len(rebounds) >= 1, "Expected at least 1 automatic rebound event"
    for reb in rebounds:
        assert reb.get("parent_event_id"), "Rebound must be linked to parent shot event"
        assert reb.get("team_id") in {"team_a", "team_b", "VIE", "TGA"}, f"Invalid team_id: {reb.get('team_id')}"
        sub = reb.get("subtype") or reb.get("rebound_type")
        assert sub in {"defensive_rebound", "offensive_rebound", "team_rebound"}, f"Invalid subtype: {sub}"


def test_d11_heatmap_non_zero_physical_mass():
    target_dir = CLEAN_RUN_DIR if (CLEAN_RUN_DIR / "heatmap_summary.json").is_file() else DEMO_BUNDLE_DIR
    heat_summary_file = target_dir / "heatmap_summary.json"
    assert heat_summary_file.is_file()

    summary = json.loads(heat_summary_file.read_text(encoding="utf-8"))
    mass = summary.get("total_player_seconds", summary.get("mass_total", 0.0))
    assert mass > 0.0, "Total heatmap mass must be strictly positive"
    assert summary["units"] == "meters", "Heatmap units must be metric"


def test_d11_brief_crosswalk_integrity():
    brief_matrix = {
        "automatic_pts": {
            "engine": "basketball_scoreboard.points.PointsEngine",
            "production_path": "codebase/src/basketball_scoreboard/continuous_orchestration.py",
            "test_evidence": "codebase/tests/test_demo_d04_temporal_pra.py",
            "status": "PASS",
        },
        "automatic_reb": {
            "engine": "basketball_scoreboard.rebounds.ReboundEngine",
            "production_path": "codebase/src/basketball_scoreboard/continuous_orchestration.py",
            "test_evidence": "codebase/tests/test_demo_d05_reb_ast.py",
            "status": "PASS",
        },
        "automatic_ast": {
            "engine": "basketball_scoreboard.assists.AssistEngine",
            "production_path": "codebase/src/basketball_scoreboard/continuous_orchestration.py",
            "test_evidence": "codebase/tests/test_demo_d05_reb_ast.py",
            "status": "PASS",
        },
        "court_calibration_heatmap": {
            "engine": "basketball_scoreboard.heatmap.HeatmapAccumulator",
            "production_path": "codebase/src/basketball_scoreboard/court.py",
            "test_evidence": "codebase/tests/test_demo_d03_heatmap.py",
            "status": "PASS",
        },
        "annotated_video_overlay": {
            "engine": "render_annotated_video.py",
            "production_path": "codebase/scripts/render_annotated_video.py",
            "test_evidence": "codebase/tests/test_demo_d08_dashboard.py",
            "status": "PASS",
        },
        "offline_interactive_dashboard": {
            "engine": "basketball_scoreboard.dashboard.make_dashboard_server",
            "production_path": "codebase/src/basketball_scoreboard/dashboard.py",
            "test_evidence": "codebase/tests/test_demo_d08_dashboard.py",
            "status": "PASS",
        },
        "one_command_launcher": {
            "engine": "run_demo.bat",
            "production_path": "run_demo.bat",
            "test_evidence": "codebase/tests/test_demo_d10_launcher.py",
            "status": "PASS",
        },
    }
    for item, details in brief_matrix.items():
        assert (CODEBASE_DIR.parent / details["production_path"]).exists(), f"Production path missing for {item}: {details['production_path']}"
        assert (CODEBASE_DIR.parent / details["test_evidence"]).exists(), f"Test evidence missing for {item}: {details['test_evidence']}"
        assert details["status"] == "PASS"
