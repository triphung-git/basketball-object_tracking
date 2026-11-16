#!/usr/bin/env python3
"""Offline annotation aid: sample a source-bound broadcast scoreboard, not a stats engine.

Scoreboard-derived events remain review candidates. This script never supplies
scoreboard readings or review labels to basketball event recognition.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import av
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from basketball_scoreboard.identity import LocalEasyOCRProvider

PARENT_SHA = '1443c1d263c8037a5684f3dbc0ef9216beb5097d9a47c4c1c9b94d1363e26865'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for part in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def dump(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def score_panel(frame, team):
    """Camera-specific white score column, excluding adjacent foul column."""
    y = 938 if team == 'TGA' else 989
    shift = (y - 938) * .235
    source = np.float32([[416-shift,y],[490-shift,y],
                         [480-shift,y+43],[406-shift,y+43]])
    target = np.float32([[0,0],[74,0],[74,43],[0,43]])
    patch = cv2.warpPerspective(frame, cv2.getPerspectiveTransform(source,target), (74,43))
    return patch[2:41,6:66]


def score_patch(frame, team):
    gray = cv2.cvtColor(score_panel(frame,team), cv2.COLOR_BGR2GRAY)
    binary = cv2.threshold(gray,110,255,cv2.THRESH_BINARY)[1]
    # Remove the slanted panel edge, never a central digit component.
    count,labels,stats,_=cv2.connectedComponentsWithStats((binary<128).astype(np.uint8))
    for label in range(1,count):
        x,y,w,h,area=stats[label]
        if (x==0 or x+w==binary.shape[1]) and h>.8*binary.shape[0]:
            binary[labels==label]=255
    return cv2.copyMakeBorder(cv2.resize(binary,None,fx=2,fy=2),20,20,20,20,
                              cv2.BORDER_CONSTANT,value=255)


def scan(args):
    source, out = Path(args.source).resolve(), Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if (out/'scoreboard-samples.jsonl').exists():
        raise FileExistsError('Use a fresh output directory; prior scan is immutable')
    if digest(source) != PARENT_SHA:
        raise ValueError('HUD coordinates are scoped to the approved Vietnam-Tonga source')
    cap = cv2.VideoCapture(str(source)); cap.set(cv2.CAP_PROP_POS_MSEC,300000)
    ok, reference = cap.read(); cap.release()
    if not ok or reference.shape[:2] != (1080,1920):
        raise ValueError('Expected original 1920x1080 source')
    # The fixed team-label artwork is used only as an overlay-presence check.
    ref = cv2.cvtColor(reference[940:1030,150:290],cv2.COLOR_BGR2GRAY)
    provider = LocalEasyOCRProvider(model_storage_directory=ROOT/'.model-cache/easyocr',gpu=False)
    reader = provider.reader
    weights = {p.name:digest(p) for p in provider.storage_dir.glob('*.pth')}
    crops = out/'scoreboard-samples'; crops.mkdir()
    cache = {team:[] for team in ('TGA','VIE')}
    # Explicit, agent-inspected font calibration is annotation assistance only.
    # These values must never be used in the automatic basketball event engine.
    seeds=[(540,'VIE',7),(345,'TGA',7),(385,'TGA',8),(995,'TGA',17),
           (1000,'VIE',17),(1045,'VIE',18),(1060,'VIE',19),
           (325,'TGA',6),(1192,'TGA',18),(1210,'TGA',19),
           (1200,'VIE',20),(1215,'VIE',21)]
    cap=cv2.VideoCapture(str(source))
    for seed_time,team,value in seeds:
        cap.set(cv2.CAP_PROP_POS_MSEC,seed_time*1000);ok,seed=cap.read()
        if not ok:raise ValueError('Cannot read font calibration frame')
        cache[team].append((score_patch(seed,team),value,1.,f'agent_inspected_font_at_{seed_time}s'))
    cap.release()
    next_s=0.; count=0; ocr_calls=0; started=time.perf_counter()
    with av.open(str(source)) as container, (out/'scoreboard-samples.jsonl').open('x',encoding='utf-8') as handle:
        stream=container.streams.video[0]; stream.thread_type='AUTO'
        for index, frame in enumerate(container.decode(stream)):
            if frame.pts is None: raise ValueError('Source PTS required')
            pts=float(frame.pts*frame.time_base)
            if pts+1e-6 < next_s: continue
            next_s += args.step_s
            image=frame.to_ndarray(format='bgr24')
            tag=cv2.cvtColor(image[940:1030,150:290],cv2.COLOR_BGR2GRAY)
            similarity=float(cv2.matchTemplate(tag,ref,cv2.TM_CCOEFF_NORMED)[0,0])
            present=similarity>=.80
            readings={}
            if present:
                for team in ('TGA','VIE'):
                    # Red score-change animation is not a stable white score cell.
                    panel=score_panel(image,team)
                    white_fraction=float(np.mean(np.min(panel,axis=2)>170))
                    if white_fraction<.40:
                        readings[team]=dict(value=None,confidence=0.,method='unstable_score_background',white_fraction=white_fraction)
                        continue
                    patch=score_patch(image,team)
                    match=None
                    for old,value,confidence,method in cache[team]:
                        difference=float(np.mean((patch<128)!=(old<128)))
                        if difference<.0015 and (match is None or difference<match[0]):
                            match=(difference,value,confidence,method)
                    if match:
                        _,value,confidence,method=match
                        readings[team]=dict(value=value,confidence=confidence,method='same_font_patch_cache',origin=method)
                    else:
                        raw=reader.recognize(patch,allowlist='0123456789',detail=1)
                        ocr_calls+=1
                        text=str(raw[0][1]).strip() if len(raw)==1 else ''
                        confidence=float(raw[0][2]) if len(raw)==1 else 0.
                        value=int(text) if text.isdigit() and len(text)<=2 and int(text)<=30 and confidence>=.45 else None
                        readings[team]=dict(value=value,confidence=confidence,text=text,method='local_easyocr')
                        if value is not None:
                            cache[team].append((patch,value,confidence,'local_easyocr'))
            name=f'{index:06d}.jpg'
            cv2.imwrite(str(crops/name),image[840:1045,85:580])
            row=dict(frame_index=index,source_time_s=pts,overlay_present=present,
                     overlay_similarity=similarity,readings=readings,image=f'scoreboard-samples/{name}')
            handle.write(json.dumps(row,allow_nan=False)+'\n'); handle.flush();count+=1
            if count%100==0:print(json.dumps(dict(samples=count,time_s=pts,ocr_calls=ocr_calls)),flush=True)
    dump(out/'scan.json',dict(status='completed',source=str(source),source_sha256=PARENT_SHA,
         samples=count,step_s=args.step_s,ocr_calls=ocr_calls,weights_sha256=weights,
         elapsed_s=time.perf_counter()-started,method='annotation_preparation_only_not_recognition',
         agent_inspected_font_seeds=[dict(time_s=t,team=k,value=v) for t,k,v in seeds],
         source_group='vietnam_tonga_same_match_exposed_development',
         all_events_review_status='pending',audio_used=False))


def candidates(args):
    out=Path(args.output_dir)
    rows=[json.loads(x) for x in (out/'scoreboard-samples.jsonl').read_text().splitlines()]
    states=[]; pending=[]
    for row in rows:
        values=tuple(row['readings'].get(team,{}).get('value') for team in ('TGA','VIE'))
        if None in values or not row['overlay_present']:
            pending=[];continue
        if pending and (values!=pending[-1][0] or row['source_time_s']-pending[-1][1]['source_time_s']>1.5*args.step_s):
            pending=[]
        pending.append((values,row))
        if len(pending)>=2:
            first=pending[0][1]
            if not states or states[-1]['score']!=list(values):
                states.append(dict(score=list(values),start_s=first['source_time_s'],
                    last_s=row['source_time_s'],first_image=first['image'],last_image=row['image']))
            else:
                states[-1].update(last_s=row['source_time_s'],last_image=row['image'])
    events=[]
    for before,after in zip(states,states[1:]):
        delta=[b-a for a,b in zip(before['score'],after['score'])]
        scoring=sum(x!=0 for x in delta)==1 and max(delta) in (1,2) and min(delta)>=0
        events.append(dict(candidate_id=f'score_{len(events)+1:03d}',before=before,after=after,
             delta=delta,kind='single_team_score_increase' if scoring else 'gap_correction_or_OCR_anomaly',
             scoreboard_update_bracket_s=[before['last_s'],after['start_s']],
             gap_s=after['start_s']-before['last_s'],review_status='pending',
             warning='Scoreboard update time is not release or basket time; replay/FT/score corrections require review'))
    dump(out/'score-states.json',states);dump(out/'score-change-candidates.json',events)
    print(json.dumps(dict(states=len(states),candidates=len(events),single_team_increases=sum(e['kind']=='single_team_score_increase' for e in events))))


def repair_font(args):
    """Repair unresolved OCR only by an explicitly source-inspected font patch.

    A separate derived scan preserves every original reading and an audit log.
    This is not approved GT and not runtime basketball recognition.
    """
    source=Path(args.source).resolve();out=Path(args.output_dir).resolve()
    prior=Path(args.input_scan).resolve()
    if digest(source)!=PARENT_SHA:raise ValueError('Wrong source')
    out.mkdir(parents=True,exist_ok=False)
    rows=[json.loads(x) for x in (prior/'scoreboard-samples.jsonl').read_text().splitlines()]
    t,team,value=args.font_seed.split(':');t=float(t);value=int(value)
    if team not in ('TGA','VIE') or not 0<=value<=30:raise ValueError('Invalid seed')
    cap=cv2.VideoCapture(str(source));cap.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,image=cap.read()
    if not ok:raise ValueError('Missing font seed')
    reference=score_patch(image,team);cv2.imwrite(str(out/'font-seed.png'),reference)
    repairs=[]
    for row in rows:
        current=row['readings'].get(team,{})
        if not row['overlay_present'] or current.get('value') is not None or current.get('method')=='unstable_score_background':continue
        cap.set(cv2.CAP_PROP_POS_MSEC,row['source_time_s']*1000);ok,image=cap.read()
        if not ok:raise ValueError('Missing repair source frame')
        patch=score_patch(image,team)
        difference=float(np.mean((reference<128)!=(patch<128)))
        if difference<.0015:
            repairs.append(dict(frame_index=row['frame_index'],source_time_s=row['source_time_s'],
                                previous=current,pixel_difference=difference))
            row['readings'][team]=dict(value=value,confidence=1.,method='agent_inspected_font_patch_repair',
                                      seed_time_s=t,seed_image_sha256=digest(out/'font-seed.png'))
    cap.release()
    # Relative media paths refer back to the original scan, without copying JPEGs.
    import os
    for row in rows:row['image']=Path(os.path.relpath(prior/row['image'],out)).as_posix()
    with (out/'scoreboard-samples.jsonl').open('x',encoding='utf-8') as handle:
        for row in rows:handle.write(json.dumps(row,allow_nan=False)+'\n')
    dump(out/'repairs.json',dict(purpose='annotation_preparation_only_pending_user_review',
         parent_scan_sha256=digest(prior/'scoreboard-samples.jsonl'),source_sha256=PARENT_SHA,
         agent_inspected_font_seed=dict(time_s=t,team=team,value=value),repairs=repairs))
    print(json.dumps(dict(repaired=len(repairs))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['scan','candidates','repair-font'])
    parser.add_argument('--source',default=str(ROOT/'assets_test/vietnam-tonga.mp4'))
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--step-s',type=float,default=1.)
    parser.add_argument('--input-scan')
    parser.add_argument('--font-seed')
    args=parser.parse_args()
    if not .25<=args.step_s<=5:parser.error('step must be .25-5 seconds')
    {'scan':scan,'candidates':candidates,'repair-font':repair_font}[args.action](args)
