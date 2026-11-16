#!/usr/bin/env python3
"""Demonstrate replaceable simulated rosters on real development-video detections.

Real-video color evidence and synthetic jersey fixtures have separate outputs.
No detector, OCR model, ground-truth annotations, or court calibration is loaded.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from basketball_scoreboard.identity import IdentityResolver, JerseyEvidenceRecord, RosterConfig
from basketball_scoreboard.spatial_io import file_hash, new_output, runtime_snapshot, write_json
from track_players import track_players_pipeline


def fixture_check(roster_data):
    """Exercise team-qualified jersey lookup; these are NOT video OCR readings."""
    roster = RosterConfig.from_dict(roster_data)
    resolver = IdentityResolver(roster)
    active = {"fixture_track_a", "fixture_track_b"}
    confirmations = []
    for step in range(4):
        time_s = step * 0.1
        for suffix, team in (("a", roster.team_a_id), ("b", roster.team_b_id)):
            track = f"fixture_track_{suffix}"
            resolver.add_team_observation(track, team, 0.99, time_s)
            resolver.add_jersey_evidence(JerseyEvidenceRecord(
                evidence_id=f"fixture_{suffix}_{step}", track_id=track,
                frame_index=step, source_time_s=time_s, detected_number="7",
                confidence=0.99, ocr_engine="synthetic_fixture_not_video_ocr",
            ))
            mapping = resolver.update_track_mapping(track, time_s, active)
            if step == 3:
                expected = roster.get_player(team, "7")
                if mapping.player_id != expected.player_id:
                    raise AssertionError("Team-qualified fixture lookup failed")
                if resolver.mapping_at(track, 0.0).player_id is not None:
                    raise AssertionError("Fixture identity was backfilled")
                confirmations.append(mapping.to_dict())
    if len({m["player_id"] for m in confirmations}) != 2:
        raise AssertionError("Opposing teams sharing jersey 7 were merged")
    return dict(is_synthetic=True, source_video=None,
                evidence_kind="fabricated_fixture_not_ocr", status="passed",
                confirmations=confirmations, real_identity_accuracy=None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    source = ROOT / "outputs/acceptance-20261102/g03-clip02-verified"
    detections, run_path = source / "detections.jsonl", source / "run.json"
    video = ROOT / "assets_test/20521993-uhd_2160_3840_60fps.mp4"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    if file_hash(video) != run["source_fingerprint_sha256"]:
        raise ValueError("Source video hash mismatch")
    output = new_output(args.output_dir, [source, video, __file__])
    write_json(output / "run.json", dict(status="running", acceptance_scope="diagnostic"))
    try:
        # First collect actual torso RGB samples with the existing diagnostic roster.
        baseline_roster = ROOT / "configs/rosters/synthetic_dual_team_roster.json"
        sample_dir = output / "color-sampling"
        status = track_players_pipeline(detections, sample_dir,
            roster_config_path=baseline_roster, run_json_path=run_path,
            allow_uncalibrated=True, video_path=video)
        if status:
            raise RuntimeError("Color sampling failed")
        colors = json.loads((sample_dir / "team_evidence.json").read_text(encoding="utf-8"))
        if not colors:
            raise ValueError("No real torso color samples available")
        # This clip's main subject supplies a diagnostic prototype, not a team label.
        prototype = np.rint(np.median([r["observed_rgb"] for r in colors], axis=0)).astype(int).tolist()
        profiles = []
        for suffix in ("alpha", "beta"):
            config = dict(
                is_synthetic=True, provenance_status="draft",
                session_id=f"demo_clip02_{suffix}",
                team_a_id=f"demo_{suffix}_a", team_b_id=f"demo_{suffix}_b",
                team_a_name=f"DEMO {suffix.upper()} A",
                team_b_name=f"DEMO {suffix.upper()} B (not verified in video)",
                team_a_color_rgb=prototype, team_b_color_rgb=[220, 30, 30],
                players=[dict(player_id=f"demo_{suffix}_{team}_{number}",
                              team_id=f"demo_{suffix}_{team}", jersey_number=number,
                              name=f"DEMO {suffix} {team.upper()} #{number}", is_active=True)
                         for team in ("a", "b") for number in ("7", "23")],
                simulation_notice="All teams, names and jerseys are placeholders, not video identities.",
                color_provenance=dict(team_a="median torso RGB from whole-clip diagnostic sampling",
                                      team_b="fabricated placeholder; not an observed second team",
                                      is_causal=False),
            )
            RosterConfig.from_dict(config)
            config_path = output / f"roster-{suffix}.json"
            write_json(config_path, config)
            tracking_dir = output / f"tracking-{suffix}"
            status = track_players_pipeline(detections, tracking_dir,
                roster_config_path=config_path, run_json_path=run_path,
                allow_uncalibrated=True, video_path=video)
            if status:
                raise RuntimeError("Roster demo tracking failed")
            rows = [json.loads(line) for line in
                    (tracking_dir / "tracked_observations.jsonl").read_text(encoding="utf-8").splitlines()]
            if any(row.get("player_id") for row in rows):
                raise AssertionError("A video identity was invented without jersey evidence")
            known_teams = {config["team_a_id"], config["team_b_id"], None}
            if any(row.get("team_id") not in known_teams for row in rows):
                raise AssertionError("Team assignment leaked from another roster")
            write_json(output / f"fixture-{suffix}.json", fixture_check(config))
            profiles.append(dict(profile=suffix, roster_file=config_path.name,
                                 roster_sha256=file_hash(config_path),
                                 tracking_directory=tracking_dir.name,
                                 observations=len(rows),
                                 team_assignments=dict(Counter(row.get("team_id") or "unknown" for row in rows)),
                                 resolved_video_players=0, fixture_status="passed"))
        summary = dict(status="completed", acceptance_scope="diagnostic_roster_loading_only",
                       source_video_sha256=file_hash(video), source_run_id=run["run_id"],
                       source_detections_sha256=file_hash(detections), runtime=runtime_snapshot(__file__),
                       team_a_color_rgb=prototype, profiles=profiles,
                       ocr_executed=False, detector_executed=False,
                       court_calibration_used=False,
                       real_team_accuracy=None, real_player_accuracy=None,
                       limitations=["Single-subject clip, not a two-team match",
                                    "Simulated rosters are not recovered real names or jersey numbers",
                                    "Whole-clip color sampling is diagnostic, not causal recognition",
                                    "Synthetic jersey fixtures are isolated from video tracking outputs",
                                    "No PRA events, physical heatmap, or task05/06 data acceptance proven"])
        write_json(output / "summary.json", summary)
        write_json(output / "run.json", summary)
        print(json.dumps(dict(status="completed", output_dir=str(output), profiles=profiles)))
        return 0
    except Exception as error:
        write_json(output / "run.json", dict(status="failed", error_class=type(error).__name__))
        raise


if __name__ == "__main__":
    sys.exit(main())
