"""Unit and contract tests for Task05 court calibration, homography, and heatmap accumulation."""
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

import numpy as np

from basketball_scoreboard.court import (
    CourtConfig,
    CourtCoordinateSystem,
    CourtModel,
    DegenerateGeometryError,
    HomographyResult,
    PointCorrespondence,
    TrajectoryObservation,
    UncalibratedCourtError,
    check_non_collinear,
    estimate_footpoint,
    project_point,
    solve_homography,
)
from basketball_scoreboard.heatmap import (
    ExclusionInterval,
    HeatmapAccumulator,
)


class Task05CourtGeometryTests(unittest.TestCase):
    """Tests for homography computation, geometry constraints, and footpoint estimation."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_homography_identity_transform(self) -> None:
        """Test that identical image and court points yield identity matrix and zero residual."""
        pts = [
            PointCorrespondence("p1", "Corner 1", (0.0, 0.0), (0.0, 0.0)),
            PointCorrespondence("p2", "Corner 2", (100.0, 0.0), (100.0, 0.0)),
            PointCorrespondence("p3", "Corner 3", (100.0, 100.0), (100.0, 100.0)),
            PointCorrespondence("p4", "Corner 4", (0.0, 100.0), (0.0, 100.0)),
        ]
        res = solve_homography(pts)
        H = res.matrix_image_to_court
        # Should be scaled identity
        scale = H[2, 2]
        H_normalized = H / scale
        np.testing.assert_allclose(H_normalized, np.eye(3), atol=1e-6)
        self.assertLess(res.mean_fit_residual_px, 1e-5)

    def test_homography_known_affine_transform_roundtrip(self) -> None:
        """Test known scale and translation transform round-trip projection."""
        # court = 0.1 * image + [5, 10]
        img_coords = [(100.0, 200.0), (500.0, 200.0), (500.0, 800.0), (100.0, 800.0)]
        court_coords = [(15.0, 30.0), (55.0, 30.0), (55.0, 90.0), (15.0, 90.0)]
        pts = [
            PointCorrespondence(f"p{i}", f"Point {i}", img_coords[i], court_coords[i])
            for i in range(4)
        ]
        res = solve_homography(pts)
        H_i2c = res.matrix_image_to_court
        H_c2i = res.matrix_court_to_image

        for img_pt, court_pt in zip(img_coords, court_coords):
            proj_c = project_point(img_pt, H_i2c)
            self.assertIsNotNone(proj_c)
            self.assertAlmostEqual(proj_c[0], court_pt[0], places=4)
            self.assertAlmostEqual(proj_c[1], court_pt[1], places=4)

            # Roundtrip back to image
            proj_img = project_point(proj_c, H_c2i)
            self.assertIsNotNone(proj_img)
            self.assertAlmostEqual(proj_img[0], img_pt[0], places=4)
            self.assertAlmostEqual(proj_img[1], img_pt[1], places=4)

    def test_homography_rejects_fewer_than_four_points(self) -> None:
        """Test rejection when fewer than 4 correspondences are provided."""
        pts = [
            PointCorrespondence("p1", "P1", (0.0, 0.0), (0.0, 0.0)),
            PointCorrespondence("p2", "P2", (10.0, 0.0), (10.0, 0.0)),
            PointCorrespondence("p3", "P3", (10.0, 10.0), (10.0, 10.0)),
        ]
        with self.assertRaises(DegenerateGeometryError):
            solve_homography(pts)

    def test_homography_rejects_collinear_points(self) -> None:
        """Test rejection when fit points are collinear."""
        pts = [
            PointCorrespondence("p1", "P1", (10.0, 10.0), (1.0, 1.0)),
            PointCorrespondence("p2", "P2", (20.0, 20.0), (2.0, 2.0)),
            PointCorrespondence("p3", "P3", (30.0, 30.0), (3.0, 3.0)),  # Collinear!
            PointCorrespondence("p4", "P4", (40.0, 40.0), (4.0, 4.0)),
        ]
        with self.assertRaises(DegenerateGeometryError):
            solve_homography(pts)

    def test_homography_rejects_non_coplanar_rim(self) -> None:
        """Test explicit rejection of elevated rim points for floor homography."""
        pts = [
            PointCorrespondence("p1", "Corner 1", (0.0, 0.0), (0.0, 0.0), is_coplanar=True),
            PointCorrespondence("p2", "Corner 2", (100.0, 0.0), (10.0, 0.0), is_coplanar=True),
            PointCorrespondence("p3", "Corner 3", (100.0, 100.0), (10.0, 10.0), is_coplanar=True),
            PointCorrespondence("rim", "Rim center", (50.0, 50.0), (5.0, 5.0), is_coplanar=False, usage="fit"),
        ]
        with self.assertRaises(DegenerateGeometryError) as ctx:
            solve_homography(pts)
        self.assertIn("Non-coplanar points cannot be used", str(ctx.exception))

    def test_project_point_handles_near_zero_denominator(self) -> None:
        """Test that projection returns None if denominator is near zero."""
        # A matrix where [x, y, 1] row 2 results in 0
        H = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [1.0, 0.0, -10.0],  # w = x - 10
        ])
        # x = 10.0 -> w = 0.0
        res = project_point((10.0, 5.0), H)
        self.assertIsNone(res)

    def test_footpoint_estimation_and_boundary_detection(self) -> None:
        """Test footpoint extraction and boundary touch classification."""
        orig_wh = (1920, 1080)
        # Normal inside bbox
        bbox_normal = [500.0, 200.0, 600.0, 450.0]
        foot, status, reason = estimate_footpoint(bbox_normal, orig_wh)
        self.assertEqual(foot, (550.0, 450.0))
        self.assertEqual(status, "valid")
        self.assertIsNone(reason)

        # Touching bottom (y2 >= 1080 - 5 = 1075)
        bbox_bottom = [500.0, 700.0, 600.0, 1078.0]
        foot, status, reason = estimate_footpoint(bbox_bottom, orig_wh)
        self.assertEqual(status, "touch_boundary")
        self.assertIn("touches image bottom", reason)

        # Touching left edge
        bbox_left = [2.0, 200.0, 100.0, 400.0]
        foot, status, reason = estimate_footpoint(bbox_left, orig_wh)
        self.assertEqual(status, "touch_boundary")

    def test_uncalibrated_court_config_rejection(self) -> None:
        """Test that unvalidated template config is rejected in calibrated mode."""
        config = CourtConfig(
            schema_version="2.0.0",
            camera_id="test_cam",
            segment_id="seg01",
            original_image_wh=(1920, 1080),
            status="template",
            court_coordinate_system=CourtCoordinateSystem(
                origin="basket",
                axes={"x": "right", "y": "up"},
                units="normalized",
                court_bounds={"x_min": -1.0, "x_max": 1.0, "y_min": 0.0, "y_max": 1.0},
            ),
            point_correspondences=[
                PointCorrespondence("p1", "P1", (0.0, 0.0), (0.0, 0.0)),
                PointCorrespondence("p2", "P2", (100.0, 0.0), (1.0, 0.0)),
                PointCorrespondence("p3", "P3", (100.0, 100.0), (1.0, 1.0)),
                PointCorrespondence("p4", "P4", (0.0, 100.0), (0.0, 1.0)),
            ],
            provenance={"review_status": "unreviewed"},
        )
        model = CourtModel(config)
        with self.assertRaises(UncalibratedCourtError):
            model.calibrate(allow_uncalibrated=False)

        # But succeeds when allow_uncalibrated=True
        homography = model.calibrate(allow_uncalibrated=True)
        self.assertIsNotNone(homography)


class Task05HeatmapAccumulationTests(unittest.TestCase):
    """Tests for player-seconds time integration, staleness, exclusions, and mass conservation."""

    def test_sampling_rate_invariance_three_players_two_seconds(self) -> None:
        """
        Critical requirement: 3 persons observed for 2.0s = 6.0 player-seconds,
        regardless of whether sampled at 30 fps or 60 fps.
        """
        bounds = {"x_min": 0.0, "x_max": 10.0, "y_min": 0.0, "y_max": 10.0}

        for fps in [30.0, 60.0]:
            acc = HeatmapAccumulator(court_bounds=bounds, grid_shape=(10, 10), units="meters")
            dt = 1.0 / fps
            num_frames = int(round(2.0 * fps))

            # Simulate 3 players across 2.0 seconds
            # Player 1 at (2.0, 2.0), Player 2 at (5.0, 5.0), Player 3 at (8.0, 8.0)
            player_positions = [
                ("p1", (2.0, 2.0)),
                ("p2", (5.0, 5.0)),
                ("p3", (8.0, 8.0)),
            ]

            obs_list: List[TrajectoryObservation] = []
            obs_id = 0
            for frame_idx in range(num_frames + 1):
                t_s = frame_idx * dt
                for pid, pos in player_positions:
                    obs = TrajectoryObservation(
                        schema_version="2.0.0",
                        observation_id=f"obs_{pid}_{obs_id}",
                        source_run_id="run_test",
                        video_id="vid_test",
                        source_fingerprint_sha256="hash",
                        frame_index=frame_idx,
                        source_time_s=t_s,
                        timestamp_status="valid",
                        segment_id="seg1",
                        camera_id="cam1",
                        bbox=[100.0, 100.0, 200.0, 200.0],
                        footpoint_image=(150.0, 200.0),
                        projected_court_xy=pos,
                        track_id=pid,
                        validity_status="valid", role="player",
                    )
                    obs_list.append(obs)
                    obs_id += 1

            acc.process_observations_batch(obs_list)
            is_conserved, total_sum, _ = acc.verify_mass_conservation()
            self.assertTrue(is_conserved)
            # Total mass should equal exactly 3 players * 2.0s = 6.0 player-seconds
            self.assertAlmostEqual(total_sum, 6.0, delta=1e-3, msg=f"Failed for fps={fps}")

    def test_vfr_mass_preservation(self) -> None:
        """Test that variable frame rate timestamps preserve true time duration."""
        bounds = {"x_min": 0.0, "x_max": 10.0, "y_min": 0.0, "y_max": 10.0}
        # Allow gaps up to 1.5s so 1.2s step is included
        acc = HeatmapAccumulator(court_bounds=bounds, grid_shape=(10, 10), units="meters", max_gap_s=1.5)

        # Irregular timestamps spanning exactly 3.0s: 0.0, 0.1, 0.45, 1.2, 1.8, 3.0
        timestamps = [0.0, 0.1, 0.45, 1.2, 1.8, 3.0]
        obs_list = [
            TrajectoryObservation(
                schema_version="2.0.0",
                observation_id=f"obs_{i}",
                source_run_id="run_test",
                video_id="vid_test",
                source_fingerprint_sha256="hash",
                frame_index=i,
                source_time_s=t,
                timestamp_status="valid",
                segment_id="seg1",
                camera_id="cam1",
                bbox=[100.0, 100.0, 200.0, 200.0],
                footpoint_image=(150.0, 200.0),
                projected_court_xy=(3.0, 3.0),
                track_id="tr1",
                validity_status="valid", role="player",
            )
            for i, t in enumerate(timestamps)
        ]
        acc.process_observations_batch(obs_list)
        is_conserved, total_sum, _ = acc.verify_mass_conservation()
        self.assertTrue(is_conserved)
        self.assertAlmostEqual(total_sum, 3.0, places=4)

    def test_max_gap_interruption(self) -> None:
        """Test that gaps exceeding max_gap_s are interrupted and do not accumulate mass."""
        bounds = {"x_min": 0.0, "x_max": 10.0, "y_min": 0.0, "y_max": 10.0}
        acc = HeatmapAccumulator(court_bounds=bounds, grid_shape=(10, 10), max_gap_s=1.0)

        # Observations: t=0.0 to t=0.5 (dt=0.5 -> added), then jump to t=3.0 (dt=2.5 > 1.0 -> gap break!), then t=3.5 (dt=0.5 -> added)
        obs_list = [
            TrajectoryObservation(
                schema_version="2.0.0",
                observation_id=f"obs_{i}",
                source_run_id="run",
                video_id="vid",
                source_fingerprint_sha256="h",
                frame_index=i,
                source_time_s=t,
                timestamp_status="valid",
                segment_id="seg1",
                camera_id="cam1",
                bbox=[10.0, 10.0, 20.0, 20.0],
                footpoint_image=(15.0, 20.0),
                projected_court_xy=(2.0, 2.0),
                track_id="tr1",
                validity_status="valid", role="player",
            )
            for i, t in enumerate([0.0, 0.5, 3.0, 3.5])
        ]
        acc.process_observations_batch(obs_list)
        # Expected mass: 0.5s + 0.5s = 1.0 player-seconds (the 2.5s gap must be discarded!)
        self.assertAlmostEqual(acc.metadata.total_player_seconds, 1.0, places=4)
        self.assertAlmostEqual(acc.metadata.stale_gap_discarded_seconds, 2.5, places=4)

    def test_exclusion_interval_clipping(self) -> None:
        """Test that declared exclusions clip intervals correctly."""
        bounds = {"x_min": 0.0, "x_max": 10.0, "y_min": 0.0, "y_max": 10.0}
        exclusions = [ExclusionInterval(start_s=0.4, end_s=0.8, reason="excluded")]
        acc = HeatmapAccumulator(court_bounds=bounds, grid_shape=(10, 10), exclusions=exclusions)

        # Observation spanning t=0.0 to t=1.0. Excluded [0.4, 0.8] has duration 0.4s.
        # Effective duration should be 1.0 - 0.4 = 0.6s.
        res = acc.add_trajectory_interval(
            interval_key="inv1",
            court_xy=(5.0, 5.0),
            start_time_s=0.0,
            end_time_s=1.0,
        )
        self.assertTrue(res)
        self.assertAlmostEqual(acc.metadata.total_player_seconds, 0.6, places=4)
        self.assertAlmostEqual(acc.metadata.excluded_player_seconds, 0.4, places=4)

    def test_team_separation_and_mass_conservation(self) -> None:
        """Test team A, team B, and unknown mass partitioning and exact conservation."""
        bounds = {"x_min": 0.0, "x_max": 10.0, "y_min": 0.0, "y_max": 10.0}
        acc = HeatmapAccumulator(
            court_bounds=bounds,
            grid_shape=(10, 10),
            team_a_id="team_red",
            team_b_id="team_blue",
            max_gap_s=3.0,
        )

        acc.add_trajectory_interval("inv_a", (2.0, 2.0), 0.0, 1.5, team_id="team_red")
        acc.add_trajectory_interval("inv_b", (8.0, 8.0), 0.0, 2.5, team_id="team_blue")
        acc.add_trajectory_interval("inv_u", (5.0, 5.0), 0.0, 0.8, team_id=None)

        is_conserved, total_sum, comp_sum = acc.verify_mass_conservation()
        self.assertTrue(is_conserved)
        self.assertAlmostEqual(total_sum, 1.5 + 2.5 + 0.8, places=4)
        self.assertAlmostEqual(acc.metadata.team_a_player_seconds, 1.5, places=4)
        self.assertAlmostEqual(acc.metadata.team_b_player_seconds, 2.5, places=4)
        self.assertAlmostEqual(acc.metadata.unknown_team_player_seconds, 0.8, places=4)

    def test_idempotent_replay_and_recompute(self) -> None:
        """Test that replaying identical intervals does not double count and recompute resets cleanly."""
        bounds = {"x_min": 0.0, "x_max": 10.0, "y_min": 0.0, "y_max": 10.0}
        acc = HeatmapAccumulator(court_bounds=bounds, grid_shape=(10, 10))

        # Add an interval
        acc.add_trajectory_interval("inv1", (2.0, 2.0), 0.0, 1.0)
        self.assertAlmostEqual(acc.metadata.total_player_seconds, 1.0, places=4)

        # Replay same interval -> rejected by deduplication
        added = acc.add_trajectory_interval("inv1", (2.0, 2.0), 0.0, 1.0)
        self.assertFalse(added)
        self.assertAlmostEqual(acc.metadata.total_player_seconds, 1.0, places=4)

        # Test recompute with updated team mapping
        obs_list = [
            TrajectoryObservation(
                schema_version="2.0.0",
                observation_id="obs_0",
                source_run_id="run",
                video_id="vid",
                source_fingerprint_sha256="h",
                frame_index=0,
                source_time_s=0.0,
                timestamp_status="valid",
                segment_id="seg1",
                camera_id="cam1",
                bbox=[10.0, 10.0, 20.0, 20.0],
                footpoint_image=(15.0, 20.0),
                projected_court_xy=(2.0, 2.0),
                track_id="tr_alpha",
                team_id=None,
                validity_status="valid", role="player",
            ),
            TrajectoryObservation(
                schema_version="2.0.0",
                observation_id="obs_1",
                source_run_id="run",
                video_id="vid",
                source_fingerprint_sha256="h",
                frame_index=1,
                source_time_s=1.0,
                timestamp_status="valid",
                segment_id="seg1",
                camera_id="cam1",
                bbox=[10.0, 10.0, 20.0, 20.0],
                footpoint_image=(15.0, 20.0),
                projected_court_xy=(2.0, 2.0),
                track_id="tr_alpha",
                team_id=None,
                validity_status="valid", role="player",
            ),
        ]
        acc.recompute(obs_list, updated_team_mappings={"tr_alpha": "team_a"})
        self.assertAlmostEqual(acc.metadata.total_player_seconds, 1.0, places=4)
        self.assertAlmostEqual(acc.metadata.team_a_player_seconds, 1.0, places=4)
        self.assertAlmostEqual(acc.metadata.unknown_team_player_seconds, 0.0, places=4)


if __name__ == "__main__":
    unittest.main()
