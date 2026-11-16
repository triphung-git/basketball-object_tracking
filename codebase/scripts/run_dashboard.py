#!/usr/bin/env python3
"""CLI entrypoint to launch the local integrated stats dashboard (Task 12 & Task 05A)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from basketball_scoreboard.boxscore import BoxScoreEngine
from basketball_scoreboard.dashboard import make_dashboard_server, load_run_bundle
from basketball_scoreboard.events import EventLedger, point_event_to_ledger_record
from basketball_scoreboard.identity import RosterConfig, RosterPlayer
from basketball_scoreboard.points import AttributionLevel, PointEventRecord, PointValueReason


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default 8080)")
    parser.add_argument("--run-dir", default=None, help="Path to production run output directory (e.g. outputs/.../run/candidate_court_dist)")
    parser.add_argument("--video", default=None, help="Path to video file")
    parser.add_argument("--roster", default=str(ROOT / "configs/rosters/vietnam_tonga.json"), help="Path to roster JSON")
    parser.add_argument("--points-jsonl", default=None, help="Optional legacy path to points_auto.jsonl")
    args = parser.parse_args()

    roster_path = Path(args.roster).resolve()
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

    ledger = EventLedger()
    run_state = {}
    heatmap_data = {}
    video_path = None

    if args.run_dir:
        run_dir_path = Path(args.run_dir).resolve()
        ledger, run_state, heatmap_data = load_run_bundle(run_dir_path)
        if not args.video:
            # check run_state for video_path
            cfg_vid = run_state.get("video_path")
            if cfg_vid and Path(cfg_vid).is_file():
                video_path = Path(cfg_vid).resolve()

    if not video_path:
        if args.video:
            video_path = Path(args.video).resolve()
        else:
            candidates = [
                ROOT / "data/v2/videos/vt_development.mp4",
                ROOT / "assets_test/vietnam-tonga.mp4",
            ]
            for c in candidates:
                if c.is_file():
                    video_path = c.resolve()
                    break

    if args.points_jsonl and Path(args.points_jsonl).is_file():
        raw_points = [json.loads(line) for line in Path(args.points_jsonl).read_text(encoding="utf-8").splitlines() if line.strip()]
        for p in raw_points:
            ptev = PointEventRecord(
                event_id=p["event_id"],
                shot_id=p["shot_id"],
                video_id=p["video_id"],
                source_time_s=p["source_time_s"],
                confirmation_time_s=p["confirmation_time_s"],
                status=p["status"],
                scoring_team_id=p["scoring_team_id"],
                scoring_player_id=p["scoring_player_id"],
                attribution_level=AttributionLevel(p["attribution_level"]),
                point_value=p["point_value"],
                value_reason=PointValueReason(p["value_reason"]),
                evidence_refs=p.get("evidence_refs", {}),
            )
            rec = point_event_to_ledger_record(ptev)
            ledger.record_event(rec)

    box_engine = BoxScoreEngine(roster=roster)
    server = make_dashboard_server(
        host=args.host,
        port=args.port,
        video_path=video_path,
        roster=roster,
        ledger=ledger,
        box_engine=box_engine,
        run_state=run_state,
        heatmap_data=heatmap_data,
    )

    print(f"============================================================")
    print(f"  BASKETBALL SCOREBOARD LOCAL DASHBOARD RUNNING")
    print(f"  URL: http://{args.host}:{args.port}")
    print(f"  Video: {video_path} (exists={video_path.is_file() if video_path else False})")
    print(f"  Events loaded: {len(ledger.get_active_events())}")
    print(f"  Press Ctrl+C to stop.")
    print(f"============================================================")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
