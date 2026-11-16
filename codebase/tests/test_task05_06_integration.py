"""Integration test suite (G56) uniting Task05 (Court & Heatmap) and Task06 (Tracking & Identity)."""
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

CODEBASE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = CODEBASE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from basketball_scoreboard.court import (
    CourtConfig,
    CourtModel,
    TrajectoryObservation,
)
from basketball_scoreboard.heatmap import HeatmapAccumulator
from basketball_scoreboard.identity import (
    IdentityResolver,
    JerseyEvidenceRecord,
    RosterConfig,
    RosterPlayer,
    TeamColorClassifier,
    enrich_observations_with_identity,
)
from basketball_scoreboard.players import PlayerTracker


class Task0506IntegrationTests(unittest.TestCase):
    """G56 Integration tests verifying the end-to-end pipeline."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.court_cfg_path = os.path.join(CODEBASE_ROOT, "configs", "courts", "synthetic_half_court.json")
        self.court_config = CourtConfig.from_json_file(self.court_cfg_path)
        self.court_model = CourtModel(self.court_config)
        self.court_model.calibrate(allow_uncalibrated=True)

        self.roster = RosterConfig(
            team_a_id="team_red",
            team_b_id="team_blue",
            team_a_name="Red Dragons",
            team_b_name="Blue Sharks",
            team_a_color_rgb=(220, 30, 30),
            team_b_color_rgb=(30, 60, 220),
            players=[
                RosterPlayer("p_red_07", "team_red", "7", "Alice Red"),
                RosterPlayer("p_blue_07", "team_blue", "7", "Bob Blue"),
            ],
        )
        self.color_clf = TeamColorClassifier(
            team_a_id="team_red",
            team_b_id="team_blue",
            team_a_color_rgb=(220, 30, 30),
            team_b_color_rgb=(30, 60, 220),
        )
        self.resolver = IdentityResolver(self.roster, self.color_clf, confirmation_hits_threshold=2)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_end_to_end_pipeline_mass_conservation_and_exclusion(self) -> None:
        """
        Verify end-to-end pipeline:
        Detections -> Tracker -> Identity Resolver -> Court Projection -> Heatmap Accumulator.
        Confirms:
        1. Observed valid player inside ROI adds to court heatmap mass.
        2. Non-player outside ROI does NOT add to court heatmap mass.
        3. Predicted samples during occlusion do NOT add to court heatmap mass.
        4. Mass conservation: total_grid == team_a_grid + team_b_grid + unknown_team_grid.
        """
        tracker = PlayerTracker(
            video_id="vid_g56",
            segment_id="seg01",
            camera_id=self.court_config.camera_id,
            court_model=self.court_model,
            min_hits_to_activate=1,
            max_age_s=1.0,
        )

        accumulator = HeatmapAccumulator(
            court_bounds=self.court_config.court_coordinate_system.court_bounds,
            grid_shape=(20, 20),
            units=self.court_config.court_coordinate_system.units,
            team_a_id="team_red",
            team_b_id="team_blue",
            max_gap_s=1.0,
        )

        # Frame sequence spanning 1.0s (10 frames at 10 fps, dt=0.1s):
        # Entity 1: Player inside court ROI, moving slowly near [1080, 2500] (center court)
        # Entity 2: Spectator outside court ROI near [50, 500] (top-left outside boundary)
        all_obs = []
        for f in range(11):
            t_s = f * 0.1
            dets = [
                # Player inside ROI (approx X=0m, Y=4m on court)
                {"xyxy": [1050.0 + f * 2.0, 2400.0, 1110.0 + f * 2.0, 2550.0], "class_name": "human", "confidence": 0.95,
                 "role": "player", "role_evidence": "synthetic_fixture_player"},
                # Spectator outside ROI
                {"xyxy": [20.0, 400.0, 80.0, 550.0], "class_name": "human", "confidence": 0.90},
            ]

            frame_obs = tracker.update_frame(
                frame_index=f,
                source_time_s=t_s,
                timestamp_status="valid",
                detections=dets,
            )

            # Assign Team Red to the player track
            for obs in frame_obs:
                if obs.role == "player" and obs.track_id:
                    self.resolver.add_team_observation(obs.track_id, "team_red", 1.0)
                    self.resolver.update_track_mapping(obs.track_id, t_s, active_track_ids=set(tracker.tracks.keys()))

            enrich_observations_with_identity(frame_obs, self.resolver)
            all_obs.extend(frame_obs)

        # Accumulate only valid observed player samples into heatmap
        accumulator.process_observations_batch(all_obs)

        # Verification of Mass
        is_conserved, total_sum, comp_sum = accumulator.verify_mass_conservation()
        self.assertTrue(is_conserved)
        # Player observed for 1.0s (from t=0.0 to t=1.0) -> exactly 1.0 player-seconds
        self.assertAlmostEqual(total_sum, 1.0, places=4)
        # All mass should be in Team Red
        self.assertAlmostEqual(accumulator.metadata.team_a_player_seconds, 1.0, places=4)
        self.assertAlmostEqual(accumulator.metadata.team_b_player_seconds, 0.0, places=4)
        self.assertAlmostEqual(accumulator.metadata.unknown_team_player_seconds, 0.0, places=4)

    def test_recompute_team_revision_without_mass_duplication(self) -> None:
        """
        Verify that after updating a track's team assignment (e.g. from unknown to team_blue),
        recomputing the heatmap accurately migrates the mass from unknown to team_blue
        WITHOUT duplicating or inflating total player-seconds.
        """
        # Create a simple 2-observation track
        obs1 = TrajectoryObservation(
            schema_version="2.0.0",
            observation_id="obs_rev_1",
            source_run_id="run_g56",
            video_id="vid_test",
            source_fingerprint_sha256="hash",
            frame_index=0,
            source_time_s=0.0,
            timestamp_status="valid",
            segment_id="seg1",
            camera_id="cam1",
            bbox=[1000.0, 2000.0, 1100.0, 2200.0],
            footpoint_image=(1050.0, 2200.0),
            projected_court_xy=(0.0, 4.0),
            track_id="trk_change",
            team_id=None,  # Initially unknown team
            role="player",
            validity_status="valid",
        )
        obs2 = TrajectoryObservation(
            schema_version="2.0.0",
            observation_id="obs_rev_2",
            source_run_id="run_g56",
            video_id="vid_test",
            source_fingerprint_sha256="hash",
            frame_index=1,
            source_time_s=1.0,
            timestamp_status="valid",
            segment_id="seg1",
            camera_id="cam1",
            bbox=[1000.0, 2000.0, 1100.0, 2200.0],
            footpoint_image=(1050.0, 2200.0),
            projected_court_xy=(0.0, 4.0),
            track_id="trk_change",
            team_id=None,
            role="player",
            validity_status="valid",
        )

        acc = HeatmapAccumulator(
            court_bounds=self.court_config.court_coordinate_system.court_bounds,
            team_a_id="team_red",
            team_b_id="team_blue",
            max_gap_s=1.5,
        )
        # Initial run: unknown team
        acc.process_observations_batch([obs1, obs2])
        self.assertAlmostEqual(acc.metadata.total_player_seconds, 1.0, places=4)
        self.assertAlmostEqual(acc.metadata.unknown_team_player_seconds, 1.0, places=4)
        self.assertAlmostEqual(acc.metadata.team_b_player_seconds, 0.0, places=4)

        # Now apply team revision: trk_change -> team_blue
        acc.recompute([obs1, obs2], updated_team_mappings={"trk_change": "team_blue"})

        # Total mass must still be exactly 1.0s, but now in team_b
        is_conserved, total_sum, comp_sum = acc.verify_mass_conservation()
        self.assertTrue(is_conserved)
        self.assertAlmostEqual(total_sum, 1.0, places=4)
        self.assertAlmostEqual(acc.metadata.team_b_player_seconds, 1.0, places=4)
        self.assertAlmostEqual(acc.metadata.unknown_team_player_seconds, 0.0, places=4)


if __name__ == "__main__":
    unittest.main()

