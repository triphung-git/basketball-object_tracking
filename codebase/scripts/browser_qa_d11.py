#!/usr/bin/env python3
"""Browser QA automated test suite for Task D11 clean-run using Headless Chrome."""
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
D11_DIR = ROOT / "outputs/demo-completion-20261116/D11"
SCREENSHOTS_DIR = D11_DIR / "screenshots"


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


def main() -> int:
    print("=== D11 Clean-Run Browser QA Suite ===")
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load run bundle from clean-run or demo-bundle
    clean_run_dir = D11_DIR / "clean-run"
    bundle_dir = ROOT / "outputs/demo-completion-20261116/demo-bundle"
    target_dir = clean_run_dir if clean_run_dir.is_dir() else bundle_dir
    print(f"Loading run bundle from: {target_dir}")

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

    ledger, run_state, heatmap_data = load_run_bundle(target_dir)
    box_engine = BoxScoreEngine(roster=roster)
    video_path = bundle_dir / "annotated.mp4"
    if not video_path.is_file():
        video_path = ROOT / "assets_test/vietnam-tonga.mp4"

    port = 8092
    server = make_dashboard_server(
        host="127.0.0.1",
        port=port,
        video_path=video_path,
        roster=roster,
        ledger=ledger,
        box_engine=box_engine,
        run_state=run_state,
        heatmap_data=heatmap_data,
    )

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(1.0)
    base_url = f"http://127.0.0.1:{port}"
    print(f"Test server started at {base_url}")

    results = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_url": base_url,
        "checks": {},
        "screenshots": {},
        "all_passed": False,
    }

    try:
        # Check 1: Desktop Screenshot
        desktop_img = SCREENSHOTS_DIR / "01_desktop_clean_run.png"
        s1_ok = take_screenshot(base_url, desktop_img, 1280, 800)
        results["checks"]["desktop_screenshot"] = {
            "status": "PASS" if s1_ok else "FAIL",
            "path": str(desktop_img.resolve()),
            "bytes": desktop_img.stat().st_size if s1_ok else 0,
        }
        print(f"  + Desktop screenshot (1280x800): {'PASS' if s1_ok else 'FAIL'}")

        # Check 2: Mobile Screenshot
        mobile_img = SCREENSHOTS_DIR / "02_mobile_clean_run.png"
        s2_ok = take_screenshot(base_url, mobile_img, 375, 812)
        results["checks"]["mobile_screenshot"] = {
            "status": "PASS" if s2_ok else "FAIL",
            "path": str(mobile_img.resolve()),
            "bytes": mobile_img.stat().st_size if s2_ok else 0,
        }
        print(f"  + Mobile screenshot (375x812): {'PASS' if s2_ok else 'FAIL'}")

        # Check 3: DOM Components
        dom = fetch_dom(base_url)
        has_video = "<video" in dom
        has_court = "<svg" in dom or "court" in dom.lower()
        has_boxscore = "Việt Nam" in dom or "Tonga" in dom
        has_timeline = "timeline" in dom.lower() or "events" in dom.lower()
        dom_ok = has_video and has_court and has_boxscore and has_timeline
        results["checks"]["dom_components"] = {
            "status": "PASS" if dom_ok else "FAIL",
            "has_video": has_video,
            "has_court_diagram": has_court,
            "has_boxscore": has_boxscore,
            "has_timeline": has_timeline,
        }
        print(f"  + DOM components: {'PASS' if dom_ok else 'FAIL'}")

        # Check 4: Export Boxscore CSV
        req_box = urllib.request.urlopen(f"{base_url}/api/export/boxscore")
        box_bytes = req_box.read()
        box_csv_text = box_bytes.decode("utf-8")
        box_rows = list(csv.reader(box_csv_text.splitlines()))
        box_ok = req_box.status == 200 and len(box_rows) >= 2
        results["checks"]["export_boxscore_csv"] = {
            "status": "PASS" if box_ok else "FAIL",
            "http_status": req_box.status,
            "bytes": len(box_bytes),
            "rows": len(box_rows),
        }
        print(f"  + Export BoxScore CSV: {'PASS' if box_ok else 'FAIL'} ({len(box_bytes)} bytes)")

        # Check 5: Export Events JSONL
        req_ev = urllib.request.urlopen(f"{base_url}/api/export/events")
        ev_bytes = req_ev.read()
        ev_lines = [line for line in ev_bytes.decode("utf-8").splitlines() if line.strip()]
        ev_ok = req_ev.status == 200
        results["checks"]["export_events_jsonl"] = {
            "status": "PASS" if ev_ok else "FAIL",
            "http_status": req_ev.status,
            "bytes": len(ev_bytes),
            "events_count": len(ev_lines),
        }
        print(f"  + Export Events JSONL: {'PASS' if ev_ok else 'FAIL'} ({len(ev_bytes)} bytes)")

        # Check 6: Export Summary JSON
        req_sum = urllib.request.urlopen(f"{base_url}/api/export/summary")
        sum_bytes = req_sum.read()
        sum_data = json.loads(sum_bytes.decode("utf-8"))
        sum_ok = req_sum.status == 200 and isinstance(sum_data, dict)
        results["checks"]["export_summary_json"] = {
            "status": "PASS" if sum_ok else "FAIL",
            "http_status": req_sum.status,
            "bytes": len(sum_bytes),
        }
        print(f"  + Export Summary JSON: {'PASS' if sum_ok else 'FAIL'} ({len(sum_bytes)} bytes)")

        # Check 7: HTTP Range 206 Partial Content
        range_req = urllib.request.Request(f"{base_url}/api/video", headers={"Range": "bytes=0-1023"})
        try:
            with urllib.request.urlopen(range_req) as resp:
                range_status = resp.status
                content_range = resp.headers.get("Content-Range", "")
                range_len = len(resp.read())
                range_ok = range_status == 206 and range_len == 1024
        except urllib.error.HTTPError as e:
            range_status = e.code
            content_range = e.headers.get("Content-Range", "")
            range_len = 0
            range_ok = range_status == 206

        results["checks"]["video_range_206_streaming"] = {
            "status": "PASS" if range_ok else "FAIL",
            "http_status": range_status,
            "content_range": content_range,
            "bytes_received": range_len,
        }
        print(f"  + HTTP Range 206 Partial Content: {'PASS' if range_ok else 'FAIL'}")

        all_ok = all(c.get("status") == "PASS" for c in results["checks"].values())
        results["all_passed"] = all_ok

    finally:
        server.shutdown()
        server.server_close()

    report_path = D11_DIR / "browser_qa_report.json"
    report_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nBrowser QA Report written to: {report_path}")
    print(f"Final QA Verdict: {'ALL CHECKS PASSED' if results['all_passed'] else 'FAILURES DETECTED'}")
    return 0 if results["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
