"""Unit and integration tests for Task 12: Integrated Local Dashboard Server."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import threading
import urllib.request
import pytest

from basketball_scoreboard.boxscore import BoxScoreEngine
from basketball_scoreboard.dashboard import make_dashboard_server
from basketball_scoreboard.events import EventLedger, EventStatus, EventType, LedgerEventRecord
from basketball_scoreboard.identity import RosterConfig, RosterPlayer


@pytest.fixture
def dashboard_fixture(tmp_path):
    # Setup dummy video file
    dummy_video = tmp_path / "dummy.mp4"
    dummy_video.write_bytes(b"\x00" * 1024)

    # Setup roster
    players = [
        RosterPlayer(team_id="team_vie", player_id="vie_07", jersey_number="7", name="Nguyễn Văn A"),
        RosterPlayer(team_id="team_tga", player_id="tga_03", jersey_number="3", name="Sione T."),
    ]
    roster = RosterConfig(
        team_a_id="team_vie",
        team_b_id="team_tga",
        team_a_name="Việt Nam",
        team_b_name="Tonga",
        team_a_color_rgb=(200, 20, 20),
        team_b_color_rgb=(20, 20, 200),
        players=players,
    )

    ledger = EventLedger()
    ledger.record_event(
        LedgerEventRecord(
            event_id="shot_dash_01",
            event_type=EventType.SHOT,
            source_time_s=15.0,
            frame_index=450,
            team_id="team_vie",
            player_id="vie_07",
            point_value=2,
            status=EventStatus.AUTO_CONFIRMED,
        )
    )

    box_engine = BoxScoreEngine(roster=roster)

    server = make_dashboard_server(
        host="127.0.0.1",
        port=0,  # pick ephemeral port
        video_path=dummy_video,
        roster=roster,
        ledger=ledger,
        box_engine=box_engine,
    )
    port = server.server_port

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    base_url = f"http://127.0.0.1:{port}"
    yield base_url

    server.shutdown()
    server.server_close()


def test_dashboard_html_endpoint(dashboard_fixture):
    req = urllib.request.Request(f"{dashboard_fixture}/")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        assert "text/html" in resp.headers["Content-Type"]
        body = resp.read().decode("utf-8")
        assert "Automatic Basketball Stats Dashboard" in body
        assert "courtSvg" in body
        assert "boxscoreTable" in body


def test_dashboard_api_endpoints(dashboard_fixture):
    # 1. /api/status
    with urllib.request.urlopen(f"{dashboard_fixture}/api/status") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "ready"
        assert data["total_events"] == 1

    # 2. /api/events
    with urllib.request.urlopen(f"{dashboard_fixture}/api/events") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["count"] == 1
        assert data["events"][0]["event_id"] == "shot_dash_01"

    # 3. /api/boxscore
    with urllib.request.urlopen(f"{dashboard_fixture}/api/boxscore") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "team_a" in data
        assert data["team_a"]["team_name"] == "Việt Nam"
        assert data["team_a"]["total_score"] == 2


def test_dashboard_export_endpoints(dashboard_fixture):
    # 1. /api/export/events
    with urllib.request.urlopen(f"{dashboard_fixture}/api/export/events") as resp:
        assert resp.status == 200
        assert "application/x-jsonlines" in resp.headers["Content-Type"]
        lines = [json.loads(l) for l in resp.read().decode("utf-8").splitlines() if l.strip()]
        assert len(lines) == 1
        assert lines[0]["event_id"] == "shot_dash_01"

    # 2. /api/export/boxscore
    with urllib.request.urlopen(f"{dashboard_fixture}/api/export/boxscore") as resp:
        assert resp.status == 200
        assert "text/csv" in resp.headers["Content-Type"]
        content = resp.read().decode("utf-8")
        reader = csv.DictReader(content.splitlines())
        rows = list(reader)
        assert len(rows) > 0
        assert any(r["Player_ID"] == "vie_07" for r in rows)


def test_dashboard_video_range_request(dashboard_fixture):
    req = urllib.request.Request(f"{dashboard_fixture}/api/video")
    req.add_header("Range", "bytes=0-127")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 206  # Partial Content
        assert resp.headers["Content-Range"] == "bytes 0-127/1024"
        chunk = resp.read()
        assert len(chunk) == 128

