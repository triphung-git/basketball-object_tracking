"""HTTP and lifecycle regression tests for importing independent match videos."""
import io
import json
from pathlib import Path
import threading
import urllib.error
import urllib.request

import numpy as np
import pytest

from basketball_scoreboard.dashboard import make_dashboard_server, spatial_overlay
from basketball_scoreboard.video import VideoWriter
from basketball_scoreboard.web_jobs import JobError, VideoJobs, write_json
from run_spatial_pipeline import _build_tracking_overlay


@pytest.fixture
def clip(tmp_path):
    path = tmp_path / 'clip.mp4'
    with VideoWriter(path, 64, 64, 10) as writer:
        for _ in range(3):
            writer.write_frame(np.zeros((64, 64, 3), dtype=np.uint8))
    return path.read_bytes()


@pytest.fixture
def web(tmp_path):
    server = make_dashboard_server(port=0, jobs_root=tmp_path / 'jobs',
        run_state={'status': 'completed', 'geometry': {'status': 'calibrated'}})
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}', server.jobs
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def request(url, data=None, headers=None):
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers or {}), timeout=10) as response:
        body = response.read()
        return response.status, json.loads(body) if 'application/json' in response.headers.get('Content-Type', '') else body


def upload(url, clip, name='trận-đấu.mp4'):
    from urllib.parse import quote
    return request(url + '/api/upload?name=' + quote(name), clip, {'X-Demo-Request': '1'})[1]


def test_upload_resets_sample_and_keeps_jobs_separate(web, clip):
    url, jobs = web
    first = upload(url, clip)
    second = upload(url, clip, '../../khác.mp4')
    assert first['id'] != second['id']
    assert second['name'] == 'khác.mp4'
    assert not first['roster_matched']
    for job in (first, second):
        _, status = request(url + '/api/status?job=' + job['id'])
        assert status['playback_source_start_s'] == 0
        assert status['geometry_status'] == 'uncalibrated'
        assert status['status'] == 'ready'
        for endpoint in ('/api/events', '/api/boxscore', '/api/export/events', '/api/export/boxscore'):
            with pytest.raises(urllib.error.HTTPError) as failure:
                request(url + endpoint + '?job=' + job['id'])
            assert failure.value.code == 404
        roster = json.loads((jobs.root / job['id'] / 'roster.json').read_text(encoding='utf-8'))
        assert roster['team_assignment_enabled'] is False


@pytest.mark.parametrize('payload,name', [(b'not a video', 'test.mp4'), (b'abc', 'video.exe'), (b'', 'empty.mp4')])
def test_invalid_uploads_rejected(web, payload, name):
    url, jobs = web
    with pytest.raises(urllib.error.HTTPError) as failure:
        upload(url, payload, name)
    assert failure.value.code in {400, 413}
    assert not jobs.jobs
    assert not list(jobs.root.glob('*/input.mp4'))


def test_upload_requires_same_origin_header(web, clip):
    url, _ = web
    for headers in ({}, {'X-Demo-Request': '1', 'Origin': 'https://unrelated.example'}):
        with pytest.raises(urllib.error.HTTPError) as failure:
            request(url + '/api/upload?name=test.mp4', clip, headers)
        assert failure.value.code == 403


def test_missing_job_does_not_fall_back_to_sample(web):
    url, _ = web
    with pytest.raises(urllib.error.HTTPError) as failure:
        request(url + '/api/spatial?job=nonexistent')
    assert failure.value.code == 404


def test_cancellation_is_terminal_and_does_not_publish_partial_results(web, clip):
    url, jobs = web
    job = upload(url, clip)
    result = request(url + '/api/cancel?job=' + job['id'], b'', {'X-Demo-Request': '1'})[1]
    assert result['status'] == 'cancelled'
    with pytest.raises(JobError):
        jobs.start(job['id'])
    assert 'ledger' not in jobs.snapshot(job['id'])


def test_summary_export_contains_only_spatial_metadata(web, clip):
    url, jobs = web
    job = upload(url, clip)
    _, summary = request(url + '/api/export/summary?job=' + job['id'])
    assert summary['job']['id'] == job['id']
    assert not {'points', 'assists', 'rebounds', 'boxscore', 'events'} & summary.keys()


def test_legacy_overlay_exposes_only_spatial_bbox_fields():
    overlay = spatial_overlay({
        'events': [{'type': 'made_shot', 'points': 2}],
        'frames': [{
            'time': 1.0,
            'score': {'team_a': 2},
            'boxes': [{'box': [1, 2, 30, 40], 'id': 'track-1', 'event': 'made_shot'}],
        }],
    })

    assert overlay == {'frames': [{
        'time': 1.0,
        'boxes': [{'box': [1, 2, 30, 40], 'id': 'track-1'}],
    }]}


def test_legacy_config_statistics_are_stripped_before_return(web, clip):
    _, jobs = web
    job = jobs.upload(io.BytesIO(clip), len(clip), 'match.mp4')
    config_path = jobs.root / job['id'] / 'match_config.json'
    config = jobs.match_config(job['id'])['config']
    config.update(points=[{'value': 2}], shot_summary={'made': 1}, events=[{'type': 'made_shot'}])
    write_json(config_path, config)

    sanitized = jobs.match_config(job['id'])['config']
    persisted = json.loads(config_path.read_text(encoding='utf-8'))

    assert not {'points', 'shot_summary', 'events', 'boxscore'} & sanitized.keys()
    assert not {'points', 'shot_summary', 'events', 'boxscore'} & persisted.keys()


def test_legacy_job_metadata_does_not_expose_statistics(web, clip):
    _, jobs = web
    job = jobs.upload(io.BytesIO(clip), len(clip), 'match.mp4')
    job_path = jobs.root / job['id'] / 'job.json'
    persisted = json.loads(job_path.read_text(encoding='utf-8'))
    persisted.update(points=2, assists=1, rebounds=3, boxscore={'team_a': 2})
    write_json(job_path, persisted)
    jobs.jobs.pop(job['id'])

    public = jobs.status(job['id'])

    assert not {'points', 'assists', 'rebounds', 'boxscore', 'events'} & public.keys()


def test_legacy_spatial_map_does_not_expose_statistics(web, clip):
    _, jobs = web
    job = jobs.upload(io.BytesIO(clip), len(clip), 'match.mp4')
    config = jobs.match_config(job['id'])['config']
    from basketball_scoreboard.spatial_analysis import config_revision
    revision = config_revision(config)
    directory = jobs.root / job['id']
    write_json(directory / 'spatial_map_status.json', {
        'status': 'completed', 'revision': revision, 'calibration_segments': 1,
        'boxscore': {'team_a': 2},
    })
    write_json(directory / 'spatial_map.json', {
        'status': 'completed', 'revision': revision,
        'tracks': [], 'frames': [], 'heatmaps': {},
        'points': [{'value': 2}], 'events': [{'type': 'made_shot'}],
    })

    spatial = jobs.spatial_map(job['id'])

    assert not {'points', 'assists', 'rebounds', 'boxscore', 'events'} & spatial.keys()


def test_truncated_upload_leaves_no_video(tmp_path):
    jobs = VideoJobs(tmp_path / 'jobs')
    with pytest.raises(JobError, match='gián đoạn'):
        jobs.upload(io.BytesIO(b'ab'), 10, 'clip.mp4')
    assert not list(jobs.root.glob('*/input.mp4'))


def test_overlay_preserves_all_players_in_sampled_frame(tmp_path):
    output = tmp_path / 'web_overlay.json'
    detections = tmp_path / 'detections.jsonl'
    tracking = tmp_path / 'tracked_observations.jsonl'
    records = [dict(source_time_s=t, track_id=track, sample_type='observed', role='player', bbox=[1, 2, 30, 40])
        for t in [0, .1, .2] for track in ['1', '2']]
    tracking.write_text('\n'.join(json.dumps(r) for r in records))
    detections.write_text('\n'.join(json.dumps({'source_time_s': t, 'detections': []}) for t in [0, .1, .2]))
    _build_tracking_overlay(detections, tracking, output)
    frames = json.loads(output.read_text())['frames']
    assert [f['time'] for f in frames] == [0, .2]
    assert all(len(f['boxes']) == 2 for f in frames)


def test_worker_failure_never_exposes_exception_or_credentials(tmp_path, monkeypatch):
    from basketball_scoreboard import web_worker
    write_json(tmp_path / 'job.json', {'duration_s': 1, 'roster_matched': False})
    def fail(*args, **kwargs):
        raise ValueError('ROBOFLOW_API_KEY: sensitive-example')
    monkeypatch.setattr(web_worker, 'run_spatial_pipeline', fail)
    assert web_worker.main(tmp_path) == 1
    result = json.loads((tmp_path / 'outcome.json').read_text(encoding='utf-8'))
    assert result['status'] == 'failed'
    assert 'sensitive-example' not in result['error']


def test_worker_runs_spatial_pipeline_without_stats_or_ocr(tmp_path, monkeypatch):
    from basketball_scoreboard import web_worker
    (tmp_path / 'analysis' / 'tracking').mkdir(parents=True)
    write_json(tmp_path / 'job.json', {
        'id': 'job', 'duration_s': 1, 'width': 64, 'height': 64,
        'source_sha256': 'source-hash', 'roster_matched': False, 'roster_configured': True,
    })
    write_json(tmp_path / 'roster.json', {
        'team_a_id': 'a', 'team_b_id': 'b', 'team_a_name': 'Đỏ', 'team_b_name': 'Xanh',
        'team_a_color_rgb': [220, 30, 30], 'team_b_color_rgb': [30, 30, 220],
        'players': [{'player_id': 'a7', 'team_id': 'a', 'jersey_number': '7', 'name': 'Cầu thủ 7'}],
    })
    calls = {}

    def run_pipeline(video, output, **kwargs):
        calls.update(kwargs)
        return {'status': 'completed', 'counts': {'total_frames_read': 3}}

    monkeypatch.setattr(web_worker, 'run_spatial_pipeline', run_pipeline)
    write_json(tmp_path / 'analysis' / 'tracking' / 'tracking_summary.json', {
        'status': 'completed', 'total_tracks_initiated': 2,
    })

    assert web_worker.main(tmp_path) == 0
    assert set(calls) == {'progress_callback'}
    assert callable(calls['progress_callback'])
    outcome = json.loads((tmp_path / 'outcome.json').read_text(encoding='utf-8'))
    assert outcome['tracks'] == 2
    assert not {'points', 'assists', 'rebounds', 'ocr'} & outcome.keys()


def test_saved_video_survives_server_restart(tmp_path, clip):
    root = tmp_path / 'jobs'
    first = VideoJobs(root)
    job = first.upload(io.BytesIO(clip), len(clip), 'match.mp4')
    resumed = VideoJobs(root)
    assert resumed.status(job['id'])['status'] == 'ready'
    assert resumed.snapshot(job['id'])['run_state']['roster_matched'] is False


def test_interrupted_worker_is_not_reported_as_running_after_restart(tmp_path, clip):
    first = VideoJobs(tmp_path / 'jobs')
    job = first.upload(io.BytesIO(clip), len(clip), 'match.mp4')
    job['status'] = 'running'
    first._save(job)
    resumed = VideoJobs(first.root)
    assert resumed.status(job['id'])['status'] == 'failed'
    assert 'gián đoạn' in resumed.status(job['id'])['error']


def test_job_lookup_cannot_escape_upload_directory(tmp_path):
    jobs = VideoJobs(tmp_path / 'jobs')
    for invalid in ['../match', '..\\match', '', None]:
        with pytest.raises(JobError) as failure:
            jobs.status(invalid)
        assert failure.value.status == 404
