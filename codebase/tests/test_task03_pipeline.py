"""Comprehensive tests for Task03 video reader, contracts, config, overlays, and pipeline."""
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import av
import numpy as np

# Add src to path
CODEBASE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = CODEBASE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from basketball_scoreboard.config import ModelConfig, PipelineConfig, VideoConfig
from basketball_scoreboard.contracts import (
    CLASS_MAPPING,
    DetectionRecord,
    FrameDetectionsRecord,
    FrameRecord,
    VideoMetadata,
)
from basketball_scoreboard.overlay import draw_detections_overlay
from basketball_scoreboard.video import VideoReader, VideoWriter, compute_file_sha256, probe_video


def create_synthetic_mp4(
    path: Path,
    num_frames: int = 5,
    width: int = 120,
    height: int = 80,
    fps: int = 30,
) -> None:
    """Helper to generate a lightweight MP4 file with controlled frames and PTS."""
    container = av.open(str(path), mode="w")
    try:
        stream = container.add_stream("libx264", rate=Fraction(fps, 1))
        stream.width = width
        stream.height = height
        stream.pix_fmt = "yuv420p"

        for i in range(num_frames):
            color = (i * 40 % 255, 100, 200)
            img = np.full((height, width, 3), color, dtype=np.uint8)
            frame = av.VideoFrame.from_ndarray(img, format="bgr24")
            frame.pts = i
            for packet in stream.encode(frame):
                container.mux(packet)

        for packet in stream.encode(None):
            container.mux(packet)
    finally:
        container.close()


class DummyFrame:
    """Mock frame to test exact PTS edge cases in VideoReader."""
    def __init__(self, pts: int | None, width: int = 64, height: int = 48) -> None:
        self.pts = pts
        self.width = width
        self.height = height

    def to_ndarray(self, format: str = "bgr24") -> np.ndarray:
        return np.zeros((self.height, self.width, 3), dtype=np.uint8)


class TestContracts(unittest.TestCase):
    def test_valid_detection_record(self):
        det = DetectionRecord(xyxy=[10.5, 20.0, 100.0, 200.0], class_id=0, class_name="ball", confidence=0.88)
        self.assertEqual(det.class_name, "ball")
        self.assertEqual(det.class_id, 0)
        self.assertEqual(det.confidence, 0.88)
        det.validate_bounds((300, 300))

    def test_detection_record_rejects_reversed_or_degenerate_bbox(self):
        with self.assertRaises(ValueError):
            DetectionRecord(xyxy=[100.0, 20.0, 10.0, 200.0], class_id=0, class_name="ball", confidence=0.5)
        with self.assertRaises(ValueError):
            DetectionRecord(xyxy=[10.0, 200.0, 100.0, 20.0], class_id=0, class_name="ball", confidence=0.5)
        with self.assertRaises(ValueError):
            DetectionRecord(xyxy=[50.0, 50.0, 50.0, 100.0], class_id=0, class_name="ball", confidence=0.5)

    def test_detection_record_rejects_bounds_overflow(self):
        det = DetectionRecord(xyxy=[10.0, 20.0, 350.0, 200.0], class_id=1, class_name="human", confidence=0.9)
        with self.assertRaises(ValueError):
            det.validate_bounds((300, 300))

    def test_detection_record_rejects_class_name_mismatch(self):
        with self.assertRaises(ValueError):
            DetectionRecord(xyxy=[10.0, 20.0, 100.0, 200.0], class_id=0, class_name="human", confidence=0.9)

    def test_detection_record_rejects_invalid_confidence_or_nan(self):
        with self.assertRaises(ValueError):
            DetectionRecord(xyxy=[10.0, 20.0, 100.0, 200.0], class_id=2, class_name="rim", confidence=1.5)
        with self.assertRaises(ValueError):
            DetectionRecord(xyxy=[10.0, 20.0, float("nan"), 200.0], class_id=2, class_name="rim", confidence=0.5)

    def test_frame_record_validation(self):
        record = FrameRecord(video_id="clip01", frame_index=0, source_time_s=0.0, original_wh=(1920, 1080))
        self.assertEqual(record.video_id, "clip01")
        self.assertEqual(record.timestamp_status, "valid")

        with self.assertRaises(ValueError):
            FrameRecord(video_id="", frame_index=0, source_time_s=0.0, original_wh=(1920, 1080))
        with self.assertRaises(ValueError):
            FrameRecord(video_id="clip01", frame_index=-1, source_time_s=0.0, original_wh=(1920, 1080))
        with self.assertRaises(ValueError):
            FrameRecord(video_id="clip01", frame_index=0, source_time_s=-0.5, original_wh=(1920, 1080))
        with self.assertRaises(ValueError):
            FrameRecord(video_id="clip01", frame_index=0, source_time_s=0.0, original_wh=(0, 1080))

    def test_frame_detections_record_jsonl_serialization(self):
        det = DetectionRecord(xyxy=[10.0, 20.0, 50.0, 60.0], class_id=0, class_name="ball", confidence=0.95)
        f_record = FrameDetectionsRecord(
            video_id="test_vid",
            frame_index=5,
            source_time_s=0.166667,
            original_wh=(640, 480),
            detections=[det],
            raw_pts=5,
            time_base="1/30",
            model_call_ms=12.345,
        )
        line = f_record.to_jsonl()
        parsed = json.loads(line)
        self.assertEqual(parsed["frame_index"], 5)
        self.assertEqual(len(parsed["detections"]), 1)
        self.assertEqual(parsed["detections"][0]["class_name"], "ball")

    def test_empty_detections_record(self):
        f_record = FrameDetectionsRecord(
            video_id="test_vid",
            frame_index=0,
            source_time_s=0.0,
            original_wh=(640, 480),
            detections=[],
        )
        data = f_record.to_dict()
        self.assertEqual(data["detections"], [])


class TestConfig(unittest.TestCase):
    def test_default_config(self):
        cfg = PipelineConfig.default()
        self.assertEqual(cfg.model.model_id, "phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1")
        self.assertEqual(cfg.model.confidence_threshold, 0.25)
        self.assertEqual(cfg.video.pts_policy, "repair_with_audit")

    def test_reject_unapproved_model(self):
        with self.assertRaises(ValueError):
            ModelConfig(model_id="other/model")

    def test_reject_invalid_confidence_or_edge(self):
        with self.assertRaises(ValueError):
            ModelConfig(confidence_threshold=0.0)
        with self.assertRaises(ValueError):
            ModelConfig(confidence_threshold=1.5)
        with self.assertRaises(ValueError):
            ModelConfig(max_edge=100)

    def test_reject_invalid_pts_policy(self):
        with self.assertRaises(ValueError):
            VideoConfig(pts_policy="magic_clock")

    def test_load_from_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.yaml"
            path.write_text("model:\n  confidence_threshold: 0.35\nvideo:\n  pts_policy: strict_reject\n", encoding="utf-8")
            cfg = PipelineConfig.from_yaml(path)
            self.assertEqual(cfg.model.confidence_threshold, 0.35)
            self.assertEqual(cfg.video.pts_policy, "strict_reject")


class TestVideoReaderAndWriter(unittest.TestCase):
    def test_cfr_video_reading(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "cfr.mp4"
            create_synthetic_mp4(video_path, num_frames=6, width=120, height=80, fps=30)

            # Probe
            metadata = probe_video(video_path)
            self.assertEqual(metadata.width, 120)
            self.assertEqual(metadata.height, 80)
            self.assertEqual(metadata.fps, 30.0)
            self.assertEqual(metadata.nb_frames, 6)
            self.assertFalse(metadata.is_vfr)

            # Read sequentially
            frames_read = 0
            with VideoReader(video_path) as reader:
                prev_time = -1.0
                for record, bgr_img in reader.frames():
                    self.assertEqual(record.frame_index, frames_read)
                    self.assertGreater(record.source_time_s, prev_time)
                    self.assertEqual(record.original_wh, (120, 80))
                    self.assertEqual(bgr_img.shape, (80, 120, 3))
                    prev_time = record.source_time_s
                    frames_read += 1
            self.assertEqual(frames_read, 6)

    def test_max_frames_truncation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "cfr.mp4"
            create_synthetic_mp4(video_path, num_frames=8, width=120, height=80, fps=30)
            with VideoReader(video_path, max_frames=3) as reader:
                count = sum(1 for _ in reader.frames())
            self.assertEqual(count, 3)

    def test_non_monotonic_pts_strict_reject(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "cfr.mp4"
            create_synthetic_mp4(video_path, num_frames=4, width=64, height=48, fps=30)
            with VideoReader(video_path, pts_policy="strict_reject") as reader:
                mock_frames = [DummyFrame(0), DummyFrame(2), DummyFrame(1)]
                with patch.object(reader, "_decode_frames", return_value=iter(mock_frames)):
                    with self.assertRaises(ValueError):
                        list(reader.frames())

    def test_non_monotonic_pts_repair(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "cfr.mp4"
            create_synthetic_mp4(video_path, num_frames=4, width=64, height=48, fps=30)
            with VideoReader(video_path, pts_policy="repair_with_audit") as reader:
                mock_frames = [DummyFrame(0), DummyFrame(2), DummyFrame(1), DummyFrame(3)]
                with patch.object(reader, "_decode_frames", return_value=iter(mock_frames)):
                    records = [r for r, _ in reader.frames()]
            self.assertEqual(len(records), 4)
            self.assertEqual(records[2].timestamp_status, "repaired")
            times = [r.source_time_s for r in records]
            self.assertTrue(all(t2 > t1 for t1, t2 in zip(times, times[1:])))

    def test_non_monotonic_pts_flag_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "cfr.mp4"
            create_synthetic_mp4(video_path, num_frames=3, width=64, height=48, fps=30)
            with VideoReader(video_path, pts_policy="flag_only") as reader:
                mock_frames = [DummyFrame(0), DummyFrame(2), DummyFrame(1)]
                with patch.object(reader, "_decode_frames", return_value=iter(mock_frames)):
                    records = [r for r, _ in reader.frames()]
            self.assertEqual(records[2].timestamp_status, "irregular")

    def test_missing_pts_estimated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "cfr.mp4"
            create_synthetic_mp4(video_path, num_frames=3, width=64, height=48, fps=30)
            with VideoReader(video_path) as reader:
                mock_frames = [DummyFrame(None), DummyFrame(None)]
                with patch.object(reader, "_decode_frames", return_value=iter(mock_frames)):
                    records = [r for r, _ in reader.frames()]
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0].timestamp_status, "estimated")
            self.assertEqual(records[1].timestamp_status, "estimated")

    def test_video_writer_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "out.mp4"
            with VideoWriter(out_path, width=100, height=100, fps=25.0) as writer:
                img = np.zeros((100, 100, 3), dtype=np.uint8)
                writer.write_frame(img)
                writer.write_frame(img)
            self.assertTrue(out_path.is_file())
            self.assertGreater(out_path.stat().st_size, 0)

            # Refuse overwrite
            with self.assertRaises(FileExistsError):
                VideoWriter(out_path, width=100, height=100, fps=25.0)

    def test_video_writer_rejects_dimension_mismatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "mismatch.mp4"
            with VideoWriter(out_path, width=100, height=100, fps=25.0) as writer:
                bad_img = np.zeros((80, 120, 3), dtype=np.uint8)
                with self.assertRaises(ValueError):
                    writer.write_frame(bad_img)


class TestOverlay(unittest.TestCase):
    def test_draw_detections_and_telemetry(self):
        img = np.zeros((200, 300, 3), dtype=np.uint8)
        det1 = DetectionRecord(xyxy=[10.0, 10.0, 50.0, 50.0], class_id=0, class_name="ball", confidence=0.85)
        det2 = DetectionRecord(xyxy=[60.0, 60.0, 150.0, 180.0], class_id=1, class_name="human", confidence=0.92)
        f_rec = FrameRecord(video_id="demo", frame_index=1, source_time_s=0.033333, original_wh=(300, 200))

        annotated = draw_detections_overlay(img, [det1, det2], f_rec)
        self.assertEqual(annotated.shape, img.shape)
        self.assertGreater(annotated.sum(), 0)

    def test_empty_detections_overlay(self):
        img = np.zeros((200, 300, 3), dtype=np.uint8)
        f_rec = FrameRecord(video_id="demo", frame_index=0, source_time_s=0.0, original_wh=(300, 200))
        annotated = draw_detections_overlay(img, [], f_rec)
        self.assertEqual(annotated.shape, img.shape)


if __name__ == "__main__":
    unittest.main()
