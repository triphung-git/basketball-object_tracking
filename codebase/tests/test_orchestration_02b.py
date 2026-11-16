"""Unit and regression tests for Continuous Event Orchestration (Task 02B).

Verifies:
1. Stream-to-PRA orchestration and output bundle
2. Positive PTS/REB/AST via separated synthetic diagnostic
3. No-event / unknown clean handling (0-event run)
4. Cuts and gaps handling
5. Duplicate / replay ledger idempotency
6. Incomplete stream (partial status)
7. Writer / directory failure handling
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

import numpy as np

from basketball_scoreboard.assists import AssistCandidate, AssistEngine
from basketball_scoreboard.boxscore import BoxScoreEngine
from basketball_scoreboard.config import APPROVED_MODEL_ID
from basketball_scoreboard.continuous_orchestration import run_continuous_orchestration
from basketball_scoreboard.events import (
    EventLedger,
    EventStatus,
    EventType,
    LedgerEventRecord,
)
from basketball_scoreboard.identity import RosterConfig
from basketball_scoreboard.points import PointEventRecord, PointsEngine
from basketball_scoreboard.rebounds import ReboundCandidate, ReboundEngine
from basketball_scoreboard.shots import RimApertureGeometry, ShotCandidateRecord, ShotPhase
from basketball_scoreboard.spatial_io import file_hash
from basketball_scoreboard.video import VideoWriter


class TestOrchestration02B(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.tmp = Path(self.temp_dir.name)

        # 10 frames at 10 fps synthetic video
        self.video_path = self.tmp / "synth_video.mp4"
        with VideoWriter(self.video_path, 320, 240, 10) as writer:
            for i in range(10):
                img = np.full((240, 320, 3), fill_value=i * 20, dtype=np.uint8)
                writer.write_frame(img, source_time_s=i * 0.1)

        self.video_sha = file_hash(self.video_path)

        # Roster
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
        self.roster = RosterConfig.from_dict(self.roster_data)

        # Mock detector
        self.mock_detector = MagicMock()
        self.mock_detector.warmup.return_value = None
        self.mock_detector.get_runtime_info.return_value = {
            "model_id": APPROVED_MODEL_ID,
            "class_mapping": {"0": "ball", "1": "human", "2": "rim"},
        }
        self.mock_detector.detect.return_value = ([], 5.0)

    def test_stream_to_pra_orchestration_bundle(self):
        """1. Verify full output bundle from continuous orchestration."""
        out_dir = self.tmp / "orch_bundle_out"
        res = run_continuous_orchestration(
            video_path=self.video_path,
            output_dir=out_dir,
            roster_config_path=self.roster_path,
            detector_factory=lambda: self.mock_detector,
            allow_uncalibrated=True,
            quiet=True,
        )
        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["stage_counts"]["total_frames_read"], 10)

        expected_files = [
            "run.json",
            "shots_auto.jsonl",
            "events_auto.jsonl",
            "events_raw.jsonl",
            "audit_trail.jsonl",
            "checkpoint.json",
            "boxscore_auto.csv",
            "heatmap_summary.json",
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
        for fname in expected_files:
            p = out_dir / fname
            self.assertTrue(p.is_file(), f"Missing required file: {fname}")

        # Check boxscore_auto.csv contains header
        csv_text = (out_dir / "boxscore_auto.csv").read_text(encoding="utf-8")
        self.assertIn("Team,Player_ID,Jersey,Name,PTS,1PT,2PT,FT,OREB,DREB,REB,AST,TO", csv_text)

    def test_positive_pts_reb_ast_synthetic(self):
        """2. Synthetic diagnostic test proving positive PTS, REB, and AST orchestration and score conservation."""
        ledger = EventLedger(ledger_id="test_pra_ledger")
        points_engine = PointsEngine(roster=self.roster)
        rebound_engine = ReboundEngine()
        assist_engine = AssistEngine()
        box_engine = BoxScoreEngine(roster=self.roster)

        # Step 1: Simulate confirmed made shot with assist
        # Pass from VIE_01 to VIE_02 at t=1.0s
        pass_events = [{
            "pass_id": "pass_001",
            "status": "auto_confirmed",
            "confidence": 0.95,
            "passer": {"player_id": "VIE_01", "team_id": "VIE", "track_id": "trk_01"},
            "receiver": {"player_id": "VIE_02", "team_id": "VIE", "track_id": "trk_02"},
            "receive_time_s": 1.2,
            "release_time_s": 1.0,
            "observed_flight_samples": 4,
            "evidence": {"dribbles": 0, "action": "catch_and_shoot"},
        }]

        # Made shot released by VIE_02 at t=1.8s, outcome at t=2.5s
        made_shot = ShotCandidateRecord(
            shot_id="shot_made_001",
            video_id="test_vid",
            segment_id="default",
            camera_id="cam_main",
            status="auto_confirmed",
            outcome="made",
            phase=ShotPhase.BASKET,
            release_time_s=1.8,
            outcome_time_s=2.5,
            shooter_player_id="VIE_02",
            shooter_team_id="VIE",
            point_value=2,
        )

        # Ingest made shot into points engine
        pts_event = points_engine.process_shot(
            shot=made_shot,
            player_observations=[],
            jersey_evidence=[],
            is_free_throw=False,
            court_distance_m=7.0,  # 2PT in 3x3
        )
        self.assertIsNotNone(pts_event)
        self.assertEqual(pts_event.point_value, 2)
        self.assertEqual(pts_event.scoring_player_id, "VIE_02")

        # Convert to ledger record and append
        shot_rec = LedgerEventRecord(
            event_id=made_shot.shot_id,
            event_type=EventType.SHOT,
            source_time_s=1.8,
            frame_index=18,
            team_id="VIE",
            player_id="VIE_02",
            point_value=2,
            subtype="field_goal",
            status=EventStatus.AUTO_CONFIRMED,
            parent_event_id=made_shot.shot_id,
        )
        ledger.record_event(shot_rec)

        # Evaluate Assist for made shot
        ast_cand = assist_engine.evaluate_made_shot(
            shot_id=made_shot.shot_id,
            shot_outcome="made",
            scorer_team_id="VIE",
            scorer_player_id="VIE_02",
            release_time_s=1.8,
            pass_events=pass_events,
            intervening_events=[],
        )
        self.assertIsNotNone(ast_cand)
        self.assertEqual(ast_cand.passer_player_id, "VIE_01")
        self.assertEqual(ast_cand.scorer_player_id, "VIE_02")
        ast_rec = ast_cand.to_ledger_record()
        ledger.record_event(ast_rec)

        # Step 2: Simulate missed shot with defensive rebound
        # Missed shot taken by VIE_02 at t=5.0s, miss at t=5.8s
        miss_shot = ShotCandidateRecord(
            shot_id="shot_miss_002",
            video_id="test_vid",
            segment_id="default",
            camera_id="cam_main",
            status="auto_confirmed",
            outcome="rim_hit",
            phase=ShotPhase.MISS,
            release_time_s=5.0,
            outcome_time_s=5.8,
            shooter_player_id="VIE_02",
            shooter_team_id="VIE",
        )

        # Recovery by opponent TGA_01 at t=6.1s - 6.4s (sustained control)
        control_obs = [
            {"source_time_s": 6.10, "state": "controlled", "sample_type": "observed", "confidence": 0.9,
             "controller": {"player_id": "TGA_01", "team_id": "TGA", "track_id": "trk_tga1"}},
            {"source_time_s": 6.20, "state": "controlled", "sample_type": "observed", "confidence": 0.9,
             "controller": {"player_id": "TGA_01", "team_id": "TGA", "track_id": "trk_tga1"}},
            {"source_time_s": 6.30, "state": "controlled", "sample_type": "observed", "confidence": 0.9,
             "controller": {"player_id": "TGA_01", "team_id": "TGA", "track_id": "trk_tga1"}},
        ]
        reb_cand = rebound_engine.evaluate_missed_shot(
            shot_id=miss_shot.shot_id,
            shot_outcome="rim_hit",
            shooting_team_id="VIE",
            miss_time_s=5.8,
            control_observations=control_obs,
            is_last_free_throw=False,
        )
        self.assertIsNotNone(reb_cand)
        self.assertIn("defensive", str(reb_cand.rebound_type).lower())
        self.assertEqual(reb_cand.player_id, "TGA_01")
        reb_rec = reb_cand.to_ledger_record()
        ledger.record_event(reb_rec)

        # Step 3: Compile box score and verify mathematical conservation
        team_a, team_b = box_engine.compile(ledger)

        # Vietnam: 2 PTS (scored by VIE_02), 1 AST (dished by VIE_01)
        self.assertEqual(team_a.total_score, 2)
        self.assertEqual(team_a.players["VIE_02"].points, 2)
        self.assertEqual(team_a.players["VIE_02"].fg_made_2pt, 1)
        self.assertEqual(team_a.assists, 1)
        self.assertEqual(team_a.players["VIE_01"].assists, 1)

        # Tonga: 1 DREB (secured by TGA_01)
        self.assertEqual(team_b.total_score, 0)
        self.assertEqual(team_b.rebounds_total, 1)
        self.assertEqual(team_b.rebounds_defensive, 1)
        self.assertEqual(team_b.players["TGA_01"].rebounds_total, 1)
        self.assertEqual(team_b.players["TGA_01"].rebounds_defensive, 1)

    def test_no_event_unknown_handling(self):
        """3. Event-free run produces zero points/rebounds/assists without hallucination."""
        out_dir = self.tmp / "no_event_out"
        res = run_continuous_orchestration(
            video_path=self.video_path,
            output_dir=out_dir,
            roster_config_path=self.roster_path,
            detector_factory=lambda: self.mock_detector,
            allow_uncalibrated=True,
            quiet=True,
        )
        totals = res["boxscore_totals"]["match_totals"]
        self.assertEqual(totals["points"], 0)
        self.assertEqual(totals["rebounds"], 0)
        self.assertEqual(totals["assists"], 0)
        self.assertEqual(res["stage_counts"]["confirmed_shots"], 0)

    def test_cuts_and_gaps_handling(self):
        """4. Verify tracking exclusions flag cut frames and avoid false triggers."""
        policy_path = self.tmp / "cut_policy.json"
        policy_path.write_text(json.dumps({
            "source_video_sha256": self.video_sha,
            "image_roi_normalized": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            "intervals": [{"start_time_s": 0.2, "end_time_s": 0.6, "reason": "scene_cut"}],
        }), encoding="utf-8")

        out_dir = self.tmp / "cuts_orch_out"
        res = run_continuous_orchestration(
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

    def test_duplicate_and_replay_idempotency(self):
        """5. Verify checkpointing and transaction replay reproduces identical totals."""
        ledger = EventLedger(ledger_id="test_idemp")
        ev1 = LedgerEventRecord(
            event_id="shot_1",
            event_type=EventType.SHOT,
            source_time_s=1.0,
            frame_index=10,
            team_id="VIE",
            player_id="VIE_01",
            point_value=1,
            status=EventStatus.AUTO_CONFIRMED,
        )
        ledger.record_event(ev1)
        # Duplicate append must be suppressed
        ledger.record_event(ev1)
        self.assertEqual(len(ledger.get_active_events()), 1)

        chk_path = self.tmp / "test_chk.json"
        chk = ledger.save_checkpoint(chk_path)
        self.assertIn("checksum", chk)

        # Restore in fresh ledger
        restored = EventLedger.load_checkpoint(chk_path)
        self.assertEqual(len(restored.get_active_events()), 1)
        self.assertEqual(restored.get_active_events()[0].event_id, "shot_1")

    def test_incomplete_stream_handling(self):
        """6. Incomplete stream (max_frames < total_frames) reports status 'partial'."""
        out_dir = self.tmp / "partial_out"
        res = run_continuous_orchestration(
            video_path=self.video_path,
            output_dir=out_dir,
            roster_config_path=self.roster_path,
            detector_factory=lambda: self.mock_detector,
            max_frames=4,
            allow_uncalibrated=True,
            quiet=True,
        )
        self.assertEqual(res["status"], "partial")
        self.assertEqual(res["stage_counts"]["total_frames_read"], 4)

    def test_writer_failure_handling(self):
        """7. Output directory conflict raises ValueError without modifying files."""
        existing_dir = self.tmp / "existing_dir"
        existing_dir.mkdir()
        sentinel = existing_dir / "sentinel.txt"
        sentinel.write_text("keep_me", encoding="utf-8")

        with self.assertRaises(ValueError):
            run_continuous_orchestration(
                video_path=self.video_path,
                output_dir=existing_dir,
                roster_config_path=self.roster_path,
                detector_factory=lambda: self.mock_detector,
                allow_uncalibrated=True,
                quiet=True,
            )
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep_me")


if __name__ == "__main__":
    unittest.main()
