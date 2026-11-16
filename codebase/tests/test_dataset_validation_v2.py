"""Comprehensive test suite for Dataset v2 schema, integrity, and readiness validator."""
import copy
import csv
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

# Add codebase and scripts to path
CODEBASE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = CODEBASE_ROOT / "scripts"
SRC_ROOT = CODEBASE_ROOT / "src"

for p in (str(SCRIPTS_ROOT), str(SRC_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from validate_dataset_v2 import ValidationV2Result, validate_dataset_v2


class DatasetV2ValidationTests(unittest.TestCase):
    def test_v2_baseline_structural_validation(self):
        """Verify the initialized v2 dataset passes structural integrity and tooling readiness."""
        res = validate_dataset_v2(CODEBASE_ROOT)
        self.assertTrue(res.is_structurally_valid, f"Structural errors: {res.errors}")
        self.assertTrue(res.is_tooling_ready)
        # Not yet data-ready or locked-ready because ground truth annotations are pending review
        self.assertFalse(res.is_data_ready)
        self.assertFalse(res.is_locked_ready)

    def _create_temp_v2_environment(self, tmpdir: str) -> Path:
        """Copy codebase/data/v2 into a temporary directory for mutation testing."""
        temp_root = Path(tmpdir)
        target_v2 = temp_root / "data" / "v2"
        shutil.copytree(CODEBASE_ROOT / "data" / "v2", target_v2)
        # Mock media directory if needed
        (temp_root / "assets_test").mkdir(parents=True, exist_ok=True)
        return temp_root

    def test_dangling_shot_reference_in_rebounds_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = self._create_temp_v2_environment(tmpdir)
            rebounds_csv = temp_root / "data/v2/annotations/rebounds.csv"
            with rebounds_csv.open("a", newline="", encoding="utf-8") as f:
                f.write("r999,clip02,s_nonexistent,p_a1,team_a,10.5,defensive,notes\n")

            res = validate_dataset_v2(temp_root)
            self.assertFalse(res.is_structurally_valid)
            self.assertTrue(any("not in shots.csv" in err for err in res.errors))

    def test_dangling_pass_reference_in_assists_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = self._create_temp_v2_environment(tmpdir)
            assists_csv = temp_root / "data/v2/annotations/assists.csv"
            with assists_csv.open("a", newline="", encoding="utf-8") as f:
                f.write("ast999,clip02,pass_ghost,s001,p_a1,p_a2,team_a,5.0,eligible,notes\n")

            res = validate_dataset_v2(temp_root)
            self.assertFalse(res.is_structurally_valid)
            self.assertTrue(any("not in passes.csv" in err for err in res.errors))

    def test_passer_equals_scorer_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = self._create_temp_v2_environment(tmpdir)
            # Add a pass and shot
            (temp_root / "data/v2/annotations/passes.csv").write_text(
                "pass_id,video_id,passer_id,receiver_id,team_id,release_time_s,receive_time_s,outcome\n"
                "p01,clip02,p_a1,p_a1,team_a,4.0,4.5,completed\n",
                encoding="utf-8",
            )
            (temp_root / "data/v2/annotations/shots.csv").write_text(
                "shot_id,video_id,shooter_id,team_id,release_time_s,outcome_time_s,shot_type,result,score_time_s,notes\n"
                "s01,clip02,p_a1,team_a,5.0,6.0,1pt,made,6.0,Layup\n",
                encoding="utf-8",
            )
            (temp_root / "data/v2/annotations/assists.csv").write_text(
                "assist_id,video_id,pass_id,shot_id,passer_id,scorer_id,team_id,assist_time_s,eligibility,notes\n"
                "a01,clip02,p01,s01,p_a1,p_a1,team_a,4.0,eligible,Self-assist attempt\n",
                encoding="utf-8",
            )
            res = validate_dataset_v2(temp_root)
            self.assertFalse(res.is_structurally_valid)
            self.assertTrue(any("passer and scorer cannot be the same" in err for err in res.errors))

    def test_team_rebound_with_actor_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = self._create_temp_v2_environment(tmpdir)
            (temp_root / "data/v2/annotations/rebounds.csv").write_text(
                "rebound_id,video_id,shot_id,actor_id,team_id,rebound_time_s,rebound_type,notes\n"
                "r01,clip02,,p_a1,team_a,5.0,team_rebound,Team rebound cannot have individual actor\n",
                encoding="utf-8",
            )
            res = validate_dataset_v2(temp_root)
            self.assertFalse(res.is_structurally_valid)
            self.assertTrue(any("team_rebound must not have individual actor_id" in err for err in res.errors))

    def test_approved_event_missing_reviewer_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = self._create_temp_v2_environment(tmpdir)
            (temp_root / "data/v2/annotations/reviews.csv").write_text(
                "table_name,record_id,review_status,reviewer,reviewed_utc,review_notes\n"
                "shots,s01,approved,,,Missing reviewer name and timestamp\n",
                encoding="utf-8",
            )
            res = validate_dataset_v2(temp_root)
            self.assertFalse(res.is_structurally_valid)
            self.assertTrue(any("missing reviewer or reviewed_utc" in err for err in res.errors))

    def test_non_finite_or_out_of_range_timestamp_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = self._create_temp_v2_environment(tmpdir)
            (temp_root / "data/v2/annotations/shots.csv").write_text(
                "shot_id,video_id,shooter_id,team_id,release_time_s,outcome_time_s,shot_type,result,score_time_s,notes\n"
                "s01,clip02,p_a1,team_a,10.0,5.0,1pt,miss,,Reversed timing\n",
                encoding="utf-8",
            )
            res = validate_dataset_v2(temp_root)
            self.assertFalse(res.is_structurally_valid)
            self.assertTrue(any("invalid release/outcome timing" in err for err in res.errors))

    def test_session_split_leakage_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = self._create_temp_v2_environment(tmpdir)
            # Create manifest with two clips sharing a session
            (temp_root / "data/v2/manifest.csv").write_text(
                "video_id,relative_path,sha256,width,height,fps,nb_frames,duration_s,time_base,is_vfr,camera_group,session_id,source_type,notes\n"
                "clip_a,assets_test/a.mp4,,100,100,30,100,3.33,1/30,False,cam1,shared_session,broadcast,\n"
                "clip_b,assets_test/b.mp4,,100,100,30,100,3.33,1/30,False,cam1,shared_session,broadcast,\n",
                encoding="utf-8",
            )
            # Place mock files
            (temp_root / "assets_test/a.mp4").write_bytes(b"a")
            (temp_root / "assets_test/b.mp4").write_bytes(b"b")
            # Splits putting them in different splits
            (temp_root / "data/v2/splits.json").write_text(
                json.dumps({
                    "status": "draft",
                    "proposed_split": {
                        "calibration": {"video_ids": ["clip_a"]},
                        "test": {"video_ids": ["clip_b"]},
                    }
                }),
                encoding="utf-8",
            )
            res = validate_dataset_v2(temp_root)
            self.assertFalse(res.is_structurally_valid)
            self.assertTrue(any("leakage" in err for err in res.errors))

    def test_coverage_overlap_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = self._create_temp_v2_environment(tmpdir)
            (temp_root / "data/v2/annotations/coverage.csv").write_text(
                "video_id,interval_id,start_time_s,end_time_s,status,notes\n"
                "clip02,cov1,0.0,10.0,fully_reviewed,\n"
                "clip02,cov2,8.0,15.0,fully_reviewed,\n",
                encoding="utf-8",
            )
            res = validate_dataset_v2(temp_root)
            self.assertFalse(res.is_structurally_valid)
            self.assertTrue(any("overlapping intervals" in err for err in res.errors))


if __name__ == "__main__":
    unittest.main()
