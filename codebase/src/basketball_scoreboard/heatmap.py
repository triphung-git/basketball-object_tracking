"""Time-weighted spatial occupancy heatmap accumulator based on player-seconds (v2)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
import os
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import matplotlib
matplotlib.use("Agg")  # Non-interactive headless backend
import matplotlib.pyplot as plt
import numpy as np

from .court import TrajectoryObservation


class HeatmapError(Exception):
    """Base error for heatmap accumulation."""
    pass


@dataclass
class ExclusionInterval:
    """Interval in source time (seconds) excluded from heatmap accumulation (e.g. cuts, dead ball)."""
    start_s: float
    end_s: float
    reason: str = "excluded"

    def __post_init__(self) -> None:
        if not all(math.isfinite(v) and v >= 0 for v in (self.start_s,self.end_s)) or self.end_s <= self.start_s:
            raise ValueError(f"Invalid exclusion interval: end_s ({self.end_s}) < start_s ({self.start_s})")

    def intersects(self, t0: float, t1: float) -> bool:
        return max(t0, self.start_s) < min(t1, self.end_s)

    def overlap_duration(self, t0: float, t1: float) -> float:
        overlap_start = max(t0, self.start_s)
        overlap_end = min(t1, self.end_s)
        return max(0.0, overlap_end - overlap_start)


@dataclass
class HeatmapMetadata:
    """Telemetry and mass accounting for heatmap accumulation."""
    units: str
    grid_shape: Tuple[int, int]  # (n_rows, n_cols)
    court_bounds: Dict[str, float]
    cell_size_xy: Tuple[float, float]
    total_player_seconds: float = 0.0
    team_a_player_seconds: float = 0.0
    team_b_player_seconds: float = 0.0
    unknown_team_player_seconds: float = 0.0
    outside_bounds_player_seconds: float = 0.0
    excluded_player_seconds: float = 0.0
    stale_gap_discarded_seconds: float = 0.0
    repaired_intervals_count: int = 0
    repaired_player_seconds: float = 0.0
    cut_discarded_seconds: float = 0.0
    invalid_interval_seconds: float = 0.0
    total_intervals_processed: int = 0
    total_observations_seen: int = 0
    max_gap_s: float = 1.0
    timestamp_policy: str = "allow_repaired_with_warning"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["grid_shape"] = list(self.grid_shape)
        d["cell_size_xy"] = [round(v, 4) for v in self.cell_size_xy]
        d["total_player_seconds"] = round(self.total_player_seconds, 6)
        d["team_a_player_seconds"] = round(self.team_a_player_seconds, 6)
        d["team_b_player_seconds"] = round(self.team_b_player_seconds, 6)
        d["unknown_team_player_seconds"] = round(self.unknown_team_player_seconds, 6)
        d["outside_bounds_player_seconds"] = round(self.outside_bounds_player_seconds, 6)
        d["excluded_player_seconds"] = round(self.excluded_player_seconds, 6)
        d["stale_gap_discarded_seconds"] = round(self.stale_gap_discarded_seconds, 6)
        d["repaired_player_seconds"] = round(self.repaired_player_seconds, 6)
        return d


class HeatmapAccumulator:
    """
    Time-weighted spatial occupancy accumulator.
    
    Invariants:
    1. Accumulation unit is strictly player-seconds.
    2. Left-hold integration on [t_i, t_{i+1}) per trajectory.
    3. Gaps exceeding max_gap_s are interrupted (zero mass accumulated).
    4. total_grid == team_a_grid + team_b_grid + unknown_team_grid (mass conservation).
    5. Replay of identical intervals is idempotent.
    """

    def __init__(
        self,
        court_bounds: Dict[str, float],
        grid_shape: Tuple[int, int] = (50, 50),
        units: str = "meters",
        team_a_id: str = "team_a",
        team_b_id: str = "team_b",
        max_gap_s: float = 1.0,
        timestamp_policy: str = "allow_repaired_with_warning",
        exclusions: Optional[List[ExclusionInterval]] = None,
        allow_unknown_role: bool = False,
    ) -> None:
        self.court_bounds = dict(court_bounds)
        self.grid_shape = (int(grid_shape[0]), int(grid_shape[1]))
        self.units = str(units)
        self.team_a_id = str(team_a_id)
        self.team_b_id = str(team_b_id)
        self.max_gap_s = float(max_gap_s)
        self.timestamp_policy = str(timestamp_policy)
        self.exclusions = list(exclusions) if exclusions is not None else []
        self.allow_unknown_role = allow_unknown_role
        if (len(grid_shape) != 2 or any(not isinstance(v,int) or isinstance(v,bool) or v <= 0 for v in grid_shape)
                or not math.isfinite(self.max_gap_s) or self.max_gap_s <= 0):
            raise ValueError("Positive integer grid dimensions and finite positive max_gap_s required")
        if self.timestamp_policy not in {"strict_valid","allow_repaired_with_warning","allow_irregular"}:
            raise ValueError("Unknown timestamp policy")
        if not self.team_a_id or not self.team_b_id or self.team_a_id == self.team_b_id:
            raise ValueError("Two distinct team IDs required")

        # Coordinate grid geometry
        x_min, x_max = self.court_bounds["x_min"], self.court_bounds["x_max"]
        y_min, y_max = self.court_bounds["y_min"], self.court_bounds["y_max"]
        if not all(math.isfinite(v) for v in (x_min,x_max,y_min,y_max)) or x_max <= x_min or y_max <= y_min:
            raise ValueError(f"Invalid court bounds: {court_bounds}")

        self.dx = (x_max - x_min) / float(self.grid_shape[1])
        self.dy = (y_max - y_min) / float(self.grid_shape[0])

        # Raw accumulation grids (n_rows = y, n_cols = x)
        self.total_grid = np.zeros(self.grid_shape, dtype=np.float64)
        self.team_a_grid = np.zeros(self.grid_shape, dtype=np.float64)
        self.team_b_grid = np.zeros(self.grid_shape, dtype=np.float64)
        self.unknown_team_grid = np.zeros(self.grid_shape, dtype=np.float64)
        self.player_grids: Dict[str, np.ndarray] = {}

        # Accounting and deduplication
        self.metadata = HeatmapMetadata(
            units=self.units,
            grid_shape=self.grid_shape,
            court_bounds=self.court_bounds,
            cell_size_xy=(self.dx, self.dy),
            max_gap_s=self.max_gap_s,
            timestamp_policy=self.timestamp_policy,
        )
        self._processed_interval_keys: Set[str] = set()
        self._seen_observations = {}

    def reset(self) -> None:
        """Reset all accumulator grids and counters."""
        self.total_grid.fill(0.0)
        self.team_a_grid.fill(0.0)
        self.team_b_grid.fill(0.0)
        self.unknown_team_grid.fill(0.0)
        self.player_grids.clear()
        self.metadata = HeatmapMetadata(
            units=self.units,
            grid_shape=self.grid_shape,
            court_bounds=self.court_bounds,
            cell_size_xy=(self.dx, self.dy),
            max_gap_s=self.max_gap_s,
            timestamp_policy=self.timestamp_policy,
        )
        self._processed_interval_keys.clear()
        self._seen_observations.clear()

    def _coord_to_indices(self, x: float, y: float) -> Optional[Tuple[int, int]]:
        """Map court coordinate (x, y) to (row, col) grid indices."""
        x_min, x_max = self.court_bounds["x_min"], self.court_bounds["x_max"]
        y_min, y_max = self.court_bounds["y_min"], self.court_bounds["y_max"]

        if not (x_min <= x <= x_max and y_min <= y <= y_max):
            return None

        # Compute column (x)
        col = int((x - x_min) / self.dx)
        if col >= self.grid_shape[1]:
            col = self.grid_shape[1] - 1

        # Compute row (y). Standard convention: row 0 is y_min (or inverted in plot)
        row = int((y - y_min) / self.dy)
        if row >= self.grid_shape[0]:
            row = self.grid_shape[0] - 1

        return (row, col)

    def add_trajectory_interval(
        self,
        interval_key: str,
        court_xy: Tuple[float, float],
        start_time_s: float,
        end_time_s: float,
        team_id: Optional[str] = None,
        player_id: Optional[str] = None,
        timestamp_status: str = "valid",
        sample_type: str = "observed",
    ) -> bool:
        """
        Accumulate a single left-hold time interval for an entity on court.
        
        Returns True if interval was accumulated, False if skipped/deduplicated/invalid.
        """
        if interval_key in self._processed_interval_keys:
            return False  # Idempotent deduplication
        if not interval_key or not all(math.isfinite(v) for v in (*court_xy,start_time_s,end_time_s)) or start_time_s < 0:
            raise ValueError("Finite interval coordinates and non-negative times required")
        if timestamp_status not in {"valid","repaired","estimated","irregular"}:
            raise ValueError("Unknown timestamp status")
        self._processed_interval_keys.add(interval_key)
        if sample_type != "observed":
            return False
        allowed = {"valid"}
        if self.timestamp_policy in {"allow_repaired_with_warning","allow_irregular"}:
            allowed.add("repaired")
        if self.timestamp_policy == "allow_irregular":
            allowed.add("irregular")
        if timestamp_status not in allowed:
            return False
        if end_time_s <= start_time_s:
            return False

        duration = end_time_s - start_time_s

        if any(e.reason in {"cut","camera_change","segment_change"} and e.intersects(start_time_s,end_time_s) for e in self.exclusions):
            self.metadata.cut_discarded_seconds += duration
            return False

        # Gap interruption check
        if duration > self.max_gap_s:
            self.metadata.stale_gap_discarded_seconds += duration
            return False

        # Exclusions clipping
        excluded_duration = 0.0
        cursor = start_time_s
        for start,end in sorted((max(start_time_s,e.start_s),min(end_time_s,e.end_s)) for e in self.exclusions):
            if end > max(start,cursor):
                excluded_duration += end - max(start,cursor)
                cursor = end

        effective_duration = max(0.0, duration - excluded_duration)
        if excluded_duration > 0.0:
            self.metadata.excluded_player_seconds += excluded_duration

        if effective_duration <= 0.0:
            self._processed_interval_keys.add(interval_key)
            return False

        # Timestamp policy check
        if timestamp_status == "repaired":
            self.metadata.repaired_intervals_count += 1
            self.metadata.repaired_player_seconds += effective_duration

        # Map to grid
        x, y = court_xy
        indices = self._coord_to_indices(x, y)
        if indices is None:
            self.metadata.outside_bounds_player_seconds += effective_duration
            self._processed_interval_keys.add(interval_key)
            return False

        row, col = indices

        # Add to grids
        self.total_grid[row, col] += effective_duration
        self.metadata.total_player_seconds += effective_duration

        if team_id == self.team_a_id:
            self.team_a_grid[row, col] += effective_duration
            self.metadata.team_a_player_seconds += effective_duration
        elif team_id == self.team_b_id:
            self.team_b_grid[row, col] += effective_duration
            self.metadata.team_b_player_seconds += effective_duration
        else:
            self.unknown_team_grid[row, col] += effective_duration
            self.metadata.unknown_team_player_seconds += effective_duration

        if player_id:
            if player_id not in self.player_grids:
                self.player_grids[player_id] = np.zeros(self.grid_shape, dtype=np.float64)
            self.player_grids[player_id][row, col] += effective_duration

        self.metadata.total_intervals_processed += 1
        self._processed_interval_keys.add(interval_key)
        return True

    def process_observations_batch(self, observations, track_grouped=True, final_time_s=None):
        """Integrate adjacent eligible observations; invalid samples break continuity.

        A stable track ID is required. Trackless detection order is not identity.
        Complete batches may be replayed; call recompute for revisions or seek.
        """
        if not track_grouped:
            raise ValueError("Trackless occupancy needs a separate diagnostic aggregate")
        if final_time_s is not None and (not math.isfinite(final_time_s) or final_time_s < 0):
            raise ValueError("Invalid final boundary")
        converted_obs = []
        for raw_obs in observations:
            if isinstance(raw_obs, dict):
                converted_obs.append(TrajectoryObservation(
                    schema_version=raw_obs.get("schema_version", "2.0.0"),
                    observation_id=str(raw_obs["observation_id"]),
                    source_run_id=str(raw_obs.get("source_run_id", "")),
                    video_id=str(raw_obs.get("video_id", "")),
                    source_fingerprint_sha256=str(raw_obs.get("source_fingerprint_sha256", "")),
                    frame_index=int(raw_obs.get("frame_index", 0)),
                    source_time_s=float(raw_obs.get("source_time_s", 0.0)),
                    timestamp_status=str(raw_obs.get("timestamp_status", "valid")),
                    segment_id=str(raw_obs.get("segment_id", "default")),
                    camera_id=str(raw_obs.get("camera_id", "cam_main")),
                    bbox=list(raw_obs["bbox"]),
                    footpoint_image=tuple(raw_obs["footpoint_image"]) if raw_obs.get("footpoint_image") is not None else (0.0, 0.0),
                    position_method=str(raw_obs.get("position_method", "bbox_bottom_center")),
                    projected_court_xy=tuple(raw_obs["projected_court_xy"]) if raw_obs.get("projected_court_xy") is not None else None,
                    court_units=str(raw_obs.get("court_units", "meters")),
                    validity_status=str(raw_obs.get("validity_status", "valid")),
                    validity_reason=raw_obs.get("validity_reason"),
                    calibration_version=raw_obs.get("calibration_version"),
                    track_id=str(raw_obs["track_id"]) if raw_obs.get("track_id") is not None else None,
                    player_id=str(raw_obs["player_id"]) if raw_obs.get("player_id") is not None else None,
                    team_id=str(raw_obs["team_id"]) if raw_obs.get("team_id") is not None else None,
                    role=str(raw_obs.get("role", "unknown")),
                    sample_type=str(raw_obs.get("sample_type", "observed")),
                    confidence=float(raw_obs.get("confidence", 1.0)),
                ))
            else:
                converted_obs.append(raw_obs)
        observations = converted_obs

        signatures, streams = {}, {}
        for obs in observations:
            key_id = (obs.source_run_id, obs.video_id, obs.source_fingerprint_sha256, obs.observation_id)
            signature = json.dumps(obs.to_dict(), sort_keys=True)
            previous = signatures.get(key_id, self._seen_observations.get(key_id))
            if previous is not None and previous != signature:
                raise ValueError("Observation changed; create a revision and recompute")
            if key_id in signatures:
                continue
            signatures[key_id] = signature
            if obs.track_id is None:
                continue
            key = (obs.source_run_id, obs.video_id, obs.source_fingerprint_sha256, obs.track_id,
                   obs.segment_id, obs.camera_id, obs.calibration_version)
            streams.setdefault(key, []).append(obs)
        self.metadata.total_observations_seen += sum(k not in self._seen_observations for k in signatures)
        self._seen_observations.update(signatures)

        def eligible(obs):
            role_ok = obs.role == "player" or (self.allow_unknown_role and obs.role == "unknown")
            return (role_ok and obs.validity_status == "valid" and obs.projected_court_xy is not None
                    and obs.sample_type == "observed")

        for key, stream in streams.items():
            stream.sort(key=lambda obs: (obs.source_time_s, obs.frame_index))
            pairs = list(zip(stream, stream[1:]))
            for current, following in pairs:
                invalid_key = f"{key}:{current.observation_id}->{following.observation_id}"
                if not eligible(current) or not eligible(following):
                    if invalid_key not in self._processed_interval_keys:
                        self.metadata.invalid_interval_seconds += max(0.,following.source_time_s-current.source_time_s)
                        self._processed_interval_keys.add(invalid_key)
                    continue
                # Both endpoints must satisfy the clock policy. In particular,
                # a repaired end must never hide an estimated start timestamp.
                statuses = {current.timestamp_status, following.timestamp_status}
                status = next((s for s in ("estimated", "irregular", "repaired") if s in statuses), "valid")
                self.add_trajectory_interval(
                    f"{key}:{current.observation_id}->{following.observation_id}",
                    current.projected_court_xy, current.source_time_s, following.source_time_s,
                    current.team_id, current.player_id, status, current.sample_type)
            if stream and final_time_s is not None:
                last = stream[-1]
                if eligible(last) and 0 < final_time_s - last.source_time_s <= self.max_gap_s:
                    self.add_trajectory_interval(
                        f"{key}:{last.observation_id}->final:{final_time_s:.6f}",
                        last.projected_court_xy, last.source_time_s, final_time_s,
                        last.team_id, last.player_id, last.timestamp_status, last.sample_type)

    def verify_mass_conservation(self, tolerance: float = 1e-6) -> Tuple[bool, float, float]:
        """
        Verify that total mass equals sum of team components and metadata.
        
        Returns:
            (is_conserved, total_sum, components_sum)
        """
        total_sum = float(np.sum(self.total_grid))
        comp_sum = float(np.sum(self.team_a_grid) + np.sum(self.team_b_grid) + np.sum(self.unknown_team_grid))
        meta_sum = self.metadata.total_player_seconds
        
        grid_conserved = abs(total_sum - comp_sum) <= tolerance
        meta_conserved = abs(total_sum - meta_sum) <= tolerance
        return (grid_conserved and meta_conserved, total_sum, comp_sum)

    def recompute(
        self,
        observations: List[TrajectoryObservation],
        updated_team_mappings: Optional[Dict[str, str]] = None,
        updated_player_mappings: Optional[Dict[str, str]] = None,
        final_time_s: Optional[float] = None,
    ) -> None:
        """
        Recompute heatmap cleanly from raw trajectory observations.
        
        Applies updated track->team or track->player mappings without appending or doubling mass.
        """
        self.reset()
        if updated_team_mappings or updated_player_mappings:
            cloned_obs: List[TrajectoryObservation] = []
            for obs in observations:
                new_team = obs.team_id
                new_player = obs.player_id
                if obs.track_id and updated_team_mappings and obs.track_id in updated_team_mappings:
                    new_team = updated_team_mappings[obs.track_id]
                if obs.track_id and updated_player_mappings and obs.track_id in updated_player_mappings:
                    new_player = updated_player_mappings[obs.track_id]

                cloned = TrajectoryObservation(
                    schema_version=obs.schema_version,
                    observation_id=obs.observation_id,
                    source_run_id=obs.source_run_id,
                    video_id=obs.video_id,
                    source_fingerprint_sha256=obs.source_fingerprint_sha256,
                    frame_index=obs.frame_index,
                    source_time_s=obs.source_time_s,
                    timestamp_status=obs.timestamp_status,
                    segment_id=obs.segment_id,
                    camera_id=obs.camera_id,
                    bbox=list(obs.bbox),
                    footpoint_image=obs.footpoint_image,
                    position_method=obs.position_method,
                    projected_court_xy=obs.projected_court_xy,
                    court_units=obs.court_units,
                    validity_status=obs.validity_status,
                    validity_reason=obs.validity_reason,
                    calibration_version=obs.calibration_version,
                    track_id=obs.track_id,
                    player_id=new_player,
                    team_id=new_team,
                    role=obs.role,
                    sample_type=obs.sample_type,
                    confidence=obs.confidence,
                )
                cloned_obs.append(cloned)
            self.process_observations_batch(cloned_obs, final_time_s=final_time_s)
        else:
            self.process_observations_batch(observations, final_time_s=final_time_s)

    def export_raw_grid(self, output_path: str) -> None:
        """Save raw 2D grid mass and metadata to JSON or NPZ."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        if output_path.endswith(".npz"):
            np.savez_compressed(
                output_path,
                total_grid=self.total_grid,
                team_a_grid=self.team_a_grid,
                team_b_grid=self.team_b_grid,
                unknown_team_grid=self.unknown_team_grid,
                metadata=json.dumps(self.metadata.to_dict()),
            )
        else:
            payload = {
                "metadata": self.metadata.to_dict(),
                "total_grid": self.total_grid.tolist(),
                "team_a_grid": self.team_a_grid.tolist(),
                "team_b_grid": self.team_b_grid.tolist(),
                "unknown_team_grid": self.unknown_team_grid.tolist(),
            }
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)

    def render_png(
        self,
        output_path: str,
        title: str = "Court Occupancy Heatmap",
        grid_type: str = "total",  # "total", "team_a", "team_b", "unknown"
        colormap: str = "hot",
    ) -> None:
        """Render publication-quality court heatmap PNG with explicit units and legend."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        if grid_type == "team_a":
            target_grid = self.team_a_grid
            sub_title = f"{title} (Team A: {self.team_a_id})"
        elif grid_type == "team_b":
            target_grid = self.team_b_grid
            sub_title = f"{title} (Team B: {self.team_b_id})"
        elif grid_type == "unknown":
            target_grid = self.unknown_team_grid
            sub_title = f"{title} (Unknown Team)"
        else:
            target_grid = self.total_grid
            sub_title = title

        x_min, x_max = self.court_bounds["x_min"], self.court_bounds["x_max"]
        y_min, y_max = self.court_bounds["y_min"], self.court_bounds["y_max"]

        fig, ax = plt.subplots(figsize=(8, 7), dpi=150)
        extent = [x_min, x_max, y_min, y_max]

        im = ax.imshow(
            target_grid,
            extent=extent,
            origin="lower",
            cmap=colormap,
            aspect="auto",
            interpolation="gaussian",
        )

        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label("Occupancy (player-seconds)", fontsize=10)

        # Draw court outline rectangle
        ax.plot([x_min, x_max, x_max, x_min, x_min], [y_min, y_min, y_max, y_max, y_min], "w--", linewidth=1.2, alpha=0.8, label="Court Bounds")

        ax.set_title(sub_title, fontsize=12, pad=10)
        ax.set_xlabel(f"Court X ({self.units})", fontsize=10)
        ax.set_ylabel(f"Court Y ({self.units})", fontsize=10)

        # Legend / Telemetry textbox
        telemetry_text = (
            f"Total Mass: {self.metadata.total_player_seconds:.2f} p-s\n"
            f"Team A: {self.metadata.team_a_player_seconds:.2f} p-s\n"
            f"Team B: {self.metadata.team_b_player_seconds:.2f} p-s\n"
            f"Unknown: {self.metadata.unknown_team_player_seconds:.2f} p-s\n"
            f"Excluded: {self.metadata.excluded_player_seconds:.2f} p-s\n"
            f"Resolution: {self.dx:.2f}x{self.dy:.2f} {self.units}"
        )
        props = dict(boxstyle="round,pad=0.5", facecolor="black", alpha=0.7, edgecolor="gray")
        ax.text(0.03, 0.97, telemetry_text, transform=ax.transAxes, fontsize=8, verticalalignment="top", color="white", bbox=props)

        ax.grid(True, linestyle=":", alpha=0.3, color="gray")
        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close(fig)


def compute_court_region_stats(
    accumulator: HeatmapAccumulator,
    basket_xy: Tuple[float, float] = (0.0, 1.575),
) -> Dict[str, Any]:
    """
    Compute breakdown of player-seconds across standard basketball court regions:
    - Paint / Key: |x| <= 2.45m and 0.0 <= y <= 5.8m
    - Mid-Range: inside 3-point arc (dist <= 6.75m from basket) and outside paint
    - Three-Point: outside 3-point arc (dist > 6.75m from basket)

    Invariants:
    Total across all regions equals total_player_seconds accumulated on grid.
    """
    bounds = accumulator.court_bounds
    dx = accumulator.dx
    dy = accumulator.dy
    rows, cols = accumulator.grid_shape

    regions: Dict[str, Dict[str, float]] = {
        "paint": {"total_seconds": 0.0, "team_a_seconds": 0.0, "team_b_seconds": 0.0, "unknown_seconds": 0.0},
        "mid_range": {"total_seconds": 0.0, "team_a_seconds": 0.0, "team_b_seconds": 0.0, "unknown_seconds": 0.0},
        "three_point": {"total_seconds": 0.0, "team_a_seconds": 0.0, "team_b_seconds": 0.0, "unknown_seconds": 0.0},
    }

    bx, by = basket_xy

    for r in range(rows):
        y = bounds["y_min"] + (r + 0.5) * dy
        for c in range(cols):
            x = bounds["x_min"] + (c + 0.5) * dx
            tot = float(accumulator.total_grid[r, c])
            if tot <= 0.0:
                continue
            ta = float(accumulator.team_a_grid[r, c])
            tb = float(accumulator.team_b_grid[r, c])
            tu = float(accumulator.unknown_team_grid[r, c])

            dist = math.hypot(x - bx, y - by)
            if abs(x) <= 2.45 and 0.0 <= y <= 5.8:
                reg = "paint"
            elif dist <= 6.75:
                reg = "mid_range"
            else:
                reg = "three_point"

            regions[reg]["total_seconds"] += tot
            regions[reg]["team_a_seconds"] += ta
            regions[reg]["team_b_seconds"] += tb
            regions[reg]["unknown_seconds"] += tu

    for reg_data in regions.values():
        for k in list(reg_data.keys()):
            reg_data[k] = round(reg_data[k], 6)

    return regions


