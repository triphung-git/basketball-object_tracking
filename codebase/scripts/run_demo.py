#!/usr/bin/env python3
"""Launch the spatial dashboard or run detection, tracking and heatmap stages."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import urllib.parse
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from basketball_scoreboard.dashboard import load_run_bundle, make_dashboard_server
from basketball_scoreboard.demo_bundle import install_dashboard_demo, verify_bundle_manifest, verify_dashboard_demo
from basketball_scoreboard.identity import RosterConfig, RosterPlayer
from run_spatial_pipeline import run_spatial_pipeline


def parse_roster(path: Path) -> RosterConfig:
    if not path.is_file():
        raise FileNotFoundError(f"Roster file not found: {path}")
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    players = [RosterPlayer(**player) for player in data["players"]]
    return RosterConfig(
        team_a_id=data["team_a_id"],
        team_b_id=data["team_b_id"],
        team_a_name=data["team_a_name"],
        team_b_name=data["team_b_name"],
        team_a_color_rgb=tuple(data["team_a_color_rgb"]),
        team_b_color_rgb=tuple(data["team_b_color_rgb"]),
        players=players,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["view", "video-analysis"], default="view")
    parser.add_argument("--preset", choices=["default", "vietnam-tonga"])
    parser.add_argument("--video")
    parser.add_argument("--roster")
    parser.add_argument("--output")
    parser.add_argument("--bundle")
    parser.add_argument("--policy")
    parser.add_argument("--court")
    parser.add_argument("--max-frames", type=int)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--job")
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    # Root launchers inject --preset default. That is the shared demo, whereas
    # user-supplied video/bundle arguments deliberately select a saved run.
    explicit_context = bool(args.bundle or args.video or args.roster or
                            args.mode == 'video-analysis' or args.preset == 'vietnam-tonga')
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    if args.max_frames is not None and args.max_frames <= 0:
        parser.error("--max-frames must be positive")

    if args.preset == "vietnam-tonga":
        args.video = args.video or str(ROOT / "assets_test" / "vietnam-tonga.mp4")
        args.roster = args.roster or str(ROOT / "configs" / "rosters" / "vietnam_tonga.json")
        args.court = args.court or str(ROOT / "configs" / "courts" / "vt_development_court.json")
    if args.job and args.mode != "view":
        parser.error("--job can only be used with --mode view")

    if args.mode == "video-analysis":
        if not args.video or not args.output:
            parser.error("--video and --output are required for video-analysis")
        video = Path(args.video).resolve()
        if not video.is_file():
            parser.error(f"Source video file not found: {video}")
        result = run_spatial_pipeline(
            video,
            args.output,
            court_config_path=args.court,
            tracking_policy_path=args.policy,
            roster_config_path=args.roster,
            max_frames=args.max_frames,
        )
        print(
            f"Completed {result['counts']['total_frames_read']} frames; "
            f"{result['spatial']['tracks']} human tracks; "
            f"heatmap {result['spatial']['heatmap_status']}."
        )
        print(f"Artifacts: {Path(args.output).resolve()}")
        bundle = Path(args.output).resolve()
        run_state, heatmap = load_run_bundle(bundle)
        roster = parse_roster(Path(args.roster).resolve()) if args.roster else None
        if not args.serve and not args.open_browser:
            return 0
        video_path = video
    elif args.bundle or args.preset == "vietnam-tonga":
        qa_bundle = ROOT / "outputs" / "demo-completion-20261116" / "demo-bundle-qa-v2"
        default_bundle = qa_bundle if qa_bundle.is_dir() else ROOT / "outputs" / "demo-completion-20261116" / "demo-bundle"
        bundle = Path(args.bundle or default_bundle).resolve()
        if not bundle.is_dir():
            parser.error(f"Saved run not found: {bundle}. Use --bundle to select an existing run.")
        manifest = verify_bundle_manifest(bundle)
        run_state, heatmap = load_run_bundle(bundle)
        video_path = Path(args.video).resolve() if args.video else None
        if video_path and not video_path.is_file():
            video_path = None
        roster_path = Path(args.roster or ROOT / "configs" / "rosters" / "vietnam_tonga.json").resolve()
        roster = parse_roster(roster_path) if roster_path.is_file() else None
        if args.check:
            files = manifest.get("total_files", 0) if manifest else "unmanifested"
            print(f"Spatial bundle ready: {bundle.name} ({files} files)")
            return 0
    else:
        bundle = None
        run_state, heatmap = {}, {}
        video_path = Path(args.video).resolve() if args.video else None
        roster = parse_roster(Path(args.roster).resolve()) if args.roster else None
        if video_path and not video_path.is_file():
            parser.error(f"Source video file not found: {video_path}")
        if not explicit_context:
            try:
                if args.check:
                    manifest = verify_dashboard_demo(ROOT / "demo")
                    print(f"Spatial demo ready ({manifest['total_files']} files)")
                    return 0
                install_dashboard_demo(ROOT / "demo", ROOT / "outputs/web-uploads")
            except (OSError, ValueError, KeyError) as exc:
                parser.error(f"Cannot prepare the dashboard demo: {exc}")

    try:
        server = make_dashboard_server(
            host=args.host,
            port=args.port,
            video_path=video_path,
            roster=roster,
            run_dir=bundle,
            run_state=run_state,
            heatmap_data=heatmap,
            explicit_context=explicit_context,
        )
    except OSError as exc:
        parser.error(f"Cannot start dashboard on {args.host}:{args.port}: {exc}. Choose another --port.")
    query = "?" + urllib.parse.urlencode({"job": args.job}) if args.job else ""
    url = f"http://{args.host}:{server.server_port}/{query}"
    print(f"Spatial dashboard: {url}")
    if args.open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
