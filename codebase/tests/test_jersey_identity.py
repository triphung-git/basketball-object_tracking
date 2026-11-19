"""Roster-only saves resolve names from evidence, never roster ordering."""
import json

import numpy as np
import pytest

from basketball_scoreboard.identity import RosterConfig,JerseyEvidenceRecord,ModelWeightsUnavailableError
from basketball_scoreboard.jersey_identity import JerseyIdentityTimeline,extract_jersey_evidence
from basketball_scoreboard.web_jobs import write_json
from test_spatial_analysis import _roster,_observation


def source_rows(path,tracks=('T',),frames=45):
    path.write_text('\n'.join(json.dumps(dict(_observation(i*.1,track_id=track),frame_index=i))
                             for i in range(frames) for track in tracks),encoding='utf-8')


def reading(track,index,number='7',confidence=1.):
    return JerseyEvidenceRecord(f'{track}:{index}:{number}',track,index,index*.1,number,confidence,
                                ocr_engine='test_fixture').to_dict()


def test_names_require_multiple_frames_and_expire_without_fresh_digits(tmp_path):
    path=tmp_path/'tracks.jsonl';source_rows(path)
    evidence=dict(status='completed',records=[reading('T',i) for i in range(3)])
    timeline=JerseyIdentityTimeline(path,RosterConfig.from_dict(_roster()),{'T':'a'},evidence)
    assert timeline.at('T',.1) is None
    assert timeline.at('T',.3)=='a7'
    assert timeline.at('T',4.) is None
    assert timeline.summary['named_players']==1


def test_small_sponsor_digits_do_not_count_as_jersey_numbers(tmp_path):
    from types import SimpleNamespace
    from basketball_scoreboard.identity import LocalEasyOCRProvider
    for file in ['craft_mlt_25k.pth','english_g2.pth']:
        (tmp_path/file).write_bytes(b'test fixture')
    provider=LocalEasyOCRProvider(model_storage_directory=tmp_path,min_number_height_fraction=.18)
    provider._reader=SimpleNamespace(readtext=lambda *a,**kw:[
        ([[20,45],[28,45],[28,50],[20,50]],'3',.999),
        ([[20,35],[50,35],[50,65],[20,65]],'7',.99)])
    crop=np.tile(np.arange(100,dtype=np.uint8)[:,None,None],(1,80,3))
    records=provider.read_jersey(crop,'T',0,0.)
    assert [r.detected_number for r in records]==['7']


def test_same_number_on_opposing_teams_resolves_to_correct_roster(tmp_path):
    roster=_roster();roster['players'].append(dict(player_id='b7',team_id='b',jersey_number='7',name='Other seven'))
    path=tmp_path/'tracks.jsonl';source_rows(path,tracks=('A','B'),frames=5)
    evidence=dict(status='completed',records=[reading(t,i) for t in ['A','B'] for i in range(3)])
    timeline=JerseyIdentityTimeline(path,RosterConfig.from_dict(roster),{'A':'a','B':'b'},evidence)
    assert timeline.at('A',.3)=='a7'
    assert timeline.at('B',.3)=='b7'


@pytest.mark.parametrize('mode',['unknown_team','wrong_number','weak_digits','duplicate_vote'])
def test_uncertain_evidence_cannot_assign_roster_names(tmp_path,mode):
    path=tmp_path/'tracks.jsonl';source_rows(path,frames=5)
    records=[reading('T',i,number='8' if mode=='wrong_number' else '7',
                     confidence=.8 if mode=='weak_digits' else 1.) for i in range(3)]
    if mode=='duplicate_vote':records=[records[0]]*5
    timeline=JerseyIdentityTimeline(path,RosterConfig.from_dict(_roster()),
        {} if mode=='unknown_team' else {'T':'a'},dict(status='completed',records=records))
    assert timeline.at('T',.3) is None


def test_ocr_cache_does_not_depend_on_roster_names_and_missing_weights_degrade(tmp_path):
    from basketball_scoreboard.video import VideoWriter,compute_file_sha256
    video=tmp_path/'input.mp4'
    with VideoWriter(video,200,240,10) as writer:
        for i in range(4):
            writer.write_frame(np.full((240,200,3),100,np.uint8))
    observations=tmp_path/'tracks.jsonl'
    observations.write_text('\n'.join(json.dumps(dict(_observation(t,track_id='T',bbox=[30,20,130,200]),
        frame_index=index)) for index,t in [(0,0.),(3,.3)]),encoding='utf-8')
    calls=[]
    class Provider:
        stats={}
        def __init__(self,**kwargs):pass
        def read_jersey(self,crop,track,index,time):
            calls.append(index);return [JerseyEvidenceRecord(str(index),track,index,time,'7',1.)]
    args=(tmp_path,observations,compute_file_sha256(video),{'T':'a'})
    first=extract_jersey_evidence(*args,provider_factory=Provider)
    second=extract_jersey_evidence(*args,provider_factory=lambda **kw:pytest.fail('Cached evidence must not initialize OCR'))
    assert first==second and calls==[0,3]
    def unavailable(**kwargs):raise ModelWeightsUnavailableError('fixture missing weights')
    absent=extract_jersey_evidence(tmp_path,observations,args[2],{'T':'b'},provider_factory=unavailable)
    assert absent['status']=='unavailable' and absent['records']==[]


def test_roster_only_save_adds_names_to_spatial_frames_and_manual_override_wins(tmp_path,monkeypatch):
    import basketball_scoreboard.spatial_analysis as spatial
    import basketball_scoreboard.jersey_identity as identity
    from test_spatial_pipeline_regressions import _spatial
    rows=[dict(_observation(i*.1),frame_index=i) for i in range(5)]
    config=_spatial(tmp_path,rows);config.update(geometry_mode='automatic',classify_teams=True)
    matrix=spatial.SpatialProjector(config).segments[0][1]
    write_json(tmp_path/'analysis/automatic_geometry.json',dict(version=1,mode='automatic',format='3x3',fps=10,
        source_sha256=config['source_sha256'],width=config['width'],height=config['height'],
        supported_frames=5,total_frames=5,frames=[dict(frame_index=i,time_s=i*.1,shot_id='s',
        image_to_court=matrix.tolist()) for i in range(5)]))
    monkeypatch.setattr(spatial,'infer_team_votes',lambda *a,**kw:{'track-1':'a'})
    monkeypatch.setattr(identity,'extract_jersey_evidence',lambda *a,**kw:dict(status='completed',
        records=[reading('track-1',i) for i in range(3)]))
    result=spatial.build_spatial_analysis(tmp_path,config)
    assert not config['assignments']
    assert any(p['player_id']=='a7' for f in result['frames'] for p in f['players'])
    config['assignments']=[dict(track_id='track-1',start_s=0,end_s=1,role='non_player',team_id=None,player_id=None)]
    hidden=spatial.build_spatial_analysis(tmp_path,config)
    assert all(not f['players'] for f in hidden['frames'])
    assert np.sum(hidden['heatmaps']['all'])==0


def test_overlay_api_uses_current_identity_without_mutating_source_boxes():
    from copy import deepcopy
    from basketball_scoreboard.dashboard import overlay_with_spatial_identity
    original=dict(frames=[dict(time=1.,boxes=[dict(id='T',box=[1,2,30,40],player_id='old',team_id='old_team',role='player')])])
    before=deepcopy(original)
    spatial=dict(status='completed',geometry_mode='automatic',frames=[dict(time=1.,players=[dict(id='T',player_id='a7',team_id='a',role='player')])])
    updated=overlay_with_spatial_identity(original,spatial)
    assert updated['frames'][0]['boxes'][0]['player_id']=='a7'
    assert updated['frames'][0]['boxes'][0]['box']==[1,2,30,40]
    assert original==before
    spatial['frames'][0]['players'][0]['player_id']=None
    unresolved=overlay_with_spatial_identity(original,spatial)
    assert 'player_id' not in unresolved['frames'][0]['boxes'][0]
    config=dict(assignments=[dict(track_id='T',start_s=0,end_s=2,role='non_player')])
    assert not overlay_with_spatial_identity(original,spatial,config)['frames'][0]['boxes']
