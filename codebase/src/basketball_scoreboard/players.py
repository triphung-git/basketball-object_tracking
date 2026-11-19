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
    appearance_team_votes: Dict[str, int] = field(default_factory=dict)

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


def compute_match_cost(
    track_bbox: List[float],
    det_bbox: List[float],
    iou_thresh: float = 0.20,
    max_center_dist_px: float = 300.0,
) -> float:
    """Calculate matching cost between track prediction and detection."""
    iou = compute_iou(track_bbox, det_bbox)
    # Scale-dependent center distance check:
    w1, h1 = track_bbox[2] - track_bbox[0], track_bbox[3] - track_bbox[1]
    w2, h2 = det_bbox[2] - det_bbox[0], det_bbox[3] - det_bbox[1]
    scale = max(h1, h2, w1, w2, 10.0)
    dist = compute_center_distance(track_bbox, det_bbox)
    if (dist > min(max_center_dist_px, 1.2 * scale)
            or max(h1, h2) / max(min(h1, h2), 1.0) > 2.5
            or max(w1, w2) / max(min(w1, w2), 1.0) > 2.5):
        return 1e5
    if iou >= iou_thresh:
        return 1.0 - iou

    # Allow distance-based association if there is partial overlap (iou > 0.05)
    # or center distance is very close relative to person size:
    if (iou > 0.05 and dist <= max_center_dist_px) or (dist <= min(max_center_dist_px, scale * 0.65)):
        return (1.0 - iou) + (dist / 1000.0)

    return 1e5


class PlayerTracker:
    """
    Kinematic tracker with two-stage association inspired by ByteTrack.
    
    Handles:
    1. VFR timestamps: kinematic velocity and stale timeouts use true delta time (seconds).
    2. Candidate spatial qualification: on-court candidates prioritized; off-court crowd/bench filtered.
    3. Two-stage association: high-confidence matching followed by low-confidence recovery.
    4. Occlusion and crossing association with scale-aware gating.
    5. Lifecycle states: tentative -> active -> lost -> retired.
    6. Camera cut detection and graceful tracking reset across scene changes.
    7. Clear separation between observed detections and predicted positions.
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
        original_wh: Tuple[int, int] = (3840, 2160),
        high_det_thresh: float = 0.50,
        low_det_thresh: float = 0.20,
        court_buffer_m: Tuple[float, float] = (1.2, 1.2),
        auto_scene_cut: bool = False,
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
        self.high_det_thresh = float(high_det_thresh)
        self.low_det_thresh = float(low_det_thresh)
        self.court_buffer_m = court_buffer_m
        self.auto_scene_cut = auto_scene_cut
        if (not all(math.isfinite(v) for v in (self.low_det_thresh, self.high_det_thresh))
                or not 0 <= self.low_det_thresh <= self.high_det_thresh <= 1
                or len(court_buffer_m) != 2
                or not all(math.isfinite(v) and v >= 0 for v in court_buffer_m)):
            raise ValueError("Invalid detection thresholds/court buffer")
        if (min_hits_to_activate < 1 or not math.isfinite(max_age_s) or max_age_s <= 0
                or not 0 <= iou_threshold <= 1 or not math.isfinite(max_center_dist_px) or max_center_dist_px <= 0):
            raise ValueError("Invalid tracker configuration")

        self._next_track_number = 1
        self.tracks: Dict[str, TrackState] = {}
        self.retired_tracks: List[TrackState] = []
        self._last_processed_time_s: Optional[float] = None
        self._prev_det_count: Optional[int] = None
        self._prev_avg_h: Optional[float] = None
        self.scene_cuts: List[float] = []
        self._requires_court_rebind = False

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
        self._prev_det_count = None
        self._prev_avg_h = None

    def _generate_track_id(self) -> str:
        tid = f"trk_{self.segment_id}_{self._next_track_number:04d}"
        self._next_track_number += 1
        return tid

    def _association_cost(self, track, predicted_bbox, detection):
        votes = track.appearance_team_votes
        observed = detection.get('appearance_team_id')
        if votes and observed:
            team = max(votes, key=votes.get)
            if votes[team] >= 3 and votes[team]/sum(votes.values()) >= .8 and observed != team:
                return 1e5
        return compute_match_cost(predicted_bbox, detection['xyxy'], self.iou_threshold, self.max_center_dist_px)

    def is_on_court_candidate(
        self,
        bbox: List[float],
        is_initialization: bool = False,
    ) -> Tuple[bool, str, Optional[Tuple[float, float]]]:
        """Check if detection bbox is in playing area or court buffer zone."""
        orig_w, orig_h = self.original_wh
        x1, y1, x2, y2 = bbox
        if self._requires_court_rebind:
            return False, "camera_calibration_scope_ended", None
        touches_bottom = (y2 >= orig_h - 6.0)

        # Bottom boundary touch: reject for new track initialization
        if is_initialization and touches_bottom:
            return False, "touch_bottom_rejected_for_init", None

        footpoint, foot_status, foot_reason = estimate_footpoint(bbox, self.original_wh)

        if self.court_model is not None and getattr(self.court_model, "is_calibrated", False):
            proj = self.court_model.project_image_to_court(footpoint)
            if proj is None:
                return False, "degenerate_projection", None
            bounds = self.court_model.config.court_coordinate_system.court_bounds
            x_min, x_max = bounds["x_min"], bounds["x_max"]
            y_min, y_max = bounds["y_min"], bounds["y_max"]
            # The configured margin is in meters, never normalized court units.
            units = self.court_model.config.court_coordinate_system.units
            factor = 1.0 if units == "meters" else 3.280839895 if units == "feet" else 0.0
            buf_x, buf_y = (v * factor for v in self.court_buffer_m) if not is_initialization else (0.0, 0.0)
            roi = self.court_model.config.court_roi_image
            if roi and not self.court_model.is_in_court_roi(footpoint):
                if is_initialization or factor == 0:
                    return False, "outside_court_roi", None
                import cv2
                projected_roi = [self.court_model.project_image_to_court(p) for p in roi]
                if any(p is None for p in projected_roi) or cv2.pointPolygonTest(
                        np.asarray(projected_roi, dtype=np.float32), tuple(map(float, proj)), True) < -max(buf_x, buf_y):
                    return False, "outside_court_roi_buffer", None

            in_candidate_zone = (
                (x_min - buf_x <= proj[0] <= x_max + buf_x) and
                (y_min - buf_y <= proj[1] <= y_max + buf_y)
            )
            if not in_candidate_zone:
                return False, "outside_court_buffer", proj
            return True, "court_candidate", proj

        # Fallback for uncalibrated / test mode:
        return True, "valid_uncalibrated_candidate", None

    def _detect_camera_cut(
        self,
        human_dets: List[Dict[str, Any]],
        source_time_s: float,
    ) -> bool:
        """Detect sudden camera cuts/transitions between close-up and wide camera."""
        if not self.auto_scene_cut:
            return False
        if not human_dets:
            self._prev_det_count = 0
            self._prev_avg_h = None
            return False
        current_count = len(human_dets)
        current_avg_h = float(np.mean([d["xyxy"][3] - d["xyxy"][1] for d in human_dets]))
        is_cut = False
        if self._prev_det_count is not None and self._prev_avg_h is not None:
            h_ratio = current_avg_h / max(self._prev_avg_h, 1.0)
            if (h_ratio > 2.0 or h_ratio < 0.5) and (abs(current_count - self._prev_det_count) >= 2 or current_avg_h > 450.0 or self._prev_avg_h > 450.0):
                is_cut = True
        self._prev_det_count = current_count
        self._prev_avg_h = current_avg_h
        return is_cut

    def _determine_role(self, footpoint_image: Tuple[float, float], evidence: Optional[str] = None, on_court: bool = True) -> str:
        """Classify entity role based on court ROI containment and evidence."""
        if evidence in {"player", "referee", "non_player"}:
            return evidence
        if self.court_model is None:
            return "player" if evidence and on_court else "unknown" if on_court else "non_player"
        if not self.court_model.config.court_roi_image:
            return "player" if evidence and on_court else "unknown" if on_court else "non_player"
        if self.court_model.is_in_court_roi(footpoint_image) and on_court:
            return "player" if evidence else "unknown"
        return "non_player"

    def _predict_track_bbox(self, track: TrackState, dt: float) -> List[float]:
        """Extrapolate bounding box using damped constant-velocity model."""
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
            if c_name != "human":
                continue
            box = d.get("xyxy", [])
            confidence = float(d.get("confidence", 1.0))
            if (len(box) != 4 or not all(math.isfinite(v) for v in box)
                    or box[2] <= box[0] or box[3] <= box[1] or not math.isfinite(confidence) or not 0 <= confidence <= 1):
                raise ValueError("Invalid human detection")
            human_dets.append(d)
        deduplicated = []
        for det in sorted(human_dets, key=lambda d: d.get("confidence", 1.0), reverse=True):
            if not any(compute_iou(det['xyxy'], other['xyxy']) >= .95 for other in deduplicated):
                deduplicated.append(det)
        human_dets = deduplicated

        # Automatic scene cut check
        if self._detect_camera_cut(human_dets, source_time_s):
            had_court = self.court_model is not None
            self.reset(new_segment_id=f"cut_{int(source_time_s*1000):06d}")
            self._requires_court_rebind = had_court or self._requires_court_rebind
            self.scene_cuts.append(source_time_s)
            self._last_processed_time_s = source_time_s
            dt = 0.0

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

        # 3. Categorize detections into candidate on-court vs off-court
        cand_dets: List[Dict[str, Any]] = []
        for det in human_dets:
            on_court, reason, proj = self.is_on_court_candidate(det["xyxy"], is_initialization=False)
            det_copy = dict(det)
            det_copy["_on_court"] = on_court
            det_copy["_proj"] = proj
            if on_court:
                cand_dets.append(det_copy)

        # High-confidence vs Low-confidence detections
        high_dets = [d for d in cand_dets if float(d.get("confidence", 1.0)) >= self.high_det_thresh]
        low_dets = [d for d in cand_dets if self.low_det_thresh <= float(d.get("confidence", 1.0)) < self.high_det_thresh]

        matched_tracks: Dict[str, Dict[str, Any]] = {}
        matched_high_dets: Set[int] = set()

        # Stage 1: Associate active tracks with high-confidence detections
        if active_track_ids and high_dets:
            cost_matrix = np.zeros((len(active_track_ids), len(high_dets)), dtype=np.float64)
            for i, tid in enumerate(active_track_ids):
                p_bbox = predicted_bboxes[tid]
                for j, det in enumerate(high_dets):
                    cost_matrix[i, j] = self._association_cost(self.tracks[tid], p_bbox, det)

            row_ind, col_ind = linear_sum_assignment(cost_matrix)
            for r, c in zip(row_ind, col_ind):
                if cost_matrix[r, c] < 1e4:
                    tid = active_track_ids[r]
                    matched_tracks[tid] = high_dets[c]
                    matched_high_dets.add(c)

        # Stage 2: Associate remaining tracks with low-confidence detections
        unmatched_track_ids_stage1 = [tid for tid in active_track_ids if tid not in matched_tracks
                                      and self.tracks[tid].hits >= self.min_hits_to_activate]
        matched_low_dets: Set[int] = set()
        if unmatched_track_ids_stage1 and low_dets:
            cost_matrix_low = np.zeros((len(unmatched_track_ids_stage1), len(low_dets)), dtype=np.float64)
            for i, tid in enumerate(unmatched_track_ids_stage1):
                p_bbox = predicted_bboxes[tid]
                for j, det in enumerate(low_dets):
                    cost_matrix_low[i, j] = self._association_cost(self.tracks[tid], p_bbox, det)

            row_ind, col_ind = linear_sum_assignment(cost_matrix_low)
            for r, c in zip(row_ind, col_ind):
                if cost_matrix_low[r, c] < 1e4:
                    tid = unmatched_track_ids_stage1[r]
                    matched_tracks[tid] = low_dets[c]
                    matched_low_dets.add(c)

        frame_observations: List[TrajectoryObservation] = []

        # 4. Update matched tracks
        for tid, det in matched_tracks.items():
            track = self.tracks[tid]
            if det.get('appearance_team_id'):
                team = det['appearance_team_id']
                track.appearance_team_votes[team] = track.appearance_team_votes.get(team, 0)+1
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
                track.status = "active" if track.hits >= self.min_hits_to_activate else "tentative"

            # Determine role and footpoint
            orig_wh = self.original_wh
            footpoint, foot_status, foot_reason = estimate_footpoint(new_bbox, orig_wh)
            on_court = det.get("_on_court", True)
            track.role = self._determine_role(footpoint, det.get("role_evidence") if det.get("role") == "player" else det.get("role"), on_court=on_court)

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

            # Prune tentative tracks that miss more than 1 frame without confirmation:
            if track.hits < self.min_hits_to_activate:
                track.status = "retired"
                self.retired_tracks.append(track)
                del self.tracks[tid]
                continue

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

        # 6. Initiate new tracks from unmatched high-confidence detections
        for det_idx, det in enumerate(high_dets):
            if det_idx in matched_high_dets:
                continue
            new_bbox = det["xyxy"]
            conf = float(det.get("confidence", 1.0))

            # Qualification check for track initialization:
            is_cand, reason, proj = self.is_on_court_candidate(new_bbox, is_initialization=True)
            if not is_cand:
                continue

            new_tid = self._generate_track_id()
            orig_wh = self.original_wh
            footpoint, foot_status, foot_reason = estimate_footpoint(new_bbox, orig_wh)
            role = self._determine_role(footpoint, det.get("role_evidence") if det.get("role") == "player" else det.get("role"), on_court=True)

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
            if det.get('appearance_team_id'):
                new_track.appearance_team_votes[det['appearance_team_id']] = 1

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
