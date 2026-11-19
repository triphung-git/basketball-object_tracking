"""Pixel-only court registration and camera tracking, without saved landmarks.

The initial hypothesis fits the 4.90 x 5.80 m lane. The two-point arc and
no-charge semicircle supply separate image evidence. Unsupported views never
inherit an earlier camera's calibration. Scores measure line agreement, not
metric position accuracy or calibrated probabilities.
"""
from __future__ import annotations

from itertools import combinations
import math

import cv2
import numpy as np
from scipy.ndimage import map_coordinates
from scipy.optimize import least_squares

AUTOMATIC_COURT_VERSION = 1
LANE = np.float32([[-2.45, 0], [2.45, 0], [2.45, 5.8], [-2.45, 5.8]])


def _template():
    segment = lambda a, b, n=40: np.linspace(a, b, n)
    angle = math.asin(math.sqrt(6.75**2 - 6.6**2) / 6.75)
    theta = np.linspace(angle, math.pi-angle, 130)
    key = np.concatenate([segment([-2.45, 0], [-2.45, 5.8]),
                          segment([2.45, 0], [2.45, 5.8]),
                          segment([-2.45, 5.8], [2.45, 5.8])])
    baseline = segment([-7.5, 0], [7.5, 0], 80)
    arc = np.c_[6.75*np.cos(theta), 1.575+6.75*np.sin(theta)]
    sides = np.concatenate([segment([-7.5, 0], [-7.5, 11]), segment([7.5, 0], [7.5, 11])])
    theta = np.linspace(0, math.pi, 45)
    no_charge = np.c_[1.25*np.cos(theta), 1.575+1.25*np.sin(theta)]
    parts = [key, baseline, arc, sides, no_charge]
    points = np.concatenate(parts)
    return np.c_[points, np.ones(len(points))], [len(p) for p in parts]


TEMPLATE, PART_LENGTHS = _template()


def _project(matrix, points):
    q = np.c_[points, np.ones(len(points))] @ matrix.T
    with np.errstate(divide='ignore', invalid='ignore'):
        return q[:, :2] / q[:, 2, None]


class LineEvidence:
    def __init__(self, image, detections=()):
        self.gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        ridge = cv2.subtract(self.gray, cv2.morphologyEx(
            self.gray, cv2.MORPH_OPEN, np.ones((11, 11), np.uint8)))
        self.mask = np.uint8((hsv[:, :, 1] < 75) & (self.gray > 160) & (ridge > 20))*255
        self.visible = np.ones(self.gray.shape, np.uint8)
        h, w = self.gray.shape
        # Scoreboards and background advertising cannot validate the floor.
        self.visible[:int(.18*h)] = 0
        for d in detections:
            if d.get('class_name') == 'human':
                x1, y1, x2, y2 = np.rint(d['xyxy']).astype(int)
                cv2.rectangle(self.visible, (x1-3, y1-3), (x2+3, y2+3), 0, -1)
        self.distance = cv2.distanceTransform(255-self.mask, cv2.DIST_L2, 3)

    def score(self, court_to_image):
        h, w = self.gray.shape
        q = TEMPLATE @ court_to_image.T
        with np.errstate(divide='ignore', invalid='ignore'):
            q = q[:, :2]/q[:, 2, None]
        valid = (np.isfinite(q).all(axis=1) & (q[:, 0] >= 3) & (q[:, 0] < w-3)
                 & (q[:, 1] > .18*h) & (q[:, 1] < h-3))
        x = np.clip(np.nan_to_num(q[:, 0]), 0, w-1).astype(int)
        y = np.clip(np.nan_to_num(q[:, 1]), 0, h-1).astype(int)
        valid &= self.visible[y, x] != 0
        if valid.sum() < 110:
            return 0., [0.]*5
        scores = np.exp(-(self.distance[y, x]/3.)**2)*valid
        parts, offset = [], 0
        for n in PART_LENGTHS:
            count = valid[offset:offset+n].sum()
            parts.append(float(scores[offset:offset+n].sum()/max(1, count)))
            offset += n
        # Require arc evidence beyond the four lane-line intersections.
        arc_start = sum(PART_LENGTHS[:2])
        if valid[arc_start:arc_start+PART_LENGTHS[2]].sum() < 35:
            return 0., parts
        score = float(np.dot(parts, [.23, .18, .40, .10, .09]))
        return score, parts


class AutomaticCourtEstimator:
    """Enumerate observed line families, then refine and reject ambiguous fits."""
    def estimate(self, image, detections=()):
        evidence = LineEvidence(image, detections)
        h, w = evidence.gray.shape
        raw = cv2.createLineSegmentDetector(0).detect(evidence.gray)[0]
        if raw is None:
            return None
        nearby = cv2.dilate(evidence.mask, np.ones((5, 5), np.uint8))
        lines = []
        for a, b, c, d in sorted(raw.reshape(-1, 4), key=lambda v: -np.hypot(v[2]-v[0], v[3]-v[1])):
            if np.hypot(c-a, d-b) < 65 or min(b, d) < .2*h:
                continue
            samples = np.int32(np.linspace([a, b], [c, d], 40))
            xs, ys = np.clip(samples[:, 0], 0, w-1), np.clip(samples[:, 1], 0, h-1)
            if np.mean(nearby[ys, xs] > 0) < .65:
                continue
            line = np.cross([a, b, 1.], [c, d, 1.])
            line /= np.linalg.norm(line[:2])
            if line[1] < 0:
                line = -line
            if any(abs(line[:2]@old[0][:2]) > .999 and abs(line@[*old[1], 1]) < 5 for old in lines):
                continue
            lines.append((line, [(a+c)/2, (b+d)/2]))
            if len(lines) >= 32:
                break
        pairs = [(i, j) for i, j in combinations(range(len(lines)), 2)
                 if abs(lines[i][0][:2]@lines[j][0][:2]) > .88
                 and 30 < abs(lines[i][0]@[*lines[j][1], 1]) < 500]
        candidates = []
        for a, b in pairs:
            for c, d in pairs:
                if len({a, b, c, d}) < 4 or abs(lines[a][0][:2]@lines[c][0][:2]) > .96:
                    continue
                corners = []
                for i, j in [(a, c), (a, d), (b, d), (b, c)]:
                    p = np.cross(lines[i][0], lines[j][0])
                    corners.append(p[:2]/p[2] if abs(p[2]) > 1e-6 else [np.nan, np.nan])
                corners = np.float32(corners)
                if not np.isfinite(corners).all() or not cv2.isContourConvex(corners):
                    continue
                if not w*h*.015 < cv2.contourArea(corners) < w*h*.4:
                    continue
                if (corners[:, 0].min() < -.2*w or corners[:, 0].max() > 1.2*w
                        or corners[:, 1].min() < .18*h or corners[:, 1].max() > 1.1*h):
                    continue
                if corners[:2, 1].sum() > corners[2:, 1].sum():
                    corners = corners[[3, 2, 1, 0]]
                if corners[0, 0] > corners[1, 0]:
                    corners = corners[[1, 0, 3, 2]]
                lengths = np.linalg.norm(np.roll(corners, -1, axis=0)-corners, axis=1)
                if lengths.min() < 60 or lengths.max()/lengths.min() > 5:
                    continue
                matrix = cv2.getPerspectiveTransform(LANE, corners)
                if not valid_floor(matrix):
                    continue
                score, parts = evidence.score(matrix)
                if score > .28 and parts[2] > .18:
                    candidates.append((score, matrix))
        candidates.sort(key=lambda v: -v[0])
        refined = []
        for _, matrix in candidates[:8]:
            corners = _project(matrix, LANE).astype(np.float32)
            def residual(parameters):
                hm = cv2.getPerspectiveTransform(LANE, np.float32(parameters.reshape(4, 2)))
                q = TEMPLATE @ hm.T
                q = q[:, :2]/q[:, 2, None]
                distances = map_coordinates(evidence.distance, [q[:, 1], q[:, 0]],
                                            order=1, mode='constant', cval=20.)
                x = np.clip(q[:, 0], 0, w-1).astype(int)
                y = np.clip(q[:, 1], 0, h-1).astype(int)
                distances *= evidence.visible[y, x]
                return np.r_[np.minimum(distances, 12), (parameters-corners.ravel())*.15]
            fit = least_squares(residual, corners.ravel().astype(float), diff_step=1e-3,
                                max_nfev=45, loss='soft_l1', f_scale=3,
                                bounds=(corners.ravel()-18, corners.ravel()+18))
            matrix = cv2.getPerspectiveTransform(LANE, np.float32(fit.x.reshape(4, 2)))
            score, parts = evidence.score(matrix)
            if valid_floor(matrix):
                refined.append((score, matrix, parts))
        refined.sort(key=lambda v: -v[0])
        if not refined:
            return None
        score, matrix, parts = refined[0]
        if score < .62 or parts[0] < .48 or parts[1] < .4 or parts[2] < .6:
            return None
        # Duplicate stripe-edge hypotheses are equivalent. Distinct court fits
        # need a useful margin, otherwise reject rather than guess a camera.
        corners = _project(matrix, LANE)
        alternative = next((s for s, hm, _ in refined[1:]
                            if np.median(np.linalg.norm(_project(hm, LANE)-corners, axis=1)) > 20), 0.)
        if score-alternative < .08:
            return None
        return dict(matrix=matrix, score=score, parts=parts, alternative_score=alternative)


def valid_floor(matrix):
    if matrix is None or not np.isfinite(matrix).all() or np.linalg.cond(matrix) > 1e8:
        return False
    polygon = np.c_[np.float64([[-7.5, 0], [7.5, 0], [7.5, 11], [-7.5, 11]]), np.ones(4)]@matrix.T
    return bool(np.min(polygon[:, 2])*np.max(polygon[:, 2]) > 0)


class AutomaticCourtTimeline:
    """Frame-clock geometry with bounded optical-flow propagation and hard cuts."""
    def __init__(self, format='3x3', estimator=None):
        self.format = format
        self.estimator = estimator or AutomaticCourtEstimator()
        self.rows = []
        self.previous_gray = self.previous_points = self.matrix = None
        self.last_anchor_s = self.last_attempt_s = -float('inf')
        self.shot = 0
        self.cuts = []
        self.last_score = 0.
        self.steps = []

    def consume(self, frame, image, detections):
        height, width = image.shape[:2]
        scale = np.array([960/width, 540/height])
        small = cv2.resize(image, (960, 540))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        dets = [dict(d, xyxy=(np.float64(d['xyxy'])*np.tile(scale, 2)).tolist()) for d in detections]
        t = frame.source_time_s
        method, step, is_cut = 'unavailable', None, False
        if self.previous_gray is not None:
            difference = float(np.mean(cv2.absdiff(cv2.resize(gray, (160, 90)),
                                                 cv2.resize(self.previous_gray, (160, 90)))))
            if self.previous_points is not None and len(self.previous_points) >= 12:
                moved, status, _ = cv2.calcOpticalFlowPyrLK(self.previous_gray, gray, self.previous_points, None,
                    winSize=(21, 21), maxLevel=3)
                returned, reverse_status, _ = cv2.calcOpticalFlowPyrLK(gray, self.previous_gray, moved, None,
                    winSize=(21, 21), maxLevel=3)
                valid = ((status.ravel() == 1) & (reverse_status.ravel() == 1)
                         & (np.linalg.norm(returned-self.previous_points, axis=2).ravel() < 1.))
                if valid.sum() >= 12:
                    source, target = self.previous_points[valid], moved[valid]
                    step, inliers = cv2.findHomography(source, target, cv2.RANSAC, 1.5)
                    if (step is None or inliers.sum() < 12 or inliers.mean() < .65
                            or cv2.contourArea(cv2.convexHull(source[inliers.ravel() != 0])) < 5000):
                        step = None
            is_cut = difference > 42 or (step is None and difference > 16)
            if is_cut:
                self.shot += 1
                self.cuts.append(t)
                self.matrix = None
                self.last_attempt_s = -float('inf')
            elif self.matrix is not None and step is not None:
                candidate = step @ self.matrix
                if valid_floor(candidate) and t-self.last_anchor_s <= 2.5:
                    self.matrix = candidate/candidate[2, 2]
                    method = 'floor_optical_flow'
                else:
                    self.matrix = None
            else:
                self.matrix = None
        # A half-court hypothesis cannot establish which end of an entire
        # 5x5 broadcast is visible. Refuse that ambiguous global coordinate map.
        if self.format == '3x3' and t-self.last_attempt_s >= (1.5 if self.matrix is not None else .5):
            self.last_attempt_s = t
            estimate = self.estimator.estimate(small, dets)
            if estimate:
                candidate = estimate['matrix']
                displacement = (float(np.median(np.linalg.norm(_project(candidate, LANE)-_project(self.matrix, LANE), axis=1)))
                                if self.matrix is not None else 0.)
                if displacement > 35:
                    self.shot += 1
                    self.cuts.append(t)
                self.matrix = candidate
                self.last_anchor_s = t
                self.last_score = estimate['score']
                method = 'automatic_line_registration'
        if self.matrix is not None:
            evidence = LineEvidence(small, dets)
            score, parts = evidence.score(self.matrix)
            if score < .40 or parts[2] < .35 or t-self.last_anchor_s > 2.5:
                self.matrix = None
                method = 'line_agreement_lost'
        matrix = None
        if self.matrix is not None:
            matrix = (np.linalg.inv(self.matrix) @ np.diag([*scale, 1.])).tolist()
        self.rows.append(dict(frame_index=frame.frame_index, time_s=t, shot_id=f'shot_{self.shot:04d}',
                              image_to_court=matrix, method=method, line_score=round(self.last_score, 4)))
        self.steps.append(None if is_cut else step)
        if method == 'automatic_line_registration':
            self._bridge_supported_gap(scale)
        floor_mask = np.zeros(gray.shape, np.uint8)
        if self.matrix is not None:
            polygon = _project(self.matrix, np.float32([[-7.5, 0], [7.5, 0], [7.5, 11], [-7.5, 11]]))
            cv2.fillPoly(floor_mask, [np.int32(np.clip(polygon, -10000, 10000))], 255)
        else:
            floor_mask[int(.2*540):] = 255
        for d in dets:
            if d.get('class_name') == 'human':
                x1, y1, x2, y2 = np.rint(d['xyxy']).astype(int)
                cv2.rectangle(floor_mask, (x1-5, y1-5), (x2+5, y2+5), 0, -1)
        self.previous_points = cv2.goodFeaturesToTrack(gray, 450, .01, 8, mask=floor_mask)
        self.previous_gray = gray

    def _bridge_supported_gap(self, scale):
        """Fill a short occlusion only when both independent endpoints agree.

        Reverse floor motion from a new pixel-derived registration. Require the
        reverse chain to meet the earlier supported calibration within 8 pixels;
        never bridge a shot boundary or a missing motion estimate.
        """
        index = len(self.rows)-1
        candidate = self.matrix.copy()
        missing = []
        current = self.rows[index]
        while index > 0 and current['time_s']-self.rows[index-1]['time_s'] <= 2.:
            step = self.steps[index]
            previous = self.rows[index-1]
            if step is None or previous['shot_id'] != current['shot_id']:
                return
            try:
                candidate = np.linalg.inv(step)@candidate
            except np.linalg.LinAlgError:
                return
            if not valid_floor(candidate):
                return
            if previous['image_to_court'] is not None:
                if not missing:
                    return
                old = np.diag([*scale,1.])@np.linalg.inv(previous['image_to_court'])
                error = np.linalg.norm(_project(old,LANE)-_project(candidate,LANE),axis=1)
                if np.max(error) <= 8.:
                    for row, hm in missing:
                        row.update(image_to_court=(np.linalg.inv(hm)@np.diag([*scale,1.])).tolist(),
                                   method='bidirectional_floor_motion',line_score=round(min(previous['line_score'],self.last_score),4))
                return
            missing.append((previous,candidate.copy()))
            index -= 1

    def artifact(self, source_sha256, width, height, fps):
        valid = sum(row['image_to_court'] is not None for row in self.rows)
        return dict(version=AUTOMATIC_COURT_VERSION, mode='automatic', format=self.format,
                    source_sha256=source_sha256, width=width, height=height, fps=fps,
                    method='line_template_ransac_optical_flow', frames=self.rows, cuts=self.cuts,
                    supported_frames=valid, total_frames=len(self.rows),
                    status='available' if valid else 'unavailable',
                    accuracy_status='not_measured', replay_status='not_semantically_classified',
                    orientation='baseline_at_top_image_left_to_right',
                    reason=None if valid else ('fullcourt_end_identity_unresolved' if self.format == '5x5' else 'insufficient_line_evidence'))


class AutomaticProjector:
    def __init__(self, artifact, exclusions=()):
        self.rows = artifact['frames']
        self.times = [r['time_s'] for r in self.rows]
        self.tolerance = .5/artifact['fps']+1e-6
        self.bounds = dict(x_min=-7.5, x_max=7.5, y_min=0, y_max=11 if artifact['format'] == '3x3' else 28)
        self.exclusions = exclusions
        self.geometry_gaps = [(r['time_s'], self.rows[i+1]['time_s']) for i, r in enumerate(self.rows[:-1])
                              if r['image_to_court'] is None or r['shot_id'] != self.rows[i+1]['shot_id']
                              or self.rows[i+1]['frame_index'] != r['frame_index']+1]

    def row_at(self, t):
        from bisect import bisect_left
        index = bisect_left(self.times, t-self.tolerance)
        return self.rows[index] if index < len(self.rows) and abs(self.times[index]-t) <= self.tolerance else None

    def excluded(self, t):
        return any(e['start_s'] <= t < e['end_s'] for e in self.exclusions)

    def project(self, xy, t):
        row = self.row_at(t)
        if self.excluded(t) or row is None or row['image_to_court'] is None:
            return None, None
        q = _project(np.float64(row['image_to_court']), np.float64([xy]))[0]
        if np.isfinite(q).all() and -7.5 <= q[0] <= 7.5 and 0 <= q[1] <= self.bounds['y_max']:
            return np.round(q, 4).tolist(), row['shot_id']
        return None, row['shot_id']

    def uninterrupted(self, a, b):
        return (not any(e['start_s'] < b and e['end_s'] > a for e in self.exclusions)
                and not any(start < b and end > a for start, end in self.geometry_gaps))


def load_automatic_geometry(path, source_sha256, width, height, format=None):
    """Reject cross-video, incompatible or malformed geometry before projection."""
    import json
    from pathlib import Path
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if (data.get('version') != AUTOMATIC_COURT_VERSION or data.get('mode') != 'automatic'
            or data.get('source_sha256') != source_sha256
            or (data.get('width'), data.get('height')) != (width, height)
            or data.get('format') not in {'3x3', '5x5'}
            or (format and data['format'] != format)
            or not isinstance(data.get('fps'), (int, float)) or data['fps'] <= 0):
        raise ValueError('Automatic geometry does not match source/configuration')
    previous_time, previous_index = -1., -1
    for row in data['frames']:
        t, index = row['time_s'], row['frame_index']
        if not math.isfinite(t) or t <= previous_time or index <= previous_index:
            raise ValueError('Invalid geometry frame clock')
        matrix = row['image_to_court']
        if matrix is not None:
            matrix = np.float64(matrix)
            if matrix.shape != (3, 3) or not np.isfinite(matrix).all() or abs(np.linalg.det(matrix)) < 1e-12:
                raise ValueError('Invalid automatic homography')
        previous_time, previous_index = t, index
    return data


def ensure_automatic_geometry(directory, config, progress=None):
    """Recompute only geometry when migrating a run or changing court format."""
    import json
    from pathlib import Path
    from .video import VideoReader
    from .web_jobs import write_json
    directory = Path(directory)
    analysis = directory/'analysis'
    target = analysis/'automatic_geometry.json'
    def load(path):
        return load_automatic_geometry(path,config['source_sha256'],config['width'],config['height'],config['format'])
    if target.is_file():
        try:
            load(target)
            return
        except ValueError:
            pass
    cached = analysis/f"automatic_geometry-{config['format']}-v{AUTOMATIC_COURT_VERSION}.json"
    if cached.is_file():
        write_json(target,load(cached))
        return
    path = next((p for p in [analysis/'detection/detections.jsonl',analysis/'detections.jsonl'] if p.is_file()),None)
    if path is None:
        raise FileNotFoundError('Automatic registration requires source detections')
    timeline = AutomaticCourtTimeline(config['format'])
    with VideoReader(directory/'input.mp4') as reader, path.open(encoding='utf-8') as handle:
        if reader.metadata.sha256 != config['source_sha256']:
            raise ValueError('Source video fingerprint changed')
        decoded = iter(reader.frames())
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            frame, image = next(decoded)
            if frame.frame_index != row['frame_index'] or abs(frame.source_time_s-row['source_time_s']) > 1e-6:
                raise ValueError('Source geometry clock mismatch')
            timeline.consume(frame,image,row['detections'])
            if progress and frame.frame_index%60 == 0:
                progress('geometry',frame.frame_index,reader.metadata.nb_frames)
    data = timeline.artifact(config['source_sha256'],config['width'],config['height'],config.get('fps',30))
    write_json(cached,data)
    write_json(target,data)
