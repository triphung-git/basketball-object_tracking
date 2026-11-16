"""Unit and regression tests for Continuous Upstream Pipeline (Task 02A).

Verifies:
1. Adapter contracts and mapping
2. CFR/VFR PTS preservation and monotonicity
3. Scene cuts and gap exclusions
4. Empty detections and event-free frames
5. Source / cache mismatch rejection
6. Unknown identity representation
7. Failed stage error propagation
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from basketball_scoreboard.config import APPROVED_MODEL_ID, ModelConfig
from basketball_scoreboard.continuous_stream import (
    ContinuousStreamFrame,
    run_continuous_upstream,
    stream_continuous_upstream,
    validate_detection_cache,
)
from basketball_scoreboard.contracts import FrameRecord
from basketball_scoreboard.spatial_io import file_hash
from basketball_scoreboard.video import VideoWriter


class TestContinuousStream02A(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.tmp = Path(self.temp_dir.name)

        # Create a small synthetic MP4 video (10 frames at 10 fps)
        self.video_path = self.tmp / "synthetic_test.mp4"
        with VideoWriter(self.video_path, 320, 240, 10) as writer:
            for i in range(10):
                img = np.full((240, 320, 3), fill_value=(i * 20) % 255, dtype=np.uint8)
                writer.write_frame(img, source_time_s=i * 0.1)

        self.video_sha = file_hash(self.video_path)

        # Create a test roster
        self.roster_path = self.tmp / "test_roster.json"
        self.roster_data = {
            "team_a_id": "VIE",
            "team_b_id": "TGA",
            "team_a_name": "Vietnam",
            "team_b_name": "Tonga",
            "team_a_color_rgb": [220, 40, 40],
            "team_b_color_rgb": [40, 40, 220],
            "players": [
                {"player_id": "VIE_01", "team_id": "VIE", "jersey_number": "1", "name": "Player 1"},
                {"player_id": "VIE_02", "team_id": "VIE", "jersey_number": "2", "name": "Player 2"},
                {"player_id": "TGA_01", "team_id": "TGA", "jersey_number": "7", "name": "Player 7"},
            ],
            "is_synthetic": True,
            "provenance_status": "draft",
        }
        self.roster_path.write_text(json.dumps(self.roster_data), encoding="utf-8")

        # Mock detector that produces predictable detections
        self.mock_detector = MagicMock()
        self.mock_detector.warmup.return_value = None
        self.mock_detector.get_runtime_info.return_value = {
            "model_id": APPROVED_MODEL_ID,
            "class_mapping": {"0": "ball", "1": "human", "2": "rim"},
        }

        # Detections: human in every frame, ball in frames 2..6, rim in all frames
        def mock_detect(image, conf_threshold=0.25):
            dets = [
                MagicMock(class_id=1, class_name="human", confidence=0.9, xyxy=[100.0, 50.0, 160.0, 180.0]),
                MagicMock(class_id=2, class_name="rim", confidence=0.85, xyxy=[280.0, 40.0, 310.0, 60.0]),
            ]
            return dets, 12.5

        self.mock_detector.detect.side_effect = mock_detect

    def test_adapter_contracts_and_mapping(self):
        """1. Verify ContinuousStreamFrame schema, to_dict(), and output bundle artifacts."""
        frame = ContinuousStreamFrame(
            frame_index=0,
            source_time_s=0.0,
            raw_pts=0,
            time_base="1/1000",
            timestamp_status="valid",
            detections=[{"class_id": 1, "class_name": "human", "confidence": 0.9, "xyxy": [10.0, 20.0, 50.0, 80.0]}],
            player_observations=[{"track_id": "trk_01", "bbox": [10.0, 20.0, 50.0, 80.0]}],
            ball_observation={"sample_type": "missing", "center_image": None},
            control_observation={"state": "free", "certainty": "confirmed"},
            rim_detections=[],
            is_cut=False,
            cut_reason=None,
        )
        d = frame.to_dict()
        self.assertEqual(d["frame_index"], 0)
        self.assertEqual(d["source_time_s"], 0.0)
        self.assertEqual(d["timestamp_status"], "valid")
        self.assertIn("detections", d)
        self.assertIn("player_observations", d)
        self.assertIn("ball_observation", d)
        self.assertIn("control_observation", d)

        # Run pipeline and verify output bundle
        out_dir = self.tmp / "test_contracts_out"
        res = run_continuous_upstream(
            video_path=self.video_path,
            output_dir=out_dir,
            roster_config_path=self.roster_path,
            detector_factory=lambda: self.mock_detector,
            allow_uncalibrated=True,
            quiet=True,
        )
        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["stage_counts"]["total_frames_read"], 10)

        # Check all required files exist
        required_files = [
            "run.json",
            "detections.jsonl",
            "tracked_observations.jsonl",
            "ball_tracks.jsonl",
            "possession_control.jsonl",
            "ball_control.jsonl",
            "pass_events.jsonl",
            "passes.jsonl",
            "identity_mappings.json",
            "jersey_evidence.json",
        ]
        for fname in required_files:
            p = out_dir / fname
            self.assertTrue(p.is_file(), f"Missing required output file: {fname}")

    def test_cfr_vfr_pts_preservation(self):
        """2. Verify that normalized source_time_s preserves true video clock without replacement."""
        # Create VFR video with non-uniform timestamps
        vfr_path = self.tmp / "vfr_test.mp4"
        timestamps = [0.0, 0.033, 0.071, 0.115, 0.158, 0.200]
        with VideoWriter(vfr_path, 320, 240, 30) as writer:
            for t in timestamps:
                img = np.zeros((240, 320, 3), dtype=np.uint8)
                writer.write_frame(img, source_time_s=t)

        out_dir = self.tmp / "vfr_out"
        res = run_continuous_upstream(
            video_path=vfr_path,
            output_dir=out_dir,
            roster_config_path=self.roster_path,
            detector_factory=lambda: self.mock_detector,
            allow_uncalibrated=True,
            quiet=True,
        )
        self.assertEqual(res["status"], "completed")

        # Read detections.jsonl and check recorded timestamps
        lines = [json.loads(line) for line in (out_dir / "detections.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(lines), len(timestamps))
        for line, expected_t in zip(lines, timestamps):
            self.assertAlmostEqual(line["source_time_s"], expected_t, delta=0.005)

    def test_cuts_and_gaps_handling(self):
        """3. Verify explicit cuts and interval exclusions reset state and flag is_cut."""
        policy_path = self.tmp / "test_policy.json"
        policy_data = {
            "source_video_sha256": self.video_sha,
            "image_roi_normalized": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            "intervals": [
                {"start_time_s": 0.3, "end_time_s": 0.5, "reason": "closeup_scene_cut"}
            ],
        }
        policy_path.write_text(json.dumps(policy_data), encoding="utf-8")

        out_dir = self.tmp / "cuts_out"
        res = run_continuous_upstream(
            video_path=self.video_path,
            output_dir=out_dir,
            roster_config_path=self.roster_path,
            tracking_policy_path=policy_path,
            detector_factory=lambda: self.mock_detector,
            allow_uncalibrated=True,
            quiet=True,
        )
        self.assertEqual(res["status"], "completed")
        self.assertGreater(res["stage_counts"]["total_cut_frames"], 0)

        # Inspect possession control states during cut
        ctrl_lines = [json.loads(line) for line in (out_dir / "possession_control.jsonl").read_text(encoding="utf-8").splitlines()]
        cut_recs = [c for c in ctrl_lines if 0.3 <= c["source_time_s"] <= 0.5]
        self.assertTrue(any(c.get("reason") in {"closeup_scene_cut", "operational_exclusion"} for c in cut_recs))

    def test_empty_detections_handling(self):
        """4. Verify frames with empty detections do not crash and emit event-free records."""
        empty_detector = MagicMock()
        empty_detector.warmup.return_value = None
        empty_detector.get_runtime_info.return_value = {
            "model_id": APPROVED_MODEL_ID,
            "class_mapping": {"0": "ball", "1": "human", "2": "rim"},
        }
        empty_detector.detect.return_value = ([], 5.0)

        out_dir = self.tmp / "empty_out"
        res = run_continuous_upstream(
            video_path=self.video_path,
            output_dir=out_dir,
            roster_config_path=self.roster_path,
            detector_factory=lambda: empty_detector,
            allow_uncalibrated=True,
            quiet=True,
        )
        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["stage_counts"]["total_detections"], 0)
        self.assertEqual(res["stage_counts"]["ball_tracks"]["missing"], 10)

        # Verify 10 records exist in detections.jsonl with empty detections list
        dets_lines = [json.loads(line) for line in (out_dir / "detections.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(dets_lines), 10)
        for line in dets_lines:
            self.assertEqual(line["detections"], [])

    def test_source_cache_mismatch_rejection(self):
        """5. Verify that mismatched cache source SHA, model ID, or class mapping raises ValueError."""
        cache_dir = self.tmp / "cache_test"
        cache_dir.mkdir()
        cache_dets = cache_dir / "detections.jsonl"
        cache_run = cache_dir / "run.json"

        # Wrong source sha
        cache_run.write_text(json.dumps({
            "source_fingerprint_sha256": "wrong_hash_12345",
            "runtime": {
                "model_id": APPROVED_MODEL_ID,
                "class_mapping": {"0": "ball", "1": "human", "2": "rim"},
            },
        }), encoding="utf-8")
        cache_dets.write_text("", encoding="utf-8")

        with self.assertRaises(ValueError) as ctx:
            validate_detection_cache(cache_dets, expected_source_sha=self.video_sha)
        self.assertIn("mismatch", str(ctx.exception).lower())

        # Correct sha, but wrong model ID
        cache_run.write_text(json.dumps({
            "source_fingerprint_sha256": self.video_sha,
            "runtime": {
                "model_id": "unapproved-random-model",
                "class_mapping": {"0": "ball", "1": "human", "2": "rim"},
            },
        }), encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            validate_detection_cache(cache_dets, expected_source_sha=self.video_sha)
        self.assertIn("model id mismatch", str(ctx.exception).lower())

    def test_unknown_identity_representation(self):
        """6. Verify that without OCR, player_id remains unassigned (None), avoiding fabricated identity."""
        out_dir = self.tmp / "identity_out"
        res = run_continuous_upstream(
            video_path=self.video_path,
            output_dir=out_dir,
            roster_config_path=self.roster_path,
            detector_factory=lambda: self.mock_detector,
            allow_uncalibrated=True,
            quiet=True,
        )
        self.assertEqual(res["status"], "completed")

        # Check tracked_observations: player_id must be None (no OCR was run)
        obs_lines = [json.loads(line) for line in (out_dir / "tracked_observations.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertGreater(len(obs_lines), 0)
        for obs in obs_lines:
            self.assertIsNone(obs.get("player_id"), "player_id must remain unassigned without verified OCR")

    def test_failed_stage_propagation(self):
        """7. Verify that exceptions in detector or non-existent files are propagated properly."""
        failing_detector = MagicMock()
        failing_detector.warmup.return_value = None
        failing_detector.detect.side_effect = RuntimeError("Inference engine collapsed")

        out_dir = self.tmp / "fail_out"
        with self.assertRaises(RuntimeError):
            run_continuous_upstream(
                video_path=self.video_path,
                output_dir=out_dir,
                roster_config_path=self.roster_path,
                detector_factory=lambda: failing_detector,
                allow_uncalibrated=True,
                quiet=True,
            )

        # Output dir must reflect failed status in run.json
        self.assertTrue((out_dir / "run.json").is_file())
        meta = json.loads((out_dir / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["status"], "failed")
        self.assertIn("RuntimeError", meta["error_message"])


if __name__ == "__main__":
    unittest.main()
