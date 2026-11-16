"""Unit tests for dataset validator enforcing schema, timebase, leakage, and draft isolation.

Uses synthetic fixtures in temporary directories without modifying real data files.
"""
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "validate_dataset",
    Path(__file__).parents[1] / "scripts/validate_dataset.py",
)
val_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(val_mod)


class DatasetValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.data_dir = self.root / "data"
        self.annotations_dir = self.data_dir / "annotations"
        self.annotations_dir.mkdir(parents=True, exist_ok=True)
        (self.root / "assets").mkdir()
        for name in ("v1.mp4", "v2.mp4"):
            (self.root / "assets" / name).write_bytes(name.encode())
        hash1 = val_mod.compute_file_sha256(self.root / "assets/v1.mp4")
        hash2 = val_mod.compute_file_sha256(self.root / "assets/v2.mp4")

        # Baseline valid manifest
        self.manifest_path = self.data_dir / "manifest.csv"
        self._write_csv(
            self.manifest_path,
            [
                "video_id,relative_path,width,height,fps,duration_s,frame_count,camera_id,session_id,conditions,scoring_eligibility,notes,sha256",
                f"vid01,assets/v1.mp4,1920,1080,30.0,10.0,300,cam1,sess1,day_static,scoring_eligible,note,{hash1}",
                f"vid02,assets/v2.mp4,1920,1080,30.0,12.0,360,cam2,sess2,day_static,scoring_eligible,note,{hash2}",
            ],
        )

        # Baseline valid events.csv (empty approved ground truth)
        self.events_path = self.annotations_dir / "events.csv"
        self._write_csv(
            self.events_path,
            ["video_id,shot_id,start_s,end_s,result,score_time_s,team,point_value,notes"],
        )

        # Baseline valid events.draft.csv
        self.draft_path = self.annotations_dir / "events.draft.csv"
        self._write_csv(
            self.draft_path,
            [
                "video_id,shot_id,start_s,end_s,result,score_time_s,team,point_value,notes",
                "vid01,s001,1.0,4.0,made,2.5,solo,2,clear shot",
                "vid02,s001,2.0,6.0,miss,,solo,2,rim bounce",
            ],
        )

        # Baseline valid reviews.csv
        self.reviews_path = self.annotations_dir / "reviews.csv"
        self._write_csv(
            self.reviews_path,
            [
                "video_id,shot_id,review_status,reviewer,reviewed_at_utc,rejection_or_approval_reason",
                "vid01,s001,needs_review,,,agent proposal",
                "vid02,s001,needs_review,,,agent proposal",
            ],
        )

        # Baseline valid coverage.csv
        self.coverage_path = self.annotations_dir / "coverage.csv"
        self._write_csv(
            self.coverage_path,
            [
                "video_id,start_s,end_s,coverage_status,reason",
                "vid01,0.0,10.0,needs_review,full scan awaiting user review",
                "vid02,0.0,12.0,needs_review,full scan awaiting user review",
            ],
        )

        # Baseline valid splits.json
        self.splits_path = self.data_dir / "splits.json"
        manifest_hash = val_mod.compute_file_sha256(self.manifest_path)
        splits_data = {
            "version": "1.0.0",
            "status": "proposed",
            "source_groups": {
                "group1": {"camera_id": "cam1", "session_id": "sess1", "video_ids": ["vid01"]},
                "group2": {"camera_id": "cam2", "session_id": "sess2", "video_ids": ["vid02"]},
            },
            "proposed_split": {
                "calibration": {"video_ids": ["vid01"]},
                "test": {"video_ids": ["vid02"]},
            },
            "integrity_fingerprints": {"manifest_sha256": manifest_hash},
        }
        self.splits_path.write_text(json.dumps(splits_data, indent=2), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_csv(self, path: Path, lines: list[str]) -> None:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_baseline_dataset_passes_structural_validation(self):
        res = val_mod.validate_dataset(self.root)
        self.assertTrue(res.is_valid, f"Expected valid, got errors: {res.errors}")
        self.assertEqual(len(res.errors), 0)
        # Not ready because approved events are empty
        self.assertFalse(res.is_ready_for_evaluation)

    def test_duplicate_key_in_events_rejected(self):
        self._write_csv(
            self.draft_path,
            [
                "video_id,shot_id,start_s,end_s,result,score_time_s,team,point_value,notes",
                "vid01,s001,1.0,4.0,made,2.5,solo,2,first",
                "vid01,s001,5.0,8.0,miss,,solo,2,duplicate key",
            ],
        )
        res = val_mod.validate_dataset(self.root)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("duplicate key" in e for e in res.errors))

    def test_out_of_range_and_nonfinite_timestamps_rejected(self):
        # start_s >= end_s, end_s > duration (10s), nonfinite value
        self._write_csv(
            self.draft_path,
            [
                "video_id,shot_id,start_s,end_s,result,score_time_s,team,point_value,notes",
                "vid01,s001,5.0,3.0,made,4.0,solo,2,inverted interval",
                "vid01,s002,2.0,15.0,miss,,solo,2,exceeds video duration",
                "vid01,s003,NaN,4.0,miss,,solo,2,non-finite timestamp",
            ],
        )
        res = val_mod.validate_dataset(self.root)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("start_s (5.0) >= end_s (3.0)" in e for e in res.errors))
        self.assertTrue(any("exceeds video duration" in e for e in res.errors))
        self.assertTrue(any("non-numeric or missing" in e for e in res.errors))

    def test_made_missing_score_time_rejected(self):
        self._write_csv(
            self.draft_path,
            [
                "video_id,shot_id,start_s,end_s,result,score_time_s,team,point_value,notes",
                "vid01,s001,1.0,4.0,made,,solo,2,made without score_time",
            ],
        )
        res = val_mod.validate_dataset(self.root)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("score_time_s is missing or invalid" in e for e in res.errors))

    def test_score_time_outside_shot_interval_rejected(self):
        self._write_csv(
            self.draft_path,
            [
                "video_id,shot_id,start_s,end_s,result,score_time_s,team,point_value,notes",
                "vid01,s001,1.0,4.0,made,5.5,solo,2,score_time outside interval",
            ],
        )
        res = val_mod.validate_dataset(self.root)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("outside shot interval" in e for e in res.errors))

    def test_miss_or_uncertain_with_score_time_rejected(self):
        self._write_csv(
            self.draft_path,
            [
                "video_id,shot_id,start_s,end_s,result,score_time_s,team,point_value,notes",
                "vid01,s001,1.0,4.0,miss,2.5,solo,2,miss should not have score_time",
                "vid02,s001,2.0,5.0,uncertain,3.5,solo,2,uncertain should not have score_time",
            ],
        )
        res = val_mod.validate_dataset(self.root)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("result is 'miss' but score_time_s is populated" in e for e in res.errors))
        self.assertTrue(any("result is 'uncertain' but score_time_s is populated" in e for e in res.errors))

    def test_same_source_group_split_leakage_rejected(self):
        # Group 1 contains vid01 and vid02, but vid01 is in calibration and vid02 is in test!
        splits_data = {
            "version": "1.0.0",
            "status": "proposed",
            "source_groups": {
                "shared_group": {"camera_id": "cam1", "session_id": "sess1", "video_ids": ["vid01", "vid02"]},
            },
            "proposed_split": {
                "calibration": {"video_ids": ["vid01"]},
                "test": {"video_ids": ["vid02"]},
            },
        }
        self.splits_path.write_text(json.dumps(splits_data), encoding="utf-8")
        res = val_mod.validate_dataset(self.root)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("Source group leakage" in e for e in res.errors))

    def test_same_video_in_both_splits_rejected(self):
        splits_data = {
            "version": "1.0.0",
            "status": "proposed",
            "source_groups": {},
            "proposed_split": {
                "calibration": {"video_ids": ["vid01"]},
                "test": {"video_ids": ["vid01"]},
            },
        }
        self.splits_path.write_text(json.dumps(splits_data), encoding="utf-8")
        res = val_mod.validate_dataset(self.root)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("Data split leakage: videos ['vid01'] appear in both" in e for e in res.errors))

    def test_locked_split_checksum_mismatch_rejected(self):
        splits_data = {
            "version": "1.0.0",
            "status": "locked",
            "source_groups": {},
            "proposed_split": {
                "calibration": {"video_ids": ["vid01"]},
                "test": {"video_ids": ["vid02"]},
            },
            "integrity_fingerprints": {"manifest_sha256": "0000000000000000000000000000000000000000000000000000000000000000"},
        }
        self.splits_path.write_text(json.dumps(splits_data), encoding="utf-8")
        res = val_mod.validate_dataset(self.root)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("Locked manifest checksum mismatch" in e for e in res.errors))

    def test_unreviewed_draft_not_promoted_to_approved(self):
        # Adding an approved record to events.csv without an approved entry in reviews.csv
        self._write_csv(
            self.events_path,
            [
                "video_id,shot_id,start_s,end_s,result,score_time_s,team,point_value,notes",
                "vid01,s001,1.0,4.0,made,2.5,solo,2,unapproved shot",
            ],
        )
        # reviews.csv has it as 'needs_review'
        self._write_csv(
            self.reviews_path,
            [
                "video_id,shot_id,review_status,reviewer,reviewed_at_utc,rejection_or_approval_reason",
                "vid01,s001,needs_review,,,agent proposal",
            ],
        )
        res = val_mod.validate_dataset(self.root)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("review_status 'needs_review' in reviews.csv, not 'approved'" in e for e in res.errors))

    def test_overlapping_shots_flagged_as_warning(self):
        self._write_csv(
            self.draft_path,
            [
                "video_id,shot_id,start_s,end_s,result,score_time_s,team,point_value,notes",
                "vid01,s001,1.0,5.0,made,3.0,solo,2,first shot",
                "vid01,s002,4.0,7.0,miss,,solo,2,overlapping shot",
            ],
        )
        res = val_mod.validate_dataset(self.root)
        self.assertTrue(res.is_valid)  # Overlap is a warning, not fatal error
        self.assertTrue(any("Temporal overlap detected" in w for w in res.warnings))

    def _reviewed_pilot(self):
        self.events_path.write_text(
            "video_id,shot_id,start_s,end_s,result,score_time_s,team,point_value,notes\n"
            "vid01,s001,1,4,made,2,solo,2,calibration\n"
            "vid02,s001,1,4,made,2,solo,2,test made\n"
            "vid02,s002,5,8,miss,,solo,2,test miss\n", encoding="utf-8")
        self.draft_path.write_text(self.events_path.read_text(encoding="utf-8").splitlines()[0] + "\n", encoding="utf-8")
        self.reviews_path.write_text(
            "video_id,shot_id,review_status,reviewer,reviewed_at_utc,rejection_or_approval_reason\n"
            "vid01,s001,approved,fixture,2026-01-01T00:00:00Z,synthetic\n"
            "vid02,s001,approved,fixture,2026-01-01T00:00:00Z,synthetic\n"
            "vid02,s002,approved,fixture,2026-01-01T00:00:00Z,synthetic\n", encoding="utf-8")
        self.coverage_path.write_text(
            "video_id,start_s,end_s,coverage_status,reason\n"
            "vid01,0,10,fully_reviewed,synthetic\n"
            "vid02,0,12,fully_reviewed,synthetic\n", encoding="utf-8")
        self._lock()

    def _lock(self):
        data = json.loads(self.splits_path.read_text(encoding="utf-8"))
        data["status"] = "locked"
        data["integrity_fingerprints"] = {
            name + "_sha256": val_mod.compute_file_sha256(path) for name, path in
            (("manifest", self.manifest_path), ("events", self.events_path), ("coverage", self.coverage_path))}
        self.splits_path.write_text(json.dumps(data), encoding="utf-8")

    def test_small_reviewed_pilot_is_ready_with_sample_size_warning(self):
        self._reviewed_pilot()
        result = val_mod.validate_dataset(self.root, require_ready=True)
        self.assertTrue(result.is_ready_for_evaluation, result.errors + result.readiness_notes)
        self.assertTrue(any("Small pilot" in warning for warning in result.warnings))

    def test_locked_labels_and_coverage_changes_are_detected(self):
        self._reviewed_pilot()
        for path, label in ((self.events_path, "events"), (self.coverage_path, "coverage")):
            original = path.read_bytes()
            path.write_bytes(original.replace(b"synthetic", b"changed") if label == "coverage" else original.replace(b"calibration", b"changed"))
            result = val_mod.validate_dataset(self.root)
            self.assertTrue(any(f"Locked {label} checksum mismatch" in error for error in result.errors), result.errors)
            path.write_bytes(original)

    def test_media_tampering_detected(self):
        (self.root / "assets/v1.mp4").write_bytes(b"changed media")
        result = val_mod.validate_dataset(self.root)
        self.assertTrue(any("media checksum mismatch" in error for error in result.errors))

    def test_test_split_classes_cannot_be_borrowed_from_calibration(self):
        self._reviewed_pilot()
        self.events_path.write_text(self.events_path.read_text().replace("vid02,s002,5,8,miss,,", "vid02,s002,5,8,made,6,"), encoding="utf-8")
        self._lock()
        result = val_mod.validate_dataset(self.root)
        self.assertFalse(result.is_ready_for_evaluation)
        self.assertIn("Approved test split lacks 'miss' shots.", result.readiness_notes)

    def test_missing_review_ledger_rejected(self):
        self.reviews_path.unlink()
        self.assertFalse(val_mod.validate_dataset(self.root).is_valid)

    def test_coverage_overlap_rejected(self):
        with self.coverage_path.open("a") as handle:
            handle.write("vid01,1,3,excluded,replay\n")
        result = val_mod.validate_dataset(self.root)
        self.assertTrue(any("Coverage overlap" in error for error in result.errors))

    def test_excluded_shot_cannot_pass_readiness(self):
        self._reviewed_pilot()
        self.coverage_path.write_text(self.coverage_path.read_text().replace("vid02,0,12,fully_reviewed", "vid02,0,12,excluded"), encoding="utf-8")
        self._lock()
        self.assertFalse(val_mod.validate_dataset(self.root).is_ready_for_evaluation)

    def test_manifest_source_leakage_cannot_be_hidden_by_omitting_groups(self):
        self.manifest_path.write_text(self.manifest_path.read_text().replace("cam2,sess2", "cam1,sess1"), encoding="utf-8")
        data = json.loads(self.splits_path.read_text())
        data["source_groups"] = {}
        self.splits_path.write_text(json.dumps(data), encoding="utf-8")
        result = val_mod.validate_dataset(self.root)
        self.assertTrue(any("Manifest session_id leakage" in error for error in result.errors))

    def test_duplicate_ids_inside_split_rejected(self):
        data = json.loads(self.splits_path.read_text())
        data["proposed_split"]["test"]["video_ids"] = ["vid02", "vid02"]
        self.splits_path.write_text(json.dumps(data), encoding="utf-8")
        self.assertTrue(any("Duplicate video IDs" in error for error in val_mod.validate_dataset(self.root).errors))

    def test_manifest_path_escape_rejected(self):
        self.manifest_path.write_text(self.manifest_path.read_text().replace("assets/v1.mp4", "../outside.mp4"), encoding="utf-8")
        self.assertTrue(any("path must stay inside" in error for error in val_mod.validate_dataset(self.root).errors))


if __name__ == "__main__":
    unittest.main()
