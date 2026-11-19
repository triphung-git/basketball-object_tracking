"""Reproductions of issues found while auditing the bbox improvement report."""
import json
from dataclasses import replace
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pytest

from basketball_scoreboard.court import CourtConfig, CourtModel
from basketball_scoreboard.identity import IdentityResolver, TeamColorClassifier, enrich_observations_with_identity
from basketball_scoreboard.players import PlayerTracker, compute_match_cost
from basketball_scoreboard.spatial_analysis import build_spatial_analysis, validate_config, default_config, ConfigurationError
from basketball_scoreboard.web_jobs import VideoJobs, write_json
from test_spatial_analysis import _job, _observation, _points, _roster
from test_spatial_pipeline_regressions import _spatial


def det(box, confidence=.9):
    return dict(class_name='human', xyxy=box, confidence=confidence)


def test_offcourt_detection_cannot_steal_a_confirmed_track():
    tracker = PlayerTracker('source', min_hits_to_activate=1)
    tracker.is_on_court_candidate = lambda box, is_initialization=False: (box[0] < 100, 'test', None)
    first = tracker.update_frame(0, 0, 'valid', [det([80, 100, 110, 200])])[0]
    rows = tracker.update_frame(1, .1, 'valid', [det([105, 100, 135, 200])])
    assert all(r.sample_type == 'predicted' for r in rows)
    assert tracker.tracks[first.track_id].last_observed_time_s == 0


def test_tentative_miss_is_retired_without_a_phantom_prediction():
    tracker = PlayerTracker('source', min_hits_to_activate=3)
    first = tracker.update_frame(0, 0, 'valid', [det([80, 100, 110, 200])])[0]
    assert tracker.update_frame(1, .1, 'valid', []) == []
    assert tracker.update_frame(2, .2, 'valid', []) == []
    assert first.track_id not in tracker.tracks


def test_weak_boxes_recover_confirmed_tracks_but_do_not_create_or_confirm_tracks():
    tracker = PlayerTracker('source', min_hits_to_activate=2)
    box = [80, 100, 110, 200]
    first = tracker.update_frame(0, 0, 'valid', [det(box)])[0]
    rows = tracker.update_frame(1, .1, 'valid', [det(box, .3)])
    assert rows == []
    assert first.track_id not in tracker.tracks
    assert tracker.update_frame(2, .2, 'valid', [det(box, .3)]) == []
    tracker.update_frame(3, .3, 'valid', [det(box)])
    current = tracker.update_frame(4, .4, 'valid', [det(box)])[0]
    recovered = tracker.update_frame(5, .5, 'valid', [det(box, .3)])[0]
    assert recovered.track_id == current.track_id
    assert recovered.sample_type == 'observed'


def test_uncalibrated_person_is_not_automatically_a_player():
    tracker = PlayerTracker('source')
    rows = tracker.update_frame(0, 0, 'valid', [det([80, 100, 110, 200])])
    assert rows[0].role == 'unknown'


@pytest.mark.parametrize('options', [dict(high_det_thresh=.1, low_det_thresh=.2),
                                    dict(high_det_thresh=float('nan')), dict(court_buffer_m=(-1, 1))])
def test_invalid_tracker_options_are_rejected(options):
    with pytest.raises(ValueError):
        PlayerTracker('source', **options)


def test_size_jump_is_not_a_valid_match_even_at_the_same_center():
    assert compute_match_cost([95, 100, 125, 200], [-40, -350, 260, 650]) >= 1e4


def model():
    cfg = CourtConfig.from_json_file(Path(__file__).parents[1] / 'configs/courts/synthetic_half_court.json')
    court = CourtModel(cfg)
    court.calibrate(allow_uncalibrated=True)
    return court


def test_cut_is_opt_in_and_cannot_silently_reopen_uncalibrated_court():
    court = model()
    tracker = PlayerTracker('source', court_model=court, auto_scene_cut=True, min_hits_to_activate=1)
    tracker.update_frame(0, 0, 'valid', [])
    tracker._detect_camera_cut = lambda *args: True
    rows = tracker.update_frame(1, .1, 'valid', [det([50, 50, 100, 150])])
    assert tracker._requires_court_rebind
    assert tracker.scene_cuts == [.1]
    assert rows == []
    with pytest.raises(ValueError):
        tracker.update_frame(1, .1, 'valid', [])
    assert not PlayerTracker('default').auto_scene_cut


def test_referee_color_heuristic_is_optional_and_unsafe_with_neutral_team_uniforms():
    default = TeamColorClassifier('a', 'b', (220, 20, 20), (20, 40, 220))
    assert default.classify_entity((45, 45, 48))[2] == 'unknown'
    white_team = TeamColorClassifier('a', 'b', (220, 220, 220), (220, 20, 20), allow_referee_heuristic=True)
    assert white_team.classify_entity((45, 45, 48))[2] == 'unknown'


def test_referee_evidence_expires_and_does_not_overwrite_nonplayer():
    from basketball_scoreboard.identity import RosterConfig
    resolver = IdentityResolver(RosterConfig.from_dict(_roster()))
    for t in (0, .15, .3):
        resolver.add_referee_observation('t', .9, t)
    mapping = resolver.update_track_mapping('t', .3)
    assert mapping.role == 'referee'
    assert mapping.evidence_summary['valid_until_s'] == pytest.approx(2.3)
    from basketball_scoreboard.court import TrajectoryObservation
    tracker = PlayerTracker('source', min_hits_to_activate=1)
    obs = tracker.update_frame(0, .3, 'valid', [det([80, 100, 110, 200])])[0]
    obs.track_id, obs.role = 't', 'non_player'
    enrich_observations_with_identity([obs], resolver)
    assert obs.role == 'non_player'
    assert resolver.update_track_mapping('t', 3).role == 'unknown'


def test_referee_is_displayed_without_color_team_or_heatmap_mass(tmp_path, monkeypatch):
    config = _spatial(tmp_path, [_observation(0, role='referee'), _observation(.1, role='referee')], classify=True)
    monkeypatch.setattr('basketball_scoreboard.spatial_analysis.infer_team_votes', lambda *a: {'track-1': 'a'})
    result = build_spatial_analysis(tmp_path, config)
    assert np.asarray(result['heatmaps']['all']).sum() == 0
    assert result['heatmap_intervals'] == []
    assert all(p['role'] == 'referee' and p['team_id'] is None for f in result['frames'] for p in f['players'])


def test_missing_trajectory_is_not_reported_as_a_completed_empty_run(tmp_path):
    with pytest.raises(FileNotFoundError):
        build_spatial_analysis(tmp_path, default_config(_job(), _roster()))


def test_legacy_single_frame_assignment_uses_source_frame_rate():
    job = dict(_job(), fps=60)
    config = default_config(job, _roster())
    config['assignments'] = [dict(track_id='t', start_s=.5, end_s=.5)]
    normalized = validate_config(config, job)
    assert normalized['assignments'][0]['end_s'] == pytest.approx(.5 + 1/60)


def test_legacy_map_without_revision_is_stale(tmp_path):
    jobs = VideoJobs(tmp_path)
    job_id = 'a'*32
    directory = tmp_path / job_id
    directory.mkdir()
    write_json(directory/'job.json', dict(id=job_id, status='completed'))
    write_json(directory/'match_config.json', {})
    write_json(directory/'match_analysis.json', dict(status='completed'))
    assert jobs.spatial_status(job_id)['status'] == 'stale'


def test_configured_roster_reaches_the_real_web_worker(tmp_path, monkeypatch):
    from basketball_scoreboard import web_worker
    write_json(tmp_path/'job.json', {'duration_s':1})
    write_json(tmp_path/'roster.json', dict(team_assignment_enabled=True))
    tracking = tmp_path/'analysis/tracking'
    tracking.mkdir(parents=True)
    write_json(tracking/'tracking_summary.json', dict(total_tracks_initiated=1))
    calls = {}
    def run(*args, **kwargs):
        calls.update(kwargs)
        return dict(status='completed', counts={'total_frames_read':1})
    monkeypatch.setattr(web_worker, 'run_spatial_pipeline', run)
    assert web_worker.main(tmp_path) == 0
    assert calls['roster_config_path'] == tmp_path/'roster.json'


def test_overlay_javascript_regressions():
    if not shutil.which('node'):
        pytest.skip('Node.js is required for overlay playback regressions')
    path = Path(__file__).with_name('overlay_playback_regressions.cjs')
    subprocess.run(['node', str(path)], check=True, capture_output=True, text=True)


@pytest.mark.parametrize('overlapping', [False, True])
def test_masked_hue_keeps_shadowed_yellow_and_rejects_shared_torso_pixels(tmp_path, overlapping):
    from basketball_scoreboard.video import VideoWriter
    from basketball_scoreboard.spatial_io import file_hash
    from track_players import track_players_pipeline
    video = tmp_path/'source.mp4'
    with VideoWriter(video,64,64,10) as writer:
        for _ in range(3):
            writer.write_frame(np.full((64,64,3),(25,100,110),dtype=np.uint8))
    source = dict(status='completed',is_synthetic=True,run_id='test',video_id='source',
                  source_fingerprint_sha256=file_hash(video),
                  video_metadata=dict(width=64,height=64,duration_s=.3),class_mapping={'1':'human'})
    write_json(tmp_path/'run.json',source)
    roster = dict(_roster(), team_a_color_rgb=[200,25,35],team_b_color_rgb=[235,210,30])
    write_json(tmp_path/'roster.json',roster)
    boxes = [[10,8,50,56]] + ([[25,8,60,56]] if overlapping else [])
    rows=[dict(video_id='source',source_time_s=i/10,frame_index=i,timestamp_status='valid',
               original_wh=[64,64],detections=[dict(det(box),class_id=1) for box in boxes]) for i in range(3)]
    (tmp_path/'detections.jsonl').write_text('\n'.join(json.dumps(row) for row in rows))
    output=tmp_path/'tracking'
    assert track_players_pipeline(tmp_path/'detections.jsonl',output,run_json_path=tmp_path/'run.json',
                                  roster_config_path=tmp_path/'roster.json',video_path=video,allow_uncalibrated=True) == 0
    observations=[json.loads(line) for line in (output/'tracked_observations.jsonl').read_text().splitlines()]
    if overlapping:
        assert all(row['team_id'] is None for row in observations)
        assert json.loads((output/'tracking_summary.json').read_text())['ambiguous_team_crops'] > 0
    else:
        assert any(row['team_id'] == 'b' for row in observations)
        assert all(row['team_id'] != 'a' for row in observations)
