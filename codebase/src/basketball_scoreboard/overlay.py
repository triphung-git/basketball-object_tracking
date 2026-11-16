"""Visual overlay renderer for detection bounding boxes and frame telemetry."""
from __future__ import annotations

from typing import List, Optional, Tuple

import cv2
import numpy as np

from .contracts import DetectionRecord, FrameRecord

# Distinct BGR color palette
CLASS_COLORS = {
    "ball": (0, 200, 255),   # Amber / Orange-Yellow
    "rim": (255, 180, 0),    # Cyan / Sky Blue
    "human": (0, 220, 0),    # Bright Green
}
DEFAULT_COLOR = (200, 200, 200)


def draw_detections_overlay(
    bgr_frame: np.ndarray,
    detections: List[DetectionRecord],
    frame_record: Optional[FrameRecord] = None,
    line_thickness: int = 2,
    font_scale: float = 0.5,
    show_telemetry: bool = True,
) -> np.ndarray:
    """Render bounding boxes, class labels, confidence scores, and telemetry on a frame."""
    canvas = bgr_frame.copy()
    height, width = canvas.shape[:2]

    # Draw bounding boxes
    for det in detections:
        color = CLASS_COLORS.get(det.class_name, DEFAULT_COLOR)
        x1, y1, x2, y2 = det.xyxy
        ix1 = int(round(max(0, min(width - 1, x1))))
        iy1 = int(round(max(0, min(height - 1, y1))))
        ix2 = int(round(max(0, min(width - 1, x2))))
        iy2 = int(round(max(0, min(height - 1, y2))))

        cv2.rectangle(canvas, (ix1, iy1), (ix2, iy2), color, line_thickness)

        label = f"{det.class_name} {det.confidence:.2f}"
        (text_w, text_h), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1
        )

        label_y1 = max(0, iy1 - text_h - 6)
        label_y2 = label_y1 + text_h + 6
        label_x2 = min(width, ix1 + text_w + 6)

        # Background tag behind text for readability
        cv2.rectangle(canvas, (ix1, label_y1), (label_x2, label_y2), (20, 20, 20), -1)
        cv2.putText(
            canvas,
            label,
            (ix1 + 3, label_y2 - baseline - 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            color,
            1,
            cv2.LINE_AA,
        )

    # Telemetry badge
    if show_telemetry and frame_record is not None:
        status_suffix = f" [{frame_record.timestamp_status}]" if frame_record.timestamp_status != "valid" else ""
        telemetry_text = f"Frame {frame_record.frame_index:05d} | PTS: {frame_record.source_time_s:06.2f}s{status_suffix} | Detections: {len(detections)}"
        (tw, th), tbase = cv2.getTextSize(
            telemetry_text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1
        )
        badge_x1, badge_y1 = 12, 12
        badge_x2, badge_y2 = badge_x1 + tw + 14, badge_y1 + th + 14

        overlay_crop = canvas[badge_y1:badge_y2, badge_x1:badge_x2]
        dark_bg = np.zeros_like(overlay_crop)
        cv2.addWeighted(overlay_crop, 0.3, dark_bg, 0.7, 0, overlay_crop)
        canvas[badge_y1:badge_y2, badge_x1:badge_x2] = overlay_crop

        cv2.rectangle(canvas, (badge_x1, badge_y1), (badge_x2, badge_y2), (60, 60, 60), 1)
        cv2.putText(
            canvas,
            telemetry_text,
            (badge_x1 + 7, badge_y2 - tbase - 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (240, 240, 240),
            1,
            cv2.LINE_AA,
        )

    return canvas
