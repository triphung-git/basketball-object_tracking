"""Automatic Rebounds Recognition and Classification Engine (Task 09 / Sequence 01B).

Detects and classifies basketball rebounds following eligible missed shots:
  - Triggered strictly by eligible missed field goals or final missed free throws (never made baskets or non-shots).
  - Multi-frame observed sustained ball control requirement: prevents predicted-only or glancing brushes.
  - Rejects non-monotonic timestamps, excessive gaps, cuts/replays, dead-ball periods, and actor switching.
  - Classifies into Offensive, Defensive, and Team rebounds based on team possession transition.
  - Ingestion into EventLedger preserving causal link to missed shot without duplicate credits.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import math
from typing import Any, Dict, List, Optional, Set, Tuple

from basketball_scoreboard.events import EventLedger, EventStatus, EventType, LedgerEventRecord


class ReboundType(str, Enum):
    """Categorical rebound classification."""
    OFFENSIVE = "offensive_rebound"
    DEFENSIVE = "defensive_rebound"
    TEAM = "team_rebound"


@dataclass
class ReboundCandidate:
    """Provisional rebound recovery detection."""
    rebound_id: str
    shot_id: str
    rebound_type: ReboundType
    team_id: str
    player_id: Optional[str]
    source_time_s: float
    frame_index: int
    control_duration_s: float
    confidence: float
    status: EventStatus = EventStatus.AUTO_CONFIRMED
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_ledger_record(self) -> LedgerEventRecord:
        """Convert into canonical LedgerEventRecord."""
        return LedgerEventRecord(
            event_id=self.rebound_id,
            event_type=EventType.REBOUND,
            source_time_s=self.source_time_s,
            frame_index=self.frame_index,
            team_id=self.team_id,
            player_id=self.player_id,
            subtype=self.rebound_type.value,
            status=self.status,
            parent_event_id=self.shot_id,
            evidence={
                "control_duration_s": round(self.control_duration_s, 3),
                "confidence": round(self.confidence, 3),
                **self.evidence,
            },
        )


@dataclass
class ReboundEngineConfig:
    """Configurable thresholds for rebound recovery evaluation."""
    min_control_duration_s: float = 0.15
    max_recovery_window_s: float = 3.5
    min_control_frames: int = 3
    max_control_gap_s: float = 0.25
    min_observation_confidence: float = 0.6
    rim_proximity_margin_factor: float = 2.5


class ReboundEngine:
    """Adjudicates rebound events following missed shots."""

    def __init__(self, config: Optional[ReboundEngineConfig] = None) -> None:
        self.config = config or ReboundEngineConfig()
        self.rebound_events: List[ReboundCandidate] = []
        self._processed_shots: Set[str] = set()

    def evaluate_missed_shot(
        self,
        shot_id: str,
        shot_outcome: str,
        shooting_team_id: Optional[str],
        miss_time_s: float,
        control_observations: List[Dict[str, Any]],
        is_last_free_throw: bool = False,
        shot_kind: Optional[str] = "field_goal",
        is_free_throw: Optional[bool] = None,
        shot_context: Optional[Dict[str, Any]] = None,
        ft_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ReboundCandidate]:
        """Evaluate ball recoveries following a missed shot.

        Args:
            shot_id: Unique identifier of the shot.
            shot_outcome: 'miss', 'rim_hit', 'rim_bounce', 'airball', 'made', 'unknown', etc.
            shooting_team_id: Team ID that took the shot.
            miss_time_s: Timestamp when shot missed (rim bounce or airball boundary).
            control_observations: Chronological sequence of player control interactions.
            is_last_free_throw: True if this was the final FT in a series.
            shot_kind: 'field_goal', 'free_throw', 'unknown', etc.
            is_free_throw: Optional boolean flag for FT shot applicability.
            shot_context: Optional contextual dictionary about the shot attempt.
            ft_context: Optional contextual dictionary about FT series state.
        """
        # Guard 1: Made baskets and non-shots strictly return None
        if shot_outcome in {"made", "not_a_shot"}:
            return None

        # Guard 2: Idempotency per physical missed shot
        if shot_id in self._processed_shots:
            return None

        # Guard 3: Free throw series applicability
        is_ft = (is_free_throw is True) or (shot_kind in {"free_throw", "ft"})
        if ft_context:
            if ft_context.get("is_free_throw") is True or ft_context.get("shot_kind") in {"free_throw", "ft"}:
                is_ft = True
            if "is_last_free_throw" in ft_context:
                is_last_free_throw = bool(ft_context["is_last_free_throw"])

        if is_ft and not is_last_free_throw:
            # Under official basketball rules, a non-final FT miss is dead ball -> No live rebound
            return None

        # Determine if shot outcome or shot kind is ambiguous
        eligible_miss_outcomes = {"miss", "rim_hit", "rim_bounce", "airball", "blocked_miss", "backboard_miss"}
        is_ambiguous_miss = (shot_outcome in {"unknown", "unresolved"}) or (shot_outcome not in eligible_miss_outcomes)
        is_ambiguous_shot_kind = (shot_kind is None) or (shot_kind in {"unknown", "unresolved"})

        # Guard 4: Filter recoveries within temporal recovery window [miss_time_s, miss_time_s + max_recovery_window_s]
        eligible_recoveries = [
            c for c in control_observations
            if miss_time_s <= c.get("source_time_s", 0.0) <= (miss_time_s + self.config.max_recovery_window_s)
        ]
        if not eligible_recoveries:
            return None

        # Sort chronologically by source_time_s and frame_index
        eligible_recoveries.sort(key=lambda x: (x.get("source_time_s", 0.0), x.get("frame_index", 0)))

        # Evaluate observed sustained control
        best_actor_control: Optional[Dict[str, Any]] = None
        current_actor: Optional[str] = None
        consecutive_count = 0
        t_start = 0.0
        t_prev: Optional[float] = None

        for c in eligible_recoveries:
            sample_type = c.get("sample_type", "observed")
            conf = float(c.get("confidence", 0.85))
            is_cut_or_dead = bool(c.get("is_cut") or c.get("is_replay") or c.get("is_dead_ball"))
            t_curr = float(c.get("source_time_s", 0.0))
            ctrl = c.get("controller") if isinstance(c.get("controller"), dict) else {}
            c_team_id = c.get("team_id") or ctrl.get("team_id")
            c_player_id = c.get("player_id") or ctrl.get("player_id")
            c_track_id = c.get("track_id") or ctrl.get("track_id")
            actor_key = f"{c_team_id}:{c_player_id or c_track_id}"
            # Continuous possession rows also describe free/unknown ball states.
            # They are not recoveries merely because several rows are consecutive.
            missing_actor = not (c_player_id or c_track_id)
            invalid_control_state = (
                ("state" in c and c["state"] != "controlled")
                or ("certainty" in c and c["certainty"] != "confirmed")
            )

            # Sustained control requires observed evidence with sufficient confidence;
            # predicted-only, dead ball, or camera cut/replay immediately breaks the chain.
            if (sample_type != "observed" or conf < self.config.min_observation_confidence
                    or is_cut_or_dead or missing_actor or invalid_control_state):
                current_actor = None
                consecutive_count = 0
                t_prev = None
                continue

            # Monotonicity check: reject duplicates or non-monotonic timestamps
            if t_prev is not None and t_curr <= t_prev:
                current_actor = None
                consecutive_count = 0
                t_prev = None
                continue

            # Gap check: gap between consecutive frames must not exceed max_control_gap_s
            if t_prev is not None and (t_curr - t_prev) > self.config.max_control_gap_s:
                current_actor = None
                consecutive_count = 0
                t_prev = None

            # Actor grouping
            if current_actor is not None and actor_key == current_actor:
                consecutive_count += 1
                t_prev = t_curr
            else:
                current_actor = actor_key
                consecutive_count = 1
                t_start = t_curr
                t_prev = t_curr

            duration = max(t_curr - t_start, 0.0)
            if consecutive_count >= self.config.min_control_frames and duration >= self.config.min_control_duration_s:
                best_actor_control = {
                    "team_id": c_team_id,
                    "player_id": c_player_id,
                    "track_id": c_track_id,
                    "source_time_s": t_start,
                    "frame_index": c.get("frame_index", 0),
                    "duration_s": duration,
                    "frames_count": consecutive_count,
                    "confidence": conf,
                }
                break

        if not best_actor_control:
            return None

        rec_team = best_actor_control["team_id"]
        rec_player = best_actor_control["player_id"]

        # Determine Rebound Type
        if not rec_team:
            reb_type = ReboundType.TEAM
            status = EventStatus.UNRESOLVED
        elif shooting_team_id and rec_team == shooting_team_id:
            reb_type = ReboundType.OFFENSIVE
            status = EventStatus.AUTO_CONFIRMED if rec_player else EventStatus.PROVISIONAL
        elif shooting_team_id and rec_team != shooting_team_id:
            reb_type = ReboundType.DEFENSIVE
            status = EventStatus.AUTO_CONFIRMED if rec_player else EventStatus.PROVISIONAL
        else:
            reb_type = ReboundType.DEFENSIVE
            status = EventStatus.UNRESOLVED

        # Ambiguous miss or ambiguous shot kind prevents AUTO_CONFIRMED
        if is_ambiguous_miss or is_ambiguous_shot_kind:
            status = EventStatus.UNRESOLVED

        self._processed_shots.add(shot_id)
        reb_id = f"reb_{shot_id}_{int(best_actor_control['source_time_s'] * 100):06d}"

        candidate = ReboundCandidate(
            rebound_id=reb_id,
            shot_id=shot_id,
            rebound_type=reb_type,
            team_id=rec_team or shooting_team_id or "unknown",
            player_id=rec_player,
            source_time_s=best_actor_control["source_time_s"],
            frame_index=best_actor_control["frame_index"],
            control_duration_s=best_actor_control["duration_s"],
            confidence=best_actor_control["confidence"],
            status=status,
            evidence={
                "shooting_team_id": shooting_team_id,
                "consecutive_frames": best_actor_control["frames_count"],
                "shot_outcome": shot_outcome,
                "shot_kind": shot_kind,
                "is_free_throw": is_ft,
                "is_last_free_throw": is_last_free_throw,
            },
        )
        self.rebound_events.append(candidate)
        return candidate
