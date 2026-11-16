"""Independent synthetic dataset tests; no real labels/media are modified."""
import csv
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from validate_dataset_v2 import validate_dataset_v2
from prepare_dataset_v2 import write_manifest, initialize_v2_templates
from basketball_scoreboard.dataset_schema import ANNOTATION_HEADERS


class Task04AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "data/v2"
        (self.data / "annotations").mkdir(parents=True)
        (self.root / "media").mkdir()
        header = "video_id,relative_path,sha256,width,height,fps,nb_frames,duration_s,time_base,is_vfr,camera_group,session_id,source_type,source_group,provenance_status,notes\n"
        for index in (1, 2):
            content = str(index).encode()
            (self.root / f"media/{index}.mp4").write_bytes(content)
            header += f"v{index},media/{index}.mp4,{hashlib.sha256(content).hexdigest()},100,100,30,300,10,1/30,False,c{index},s{index},fixture,g{index},confirmed,synthetic\n"
        (self.data / "manifest.csv").write_text(header)
        (self.data / "roster.csv").write_text("team_id,player_id,jersey_number,name,is_active\nA,A1,1,Fixture A1,true\nA,A2,2,Fixture A2,true\nB,B1,1,Fixture B1,true\n")
        self.rules = {"rule_profile": "synthetic fixture", "point_values": {"inside_arc": 1, "outside_arc": 2, "free_throw": 1},
                      "review_status": "approved", "applicability_status": "confirmed", "roster_status": "approved", "protocol_status": "approved"}
        (self.data / "ruleset.json").write_text(json.dumps(self.rules))
        self.split = {"status": "proposed", "proposed_split": {"calibration": {"video_ids": ["v1"]}, "test": {"video_ids": ["v2"]}}}
        (self.data / "splits.json").write_text(json.dumps(self.split))
        for table, columns in ANNOTATION_HEADERS.items():
            self.write(table, [])

    def write(self, table, rows):
        with (self.data / f"annotations/{table}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(ANNOTATION_HEADERS[table].split(","))
            writer.writerows(rows)

    def test_fresh_templates_do_not_invent_players_or_split_video_ids(self):
        folder = self.root / "fresh-v2"
        initialize_v2_templates(folder)
        split = json.loads((folder / "splits.json").read_text())
        self.assertTrue(all(not p["video_ids"] for p in split["proposed_split"].values()))
        with (folder / "roster.csv").open() as handle:
            self.assertEqual(list(csv.DictReader(handle)), [])
        self.assertTrue(all((folder / "annotations" / (name + ".csv")).is_file() for name in ANNOTATION_HEADERS))

    def test_pending_protocol_cannot_be_data_ready(self):
        self.populate()
        self.rules["protocol_status"] = "draft"
        (self.data / "ruleset.json").write_text(json.dumps(self.rules))
        result = validate_dataset_v2(self.root)
        self.assertTrue(result.is_structurally_valid)
        self.assertFalse(result.is_data_ready)

    def test_unreviewed_provenance_cannot_be_data_ready(self):
        self.populate()
        path = self.data / "manifest.csv"
        path.write_text(path.read_text().replace(",confirmed,", ",pending,"))
        self.assertFalse(validate_dataset_v2(self.root).is_data_ready)

    def test_same_source_group_cannot_cross_splits(self):
        path = self.data / "manifest.csv"
        path.write_text(path.read_text().replace(",g2,", ",g1,"))
        self.assertFalse(validate_dataset_v2(self.root).is_structurally_valid)

    def test_approved_event_cannot_depend_on_draft_pass(self):
        self.populate()
        path = self.data / "annotations/reviews.csv"
        path.write_text(path.read_text().replace("passes,v1p1,approved", "passes,v1p1,draft"))
        result = validate_dataset_v2(self.root)
        self.assertTrue(result.is_structurally_valid)
        self.assertFalse(result.is_data_ready)
        self.assertTrue(any("unapproved passes/v1p1" in n for n in result.readiness_notes))

    def populate(self):
        rows = {table: [] for table in ANNOTATION_HEADERS}
        for vid in ("v1", "v2"):
            rows["shots"] += [[vid+"s1", vid, "A2", "A", 4, 5, "1pt", "made", 4.9, "fixture"],
                              [vid+"s2", vid, "B1", "B", 7, 8, "2pt", "miss", "", "fixture"]]
            rows["passes"] += [[vid+"p1", vid, "A1", "A2", "A", 3, 3.3, "completed"],
                               [vid+"p2", vid, "A1", "A2", "A", 1, 1.2, "completed"]]
            rows["rebounds"] += [[vid+"r1", vid, vid+"s2", "A1", "A", 8.3, "defensive", "fixture"]]
            rows["assists"] += [[vid+"a1", vid, vid+"p1", vid+"s1", "A1", "A2", "A", 3, "eligible", "fixture"],
                                [vid+"a2", vid, vid+"p2", vid+"s1", "A1", "A2", "A", 1, "ineligible", "earlier pass"]]
            rows["coverage"] += [[vid, vid+"cov", 0, 10, "fully_reviewed", "fixture"]]
            rows["player_positions"] += [[vid+"pos", vid, "A1", "A", 2.8, 10, 10, 1, 2, "visible", "fixture"]]
            rows["identities"] += [[vid+"id", vid, "track1", "A1", "A", 0, 9, "synthetic", "fixture"]]
            rows["ball_control"] += [[vid+"control", vid, "A1", "A", 2.8, 3, "controlled", "observed", "fixture"]]
        for table, records in rows.items():
            if table == "reviews":
                continue
            for row in records:
                record_id = row[1] if table == "coverage" else row[0]
                rows["reviews"].append([table, record_id, "approved", "fixture", "2026-01-01T00:00:00Z", "synthetic test only"])
        for table, records in rows.items():
            self.write(table, records)

    def lock(self):
        self.split["status"] = "locked"
        (self.data / "splits.json").write_text(json.dumps(self.split))
        hashes = {p.relative_to(self.data).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.data.rglob("*") if p.is_file() and p.name != "lock.json"}
        (self.data / "lock.json").write_text(json.dumps({"files": hashes}))

    def test_empty_schema_is_tooling_not_data_ready(self):
        result = validate_dataset_v2(self.root)
        self.assertTrue(result.is_structurally_valid, result.errors)
        self.assertTrue(result.is_tooling_ready)
        self.assertFalse(result.is_data_ready)

    def test_complete_synthetic_locked_fixture_can_reach_locked_gate(self):
        self.populate()
        self.lock()
        result = validate_dataset_v2(self.root)
        self.assertTrue(result.is_locked_ready, result.errors + result.readiness_notes)

    def test_malformed_headers_cannot_pass_as_empty_ground_truth(self):
        (self.data / "annotations/shots.csv").write_text("wrong,header\n")
        self.assertFalse(validate_dataset_v2(self.root).is_structurally_valid)

    def test_nonfinite_shot_rebound_pass_assist_and_coverage_are_rejected(self):
        self.populate()
        for table, column in [("shots", "release_time_s"), ("rebounds", "rebound_time_s"),
                              ("passes", "receive_time_s"), ("assists", "assist_time_s"), ("coverage", "end_time_s")]:
            path = self.data / f"annotations/{table}.csv"
            original = path.read_text()
            lines = list(csv.reader(original.splitlines()))
            lines[1][lines[0].index(column)] = "NaN"
            with path.open("w", newline="") as handle:
                csv.writer(handle).writerows(lines)
            with self.subTest(table=table):
                result = validate_dataset_v2(self.root)
                self.assertFalse(result.is_structurally_valid)
                self.assertTrue(any("non-finite" in error for error in result.errors))
            path.write_text(original)

    def test_lock_tampering_is_detected_for_labels_roster_rules_and_split(self):
        self.populate()
        self.lock()
        for relative in ("annotations/shots.csv", "annotations/coverage.csv", "roster.csv", "ruleset.json", "splits.json"):
            path = self.data / relative
            original = path.read_bytes()
            path.write_bytes(original + b"\n")
            with self.subTest(file=relative):
                self.assertTrue(any("fingerprint" in error for error in validate_dataset_v2(self.root).errors))
            path.write_bytes(original)

    def test_missing_external_lock_cannot_claim_locked_ready(self):
        self.populate()
        self.split["status"] = "locked"
        (self.data / "splits.json").write_text(json.dumps(self.split))
        self.assertFalse(validate_dataset_v2(self.root).is_locked_ready)

    def test_unknown_split_video_and_duplicate_pass_are_rejected(self):
        self.split["proposed_split"]["test"]["video_ids"] = ["missing"]
        (self.data / "splits.json").write_text(json.dumps(self.split))
        self.assertFalse(validate_dataset_v2(self.root).is_structurally_valid)
        self.populate()
        path = self.data / "annotations/passes.csv"
        with path.open("a") as handle:
            handle.write(path.read_text().splitlines()[1] + "\n")
        self.assertTrue(any("duplicate pass_id" in error for error in validate_dataset_v2(self.root).errors))

    def test_cross_video_event_links_cannot_pass(self):
        self.populate()
        path = self.data / "annotations/assists.csv"
        path.write_text(path.read_text().replace("v1p1,v1s1", "v2p1,v1s1"))
        self.assertTrue(any("cross-video" in error for error in validate_dataset_v2(self.root).errors))

    def test_rebound_after_made_shot_rejected(self):
        self.populate()
        path = self.data / "annotations/rebounds.csv"
        path.write_text(path.read_text().replace("v1s2", "v1s1"))
        self.assertTrue(any("non-missed" in error for error in validate_dataset_v2(self.root).errors))

    def test_manifest_escape_and_blank_hash_rejected(self):
        path = self.data / "manifest.csv"
        text = path.read_text()
        path.write_text(text.replace("media/1.mp4", "../outside.mp4"))
        self.assertTrue(any("escapes" in error for error in validate_dataset_v2(self.root).errors))

    def test_zero_positive_assists_does_not_reach_data_gate(self):
        self.populate()
        path = self.data / "annotations/assists.csv"
        path.write_text(path.read_text().replace(",eligible,", ",ineligible,"))
        self.assertFalse(validate_dataset_v2(self.root).is_data_ready)

    def test_approved_coverage_cannot_be_replaced_by_excluded(self):
        self.populate()
        path = self.data / "annotations/coverage.csv"
        path.write_text(path.read_text().replace("fully_reviewed", "excluded"))
        self.assertFalse(validate_dataset_v2(self.root).is_data_ready)

    def test_preparer_never_overwrites_even_with_force(self):
        path = self.data / "manifest.csv"
        original = path.read_bytes()
        with self.assertRaises(FileExistsError):
            write_manifest(path, [], force=True)
        self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
