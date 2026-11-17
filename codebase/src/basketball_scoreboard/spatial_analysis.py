"""Source-bound spatial map enrichment from saved human-tracking artifacts."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np

from .identity import RosterConfig
COLOR_METHOD = 'prototype_hue_votes_v2'
SPATIAL_ALGORITHM_VERSION = 2


class ConfigurationError(ValueError):
    pass


def read_rows(path):
    if Path(path).is_file():
        with Path(path).open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def default_config(job, roster):
    return dict(version=1, format="3x3", roster=roster, segments=[], assignments=[],
                exclusions=[], classify_teams=False,
                source_sha256=job.get("source_sha256"), width=job["width"], height=job["height"])


def _number(value, label, lower=0, upper=float("inf")):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not lower <= value <= upper:
        raise ConfigurationError(f"{label} không hợp lệ.")
    return float(value)


def validate_config(data, job):
    """Normalize untrusted input; reject stale source, conflicting identities and geometry."""
    try:
        if not isinstance(data, dict) or data.get("format") not in {"3x3", "5x5"}:
            raise ConfigurationError("Chọn thể thức 3×3 hoặc 5×5.")
        if (data.get("width"), data.get("height")) != (job["width"], job["height"]):
            raise ConfigurationError("Hiệu chuẩn không khớp kích thước video.")
        if data.get("source_sha256") != job.get("source_sha256"):
            raise ConfigurationError("Cấu hình không thuộc video đang chọn.")
        if not isinstance(data.get("roster"), dict):
            raise ConfigurationError("Danh sách đội và cầu thủ không hợp lệ.")
        roster = RosterConfig.from_dict(data["roster"])
        if len(roster.players) > 50 or any(len(p.name) > 100 or len(p.jersey_number) > 8 for p in roster.players):
            raise ConfigurationError("Danh sách cầu thủ quá dài.")
        if any(len(n) > 100 for n in [roster.team_a_name, roster.team_b_name]):
            raise ConfigurationError("Tên đội quá dài.")
        normalized = default_config(job, roster.to_dict())
        normalized.update(format=data["format"],
                          classify_teams=data.get("classify_teams", False) is True)
        if normalized["classify_teams"] and np.linalg.norm(np.array(roster.team_a_color_rgb) - roster.team_b_color_rgb) < 45:
            raise ConfigurationError("Chọn hai màu áo khác nhau để nhận diện đội.")
        segments, exclusions, assignments = data.get("segments", []), data.get("exclusions", []), data.get("assignments", [])
        if not all(isinstance(items, list) for items in [segments, exclusions, assignments]) or len(segments) > 300 or len(assignments) > 10000 or len(exclusions) > 1000:
            raise ConfigurationError("Quá nhiều vùng cấu hình.")
        ymax = 11 if data["format"] == "3x3" else 28
        for item in segments:
            start = _number(item["start_s"], "Mốc bắt đầu", upper=job["duration_s"])
            end = _number(item["end_s"], "Mốc kết thúc", lower=start, upper=job["duration_s"])
            anchor = _number(item["anchor_s"], "Khung hình hiệu chuẩn", lower=start, upper=end)
            if end <= start:
                raise ConfigurationError("Khoảng hiệu chuẩn phải có độ dài dương.")
            points = item["points"]
            if not isinstance(points, list) or not 4 <= len(points) <= 30:
                raise ConfigurationError("Cần ít nhất bốn mốc sân không thẳng hàng.")
            clean = []
            for point in points:
                image, court = point["image"], point["court"]
                if len(image) != 2 or len(court) != 2:
                    raise ConfigurationError("Mốc sân cần hai tọa độ.")
                clean.append(dict(image=[_number(image[0], "Tọa độ ảnh", upper=job["width"]), _number(image[1], "Tọa độ ảnh", upper=job["height"])],
                                  court=[_number(court[0], "Tọa độ sân", -7.5, 7.5), _number(court[1], "Tọa độ sân", upper=ymax)]))
            image = np.float64([p["image"] for p in clean])
            court = np.float64([p["court"] for p in clean])
            if len(np.unique(image, axis=0)) < 4 or cv2.contourArea(cv2.convexHull(image.astype(np.float32))) < 100:
                raise ConfigurationError("Các mốc ảnh quá gần nhau hoặc thẳng hàng.")
            h, _ = cv2.findHomography(image, court, 0)
            if h is None or not np.isfinite(h).all() or np.linalg.matrix_rank(h) < 3:
                raise ConfigurationError("Không tính được phép ánh xạ sân.")
            reprojection = cv2.perspectiveTransform(court.reshape(1, -1, 2), np.linalg.inv(h))[0]
            residual = float(np.max(np.linalg.norm(reprojection - image, axis=1)))
            if residual > 15:
                raise ConfigurationError("Các mốc sân không nhất quán (sai số trên 15 pixel).")
            normalized["segments"].append(dict(start_s=start, end_s=end, anchor_s=anchor, points=clean, max_residual_px=round(residual, 3)))
        normalized["segments"].sort(key=lambda s: s["start_s"])
        if any(a["end_s"] > b["start_s"] for a, b in zip(normalized["segments"], normalized["segments"][1:])):
            raise ConfigurationError("Các khoảng hiệu chuẩn không được chồng nhau.")
        for item in exclusions:
            start = _number(item["start_s"], "Mốc loại trừ", upper=job["duration_s"])
            end = _number(item["end_s"], "Mốc loại trừ", lower=start, upper=job["duration_s"])
            if end <= start:
                raise ConfigurationError("Khoảng loại trừ phải có độ dài dương.")
            normalized["exclusions"].append(dict(start_s=start, end_s=end))
        player_map = {p.player_id: p for p in roster.players}
        teams = {roster.team_a_id, roster.team_b_id}
        for item in assignments:
            tid = item["track_id"]
            if not isinstance(tid, str) or not 0 < len(tid) <= 200:
                raise ConfigurationError("Mã theo dõi không hợp lệ.")
            role = item.get("role", "player")
            pid, team = item.get("player_id") or None, item.get("team_id") or None
            if role not in {"player", "non_player"} or (team is not None and team not in teams) or (pid and pid not in player_map):
                raise ConfigurationError("Đội hoặc cầu thủ được gán không hợp lệ.")
            if pid:
                if team and team != player_map[pid].team_id:
                    raise ConfigurationError("Cầu thủ không thuộc đội đã chọn.")
                team = player_map[pid].team_id
            start = _number(item.get("start_s", 0), "Khoảng gán danh tính", upper=job["duration_s"])
            end = _number(item.get("end_s", job["duration_s"]), "Khoảng gán danh tính", lower=start, upper=job["duration_s"])
            if end <= start:
                raise ConfigurationError("Khoảng gán danh tính phải có độ dài dương.")
            if role == "non_player":
                pid = team = None
            normalized["assignments"].append(dict(track_id=tid, role=role, player_id=pid, team_id=team, start_s=start, end_s=end))
        by_track = defaultdict(list)
        for item in normalized["assignments"]:
            by_track[item["track_id"]].append(item)
        for items in by_track.values():
            items.sort(key=lambda v: v["start_s"])
            if any(a["end_s"] > b["start_s"] for a, b in zip(items, items[1:])):
                raise ConfigurationError("Một mã theo dõi có các khoảng gán chồng nhau.")
        return normalized
    except ConfigurationError:
        raise
    except (KeyError, TypeError, ValueError, OverflowError, cv2.error, np.linalg.LinAlgError) as exc:
        raise ConfigurationError("Cấu hình trận đấu hoặc mốc sân không hợp lệ.") from exc


def config_revision(config):
    payload = dict(algorithm=SPATIAL_ALGORITHM_VERSION, config=config)
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True).encode()).hexdigest()[:16]


class SpatialProjector:
    def __init__(self, config):
        self.segments = []
        self.exclusions = config["exclusions"]
        self.bounds = dict(x_min=-7.5, x_max=7.5, y_min=0, y_max=11 if config["format"] == "3x3" else 28)
        for index, s in enumerate(config["segments"]):
            h, _ = cv2.findHomography(np.float64([p["image"] for p in s["points"]]), np.float64([p["court"] for p in s["points"]]), 0)
            self.segments.append((s, h, index))

    def excluded(self, t):
        return any(e["start_s"] <= t < e["end_s"] for e in self.exclusions)

    def project(self, xy, t):
        if self.excluded(t):
            return None, None
        for s, h, index in self.segments:
            if s["start_s"] <= t < s["end_s"]:
                q = h @ [*xy, 1.0]
                if abs(q[2]) < 1e-8:
                    return None, None
                x, y = q[:2] / q[2]
                if math.isfinite(x) and math.isfinite(y) and -7.5 <= x <= 7.5 and 0 <= y <= self.bounds["y_max"]:
                    return [round(float(x), 4), round(float(y), 4)], index
        return None, None

    def uninterrupted(self, a, b):
        return not any(e["start_s"] < b and e["end_s"] > a for e in self.exclusions)


def _identity(obs, assignments, players, teams):
    t, track = obs["source_time_s"], obs["track_id"]
    for item in assignments.get(track, []):
        if item["start_s"] <= t < item["end_s"]:
            return item["team_id"], item["player_id"], item["role"], "manual"
    pid, team = obs.get("player_id"), obs.get("team_id")
    if pid not in players:
        pid = None
    if pid:
        team = players[pid].team_id
    if team not in teams:
        team = None
    return team, pid, obs.get("role", "unknown"), "automatic" if pid or team else "unknown"


def infer_team_votes(directory, frames, roster, progress=None):
    """Read sparse torso crops from the original video; no detector/API calls."""
    import av
    from .identity import extract_jersey_rgb
    votes, seen = defaultdict(Counter), Counter()
    selected = []
    last = -1.0
    for frame in frames:
        if frame["time"] - last >= .5 and any(seen[p["id"]] < 5 for p in frame["players"]):
            selected.append(frame)
            for p in frame["players"]:
                seen[p["id"]] += 1
            last = frame["time"]
    # Decode sequentially: repeatedly seeking an inter-frame codec decodes the
    # same GOP many times. Convert only the sparse selected frames to RGB/BGR.
    with av.open(str(directory / "input.mp4")) as container:
        stream = container.streams.video[0]
        stream.thread_type = 'AUTO'
        first_time = None
        index = 0
        for frame_index, decoded in enumerate(container.decode(stream)):
            if index >= len(selected):
                break
            target_index = selected[index].get('frame_index')
            if target_index is not None:
                if frame_index < target_index:
                    continue
                if frame_index != target_index:
                    index += 1
                    continue
            else:
                # Compatibility for older frame bundles without frame indices.
                if decoded.time is None:
                    continue
                if first_time is None:
                    first_time = float(decoded.time)
                source_time = float(decoded.time)-first_time
                while index < len(selected) and selected[index]['time'] < source_time - .05:
                    index += 1
                if index >= len(selected):
                    break
                if source_time + .001 < selected[index]['time']:
                    continue
            frame = selected[index]
            bgr = decoded.to_ndarray(format='bgr24')
            for p in frame["players"]:
                x1, y1, x2, y2 = p["box"]
                w, h = x2 - x1, y2 - y1
                left, right = max(0, int(x1 + .2*w)), min(bgr.shape[1], int(x2 - .2*w))
                top, bottom = max(0, int(y1 + .15*h)), min(bgr.shape[0], int(y1 + .55*h))
                if right <= left or bottom <= top:
                    continue
                rgb, evidence = extract_jersey_rgb(bgr[top:bottom, left:right], [roster.team_a_color_rgb, roster.team_b_color_rgb])
                if rgb:
                    # The prototype mask already checked hue, saturation, pixel
                    # fraction and ambiguity. Raw RGB distance can incorrectly
                    # flip a shadowed yellow jersey to red; retain its hue vote.
                    winner = int(np.argmax(evidence['fractions']))
                    votes[p['id']][[roster.team_a_id, roster.team_b_id][winner]] += 1
            index += 1
            if progress and index % 10 == 0:
                progress("colors", index, len(selected))
    resolved = {}
    for track, counts in votes.items():
        team, count = counts.most_common(1)[0]
        if count >= 3 and count / sum(counts.values()) >= .8:
            resolved[track] = team
    return resolved


def build_spatial_analysis(directory, config, progress=None):
    """Build court positions and time-weighted heatmaps from observed player tracks."""
    directory = Path(directory)
    analysis = directory / "analysis"
    roster = RosterConfig.from_dict(config["roster"])
    players = {p.player_id: p for p in roster.players}
    teams = {roster.team_a_id, roster.team_b_id}
    assignments = defaultdict(list)
    for item in config["assignments"]:
        assignments[item["track_id"]].append(item)
    projector = SpatialProjector(config)
    tracks, frames, last, actor_last = {}, {}, {}, {}
    grids = {"all": np.zeros((44, 60))}
    unassigned_grids = {}
    heatmap_intervals, interval_by_track = [], {}
    max_gap = .3
    observations_path = analysis / "tracking" / "tracked_observations.jsonl"
    for i, obs in enumerate(read_rows(observations_path)):
        track = obs.get("track_id")
        if (obs.get("sample_type") != "observed" or not obs.get("track_id")
                or obs.get("timestamp_status", "valid") not in {"valid", "repaired"}):
            last.pop(track, None)
            continue
        t, track = float(obs["source_time_s"]), obs["track_id"]
        team, pid, role, origin = _identity(obs, assignments, players, teams)
        tr = tracks.setdefault(track, dict(id=track, start_s=t, end_s=t, samples=0, team_id=team, player_id=pid, role=role))
        tr.update(end_s=t, samples=tr["samples"]+1)
        tr.update(team_id=team, player_id=pid, role=role)
        if role == "non_player" or projector.excluded(t):
            last.pop(track, None)
            continue
        key = "player:" + pid if pid else "track:" + track
        xy = None
        segment = None
        # Cropped feet / predicted points cannot create physical coordinates.
        if obs.get("validity_status") in {"valid", "outside_roi", "outside_court_bounds", "degenerate_projection"}:
            foot = obs.get("footpoint_image") or [(obs["bbox"][0]+obs["bbox"][2])/2, obs["bbox"][3]]
            xy, segment = projector.project(foot, t)
        old = last.get(track)
        if old and old["key"] == key and old["team"] == team and old["role"] == role:
            dt = t-old["t"]
            if 0 < dt <= max_gap and projector.uninterrupted(old["t"], t):
                # Overlapping tracks assigned to one player cannot double-count occupancy.
                actor_time = actor_last.get(key, -1)
                if old["t"] >= actor_time - 1e-6:
                    if xy is not None and old["xy"] is not None and old["segment"] == segment:
                        displacement = math.dist(old["xy"], xy)
                        if displacement <= 12 * dt:
                            actor_last[key] = t
                            x, y = old["xy"]
                            col = min(59, int((x+7.5)/15*60))
                            row = min(43, int(y/projector.bounds["y_max"]*44))
                            keys = ["all", "track:"+track]
                            if team:
                                keys.append("team:"+team)
                            if pid:
                                keys.append("player:"+pid)
                            for grid_key in keys:
                                grids.setdefault(grid_key, np.zeros((44, 60)))[row, col] += dt
                            color_eligible = not team and old['origin'] != 'manual' and origin != 'manual'
                            if color_eligible:
                                unassigned_grids.setdefault(track, np.zeros((44, 60)))[row, col] += dt
                            # Preserve accepted intervals for exact time-window
                            # queries; merge adjacent stays in the same cell.
                            entry = [old['t'], t, row, col, track, team, pid, color_eligible]
                            previous = interval_by_track.get(track)
                            if previous is not None and previous[1] == entry[0] and previous[2:] == entry[2:]:
                                previous[1] = t
                            else:
                                heatmap_intervals.append(entry)
                                interval_by_track[track] = entry
        last[track] = dict(t=t, xy=xy, segment=segment, key=key, team=team, role=role, origin=origin)
        # 5 Hz playback, retaining every observed person in the selected frame.
        bucket = int(t*5 + 1e-8)
        frame = frames.setdefault(bucket, dict(time=t, players=[], segment=segment, frame_index=obs.get('frame_index')))
        if abs(frame["time"]-t) < .001:
            frame["players"].append(dict(id=track, player_id=pid, team_id=team, origin=origin, role=role,
                                         xy=xy, box=obs["bbox"]))
        if progress and i % 25000 == 0:
            progress("tracks", i, 0)
    ordered = sorted(frames.values(), key=lambda f: f["time"])
    color_teams = {}
    color_tracks = set()
    color_input_signature = None
    if config.get("classify_teams"):
        color_input_signature = hashlib.sha256(json.dumps(
            [(f['time'], f.get('frame_index'), [(p['id'], p['box']) for p in f['players']]) for f in ordered],
            separators=(',', ':')).encode()).hexdigest()
        # Reuse evidence for the same source tracks, colors and exclusion scope.
        # Mapping a name or moving court landmarks must not decode the whole video again.
        previous_path = directory / 'spatial_map.json'
        if previous_path.is_file():
            previous_result = json.loads(previous_path.read_text(encoding='utf-8'))
            old_roster = previous_result.get('roster', {})
            fields = ['team_a_id', 'team_b_id', 'team_a_color_rgb', 'team_b_color_rgb']
            signature = lambda rows: [(r['id'], r['start_s'], r['end_s'], r['samples']) for r in rows]
            has_color_evidence = previous_result.get('color_classification_enabled', False) and previous_result.get('color_method') == COLOR_METHOD
            if (has_color_evidence and all(old_roster.get(k) == config['roster'][k] for k in fields)
                    and previous_result.get('color_input_signature') == color_input_signature
                    and previous_result.get('color_scope', []) == config['exclusions']
                    and signature(previous_result.get('tracks', [])) == signature(tracks.values())):
                color_teams = previous_result.get('color_teams', {})
                if not color_teams:
                    color_teams = {p['id']: p['team_id'] for f in previous_result.get('frames', []) for p in f['players'] if p.get('origin') == 'color_estimate'}
                color_tracks = set(previous_result.get('color_tracks', []))
                if not color_tracks:
                    color_tracks = {p['id'] for f in previous_result.get('frames', []) for p in f['players']}
        remaining = [dict(f, players=[p for p in f['players'] if p['id'] not in color_tracks]) for f in ordered]
        remaining = [f for f in remaining if f['players']]
        if remaining:
            color_teams.update(infer_team_votes(directory, remaining, roster, progress))
        color_tracks.update(p['id'] for f in ordered for p in f['players'])
        # Color evidence is a team suggestion, never a jersey identity or role proof.
        for frame in ordered:
            for person in frame["players"]:
                if person["origin"] != "manual" and not person["team_id"] and person["id"] in color_teams:
                    person.update(team_id=color_teams[person["id"]], origin="color_estimate")
        for track, team in color_teams.items():
            if track not in tracks:
                continue
            if tracks[track]["team_id"] is None and not assignments.get(track):
                tracks[track]["team_id"] = team
            grid = unassigned_grids.get(track)
            if grid is not None:
                grids.setdefault("team:"+team, np.zeros((44, 60)))[:] += grid
    for interval in heatmap_intervals:
        if interval[7] and interval[4] in color_teams:
            interval[5] = color_teams[interval[4]]
        del interval[7:]
    return dict(version=SPATIAL_ALGORITHM_VERSION, revision=config_revision(config), status="completed", format=config["format"],
                bounds=projector.bounds, roster=roster.to_dict(), tracks=list(tracks.values()),
                frames=ordered,
                color_teams=color_teams, color_tracks=sorted(color_tracks), color_scope=config['exclusions'], color_classification_enabled=config.get('classify_teams', False), color_method=COLOR_METHOD,
                color_input_signature=color_input_signature,
                heatmaps={k:v.round(6).tolist() for k,v in grids.items()},
                heatmap_intervals=heatmap_intervals,
                calibration_segments=len(config["segments"]))
