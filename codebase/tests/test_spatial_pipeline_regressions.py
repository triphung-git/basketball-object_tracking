"""Regressions for spatial-only imports, geometry, continuity and real adapters."""
import importlib
import json

import numpy as np
import pytest

from basketball_scoreboard import app
from basketball_scoreboard.config import APPROVED_MODEL_ID, VideoConfig
from basketball_scoreboard.contracts import DetectionRecord
from basketball_scoreboard.court import CourtConfig, CourtModel, PointCorrespondence, solve_homography
from basketball_scoreboard.heatmap import HeatmapAccumulator
from basketball_scoreboard.players import PlayerTracker
from basketball_scoreboard.scene_filter import SceneFilter
from basketball_scoreboard.spatial_analysis import ConfigurationError, build_spatial_analysis, default_config, validate_config
from basketball_scoreboard.spatial_io import file_hash
from basketball_scoreboard.video import VideoWriter
import basketball_scoreboard
import run_spatial_pipeline as runner
from test_spatial_analysis import _job, _observation, _points, _roster


def _court(video):
    return {
        'schema_version': '2.0.1', 'camera_id': 'test', 'segment_id': 'test',
        'status': 'draft', 'is_synthetic': True, 'original_image_wh': [64, 64],
        'source_video_hash': file_hash(video),
        'court_coordinate_system': {
            'origin': 'corner', 'axes': {}, 'units': 'normalized',
            'court_bounds': {'x_min': 0, 'x_max': 10, 'y_min': 0, 'y_max': 10}},
        'court_roi_image': [[0, 0], [64, 0], [64, 64], [0, 64]],
        'point_correspondences': [dict(point_id=str(i), image_xy=image, court_xy=court)
            for i, (image, court) in enumerate(zip(
                [[0, 0], [64, 0], [64, 64], [0, 64]],
                [[0, 0], [10, 0], [10, 10], [0, 10]]))],
    }


def _spatial(tmp_path, rows, *, assignments=(), classify=False):
    tracking = tmp_path / 'analysis' / 'tracking'
    tracking.mkdir(parents=True)
    (tracking / 'tracked_observations.jsonl').write_text(
        '\n'.join(json.dumps(row) for row in rows), encoding='utf-8')
    config = default_config(_job(), _roster())
    config['segments'] = [dict(start_s=0, end_s=1, anchor_s=0, points=_points())]
    config['assignments'] = list(assignments)
    config['classify_teams'] = classify
    return config


def test_all_retained_modules_import_without_deleted_statistics():
    from pathlib import Path
    for path in Path(basketball_scoreboard.__file__).parent.glob('*.py'):
        importlib.import_module(f'basketball_scoreboard.{path.stem}')


@pytest.mark.parametrize('humans,max_frames', [(True, None), (True, 2), (False, None), ('clipped', None)])
def test_real_spatial_adapters_with_prefix_and_empty_tracks(tmp_path, monkeypatch, humans, max_frames):
    video = tmp_path / 'source.mp4'
    with VideoWriter(video, 64, 64, 10) as writer:
        for _ in range(3):
            writer.write_frame(np.zeros((64, 64, 3), dtype=np.uint8))
    court = tmp_path / 'court.json'
    court.write_text(json.dumps(_court(video)), encoding='utf-8')

    class Detector:
        def __init__(self, *args, **kwargs):
            pass

        def warmup(self):
            pass

        def detect(self, *args):
            left = 0 if humans == 'clipped' else 10
            return ([DetectionRecord([left, 8, 50, 56], 1, 'human', .9)] if humans else []), 1.0

        def get_runtime_info(self):
            return {'model_id': APPROVED_MODEL_ID, 'class_mapping': {0: 'ball', 1: 'human', 2: 'rim'}}

    def detection(*args, **kwargs):
        return app.run_pipeline(*args, **kwargs, detector_factory=Detector)

    def unexpected_decode(*args, **kwargs):
        pytest.fail('Tracking without crop extraction must not decode the source again')

    monkeypatch.setattr(runner, 'run_pipeline', detection)
    monkeypatch.setattr('track_players.VideoReader', unexpected_decode)
    monkeypatch.setattr('basketball_scoreboard.video.probe_video', unexpected_decode)
    output = tmp_path / 'run'
    result = runner.run_spatial_pipeline(video, output, court_config_path=court, max_frames=max_frames)
    assert result['status'] == ('partial' if max_frames else 'completed')
    assert result['counts']['total_frames_read'] == (max_frames or 3)
    assert result['timings']['total_pipeline_s'] >= result['timings']['detection_pipeline_s']
    summary = json.loads((output / 'heatmap/heatmap_summary.json').read_text())
    mass = summary['heatmap_metadata']['total_player_seconds']
    assert mass == pytest.approx(((max_frames or 3) - 1) * .1 if humans is True else 0)
    if humans == 'clipped':
        projected = [json.loads(line) for line in (output / 'heatmap/trajectories.jsonl').read_text().splitlines()]
        assert all(row['projected_court_xy'] is None and row['validity_status'] == 'touch_boundary' for row in projected)


@pytest.mark.parametrize('barrier', [{'sample_type': 'predicted'}, {'timestamp_status': 'estimated'}])
def test_spatial_heatmap_does_not_bridge_unobserved_clock(tmp_path, barrier):
    rows = [_observation(0), _observation(.1, **barrier), _observation(.2)]
    result = build_spatial_analysis(tmp_path, _spatial(tmp_path, rows))
    assert np.asarray(result['heatmaps']['all']).sum() == 0
    assert result['heatmap_intervals'] == []


def test_spatial_team_change_is_a_continuity_barrier(tmp_path):
    rows = [_observation(0, team_id='a'), _observation(.1, team_id='b')]
    result = build_spatial_analysis(tmp_path, _spatial(tmp_path, rows))
    assert np.asarray(result['heatmaps']['all']).sum() == 0


def test_color_suggestions_preserve_manual_unknown_team(tmp_path, monkeypatch):
    rows = [_observation(0), _observation(.1)]
    assignment = dict(track_id='track-1', team_id=None, player_id=None, role='player', start_s=0, end_s=1)
    config = _spatial(tmp_path, rows, assignments=[assignment], classify=True)
    monkeypatch.setattr('basketball_scoreboard.spatial_analysis.infer_team_votes', lambda *a: {'track-1': 'a'})
    result = build_spatial_analysis(tmp_path, config)
    assert all(p['team_id'] is None for f in result['frames'] for p in f['players'])
    assert 'team:a' not in result['heatmaps']


def test_color_team_grid_includes_automatic_parts_of_manually_assigned_track(tmp_path, monkeypatch):
    rows = [_observation(t) for t in (0, .1, .2, .3, .4)]
    assignment = dict(track_id='track-1', team_id='b', player_id=None, role='player', start_s=.1, end_s=.2)
    config = _spatial(tmp_path, rows, assignments=[assignment], classify=True)
    monkeypatch.setattr('basketball_scoreboard.spatial_analysis.infer_team_votes', lambda *a: {'track-1': 'a'})
    result = build_spatial_analysis(tmp_path, config)
    assert np.asarray(result['heatmaps']['team:a']).sum() == pytest.approx(.2)
    assert sum(row[1] - row[0] for row in result['heatmap_intervals'] if row[5] == 'a') == pytest.approx(.2)


def test_heatmap_windows_clip_accepted_intervals_without_playback_resampling(tmp_path):
    rows = [_observation(t) for t in (0, .05, .1, .15, .2)]
    result = build_spatial_analysis(tmp_path, _spatial(tmp_path, rows))
    intervals = result['heatmap_intervals']
    # Adjacent intervals in the same grid cell are compressed without losing
    # sub-frame window boundaries or requiring a 5 Hz position approximation.
    assert len(intervals) == 1
    assert sum(max(0, min(.13, row[1]) - max(.07, row[0])) for row in intervals) == pytest.approx(.06)
    assert sum(row[1] - row[0] for row in intervals) == pytest.approx(np.asarray(result['heatmaps']['all']).sum())


def test_clipped_footpoint_remains_invalid_outside_roi(tmp_path):
    source = tmp_path / 'source'
    source.write_bytes(b'source')
    config = _court(source)
    config['court_roi_image'] = [[40, 0], [64, 0], [64, 64], [40, 64]]
    model = CourtModel(CourtConfig.from_dict(config))
    model.calibrate(allow_uncalibrated=True)
    obs = model.process_detection([0, 8, 50, 56], 0, 0, 'valid', 'video', 'hash', 'run', 'obs')
    assert obs.validity_status == 'touch_boundary'
    assert obs.projected_court_xy is None


def test_heatmap_repaired_end_does_not_override_estimated_start():
    acc = HeatmapAccumulator(dict(x_min=-7.5, x_max=7.5, y_min=0, y_max=11))
    rows = [dict(_observation(t), observation_id=str(i), projected_court_xy=[0, 5], timestamp_status=status)
            for i, (t, status) in enumerate([(0, 'estimated'), (.1, 'repaired')])]
    acc.process_observations_batch(rows)
    assert acc.total_grid.sum() == 0


def test_overlay_keeps_source_clock_when_tracks_start_late(tmp_path):
    detections, tracks, output = [tmp_path / name for name in ('detections.jsonl', 'tracks.jsonl', 'overlay.json')]
    detections.write_text('\n'.join(json.dumps(dict(source_time_s=t, detections=[])) for t in (0, .1, .2)))
    tracks.write_text(json.dumps(_observation(.1)))
    runner._build_tracking_overlay(detections, tracks, output)
    frames = json.loads(output.read_text())['frames']
    assert [f['time'] for f in frames] == [0, .2]
    assert all(f['boxes'] == [] for f in frames)


def test_lost_tentative_track_still_requires_minimum_hits():
    tracker = PlayerTracker('video', min_hits_to_activate=3)
    detection = dict(class_name='human', xyxy=[10, 20, 40, 80])
    first = tracker.update_frame(0, 0, 'valid', [detection])[0]
    tracker.update_frame(1, .1, 'valid', [])
    recovered = tracker.update_frame(2, .2, 'valid', [detection])[0]
    assert first.track_id not in tracker.tracks
    assert tracker.tracks[recovered.track_id].status == 'tentative'
    tracker.update_frame(3, .3, 'valid', [detection])
    tracker.update_frame(4, .4, 'valid', [detection])
    assert tracker.tracks[recovered.track_id].status == 'active'


def test_scene_filter_recovers_on_stable_new_scene():
    rng = np.random.default_rng(123)
    first = rng.integers(60, 180, size=(180, 320, 3), dtype=np.uint8)
    second = 255 - first
    scene = SceneFilter(motion_threshold=25)
    assert not scene.inspect_frame(first, 0).skip
    assert scene.inspect_frame(second, .1).skip
    assert not scene.inspect_frame(second, .2).skip


def test_homography_uses_all_points_when_first_four_include_collinear_subset():
    image = [(0, 0), (50, 0), (100, 0), (0, 100), (100, 100), (50, 50)]
    points = [PointCorrespondence(str(i), '', p, (p[0] / 10, p[1] / 10)) for i, p in enumerate(image)]
    result = solve_homography(points)
    assert result.max_fit_residual_px < 1e-5


def test_malformed_roster_is_a_configuration_error():
    config = default_config(_job(), [])
    with pytest.raises(ConfigurationError):
        validate_config(config, _job())


def test_worker_progress_does_not_restart_when_tracking_begins(tmp_path, monkeypatch):
    from basketball_scoreboard import web_worker
    (tmp_path / 'job.json').write_text(json.dumps({'duration_s': 10}))
    tracking = tmp_path / 'analysis/tracking'
    tracking.mkdir(parents=True)
    (tracking / 'tracking_summary.json').write_text(json.dumps({'total_tracks_initiated': 1}))
    updates = []
    original_write = web_worker.write_json

    def save(path, value):
        if path.name == 'progress.json':
            updates.append(value['progress'])
        original_write(path, value)

    def run(*args, progress_callback, **kwargs):
        for stage, time in [('detection', 9), ('tracking', 0), ('tracking', 5)]:
            progress_callback(dict(stage=stage, source_time_s=time))
        return dict(status='completed', counts={'total_frames_read': 100})

    monkeypatch.setattr(web_worker, 'run_spatial_pipeline', run)
    monkeypatch.setattr(web_worker, 'write_json', save)
    assert web_worker.main(tmp_path) == 0
    assert updates == sorted(updates)


@pytest.mark.parametrize('value', [True, 1.5, float('nan')])
def test_max_frames_requires_a_positive_integer(value):
    with pytest.raises(ValueError):
        VideoConfig(max_frames=value)
