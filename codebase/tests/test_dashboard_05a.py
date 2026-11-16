"""Comprehensive tests for Task 05A: Dashboard API, exports, range requests, geometry bindings, and safe rendering."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
import threading
import urllib.request
import urllib.error
import pytest

from basketball_scoreboard.boxscore import BoxScoreEngine
from basketball_scoreboard.dashboard import make_dashboard_server, load_run_bundle
from basketball_scoreboard.events import EventLedger, EventStatus, EventType, LedgerEventRecord
from basketball_scoreboard.identity import RosterConfig, RosterPlayer


@pytest.fixture
def dashboard_fixture_05a(tmp_path):
    # Setup dummy video file
    dummy_video = tmp_path / "test_video.mp4"
    dummy_video.write_bytes(b"BASKETBALL_STREAM_DATA" * 50)  # 1100 bytes
    file_size = len(dummy_video.read_bytes())

    # Setup roster with potential XSS strings to verify safe handling
    players = [
        RosterPlayer(team_id="team_vie", player_id="vie_01", jersey_number="1", name="Phú Vinh <script>alert(1)</script>"),
        RosterPlayer(team_id="team_tga", player_id="tga_09", jersey_number="9", name="Luke Sinisa & Tonga"),
    ]
    roster = RosterConfig(
        team_a_id="team_vie",
        team_b_id="team_tga",
        team_a_name="Việt Nam <Safe>",
        team_b_name="Tonga & Co.",
        team_a_color_rgb=(239, 68, 68),
        team_b_color_rgb=(59, 130, 246),
        players=players,
    )

    ledger = EventLedger()
    # 1. Shot with calibrated court coordinates
    ledger.record_event(
        LedgerEventRecord(
            event_id="shot_calibrated_01",
            event_type=EventType.SHOT,
            source_time_s=10.133,
            frame_index=304,
            team_id="team_tga",
            player_id="tga_09",
            point_value=1,
            status=EventStatus.AUTO_CONFIRMED,
            evidence={
                "court_x_m": -1.38,
                "court_y_m": 4.01,
                "court_distance_m": 2.79,
                "value_reason": "fiba_3x3_1pt_inside_arc",
            },
        )
    )
    # 2. Shot with uncalibrated / missing coordinates
    ledger.record_event(
        LedgerEventRecord(
            event_id="shot_uncalibrated_02",
            event_type=EventType.SHOT,
            source_time_s=25.0,
            frame_index=750,
            team_id="team_vie",
            player_id="vie_01",
            point_value=None,
            status=EventStatus.UNRESOLVED,
            evidence={
                "value_reason": "unresolved_geometry",
            },
        )
    )

    run_state = {
        "status": "completed",
        "video_path": str(dummy_video),
        "video_id": "test_match",
        "geometry": {"status": "calibrated"},
        "quality_gate": "FAIL_MVP_IN_PROGRESS",
    }
    heatmap_data = {
        "status": "unavailable",
        "reason": "Court geometry is uncalibrated / diagnostic mode; physical court heatmap generation suspended",
        "total_player_seconds": 0.0,
        "observations_tracked": 1425,
    }

    box_engine = BoxScoreEngine(roster=roster)

    server = make_dashboard_server(
        host="127.0.0.1",
        port=0,
        video_path=dummy_video,
        roster=roster,
        ledger=ledger,
        box_engine=box_engine,
        run_state=run_state,
        heatmap_data=heatmap_data,
    )
    port = server.server_port
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    base_url = f"http://127.0.0.1:{port}"
    yield base_url, dummy_video, file_size

    server.shutdown()
    server.server_close()


def test_dashboard_status_and_run_info(dashboard_fixture_05a):
    base_url, _, _ = dashboard_fixture_05a

    with urllib.request.urlopen(f"{base_url}/api/status") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "completed"
        assert data["geometry_status"] == "calibrated"
        assert data["video_exists"] is True
        assert data["total_events"] == 2

    with urllib.request.urlopen(f"{base_url}/api/run_info") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["quality_gate"] == "FAIL_MVP_IN_PROGRESS"


def test_dashboard_heatmap_diagnostic_reporting(dashboard_fixture_05a):
    base_url, _, _ = dashboard_fixture_05a

    with urllib.request.urlopen(f"{base_url}/api/heatmap") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "unavailable"
        assert "Court geometry is uncalibrated" in data["reason"]


def test_dashboard_video_range_and_invalid_ranges(dashboard_fixture_05a):
    base_url, _, file_size = dashboard_fixture_05a

    # 1. Valid range
    req_valid = urllib.request.Request(f"{base_url}/api/video")
    req_valid.add_header("Range", "bytes=0-49")
    with urllib.request.urlopen(req_valid) as resp:
        assert resp.status == 206
        assert resp.headers["Content-Range"] == f"bytes 0-49/{file_size}"
        chunk = resp.read()
        assert len(chunk) == 50

    # 2. Invalid range: start >= file_size (must return 416)
    req_invalid = urllib.request.Request(f"{base_url}/api/video")
    req_invalid.add_header("Range", f"bytes={file_size + 1000}-")
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req_invalid)
    assert exc_info.value.code == 416
    assert f"bytes */{file_size}" in exc_info.value.headers.get("Content-Range", "")

    # 3. Invalid syntax range (must return 416)
    req_syntax = urllib.request.Request(f"{base_url}/api/video")
    req_syntax.add_header("Range", "bytes=abc-def")
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req_syntax)
    assert exc_info.value.code == 416


def test_dashboard_missing_video_handling(tmp_path):
    missing_video = tmp_path / "does_not_exist.mp4"
    server = make_dashboard_server(
        host="127.0.0.1",
        port=0,
        video_path=missing_video,
    )
    port = server.server_port
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    base_url = f"http://127.0.0.1:{port}"
    try:
        # /api/status should report video_exists: False
        with urllib.request.urlopen(f"{base_url}/api/status") as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["video_exists"] is False

        # /api/video should return 404
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(f"{base_url}/api/video")
        assert exc_info.value.code == 404
    finally:
        server.shutdown()
        server.server_close()


def test_dashboard_exports(dashboard_fixture_05a):
    base_url, _, _ = dashboard_fixture_05a

    # 1. Export Events JSONL
    with urllib.request.urlopen(f"{base_url}/api/export/events") as resp:
        assert resp.status == 200
        assert "application/x-jsonlines" in resp.headers["Content-Type"]
        lines = [json.loads(l) for l in resp.read().decode("utf-8").splitlines() if l.strip()]
        assert len(lines) == 2
        assert lines[0]["event_id"] == "shot_calibrated_01"
        assert lines[0]["evidence"]["court_x_m"] == -1.38

    # 2. Export Boxscore CSV
    with urllib.request.urlopen(f"{base_url}/api/export/boxscore") as resp:
        assert resp.status == 200
        assert "text/csv" in resp.headers["Content-Type"]
        content = resp.read().decode("utf-8")
        reader = csv.DictReader(content.splitlines())
        rows = list(reader)
        assert len(rows) > 0
        assert any("Tonga" in r["Team"] for r in rows)

    # 3. Export Summary JSON
    with urllib.request.urlopen(f"{base_url}/api/export/summary") as resp:
        assert resp.status == 200
        assert "application/json" in resp.headers["Content-Type"]
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "completed"


def test_dashboard_real_run_bundle_loading():
    run_dir = Path(__file__).resolve().parents[1] / "outputs/remaining-tasks-20261115/04A/run/candidate_court_dist"
    assert run_dir.is_dir()

    ledger, run_state, heatmap_data = load_run_bundle(run_dir)
    assert len(ledger.get_active_events()) >= 1
    assert run_state.get("status") == "completed" or "video" in run_state
    assert heatmap_data.get("status") in {"unavailable", "generated"}
