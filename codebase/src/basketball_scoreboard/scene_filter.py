"""Automated scene and replay frame filter for continuous basketball stream.

Detects sudden camera whip pans, broadcast graphic transitions, and full-screen replay
overlays, enabling the pipeline to skip or flag corrupted observations automatically.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np


@dataclass
class FilterResult:
    """Decision output for a single video frame."""
    skip: bool
    reason: Optional[str]
    motion_score: float
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skip": self.skip,
            "reason": self.reason,
            "motion_score": round(float(self.motion_score), 4),
            "detail": self.detail,
        }


class SceneFilter:
    """Heuristic frame-by-frame filter for camera motion and replay suppression."""

    def __init__(
        self,
        motion_threshold: float = 35.0,
        min_variance: float = 14.0,
        downscale_wh: Tuple[int, int] = (320, 180),
        max_consecutive_skips: int = 45,
    ) -> None:
        self.motion_threshold = float(motion_threshold)
        self.min_variance = float(min_variance)
        self.downscale_wh = downscale_wh
        self.max_consecutive_skips = int(max_consecutive_skips)

        self._prev_gray: Optional[np.ndarray] = None
        self._total_frames = 0
        self._skipped_frames = 0
        self._skip_reasons: Dict[str, int] = {}
        self._consecutive_skips = 0

    def reset(self) -> None:
        """Reset internal frame history and counters."""
        self._prev_gray = None
        self._consecutive_skips = 0

    def get_summary(self) -> Dict[str, Any]:
        """Return aggregate filter statistics."""
        return {
            "total_inspected": self._total_frames,
            "total_skipped": self._skipped_frames,
            "skip_rate": (
                round(self._skipped_frames / max(1, self._total_frames), 4)
            ),
            "skip_reasons": dict(self._skip_reasons),
        }

    def inspect_frame(
        self,
        bgr_image: np.ndarray,
        pts_s: float,
        frame_index: int = 0,
    ) -> FilterResult:
        """Evaluate if frame should be processed or skipped due to scene anomaly."""
        self._total_frames += 1

        if bgr_image is None or bgr_image.size == 0:
            self._skipped_frames += 1
            self._skip_reasons["empty_frame"] = self._skip_reasons.get("empty_frame", 0) + 1
            return FilterResult(
                skip=True,
                reason="empty_frame",
                motion_score=0.0,
                detail={"frame_index": frame_index, "pts_s": pts_s},
            )

        # Downscale for fast heuristic evaluation (< 0.5 ms)
        small = cv2.resize(bgr_image, self.downscale_wh, interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        overall_var = float(np.var(gray))
        h, w = gray.shape

        # 1. Check solid color / graphic transition
        if overall_var < (self.min_variance ** 2):
            reason = "low_variance_transition"
            return self._record_skip(reason, 0.0, pts_s, frame_index, {"var": round(overall_var, 2)})

        # 2. Check full-screen solid wash (white or black out)
        mean_intensity = float(np.mean(gray))
        if mean_intensity > 248.0 or mean_intensity < 8.0:
            reason = "extreme_exposure"
            return self._record_skip(reason, 0.0, pts_s, frame_index, {"mean": round(mean_intensity, 1)})

        # 3. Check inter-frame camera motion
        motion_score = 0.0
        if self._prev_gray is not None:
            diff = cv2.absdiff(gray, self._prev_gray)
            motion_score = float(np.mean(diff))
            # Compare adjacent frames even after a cut. Holding the old scene
            # would reject an otherwise stable new scene for up to 45 frames.
            self._prev_gray = gray

            # Guard against skipping indefinitely during long panning
            if self._consecutive_skips < self.max_consecutive_skips:
                if motion_score > self.motion_threshold:
                    reason = "whip_pan_or_cut"
                    return self._record_skip(
                        reason,
                        motion_score,
                        pts_s,
                        frame_index,
                        {"mad": round(motion_score, 2)},
                    )

        # Frame passed checks
        self._prev_gray = gray
        self._consecutive_skips = 0
        return FilterResult(
            skip=False,
            reason=None,
            motion_score=motion_score,
            detail={"var": round(overall_var, 2), "pts_s": round(pts_s, 3)},
        )

    def _record_skip(
        self,
        reason: str,
        motion_score: float,
        pts_s: float,
        frame_index: int,
        extra: Dict[str, Any],
    ) -> FilterResult:
        self._skipped_frames += 1
        self._consecutive_skips += 1
        self._skip_reasons[reason] = self._skip_reasons.get(reason, 0) + 1
        detail = {"pts_s": round(pts_s, 3), "frame_index": frame_index}
        detail.update(extra)
        return FilterResult(
            skip=True,
            reason=reason,
            motion_score=motion_score,
            detail=detail,
        )
