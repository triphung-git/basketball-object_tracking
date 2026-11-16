"""Temporal shot recognition, FSM trajectory tracking, and rim crossing confirmation (v2).

This module implements the 4-phase finite state machine:
  READY -> RELEASE -> FLIGHT_ARC -> OUTCOME (BASKET | REBOUND/MISS)
with safety states UNRESOLVED, ABORTED, and RESET.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import math
from typing import Any, Dict, List, Optional, Set, Tuple


class ShotPhase(str, Enum):
    """Phases of a basketball shot trajectory."""
    READY = "ready"
    RELEASE = "release"
    FLIGHT_ARC = "flight_arc"
    BASKET = "basket"
    MISS = "miss"
    ABORTED = "aborted"
    RESET = "reset"


class AttributionLevel(str, Enum):
    """Level of confidence in shot attribution."""
    PLAYER = "player"
    TEAM = "team"
    UNKNOWN = "unknown"


@dataclass
class RimApertureGeometry:
    """Geometric definition and aperture bands of a detected basketball rim.

    In 2D camera coordinates (where y grows downward):
      - y_top: upper entry plane (above rim level)
      - y_center: rim ring center level
      - y_bottom: lower exit plane (below rim level / upper net)
    """
    xyxy: List[float]
    confidence: float
    frame_index: int
    source_time_s: float

    def __post_init__(self) -> None:
        if len(self.xyxy) != 4 or any(not math.isfinite(v) for v in self.xyxy):
            raise ValueError(f"Invalid rim coordinates: {self.xyxy}")
        x1, y1, x2, y2 = self.xyxy
        if x2 <= x1 or y2 <= y1:
            raise ValueError(f"Degenerate rim bbox: {self.xyxy}")

    @property
    def width(self) -> float:
        return self.xyxy[2] - self.xyxy[0]

    @property
    def height(self) -> float:
        return self.xyxy[3] - self.xyxy[1]

    @property
    def center(self) -> Tuple[float, float]:
        return (
            (self.xyxy[0] + self.xyxy[2]) / 2.0,
            (self.xyxy[1] + self.xyxy[3]) / 2.0,
        )

    @property
    def aperture_x_bounds(self) -> Tuple[float, float]:
        """Horizontal extent of the entry aperture (with small margin)."""
        c_x = self.center[0]
        half_w = self.width * 0.45
        return (c_x - half_w, c_x + half_w)

    @property
    def entry_band_y(self) -> Tuple[float, float]:
        """Upper entry band: just above to top of rim ring."""
        c_y = self.center[1]
        h = self.height
        return (c_y - h * 0.8, c_y - h * 0.1)

    @property
    def exit_band_y(self) -> Tuple[float, float]:
        """Lower exit band: through and below rim ring (net entry zone)."""
        c_y = self.center[1]
        h = self.height
        return (c_y + h * 0.4, c_y + h * 1.5)


@dataclass
class ShotCandidateRecord:
    """Formal data contract for a temporal shot sequence candidate."""
    shot_id: str
    video_id: str
    segment_id: str
    camera_id: str
    status: str  # "candidate", "provisional", "auto_confirmed", "void", "unresolved"
    outcome: str  # "made", "miss", "unresolved"
    phase: ShotPhase
    release_time_s: Optional[float] = None
    release_frame_idx: Optional[int] = None
    outcome_time_s: Optional[float] = None
    outcome_frame_idx: Optional[int] = None
    confirmation_time_s: Optional[float] = None
    shooter_track_id: Optional[str] = None
    shooter_player_id: Optional[str] = None
    shooter_team_id: Optional[str] = None
    attribution_level: AttributionLevel = AttributionLevel.UNKNOWN
    point_value: Optional[int] = None
    evidence_details: Dict[str, Any] = field(default_factory=dict)
    reason_codes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["phase"] = self.phase.value
        data["attribution_level"] = self.attribution_level.value
        return data


@dataclass
class ShotEngineConfig:
    """Tunable configuration parameters for the Temporal Shot Engine."""
    # Release detection
    min_release_ball_speed_px_s: float = 80.0
    max_actor_distance_for_release: float = 180.0
    min_release_ascent_angle_deg: float = 15.0  # Angle above horizontal

    # Flight arc
    max_flight_gap_seconds: float = 0.35  # Max allowable continuous prediction bridge
    max_flight_duration_seconds: float = 2.8  # Typical basketball flight is 1.0 - 2.2s
    min_flight_duration_seconds: float = 0.35

    # Rim interaction & Crossing
    rim_proximity_px: float = 250.0
    min_crossing_observed_samples: int = 1  # At least 1 observed sample near rim
    require_downward_motion: bool = True
    min_downward_velocity_px_s: float = 30.0
    min_ball_confidence: float = 0.15

    # Net / Deceleration Cue
    enable_net_cue: bool = True
    net_deceleration_min_ratio: float = 0.65  # Speed after crossing <= 0.65 of entry speed
    net_cue_weight: float = 0.3

    # Idempotency & Cooldown
    shot_cooldown_seconds: float = 2.0  # Min time between distinct physical shots
    replay_suppression_enabled: bool = True


class TemporalShotFSM:
    """Four-phase finite state machine for basketball shot recognition.

    Lifecycle:
      1. READY: Ball in player control / near body.
      2. RELEASE: Ball separates upward toward rim with increasing velocity.
      3. FLIGHT_ARC: Ball travels through air toward target basket.
      4. OUTCOME:
           - BASKET: Ball passes downward through rim aperture band.
           - MISS: Ball contacts rim / backboard and deflects away without passing through aperture.
           - ABORTED: Trajectory interrupted by scene cut, timeout, or ambiguity.
    """

    def __init__(
        self,
        config: Optional[ShotEngineConfig] = None,
        video_id: str = "video",
        camera_id: str = "cam_main",
    ) -> None:
        self.config = config or ShotEngineConfig()
        self.video_id = video_id
        self.camera_id = camera_id

        self.current_phase: ShotPhase = ShotPhase.READY
        self.current_shot_id: Optional[str] = None
        self.shot_counter: int = 0

        # Trajectory buffer
        self.ball_trajectory: List[Dict[str, Any]] = []
        self.rim_samples: List[RimApertureGeometry] = []
        self.actor_candidates: List[Dict[str, Any]] = []

        # State timestamps
        self.ready_time_s: Optional[float] = None
        self.release_time_s: Optional[float] = None
        self.release_frame_idx: Optional[int] = None
        self.flight_start_s: Optional[float] = None
        self.last_confirmed_shot_time_s: Optional[float] = None
        self.last_observed_ball_time_s: Optional[float] = None
        self.last_observed_ball_center: Optional[List[float]] = None
        self.last_processed_frame_idx: Optional[int] = None
        self.last_processed_time_s: Optional[float] = None

        # Confirmed outputs
        self.confirmed_shots: List[ShotCandidateRecord] = []
        self.all_candidates: List[ShotCandidateRecord] = []

    def reset(self, reason: str = "manual_reset") -> None:
        """Reset state machine upon scene cut or explicit boundary."""
        if self.current_phase in {ShotPhase.RELEASE, ShotPhase.FLIGHT_ARC}:
            # Log aborted candidate if was in-flight
            self._record_candidate(
                status="void",
                outcome="unresolved",
                phase=ShotPhase.ABORTED,
                reason=f"Aborted: {reason}",
            )
        self.current_phase = ShotPhase.READY
        self.current_shot_id = None
        self.ball_trajectory.clear()
        self.rim_samples.clear()
        self.actor_candidates.clear()
        self.ready_time_s = None
        self.release_time_s = None
        self.release_frame_idx = None
        self.flight_start_s = None
        self.last_observed_ball_time_s = None
        self.last_observed_ball_center = None
        self.last_processed_frame_idx = None
        self.last_processed_time_s = None

    def step(
        self,
        frame_idx: int,
        source_time_s: float,
        ball_obs: Optional[Dict[str, Any]],
        rim_detections: List[Dict[str, Any]],
        player_observations: List[Dict[str, Any]],
        is_camera_cut: bool = False,
        camera_layout_invalid: bool = False,
    ) -> Optional[ShotCandidateRecord]:
        """Update FSM state for a single frame.

        Returns a ShotCandidateRecord if a shot reaches an OUTCOME phase in this frame.
        """
        if is_camera_cut:
            self.reset(reason="camera_cut_detected")
            return None

        if camera_layout_invalid:
            # Special case: camera closeup / follow-shot (e.g. play_006)
            # Maintain ready state but abstain from false trigger
            return None

        # Guard against duplicate frames / inverted timestamps
        if self.last_processed_frame_idx is not None and frame_idx == self.last_processed_frame_idx:
            return None
        if self.last_processed_time_s is not None and source_time_s < self.last_processed_time_s:
            self.reset(reason="timestamp_discontinuity_reversed")
            return None

        self.last_processed_frame_idx = frame_idx
        self.last_processed_time_s = source_time_s

        # 1. Update rim geometry
        cur_rim: Optional[RimApertureGeometry] = None
        if rim_detections:
            best_rim = max(rim_detections, key=lambda d: d.get("confidence", 0.0))
            if best_rim.get("confidence", 0.0) >= 0.2:
                cur_rim = RimApertureGeometry(
                    xyxy=best_rim["xyxy"],
                    confidence=best_rim["confidence"],
                    frame_index=frame_idx,
                    source_time_s=source_time_s,
                )
                self.rim_samples.append(cur_rim)
                # Keep last 60 rim samples (~2.0s)
                if len(self.rim_samples) > 60:
                    self.rim_samples.pop(0)

        # 2. Determine observation status & update ball observation history
        is_real_obs = (
            ball_obs is not None
            and ball_obs.get("sample_type") == "observed"
            and (ball_obs.get("center_image") is not None or ball_obs.get("center") is not None or ball_obs.get("xyxy") is not None)
            and (ball_obs.get("confidence") is None or ball_obs.get("confidence") >= self.config.min_ball_confidence)
        )

        # Enforce observation gap in FLIGHT_ARC against the last genuine observation
        if self.current_phase == ShotPhase.FLIGHT_ARC:
            last_obs_t = self.last_observed_ball_time_s if self.last_observed_ball_time_s is not None else self.release_time_s
            if last_obs_t is not None:
                gap_s = source_time_s - last_obs_t
                if gap_s > self.config.max_flight_gap_seconds:
                    rec = self._record_candidate(
                        status="unresolved",
                        outcome="unresolved",
                        phase=ShotPhase.ABORTED,
                        reason="ball_observation_gap_exceeded",
                    )
                    self.reset(reason="flight_gap_exceeded")
                    return rec

        if is_real_obs:
            self.last_observed_ball_time_s = source_time_s
            b_center = ball_obs.get("center_image") or ball_obs.get("center")
            if not b_center and ball_obs.get("xyxy"):
                b_center = [(ball_obs["xyxy"][0] + ball_obs["xyxy"][2]) / 2.0, (ball_obs["xyxy"][1] + ball_obs["xyxy"][3]) / 2.0]
            self.last_observed_ball_center = b_center

        if ball_obs:
            self.ball_trajectory.append({
                "frame_index": frame_idx,
                "source_time_s": source_time_s,
                "sample_type": ball_obs.get("sample_type", "missing"),
                "confidence": ball_obs.get("confidence"),
                "xyxy": ball_obs.get("xyxy"),
                "center": ball_obs.get("center_image") or (
                    [(ball_obs["xyxy"][0] + ball_obs["xyxy"][2]) / 2.0,
                     (ball_obs["xyxy"][1] + ball_obs["xyxy"][3]) / 2.0]
                    if ball_obs.get("xyxy") else None
                ),
                "track_id": ball_obs.get("track_id"),
            })
            if len(self.ball_trajectory) > 90:  # ~3 seconds buffer
                self.ball_trajectory.pop(0)

        # 3. Check cooldown
        if self.last_confirmed_shot_time_s is not None:
            if source_time_s - self.last_confirmed_shot_time_s < self.config.shot_cooldown_seconds:
                return None

        # 4. State transitions
        if self.current_phase == ShotPhase.READY:
            return self._handle_ready(frame_idx, source_time_s, ball_obs, player_observations, cur_rim)

        elif self.current_phase == ShotPhase.RELEASE:
            return self._handle_release(frame_idx, source_time_s, ball_obs, cur_rim)

        elif self.current_phase == ShotPhase.FLIGHT_ARC:
            return self._handle_flight_arc(frame_idx, source_time_s, ball_obs, cur_rim)

        return None

    def _handle_ready(
        self,
        frame_idx: int,
        source_time_s: float,
        ball_obs: Optional[Dict[str, Any]],
        player_observations: List[Dict[str, Any]],
        cur_rim: Optional[RimApertureGeometry],
    ) -> Optional[ShotCandidateRecord]:
        """READY phase: monitor ball-actor proximity and detect upward separation."""
        if not ball_obs or ball_obs.get("sample_type") != "observed" or not ball_obs.get("center_image"):
            return None

        b_c = ball_obs["center_image"]
        target_rim = cur_rim or (self.rim_samples[-1] if self.rim_samples else None)
        if target_rim and math.dist(b_c, target_rim.center) < 160.0:
            return None

        # Find closest player
        closest_player = None
        min_dist = float("inf")
        for p in player_observations:
            if p.get("sample_type") == "observed" and p.get("role") != "non_player":
                p_c = [
                    (p["bbox"][0] + p["bbox"][2]) / 2.0,
                    (p["bbox"][1] + p["bbox"][3]) / 2.0,
                ]
                d = math.dist(b_c, p_c)
                if d < min_dist:
                    min_dist = d
                    closest_player = p

        if closest_player and min_dist <= self.config.max_actor_distance_for_release:
            p_box = closest_player["bbox"]
            p_h = p_box[3] - p_box[1]
            # Ball must be at or above lower torso (prevents floor bounce of dribble)
            if b_c[1] <= p_box[3] - p_h * 0.2:
                self.actor_candidates.append({
                    "frame_index": frame_idx,
                    "source_time_s": source_time_s,
                    "player": closest_player,
                    "dist": min_dist,
                })
                if len(self.actor_candidates) > 30:
                    self.actor_candidates.pop(0)

        # Check for separation from player (Release onset)
        if len(self.ball_trajectory) >= 3 and len(self.actor_candidates) >= 2:
            vel = self._compute_recent_ball_velocity()
            if vel is not None:
                vx, vy, speed = vel
                # In image coordinates, vy < -60 px/s is upward shot motion
                if vy < -60.0 and speed >= 100.0:
                    # Potential release detected
                    self.shot_counter += 1
                    self.current_shot_id = f"shot_{self.video_id}_{self.shot_counter:04d}"
                    self.current_phase = ShotPhase.RELEASE
                    self.release_time_s = source_time_s
                    self.release_frame_idx = frame_idx
                    self.flight_start_s = source_time_s
                    self.last_observed_ball_time_s = source_time_s
                    self.last_observed_ball_center = b_c

        return None

    def _handle_release(
        self,
        frame_idx: int,
        source_time_s: float,
        ball_obs: Optional[Dict[str, Any]],
        cur_rim: Optional[RimApertureGeometry],
    ) -> Optional[ShotCandidateRecord]:
        """RELEASE phase: evaluate motion continuity and confirm transition to FLIGHT_ARC."""
        if not ball_obs:
            # Short gap allowance at release
            if source_time_s - (self.release_time_s or source_time_s) > 0.4:
                self.reset(reason="ball_lost_immediately_after_release")
            return None

        vel = self._compute_recent_ball_velocity()
        if vel is not None:
            vx, vy, speed = vel
            b_c = ball_obs.get("center_image") or ball_obs.get("center")
            dist_to_rim = math.dist(b_c, cur_rim.center) if (b_c and cur_rim) else float("inf")
            if vy < 0 or dist_to_rim < 500:
                self.current_phase = ShotPhase.FLIGHT_ARC
                return None

        # Timeout if stuck in release
        if source_time_s - (self.release_time_s or source_time_s) > 0.6:
            self.current_phase = ShotPhase.FLIGHT_ARC

        return None

    def _handle_flight_arc(
        self,
        frame_idx: int,
        source_time_s: float,
        ball_obs: Optional[Dict[str, Any]],
        cur_rim: Optional[RimApertureGeometry],
    ) -> Optional[ShotCandidateRecord]:
        """FLIGHT_ARC phase: track trajectory toward rim and test outcome."""
        flight_dur = source_time_s - (self.release_time_s or source_time_s)

        # 1. Flight timeout check
        if flight_dur > self.config.max_flight_duration_seconds:
            rec = self._record_candidate(
                status="unresolved",
                outcome="unresolved",
                phase=ShotPhase.ABORTED,
                reason="flight_duration_exceeded",
            )
            self.reset(reason="flight_timeout")
            return rec

        # 2. Check rim interaction
        target_rim = cur_rim or (self.rim_samples[-1] if self.rim_samples else None)
        if not target_rim:
            return None

        # Check rim staleness (if rim detection is older than 1.5s, it is stale)
        if source_time_s - target_rim.source_time_s > 1.5:
            return None

        b_c = (ball_obs.get("center_image") or ball_obs.get("center")) if ball_obs else None
        if not b_c:
            b_c = self.last_observed_ball_center
        if not b_c:
            return None

        # Check if ball is stationary while far from rim -> aborted (false release / still holding)
        if flight_dur > 0.2:
            pts = [b for b in self.ball_trajectory[-3:] if b.get("center")]
            if len(pts) >= 3:
                dist_moved = math.dist(pts[0]["center"], pts[-1]["center"])
                if dist_moved < 15.0 and math.dist(b_c, target_rim.center) > 250.0:
                    self.reset(reason="ball_stationary_abort")
                    return None

        # Outcome check requires minimal flight time to reach rim
        if flight_dur >= self.config.min_flight_duration_seconds:
            dist_to_rim = math.dist(b_c, target_rim.center)

            # 3. Near rim evaluation (within rim proximity window)
            if dist_to_rim <= self.config.rim_proximity_px:
                # Test for MADE BASKET (downward aperture crossing from REAL observations)
                made_result = self._check_rim_aperture_crossing(target_rim)
                if made_result["is_made"]:
                    rec = self._record_candidate(
                        status="auto_confirmed",
                        outcome="made",
                        phase=ShotPhase.BASKET,
                        reason="rim_aperture_downward_crossing",
                        evidence=made_result,
                    )
                    self.last_confirmed_shot_time_s = source_time_s
                    self.reset(reason="basket_confirmed")
                    return rec

                # Test for MISSED SHOT (rebound / deflect away)
                miss_result = self._check_rim_miss(target_rim)
                if miss_result["is_miss"]:
                    rec = self._record_candidate(
                        status="auto_confirmed",
                        outcome="miss",
                        phase=ShotPhase.MISS,
                        reason=miss_result["reason"],
                        evidence=miss_result,
                    )
                    self.last_confirmed_shot_time_s = source_time_s
                    self.reset(reason="miss_confirmed")
                    return rec

        return None

    def _check_rim_aperture_crossing(
        self,
        rim: RimApertureGeometry,
    ) -> Dict[str, Any]:
        """Verify downward crossing through rim aperture band from REAL observations.

        Conditions for a Made Basket:
          1. At least 2 distinct OBSERVED ball samples near rim.
          2. Verified top entry: observed ball sample in upper entry band.
          3. Verified bottom exit: observed ball sample at or below rim ring level.
          4. Chronological order: observed top entry strictly precedes observed bottom exit.
          5. Verified downward motion (v_y >= min_downward_velocity_px_s).
          6. Horizontal position constrained within the aperture bounds.
          7. No observation gap > max_flight_gap_seconds in the crossing span.
          8. Optional net deceleration cue (if enabled and measurable).
        """
        # Filter ONLY real observed points near rim with sufficient confidence during current shot flight
        min_t = (self.release_time_s or 0.0)
        obs_near_rim = [
            b for b in self.ball_trajectory
            if b.get("sample_type") == "observed"
            and b.get("center") is not None
            and b.get("source_time_s", 0.0) >= min_t
            and math.dist(b["center"], rim.center) <= self.config.rim_proximity_px
            and (b.get("confidence") is None or b.get("confidence") >= self.config.min_ball_confidence)
        ]
        if len(obs_near_rim) < 2:
            return {
                "is_made": False,
                "reason": "insufficient_observed_samples_near_rim",
                "observed_count": len(obs_near_rim),
            }

        # Horizontal aperture check with margin
        x_min, x_max = rim.aperture_x_bounds
        h_margin = rim.width * 0.35
        aperture_obs = [
            b for b in obs_near_rim
            if (x_min - h_margin) <= b["center"][0] <= (x_max + h_margin)
            and abs(b["center"][1] - rim.center[1]) <= rim.height * 2.2
        ]
        if len(aperture_obs) < 2:
            return {
                "is_made": False,
                "reason": "horizontal_aperture_miss",
                "aperture_obs_count": len(aperture_obs),
            }

        # Check observed entry from above and exit below rim ring
        # Top entry: at or above upper band (<= rim.xyxy[1] + rim.height * 0.35)
        # Bottom exit: at or below ring level (>= rim.center[1])
        top_entry_obs = [
            b for b in aperture_obs
            if b["center"][1] <= rim.xyxy[1] + rim.height * 0.35
        ]
        bottom_exit_obs = [
            b for b in aperture_obs
            if b["center"][1] >= rim.center[1]
        ]

        if not top_entry_obs:
            return {"is_made": False, "reason": "no_observed_top_entry"}
        if not bottom_exit_obs:
            return {"is_made": False, "reason": "no_observed_bottom_exit"}

        first_entry = min(top_entry_obs, key=lambda b: (b["source_time_s"], b["frame_index"]))
        last_exit = max(bottom_exit_obs, key=lambda b: (b["source_time_s"], b["frame_index"]))

        if last_exit["source_time_s"] <= first_entry["source_time_s"]:
            return {"is_made": False, "reason": "exit_precedes_entry_reverse_motion"}

        # Vertical displacement & velocity
        delta_y = last_exit["center"][1] - first_entry["center"][1]
        delta_t = max(0.001, last_exit["source_time_s"] - first_entry["source_time_s"])
        v_y = delta_y / delta_t

        if delta_y <= 0:
            return {"is_made": False, "reason": "non_downward_trajectory", "v_y": round(v_y, 2)}

        if self.config.require_downward_motion and v_y <= self.config.min_downward_velocity_px_s:
            return {"is_made": False, "reason": "insufficient_downward_velocity", "v_y": round(v_y, 2)}

        # Crossing continuity: check gaps between observations across crossing span
        span_obs = [
            b for b in aperture_obs
            if first_entry["source_time_s"] <= b["source_time_s"] <= last_exit["source_time_s"]
        ]
        span_obs.sort(key=lambda b: (b["source_time_s"], b["frame_index"]))
        max_crossing_gap = 0.0
        for i in range(len(span_obs) - 1):
            gap = span_obs[i + 1]["source_time_s"] - span_obs[i]["source_time_s"]
            if gap > max_crossing_gap:
                max_crossing_gap = gap
            if gap > self.config.max_flight_gap_seconds:
                return {
                    "is_made": False,
                    "reason": "observation_gap_in_crossing_exceeded",
                    "max_gap_s": round(gap, 3),
                }

        # Track consistency
        tracks = {b.get("track_id") for b in span_obs if b.get("track_id") is not None}
        if len(tracks) > 1:
            return {"is_made": False, "reason": "conflicting_ball_tracks", "tracks": list(tracks)}

        # Deceleration / Net Cue
        net_cue_passed = None
        net_cue_status = "disabled"
        decel_ratio = None
        if self.config.enable_net_cue:
            if len(span_obs) >= 3:
                p0, p1 = span_obs[0], span_obs[1]
                p_end1, p_end2 = span_obs[-2], span_obs[-1]
                dt_in = max(0.001, p1["source_time_s"] - p0["source_time_s"])
                dt_out = max(0.001, p_end2["source_time_s"] - p_end1["source_time_s"])
                vy_in = (p1["center"][1] - p0["center"][1]) / dt_in
                vy_out = (p_end2["center"][1] - p_end1["center"][1]) / dt_out
                if vy_in > 20.0 and vy_out >= 0:
                    decel_ratio = round(vy_out / max(1.0, vy_in), 3)
                    net_cue_passed = bool(decel_ratio <= self.config.net_deceleration_min_ratio)
                    net_cue_status = "measured_pass" if net_cue_passed else "measured_no_decel"
                else:
                    net_cue_status = "unmeasurable_velocity"
            else:
                net_cue_status = "unavailable_insufficient_samples"

        return {
            "is_made": True,
            "entry_frame_idx": first_entry["frame_index"],
            "entry_time_s": first_entry["source_time_s"],
            "entry_center": [round(c, 1) for c in first_entry["center"]],
            "exit_frame_idx": last_exit["frame_index"],
            "exit_time_s": last_exit["source_time_s"],
            "exit_center": [round(c, 1) for c in last_exit["center"]],
            "delta_y": round(delta_y, 2),
            "delta_t": round(delta_t, 3),
            "v_y": round(v_y, 2),
            "observed_samples_near_rim": len(obs_near_rim),
            "observed_crossing_count": len(span_obs),
            "max_crossing_gap_s": round(max_crossing_gap, 3),
            "rim_confidence": round(rim.confidence, 3),
            "rim_center": [round(c, 1) for c in rim.center],
            "decel_ratio": decel_ratio,
            "net_cue_passed": net_cue_passed,
            "net_cue_status": net_cue_status,
        }

    def _check_rim_miss(
        self,
        rim: RimApertureGeometry,
    ) -> Dict[str, Any]:
        """Detect rebound / deflection away from rim indicating a missed shot."""
        recent_pts = [b for b in self.ball_trajectory if b.get("center") is not None]
        if len(recent_pts) < 4:
            return {"is_miss": False, "reason": "insufficient_points"}

        # Look for upward bounce after descending toward rim (reversal from downward to upward)
        y_vals = [b["center"][1] for b in recent_pts[-4:]]
        if len(y_vals) >= 3 and y_vals[-2] >= rim.center[1] - rim.height * 0.8:
            was_descending = y_vals[-3] < y_vals[-2]
            now_ascending = y_vals[-1] < y_vals[-2] - 10.0
            if was_descending and now_ascending:
                return {"is_miss": True, "reason": "rim_bounce_upward_deflection"}

        # Check for wide miss descending past rim without crossing aperture
        last_pt = recent_pts[-1]["center"]
        x_min, x_max = rim.aperture_x_bounds
        if last_pt[1] > rim.center[1] + rim.height * 0.5:
            if last_pt[0] < x_min - rim.width * 0.4 or last_pt[0] > x_max + rim.width * 0.4:
                # Must have been near rim level earlier
                if any(abs(b["center"][1] - rim.center[1]) <= rim.height * 0.8 for b in recent_pts[:-1]):
                    return {"is_miss": True, "reason": "wide_rim_miss_descending_outside_aperture"}

        return {"is_miss": False, "reason": "no_clear_miss_signal"}

    def _compute_recent_ball_velocity(self) -> Optional[Tuple[float, float, float]]:
        """Compute average (vx, vy, speed) from last ball trajectory samples."""
        pts = [b for b in self.ball_trajectory if b.get("center") is not None]
        if len(pts) < 2:
            return None

        p1 = pts[-2]
        p2 = pts[-1]
        dt = p2["source_time_s"] - p1["source_time_s"]
        if dt <= 0.001 or dt > 0.2:
            return None

        dist = math.dist(p1["center"], p2["center"])
        if dist > 75.0 and dt < 0.05:
            return None

        vx = (p2["center"][0] - p1["center"][0]) / dt
        vy = (p2["center"][1] - p1["center"][1]) / dt
        speed = math.hypot(vx, vy)
        return (vx, vy, speed)

    def _record_candidate(
        self,
        status: str,
        outcome: str,
        phase: ShotPhase,
        reason: str,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> ShotCandidateRecord:
        """Create and register candidate record."""
        # Find shooter from actor candidates
        best_actor = self.actor_candidates[-1]["player"] if self.actor_candidates else None
        shooter_track = best_actor.get("track_id") if best_actor else None
        shooter_team = best_actor.get("team_id") if best_actor else None
        shooter_player = best_actor.get("player_id") if best_actor else None

        rec = ShotCandidateRecord(
            shot_id=self.current_shot_id or f"shot_{self.video_id}_{self.shot_counter:04d}",
            video_id=self.video_id,
            segment_id=self.video_id,
            camera_id=self.camera_id,
            status=status,
            outcome=outcome,
            phase=phase,
            release_time_s=self.release_time_s,
            release_frame_idx=self.release_frame_idx,
            outcome_time_s=self.ball_trajectory[-1]["source_time_s"] if self.ball_trajectory else None,
            outcome_frame_idx=self.ball_trajectory[-1]["frame_index"] if self.ball_trajectory else None,
            confirmation_time_s=self.last_processed_time_s or (self.ball_trajectory[-1]["source_time_s"] if self.ball_trajectory else None),
            shooter_track_id=shooter_track,
            shooter_player_id=shooter_player,
            shooter_team_id=shooter_team,
            attribution_level=AttributionLevel.PLAYER if shooter_player else (
                AttributionLevel.TEAM if shooter_team else AttributionLevel.UNKNOWN
            ),
            evidence_details=evidence or {},
            reason_codes=[reason],
        )
        self.all_candidates.append(rec)
        if status == "auto_confirmed":
            self.confirmed_shots.append(rec)
        return rec
