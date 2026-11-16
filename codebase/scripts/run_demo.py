#!/usr/bin/env python3
"""Unified Automatic Basketball Stats Demo Runner (Task 15 / Sequence 01A / D10).

Execution modes:
  - view: Launches interactive local dashboard on verified demo bundle or run output directory.
  - video-analysis: Continuous end-to-end video pipeline.
  - diagnostic-cache: Replays pre-computed observation cache segments without GT hints.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import time
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from basketball_scoreboard.assists import AssistEngine
from basketball_scoreboard.boxscore import BoxScoreEngine
from basketball_scoreboard.continuous_orchestration import run_continuous_orchestration
from basketball_scoreboard.dashboard import make_dashboard_server, load_run_bundle
from basketball_scoreboard.demo_bundle import summarize_run, verify_bundle_manifest
from basketball_scoreboard.events import EventLedger, point_event_to_ledger_record
from basketball_scoreboard.identity import RosterConfig, RosterPlayer
from basketball_scoreboard.points import AttributionLevel, PointEventRecord, PointValueReason
from basketball_scoreboard.rebounds import ReboundEngine
from basketball_scoreboard.shots import ShotEngineConfig

from basketball_scoreboard.video import compute_file_sha256 as file_sha256


def is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def find_available_port(host: str, start_port: int, max_attempts: int = 10) -> int:
    for p in range(start_port, start_port + max_attempts):
        if not is_port_in_use(host, p):
            return p
    raise OSError(f"No available port in range {start_port}..{start_port + max_attempts - 1}")


def parse_roster(roster_path: Path) -> tuple[RosterConfig, list[RosterPlayer]]:
    if not roster_path.is_file():
        raise FileNotFoundError(f"Roster file not found: {roster_path}")
    roster_data = json.loads(roster_path.read_text(encoding="utf-8"))
    for req_field in ["team_a_id", "team_b_id", "team_a_name", "team_b_name", "team_a_color_rgb", "team_b_color_rgb", "players"]:
        if req_field not in roster_data:
            raise ValueError(f"Missing required field '{req_field}' in roster JSON")
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
    return roster, players


def print_banner(mode: str, subtitle: str = ""):
    print("=" * 72)
    print("   AUTOMATIC BASKETBALL STATS DEMO (FIBA 3x3)")
    print(f"   Mode: {mode.upper()}")
    if subtitle:
        print(f"   {subtitle}")
    print("=" * 72)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--preset",
        choices=["default", "vietnam-tonga"],
        help="Convenience preset to automatically configure paths for Vietnam vs Tonga demo",
    )
    parser.add_argument(
        "--mode",
        choices=["view", "video-analysis", "diagnostic-cache"],
        default=None,
        help="Runner mode: 'view' (view demo bundle dashboard), 'video-analysis' (continuous pipeline), or 'diagnostic-cache'",
    )
    parser.add_argument("--video", default=None, help="Path to source video MP4")
    parser.add_argument("--roster", default=None, help="Path to roster JSON")
    parser.add_argument("--output", default=None, help="Path to output directory (must not already exist)")
    parser.add_argument(
        "--bundle",
        default=None,
        help="Path to demo bundle or run output directory for 'view' mode",
    )
    parser.add_argument(
        "--baseline-dir",
        default=None,
        help="Path to cached observation baseline directory",
    )
    parser.add_argument("--policy", help="Path to tracking policy JSON (scene cuts and ROI)")
    parser.add_argument("--court", help="Path to court config JSON")
    parser.add_argument("--detections-cache", help="Path to validated detections.jsonl cache")
    parser.add_argument("--ocr-cache", help="Path to validated jersey_evidence.json cache")
    parser.add_argument("--disable-ocr", action="store_true", help="Disable local OCR execution")
    parser.add_argument("--allow-uncalibrated", action="store_true", default=True, help="Allow uncalibrated/diagnostic mode")
    parser.add_argument("--require-calibrated", dest="allow_uncalibrated", action="store_false", help="Reject input outside reviewed calibration scope")
    parser.add_argument("--max-frames", type=int, help="Optional frame processing limit")
    parser.add_argument("--start-time-s", type=float, default=None, help="First source timestamp to process")
    parser.add_argument("--end-time-s", type=float, default=None, help="Last source timestamp to process")
    parser.add_argument("--serve", action="store_true", help="Launch interactive local dashboard upon completion")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind")
    parser.add_argument("--port", type=int, default=8080, help="Port for local dashboard")
    parser.add_argument("--open-browser", action="store_true", help="Automatically open web browser on dashboard URL")
    parser.add_argument("--check", action="store_true", help="Validate view bundle and exit without starting a server")
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    if args.max_frames is not None and args.max_frames <= 0:
        parser.error("--max-frames must be positive")

    # 1. Preset Resolution
    if args.preset in {"default", "vietnam-tonga"}:
        if args.mode is None:
            args.mode = "view"
        if args.video is None:
            args.video = str(ROOT / "assets_test/vietnam-tonga.mp4")
        if args.roster is None:
            args.roster = str(ROOT / "configs/rosters/vietnam_tonga.json")
        if args.court is None:
            args.court = str(ROOT / "configs/courts/vt_development_court.json")
        if args.bundle is None:
            qa_bundle = ROOT / "outputs/demo-completion-20261116/demo-bundle-qa-v2"
            args.bundle = str(qa_bundle if qa_bundle.is_dir() else ROOT / "outputs/demo-completion-20261116/demo-bundle")
    else:
        # Default mode if not preset and not explicitly provided
        if args.mode is None:
            # If user explicitly passed --output or --baseline-dir, fallback to diagnostic-cache for backwards compatibility
            if args.bundle or args.check:
                args.mode = "view"
            else:
                args.mode = "diagnostic-cache"
        if args.video is None:
            args.video = str(ROOT / "assets_test/vietnam-tonga.mp4")
        if args.roster is None:
            args.roster = str(ROOT / "configs/rosters/vietnam_tonga.json")
        if args.baseline_dir is None:
            args.baseline_dir = str(ROOT / "outputs/task08-critical-baseline-20261108")

    t_start = time.perf_counter()

    # =========================================================================
    # MODE 1: VIEW (Demo Bundle Dashboard Viewer)
    # =========================================================================
    if args.mode == "view":
        print_banner("VIEW", "Interactive Local Dashboard & Demo Bundle Viewer")
        qa_bundle = ROOT / "outputs/demo-completion-20261116/demo-bundle-qa-v2"
        default_bundle = qa_bundle if qa_bundle.is_dir() else ROOT / "outputs/demo-completion-20261116/demo-bundle"
        bundle_path = Path(args.bundle or default_bundle).resolve()
        if not bundle_path.is_dir():
            print(f"Error: Demo bundle directory not found: {bundle_path}", file=sys.stderr)
            return 1

        try:
            mdata = verify_bundle_manifest(bundle_path)
            ledger, run_state, heatmap_data = load_run_bundle(bundle_path)
            if mdata:
                print(f"[Preflight] Verified manifest '{mdata.get('bundle_id')}': {mdata.get('total_files')} files ({mdata.get('total_bytes', 0) / (1024*1024):.2f} MB)")
            else:
                print(f"[Preflight] Inspecting run bundle directory: {bundle_path.name}")
        except (ValueError, OSError, KeyError, TypeError) as exc:
            print(f"Error: Invalid demo bundle: {exc}", file=sys.stderr)
            return 1

        # Video resolution
        video_path = None
        if (bundle_path / "annotated.mp4").is_file():
            video_path = (bundle_path / "annotated.mp4").resolve()
        elif args.video and Path(args.video).is_file():
            video_path = Path(args.video).resolve()
        elif (ROOT / "assets_test/vietnam-tonga.mp4").is_file():
            video_path = (ROOT / "assets_test/vietnam-tonga.mp4").resolve()

        # Roster resolution
        roster_path = Path(args.roster).resolve()
        try:
            roster, players = parse_roster(roster_path)
            print(f"[Preflight] Roster loaded: {roster.team_a_name} vs {roster.team_b_name} ({len(players)} players)")
        except Exception as exc:
            print(f"Error: Failed to parse roster file {roster_path}: {exc}", file=sys.stderr)
            return 1

        if args.check:
            print(f"[Preflight] PASS | video={video_path.name if video_path else 'unavailable'} | demo={run_state.get('demo_verdict', 'DEMO_PARTIAL')} | quality={run_state.get('quality_gate', 'NOT_ACCEPTED')}")
            return 0

        # Port resolution
        selected_port = args.port
        if is_port_in_use(args.host, selected_port):
            avail = find_available_port(args.host, selected_port + 1)
            print(f"[Warning] Port {selected_port} is already in use. Switching to port {avail}.")
            selected_port = avail

        box_engine = BoxScoreEngine(roster=roster)

        server = make_dashboard_server(
            host=args.host,
            port=selected_port,
            video_path=video_path,
            roster=roster,
            ledger=ledger,
            box_engine=box_engine,
            run_state=run_state,
            heatmap_data=heatmap_data,
            run_dir=bundle_path,
        )

        url = f"http://{args.host}:{server.server_port}"
        print("-" * 72)
        print(f"  Server URL:       {url}")
        print(f"  Video Playback:   {video_path.name if video_path else 'None'}")
        print(f"  Confirmed Events: {len(ledger.get_active_events())} active events")
        print(f"  Box Score Export: {url}/api/export/boxscore")
        print(f"  Events Export:    {url}/api/export/events")
        print(f"  Summary Export:   {url}/api/export/summary")
        print("-" * 72)
        print("  Press Ctrl+C to terminate dashboard server.")
        print("=" * 72)

        if args.open_browser:
            webbrowser.open(url)

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down dashboard server...")
        finally:
            server.server_close()
        return 0

    # =========================================================================
    # MODE 2: VIDEO ANALYSIS (Continuous Video Pipeline)
    # =========================================================================
    if args.mode == "video-analysis":
        print_banner("VIDEO-ANALYSIS", "Continuous End-to-End Production Pipeline")
        if not args.output:
            print("Error: --output directory path is required for video-analysis mode.", file=sys.stderr)
            return 1

        out_dir = Path(args.output).resolve()
        if out_dir.exists():
            print(
                f"Error: Output directory already exists: {out_dir}. "
                "Overwriting existing evidence is prohibited. Please specify a new directory.",
                file=sys.stderr,
            )
            return 1

        video_path = Path(args.video).resolve()
        if not video_path.is_file():
            print(f"Error: Source video file not found: {video_path}", file=sys.stderr)
            return 1

        roster_path = Path(args.roster).resolve()
        if not roster_path.is_file():
            print(f"Error: Roster file not found: {roster_path}", file=sys.stderr)
            return 1

        try:
            res = run_continuous_orchestration(
                video_path=video_path,
                output_dir=out_dir,
                roster_config_path=roster_path,
                court_config_path=args.court,
                tracking_policy_path=args.policy,
                detections_cache_path=args.detections_cache,
                ocr_cache_path=args.ocr_cache,
                enable_ocr=not args.disable_ocr,
                allow_uncalibrated=args.allow_uncalibrated,
                max_frames=args.max_frames,
                start_time_s=args.start_time_s,
                end_time_s=args.end_time_s,
            )
            pts_m = res["boxscore_totals"]["match_totals"]["points"]
            reb_m = res["boxscore_totals"]["match_totals"]["rebounds"]
            ast_m = res["boxscore_totals"]["match_totals"]["assists"]
            heatmap = json.loads((out_dir / "heatmap_summary.json").read_text(encoding="utf-8"))
            summary_data = summarize_run(res, heatmap)
            from render_annotated_video import render_overlay_video
            coverage = res["source_coverage"]
            render_overlay_video(
                video_path, out_dir / "annotated.mp4", out_dir,
                start_time_s=coverage["first_time_s"],
                end_time_s=coverage["last_time_s"],
                max_frames=res["stage_counts"]["total_frames_read"],
            )
            (out_dir / "summary.json").write_text(json.dumps(summary_data, indent=2) + "\n", encoding="utf-8")
            print(f"Completed run ({res['status']}): {res['stage_counts']['total_frames_read']} frames, {res['stage_counts']['confirmed_shots']} shots, {pts_m} PTS, {reb_m} REB, {ast_m} AST")
            print(f"Artifacts: {out_dir}")

            if args.serve:
                display_roster = RosterConfig.from_dict(json.loads(roster_path.read_text(encoding="utf-8")))
                server = make_dashboard_server(
                    run_dir=out_dir,
                    video_path=out_dir / "annotated.mp4",
                    roster=display_roster,
                    box_engine=BoxScoreEngine(roster=display_roster),
                    host=args.host,
                    port=args.port,
                )
                print(f"Serving dashboard at http://{args.host}:{server.server_port} (Ctrl+C to stop)")
                if args.open_browser:
                    webbrowser.open(f"http://{args.host}:{server.server_port}")
                try:
                    server.serve_forever()
                except KeyboardInterrupt:
                    pass
                finally:
                    server.server_close()
            return 0
        except Exception as exc:
            print(f"Error during video analysis pipeline: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1

    # =========================================================================
    # MODE 3: DIAGNOSTIC CACHE (Replay Observation Cache)
    # =========================================================================
    print_banner("DIAGNOSTIC-CACHE", "Replay Pre-computed Observation Cache")
    from run_task08_temporal_shot_engine import run_engine_on_window

    if not args.output:
        print("Error: --output directory path is required for diagnostic-cache mode.", file=sys.stderr)
        return 1

    out_dir = Path(args.output).resolve()
    if out_dir.exists():
        print(
            f"Error: Output directory already exists: {out_dir}. "
            "Overwriting existing evidence is prohibited. Please specify a new directory.",
            file=sys.stderr,
        )
        return 1

    video_path = Path(args.video).resolve()
    if not video_path.is_file():
        print(f"Error: Source video file not found: {video_path}", file=sys.stderr)
        return 1
    video_sha = file_sha256(video_path)
    print(f"1. Verified Source Video: {video_path.name} (SHA-256: {video_sha[:16]}...)")

    roster_path = Path(args.roster).resolve()
    try:
        roster, players = parse_roster(roster_path)
    except FileNotFoundError:
        print(f"Error: Roster file not found: {roster_path}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: Failed to parse roster file {roster_path}: {exc}", file=sys.stderr)
        return 1
    print(f"   Roster loaded: {roster.team_a_name} vs {roster.team_b_name} ({len(players)} players)")

    baseline_dir = Path(args.baseline_dir).resolve()
    if not baseline_dir.is_dir():
        print(f"Error: Baseline cache directory not found: {baseline_dir}", file=sys.stderr)
        return 1

    manifest_path = baseline_dir / "recognition_input_manifest.json"
    run_json_path = baseline_dir / "run.json"

    cache_source_sha: str | None = None
    manifest_windows: list[str] = []
    binding_type = "none"

    if manifest_path.is_file():
        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            provenance = manifest_data.get("provenance", {})
            cache_source_sha = provenance.get("source_sha256")
            manifest_windows = [
                w["window_id"] for w in manifest_data.get("windows", []) if isinstance(w, dict) and "window_id" in w
            ]
            binding_type = "manifest_v1"
        except Exception as exc:
            print(f"Error: Failed to parse cache manifest {manifest_path}: {exc}", file=sys.stderr)
            return 1
    elif run_json_path.is_file():
        try:
            run_data = json.loads(run_json_path.read_text(encoding="utf-8"))
            cache_source_sha = run_data.get("source_fingerprint_sha256")
            binding_type = "run_json_v1"
        except Exception as exc:
            print(f"Error: Failed to parse cache run.json {run_json_path}: {exc}", file=sys.stderr)
            return 1

    if cache_source_sha is not None:
        if video_sha.lower() != cache_source_sha.lower():
            print(
                f"Error: Cache/source mismatch: Source video SHA-256 ({video_sha}) "
                f"does not match cache binding ({cache_source_sha}).",
                file=sys.stderr,
            )
            return 1
        print(f"   Cache binding verified ({binding_type}): matched source SHA-256.")
    else:
        binding_type = "legacy_unbound_diagnostic"
        print(f"   Warning: Cache lacks explicit source SHA-256 binding. Proceeding with legacy diagnostic path.")

    if not manifest_windows:
        manifest_windows = sorted([p.name for p in baseline_dir.iterdir() if p.is_dir() and p.name.startswith("play_")])

    print(f"   Manifest target windows ({len(manifest_windows)}): {', '.join(manifest_windows) if manifest_windows else 'none'}")

    shot_config = ShotEngineConfig(
        enable_net_cue=True,
        shot_cooldown_seconds=2.0,
        replay_suppression_enabled=True,
    )
    rebound_engine = ReboundEngine()
    assist_engine = AssistEngine()
    ledger = EventLedger()
    box_engine = BoxScoreEngine(roster=roster)

    print(f"2. Running Temporal FSM across {len(manifest_windows)} manifest windows...")
    processed_windows: list[str] = []
    skipped_windows: list[dict[str, str]] = []
    invalid_windows: list[dict[str, str]] = []

    total_shots_confirmed = 0

    for wid in manifest_windows:
        w_dir = baseline_dir / wid
        if not w_dir.is_dir():
            skipped_windows.append({"window_id": wid, "reason": "directory not found in cache"})
            continue

        ball_tracks_file = w_dir / "ball_tracks.jsonl"
        tracked_obs_file = w_dir / "tracked_observations.jsonl"
        raw_dets_file = w_dir / "raw_detections.jsonl"

        if not (ball_tracks_file.is_file() and tracked_obs_file.is_file() and raw_dets_file.is_file()):
            invalid_windows.append({"window_id": wid, "reason": "missing required observation jsonl files"})
            continue

        try:
            ball_tracks = [json.loads(line) for line in ball_tracks_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            tracked_obs = [json.loads(line) for line in tracked_obs_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            raw_dets = [json.loads(line) for line in raw_dets_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            jersey_ev_file = w_dir / "jersey_evidence.json"
            jersey_ev = json.loads(jersey_ev_file.read_text(encoding="utf-8")) if jersey_ev_file.is_file() else []
        except Exception as exc:
            invalid_windows.append({"window_id": wid, "reason": f"corrupted json/jsonl file: {exc}"})
            continue

        shots, points, transitions = run_engine_on_window(
            window_id=wid,
            ball_tracks=ball_tracks,
            tracked_obs=tracked_obs,
            raw_detections=raw_dets,
            jersey_evidence=jersey_ev,
            roster=roster,
            config=shot_config,
        )

        for ptev in points:
            rec = point_event_to_ledger_record(ptev)
            ledger.record_event(rec)
            total_shots_confirmed += 1

        processed_windows.append(wid)

    print(f"   Window execution complete: {len(processed_windows)} processed, {len(skipped_windows)} skipped, {len(invalid_windows)} invalid.")
    print(f"   Confirmed made shot events recorded: {total_shots_confirmed}")

    if len(manifest_windows) == 0 or len(processed_windows) == 0:
        execution_status = "failed"
    elif len(processed_windows) < len(manifest_windows):
        execution_status = "partial"
    else:
        execution_status = "completed"

    team_a_box, team_b_box = box_engine.compile(ledger)
    print("3. Compiled Box Score:")
    print(f"   {team_a_box.team_name}: Total Score = {team_a_box.total_score} (Unresolved shots: {team_a_box.unresolved_shots})")
    print(f"   {team_b_box.team_name}: Total Score = {team_b_box.total_score} (Unresolved shots: {team_b_box.unresolved_shots})")

    out_dir.mkdir(parents=True, exist_ok=False)

    events_export_path = out_dir / "events_auto.jsonl"
    raw_events_path = out_dir / "events_raw.jsonl"
    audit_trail_path = out_dir / "audit_trail.jsonl"
    checkpoint_path = out_dir / "checkpoint.json"
    boxscore_export_path = out_dir / "boxscore_auto.csv"
    summary_path = out_dir / "summary.json"

    ledger.export_jsonl(events_export_path)
    ledger.export_raw_transactions(raw_events_path)
    ledger.export_audit_log(audit_trail_path)
    ledger.save_checkpoint(checkpoint_path)
    BoxScoreEngine.export_csv(team_a_box, team_b_box, boxscore_export_path)

    elapsed = time.perf_counter() - t_start
    summary_data = {
        "schema_version": "demo-diagnostic-replay-v2",
        "mode": args.mode,
        "pipeline_scope": "diagnostic_cache_replay",
        "status": execution_status,
        "summary_note": "Replayed pre-computed observation cache; continuous video pipeline is not yet integrated.",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "video": {
            "path": str(video_path),
            "sha256": video_sha,
            "status": "verified_against_cache" if cache_source_sha else "verified_file_exists",
        },
        "roster": {
            "path": str(roster_path),
            "team_a": roster.team_a_name,
            "team_b": roster.team_b_name,
            "players_count": len(players),
        },
        "cache": {
            "baseline_dir": str(baseline_dir),
            "binding_type": binding_type,
            "bound_source_sha256": cache_source_sha,
        },
        "window_manifest": {
            "total_windows": len(manifest_windows),
            "processed_count": len(processed_windows),
            "processed_windows": processed_windows,
            "skipped_count": len(skipped_windows),
            "skipped_windows": skipped_windows,
            "invalid_count": len(invalid_windows),
            "invalid_windows": invalid_windows,
        },
        "results": {
            "total_active_events": len(ledger.get_active_events()),
            "total_shots_confirmed": total_shots_confirmed,
            "team_a_score": team_a_box.total_score,
            "team_b_score": team_b_box.total_score,
            "team_a_unresolved_shots": team_a_box.unresolved_shots,
            "team_b_unresolved_shots": team_b_box.unresolved_shots,
            "elapsed_s": round(elapsed, 3),
        },
        "exports": {
            "events_jsonl": str(events_export_path),
            "events_raw_jsonl": str(raw_events_path),
            "audit_trail_jsonl": str(audit_trail_path),
            "checkpoint_json": str(checkpoint_path),
            "boxscore_csv": str(boxscore_export_path),
        },
    }
    summary_path.write_text(json.dumps(summary_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("4. Deliverables Successfully Written:")
    print(f"   - Events Log (Active): {events_export_path}")
    print(f"   - Raw Transactions:   {raw_events_path}")
    print(f"   - Audit Trail:        {audit_trail_path}")
    print(f"   - Checkpoint:         {checkpoint_path}")
    print(f"   - Box Score:          {boxscore_export_path}")
    print(f"   - Summary:            {summary_path}")
    print(f"   Replay completed in {elapsed:.2f}s with status '{execution_status}'.")

    if args.serve:
        print("\n5. Starting Local Integrated Dashboard...")
        server = make_dashboard_server(
            host=args.host,
            port=args.port,
            video_path=video_path,
            roster=roster,
            ledger=ledger,
            box_engine=box_engine,
        )
        print(f"   URL: http://{args.host}:{args.port}")
        print("   Press Ctrl+C to terminate.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down dashboard...")
        finally:
            server.server_close()

    return 0 if execution_status in {"completed", "partial"} else 1


if __name__ == "__main__":
    sys.exit(main())
