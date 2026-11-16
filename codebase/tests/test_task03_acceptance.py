"""Acceptance regressions: timestamp export, fail-closed artifacts and holdout safety."""
from fractions import Fraction
import io
import json
import logging
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import av
import numpy as np

from test_task03_pipeline import create_synthetic_mp4, DummyFrame
from basketball_scoreboard import app
from basketball_scoreboard.config import PipelineConfig, ExportConfig
from basketball_scoreboard.contracts import DetectionRecord
from basketball_scoreboard.video import VideoReader, VideoWriter


class FakeDetector:
    def __init__(self, *args, **kwargs):
        self.env_path = kwargs.get("env_path")
    def warmup(self):
        return []
    def detect(self, *args):
        return [], 1.0
    def get_runtime_info(self):
        return {"init_s": 0, "class_mapping": {0: "human", 1: "rim", 2: "ball"}}


class Task03AcceptanceTests(unittest.TestCase):
    def test_end_of_stream_duplicate_pts_are_repaired_on_export_clock(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "source.mp4"
            create_synthetic_mp4(video, num_frames=3, width=64, height=48)
            frames = [DummyFrame(1085), DummyFrame(1085), DummyFrame(1086), DummyFrame(1087)]
            # Retain a large origin so the fixture reproduces subtraction epsilon.
            frames.insert(0, DummyFrame(0))
            for frame in frames:
                frame.time_base = Fraction(1, 60)
            with VideoReader(video, pts_policy="repair_with_audit") as reader:
                reader.metadata.fps = 60.0
                with patch.object(reader, "_decode_frames", return_value=iter(frames)):
                    records = [record for record, _ in reader.frames()]
            times = [record.source_time_s for record in records]
            self.assertTrue(all(a < b for a, b in zip(times, times[1:])))
            self.assertEqual([r.timestamp_status for r in records][-3:], ["repaired"] * 3)

    def test_writer_rejects_sub_tick_timestamp_collision(self):
        with tempfile.TemporaryDirectory() as directory:
            with VideoWriter(Path(directory) / "video.mp4", 64, 48, 30) as writer:
                image = np.zeros((48,64,3), dtype=np.uint8)
                writer.write_frame(image, 0.0)
                with self.assertRaises(ValueError):
                    writer.write_frame(image, 1e-15)

    def test_vfr_export_preserves_source_times(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "vfr.mp4"
            source_times = [0.0, 0.04, 0.11, 0.15, 0.23]
            with VideoWriter(video, 64, 48, 30) as writer:
                for timestamp in source_times:
                    writer.write_frame(np.zeros((48, 64, 3), dtype=np.uint8), timestamp)
            with av.open(str(video)) as container:
                decoded_times = [float(frame.pts * frame.time_base) for frame in container.decode(video=0)]
            self.assertEqual(len(decoded_times), len(source_times))
            for actual, expected in zip(decoded_times, source_times):
                self.assertAlmostEqual(actual, expected, places=4)

    def test_reader_uses_frame_timebase_not_a_mutable_stream_clock(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "source.mp4"
            create_synthetic_mp4(video, num_frames=3, width=64, height=48)
            frames = [DummyFrame(0), DummyFrame(100), DummyFrame(200)]
            for frame in frames:
                frame.time_base = Fraction(1, 1000)
            with VideoReader(video, pts_policy="strict_reject") as reader:
                with patch.object(reader, "_decode_frames", return_value=iter(frames)):
                    records = [record for record, _ in reader.frames()]
            self.assertEqual([r.source_time_s for r in records], [0.0, 0.1, 0.2])

    def test_strict_reader_rejects_missing_pts(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "source.mp4"
            create_synthetic_mp4(video, width=64, height=48)
            with VideoReader(video, pts_policy="strict_reject") as reader:
                with patch.object(reader, "_decode_frames", return_value=iter([DummyFrame(None)])):
                    with self.assertRaises(ValueError):
                        list(reader.frames())

    def test_runtime_mapping_can_differ_from_baseline_order(self):
        record = DetectionRecord([0, 0, 10, 10], 0, "human", 0.9, class_mapping={0: "human"})
        self.assertEqual(record.to_dict()["class_name"], "human")
        self.assertNotIn("class_mapping", record.to_dict())

    def test_config_override_and_export_escape_rejected(self):
        config = PipelineConfig.default()
        config.model.max_edge = 1
        with self.assertRaises(ValueError):
            config.validate()
        for filename in ("../run.json", "./run.json"):
            with self.assertRaises(ValueError):
                ExportConfig(run_filename=filename)
        with self.assertRaises(ValueError):
            ExportConfig(detections_filename="run.json")

    def test_model_init_failure_has_safe_failed_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video, output = root / "input.mp4", root / "output"
            create_synthetic_mp4(video, width=64, height=48)
            log = io.StringIO()
            handler = logging.StreamHandler(log)
            app.logger.addHandler(handler)
            try:
                with patch.object(app, "ObjectDetector", side_effect=RuntimeError("secret-fixture api_key=never-print")):
                    with self.assertRaises(RuntimeError):
                        app.run_pipeline(video, output)
            finally:
                app.logger.removeHandler(handler)
            metadata = json.loads((output / "run.json").read_text())
            self.assertEqual(metadata["status"], "failed")
            self.assertNotIn("secret-fixture", (output / "run.json").read_text() + log.getvalue())

    def test_zero_frame_decode_fails_and_explicit_prefix_is_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "input.mp4"
            create_synthetic_mp4(video, num_frames=3, width=64, height=48)
            with patch.object(app, "ObjectDetector", FakeDetector):
                config = PipelineConfig.default()
                config.video.max_frames = 1
                result = app.run_pipeline(video, root / "prefix", config, export_video=False)
                self.assertEqual(result["status"], "partial")
                self.assertEqual(result["class_mapping"][0], "human")
                with patch.object(VideoReader, "_decode_frames", return_value=iter([])):
                    with self.assertRaises(RuntimeError):
                        app.run_pipeline(video, root / "empty", export_video=False)
            self.assertEqual(json.loads((root / "empty/run.json").read_text())["status"], "failed")

    def test_writer_failure_is_not_completed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "input.mp4"
            create_synthetic_mp4(video, num_frames=2, width=64, height=48)
            with patch.object(app, "ObjectDetector", FakeDetector), patch.object(VideoWriter, "write_frame", side_effect=OSError("fixture")):
                with self.assertRaises(RuntimeError):
                    app.run_pipeline(video, root / "failed")
            self.assertEqual(json.loads((root / "failed/run.json").read_text())["status"], "failed")

    def test_renamed_holdout_is_blocked_by_content_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            (root / "data/manifest.csv").write_text("video_id,sha256\nheld,protected-hash\n")
            (root / "data/splits.json").write_text(json.dumps({"proposed_split": {"test": {"video_ids": ["held"]}}}))
            with self.assertRaises(ValueError):
                app.assert_development_video_allowed("protected-hash", root)


if __name__ == "__main__":
    unittest.main()
