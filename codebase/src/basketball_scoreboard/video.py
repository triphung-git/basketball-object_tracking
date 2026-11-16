"""Sequential video reader, PTS normalizer, and export writer."""
from __future__ import annotations

from fractions import Fraction
import hashlib
import logging
import math
import os
from pathlib import Path
from typing import Generator, Iterator, Optional, Tuple

import av
import numpy as np

from .contracts import FrameRecord, VideoMetadata

logger = logging.getLogger(__name__)


def compute_file_sha256(path: Path | str, chunk_size: int = 65536) -> str:
    """Compute standard SHA-256 hex digest of a file in streaming chunks."""
    file_path = Path(path).resolve()
    hasher = hashlib.sha256()
    with file_path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def probe_video(video_path: Path | str) -> VideoMetadata:
    """Inspect stream metadata and determine container properties."""
    path = Path(video_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Video file not found: {path}")

    sha256_hash = compute_file_sha256(path)
    container = av.open(str(path))
    try:
        if not container.streams.video:
            raise ValueError(f"No video streams found in {path}")
        stream = container.streams.video[0]
        width = stream.width
        height = stream.height
        if width is None or height is None or width <= 0 or height <= 0:
            raise ValueError(f"Invalid stream dimensions: {width}x{height}")

        # Determine frame rate
        rate = stream.average_rate or stream.guessed_rate or stream.base_rate
        if rate is None or rate <= 0:
            raise ValueError(f"Could not determine valid frame rate for {path}")
        fps = float(rate)

        # Determine frame count and duration
        nb_frames = stream.frames
        duration_s = float(stream.duration * stream.time_base) if (stream.duration and stream.time_base) else 0.0
        if duration_s <= 0.0 and container.duration:
            duration_s = float(container.duration / av.time_base)
        if (nb_frames is None or nb_frames <= 0) and duration_s > 0:
            nb_frames = max(1, round(duration_s * fps))
        if nb_frames is None or nb_frames <= 0:
            nb_frames = 1

        time_base_str = str(stream.time_base) if stream.time_base else "1/60"

        # Check VFR: difference between base_rate and avg_frame_rate
        base_rate = float(stream.base_rate) if stream.base_rate else fps
        is_vfr = abs(base_rate - fps) > 0.05

        return VideoMetadata(
            video_id=path.stem,
            relative_path=str(path),
            width=width,
            height=height,
            fps=fps,
            nb_frames=nb_frames,
            duration_s=duration_s,
            time_base=time_base_str,
            is_vfr=is_vfr,
            sha256=sha256_hash,
            codec=stream.codec_context.name if stream.codec_context else "h264",
        )
    finally:
        container.close()


class VideoReader:
    """Sequential frame decoder providing normalized presentation timestamps."""

    def __init__(
        self,
        video_path: Path | str,
        pts_policy: str = "repair_with_audit",
        max_frames: Optional[int] = None,
        start_time_s: Optional[float] = None,
    ) -> None:
        self.video_path = Path(video_path).resolve()
        if not self.video_path.is_file():
            raise FileNotFoundError(f"Video file not found: {self.video_path}")
        self.pts_policy = pts_policy
        if pts_policy not in {"strict_reject", "repair_with_audit", "flag_only"}:
            raise ValueError("Unknown PTS policy")
        self.max_frames = max_frames
        self.start_time_s = start_time_s
        self.metadata = probe_video(self.video_path)
        self.container: Optional[av.container.InputContainer] = None
        self._is_closed = False

    def __enter__(self) -> VideoReader:
        self.container = av.open(str(self.video_path))
        self._is_closed = False
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        if not self._is_closed and self.container is not None:
            try:
                self.container.close()
            except Exception:
                pass
            self._is_closed = True

    def _decode_frames(self):
        """Decode frames from video stream. Isolated to facilitate testing."""
        return self.container.decode(video=0)

    def frames(self) -> Iterator[Tuple[FrameRecord, np.ndarray]]:
        """Yield (FrameRecord, BGR ndarray) tuples sequentially."""
        if self.container is None or self._is_closed:
            self.container = av.open(str(self.video_path))
            self._is_closed = False

        stream = self.container.streams.video[0]
        time_base = stream.time_base or Fraction(1, int(round(self.metadata.fps)))
        tb_float = float(time_base)
        fallback_step = 1.0 / self.metadata.fps if self.metadata.fps > 0 else 1.0 / 30.0

        origin_s: Optional[float] = None
        estimated_origin = False
        last_pts_s = -1.0
        frame_index = 0

        for frame in self._decode_frames():
            if self.max_frames is not None and frame_index >= self.max_frames:
                break

            raw_pts = frame.pts
            frame_tb = getattr(frame, "time_base", None) or time_base
            timestamp_status = "valid"

            if raw_pts is not None:
                raw_time_s = float(raw_pts * frame_tb)
                if origin_s is None:
                    origin_s = raw_time_s - (last_pts_s + fallback_step if frame_index else 0.0)
                    estimated_origin = frame_index > 0
                current_pts_s = raw_time_s - origin_s
                if estimated_origin:
                    timestamp_status = "estimated"
            else:
                if self.pts_policy == "strict_reject":
                    raise ValueError(f"Missing PTS at frame {frame_index}")
                current_pts_s = last_pts_s + fallback_step if frame_index else 0.0
                timestamp_status = "estimated"

            # Compare on the serialized/export clock, not floating-point epsilon.
            # Otherwise a 3e-15s increase can become duplicate JSON/MP4 timestamps.
            current_pts_s = round(current_pts_s, 6)
            # Check non-monotonic or duplicate PTS
            if current_pts_s <= last_pts_s:
                if self.pts_policy == "strict_reject":
                    raise ValueError(
                        f"Non-monotonic PTS detected at frame {frame_index}: "
                        f"current {current_pts_s:.6f}s <= previous {last_pts_s:.6f}s"
                    )
                elif self.pts_policy == "repair_with_audit":
                    repaired_pts_s = round(last_pts_s + fallback_step, 6)
                    logger.warning(
                        "Repairing non-monotonic PTS at frame %d: %.6fs -> %.6fs",
                        frame_index,
                        current_pts_s,
                        repaired_pts_s,
                    )
                    current_pts_s = repaired_pts_s
                    timestamp_status = "repaired"
                elif self.pts_policy == "flag_only":
                    timestamp_status = "irregular"

            last_pts_s = current_pts_s

            record = FrameRecord(
                video_id=self.metadata.video_id,
                frame_index=frame_index,
                source_time_s=max(0.0, current_pts_s),
                original_wh=(frame.width, frame.height),
                raw_pts=raw_pts,
                time_base=str(frame_tb),
                timestamp_status=timestamp_status,
                timestamp_policy=self.pts_policy,
            )

            # Keep the original frame index and normalized PTS while skipping
            # expensive image conversion before a requested analysis window.
            if self.start_time_s is not None and current_pts_s < self.start_time_s:
                frame_index += 1
                continue
            # Convert to BGR uint8 numpy array
            bgr_image = frame.to_ndarray(format="bgr24")

            yield record, bgr_image
            frame_index += 1


class VideoWriter:
    """Encoder for writing annotated video with PyAV while preserving timing."""

    def __init__(
        self,
        output_path: Path | str,
        width: int,
        height: int,
        fps: float,
        codec: str = "libx264",
        pix_fmt: str = "yuv420p",
        preset: str = "veryfast",
    ) -> None:
        self.output_path = Path(output_path).resolve()
        if self.output_path.exists():
            raise FileExistsError(f"Refusing to overwrite existing output: {self.output_path}")
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        self.width = width
        self.height = height
        self.fps = fps
        self.codec = codec
        self.pix_fmt = pix_fmt

        self.container = av.open(str(self.output_path), mode="w")
        self.stream = self.container.add_stream(self.codec, rate=Fraction(round(fps * 1000), 1000))
        self.stream.width = width
        self.stream.height = height
        self.stream.pix_fmt = pix_fmt
        self.stream.options = {"preset": preset, "crf": "18"}
        self.export_time_base = Fraction(1, 1000000)
        self.stream.time_base = self.export_time_base
        self.stream.codec_context.time_base = self.export_time_base
        self.last_timestamp_s = -1.0
        self.last_timestamp_tick = -1
        self.frames_written = 0
        self._is_closed = False

    def __enter__(self) -> VideoWriter:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def write_frame(self, bgr_image: np.ndarray, source_time_s: Optional[float] = None) -> None:
        """Encode and mux a single BGR frame."""
        if self._is_closed:
            raise RuntimeError("Cannot write to closed VideoWriter")
        h, w = bgr_image.shape[:2]
        if w != self.width or h != self.height:
            raise ValueError(
                f"Image shape ({w}x{h}) does not match writer dimensions ({self.width}x{self.height})"
            )

        video_frame = av.VideoFrame.from_ndarray(bgr_image, format="bgr24")
        timestamp = self.frames_written / self.fps if source_time_s is None else source_time_s
        if not math.isfinite(timestamp) or timestamp < 0 or timestamp <= self.last_timestamp_s:
            raise ValueError("Export timestamps must be finite, non-negative and strictly increasing")
        timestamp_tick = round(timestamp / float(self.export_time_base))
        if timestamp_tick <= self.last_timestamp_tick:
            raise ValueError("Export timestamps collide at the configured timebase precision")
        video_frame.pts = timestamp_tick
        video_frame.time_base = self.export_time_base
        for packet in self.stream.encode(video_frame):
            self.container.mux(packet)
        self.last_timestamp_s = timestamp
        self.last_timestamp_tick = timestamp_tick
        self.frames_written += 1

    def close(self) -> None:
        """Flush encoder packets, write trailer, and close container."""
        if not self._is_closed:
            try:
                # Flush remaining buffered packets
                for packet in self.stream.encode(None):
                    self.container.mux(packet)
            except Exception as e:
                logger.error("Error closing VideoWriter: %s", e)
                raise
            finally:
                self.container.close()
                self._is_closed = True
