import json
from pathlib import Path
import shutil

import pytest

from basketball_scoreboard.demo_bundle import install_dashboard_demo, verify_dashboard_demo


DEMO = Path(__file__).resolve().parents[1] / "demo"


def test_bundled_demo_installs_without_overwriting_local_edits(tmp_path):
    jobs = tmp_path / "web uploads"
    job_id = install_dashboard_demo(DEMO, jobs)
    assert json.loads((jobs / "demo.json").read_text())["job_id"] == job_id
    config = jobs / job_id / "match_config.json"
    edits = json.loads(config.read_text(encoding="utf-8"))
    edits["roster"]["team_a_name"] = "Local team"
    config.write_text(json.dumps(edits), encoding="utf-8")

    assert install_dashboard_demo(DEMO, jobs) == job_id
    assert json.loads(config.read_text())["roster"]["team_a_name"] == "Local team"
    assert json.loads((DEMO / "match_config.json").read_text(encoding="utf-8"))["roster"]["team_a_name"] != "Local team"


def test_bundled_demo_rejects_a_modified_artifact_of_the_same_size(tmp_path):
    demo = tmp_path / "demo"
    shutil.copytree(DEMO, demo)
    artifact = demo / "analysis/web_overlay.json"
    original = artifact.read_bytes()
    artifact.write_bytes(b" " + original[1:])

    with pytest.raises(ValueError, match="SHA-256 mismatch: analysis/web_overlay.json"):
        verify_dashboard_demo(demo)
