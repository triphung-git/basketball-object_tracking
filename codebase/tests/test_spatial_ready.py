"""Acceptance regressions for physical positions, calibration and occupancy."""
import json
from dataclasses import replace
from itertools import permutations

import numpy as np
import pytest

from basketball_scoreboard.court import TrajectoryObservation
from basketball_scoreboard.heatmap import HeatmapAccumulator
from basketball_scoreboard.spatial_analysis import build_spatial_analysis, validate_config, ConfigurationError
from test_spatial_analysis import _job, _roster, _points, _observation
from test_spatial_pipeline_regressions import _spatial


def cli_observation(time, track='T1', **updates):
    row = dict(schema_version='2.0.0', observation_id=f'{track}:{time}', source_run_id='run', video_id='video',
               source_fingerprint_sha256='a'*64, frame_index=round(time*60), source_time_s=time,
               timestamp_status='valid', segment_id='s', camera_id='cam', bbox=[90,110,110,160],
               footpoint_image=(100,150), projected_court_xy=(0,5), validity_status='valid',
               track_id=track, player_id='a7', team_id='a', role='player', confidence=.9)
    row.update(updates)
    return TrajectoryObservation(**row)


def test_overlap_union_is_order_independent_and_replay_is_idempotent():
    observations = [cli_observation(0), cli_observation(.2), cli_observation(.1,'T2'), cli_observation(.3,'T2')]
    for order in permutations(observations):
        acc = HeatmapAccumulator(dict(x_min=-7.5,x_max=7.5,y_min=0,y_max=11), team_a_id='a',team_b_id='b')
        acc.process_observations_batch(order)
        acc.process_observations_batch(order)
        assert acc.total_grid.sum() == pytest.approx(.3)
        assert acc.metadata.identity_overlap_seconds == pytest.approx(.1)


@pytest.mark.parametrize('change', [dict(camera_id='other'),dict(segment_id='other'),dict(calibration_version='new'),
                                   dict(team_id='b'),dict(player_id='other'),dict(role='referee')])
def test_cli_and_web_do_not_bridge_source_or_identity_changes(tmp_path, change):
    rows = [cli_observation(0), replace(cli_observation(.2), **change)]
    acc = HeatmapAccumulator(dict(x_min=-7.5,x_max=7.5,y_min=0,y_max=11))
    acc.process_observations_batch(rows)
    assert acc.total_grid.sum() == 0
    source = [r.to_dict() for r in rows]
    if 'team_id' in change:
        for row in source:
            row['player_id'] = None
    if 'player_id' in change:
        # The web roster strips an unknown player ID; it still changes identity.
        source[1]['player_id'] = None
    config = _spatial(tmp_path, source)
    result = build_spatial_analysis(tmp_path,config)
    assert np.sum(result['heatmaps']['all']) == 0


def test_web_overlap_keeps_partial_tail_and_one_marker(tmp_path):
    rows = [_observation(t,track_id=track,player_id='a7',team_id='a',confidence=conf)
            for t,track,conf in [(0,'T1',.9),(.1,'T2',.8),(.2,'T1',.9),(.3,'T2',.8)]]
    result = build_spatial_analysis(tmp_path,_spatial(tmp_path,rows))
    assert np.sum(result['heatmaps']['all']) == pytest.approx(.3)
    rows = [_observation(t,track_id=track,player_id='a7',team_id='a',confidence=conf)
            for t in [0,.2] for track,conf in [('T1',.9),('T2',.8)]]
    config = _spatial(tmp_path/'same-time',rows)
    result = build_spatial_analysis(tmp_path/'same-time',config)
    assert all(sum(p['xy'] is not None for p in f['players']) == 1 for f in result['frames'])
    assert result['quality']['duplicate_identity_markers'] == 2


def test_unknown_roles_are_separate_and_speed_jumps_rejected(tmp_path):
    config = _spatial(tmp_path,[_observation(t,role='unknown') for t in [0,.2]])
    result = build_spatial_analysis(tmp_path,config)
    assert np.sum(result['heatmaps']['all']) == 0
    assert np.sum(result['heatmaps']['unknown_role']) == pytest.approx(.2)
    rows = [cli_observation(0,projected_court_xy=(-5,5)), cli_observation(.1,projected_court_xy=(5,5))]
    acc = HeatmapAccumulator(dict(x_min=-7.5,x_max=7.5,y_min=0,y_max=11))
    acc.process_observations_batch(rows)
    assert acc.total_grid.sum() == 0
    assert acc.metadata.speed_outlier_seconds == pytest.approx(.1)


def test_check_landmarks_are_independent_and_roi_is_enforced(tmp_path):
    config = _spatial(tmp_path,[_observation(t) for t in [0,.2]])
    config['segments'][0]['points'][-1]['usage']='check'
    config['segments'][0]['roi_image']=[[10,10],[40,10],[40,40],[10,40]]
    normalized = validate_config(config,_job())
    assert normalized['segments'][0]['quality'] == 'checked_landmarks'
    result = build_spatial_analysis(tmp_path,normalized)
    assert np.sum(result['heatmaps']['all']) == 0
    assert all(p['xy'] is None for f in result['frames'] for p in f['players'])
    config['segments'][0]['points'][-1]['image'] = [10,10]
    with pytest.raises(ConfigurationError):
        validate_config(config,_job())


def test_five_by_five_has_square_metric_cells_and_disabled_shots_have_no_mass(tmp_path):
    config = _spatial(tmp_path,[_observation(t) for t in [0,.2]])
    config['format']='5x5'
    result = build_spatial_analysis(tmp_path,config)
    assert result['grid_shape'] == [112,60]
    assert result['cell_size_xy'] == [.25,.25]
    config['segments'][0]['enabled']=False
    result = build_spatial_analysis(tmp_path,config)
    assert np.sum(result['heatmaps']['all']) == 0


def test_calibration_preview_http_does_not_save_draft(tmp_path):
    from basketball_scoreboard.web_jobs import VideoJobs,write_json
    from basketball_scoreboard.spatial_analysis import default_config
    job_id='a'*32;folder=tmp_path/job_id;folder.mkdir()
    job=dict(_job(),id=job_id,status='completed')
    write_json(folder/'job.json',job)
    jobs=VideoJobs(tmp_path)
    config=default_config(job,_roster())
    config['segments']=[dict(start_s=0,end_s=1,points=_points())]
    result=jobs.preview_calibration(job_id,config)
    assert result['segments'][0]['lines']
    assert not (folder/'match_config.json').exists()


def test_camera_geometry_gaps_do_not_get_filled(tmp_path):
    config=_spatial(tmp_path,[_observation(t) for t in [0,.2]])
    config['fps']=60
    points=config['segments'][0]['points']
    config['segments'][0]['keyframes']=[dict(time_s=t,image_points=[p['image'] for p in points]) for t in [0,.2]]
    result=build_spatial_analysis(tmp_path,config)
    assert np.sum(result['heatmaps']['all'])==0
    from basketball_scoreboard.spatial_analysis import SpatialProjector
    projector=SpatialProjector(config)
    assert projector.project([100,150],.1)==(None,None)


def test_dynamic_roi_moves_with_the_floor_not_fixed_image_pixels():
    from basketball_scoreboard.spatial_analysis import default_config,SpatialProjector
    config=default_config(_job(),_roster());points=_points()
    config['segments']=[dict(start_s=0,end_s=1,anchor_s=0,points=points,
        roi_image=[[80,140],[120,140],[120,160],[80,160]],
        keyframes=[dict(time_s=0,image_points=[p['image'] for p in points]),
                   dict(time_s=.2,image_points=[[p['image'][0]+20,p['image'][1]] for p in points])])]
    projector=SpatialProjector(validate_config(config,_job()))
    assert projector.project([130,150],.2)[0]==[1.,5.]
    assert projector.project([170,150],.2)==(None,None)


def test_cli_and_web_raw_grids_agree_for_same_policy(tmp_path):
    rows=[cli_observation(t) for t in [0,.1,.2]]
    config=_spatial(tmp_path,[row.to_dict() for row in rows])
    web=build_spatial_analysis(tmp_path,config)
    cli=HeatmapAccumulator(web['bounds'],grid_shape=tuple(web['grid_shape']),max_gap_s=.3,team_a_id='a',team_b_id='b')
    cli.process_observations_batch(rows)
    np.testing.assert_allclose(cli.total_grid,web['heatmaps']['all'],atol=1e-6)


def test_real_calibration_must_pass_before_detector_runs(tmp_path,monkeypatch):
    from basketball_scoreboard.court import UncalibratedCourtError
    import run_spatial_pipeline as runner
    from test_spatial_pipeline_regressions import _court
    video=tmp_path/'video.mp4';video.write_bytes(b'input')
    court=_court(video);court.update(is_synthetic=False,status='draft')
    path=tmp_path/'court.json';path.write_text(json.dumps(court))
    monkeypatch.setattr(runner,'run_pipeline',lambda *a,**kw:pytest.fail('Invalid court must stop before inference'))
    with pytest.raises(UncalibratedCourtError):
        runner.run_spatial_pipeline(video,tmp_path/'out',court_config_path=path)
    assert not (tmp_path/'out').exists()


def test_launcher_reopens_existing_dashboard_without_rebinding(monkeypatch):
    import io
    import run_dashboard
    opened=[]
    monkeypatch.setattr('sys.argv',['run_dashboard.py','--host','127.0.0.1','--port','8081','--open-browser'])
    monkeypatch.setattr(run_dashboard.urllib.request,'urlopen',lambda *a,**kw:io.BytesIO(b'{"application":"basketball-spatial-dashboard"}'))
    monkeypatch.setattr(run_dashboard.webbrowser,'open',opened.append)
    monkeypatch.setattr(run_dashboard,'make_dashboard_server',lambda *a,**kw:pytest.fail('Do not rebind a running dashboard'))
    run_dashboard.main()
    assert opened==['http://127.0.0.1:8081']


def test_unavailable_heatmap_is_not_reported_generated(tmp_path):
    from basketball_scoreboard.dashboard import load_run_bundle
    (tmp_path/'run.json').write_text(json.dumps(dict(status='completed')))
    (tmp_path/'heatmap_summary.json').write_text(json.dumps(dict(status='unavailable',reason='No calibration')))
    _,heatmap=load_run_bundle(tmp_path)
    assert heatmap=={}
