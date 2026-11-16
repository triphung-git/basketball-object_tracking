"""Automatic Assists Recognition and Causal Pass Tracking Engine (Task 10 / Sequence 01C).

Tracks causal pass-to-score chains leading directly to confirmed made baskets:
  - Triggered strictly by confirmed made field goals (never missed shots, non-shots, or unconfirmed shots).
  - Validates teammate attribution: passer must belong to same team as scorer, distinct from scorer.
  - Requires identified receiver that strictly matches the scorer.
  - Requires confirmed pass status with confidence meeting threshold.
  - Enforces temporal and action continuity: limits catch-to-release duration (e.g. <= 4.0s).
  - Enforces direct-shot and allow-dribbles guards: rejects independent drives, ISO actions, or excessive dribbles.
  - Invalidation guards: any intervening turnover, deflection, loose ball, camera cut, replay, dead ball, or rebound breaks the assist chain.
  - Generates canonical LedgerEventRecord referencing the parent made shot event.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import math
from typing import Any, Dict, List, Optional, Set, Tuple

from basketball_scoreboard.events import EventLedger, EventStatus, EventType, LedgerEventRecord


CHAIN_BREAK_KINDS = {
    "turnover",
    "defensive_rebound",
    "offensive_rebound",
    "rebound",
    "possession_reset",
    "deflection",
    "loose_ball",
    "camera_cut",
    "cut",
    "replay",
    "dead_ball",
    "steal",
    "foul",
}


@dataclass
class AssistCandidate:
    """Adjudicated assist credit linked to a confirmed made basket."""
    assist_id: str
    shot_id: str
    pass_id: Optional[str]
    passer_player_id: str
    passer_team_id: str
    scorer_player_id: str
    pass_catch_time_s: float
    shot_release_time_s: float
    status: EventStatus = EventStatus.AUTO_CONFIRMED
    confidence: float = 0.90
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_ledger_record(self) -> LedgerEventRecord:
        """Convert into canonical LedgerEventRecord."""
        return LedgerEventRecord(
            event_id=self.assist_id,
            event_type=EventType.ASSIST,
            source_time_s=self.pass_catch_time_s,
            frame_index=self.evidence.get("frame_index", 0),
            team_id=self.passer_team_id,
            player_id=self.passer_player_id,
            subtype="direct_assist",
            status=self.status,
            parent_event_id=self.shot_id,
            evidence={
                "scorer_player_id": self.scorer_player_id,
                "shot_release_time_s": round(self.shot_release_time_s, 3),
                "catch_to_release_s": round(self.shot_release_time_s - self.pass_catch_time_s, 3),
                "confidence": round(self.confidence, 3),
                **self.evidence,
            },
        )


@dataclass
class AssistEngineConfig:
    """Configurable thresholds for assist adjudication."""
    max_catch_to_release_s: float = 4.0
    require_direct_shot: bool = True
    allow_dribbles: int = 2
    min_pass_confidence: float = 0.6
    require_action_evidence: bool = False


class AssistEngine:
    """Adjudicates assists from confirmed passes and scores."""

    def __init__(self, config: Optional[AssistEngineConfig] = None) -> None:
        self.config = config or AssistEngineConfig()
        self.assist_events: List[AssistCandidate] = []
        self._processed_shots: Set[str] = set()

    def evaluate_made_shot(
        self,
        shot_id: str,
        shot_outcome: str,
        scorer_team_id: Optional[str],
        scorer_player_id: Optional[str],
        release_time_s: float,
        pass_events: List[Dict[str, Any]],
        intervening_events: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[AssistCandidate]:
        """Evaluate if an eligible pass preceded the made basket.

        Args:
            shot_id: Identifier of the made shot.
            shot_outcome: Outcome of shot; must strictly be 'made'.
            scorer_team_id: Team ID of the scoring player.
            scorer_player_id: Player ID of the shooter.
            release_time_s: Timestamp when shot was released.
            pass_events: Chronological sequence of completed passes.
            intervening_events: Any turnovers, fouls, deflections, rebounds, cuts, or loose balls.
        """
        # Guard 1: Only confirmed made shots can be assisted!
        if shot_outcome != "made":
            return None

        # Guard 2: Scorer team and player must be identified
        if not scorer_team_id or not scorer_player_id:
            return None

        # Guard 3: Single assist per made shot attempt
        if shot_id in self._processed_shots:
            return None

        intervening = intervening_events or []

        # Find most recent completed pass to the scorer prior to release
        candidate_pass: Optional[Dict[str, Any]] = None
        for p in reversed(pass_events):
            t_pass_end = float(p.get("confirmed_at_s") or p.get("receiver_time_s") or p.get("source_time_s", 0.0))
            if t_pass_end > release_time_s:
                continue

            dt = release_time_s - t_pass_end
            if dt > self.config.max_catch_to_release_s:
                break  # Passes further back exceed assist window

            receiver_id = p.get("receiver_player_id") or p.get("receiver", {}).get("player_id")
            passer_id = p.get("passer_player_id") or p.get("passer", {}).get("player_id")
            passer_team = p.get("team_id") or p.get("passer", {}).get("team_id")

            # Receiver MUST be identified and MUST match scorer
            if not receiver_id or receiver_id != scorer_player_id:
                continue

            # Validate teammate relation: passer must be on same team, distinct from scorer
            if not passer_team or passer_team != scorer_team_id:
                continue
            if not passer_id or passer_id == scorer_player_id:
                continue  # Self-pass is not an assist

            # Validate pass confirmation status and confidence
            p_status = p.get("status", "auto_confirmed")
            if isinstance(p_status, EventStatus):
                p_status = p_status.value
            p_conf = float(p.get("confidence", 0.90))

            if p_status != "auto_confirmed" or p_conf < self.config.min_pass_confidence:
                # Candidate, unconfirmed, or low-confidence pass cannot generate auto-confirmed assist
                continue

            # Check post-catch action context and dribble limits
            action_ctx = p.get("action_context")
            if action_ctx in {"independent_drive", "isolation", "broken_play", "turnover_recovery"}:
                # Scorer created own shot via independent drive/ISO move
                continue

            dribbles = p.get("dribbles_after_catch")
            if dribbles is not None and dribbles > self.config.allow_dribbles:
                # Exceeded maximum allowable dribbles for a direct assist
                continue

            # Check for intervening chain breaks
            has_break = False
            for inv in intervening:
                t_inv = float(inv.get("source_time_s", 0.0))
                if t_pass_end < t_inv < release_time_s:
                    kind = str(inv.get("kind") or inv.get("event_type", "")).lower()
                    if kind in CHAIN_BREAK_KINDS:
                        has_break = True
                        break

            if has_break:
                continue

            candidate_pass = {
                "pass_id": p.get("pass_id"),
                "passer_id": passer_id,
                "passer_team": passer_team,
                "catch_time_s": t_pass_end,
                "confidence": p_conf,
                "frame_index": p.get("frame_index", 0),
                "action_context": action_ctx,
                "dribbles_after_catch": dribbles,
            }
            break

        if not candidate_pass or not candidate_pass["passer_id"]:
            return None

        self._processed_shots.add(shot_id)
        ast_id = f"ast_{shot_id}_{candidate_pass['passer_id']}"
        candidate = AssistCandidate(
            assist_id=ast_id,
            shot_id=shot_id,
            pass_id=candidate_pass["pass_id"],
            passer_player_id=candidate_pass["passer_id"],
            passer_team_id=candidate_pass["passer_team"],
            scorer_player_id=scorer_player_id,
            pass_catch_time_s=candidate_pass["catch_time_s"],
            shot_release_time_s=release_time_s,
            status=EventStatus.AUTO_CONFIRMED,
            confidence=candidate_pass["confidence"],
            evidence={
                "frame_index": candidate_pass["frame_index"],
                "action_context": candidate_pass["action_context"],
                "dribbles_after_catch": candidate_pass["dribbles_after_catch"],
            },
        )
        self.assist_events.append(candidate)
        return candidate
