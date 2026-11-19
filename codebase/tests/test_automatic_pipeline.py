"""Automatic geometry, source isolation and cross-process dashboard acceptance."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from basketball_scoreboard.automatic_court import (
    AutomaticCourtEstimator, AutomaticCourtTimeline, AutomaticProjector,
    TEMPLATE, LANE, load_automatic_geometry,
)
from basketball_scoreboard.shared_jobs import SharedJobs
from basketball_scoreboard.web_jobs import VideoJobs, write_json, JobError
from test_spatial_analysis import _job, _roster


def rendered_court():
    image = np.full((540,960,3),90,np.uint8)
    matrix = cv2.getPerspectiveTransform(LANE,np.float32([[300,240],[590,215],[760,335],[405,410]]))
    offset=0
    from basketball_scoreboard.automatic_court import PART_LENGTHS
    for count in PART_LENGTHS:
        points = TEMPLATE[offset:offset+count]@matrix.T
        points = np.int32(points[:,:2]/points[:,2,None])
        # Template concatenates three lane strokes and two sidelines.
        splits = [40,80] if offset==0 else [40] if offset==330 else []
        for stroke in np.split(points,splits):
            cv2.polylines(image,[stroke],False,(245,245,245),3,cv2.LINE_AA)
        offset+=count
    return image,matrix


def test_cold_registration_uses_pixels_and_recovers_metric_scale():
    image,truth=rendered_court()
    estimate=AutomaticCourtEstimator().estimate(image)
    assert estimate is not None
    world=np.float32([[-2,1],[0,5],[4,7],[-4,6]])
    pixels=cv2.perspectiveTransform(world[None],truth)
    actual=cv2.perspectiveTransform(pixels,np.linalg.inv(estimate['matrix']))[0]
    np.testing.assert_allclose(actual,world,atol=.18)
    assert estimate['parts'][2]>.6


def test_blank_and_lane_only_views_do_not_invent_geometry():
    estimator=AutomaticCourtEstimator()
    assert estimator.estimate(np.zeros((540,960,3),np.uint8)) is None
    image=np.full((540,960,3),100,np.uint8)
    cv2.polylines(image,[np.int32([[300,240],[590,215],[760,335],[405,410]])],True,(255,255,255),3)
    assert estimator.estimate(image) is None


def artifact(rows):
    return dict(version=1,mode='automatic',format='3x3',source_sha256='a'*64,
                width=960,height=540,fps=10,frames=rows,supported_frames=2,total_frames=len(rows))


def test_automatic_source_binding_and_missing_geometry_never_use_manual_segments(tmp_path):
    from basketball_scoreboard.spatial_analysis import build_spatial_analysis
    from test_spatial_pipeline_regressions import _spatial
    from test_spatial_analysis import _observation
    config=_spatial(tmp_path,[_observation(0),_observation(.2)])
    config['geometry_mode']='automatic'
    result=build_spatial_analysis(tmp_path,config)
    assert np.sum(result['heatmaps']['all'])==0
    assert result['quality']['calibration_status']=='automatic_unavailable'
    rows=[dict(frame_index=i,time_s=i*.1,shot_id='shot',image_to_court=np.eye(3).tolist()) for i in range(3)]
    path=tmp_path/'geometry.json';write_json(path,artifact(rows))
    with pytest.raises(ValueError):
        load_automatic_geometry(path,'b'*64,960,540)
    with pytest.raises(ValueError):
        load_automatic_geometry(path,'a'*64,1920,1080)


def test_no_interpolation_through_geometry_holes_or_shot_cuts():
    rows=[dict(frame_index=i,time_s=i*.1,shot_id='s1' if i<2 else 's2',
               image_to_court=None if i==1 else np.eye(3).tolist()) for i in range(3)]
    projector=AutomaticProjector(artifact(rows))
    assert projector.project([1,2],.1)==(None,None)
    assert projector.project([1,2],.06)==(None,None)
    assert not projector.uninterrupted(0,.2)
    assert projector.project([1,2],.2)==([1.,2.],'s2')


def test_camera_cut_resets_geometry_before_pixel_tracking(monkeypatch):
    import basketball_scoreboard.automatic_court as module
    image,matrix=rendered_court()
    estimator=SimpleNamespace(estimate=lambda *args:dict(matrix=matrix,score=.9,parts=[.9]*5))
    monkeypatch.setattr(module.LineEvidence,'score',lambda *args:(.9,[.9]*5))
    timeline=AutomaticCourtTimeline(estimator=estimator)
    timeline.consume(SimpleNamespace(source_time_s=0,frame_index=0),image,[])
    timeline.consume(SimpleNamespace(source_time_s=.1,frame_index=1),255-image,[])
    assert timeline.rows[0]['shot_id']!=timeline.rows[1]['shot_id']
    assert timeline.cuts==[.1]


def prepare_job(root,status='running'):
    job_id='a'*32;folder=root/job_id;folder.mkdir(parents=True)
    job=dict(_job(),id=job_id,status=status,progress=0,roster_matched=False,error=None)
    write_json(folder/'job.json',job);write_json(folder/'roster.json',_roster())
    return job_id,folder


def test_worker_slot_is_exclusive_across_real_processes(tmp_path):
    shared=SharedJobs(tmp_path)
    token=shared.claim('analysis','a'*32,'first')
    code="from basketball_scoreboard.shared_jobs import SharedJobs;import sys;print(SharedJobs(sys.argv[1]).claim('analysis','b'*32,'second'))"
    result=subprocess.run([sys.executable,'-c',code,str(tmp_path)],capture_output=True,text=True,check=True,
                          env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')},
                          creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=15)
    assert result.stdout.strip()=='None'
    assert shared.finish('analysis',token,'completed')
    assert shared.claim('analysis','b'*32,'second')


def test_foreign_server_refresh_progress_cancel_and_close_are_consistent(tmp_path):
    job_id,folder=prepare_job(tmp_path)
    first,second=VideoJobs(tmp_path),VideoJobs(tmp_path)
    token=first.shared.claim('analysis',job_id,first.owner)
    write_json(folder/'progress.json',dict(progress=37,stage='detection',status='running'))
    assert second.status(job_id)['progress']==37
    assert second.active()['id']==job_id
    second.close()
    assert first.shared.live(first.shared.get('analysis'))
    assert second.cancel(job_id)['status']=='cancelled'
    write_json(folder/'outcome.json',dict(status='completed',progress=100))
    first.worker_tokens[job_id]=token
    first._watch(job_id,SimpleNamespace(wait=lambda:0))
    assert first.status(job_id)['status']=='cancelled'
    assert second.status(job_id)['status']=='cancelled'
    write_json(folder/'spatial_map.json',dict(status='completed',frames=[dict(time=0,players=[])]))
    write_json(folder/'spatial_map_status.json',dict(status='completed',revision='partial'))
    assert first.spatial_map(job_id)=={'status':'unavailable'}


def test_foreign_cancel_interrupts_blocking_worker(tmp_path):
    job_id,folder=prepare_job(tmp_path)
    shared=SharedJobs(tmp_path);token=shared.claim('analysis',job_id,'owner')
    code="""import sys,time
from pathlib import Path
from basketball_scoreboard import web_worker
web_worker.run_spatial_pipeline=lambda *a,**kw:time.sleep(60)
raise SystemExit(web_worker.main(Path(sys.argv[1])))
"""
    process=subprocess.Popen([sys.executable,'-c',code,str(folder)],
        env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src'),'BASKETBALL_WORKER_TOKEN':token},
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    try:
        deadline=time.monotonic()+15
        while time.monotonic()<deadline and shared.get('analysis')['pid']==os.getpid():
            time.sleep(.05)
        # Windows' venv launcher and the worker interpreter have different PIDs.
        assert shared.get('analysis')['pid']!=os.getpid()
        VideoJobs(tmp_path).cancel(job_id)
        assert process.wait(timeout=5)!=0
        assert VideoJobs(tmp_path).status(job_id)['status']=='cancelled'
    finally:
        if process.poll() is None:
            shared.finish('analysis',token,'cancelled')
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.terminate();process.wait(timeout=5)


def test_configuration_revision_conflict_preserves_other_server_changes(tmp_path):
    job_id,folder=prepare_job(tmp_path,status='ready')
    jobs=VideoJobs(tmp_path);first=jobs.match_config(job_id)
    change=dict(first['config']);change['roster']=dict(change['roster'],team_a_name='Changed')
    jobs.configure(job_id,change)
    with pytest.raises(JobError) as failure:
        jobs.configure(job_id,dict(first['config'],_expected_revision=first['revision']))
    assert failure.value.status==409
    assert jobs.match_config(job_id)['config']['roster']['team_a_name']=='Changed'


@pytest.mark.parametrize('payload',[None,[],'invalid'])
def test_invalid_configuration_payload_returns_controlled_error(tmp_path,payload):
    job_id,_=prepare_job(tmp_path,status='ready')
    with pytest.raises(JobError) as failure:
        VideoJobs(tmp_path).configure(job_id,payload)
    assert failure.value.status==400


def test_stale_background_projection_cannot_publish(tmp_path,monkeypatch):
    import basketball_scoreboard.spatial_analysis as spatial
    job_id,folder=prepare_job(tmp_path,status='completed')
    jobs=VideoJobs(tmp_path);config=jobs.match_config(job_id)['config']
    (folder/'analysis').mkdir()
    write_json(folder/'analysis/automatic_geometry.json',dict(artifact([]),
        source_sha256=config['source_sha256'],width=config['width'],height=config['height']))
    started,release=threading.Event(),threading.Event()
    def build(*args,**kwargs):
        started.set();assert release.wait(5)
        return dict(status='completed',revision=spatial.config_revision(config),calibration_segments=0)
    monkeypatch.setattr(spatial,'build_spatial_analysis',build)
    assert jobs.rebuild_spatial_map(job_id)['status']=='running'
    assert started.wait(5)
    changed=dict(config,cell_size_m=.5);write_json(folder/'match_config.json',changed)
    release.set();deadline=time.monotonic()+5
    while jobs.shared.get('spatial:'+job_id)['state']=='running' and time.monotonic()<deadline:
        time.sleep(.02)
    assert jobs.shared.get('spatial:'+job_id)['state']=='stale'
    assert not (folder/'spatial_map.json').exists()


def test_opposing_team_evidence_prevents_cross_team_association():
    from basketball_scoreboard.players import PlayerTracker
    tracker=PlayerTracker('video',original_wh=(960,540),min_hits_to_activate=1)
    ids={}
    for i in range(4):
        observations=tracker.update_frame(i,i*.1,'valid',[
            dict(class_name='human',xyxy=[100,100,150,300],confidence=.9,appearance_team_id='a'),
            dict(class_name='human',xyxy=[155,100,205,300],confidence=.9,appearance_team_id='b')])
        ids={round(o.bbox[0]):o.track_id for o in observations}
    swapped=tracker.update_frame(4,.4,'valid',[
        dict(class_name='human',xyxy=[150,100,200,300],confidence=.9,appearance_team_id='a'),
        dict(class_name='human',xyxy=[105,100,155,300],confidence=.9,appearance_team_id='b')])
    assert next(o.track_id for o in swapped if o.bbox[0]==150)==ids[100]
    assert next(o.track_id for o in swapped if o.bbox[0]==105)==ids[155]


def test_default_pipeline_finishes_without_manual_geometry_or_extra_detector(monkeypatch,tmp_path):
    import run_spatial_pipeline as runner
    from basketball_scoreboard import app
    from basketball_scoreboard.contracts import DetectionRecord
    from basketball_scoreboard.video import VideoWriter
    from basketball_scoreboard.config import APPROVED_MODEL_ID
    video=tmp_path/'video.mp4'
    with VideoWriter(video,64,64,10) as writer:
        for _ in range(3):
            writer.write_frame(np.zeros((64,64,3),np.uint8))
    calls=[]
    class Detector:
        def __init__(self,*args,**kwargs):pass
        def warmup(self):pass
        def detect(self,*args):
            calls.append(1)
            return [DetectionRecord([10,8,45,56],1,'human',.9)],1.
        def get_runtime_info(self):
            return dict(model_id=APPROVED_MODEL_ID,class_mapping={0:'ball',1:'human',2:'rim'})
    monkeypatch.setattr(runner,'run_pipeline',lambda *a,**kw:app.run_pipeline(*a,**kw,detector_factory=Detector))
    monkeypatch.setattr(runner.CourtConfig,'from_json_file',lambda *a,**kw:pytest.fail('Automatic mode must not load manual calibration'))
    output=tmp_path/'analysis'
    result=runner.run_spatial_pipeline(video,output)
    assert result['status']=='completed'
    assert len(calls)==3
    assert result['spatial']['geometry_mode']=='automatic'
    assert result['spatial']['heatmap_status']=='unavailable'
    assert (output/'web_overlay.json').is_file()
    spatial=json.loads((output/'spatial_map.json').read_text())
    assert spatial['quality']['geometry_supported_frames']==0
    assert np.sum(spatial['heatmaps']['all'])==0


def test_team_evidence_cache_survives_identity_edit_but_invalidates_colors(tmp_path,monkeypatch):
    import basketball_scoreboard.spatial_analysis as spatial
    monkeypatch.setattr('basketball_scoreboard.jersey_identity.extract_jersey_evidence',
                        lambda *a,**kw:dict(status='unavailable',records=[]))
    from test_spatial_pipeline_regressions import _spatial
    from test_spatial_analysis import _observation
    config=_spatial(tmp_path,[_observation(0),_observation(.2)])
    config.update(geometry_mode='automatic',classify_teams=True)
    matrix=spatial.SpatialProjector(config).segments[0][1]
    geometry=artifact([dict(frame_index=i,time_s=i*.2,shot_id='s',image_to_court=matrix.tolist()) for i in range(2)])
    geometry.update(source_sha256=config['source_sha256'],width=config['width'],height=config['height'],fps=5)
    write_json(tmp_path/'analysis/automatic_geometry.json',geometry)
    calls=[]
    def votes(*args,**kwargs):
        calls.append(1);return {'track-1':'a' if len(calls)==1 else 'b'}
    monkeypatch.setattr(spatial,'infer_team_votes',votes)
    first=spatial.build_spatial_analysis(tmp_path,config)
    assert np.sum(first['heatmaps']['team:a'])==pytest.approx(.2)
    config['assignments']=[dict(track_id='track-1',team_id='a',player_id='a7',role='player',start_s=0,end_s=1)]
    identity=spatial.build_spatial_analysis(tmp_path,config)
    assert np.sum(identity['heatmaps']['player:a7'])==pytest.approx(.2)
    assert len(calls)==1
    config['assignments']=[]
    config['roster']['team_a_color_rgb']=[225,190,30]
    changed=spatial.build_spatial_analysis(tmp_path,config)
    assert np.sum(changed['heatmaps']['team:b'])==pytest.approx(.2)
    assert len(calls)==2
    assert {t['id'] for t in first['tracks']}=={t['id'] for t in changed['tracks']}


@pytest.mark.parametrize('preset,explicit',[('default',False),('vietnam-tonga',True)])
def test_root_launcher_default_preset_keeps_shared_demo_context(tmp_path,monkeypatch,preset,explicit):
    import run_demo
    bundle=tmp_path/'outputs/demo-completion-20261116/demo-bundle'
    bundle.mkdir(parents=True)
    captured={}
    monkeypatch.setattr(run_demo,'ROOT',tmp_path)
    monkeypatch.setattr(run_demo,'verify_bundle_manifest',lambda *args:None)
    monkeypatch.setattr(run_demo,'install_dashboard_demo',lambda *args:None)
    monkeypatch.setattr(run_demo,'load_run_bundle',lambda *args:({},{}))
    def server(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(server_port=8080,serve_forever=lambda:None,server_close=lambda:None)
    monkeypatch.setattr(run_demo,'make_dashboard_server',server)
    assert run_demo.main(['--preset',preset,'--mode','view'])==0
    assert captured['explicit_context'] is explicit
    assert captured['run_dir'] == (bundle if explicit else None)
