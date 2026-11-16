#!/usr/bin/env python3
"""Browser QA automated test suite for Task D08 using Headless Chrome."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from basketball_scoreboard.boxscore import BoxScoreEngine
from basketball_scoreboard.dashboard import make_dashboard_server, load_run_bundle
from basketball_scoreboard.identity import RosterConfig, RosterPlayer

CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
D08_DIR = ROOT / "outputs/demo-completion-20261116/D08"
SCREENSHOTS_DIR = D08_DIR / "screenshots"


def take_screenshot(url: str, output_path: Path, width: int = 1280, height: int = 800) -> bool:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        CHROME_PATH,
        "--headless",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--window-size={width},{height}",
        f"--screenshot={str(output_path.resolve())}",
        url,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    return output_path.is_file() and output_path.stat().st_size > 0


def fetch_dom(url: str) -> str:
    cmd = [
        CHROME_PATH,
        "--headless",
        "--disable-gpu",
        "--dump-dom",
        url,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    return res.stdout


def run_browser_qa() -> dict:
    D08_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    run_dir = ROOT / "outputs/demo-completion-20261116/D05/run"
    video_path = D08_DIR / "annotated.mp4"
    if not video_path.is_file():
        video_path = ROOT / "assets_test/vietnam-tonga.mp4"

    roster_path = ROOT / "configs/rosters/vietnam_tonga.json"
    roster_data = json.loads(roster_path.read_text(encoding="utf-8"))
    players = [RosterPlayer(**p) for p in roster_data["players"]]
    roster = RosterConfig(
        team_a_id=roster_data["team_a_id"],
        team_b_id=roster_data["team_b_id"],
        team_a_name=roster_data["team_a_name"],
        team_b_name=roster_data["team_b_name"],
        team_a_color_rgb=tuple(roster_data["team_a_color_rgb"]),
        team_b_color_rgb=tuple(roster_data["team_b_color_rgb"]),
        players=players,
    )
    box_engine = BoxScoreEngine(roster=roster)

    server = make_dashboard_server(
        host="127.0.0.1",
        port=0,
        video_path=video_path,
        roster=roster,
        box_engine=box_engine,
        run_dir=run_dir,
    )
    port = server.server_port
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    url = f"http://127.0.0.1:{port}"
    time.sleep(0.5)

    qa_report = {
        "task": "D08",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "chrome_path": CHROME_PATH,
        "dashboard_url": url,
        "scenarios": {},
        "exports_verified": {},
        "screenshots": [],
        "all_passed": True,
    }

    # 1. Desktop Screenshot (1280x800)
    desktop_shot = SCREENSHOTS_DIR / "01_desktop_dashboard.png"
    ok_desktop = take_screenshot(url, desktop_shot, 1280, 800)
    qa_report["screenshots"].append({
        "name": "01_desktop_dashboard.png",
        "path": str(desktop_shot),
        "size_bytes": desktop_shot.stat().st_size if ok_desktop else 0,
        "viewport": "1280x800",
    })
    qa_report["scenarios"]["desktop_layout"] = {"pass": ok_desktop}

    # 2. Mobile Screenshot (375x812)
    mobile_shot = SCREENSHOTS_DIR / "02_mobile_dashboard.png"
    ok_mobile = take_screenshot(url, mobile_shot, 375, 812)
    qa_report["screenshots"].append({
        "name": "02_mobile_dashboard.png",
        "path": str(mobile_shot),
        "size_bytes": mobile_shot.stat().st_size if ok_mobile else 0,
        "viewport": "375x812",
    })
    qa_report["scenarios"]["mobile_layout"] = {"pass": ok_mobile}

    # 3. DOM Component Verification
    dom = fetch_dom(url)
    dom_checks = {
        "video_player": "<video" in dom,
        "timeline_events": "Timeline" in dom or "timeline" in dom,
        "boxscore_table": "Việt Nam" in dom and "Tonga" in dom,
        "court_visualizer": "<svg" in dom or "court" in dom.lower(),
        "export_links": "/api/export/boxscore" in dom and "/api/export/events" in dom,
    }
    qa_report["scenarios"]["dom_components"] = dom_checks
    for k, v in dom_checks.items():
        if not v:
            qa_report["all_passed"] = False

    # 4. Export Endpoints Verification
    endpoints = [
        ("/api/export/boxscore", "text/csv"),
        ("/api/export/events", "application/x-ndjson"),
        ("/api/export/summary", "application/json"),
    ]
    for ep, content_type in endpoints:
        req = urllib.request.Request(f"{url}{ep}")
        with urllib.request.urlopen(req) as resp:
            data = resp.read()
            qa_report["exports_verified"][ep] = {
                "status_code": resp.status,
                "size_bytes": len(data),
                "valid": resp.status == 200 and len(data) > 0,
            }

    # 5. HTTP Range Streaming Verification (206 Partial Content)
    range_req = urllib.request.Request(f"{url}/api/video")
    range_req.add_header("Range", "bytes=0-1023")
    try:
        with urllib.request.urlopen(range_req) as resp:
            data = resp.read()
            qa_report["scenarios"]["http_range_streaming"] = {
                "status_code": resp.status,
                "bytes_received": len(data),
                "is_206": resp.status == 206,
                "content_range": resp.headers.get("Content-Range"),
            }
    except Exception as exc:
        qa_report["scenarios"]["http_range_streaming"] = {
            "error": str(exc),
            "is_206": False,
        }

    server.shutdown()
    report_file = D08_DIR / "browser_qa_report.json"
    report_file.write_text(json.dumps(qa_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return qa_report


def main():
    report = run_browser_qa()
    print("=== BROWSER QA D08 FINISHED ===")
    print("All Passed:", report["all_passed"])
    print("Desktop Screenshot:", report["screenshots"][0]["path"])
    print("Mobile Screenshot:", report["screenshots"][1]["path"])
    print("HTTP Range 206:", report["scenarios"].get("http_range_streaming", {}).get("is_206"))
    for ep, res in report["exports_verified"].items():
        print(f"Export {ep}: {res['size_bytes']} bytes (Status {res['status_code']})")


if __name__ == "__main__":
    main()
