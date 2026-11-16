"""Regression checks for manifest preservation and stable IDs."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("prepare_dataset", Path(__file__).parents[1] / "scripts/prepare_dataset.py")
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class PrepareDatasetTests(unittest.TestCase):
    def test_manifest_writer_never_overwrites_existing_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.csv"
            path.write_text("curated", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                prepare.write_manifest_csv([], path)
            self.assertEqual(path.read_text(), "curated")

    def test_unknown_video_id_is_stable_when_new_filename_sorts_first(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "z.mp4").write_bytes(b"original")
            metadata = {"width": 640, "height": 480, "fps": 30, "duration_s": 2, "frame_count": 60}
            with patch.object(prepare, "probe_video", return_value=metadata):
                before = prepare.collect_manifest([root], root)
                (root / "a.mp4").write_bytes(b"new")
                after = prepare.collect_manifest([root], root)
            self.assertEqual(before[0]["video_id"], next(row["video_id"] for row in after if row["relative_path"] == "z.mp4"))
