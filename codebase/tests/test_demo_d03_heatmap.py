"""Unit and integration tests for Task D03: Court Calibration & Heatmap Accumulation."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import numpy as np
import pytest

from basketball_scoreboard.court import CourtConfig, CourtModel, TrajectoryObservation
from basketball_scoreboard.heatmap import (
    ExclusionInterval,
    HeatmapAccumulator,
    compute_court_region_stats,
)
from basketball_scoreboard.continuous_orchestration import run_continuous_orchestration
from basketball_scoreboard.identity import RosterConfig


def make_test_court_config() -> CourtConfig:
    return CourtConfig(
        schema_version="2.0.0",
        camera_id="cam_main",
        segment_id="session_vietnam_tonga_dev",
        original_image_wh=(1920, 1080),
        status="validated",
        is_synthetic=False,
        court_coordinate_system={
            "origin": "basket_center_floor",
            "axes": {"x_positive": "right", "y_positive": "towards_half_court"},
            "units": "meters",
            "court_bounds": {"x_min": -7.5, "x_max": 7.5, "y_min": 0.0, "y_max": 11.0},
            "scale_factor": 1.0,
            "scale_status": "verified_meters",
        },
        point_correspondences=[
            {"point_id": "P1", "name": "Key baseline L", "image_xy": [510.0, 617.0], "court_xy": [-2.45, 0.0], "is_coplanar": True, "usage": "fit"},
            {"point_id": "P2", "name": "Key baseline R", "image_xy": [916.0, 542.0], "court_xy": [2.45, 0.0], "is_coplanar": True, "usage": "fit"},
            {"point_id": "P3", "name": "Key FT L", "image_xy": [862.0, 809.0], "court_xy": [-2.45, 5.8], "is_coplanar": True, "usage": "fit"},
            {"point_id": "P4", "name": "Key FT R", "image_xy": [1318.0, 667.0], "court_xy": [2.45, 5.8], "is_coplanar": True, "usage": "fit"},
        ],
        court_roi_image=[
            (510.0, 617.0),
            (916.0, 542.0),
            (1165.0, 496.0),
            (1542.0, 658.0),
            (1390.0, 836.0),
            (60.0, 842.0),
        ],
        source_video_hash="8fd370b0668860a5c70d56bf256c76e3783bc1fe6598b529944ad00ca0616b45",
        thresholds={"max_reprojection_error_px": 25.0},
        provenance={"review_status": "approved", "reviewed_by": "user_triphung"},
    )


def test_region_stats_conservation():
    bounds = {"x_min": -7.5, "x_max": 7.5, "y_min": 0.0, "y_max": 11.0}
    acc = HeatmapAccumulator(bounds, grid_shape=(50, 50), team_a_id="VIE", team_b_id="TGA")

    # Add points in paint: (0.0, 3.0)
    acc.add_trajectory_interval("int_paint_1", (0.0, 3.0), 0.0, 1.0, team_id="VIE", player_id="p1")
    # Add points in mid_range: (4.0, 4.0) -> dist = hypot(4.0, 4.0 - 1.575) = hypot(4, 2.425) = 4.67m <= 6.75m
    acc.add_trajectory_interval("int_mid_1", (4.0, 4.0), 1.0, 2.0, team_id="TGA", player_id="p2")
    # Add points in three_point: (6.0, 8.0) -> dist = hypot(6.0, 6.425) = 8.79m > 6.75m
    acc.add_trajectory_interval("int_3pt_1", (6.0, 8.0), 2.0, 3.0, team_id=None, player_id=None)

    stats = compute_court_region_stats(acc, basket_xy=(0.0, 1.575))

    assert abs(stats["paint"]["total_seconds"] - 1.0) < 1e-5
    assert abs(stats["paint"]["team_a_seconds"] - 1.0) < 1e-5
    assert abs(stats["mid_range"]["total_seconds"] - 1.0) < 1e-5
    assert abs(stats["mid_range"]["team_b_seconds"] - 1.0) < 1e-5
    assert abs(stats["three_point"]["total_seconds"] - 1.0) < 1e-5
    assert abs(stats["three_point"]["unknown_seconds"] - 1.0) < 1e-5

    total_region_seconds = sum(s["total_seconds"] for s in stats.values())
    assert abs(total_region_seconds - acc.metadata.total_player_seconds) < 1e-5


def test_process_observations_batch_dict_compatibility():
    bounds = {"x_min": -7.5, "x_max": 7.5, "y_min": 0.0, "y_max": 11.0}
    acc = HeatmapAccumulator(bounds, grid_shape=(50, 50), team_a_id="VIE", team_b_id="TGA")

    obs_dicts = [
        {
            "schema_version": "2.0.0",
            "observation_id": "obs_000000_1",
            "source_run_id": "run1",
            "video_id": "vid1",
            "source_fingerprint_sha256": "sha1",
            "frame_index": 0,
            "source_time_s": 0.0,
            "timestamp_status": "valid",
            "segment_id": "default",
            "camera_id": "cam_main",
            "bbox": [500.0, 600.0, 540.0, 680.0],
            "footpoint_image": [520.0, 680.0],
            "position_method": "bbox_bottom_center",
            "projected_court_xy": [0.0, 4.0],
            "court_units": "meters",
            "validity_status": "valid",
            "track_id": "1",
            "role": "player",
            "sample_type": "observed",
            "confidence": 0.95,
        },
        {
            "schema_version": "2.0.0",
            "observation_id": "obs_000001_1",
            "source_run_id": "run1",
            "video_id": "vid1",
            "source_fingerprint_sha256": "sha1",
            "frame_index": 1,
            "source_time_s": 0.033333,
            "timestamp_status": "valid",
            "segment_id": "default",
            "camera_id": "cam_main",
            "bbox": [502.0, 600.0, 542.0, 680.0],
            "footpoint_image": [522.0, 680.0],
            "position_method": "bbox_bottom_center",
            "projected_court_xy": [0.05, 4.02],
            "court_units": "meters",
            "validity_status": "valid",
            "track_id": "1",
            "role": "player",
            "sample_type": "observed",
            "confidence": 0.95,
        },
    ]

    acc.process_observations_batch(obs_dicts)
    assert acc.metadata.total_player_seconds > 0.0
    conserved, total, comp = acc.verify_mass_conservation()
    assert conserved
    assert abs(total - 0.033333) < 1e-4


def test_continuous_orchestration_calibrated_court_artifacts(tmp_path):
    root = Path(__file__).resolve().parents[1]
    court_path = root / "configs/courts/vt_development_court.json"
    roster_path = root / "configs/rosters/vietnam_tonga.json"
    video_path = root / "assets_test/vietnam-tonga.mp4"
    cache_path = root / "outputs/quality-revision-20261116/full-match-01/video-run/detections.jsonl"
    out_dir = tmp_path / "calibrated_run"

    res = run_continuous_orchestration(
        video_path=video_path,
        output_dir=out_dir,
        roster_config_path=roster_path,
        court_config_path=court_path,
        detections_cache_path=cache_path,
        enable_ocr=False,
        allow_uncalibrated=True,
        start_time_s=300.0,
        end_time_s=302.0,
    )

    assert res["status"] == "completed"
    assert res["geometry"]["status"] == "calibrated"

    # Verify trajectories artifact
    assert (out_dir / "trajectories.jsonl").is_file()
    traj_lines = (out_dir / "trajectories.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(traj_lines) > 0

    # Verify heatmap summary
    assert (out_dir / "heatmap_summary.json").is_file()
    summary = json.loads((out_dir / "heatmap_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "generated"
    assert summary["acceptance_scope"] == "technical"
    assert summary["total_player_seconds"] > 0.0
    assert summary["mass_conservation"]["is_conserved"] is True
    assert "region_stats" in summary
    assert "paint" in summary["region_stats"]

    # Verify heatmap png
    assert (out_dir / "heatmap.png").is_file()
    assert (out_dir / "heatmap.png").stat().st_size > 1000
    assert (out_dir / "heatmap_raw_grid.json").is_file()
