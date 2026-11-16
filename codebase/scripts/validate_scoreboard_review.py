#!/usr/bin/env python3
"""Check prepared media, provenance and browser QA, without approving labels."""
import argparse
import json
from pathlib import Path
import re
import sys

import av
import cv2

sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_scoreboard_review import PARENT_SHA,digest,dump


def validate(out):
    out=Path(out).resolve()
    packet=json.loads((out/'review-manifest.json').read_text(encoding='utf-8'))
    assert packet['source_sha256']==PARENT_SHA==digest(packet['source_video'])
    assert packet['status']=='pending_user_review'
    entries=packet['entries'];assert len(entries)==34
    assert len({e['id'] for e in entries})==34
    assert sum(e['recommended'] for e in entries)==8
    assert packet['initial_score_tga_vie']==[0,0] and packet['final_score_tga_vie']==[19,21]
    total_frames=0;total_bytes=0;durations=[]
    def resource(relative):
        path=(out/relative).resolve()
        if not path.is_relative_to(out):raise ValueError('Packet media escaped output root')
        if not path.is_file():raise ValueError('Missing packet media')
        return path
    previous=[0,0]
    for e in entries:
        assert e['review_status']=='pending'
        assert e['shooter_id'] is None and e['release_time_s'] is None and e['basket_time_s'] is None
        assert e['before_score_tga_vie']==previous
        delta=[b-a for a,b in zip(previous,e['after_score_tga_vie'])]
        assert sum(x!=0 for x in delta)==1 and min(delta)==0 and max(delta) in (1,2)
        assert e['draft_points']==max(delta)
        assert e['draft_scoring_team']==('team_b' if delta[0] else 'team_a')
        previous=e['after_score_tga_vie']
        media=resource(e['video']);assert digest(media)==e['integrity']['sha256']
        assert abs(e['duration_s']-(e['end_s']-e['start_s']))<1e-6
        assert e['integrity']['frames']==round(e['duration_s']*30)
        assert e['integrity']['max_pts_error_s']<=2e-6
        assert abs(e['integrity']['parent_first_pts_s']-e['start_s'])<=2e-6
        assert abs(e['integrity']['parent_last_pts_s']-(e['end_s']-1/30))<=2e-6
        with av.open(str(media)) as container:
            stream=container.streams.video[0]
            assert stream.width==1920 and stream.height==1080
            assert float(stream.average_rate)==30
            assert len(container.streams.audio)==0
        for name in e['evidence'].values():
            image=cv2.imread(str(resource(name)));assert image.shape[:2]==(205,495)
        assert len(e['keyframes'])==6
        for k in e['keyframes']:
            image=cv2.imread(str(resource(k['image'])));assert image.shape[:2]==(1080,1920)
            assert abs(k['source_time_s']-(k['clip_time_s']+e['start_s']))<2e-6
            assert k['source_frame_index']==round(k['source_time_s']*30)
        total_frames+=e['integrity']['frames'];total_bytes+=media.stat().st_size;durations.append(e['duration_s'])
    html=(out/'review.html').read_text(encoding='utf-8')
    payload=re.search(r'<script id="packet" type="application/json">(.*?)</script>',html,re.S)
    assert json.loads(payload.group(1))==packet
    assert digest(out/'review-manifest.json') in html
    assert (out/'Mo-review-bang-trinh-duyet.cmd').is_file()
    assert 'open_scoreboard_review.py' in (out/'Mo-review-bang-trinh-duyet.cmd').read_text()
    browser=json.loads((out/'ui-qa/browser-results.json').read_text(encoding='utf-8'))
    assert browser['status']=='passed' and browser['real_review_status']=='all_pending'
    assert not browser['errors']
    playback_path=out/'ui-qa/playback-fix-results.json'
    playback=json.loads(playback_path.read_text(encoding='utf-8')) if playback_path.exists() else None
    if playback:
        assert playback['status']=='passed' and not playback['errors']
        assert playback['all_34_clips_browser_decoded_and_seeked']
    # Compare locked labels and source against prior approved audit, not new labels.
    baseline=Path('codebase/outputs/acceptance-20261104-task07/before.json')
    locked=json.loads(baseline.read_text())
    locked={name:value for name,value in locked.items() if name.startswith('codebase/data/')}
    for name,value in locked.items():assert digest(name)==value,(name,'locked data changed')
    prior=json.loads(Path('codebase/outputs/task07b-ownership-20261106/freeze.json').read_text())
    prior_sources={name:value for name,value in prior.items() if name.startswith(('codebase/src/','codebase/configs/','codebase/scripts/','codebase/tests/'))}
    for name,value in prior_sources.items():assert digest(name)==value,(name,'prior implementation changed')
    canonical='codebase/data/matches/vietnam_tonga/reviewed-vt_development-v2.json'
    assert digest(canonical)=='ee3f10d78164fe4d1b3301e80cb77896ddf3717fae87c45424721c068506b81d'
    weights=json.loads((out/'scan-v4/scan.json').read_text())['weights_sha256']
    for name,value in weights.items():assert digest(Path('codebase/.model-cache/easyocr')/name)==value
    result=dict(status='passed_preparation_and_review_tooling_not_recognition_acceptance',
        source_sha256=PARENT_SHA,manifest_sha256=digest(out/'review-manifest.json'),
        clips=len(entries),priority_clips=8,frames_exported_and_fully_decoded_at_build=total_frames,
        total_clip_bytes=total_bytes,duration_range_s=[min(durations),max(durations)],
        total_clip_duration_s=sum(durations),recommended_duration_s=sum(e['duration_s'] for e in entries if e['recommended']),
        all_clips_1080p_30fps=True,max_export_pts_error_s=max(e['integrity']['max_pts_error_s'] for e in entries),
        scoreboard_evidence_images=2*len(entries),original_source_keyframes=6*len(entries),
        browser_checks_passed=len(browser['checks']),browser_errors=[],
        playback_recovery_checks_passed=len(playback['checks']) if playback else None,
        external_browser_launcher_present=True,
        locked_dataset_files_unchanged=len(locked),prior_source_config_test_files_unchanged=len(prior_sources),
        canonical_control_GT_unchanged=True,OCR_weights_unchanged=True,
        pending_user_review=len(entries),approved_labels=0,training_started=False,
        detector_inference_run=False,automatic_scoring_accuracy_measured=False,
        scoreboard_used_only_for_annotation_preparation=True,
        task07_status='IN_PROGRESS',task08_status='TODO',same_match_exposed=True)
    dump(out/'packet-integrity.json',result)
    print(json.dumps(result,ensure_ascii=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',required=True)
    validate(parser.parse_args().output_dir)
