"""Source-bound spatial map enrichment from saved human-tracking artifacts."""
from __future__ import annotations

from collections import Counter, defaultdict
from bisect import bisect_right
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np

from .identity import RosterConfig
from .court import CourtError, PointCorrespondence, court_markings, project_point, solve_homography
from .spatial_intervals import (OccupancyInterval, continuity_reason, grid_shape_for_bounds,
                                resolve_identity_overlaps, source_scope, unique_position_markers)
COLOR_METHOD = 'prototype_hue_votes_v2'
SPATIAL_ALGORITHM_VERSION = 6


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
                cell_size_m=.25, max_gap_s=.3, max_speed_m_s=12.,
                fps=job.get('fps', 30),
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
        normalized['geometry_mode'] = data.get('geometry_mode', 'legacy_manual' if data.get('segments') else 'automatic')
        if normalized['geometry_mode'] not in {'automatic', 'legacy_manual'}:
            raise ConfigurationError('Invalid geometry mode')
        if normalized['geometry_mode'] == 'automatic':
            # Supplying different team colors always enables automatic teams.
            normalized['classify_teams'] = bool(np.linalg.norm(np.array(roster.team_a_color_rgb)-roster.team_b_color_rgb) >= 45)
        for field, default, low, high in [('cell_size_m', .25, .1, 1.), ('max_gap_s', .3, .02, 1.),
                                           ('max_speed_m_s', 12., 1., 20.)]:
            normalized[field] = _number(data.get(field, default), field, low, high)
        if normalized["classify_teams"] and np.linalg.norm(np.array(roster.team_a_color_rgb) - roster.team_b_color_rgb) < 45:
            raise ConfigurationError("Chọn hai màu áo khác nhau để nhận diện đội.")
        segments, exclusions, assignments = data.get("segments", []), data.get("exclusions", []), data.get("assignments", [])
        if not all(isinstance(items, list) for items in [segments, exclusions, assignments]) or len(segments) > 300 or len(assignments) > 10000 or len(exclusions) > 1000:
            raise ConfigurationError("Quá nhiều vùng cấu hình.")
        ymax = 11 if data["format"] == "3x3" else 28
        for item in segments:
            start = _number(item["start_s"], "Mốc bắt đầu", upper=job["duration_s"])
            end = _number(item["end_s"], "Mốc kết thúc", lower=start, upper=job["duration_s"])
            anchor = _number(item.get("anchor_s", item["start_s"]), "Khung hình hiệu chuẩn", lower=start, upper=end)
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
                usage = point.get('usage', 'fit')
                if usage not in {'fit', 'check'}:
                    raise ConfigurationError('Chọn mốc khớp hoặc mốc kiểm tra.')
                clean.append(dict(image=[_number(image[0], "Tọa độ ảnh", upper=job["width"]), _number(image[1], "Tọa độ ảnh", upper=job["height"])],
                                  court=[_number(court[0], "Tọa độ sân", -7.5, 7.5), _number(court[1], "Tọa độ sân", upper=ymax)], usage=usage))
            image = np.float64([p["image"] for p in clean])
            court = np.float64([p["court"] for p in clean])
            if len(np.unique(image, axis=0)) < 4 or cv2.contourArea(cv2.convexHull(image.astype(np.float32))) < 100:
                raise ConfigurationError("Các mốc ảnh quá gần nhau hoặc thẳng hàng.")
            solved = solve_segment(clean)
            residual = max([solved.max_fit_residual_px, *(solved.check_residuals_px or [])])
            if residual > 15:
                raise ConfigurationError("Các mốc sân không nhất quán (sai số trên 15 pixel).")
            roi = item.get('roi_image', [])
            if not isinstance(roi, list) or (roi and not 3 <= len(roi) <= 30):
                raise ConfigurationError('ROI cần từ 3 đến 30 đỉnh.')
            roi = [[_number(p[0], 'ROI X', upper=job['width']), _number(p[1], 'ROI Y', upper=job['height'])]
                   for p in roi if isinstance(p, (list, tuple)) and len(p) == 2]
            if len(roi) != len(item.get('roi_image', [])) or (roi and cv2.contourArea(np.float32(roi)) < 100):
                raise ConfigurationError('ROI sân không hợp lệ.')
            if roi:
                denominators = np.c_[np.float64(roi), np.ones(len(roi))] @ solved.matrix_image_to_court[2]
                if np.min(np.abs(denominators)) < 1e-8 or np.min(denominators)*np.max(denominators) <= 0:
                    raise ConfigurationError('ROI không được đi qua đường suy biến của phép chiếu.')
            keyframes = item.get('keyframes', [])
            if not isinstance(keyframes, list) or len(keyframes) > 6000:
                raise ConfigurationError('Quá nhiều khung hiệu chuẩn chuyển động.')
            dynamic = []
            previous = -1.
            for frame in keyframes:
                frame_time = _number(frame['time_s'], 'Thời gian hiệu chuẩn', start, end)
                images = frame['image_points']
                if frame_time <= previous or not isinstance(images, list) or len(images) != len(clean):
                    raise ConfigurationError('Khung hiệu chuẩn phải tăng theo thời gian và giữ cùng bộ mốc.')
                if any(not isinstance(p, (list, tuple)) or len(p) != 2 for p in images):
                    raise ConfigurationError('Mốc hiệu chuẩn cần đúng hai tọa độ.')
                images = [[_number(p[0], 'Mốc X', upper=job['width']), _number(p[1], 'Mốc Y', upper=job['height'])] for p in images]
                measured = solve_segment([dict(p, image=q) for p, q in zip(clean, images)])
                if max([measured.max_fit_residual_px, *(measured.check_residuals_px or [])]) > 15:
                    raise ConfigurationError('Mốc hiệu chuẩn chuyển động không nhất quán.')
                dynamic.append(dict(time_s=frame_time, image_points=images))
                previous = frame_time
            normalized["segments"].append(dict(start_s=start, end_s=end, anchor_s=anchor, points=clean,
                roi_image=roi, enabled=item.get('enabled', True) is True, max_residual_px=round(residual, 3),
                check_residuals_px=solved.check_residuals_px or [],
                quality='checked_landmarks' if solved.check_residuals_px else 'fit_only', keyframes=dynamic))
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
            if role not in {"player", "non_player", "referee"} or (team is not None and team not in teams) or (pid and pid not in player_map):
                raise ConfigurationError("Đội hoặc cầu thủ được gán không hợp lệ.")
            if pid:
                if team and team != player_map[pid].team_id:
                    raise ConfigurationError("Cầu thủ không thuộc đội đã chọn.")
                team = player_map[pid].team_id
            start = _number(item.get("start_s", 0), "Khoảng gán danh tính", upper=job["duration_s"])
            end = _number(item.get("end_s", job["duration_s"]), "Khoảng gán danh tính", lower=start, upper=job["duration_s"])
            if end == start:
                fps = job.get("fps", 30)
                step = 1 / fps if isinstance(fps, (float, int)) and math.isfinite(fps) and fps > 0 else 1 / 30
                end = min(float(job["duration_s"]), float(start) + step)
            if end <= start:
                continue
            if role in {"non_player", "referee"}:
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
    except (KeyError, IndexError, TypeError, ValueError, OverflowError, CourtError, cv2.error, np.linalg.LinAlgError) as exc:
        raise ConfigurationError("Cấu hình trận đấu hoặc mốc sân không hợp lệ.") from exc


def config_revision(config):
    payload = dict(algorithm=SPATIAL_ALGORITHM_VERSION, config=config)
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True).encode()).hexdigest()[:16]


def solve_segment(points):
    return solve_homography([PointCorrespondence(str(i), str(i), tuple(p['image']), tuple(p['court']),
                                                usage=p.get('usage', 'fit')) for i, p in enumerate(points)])


def calibration_preview(config):
    """Image-space diagnostics only; never claim independent ground-truth accuracy."""
    result = []
    ymax = 11 if config['format'] == '3x3' else 28
    for segment in config['segments']:
        solved = solve_segment(segment['points'])
        h = solved.matrix_court_to_image
        lines = []
        for y in np.arange(0, ymax + .1, 1.):
            lines.append([project_point((-7.5, y), h), project_point((7.5, y), h)])
        for x in np.arange(-7.5, 7.6, 1.):
            lines.append([project_point((x, 0.), h), project_point((x, ymax), h)])
        for polyline in court_markings(dict(x_min=-7.5,x_max=7.5,y_min=0,y_max=ymax)):
            for a,b in zip(polyline,polyline[1:]):
                lines.append([project_point(a,h),project_point(b,h)])
        result.append(dict(start_s=segment['start_s'], end_s=segment['end_s'],
                           lines=[line for line in lines if all(p is not None for p in line)],
                           fit_residuals_px=solved.fit_residuals_px, check_residuals_px=solved.check_residuals_px or []))
    return result


class SpatialProjector:
    def __init__(self, config):
        self.segments = []
        self.dynamic = {}
        self.dynamic_rois = {}
        self.geometry_gaps = []
        fps = config.get('fps', 30)
        self.keyframe_tolerance_s = .5/fps if isinstance(fps, (int, float)) and math.isfinite(fps) and fps > 0 else 1/60
        self.exclusions = config["exclusions"]
        self.bounds = dict(x_min=-7.5, x_max=7.5, y_min=0, y_max=11 if config["format"] == "3x3" else 28)
        for index, s in enumerate(config["segments"]):
            h = solve_segment(s['points']).matrix_image_to_court
            self.segments.append((s, h, index))
            if s.get('keyframes'):
                if s.get('roi_image'):
                    polygon=[project_point(p,h) for p in s['roi_image']]
                    if any(p is None for p in polygon):
                        raise ConfigurationError('Không chiếu được vùng mặt sân.')
                    self.dynamic_rois[index]=np.float32(polygon)
                times, matrices = [], []
                for frame in s['keyframes']:
                    times.append(frame['time_s'])
                    matrices.append(solve_segment([dict(p, image=q) for p, q in zip(s['points'], frame['image_points'])]).matrix_image_to_court)
                self.dynamic[index] = (times, matrices)
                self.geometry_gaps.extend((a+self.keyframe_tolerance_s,b) for a,b in zip(times,times[1:])
                                          if b-a > 3*self.keyframe_tolerance_s+1e-6)

    def excluded(self, t):
        return any(e["start_s"] <= t < e["end_s"] for e in self.exclusions)

    def project(self, xy, t):
        if self.excluded(t):
            return None, None
        for s, h, index in self.segments:
            if s["start_s"] <= t < s["end_s"]:
                if not s.get('enabled', True):
                    return None, None
                if index in self.dynamic:
                    times, matrices = self.dynamic[index]
                    selected = bisect_right(times, t+1e-6)-1
                    if selected < 0 or t-times[selected] > self.keyframe_tolerance_s + 1e-6:
                        return None, None
                    h = matrices[selected]
                if s.get('roi_image') and index not in self.dynamic and cv2.pointPolygonTest(np.float32(s['roi_image']), tuple(map(float, xy)), False) < 0:
                    return None, None
                q = h @ [*xy, 1.0]
                if abs(q[2]) < 1e-8:
                    return None, None
                x, y = q[:2] / q[2]
                if index in self.dynamic_rois and math.isfinite(x) and math.isfinite(y):
                    if cv2.pointPolygonTest(self.dynamic_rois[index], (float(x),float(y)), False) < 0:
                        return None, None
                if math.isfinite(x) and math.isfinite(y) and -7.5 <= x <= 7.5 and 0 <= y <= self.bounds["y_max"]:
                    return [round(float(x), 4), round(float(y), 4)], index
        return None, None

    def uninterrupted(self, a, b):
        return (not any(e["start_s"] < b and e["end_s"] > a for e in self.exclusions)
                and not any(start < b and end > a for start,end in self.geometry_gaps))


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


def infer_team_votes(directory, frames, roster, progress=None, *, video_path=None):
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
    with av.open(str(video_path or directory / "input.mp4")) as container:
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


def build_spatial_analysis(directory, config, progress=None, *, analysis_dir=None, source_video_path=None):
    """Build court positions and time-weighted heatmaps from observed player tracks."""
    directory = Path(directory)
    analysis = Path(analysis_dir) if analysis_dir else directory / "analysis"
    roster = RosterConfig.from_dict(config["roster"])
    players = {p.player_id: p for p in roster.players}
    teams = {roster.team_a_id, roster.team_b_id}
    assignments = defaultdict(list)
    for item in config["assignments"]:
        assignments[item["track_id"]].append(item)
    geometry = None
    automatic_mode = config.get('geometry_mode', 'legacy_manual' if config.get('segments') else 'automatic') == 'automatic'
    if automatic_mode:
        from .automatic_court import AutomaticProjector, load_automatic_geometry
        path = analysis/'automatic_geometry.json'
        if path.is_file():
            geometry = load_automatic_geometry(path,config['source_sha256'],config['width'],config['height'],config['format'])
        else:
            geometry = dict(frames=[],fps=config.get('fps',30),format=config['format'],supported_frames=0,total_frames=0)
        projector = AutomaticProjector(geometry,config['exclusions'])
    else:
        projector = SpatialProjector(config)
    tracks, frames, last = {}, {}, {}
    shape = grid_shape_for_bounds(projector.bounds, config.get('cell_size_m', .25))
    grids = {"all": np.zeros(shape), 'unknown_role': np.zeros(shape)}
    unassigned_grids = {}
    heatmap_intervals, interval_by_track = [], {}
    unknown_intervals, candidates, unknown_candidates = [], [], []
    counters = Counter()
    max_gap = config.get('max_gap_s', .3)
    observations_path = analysis / "tracking" / "tracked_observations.jsonl"
    if not observations_path.is_file():
        observations_path = analysis / "tracked_observations.jsonl"
    if not observations_path.is_file():
        observations_path = directory / "tracked_observations.jsonl"
    if not observations_path.is_file():
        raise FileNotFoundError("Missing source tracking observations")
    automatic_teams = None
    if automatic_mode and config.get('classify_teams'):
        # Re-evaluate colors on the same immutable tracks, keeping manual
        # identities attached when team prototypes change after inference.
        fields = ['team_a_id','team_b_id','team_a_color_rgb','team_b_color_rgb']
        with observations_path.open('rb') as source:
            observation_hash = hashlib.file_digest(source,'sha256').hexdigest()
        signature = hashlib.sha256(json.dumps(dict(source=config.get('source_sha256'),
            observations=observation_hash,roster={k:config['roster'][k] for k in fields},
            exclusions=config['exclusions'],method=COLOR_METHOD),sort_keys=True).encode()).hexdigest()
        cache_path = analysis/'automatic_team_evidence.json'
        try:
            cached = json.loads(cache_path.read_text(encoding='utf-8'))
            if cached.get('signature') == signature and isinstance(cached.get('teams'),dict):
                automatic_teams = cached['teams']
        except (OSError,ValueError):
            pass
        if automatic_teams is None:
            color_frames = {}
            for obs in read_rows(observations_path):
                if obs.get('sample_type') != 'observed' or obs.get('role') == 'non_player':
                    continue
                t = obs['source_time_s']
                if projector.excluded(t):
                    continue
                bucket = int(t*2+1e-8)
                frame = color_frames.setdefault(bucket,dict(time=t,frame_index=obs.get('frame_index'),players=[]))
                if abs(frame['time']-t)<.001:
                    frame['players'].append(dict(id=obs['track_id'],box=obs['bbox']))
            options = dict(video_path=source_video_path) if source_video_path else {}
            automatic_teams = infer_team_votes(directory, list(color_frames.values()), roster, progress, **options)
            from .web_jobs import write_json
            write_json(cache_path,dict(signature=signature,teams=automatic_teams))
    jersey_identity = None
    identity_summary = dict(status='no_roster',named_players=0,named_tracks=0)
    if automatic_mode and any(p.is_active for p in roster.players):
        if automatic_teams:
            from .jersey_identity import extract_jersey_evidence,JerseyIdentityTimeline
            evidence = extract_jersey_evidence(directory,observations_path,config['source_sha256'],automatic_teams,
                video_path=source_video_path,progress=progress)
            jersey_identity = JerseyIdentityTimeline(observations_path,roster,automatic_teams,evidence)
            identity_summary = jersey_identity.summary
        else:
            identity_summary = dict(status='unresolved_team',named_players=0,named_tracks=0)
    for i, obs in enumerate(read_rows(observations_path)):
        counters['observations'] += 1
        track = obs.get("track_id")
        if (obs.get("sample_type") != "observed" or not obs.get("track_id")
                or obs.get("timestamp_status", "valid") not in {"valid", "repaired"}):
            last.pop(track, None)
            continue
        t, track = float(obs["source_time_s"]), obs["track_id"]
        counters['observed'] += 1
        if automatic_teams is not None:
            obs = dict(obs,team_id=automatic_teams.get(track),player_id=None)
            if obs.get('role') not in {'non_player','referee'}:
                obs['role'] = 'player' if obs['team_id'] else 'unknown'
        if jersey_identity:
            obs = dict(obs,player_id=jersey_identity.at(track,t))
        team, pid, role, origin = _identity(obs, assignments, players, teams)
        tr = tracks.setdefault(track, dict(id=track, start_s=t, end_s=t, samples=0, team_id=team, player_id=pid, role=role))
        tr.update(end_s=t, samples=tr["samples"]+1)
        tr.update(team_id=team, player_id=pid, role=role)
        if role == "non_player" or projector.excluded(t):
            last.pop(track, None)
            continue
        xy = None
        segment = None
        # Cropped feet / predicted points cannot create physical coordinates.
        if obs.get("validity_status") in {"valid", "outside_roi", "outside_court_bounds", "degenerate_projection"}:
            foot = obs.get("footpoint_image") or [(obs["bbox"][0]+obs["bbox"][2])/2, obs["bbox"][3]]
            xy, segment = projector.project(foot, t)
        old = last.get(track)
        current = dict(t=t, xy=xy, segment=segment, team_id=team, player_id=pid, track_id=track,
                       role=role, origin=origin, scope=source_scope(obs), confidence=obs.get('confidence', 0),
                       frame_index=obs.get('frame_index'))
        continuous = False
        if old:
            reason = continuity_reason(old, current, max_gap, config.get('max_speed_m_s', 12.), allow_unknown_role=True)
            if reason is None and not projector.uninterrupted(old['t'], t):
                reason = 'excluded_interval'
            if reason:
                counters[reason + '_intervals'] += 1
            else:
                continuous = (current['frame_index'] is not None and old['frame_index'] is not None
                              and current['frame_index'] == old['frame_index'] + 1)
                target = candidates if role == 'player' else unknown_candidates
                target.append(OccupancyInterval(old['t'], t, dict(old, color_eligible=old['origin'] != 'manual' and origin != 'manual')))
        current['continuity_start_s'] = old['continuity_start_s'] if continuous else t
        last[track] = current
        counters['projectable'] += xy is not None
        # 5 Hz playback, retaining every observed person in the selected frame.
        bucket = int(t*5 + 1e-8)
        frame = frames.setdefault(bucket, dict(time=t, players=[], segment=segment, frame_index=obs.get('frame_index')))
        if abs(frame["time"]-t) < .001:
            frame["players"].append(dict(id=track, player_id=pid, team_id=team, origin=origin, role=role,
                                         xy=xy, box=obs["bbox"], confidence=obs.get('confidence', 0),
                                         segment=segment, source_scope=list(source_scope(obs)),
                                         continuity_start_s=current['continuity_start_s']))
        if progress and i % 25000 == 0:
            progress("tracks", i, 0)
    ordered = sorted(frames.values(), key=lambda f: f["time"])
    for frame in ordered:
        counters['duplicate_identity_markers'] += unique_position_markers(frame['players'])
    accepted = resolve_identity_overlaps(candidates)
    counters['identity_overlap_seconds'] = max(0., sum(v.end-v.start for v in candidates)-sum(v.end-v.start for v in accepted))
    for item in [*accepted, *resolve_identity_overlaps(unknown_candidates)]:
        old = item.sample
        track, team, pid, role = (old[k] for k in ('track_id', 'team_id', 'player_id', 'role'))
        x, y = old['xy']
        row = min(shape[0]-1, int(y/projector.bounds['y_max']*shape[0]))
        col = min(shape[1]-1, int((x+7.5)/15*shape[1]))
        dt = item.end-item.start
        if role == 'unknown':
            grids['unknown_role'][row, col] += dt
            unknown_intervals.append([item.start, item.end, row, col, track, team, pid])
            continue
        keys = ['all', 'track:'+track, 'team:'+team if team else 'unknown_team']
        if pid:
            keys.append('player:'+pid)
        for grid_key in keys:
            grids.setdefault(grid_key, np.zeros(shape))[row, col] += dt
        color_eligible = not team and old.get('color_eligible', False)
        if color_eligible:
            unassigned_grids.setdefault(track, np.zeros(shape))[row, col] += dt
        entry = [item.start, item.end, row, col, track, team, pid, color_eligible]
        previous = interval_by_track.get(track)
        if previous is not None and abs(previous[1]-entry[0]) < 1e-9 and previous[2:] == entry[2:]:
            previous[1] = item.end
        else:
            heatmap_intervals.append(entry)
            interval_by_track[track] = entry
    color_teams = {}
    color_tracks = set()
    color_input_signature = None
    if config.get("classify_teams") and not automatic_mode:
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
                if person["role"] != "referee" and person["origin"] != "manual" and not person["team_id"] and person["id"] in color_teams:
                    person.update(team_id=color_teams[person["id"]], origin="color_estimate")
        for track, team in color_teams.items():
            if track not in tracks:
                continue
            if tracks[track]["role"] != "referee" and tracks[track]["team_id"] is None and not assignments.get(track):
                tracks[track]["team_id"] = team
            grid = unassigned_grids.get(track)
            if grid is not None:
                grids.setdefault("team:"+team, np.zeros(shape))[:] += grid
                grids['unknown_team'][:] -= grid
    for interval in heatmap_intervals:
        if interval[7] and interval[4] in color_teams:
            interval[5] = color_teams[interval[4]]
        del interval[7:]
    mass = float(grids['all'].sum())
    unknown_mass = float(grids['unknown_role'].sum())
    quality = dict(counters, total_player_seconds=mass, unknown_role_seconds=unknown_mass,
                   unknown_team_seconds=float(grids.get('unknown_team', np.zeros(1)).sum()),
                   projection_fraction=counters['projectable']/max(1, counters['observed']),
                   accuracy_status='not_measured', calibration_status='checked_landmarks' if config['segments'] and all(s.get('quality') == 'checked_landmarks' for s in config['segments']) else 'fit_only' if config['segments'] else 'uncalibrated')
    if automatic_mode:
        quality.update(calibration_status='automatic_line_checked' if geometry['supported_frames'] else 'automatic_unavailable',
                       geometry_supported_frames=geometry['supported_frames'],geometry_total_frames=geometry['total_frames'],
                       replay_status=geometry.get('replay_status','not_semantically_classified'),
                       geometry_reason=geometry.get('reason'))
    return dict(version=SPATIAL_ALGORITHM_VERSION, revision=config_revision(config), status="completed", format=config["format"],
                bounds=projector.bounds, roster=roster.to_dict(), tracks=list(tracks.values()),
                court_lines=court_markings(projector.bounds),
                frames=ordered,
                color_teams=color_teams, color_tracks=sorted(color_tracks), color_scope=config['exclusions'], color_classification_enabled=config.get('classify_teams', False), color_method=COLOR_METHOD,
                color_input_signature=color_input_signature,
                heatmaps={k:v.round(6).tolist() for k,v in grids.items()},
                heatmap_intervals=heatmap_intervals,
                unknown_heatmap_intervals=unknown_intervals, quality=quality, grid_shape=list(shape),
                cell_size_xy=[15/shape[1], projector.bounds['y_max']/shape[0]],
                calibration_segments=len({r['shot_id'] for r in geometry['frames'] if r['image_to_court']}) if automatic_mode else len(config["segments"]),
                geometry_mode='automatic' if automatic_mode else 'legacy_manual',identity=identity_summary)
