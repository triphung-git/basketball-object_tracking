"""Unit and contract tests for Task06 player tracking, team classification, and identity resolution."""
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

import numpy as np

CODEBASE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = CODEBASE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from basketball_scoreboard.identity import (
    IdentityResolver,
    JerseyEvidenceRecord,
    LocalEasyOCRProvider,
    MockOCRProvider,
    ModelWeightsUnavailableError,
    OCRProvider,
    RosterConfig,
    RosterPlayer,
    TeamColorClassifier,
    enrich_observations_with_identity,
    evaluate_crop_quality,
)
from basketball_scoreboard.players import (
    PlayerTracker,
    compute_center_distance,
    compute_iou,
)


class Task06PlayerTrackingTests(unittest.TestCase):
    """Tests for kinematic tracking, association, occlusion, and track lifecycle."""

    def test_compute_iou_and_distance(self) -> None:
        """Test IoU and center distance calculations."""
        b1 = [0.0, 0.0, 10.0, 10.0]
        b2 = [5.0, 0.0, 15.0, 10.0]
        # Intersection: [5, 0, 10, 10] -> w=5, h=10 -> area=50
        # Union: 100 + 100 - 50 = 150 -> IoU = 50/150 = 1/3
        iou = compute_iou(b1, b2)
        self.assertAlmostEqual(iou, 1.0 / 3.0, places=4)

        dist = compute_center_distance(b1, b2)
        # Center 1: (5, 5), Center 2: (10, 5) -> dist = 5.0
        self.assertAlmostEqual(dist, 5.0, places=4)

    def test_straightforward_track_association(self) -> None:
        """Test that a moving entity across consecutive frames maintains a single persistent track ID."""
        tracker = PlayerTracker(video_id="vid_test", min_hits_to_activate=2)

        # Frame 0: detection at [100, 100, 150, 200]
        obs0 = tracker.update_frame(
            frame_index=0,
            source_time_s=0.0,
            timestamp_status="valid",
            detections=[{"xyxy": [100.0, 100.0, 150.0, 200.0], "class_name": "human", "confidence": 0.9}],
        )
        self.assertEqual(len(obs0), 1)
        tid = obs0[0].track_id
        self.assertIsNotNone(tid)

        # Frame 1: entity moved slightly to [105, 102, 155, 202]
        obs1 = tracker.update_frame(
            frame_index=1,
            source_time_s=0.033,
            timestamp_status="valid",
            detections=[{"xyxy": [105.0, 102.0, 155.0, 202.0], "class_name": "human", "confidence": 0.92}],
        )
        self.assertEqual(len(obs1), 1)
        self.assertEqual(obs1[0].track_id, tid, "Track ID must remain persistent across frames")
        self.assertEqual(obs1[0].sample_type, "observed")

    def test_crossing_and_bbox_order_independence(self) -> None:
        """
        Test that two entities crossing maintain their identities regardless of
        the order in which detections are returned in the detection list.
        """
        tracker = PlayerTracker(video_id="vid_test", min_hits_to_activate=1)

        # Frame 0: Person A on left (x=100), Person B on right (x=400)
        tracker.update_frame(
            frame_index=0,
            source_time_s=0.0,
            timestamp_status="valid",
            detections=[
                {"xyxy": [100.0, 100.0, 140.0, 200.0], "class_name": "human"},
                {"xyxy": [400.0, 100.0, 440.0, 200.0], "class_name": "human"},
            ],
        )
        tids = list(tracker.tracks.keys())
        self.assertEqual(len(tids), 2)
        tid_left, tid_right = tids[0], tids[1]

        # Frame 1: Detections returned in REVERSED order in input list
        obs1 = tracker.update_frame(
            frame_index=1,
            source_time_s=0.1,
            timestamp_status="valid",
            detections=[
                {"xyxy": [402.0, 101.0, 442.0, 201.0], "class_name": "human"},  # Right person first!
                {"xyxy": [102.0, 101.0, 142.0, 201.0], "class_name": "human"},  # Left person second!
            ],
        )
        matched = {o.track_id: o.bbox for o in obs1}
        # Verify left person still has tid_left
        self.assertAlmostEqual(matched[tid_left][0], 102.0, places=1)
        # Verify right person still has tid_right
        self.assertAlmostEqual(matched[tid_right][0], 402.0, places=1)

    def test_occlusion_and_predicted_status(self) -> None:
        """Test that when a detection is missed during occlusion, it produces a predicted sample."""
        tracker = PlayerTracker(video_id="vid_test", min_hits_to_activate=1, max_age_s=0.5)

        # Frame 0: visible
        tracker.update_frame(
            frame_index=0,
            source_time_s=0.0,
            timestamp_status="valid",
            detections=[{"xyxy": [100.0, 100.0, 150.0, 200.0], "class_name": "human"}],
        )

        # Frame 1: missed detection (occluded by post/defender)
        obs1 = tracker.update_frame(
            frame_index=1,
            source_time_s=0.05,
            timestamp_status="valid",
            detections=[],  # Empty!
        )
        self.assertEqual(len(obs1), 1)
        self.assertEqual(obs1[0].sample_type, "predicted", "Missed sample must be explicitly marked predicted")
        self.assertEqual(obs1[0].validity_status, "predicted_occluded")

    def test_stale_timeout_retires_track(self) -> None:
        """Test that a track lost longer than max_age_s is retired and removed from active tracking."""
        tracker = PlayerTracker(video_id="vid_test", min_hits_to_activate=1, max_age_s=0.5)

        tracker.update_frame(
            frame_index=0,
            source_time_s=0.0,
            timestamp_status="valid",
            detections=[{"xyxy": [100.0, 100.0, 150.0, 200.0], "class_name": "human"}],
        )
        tid = list(tracker.tracks.keys())[0]

        # Jump forward past max_age_s (0.0 to 1.0s > 0.5s)
        obs_late = tracker.update_frame(
            frame_index=10,
            source_time_s=1.0,
            timestamp_status="valid",
            detections=[],
        )
        self.assertNotIn(tid, tracker.tracks, "Stale track must be retired")
        self.assertEqual(len(tracker.retired_tracks), 1)


class Task06IdentityResolverTests(unittest.TestCase):
    """Tests for roster validation, duplicate jersey handling, temporal voting, and conflict detection."""

    def setUp(self) -> None:
        # Create a realistic FIBA 3x3 dual-team roster
        self.roster = RosterConfig(
            team_a_id="team_red",
            team_b_id="team_blue",
            team_a_name="Red Team",
            team_b_name="Blue Team",
            team_a_color_rgb=(200, 30, 30),
            team_b_color_rgb=(30, 60, 200),
            players=[
                RosterPlayer("p_red_07", "team_red", "7", "Alice Red"),
                RosterPlayer("p_red_23", "team_red", "23", "Bob Red"),
                RosterPlayer("p_blue_07", "team_blue", "7", "Charlie Blue"),  # Same jersey #7 on opposing team!
                RosterPlayer("p_blue_15", "team_blue", "15", "David Blue"),
            ],
        )

    def test_roster_permits_same_jersey_number_across_opposing_teams(self) -> None:
        """Critical FIBA rule: opposing teams CAN share jersey numbers; lookup must be team-qualified."""
        player_red_7 = self.roster.get_player("team_red", "7")
        self.assertIsNotNone(player_red_7)
        self.assertEqual(player_red_7.player_id, "p_red_07")

        player_blue_7 = self.roster.get_player("team_blue", "7")
        self.assertIsNotNone(player_blue_7)
        self.assertEqual(player_blue_7.player_id, "p_blue_07")

    def test_roster_rejects_duplicate_jersey_within_same_team(self) -> None:
        """Within the SAME team, duplicate jersey numbers must be rejected."""
        with self.assertRaises(ValueError) as ctx:
            RosterConfig(
                team_a_id="team_red",
                team_b_id="team_blue",
                team_a_name="Red",
                team_b_name="Blue",
                team_a_color_rgb=(200, 0, 0),
                team_b_color_rgb=(0, 0, 200),
                players=[
                    RosterPlayer("p1", "team_red", "10", "Player 1"),
                    RosterPlayer("p2", "team_red", "10", "Player 2"),  # Duplicate #10 in Red team!
                ],
            )
        self.assertIn("Duplicate jersey number in Team team_red", str(ctx.exception))

    def test_team_color_classification_and_ambiguity(self) -> None:
        """Test color distance classification and ambiguous zone handling."""
        clf = TeamColorClassifier(
            team_a_id="team_red",
            team_b_id="team_blue",
            team_a_color_rgb=(220, 20, 20),
            team_b_color_rgb=(20, 40, 220),
            ambiguity_margin=40.0,
        )

        # Clear red jersey
        team, conf, _ = clf.classify_rgb((215.0, 25.0, 22.0))
        self.assertEqual(team, "team_red")
        self.assertGreater(conf, 0.8)

        # Clear blue jersey
        team, conf, _ = clf.classify_rgb((25.0, 35.0, 210.0))
        self.assertEqual(team, "team_blue")
        self.assertGreater(conf, 0.8)

        # Gray/referee/ambiguous color: equidistant
        team, conf, reason = clf.classify_rgb((120.0, 120.0, 120.0))
        self.assertIsNone(team, "Equidistant/ambiguous color must return team None (unknown)")
        self.assertIn("Ambiguous jersey color", reason)

    def test_ocr_hysteresis_rejects_single_frame_noise(self) -> None:
        """
        Test that a single-frame misread by OCR does not flip or corrupt player identity.
        Requires confirmation_hits_threshold votes to confirm.
        """
        resolver = IdentityResolver(self.roster, confirmation_hits_threshold=3)

        # Track 1 confirmed as team_red
        resolver.add_team_observation("trk_01", "team_red", 1.0)
        resolver.add_team_observation("trk_01", "team_red", 1.0)

        # 1 reading of jersey #23 (score=1.0 < 3.0 threshold) -> should remain unresolved!
        resolver.add_jersey_evidence(JerseyEvidenceRecord("ev1", "trk_01", 1, 0.1, "23", 1.0))
        mapping1 = resolver.update_track_mapping("trk_01", 0.1)
        self.assertEqual(mapping1.team_id, "team_red")
        self.assertIsNone(mapping1.player_id, "Single reading must not immediately confirm player identity")

        # 1 noisy frame reads "88" (glare / motion blur)
        resolver.add_jersey_evidence(JerseyEvidenceRecord("ev2", "trk_01", 2, 0.15, "88", 0.8))
        mapping2 = resolver.update_track_mapping("trk_01", 0.15)
        self.assertIsNone(mapping2.player_id)

        # Two more solid readings of #23 (total score: 1.0 + 1.0 + 1.0 = 3.0 >= 3.0 threshold)
        resolver.add_jersey_evidence(JerseyEvidenceRecord("ev3", "trk_01", 3, 0.2, "23", 1.0))
        resolver.add_jersey_evidence(JerseyEvidenceRecord("ev4", "trk_01", 4, 0.25, "23", 1.0))
        mapping3 = resolver.update_track_mapping("trk_01", 0.25)
        self.assertEqual(mapping3.player_id, "p_red_23", "Player #23 must now be resolved after consensus")

    def test_duplicate_active_player_conflict_detection(self) -> None:
        """
        Test that if two distinct active tracks are both claimed by the same player,
        conflict_status 'duplicate_active_player' is flagged.
        """
        resolver = IdentityResolver(self.roster, confirmation_hits_threshold=1)

        # Track 1 is red #7
        resolver.add_team_observation("trk_01", "team_red", 1.0)
        resolver.add_jersey_evidence(JerseyEvidenceRecord("ev1", "trk_01", 1, 0.0, "7", 1.0))
        resolver.update_track_mapping("trk_01", 0.0, active_track_ids={"trk_01"})

        # Track 2 is ALSO red #7 simultaneously
        resolver.add_team_observation("trk_02", "team_red", 1.0)
        resolver.add_jersey_evidence(JerseyEvidenceRecord("ev2", "trk_02", 1, 0.0, "7", 1.0))
        mapping2 = resolver.update_track_mapping("trk_02", 0.0, active_track_ids={"trk_01", "trk_02"})

        self.assertEqual(mapping2.conflict_status, "duplicate_active_player")


class Task06OCRProviderTests(unittest.TestCase):
    """Tests for OCR provider contract, crop quality validation, and offline security."""

    def test_crop_quality_evaluation(self) -> None:
        """Test crop dimension and contrast rejection rules."""
        import numpy as np
        # Null or empty crop
        valid, reason = evaluate_crop_quality(None)
        self.assertFalse(valid)
        self.assertIn("Empty", reason)

        # Too small (e.g. 10x10 < 16x24)
        small_crop = np.zeros((10, 10, 3), dtype=np.uint8)
        valid, reason = evaluate_crop_quality(small_crop, min_width=16, min_height=24)
        self.assertFalse(valid)
        self.assertIn("below minimum threshold", reason)

        # Adequate size but flat/uniform (zero standard deviation)
        flat_crop = np.full((30, 20, 3), 128, dtype=np.uint8)
        valid, reason = evaluate_crop_quality(flat_crop, min_std_dev=8.0)
        self.assertFalse(valid)
        self.assertIn("Insufficient crop texture", reason)

        # Adequate size and contrast
        good_crop = np.random.randint(0, 255, size=(40, 30, 3), dtype=np.uint8)
        valid, reason = evaluate_crop_quality(good_crop)
        self.assertTrue(valid)
        self.assertIsNone(reason)

    def test_local_easyocr_rejects_missing_weights_without_download(self) -> None:
        """
        Verify that LocalEasyOCRProvider proactively checks for craft_mlt_25k.pth
        and english_g2.pth on disk, refusing automated download and raising
        ModelWeightsUnavailableError.
        """
        with tempfile.TemporaryDirectory() as empty_dir:
            with self.assertRaises(ModelWeightsUnavailableError) as ctx:
                LocalEasyOCRProvider(model_storage_directory=empty_dir)
            self.assertIn("Local EasyOCR weights", str(ctx.exception))
            self.assertIn("Silent automated download is forbidden", str(ctx.exception))

    def test_local_easyocr_initializes_with_cached_weights(self) -> None:
        """
        Verify that LocalEasyOCRProvider loads cached weights from disk without downloading,
        and accurately recognizes digits from a jersey crop.
        """
        import cv2
        provider = LocalEasyOCRProvider()
        self.assertEqual(provider.name, "easyocr_local")
        self.assertTrue(provider.is_production)

        # Create a synthetic crop with white number '23' on dark background
        img = np.zeros((60, 60, 3), dtype=np.uint8)
        cv2.putText(img, "23", (10, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)

        readings = provider.read_jersey(img, track_id="trk_01", frame_index=1, source_time_s=0.1)
        self.assertGreaterEqual(len(readings), 1)
        self.assertEqual(readings[0].detected_number, "23")
        self.assertGreaterEqual(readings[0].confidence, 0.5)
        self.assertEqual(readings[0].ocr_engine, "easyocr_local")

    def test_mock_ocr_provider_drives_identity_resolution(self) -> None:
        """
        Verify that MockOCRProvider generates valid JerseyEvidenceRecords that
        integrate with IdentityResolver and resolve player identities causally.
        """
        import numpy as np
        roster = RosterConfig(
            team_a_id="team_red",
            team_b_id="team_blue",
            team_a_name="Red Hawks",
            team_b_name="Blue Waves",
            team_a_color_rgb=(220, 20, 20),
            team_b_color_rgb=(20, 40, 220),
            players=[
                RosterPlayer(player_id="p_red_23", team_id="team_red", jersey_number="23", name="Jordan"),
            ],
            provenance_status="approved",
        )
        provider = MockOCRProvider(default_number="23", default_confidence=1.0)
        resolver = IdentityResolver(roster, confirmation_hits_threshold=2)

        # Add team observation
        resolver.add_team_observation("trk_01", "team_red", 1.0, 0.0)

        # Frame 0 crop reading
        dummy_crop = np.random.randint(0, 255, size=(50, 40, 3), dtype=np.uint8)
        readings_0 = provider.read_jersey(dummy_crop, "trk_01", 0, 0.0)
        self.assertEqual(len(readings_0), 1)
        self.assertEqual(readings_0[0].detected_number, "23")
        resolver.add_jersey_evidence(readings_0[0])

        # After 1 hit (< threshold 2) -> player is still unresolved
        mapping_0 = resolver.update_track_mapping("trk_01", 0.0)
        self.assertEqual(mapping_0.team_id, "team_red")
        self.assertIsNone(mapping_0.player_id)

        # Frame 5 crop reading
        resolver.add_team_observation("trk_01", "team_red", 1.0, 0.167)
        readings_1 = provider.read_jersey(dummy_crop, "trk_01", 5, 0.167)
        resolver.add_jersey_evidence(readings_1[0])

        # After 2 hits (>= threshold 2) -> player confirmed!
        mapping_1 = resolver.update_track_mapping("trk_01", 0.167)
        self.assertEqual(mapping_1.player_id, "p_red_23")


if __name__ == "__main__":
    unittest.main()
