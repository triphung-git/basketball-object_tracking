#!/usr/bin/env python3
"""Launch the local video and spatial-analysis dashboard."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from basketball_scoreboard.dashboard import load_run_bundle, make_dashboard_server
from basketball_scoreboard.identity import RosterConfig


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    parser.add_argument("--run-dir", help="Path to a spatial-analysis run directory")
    parser.add_argument("--video", help="Path to a video file")
    parser.add_argument("--roster", help="Optional roster JSON for manual player assignment")
    args = parser.parse_args()

    run_state = {}
    heatmap_data = {}
    video_path = Path(args.video).resolve() if args.video else None
    run_dir = Path(args.run_dir).resolve() if args.run_dir else None

    if run_dir:
        run_state, heatmap_data = load_run_bundle(run_dir)
        if video_path is None:
            run_path = run_dir / "run.json"
            if not run_path.is_file():
                run_path = run_dir / "summary.json"
            raw_run = json.loads(run_path.read_text(encoding="utf-8")) if run_path.is_file() else {}
            configured_video = raw_run.get("video_path")
            if configured_video and Path(configured_video).is_file():
                video_path = Path(configured_video).resolve()

    roster = None
    if args.roster:
        roster_data = json.loads(Path(args.roster).read_text(encoding="utf-8"))
        roster = RosterConfig.from_dict(roster_data)
    server = make_dashboard_server(
        host=args.host,
        port=args.port,
        video_path=video_path,
        roster=roster,
        run_state=run_state,
        heatmap_data=heatmap_data,
        run_dir=run_dir,
    )

    print("============================================================")
    print("  BASKETBALL VIDEO AND SPATIAL DASHBOARD")
    print(f"  URL: http://{args.host}:{server.server_port}")
    print(f"  Video: {video_path} (exists={video_path.is_file() if video_path else False})")
    print("  Press Ctrl+C to stop.")
    print("============================================================")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
