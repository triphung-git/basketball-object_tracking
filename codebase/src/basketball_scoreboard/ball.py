"""Causal single-ball tracking in image coordinates; no model or GT access."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from .tracking_policy import in_image_roi


@dataclass(frozen=True)
class BallConfig:
    min_confidence: float = 0.25
    ambiguity_margin: float = 0.08
    prediction_horizon_s: float = 0.15
    max_gap_s: float = 0.30
    base_gate_diagonal: float = 0.05
    max_speed_diagonal_s: float = 2.0
    velocity_smoothing: float = 0.5
    max_diameter_diagonal: float = 0.08
    human_context_weight: float = 0.0
    max_initial_body_distance: float = 1.0
    actor_continuity_weight: float = 0.0
    actor_continuity_gate_heights: float = 0.45

    def __post_init__(self):
        for key, value in asdict(self).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 or (value == 0 and key not in {'human_context_weight', 'actor_continuity_weight'}):
                raise ValueError(f"Invalid ball config: {key}")
        if max(self.min_confidence, self.ambiguity_margin, self.velocity_smoothing) > 1:
            raise ValueError("Ball probabilities/weights must not exceed one")
        if self.prediction_horizon_s > self.max_gap_s:
            raise ValueError("Prediction horizon exceeds ball gap limit")
        if self.actor_continuity_weight > 1:
            raise ValueError('Actor continuity weight must not exceed one')


def center(box):
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def iou(a, b):
    overlap = max(0., min(a[2], b[2]) - max(a[0], b[0])) * max(0., min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - overlap
    return overlap / union if union > 0 else 0.


class BallTracker:
    """Confidence/kinematics baseline. Prediction never counts as observation."""

    def __init__(self, original_wh, namespace, config=None):
        if len(original_wh) != 2 or any(isinstance(x, bool) or not isinstance(x, int) or x <= 0 for x in original_wh):
            raise ValueError("Ball tracker requires positive integer dimensions")
        if not namespace:
            raise ValueError("Ball namespace required")
        self.width, self.height = original_wh
        self.diagonal = math.hypot(*original_wh)
        self.namespace = namespace
        self.config = config or BallConfig()
        self.last_time = -1.
        self.segment = None
        self.counter = 0
        self.active = None

    def reset(self):
        self.active = None

    def update(self, frame_index, time_s, detections, segment="default", reset=False, clock_valid=True, human_boxes=(),ball_roi=None,
               human_observations=()):
        if isinstance(frame_index, bool) or not isinstance(frame_index, int) or frame_index < 0:
            raise ValueError("Invalid ball frame index")
        if not math.isfinite(time_s) or time_s < 0 or time_s <= self.last_time:
            raise ValueError("Ball timestamps must strictly increase")
        reset_reason = None
        if reset or (self.segment is not None and segment != self.segment):
            reset_reason = "explicit_or_segment_reset"
        elif self.last_time >= 0 and time_s - self.last_time > self.config.max_gap_s:
            reset_reason = "coverage_gap"
        if reset_reason or not clock_valid:
            self.reset()
        self.last_time, self.segment = time_s, segment
        if self.active and time_s - self.active["time"] > self.config.max_gap_s:
            self.reset()
            reset_reason = reset_reason or "ball_stale"
        base = dict(schema_version="2.1.0", observation_id=f"{self.namespace}:ball_obs:{frame_index}",
                    frame_index=frame_index, source_time_s=time_s, segment_id=segment,
                    ball_track_id=None, sample_type="missing", xyxy=None, center_image=None,
                    confidence=None, reason="no_ball_observation", reset_reason=reset_reason,
                    evidence_refs=[], candidate_count=0,context_actor_count=len(human_boxes),spatially_rejected_candidates=0)
        if not clock_valid:
            return {**base, "reason": "untrusted_clock"}
        candidates = []
        for index, detection in enumerate(detections):
            if detection.get("class_name") != "ball":
                continue
            box, confidence = detection["xyxy"], detection["confidence"]
            if len(box) != 4 or not all(math.isfinite(x) for x in box) or not math.isfinite(confidence):
                raise ValueError("Nonfinite ball detection")
            if not (0 <= box[0] < box[2] <= self.width and 0 <= box[1] < box[3] <= self.height and 0 <= confidence <= 1):
                raise ValueError("Invalid ball detection bounds/confidence")
            if ball_roi is not None and not in_image_roi({'image_roi_normalized':ball_roi},center(box),(self.width,self.height)):
                base['spatially_rejected_candidates']+=1
                continue
            if confidence >= self.config.min_confidence and max(box[2]-box[0],box[3]-box[1]) <= self.config.max_diameter_diagonal*self.diagonal:
                candidates.append((float(confidence), tuple(box), index))
        candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
        unique = []
        for item in candidates:
            if not any(iou(item[1], old[1]) >= 0.95 for old in unique):
                unique.append(item)
        base["candidate_count"] = len(unique)
        ranked = []
        predicted = None
        players, actor_expected = {}, None
        if self.config.actor_continuity_weight:
            from .ball_actor_context import current_players, actor_prediction
            players = current_players(human_observations, frame_index, time_s)
            actor_expected = actor_prediction(self.active.get('actor_anchor') if self.active else None, players)
        if self.active:
            elapsed = time_s - self.active["time"]
            p = center(self.active["box"])
            predicted = (p[0] + self.active["velocity"][0]*elapsed,
                         p[1] + self.active["velocity"][1]*elapsed)
            gate = self.diagonal * (self.config.base_gate_diagonal + self.config.max_speed_diagonal_s * elapsed)
        for confidence, box, index in unique:
            score = confidence
            context_score=0.
            if self.config.human_context_weight:
                bx,by=center(box)
                distances=[math.hypot(max(p[0]-bx,0.,bx-p[2]),max(p[1]-by,0.,by-p[3]))/(p[3]-p[1]) for p in human_boxes]
                distance=min(distances,default=float('inf'))
                if not self.active and distance>self.config.max_initial_body_distance:
                    continue
                context_score=self.config.human_context_weight*max(0.,1-distance/self.config.max_initial_body_distance)
            if self.active:
                distance = math.dist(center(box), predicted)
                old_box = self.active["box"]
                ratio = ((box[2]-box[0])*(box[3]-box[1])) / ((old_box[2]-old_box[0])*(old_box[3]-old_box[1]))
                if distance > gate or not .2 <= ratio <= 5.:
                    continue
                score = .65 * (1 - distance / gate) + .35 * confidence
            score += context_score
            # A cue changes candidate ranking only. It cannot create a detection,
            # bypass the image ROI/size/motion gates, or force a possession.
            if actor_expected:
                actor_distance = math.dist(center(box), actor_expected[:2]) / actor_expected[2]
                score += self.config.actor_continuity_weight * max(0., 1. - actor_distance / self.config.actor_continuity_gate_heights)
            ranked.append((score, confidence, box, index))
        ranked.sort(key=lambda x: (-x[0], x[2], x[3]))
        ambiguous = len(ranked) > 1 and ranked[0][0] - ranked[1][0] < self.config.ambiguity_margin
        if ranked and not ambiguous:
            score, confidence, box, index = ranked[0]
            velocity = (0., 0.)
            if self.active:
                old_center = center(self.active["box"])
                new_center = center(box)
                elapsed = time_s - self.active["time"]
                alpha = self.config.velocity_smoothing
                velocity = tuple(alpha * (new_center[i]-old_center[i])/elapsed +
                                 (1-alpha)*self.active["velocity"][i] for i in (0, 1))
                track_id = self.active["id"]
            else:
                self.counter += 1
                track_id = f"{self.namespace}:ball_track:{self.counter}"
            self.active = dict(id=track_id, box=box, velocity=velocity, time=time_s)
            if self.config.actor_continuity_weight:
                from .ball_actor_context import actor_anchor
                self.active['actor_anchor'] = actor_anchor(box, players)
            return {**base, "ball_track_id": track_id, "sample_type": "observed", "xyxy": list(box),
                    "center_image": list(center(box)), "confidence": confidence,
                    "association_score": score, "score_kind": "heuristic_not_probability",
                    "reason": "observed_association", "evidence_refs": [f"detection:{frame_index}:{index}"]}
        reason = "ambiguous_ball_candidates" if ambiguous else "no_gated_ball_observation"
        if self.active and time_s - self.active["time"] <= self.config.prediction_horizon_s:
            if (0 <= predicted[0] <= self.width and 0 <= predicted[1] <= self.height and
                    (ball_roi is None or in_image_roi({'image_roi_normalized':ball_roi},predicted,(self.width,self.height)))):
                return {**base, "ball_track_id": self.active["id"], "sample_type": "predicted",
                        "center_image": list(predicted), "reason": reason}
        return {**base, "reason": reason}
