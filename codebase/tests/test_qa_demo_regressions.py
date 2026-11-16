import json
from pathlib import Path
import threading
import urllib.request
import urllib.error

import pytest

from basketball_scoreboard.dashboard import make_dashboard_server, load_run_bundle
from basketball_scoreboard.demo_bundle import summarize_run, verify_bundle_manifest
from basketball_scoreboard.rebounds import ReboundEngine
from basketball_scoreboard.calibration_scope import load_bound_court
from basketball_scoreboard.video import probe_video

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def http_server(tmp_path):
    video = tmp_path / 'annotated.mp4'
    video.write_bytes(bytes(range(256)) * 16)
    server = make_dashboard_server(port=0, video_path=video, run_dir=tmp_path,
        run_state={'source_coverage': {'first_time_s': 300.0}, 'status': 'completed'})
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}', video
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


@pytest.mark.parametrize('header,expected', [
    ('bytes=-10', bytes(range(246, 256))),
    ('bytes=4090-999999', bytes(range(250, 256))),
    ('bytes=4090-', bytes(range(250, 256))),
])
def test_browser_byte_ranges(http_server, header, expected):
    url, _ = http_server
    request = urllib.request.Request(url + '/api/video', headers={'Range': header})
    with urllib.request.urlopen(request, timeout=5) as response:
        assert response.status == 206
        assert response.read() == expected


def test_large_video_is_not_truncated(http_server):
    url, video = http_server
    size = 65 * 1024 * 1024 + 17
    with video.open('wb') as handle:
        handle.seek(size - 1)
        handle.write(b'Z')
    with urllib.request.urlopen(url + '/api/video', timeout=10) as response:
        received = 0
        last = b''
        while chunk := response.read(1024 * 1024):
            received += len(chunk)
            last = chunk
        assert received == size
        assert last[-1:] == b'Z'


def test_playback_source_offset_and_no_implicit_calibration(http_server):
    url, _ = http_server
    with urllib.request.urlopen(url + '/api/status', timeout=5) as response:
        data = json.load(response)
    assert data['playback_source_start_s'] == 300.0
    assert data['geometry_status'] == 'uncalibrated'


def test_summary_uses_actual_run():
    run = {'stage_counts': {'total_frames_read': 151, 'confirmed_shots': 1},
           'timings': {'pipeline_fps': 2.1}, 'geometry': {'status': 'calibrated'},
           'boxscore_totals': {'match_totals': {'points': 0, 'rebounds': 0, 'assists': 0}}}
    summary = summarize_run(run, {'total_player_seconds': 17.4})
    assert summary['frames_processed'] == 151
    assert summary['pipeline_fps'] == 2.1
    assert summary['rebounds_total'] == 0
    assert summary['heatmap_mass_person_seconds'] == 17.4
    assert summary['geometry']['status'] == 'calibrated'


def test_loader_uses_canonical_run_instead_of_stale_summary(tmp_path):
    (tmp_path / 'run.json').write_text(json.dumps({'stage_counts': {}, 'geometry': {'status': 'uncalibrated_diagnostic'}}))
    (tmp_path / 'summary.json').write_text(json.dumps({'rebounds_total': 99, 'court_calibrated': True}))
    _, state, _ = load_run_bundle(tmp_path)
    assert state['rebounds_total'] == 0
    assert state['court_calibrated'] is False


def test_corrupt_events_fail_with_line_number(tmp_path):
    (tmp_path / 'events_auto.jsonl').write_text('{broken json}\n')
    with pytest.raises(ValueError, match='events_auto.jsonl:1'):
        load_run_bundle(tmp_path)


def test_manifest_tampering_is_rejected(tmp_path):
    import hashlib
    (tmp_path / 'run.json').write_bytes(b'{}')
    manifest = {'files': [{'path': 'run.json', 'bytes': 2,
                'sha256': hashlib.sha256(b'{}').hexdigest()}], 'total_files': 1, 'total_bytes': 2}
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest))
    verify_bundle_manifest(tmp_path)
    (tmp_path / 'run.json').write_bytes(b'[]')
    with pytest.raises(ValueError, match='SHA-256'):
        load_run_bundle(tmp_path)


@pytest.mark.parametrize('state', ['unknown', 'free', 'loose', 'control_candidate'])
def test_unconfirmed_control_cannot_create_rebound(state):
    controls = [{'source_time_s': 10.1 + i * .1, 'frame_index': i,
        'state': state, 'certainty': 'unresolved', 'controller': None} for i in range(5)]
    assert ReboundEngine().evaluate_missed_shot('miss1', 'miss', 'team_b', 10.0, controls) is None


def test_controller_free_rows_cannot_create_rebound_even_without_state():
    controls = [{'source_time_s': 10.1 + i * .1, 'frame_index': i} for i in range(5)]
    assert ReboundEngine().evaluate_missed_shot('miss1', 'miss', 'team_b', 10.0, controls) is None


@pytest.mark.parametrize('start,end,expected', [(300., 305., 'calibrated'),
    (290., 305., 'uncalibrated_diagnostic'), (300., 400., 'uncalibrated_diagnostic')])
def test_court_reuse_requires_whole_requested_scope(start, end, expected):
    # Metadata only: this test does not run recognition on the source.
    from types import SimpleNamespace
    metadata = SimpleNamespace(width=1920, height=1080, duration_s=1381., fps=30.)
    model, _, status = load_bound_court(ROOT / 'configs/courts/vt_development_court.json',
        '1443c1d263c8037a5684f3dbc0ef9216beb5097d9a47c4c1c9b94d1363e26865',
        metadata, start, end)
    assert status == expected
    assert (model is not None) == (expected == 'calibrated')


def test_overlay_clip_has_zero_based_clock(tmp_path):
    import av
    import numpy as np
    from basketball_scoreboard.video import VideoWriter, VideoReader
    from render_annotated_video import render_overlay_video
    source = tmp_path / 'source.mp4'
    with VideoWriter(source, 64, 64, 10) as writer:
        for i in range(10):
            writer.write_frame(np.zeros((64, 64, 3), dtype=np.uint8), i / 10.)
    run = tmp_path / 'run'
    run.mkdir()
    output = tmp_path / 'annotated.mp4'
    render_overlay_video(source, output, run, start_time_s=.5, end_time_s=.9, max_frames=5)
    with av.open(str(output)) as container:
        times = [float(f.pts * f.time_base) for f in container.decode(video=0)]
    assert times == pytest.approx([0., .1, .2, .3, .4], abs=.001)
    with VideoReader(source, start_time_s=.5) as reader:
        frames = list(reader.frames())
    assert [rec.frame_index for rec, _ in frames] == [5, 6, 7, 8, 9]
    assert frames[0][0].source_time_s == .5
    with pytest.raises(FileExistsError):
        render_overlay_video(source, output, run, start_time_s=.5, end_time_s=.9, max_frames=5)
