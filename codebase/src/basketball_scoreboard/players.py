"""Player tracking with a damped constant-velocity predictor and explicit lifecycle (v2)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np
from scipy.optimize import linear_sum_assignment

from .court import (
    CourtModel,
    TrajectoryObservation,
    estimate_footpoint,
)


class TrackerError(Exception):
    """Base error for tracker lifecycle and association."""
    pass


@dataclass
class TrackState:
    """Internal kinematic and lifecycle state of an active entity track."""
    track_id: str
    video_id: str
    segment_id: str
    camera_id: str
    # Bounding box in [x1, y1, x2, y2]
    bbox: List[float]
    # Center velocity [vx, vy, vw, vh] in px/sec
    velocity: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    last_time_s: float = 0.0
    first_time_s: float = 0.0
    hits: int = 1
    misses: int = 0
    status: str = "tentative"  # "tentative", "active", "lost", "retired"
    role: str = "unknown"  # "player", "non_player", "unknown"
    confidence: float = 1.0
    last_observed_time_s: float = 0.0
    history_length: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "track_id": self.track_id,
            "video_id": self.video_id,
            "segment_id": self.segment_id,
            "camera_id": self.camera_id,
            "bbox": [round(float(v), 2) for v in self.bbox],
            "velocity": [round(float(v), 2) for v in self.velocity],
            "last_time_s": round(self.last_time_s, 6),
            "first_time_s": round(self.first_time_s, 6),
            "hits": self.hits,
            "misses": self.misses,
            "status": self.status,
            "role": self.role,
            "confidence": round(self.confidence, 4),
        }


def compute_iou(bbox1: List[float], bbox2: List[float]) -> float:
    """Calculate Intersection over Union (IoU) between two bounding boxes [x1, y1, x2, y2]."""
    x1 = max(bbox1[0], bbox2[0])
    y1 = max(bbox1[1], bbox2[1])
    x2 = min(bbox1[2], bbox2[2])
    y2 = min(bbox1[3], bbox2[3])

    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter_area = inter_w * inter_h

    area1 = max(0.0, bbox1[2] - bbox1[0]) * max(0.0, bbox1[3] - bbox1[1])
    area2 = max(0.0, bbox2[2] - bbox2[0]) * max(0.0, bbox2[3] - bbox2[1])

    union_area = area1 + area2 - inter_area
    if union_area <= 0.0:
        return 0.0
    return float(inter_area / union_area)


def compute_center_distance(bbox1: List[float], bbox2: List[float]) -> float:
    """Calculate Euclidean distance between centers of two bounding boxes."""
    c1_x = (bbox1[0] + bbox1[2]) / 2.0
    c1_y = (bbox1[1] + bbox1[3]) / 2.0
    c2_x = (bbox2[0] + bbox2[2]) / 2.0
    c2_y = (bbox2[1] + bbox2[3]) / 2.0
    return math.hypot(c2_x - c1_x, c2_y - c1_y)


class PlayerTracker:
    """
    Kinematic spatial tracker for human detections on court.
    
    Handles:
    1. VFR timestamps: kinematic velocity and stale timeouts use true delta time (seconds).
    2. Occlusion and crossing association via Hungarian matching on IoU + distance.
    3. Lifecycle states: tentative -> active -> lost -> retired.
    4. Distinguishing observed detections vs predicted positions.
    5. Court ROI spatial role filtering (player vs non-player).
    """

    def __init__(
        self,
        video_id: str,
        segment_id: str = "default",
        camera_id: str = "cam_01",
        court_model: Optional[CourtModel] = None,
        min_hits_to_activate: int = 3,
        max_age_s: float = 1.0,
        iou_threshold: float = 0.25,
        max_center_dist_px: float = 300.0,
        original_wh: Tuple[int,int] = (3840,2160),
    ) -> None:
        self.video_id = str(video_id)
        self.segment_id = court_model.config.segment_id if court_model else str(segment_id)
        self.camera_id = court_model.config.camera_id if court_model else str(camera_id)
        self.court_model = court_model
        self.min_hits_to_activate = int(min_hits_to_activate)
        self.max_age_s = float(max_age_s)
        self.iou_threshold = float(iou_threshold)
        self.max_center_dist_px = float(max_center_dist_px)
        self.original_wh = court_model.config.original_image_wh if court_model else original_wh
        if (min_hits_to_activate < 1 or not math.isfinite(max_age_s) or max_age_s <= 0
                or not 0 <= iou_threshold <= 1 or not math.isfinite(max_center_dist_px) or max_center_dist_px <= 0):
            raise ValueError("Invalid tracker configuration")

        self._next_track_number = 1
        self.tracks: Dict[str, TrackState] = {}
        self.retired_tracks: List[TrackState] = []
        self._last_processed_time_s: Optional[float] = None

    def reset(self, new_segment_id: Optional[str] = None) -> None:
        """Reset all active tracks (e.g. on scene cut, camera motion, or segment change)."""
        for t in self.tracks.values():
            t.status = "retired"
            self.retired_tracks.append(t)
        self.tracks.clear()
        if new_segment_id:
            self.segment_id = new_segment_id
            if self.court_model and new_segment_id != self.court_model.config.segment_id:
                self.court_model = None
        self._last_processed_time_s = None

    def _generate_track_id(self) -> str:
        tid = f"trk_{self.segment_id}_{self._next_track_number:04d}"
        self._next_track_number += 1
        return tid

    def _determine_role(self, footpoint_image: Tuple[float, float], evidence: Optional[str] = None) -> str:
        """Classify entity role based on court ROI containment."""
        if self.court_model is None:
            return "unknown"
        if not self.court_model.config.court_roi_image:
            return "unknown"
        if self.court_model.is_in_court_roi(footpoint_image):
            return "player" if evidence else "unknown"
        return "non_player"

    def _predict_track_bbox(self, track: TrackState, dt: float) -> List[float]:
        """Extrapolate bounding box using constant-velocity model."""
        if dt <= 0.0 or track.misses > 2:
            return list(track.bbox)
        # Bbox: [x1, y1, x2, y2]
        vx, vy, vw, vh = track.velocity
        x1, y1, x2, y2 = track.bbox
        w = x2 - x1
        h = y2 - y1
        cx = (x1 + x2) / 2.0 + vx * dt
        cy = (y1 + y2) / 2.0 + vy * dt
        nw = max(10.0, w + vw * dt)
        nh = max(10.0, h + vh * dt)
        return [cx - nw / 2.0, cy - nh / 2.0, cx + nw / 2.0, cy + nh / 2.0]

    def update_frame(
        self,
        frame_index: int,
        source_time_s: float,
        timestamp_status: str,
        detections: List[Dict[str, Any]],
        source_fingerprint_sha256: str = "unknown_hash",
        source_run_id: str = "unknown_run",
    ) -> List[TrajectoryObservation]:
        """
        Process a single frame of human detections and update tracker state.
        
        Returns:
            List of TrajectoryObservation records for active tracks in this frame.
        """
        dt = 0.0
        if not math.isfinite(source_time_s) or source_time_s < 0 or frame_index < 0:
            raise ValueError("Invalid frame timestamp/index")
        if self._last_processed_time_s is not None:
            dt = source_time_s - self._last_processed_time_s
            if dt <= 0.0:
                raise ValueError("Duplicate/out-of-order frame; reset or replay a new tracker")
        self._last_processed_time_s = source_time_s

        # 1. Filter human detections
        human_dets: List[Dict[str, Any]] = []
        for d in detections:
            c_name = d.get("class_name")
            c_id = d.get("class_id")
            if c_name != "human":
                continue
            box = d.get("xyxy",[])
            confidence = float(d.get("confidence",1.0))
            if (len(box) != 4 or not all(math.isfinite(v) for v in box)
                    or box[2] <= box[0] or box[3] <= box[1] or not math.isfinite(confidence) or not 0 <= confidence <= 1):
                raise ValueError("Invalid human detection")
            human_dets.append(d)
        deduplicated = []
        for det in sorted(human_dets,key=lambda d: d.get("confidence",1.0),reverse=True):
            if not any(compute_iou(det['xyxy'],other['xyxy']) >= .95 for other in deduplicated):
                deduplicated.append(det)
        human_dets = deduplicated
        for tid, track in list(self.tracks.items()):
            if source_time_s - track.last_observed_time_s > self.max_age_s:
                track.status = "retired"
                self.retired_tracks.append(track)
                del self.tracks[tid]

        # 2. Predict positions of existing tracks
        active_track_ids = list(self.tracks.keys())
        predicted_bboxes: Dict[str, List[float]] = {}
        for tid in active_track_ids:
            track = self.tracks[tid]
            predicted_bboxes[tid] = self._predict_track_bbox(track, dt)

        # 3. Association via Hungarian matching
        n_tracks = len(active_track_ids)
        n_dets = len(human_dets)

        matched_tracks: Dict[str, int] = {}
        matched_dets: Set[int] = set()

        if n_tracks > 0 and n_dets > 0:
            cost_matrix = np.zeros((n_tracks, n_dets), dtype=np.float64)
            for i, tid in enumerate(active_track_ids):
                p_bbox = predicted_bboxes[tid]
                for j, det in enumerate(human_dets):
                    d_bbox = det["xyxy"]
                    iou = compute_iou(p_bbox, d_bbox)
                    dist = compute_center_distance(p_bbox, d_bbox)

                    if iou < self.iou_threshold and dist > self.max_center_dist_px:
                        cost_matrix[i, j] = 1e5  # Gating
                    else:
                        # Cost: weighted combination of 1-iou and normalized distance
                        cost_matrix[i, j] = (1.0 - iou) + (dist / 1000.0)

            row_ind, col_ind = linear_sum_assignment(cost_matrix)
            for r, c in zip(row_ind, col_ind):
                if cost_matrix[r, c] < 1e4:
                    tid = active_track_ids[r]
                    matched_tracks[tid] = c
                    matched_dets.add(c)

        frame_observations: List[TrajectoryObservation] = []

        # 4. Update matched tracks
        for tid, det_idx in matched_tracks.items():
            track = self.tracks[tid]
            det = human_dets[det_idx]
            new_bbox = det["xyxy"]
            conf = float(det.get("confidence", 1.0))

            # Update velocity
            if dt > 0.0:
                old_cx = (track.bbox[0] + track.bbox[2]) / 2.0
                old_cy = (track.bbox[1] + track.bbox[3]) / 2.0
                new_cx = (new_bbox[0] + new_bbox[2]) / 2.0
                new_cy = (new_bbox[1] + new_bbox[3]) / 2.0
                vx = (new_cx - old_cx) / dt
                vy = (new_cy - old_cy) / dt
                # Damped velocity update
                track.velocity = [
                    0.7 * track.velocity[0] + 0.3 * vx,
                    0.7 * track.velocity[1] + 0.3 * vy,
                    0.0, 0.0
                ]

            track.bbox = list(new_bbox)
            track.last_time_s = source_time_s
            track.last_observed_time_s = source_time_s
            track.hits += 1
            track.misses = 0
            track.confidence = conf
            track.history_length += 1

            if track.status == "tentative" and track.hits >= self.min_hits_to_activate:
                track.status = "active"
            elif track.status == "lost":
                track.status = "active"

            # Determine role and footpoint
            orig_wh = self.original_wh
            footpoint, foot_status, foot_reason = estimate_footpoint(new_bbox, orig_wh)
            track.role = self._determine_role(footpoint,det.get("role_evidence") if det.get("role") == "player" else None)

            # Generate observation
            obs_id = f"obs_{frame_index:06d}_{track.track_id}"
            if self.court_model:
                obs = self.court_model.process_detection(
                    bbox=new_bbox,
                    frame_index=frame_index,
                    source_time_s=source_time_s,
                    timestamp_status=timestamp_status,
                    video_id=self.video_id,
                    source_fingerprint_sha256=source_fingerprint_sha256,
                    source_run_id=source_run_id,
                    observation_id=obs_id,
                    track_id=track.track_id,
                    role=track.role,
                    sample_type="observed",
                    confidence=conf,
                )
            else:
                obs = TrajectoryObservation(
                    schema_version="2.0.0",
                    observation_id=obs_id,
                    source_run_id=source_run_id,
                    video_id=self.video_id,
                    source_fingerprint_sha256=source_fingerprint_sha256,
                    frame_index=frame_index,
                    source_time_s=source_time_s,
                    timestamp_status=timestamp_status,
                    segment_id=self.segment_id,
                    camera_id=self.camera_id,
                    bbox=new_bbox,
                    footpoint_image=footpoint,
                    validity_status=foot_status,
                    validity_reason=foot_reason,
                    track_id=track.track_id,
                    role=track.role,
                    sample_type="observed",
                    confidence=conf,
                )
            frame_observations.append(obs)

        # 5. Handle unmatched tracks (missed / occlusion)
        unmatched_track_ids = [tid for tid in active_track_ids if tid not in matched_tracks]
        for tid in unmatched_track_ids:
            track = self.tracks[tid]
            track.misses += 1
            track.last_time_s = source_time_s
            track.status = "lost"

            # Check stale timeout
            time_since_observed = source_time_s - track.last_observed_time_s
            if time_since_observed > self.max_age_s:
                track.status = "retired"
                self.retired_tracks.append(track)
                del self.tracks[tid]
                continue

            # Extrapolate position as predicted
            pred_bbox = predicted_bboxes[tid]
            track.bbox = pred_bbox
            orig_wh = self.original_wh
            footpoint, _, _ = estimate_footpoint(pred_bbox, orig_wh)

            obs_id = f"obs_{frame_index:06d}_{track.track_id}_pred"
            # Explicitly mark as predicted/interpolated (never mixed with observed ground truth)
            obs = TrajectoryObservation(
                schema_version="2.0.0",
                observation_id=obs_id,
                source_run_id=source_run_id,
                video_id=self.video_id,
                source_fingerprint_sha256=source_fingerprint_sha256,
                frame_index=frame_index,
                source_time_s=source_time_s,
                timestamp_status=timestamp_status,
                segment_id=self.segment_id,
                camera_id=self.camera_id,
                bbox=pred_bbox,
                footpoint_image=footpoint,
                validity_status="predicted_occluded",
                validity_reason="Detector missed entity; position extrapolated by kinematic tracker",
                track_id=track.track_id,
                role=track.role,
                sample_type="predicted",
                confidence=0.5 * track.confidence,
            )
            frame_observations.append(obs)

        # 6. Initiate new tentative tracks from unmatched detections
        for det_idx, det in enumerate(human_dets):
            if det_idx in matched_dets:
                continue
            new_bbox = det["xyxy"]
            conf = float(det.get("confidence", 1.0))
            new_tid = self._generate_track_id()

            orig_wh = self.original_wh
            footpoint, foot_status, foot_reason = estimate_footpoint(new_bbox, orig_wh)
            role = self._determine_role(footpoint,det.get("role_evidence") if det.get("role") == "player" else None)

            new_track = TrackState(
                track_id=new_tid,
                video_id=self.video_id,
                segment_id=self.segment_id,
                camera_id=self.camera_id,
                bbox=list(new_bbox),
                last_time_s=source_time_s,
                first_time_s=source_time_s,
                last_observed_time_s=source_time_s,
                hits=1,
                misses=0,
                status="tentative" if self.min_hits_to_activate > 1 else "active",
                role=role,
                confidence=conf,
            )
            self.tracks[new_tid] = new_track

            obs_id = f"obs_{frame_index:06d}_{new_tid}"
            if self.court_model:
                obs = self.court_model.process_detection(
                    bbox=new_bbox,
                    frame_index=frame_index,
                    source_time_s=source_time_s,
                    timestamp_status=timestamp_status,
                    video_id=self.video_id,
                    source_fingerprint_sha256=source_fingerprint_sha256,
                    source_run_id=source_run_id,
                    observation_id=obs_id,
                    track_id=new_tid,
                    role=role,
                    sample_type="observed",
                    confidence=conf,
                )
            else:
                obs = TrajectoryObservation(
                    schema_version="2.0.0",
                    observation_id=obs_id,
                    source_run_id=source_run_id,
                    video_id=self.video_id,
                    source_fingerprint_sha256=source_fingerprint_sha256,
                    frame_index=frame_index,
                    source_time_s=source_time_s,
                    timestamp_status=timestamp_status,
                    segment_id=self.segment_id,
                    camera_id=self.camera_id,
                    bbox=new_bbox,
                    footpoint_image=footpoint,
                    validity_status=foot_status,
                    validity_reason=foot_reason,
                    track_id=new_tid,
                    role=role,
                    sample_type="observed",
                    confidence=conf,
                )
            frame_observations.append(obs)

        return frame_observations
