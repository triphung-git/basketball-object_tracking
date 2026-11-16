"""Tests for credential handling and resized-to-original coordinate integrity."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("smoke_model", Path(__file__).parents[1] / "scripts/smoke_model.py")
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class SmokeContractTests(unittest.TestCase):
    def test_portrait_coordinates_recover_original_resolution(self):
        result = smoke.normalize_detections(
            [[10, 20, 100, 200]], [2], [0.8], ["human", "rim", "ball"],
            (2160, 3840), (720, 1280), 0.25,
        )
        self.assertEqual(result[0]["xyxy"], [30, 60, 300, 600])
        self.assertEqual(result[0]["class_name"], "ball")

    def test_corrupt_detections_are_rejected(self):
        for box, class_id, score in [([0, 0, float("nan"), 10], 0, 0.5),
                                     ([10, 0, 0, 10], 0, 0.5),
                                     ([0, 0, 10, 10], 9, 0.5),
                                     ([0, 0, 10, 10], 0, 1.1)]:
            with self.subTest(box=box, class_id=class_id, score=score), self.assertRaises(ValueError):
                smoke.normalize_detections([box], [class_id], [score], ["ball"], (100, 100), (100, 100), 0.25)

    def test_env_file_is_literal_and_does_not_override_process(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text('ROBOFLOW_API_KEY="file-test-value"\nOTHER_VAR=$(anything)\n', encoding="utf-8")
            with patch.dict(os.environ, {"ROBOFLOW_API_KEY": "process-test-value", "ROBOFLOW_MODEL_ID": smoke.MODEL_ID}):
                self.assertEqual(smoke.load_credentials(path), "process-test-value")

    def test_wrong_model_and_missing_key_fail_before_runtime_import(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / ".env"
            with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(ValueError, "Missing key"):
                smoke.load_credentials(missing)
            with patch.dict(os.environ, {"ROBOFLOW_API_KEY": "test-value", "ROBOFLOW_MODEL_ID": "other/model"}, clear=True):
                with self.assertRaisesRegex(ValueError, "Model ID differs"):
                    smoke.load_credentials(missing)

    def test_windows_symlink_compat_callable(self):
        # Verify helper executes safely without errors
        smoke._apply_windows_symlink_compat()
        if os.name == "nt":
            import inference_models.models.auto_loaders.core as core
            self.assertTrue(callable(core.handle_symlink_creation))
            self.assertTrue(callable(core._materialize_package_artifact_identities))

    def test_smoke_does_not_consume_locked_holdout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data"
            data.mkdir()
            videos = root / "assets_test"
            videos.mkdir()
            for name in ("calibration.mp4", "holdout.mp4"):
                (videos / name).write_bytes(b"fixture")
            (data / "manifest.csv").write_text("video_id,relative_path\na,assets_test/calibration.mp4\nb,assets_test/holdout.mp4\n")
            (data / "splits.json").write_text(json.dumps({"status": "locked", "proposed_split": {"test": {"video_ids": ["b"]}}}))
            self.assertEqual([v.name for v in smoke.select_videos(videos, data_dir=data)], ["calibration.mp4"])
            with self.assertRaisesRegex(ValueError, "locked test"):
                smoke.select_videos(videos, ["holdout.mp4"], data_dir=data)

    @unittest.skipUnless(os.name == "nt", "Windows copy compatibility")
    def test_copy_fallback_only_handles_missing_symlink_privilege(self):
        smoke._apply_windows_symlink_compat()
        import inference_models.models.auto_loaders.core as core
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / "blob", Path(directory) / "copy"
            source.write_bytes(b"verified fixture")
            error = OSError("fixture privilege error")
            error.winerror = 1314
            with patch.object(os, "symlink", side_effect=error):
                core.handle_symlink_creation(str(source), str(target))
            self.assertEqual(target.read_bytes(), source.read_bytes())
            with patch.object(os, "symlink", side_effect=FileExistsError("fixture exists")):
                with self.assertRaises(FileExistsError):
                    core.handle_symlink_creation(str(source), str(target))
            self.assertEqual(target.read_bytes(), source.read_bytes())

    @unittest.skipUnless(os.name == "nt", "Windows copy compatibility")
    def test_copy_compat_rejects_corrupt_blob_and_artifact_path_escape(self):
        smoke._apply_windows_symlink_compat()
        import inference_models.models.auto_loaders.core as core
        import inference_models.models.auto_loaders.model_cache_paths as paths
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "package"
            blobs = Path(directory) / "blobs"
            package.mkdir()
            blobs.mkdir()
            expected_md5 = "0" * 32
            (blobs / expected_md5).write_bytes(b"corrupted fixture")
            with patch.object(paths, "generate_shared_blobs_path", return_value=str(blobs)):
                for file_handle in ("weights.onnx", "../escape.onnx"):
                    with self.subTest(file_handle=file_handle), self.assertRaises(core.CorruptedModelPackageError):
                        core._materialize_package_artifact_identities(str(package), [
                            {"file_handle": file_handle, "md5_hash": expected_md5, "storage": "shared_blob"}])


if __name__ == "__main__":
    unittest.main()
