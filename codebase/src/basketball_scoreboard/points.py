"""Automatic points calculation, bounded causal shooter history, team fallback, and event ledger (v2).

This module implements:
  1. Bounded shooter history resolution in [t_release - 2.0s, t_release].
  2. Team fallback attribution when player jersey OCR is unresolved.
  3. Point valuation according to FIBA 3x3 rules profile.
  4. Idempotent points ledger preventing double-counting.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .identity import RosterConfig, RosterPlayer
from .shots import AttributionLevel, ShotCandidateRecord


class PointValueReason(str, Enum):
    """Reasoning code for assigned point value."""
    FIBA_3X3_1PT_INSIDE_ARC = "fiba_3x3_1pt_inside_arc"
    FIBA_3X3_2PT_OUTSIDE_ARC = "fiba_3x3_2pt_outside_arc"
    FREE_THROW = "free_throw"
    UNRESOLVED_GEOMETRY = "unresolved_geometry"


@dataclass
class PointEventRecord:
    """Formal data contract for an automatic scoring event."""
    event_id: str
    shot_id: str
    video_id: str
    source_time_s: float
    confirmation_time_s: float
    status: str  # "auto_confirmed", "provisional", "void", "unresolved"
    scoring_team_id: Optional[str]
    scoring_player_id: Optional[str]
    attribution_level: AttributionLevel
    point_value: Optional[int]  # 1, 2, or None if unresolved
    value_reason: PointValueReason
    evidence_refs: Dict[str, Any] = field(default_factory=dict)
    is_idempotent: bool = True
    revision: int = 1

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["attribution_level"] = self.attribution_level.value
        data["value_reason"] = self.value_reason.value
        return data


class BoundedShooterHistoryResolver:
    """Resolves shooter identity causally from history in [t_release - 2.0s, t_release].

    Rules:
      1. Causal integrity: Only observations with capture PTS <= t_release are considered.
      2. Weighted consensus across OCR readings: weights by OCR confidence, box height,
         and temporal proximity to release.
      3. Roster validation: Verified against roster for valid team + jersey pairs.
      4. Team Fallback: If jersey OCR is ambiguous/unresolved, falls back to team_id
         from jersey color consensus.
    """

    def __init__(
        self,
        roster: RosterConfig,
        history_window_seconds: float = 2.0,
        min_ocr_confidence: float = 0.60,
    ) -> None:
        self.roster = roster
        self.history_window_s = history_window_seconds
        self.min_ocr_conf = min_ocr_confidence

    def resolve_shooter(
        self,
        shooter_track_id: Optional[str],
        release_time_s: float,
        player_observations: List[Dict[str, Any]],
        jersey_evidence: List[Dict[str, Any]],
    ) -> Tuple[Optional[str], Optional[str], AttributionLevel, Dict[str, Any]]:
        """Resolve (player_id, team_id, attribution_level, evidence_meta).

        Returns:
          player_id: Optional[str] (e.g. 'a_nguyen_huynh_phu_vinh' or None)
          team_id: Optional[str] ('team_a', 'team_b', or None)
          attribution_level: AttributionLevel (PLAYER, TEAM, or UNKNOWN)
          evidence: Dict summarizing votes, consensus, and history trace.
        """
        t_start = release_time_s - self.history_window_s
        t_end = release_time_s  # Strictly causal: no future evidence

        evidence_meta: Dict[str, Any] = {
            "query_window_s": [round(t_start, 3), round(t_end, 3)],
            "target_track_id": shooter_track_id,
            "ocr_readings_evaluated": 0,
            "team_observations_evaluated": 0,
            "candidate_votes": {},
            "team_votes": {},
        }

        if not shooter_track_id:
            return None, None, AttributionLevel.UNKNOWN, evidence_meta

        # 1. Gather causal player observations for target track (and tracklets nearby)
        track_obs_in_window = [
            obs for obs in player_observations
            if obs.get("track_id") == shooter_track_id
            and t_start <= obs.get("source_time_s", 0.0) <= t_end
        ]
        evidence_meta["team_observations_evaluated"] = len(track_obs_in_window)

        # Team consensus from color classification
        team_votes: Dict[str, float] = {"team_a": 0.0, "team_b": 0.0}
        for obs in track_obs_in_window:
            tid = obs.get("team_id")
            conf = obs.get("confidence", 0.8)
            if tid in team_votes:
                team_votes[tid] += conf

        evidence_meta["team_votes"] = {k: round(v, 2) for k, v in team_votes.items()}
        consensus_team_id: Optional[str] = None
        total_team_weight = sum(team_votes.values())
        if total_team_weight > 0:
            best_team = max(team_votes.items(), key=lambda item: item[1])
            if best_team[1] / total_team_weight >= 0.70:
                consensus_team_id = best_team[0]

        # 2. Gather causal OCR evidence
        ocr_in_window = [
            ev for ev in jersey_evidence
            if ev.get("track_id") == shooter_track_id
            and t_start <= ev.get("source_time_s", 0.0) <= t_end
            and ev.get("confidence", 0.0) >= self.min_ocr_conf
        ]
        evidence_meta["ocr_readings_evaluated"] = len(ocr_in_window)

        jersey_votes: Dict[str, float] = {}
        for ev in ocr_in_window:
            num = str(ev.get("detected_number", "")).strip()
            conf = float(ev.get("confidence", 0.5))
            t_s = float(ev.get("source_time_s", release_time_s))
            # Weight by temporal recency (closer to release gets higher weight)
            recency_weight = 1.0 - (release_time_s - t_s) / max(0.1, self.history_window_s) * 0.4
            weight = conf * recency_weight
            jersey_votes[num] = jersey_votes.get(num, 0.0) + weight

        evidence_meta["candidate_votes"] = {k: round(v, 2) for k, v in jersey_votes.items()}

        # 3. Check for resolved player
        resolved_player_id: Optional[str] = None
        if jersey_votes and consensus_team_id:
            best_num = max(jersey_votes.items(), key=lambda item: item[1])[0]
            # Match against roster
            player = self.roster.get_player(consensus_team_id, best_num)
            if player:
                resolved_player_id = player.player_id

        # 4. Determine Attribution Level
        if resolved_player_id and consensus_team_id:
            return resolved_player_id, consensus_team_id, AttributionLevel.PLAYER, evidence_meta
        elif consensus_team_id:
            # TEAM FALLBACK
            return None, consensus_team_id, AttributionLevel.TEAM, evidence_meta
        else:
            return None, None, AttributionLevel.UNKNOWN, evidence_meta


class PointsEngine:
    """Calculates points from confirmed shots, applies rule profile, and manages ledger."""

    def __init__(
        self,
        roster: RosterConfig,
        rule_profile: str = "fiba_3x3_standard",
    ) -> None:
        self.roster = roster
        self.rule_profile = rule_profile
        self.resolver = BoundedShooterHistoryResolver(roster=roster)

        # Ledger
        self.events: List[PointEventRecord] = []
        self.team_points: Dict[str, int] = {
            self.roster.team_a_id: 0,
            self.roster.team_b_id: 0,
        }
        self.processed_shot_ids: Set[str] = set()

    def process_shot(
        self,
        shot: ShotCandidateRecord,
        player_observations: List[Dict[str, Any]],
        jersey_evidence: List[Dict[str, Any]],
        is_free_throw: bool = False,
        court_distance_m: Optional[float] = None,
    ) -> Optional[PointEventRecord]:
        """Process a confirmed shot and award points idempotently if made."""
        if shot.outcome != "made" or shot.status != "auto_confirmed":
            return None

        # Check idempotency: prevent double counting
        if shot.shot_id in self.processed_shot_ids:
            return None

        release_t = shot.release_time_s or shot.outcome_time_s or 0.0
        outcome_t = shot.outcome_time_s or release_t

        # 1. Resolve Shooter Identity & Team Attribution
        player_id, team_id, attr_level, hist_evidence = self.resolver.resolve_shooter(
            shooter_track_id=shot.shooter_track_id,
            release_time_s=release_t,
            player_observations=player_observations,
            jersey_evidence=jersey_evidence,
        )
        if not player_id and getattr(shot, "shooter_player_id", None):
            player_id = shot.shooter_player_id
            team_id = getattr(shot, "shooter_team_id", None) or team_id
            attr_level = AttributionLevel.PLAYER
        elif not team_id and getattr(shot, "shooter_team_id", None):
            team_id = shot.shooter_team_id
            attr_level = AttributionLevel.TEAM

        # 2. Determine Point Value (FIBA 3x3 Rules)
        val: Optional[int] = None
        reason = PointValueReason.UNRESOLVED_GEOMETRY
        status = "auto_confirmed"
        if is_free_throw:
            val = 1
            reason = PointValueReason.FREE_THROW
        elif court_distance_m is not None:
            # FIBA 3x3 arc is 6.75m from basket center
            if court_distance_m > 6.75:
                val = 2
                reason = PointValueReason.FIBA_3X3_2PT_OUTSIDE_ARC
            else:
                val = 1
                reason = PointValueReason.FIBA_3X3_1PT_INSIDE_ARC
        else:
            # When court geometry/projection is unavailable, keep unresolved
            val = None
            reason = PointValueReason.UNRESOLVED_GEOMETRY
            status = "unresolved_geometry"

        # 3. Create Event Record
        event_id = f"score_{shot.video_id}_{len(self.events) + 1:04d}"
        ev = PointEventRecord(
            event_id=event_id,
            shot_id=shot.shot_id,
            video_id=shot.video_id,
            source_time_s=outcome_t,
            confirmation_time_s=outcome_t,
            status=status,
            scoring_team_id=team_id,
            scoring_player_id=player_id,
            attribution_level=attr_level,
            point_value=val,
            value_reason=reason,
            evidence_refs={
                "shot_evidence": shot.evidence_details,
                "history_evidence": hist_evidence,
            },
            is_idempotent=True,
        )

        self.events.append(ev)
        self.processed_shot_ids.add(shot.shot_id)

        # 4. Award Team Points
        if team_id in self.team_points and val is not None:
            self.team_points[team_id] += val

        return ev

    def get_summary(self) -> Dict[str, Any]:
        """Return ledger summary and aggregate scores."""
        return {
            "team_scores": {
                self.roster.team_a_name: self.team_points.get(self.roster.team_a_id, 0),
                self.roster.team_b_name: self.team_points.get(self.roster.team_b_id, 0),
            },
            "team_ids": {
                "team_a": self.roster.team_a_id,
                "team_b": self.roster.team_b_id,
            },
            "total_score_events": len(self.events),
            "attribution_breakdown": {
                "player": sum(1 for e in self.events if e.attribution_level == AttributionLevel.PLAYER),
                "team": sum(1 for e in self.events if e.attribution_level == AttributionLevel.TEAM),
                "unknown": sum(1 for e in self.events if e.attribution_level == AttributionLevel.UNKNOWN),
            },
        }

