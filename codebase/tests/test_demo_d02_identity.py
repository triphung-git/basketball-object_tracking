"""Target acceptance tests for D02: Continuous OCR, Team, and Identity Integration."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

import numpy as np

from basketball_scoreboard.config import APPROVED_MODEL_ID
from basketball_scoreboard.continuous_orchestration import run_continuous_orchestration
from basketball_scoreboard.continuous_stream import (
    ContinuousStreamFrame,
    run_continuous_upstream,
    stream_continuous_upstream,
)
from basketball_scoreboard.identity import (
    IdentityResolver,
    JerseyEvidenceRecord,
    MockOCRProvider,
    RosterConfig,
    RosterPlayer,
    TeamColorClassifier,
    evaluate_crop_quality,
)
from basketball_scoreboard.spatial_io import file_hash
from basketball_scoreboard.video import VideoWriter


class TestDemoD02IdentityIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.tmp = Path(self.temp_dir.name)

        # Create a synthetic MP4 video (15 frames at 10 fps)
        self.video_path = self.tmp / "d02_test_vid.mp4"
        with VideoWriter(self.video_path, 320, 240, 10) as writer:
            for i in range(15):
                # Put a distinct red box in the player torso area
                img = np.full((240, 320, 3), 50, dtype=np.uint8)
                img[50:150, 100:160] = [30, 30, 220]  # Red in BGR
                writer.write_frame(img, source_time_s=i * 0.1)

        self.video_sha = file_hash(self.video_path)

        # Create roster
        self.roster_path = self.tmp / "roster_d02.json"
        self.roster_data = {
            "team_a_id": "VIE",
            "team_b_id": "TGA",
            "team_a_name": "Vietnam",
            "team_b_name": "Tonga",
            "team_a_color_rgb": [220, 30, 30],
            "team_b_color_rgb": [30, 30, 220],
            "players": [
                {"player_id": "VIE_18", "team_id": "VIE", "jersey_number": "18", "name": "Nguyen 18"},
                {"player_id": "VIE_23", "team_id": "VIE", "jersey_number": "23", "name": "Tran 23"},
                {"player_id": "TGA_07", "team_id": "TGA", "jersey_number": "7", "name": "Tonga 7"},
            ],
            "is_synthetic": True,
            "provenance_status": "draft",
        }
        self.roster_path.write_text(json.dumps(self.roster_data), encoding="utf-8")

        # Mock detector with human detection
        self.mock_detector = MagicMock()
        self.mock_detector.warmup.return_value = None
        self.mock_detector.get_runtime_info.return_value = {
            "model_id": APPROVED_MODEL_ID,
            "class_mapping": {"0": "ball", "1": "human", "2": "rim"},
        }

        def mock_detect(image, conf_threshold=0.25):
            dets = [
                MagicMock(class_id=1, class_name="human", confidence=0.92, xyxy=[100.0, 50.0, 160.0, 180.0]),
            ]
            return dets, 10.0

        self.mock_detector.detect.side_effect = mock_detect

    def test_continuous_stream_calls_ocr_and_resolves_player(self):
        """Verify that stream_continuous_upstream calls OCR provider and resolves player identity."""
        mock_ocr = MockOCRProvider(default_number="18", default_confidence=0.95)

        out_dir = self.tmp / "ocr_upstream_out"
        res = run_continuous_upstream(
            video_path=self.video_path,
            output_dir=out_dir,
            roster_config_path=self.roster_path,
            detector_factory=lambda: self.mock_detector,
            ocr_provider=mock_ocr,
            enable_ocr=True,
            ocr_interval_frames=1,
            allow_uncalibrated=True,
            quiet=True,
        )

        self.assertEqual(res["status"], "completed")

        # Verify jersey_evidence.json is NOT empty
        jersey_ev_path = out_dir / "jersey_evidence.json"
        self.assertTrue(jersey_ev_path.is_file())
        jersey_ev = json.loads(jersey_ev_path.read_text(encoding="utf-8"))
        self.assertGreater(len(jersey_ev), 0, "jersey_evidence.json must contain real evidence records, not []")
        self.assertEqual(jersey_ev[0]["detected_number"], "18")

        # Verify identity_mappings.json contains resolved player VIE_18
        mappings_path = out_dir / "identity_mappings.json"
        self.assertTrue(mappings_path.is_file())
        mappings = json.loads(mappings_path.read_text(encoding="utf-8"))
        self.assertGreater(len(mappings), 0)
        resolved_players = [m["player_id"] for m in mappings if m.get("player_id")]
        self.assertIn("VIE_18", resolved_players, "Player VIE_18 should be resolved via OCR consensus")

    def test_ocr_cache_path_injection(self):
        """Verify that passing ocr_cache_path injects pre-computed jersey evidence without live OCR."""
        cache_file = self.tmp / "sample_ocr_cache.json"
        sample_cache = [
            {
                "evidence_id": "ev_cached_01",
                "track_id": "trk_0001",
                "frame_index": 0,
                "source_time_s": 0.0,
                "detected_number": "23",
                "confidence": 0.98,
                "ocr_engine": "easyocr_cached",
                "is_valid": True,
            },
            {
                "evidence_id": "ev_cached_02",
                "track_id": "trk_0001",
                "frame_index": 1,
                "source_time_s": 0.1,
                "detected_number": "23",
                "confidence": 0.98,
                "ocr_engine": "easyocr_cached",
                "is_valid": True,
            },
            {
                "evidence_id": "ev_cached_03",
                "track_id": "trk_0001",
                "frame_index": 2,
                "source_time_s": 0.2,
                "detected_number": "23",
                "confidence": 0.98,
                "ocr_engine": "easyocr_cached",
                "is_valid": True,
            },
        ]
        cache_file.write_text(json.dumps(sample_cache), encoding="utf-8")

        out_dir = self.tmp / "cached_ocr_out"
        res = run_continuous_upstream(
            video_path=self.video_path,
            output_dir=out_dir,
            roster_config_path=self.roster_path,
            detector_factory=lambda: self.mock_detector,
            ocr_cache_path=cache_file,
            allow_uncalibrated=True,
            quiet=True,
        )

        self.assertEqual(res["status"], "completed")
        jersey_ev = json.loads((out_dir / "jersey_evidence.json").read_text(encoding="utf-8"))
        self.assertEqual(len(jersey_ev), 3)
        self.assertEqual(jersey_ev[0]["detected_number"], "23")

    def test_crop_quality_gate(self):
        """Verify that evaluate_crop_quality correctly filters out unsuitable crops."""
        # None
        valid, reason = evaluate_crop_quality(None)
        self.assertFalse(valid)
        self.assertIn("Empty", reason)

        # Flat / uniform crop
        flat = np.full((50, 40, 3), 100, dtype=np.uint8)
        valid, reason = evaluate_crop_quality(flat, min_std_dev=5.0)
        self.assertFalse(valid)
        self.assertIn("texture", reason)

        # Good contrast crop
        good = np.zeros((60, 40, 3), dtype=np.uint8)
        good[:30, :] = 255
        valid, reason = evaluate_crop_quality(good)
        self.assertTrue(valid)
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()
