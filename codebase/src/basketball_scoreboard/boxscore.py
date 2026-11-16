"""Automatic Box Score Aggregator for Basketball Scoreboard (Task 11).

Consolidates events from EventLedger into formal team and player box scores:
  - Enforces mathematical conservation invariants:
      sum(player.points) + team_only_points == observed_points
      total_score == initial_score_offset + observed_points
      sum(player.rebounds) + rebounds_team == rebounds_total
      rebounds_offensive + rebounds_defensive + rebounds_unclassified == rebounds_total
      sum(player.assists) + assists_team_only == assists_total
      sum(player.turnovers) + turnovers_team_only == turnovers_total
  - Strict eligibility filtering: only AUTO_CONFIRMED, non-void events contribute to confirmed stats.
  - Distinguishes 1PT, 2PT, and FT made field goals.
  - Distinguishes offensive, defensive, unclassified, and team rebounds.
  - Preserves assists, turnovers, and unresolved shots without artificial inflation or double counting.
  - Distinguishes initial score offsets from observed runtime video increments.
  - Exports to boxscore_auto.csv, dictionary summaries, and reconciliation audits.
"""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
import io
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from basketball_scoreboard.events import EventLedger, EventStatus, EventType, LedgerEventRecord
from basketball_scoreboard.identity import RosterConfig, RosterPlayer


@dataclass
class PlayerBoxScore:
    """Individual player statistical line."""
    team_id: str
    player_id: str
    player_number: Optional[int] = None
    player_name: Optional[str] = None
    points: int = 0
    fg_made_1pt: int = 0
    fg_made_2pt: int = 0
    ft_made: int = 0
    rebounds_offensive: int = 0
    rebounds_defensive: int = 0
    rebounds_total: int = 0
    assists: int = 0
    turnovers: int = 0
    unresolved_shots: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TeamBoxScore:
    """Consolidated team statistical line and roster breakdown."""
    team_id: str
    team_name: str
    initial_score_offset: int = 0
    observed_points: int = 0
    total_score: int = 0
    team_only_points: int = 0
    rebounds_offensive: int = 0
    rebounds_defensive: int = 0
    rebounds_team: int = 0
    rebounds_total: int = 0
    rebounds_unclassified: int = 0
    assists: int = 0
    assists_team_only: int = 0
    turnovers: int = 0
    turnovers_team_only: int = 0
    unresolved_shots: int = 0
    players: Dict[str, PlayerBoxScore] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["players"] = {pid: p.to_dict() for pid, p in self.players.items()}
        return d


class BoxScoreEngine:
    """Engine for compiling consistent, validated box scores from an EventLedger."""

    def __init__(
        self,
        roster: RosterConfig,
        initial_score_offsets: Optional[Dict[str, int]] = None,
    ) -> None:
        self.roster = roster
        self.initial_offsets = initial_score_offsets or {}

    def compile(self, ledger: EventLedger) -> Tuple[TeamBoxScore, TeamBoxScore]:
        """Aggregate all confirmed events from ledger and verify mathematical invariants."""
        # Initialize TeamBoxScores
        team_a = TeamBoxScore(
            team_id=self.roster.team_a_id,
            team_name=self.roster.team_a_name,
            initial_score_offset=self.initial_offsets.get(self.roster.team_a_id, 0),
        )
        team_b = TeamBoxScore(
            team_id=self.roster.team_b_id,
            team_name=self.roster.team_b_name,
            initial_score_offset=self.initial_offsets.get(self.roster.team_b_id, 0),
        )

        # Prepopulate roster players
        for p in self.roster.players:
            num = int(p.jersey_number) if str(p.jersey_number).isdigit() else None
            p_box = PlayerBoxScore(
                team_id=p.team_id,
                player_id=p.player_id,
                player_number=num,
                player_name=p.name,
            )
            if p.team_id == self.roster.team_a_id:
                team_a.players[p.player_id] = p_box
            elif p.team_id == self.roster.team_b_id:
                team_b.players[p.player_id] = p_box

        teams_map = {
            self.roster.team_a_id: team_a,
            self.roster.team_b_id: team_b,
        }

        # Retrieve active events from ledger
        active_events = ledger.get_active_events()

        for ev in active_events:
            team_box = teams_map.get(ev.team_id or "")
            if not team_box:
                # Team unresolved or not in current match roster
                continue

            # Check eligibility contract
            is_eligible = ledger.is_event_eligible(ev)

            if is_eligible:
                # Process by EventType for confirmed stats
                if ev.event_type == EventType.SHOT:
                    self._accumulate_shot(ev, team_box)
                elif ev.event_type == EventType.REBOUND:
                    self._accumulate_rebound(ev, team_box)
                elif ev.event_type == EventType.ASSIST:
                    self._accumulate_assist(ev, team_box)
                elif ev.event_type == EventType.TURNOVER:
                    self._accumulate_turnover(ev, team_box)
            else:
                # Non-eligible event: cannot increase confirmed PTS/REB/AST/TO.
                # However, track unresolved geometry shots for audit/coverage
                if ev.event_type == EventType.SHOT and not ev.is_void:
                    if ev.status == EventStatus.UNRESOLVED or ev.point_value is None:
                        team_box.unresolved_shots += 1
                        if ev.player_id and ev.player_id in team_box.players:
                            team_box.players[ev.player_id].unresolved_shots += 1

        # Finalize and verify mathematical invariants
        self._finalize_team(team_a)
        self._finalize_team(team_b)

        return team_a, team_b

    def _accumulate_shot(self, ev: LedgerEventRecord, team_box: TeamBoxScore) -> None:
        if ev.point_value is None:
            # Unresolved point geometry
            team_box.unresolved_shots += 1
            if ev.player_id and ev.player_id in team_box.players:
                team_box.players[ev.player_id].unresolved_shots += 1
            return

        pts = ev.point_value
        team_box.observed_points += pts

        # Assign to player if known on this team's roster, otherwise team-only attribution
        if ev.player_id and ev.player_id in team_box.players:
            p_box = team_box.players[ev.player_id]
            p_box.points += pts
            if pts == 1:
                if ev.subtype == "free_throw":
                    p_box.ft_made += 1
                else:
                    p_box.fg_made_1pt += 1
            elif pts == 2:
                p_box.fg_made_2pt += 1
            elif pts == 3:
                p_box.fg_made_2pt += 1  # 2pt in 3x3 context / outside arc
        else:
            # Team-only attribution (unknown or unassigned player)
            team_box.team_only_points += pts

    def _accumulate_rebound(self, ev: LedgerEventRecord, team_box: TeamBoxScore) -> None:
        is_off = (ev.subtype == "offensive_rebound")
        is_def = (ev.subtype == "defensive_rebound")
        is_team = (ev.subtype == "team_rebound" or not ev.player_id or ev.player_id not in team_box.players)

        if is_team:
            team_box.rebounds_team += 1
            if is_off:
                team_box.rebounds_offensive += 1
            elif is_def:
                team_box.rebounds_defensive += 1
            else:
                team_box.rebounds_unclassified += 1
            team_box.rebounds_total += 1
        else:
            p_box = team_box.players[ev.player_id]
            if is_off:
                p_box.rebounds_offensive += 1
                team_box.rebounds_offensive += 1
            elif is_def:
                p_box.rebounds_defensive += 1
                team_box.rebounds_defensive += 1
            else:
                team_box.rebounds_unclassified += 1
            p_box.rebounds_total += 1
            team_box.rebounds_total += 1

    def _accumulate_assist(self, ev: LedgerEventRecord, team_box: TeamBoxScore) -> None:
        if ev.player_id and ev.player_id in team_box.players:
            team_box.players[ev.player_id].assists += 1
            team_box.assists += 1
        else:
            # Verified team assist without specific player attribution
            team_box.assists_team_only += 1
            team_box.assists += 1

    def _accumulate_turnover(self, ev: LedgerEventRecord, team_box: TeamBoxScore) -> None:
        if ev.player_id and ev.player_id in team_box.players:
            team_box.players[ev.player_id].turnovers += 1
            team_box.turnovers += 1
        else:
            team_box.turnovers_team_only += 1
            team_box.turnovers += 1

    def _finalize_team(self, team_box: TeamBoxScore) -> None:
        team_box.total_score = team_box.initial_score_offset + team_box.observed_points

        # Score conservation check
        player_points_sum = sum(p.points for p in team_box.players.values())
        if player_points_sum + team_box.team_only_points != team_box.observed_points:
            raise AssertionError(
                f"Score Conservation Violation in {team_box.team_name}: "
                f"player_points ({player_points_sum}) + team_only ({team_box.team_only_points}) "
                f"!= observed ({team_box.observed_points})"
            )

        # Rebound player vs team conservation check
        player_reb_sum = sum(p.rebounds_total for p in team_box.players.values())
        if player_reb_sum + team_box.rebounds_team != team_box.rebounds_total:
            raise AssertionError(
                f"Rebounds Conservation Violation in {team_box.team_name}: "
                f"player_reb ({player_reb_sum}) + team_reb ({team_box.rebounds_team}) "
                f"!= total ({team_box.rebounds_total})"
            )

        # Rebound type conservation check
        type_reb_sum = team_box.rebounds_offensive + team_box.rebounds_defensive + team_box.rebounds_unclassified
        if type_reb_sum != team_box.rebounds_total:
            raise AssertionError(
                f"Rebounds Classification Violation in {team_box.team_name}: "
                f"off ({team_box.rebounds_offensive}) + def ({team_box.rebounds_defensive}) + unclass ({team_box.rebounds_unclassified}) "
                f"!= total ({team_box.rebounds_total})"
            )

        # Assists conservation check
        player_ast_sum = sum(p.assists for p in team_box.players.values())
        if player_ast_sum + team_box.assists_team_only != team_box.assists:
            raise AssertionError(
                f"Assists Conservation Violation in {team_box.team_name}: "
                f"player_ast ({player_ast_sum}) + team_only ({team_box.assists_team_only}) "
                f"!= total ({team_box.assists})"
            )

        # Turnovers conservation check
        player_to_sum = sum(p.turnovers for p in team_box.players.values())
        if player_to_sum + team_box.turnovers_team_only != team_box.turnovers:
            raise AssertionError(
                f"Turnovers Conservation Violation in {team_box.team_name}: "
                f"player_to ({player_to_sum}) + team_only ({team_box.turnovers_team_only}) "
                f"!= total ({team_box.turnovers})"
            )

    @classmethod
    def export_csv(
        cls,
        team_a: TeamBoxScore,
        team_b: TeamBoxScore,
        target: Any,
    ) -> None:
        """Export box score summary and player breakdown rows to CSV."""
        fieldnames = [
            "Team",
            "Player_ID",
            "Jersey",
            "Name",
            "PTS",
            "1PT",
            "2PT",
            "FT",
            "OREB",
            "DREB",
            "REB",
            "AST",
            "TO",
            "Unresolved_Shots",
        ]

        if hasattr(target, "write"):
            cls._write_csv_content(team_a, team_b, target, fieldnames)
        else:
            p = Path(target)
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("w", newline="", encoding="utf-8") as handle:
                cls._write_csv_content(team_a, team_b, handle, fieldnames)

    @classmethod
    def _write_csv_content(
        cls,
        team_a: TeamBoxScore,
        team_b: TeamBoxScore,
        handle: Any,
        fieldnames: List[str],
    ) -> None:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for team in [team_a, team_b]:
            # Team summary header row
            writer.writerow({
                "Team": team.team_name,
                "Player_ID": "TEAM_TOTAL",
                "Jersey": "-",
                "Name": f"TOTAL (Offset {team.initial_score_offset} + Obs {team.observed_points})",
                "PTS": team.total_score,
                "1PT": sum(p.fg_made_1pt for p in team.players.values()),
                "2PT": sum(p.fg_made_2pt for p in team.players.values()),
                "FT": sum(p.ft_made for p in team.players.values()),
                "OREB": team.rebounds_offensive,
                "DREB": team.rebounds_defensive,
                "REB": team.rebounds_total,
                "AST": team.assists,
                "TO": team.turnovers,
                "Unresolved_Shots": team.unresolved_shots,
            })

            # Individual players
            for p_box in team.players.values():
                writer.writerow({
                    "Team": team.team_name,
                    "Player_ID": p_box.player_id,
                    "Jersey": f"#{p_box.player_number}" if p_box.player_number is not None else "-",
                    "Name": p_box.player_name or p_box.player_id,
                    "PTS": p_box.points,
                    "1PT": p_box.fg_made_1pt,
                    "2PT": p_box.fg_made_2pt,
                    "FT": p_box.ft_made,
                    "OREB": p_box.rebounds_offensive,
                    "DREB": p_box.rebounds_defensive,
                    "REB": p_box.rebounds_total,
                    "AST": p_box.assists,
                    "TO": p_box.turnovers,
                    "Unresolved_Shots": p_box.unresolved_shots,
                })

            # Team unassigned points / stats row if any
            if team.team_only_points > 0 or team.rebounds_team > 0 or team.assists_team_only > 0 or team.turnovers_team_only > 0:
                writer.writerow({
                    "Team": team.team_name,
                    "Player_ID": "TEAM_UNASSIGNED",
                    "Jersey": "-",
                    "Name": "Team-Only Attribution (Unknown Player)",
                    "PTS": team.team_only_points,
                    "1PT": "-",
                    "2PT": "-",
                    "FT": "-",
                    "OREB": "-",
                    "DREB": "-",
                    "REB": team.rebounds_team,
                    "AST": team.assists_team_only if team.assists_team_only > 0 else "-",
                    "TO": team.turnovers_team_only if team.turnovers_team_only > 0 else "-",
                    "Unresolved_Shots": "-",
                })
