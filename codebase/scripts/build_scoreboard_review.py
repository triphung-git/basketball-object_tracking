#!/usr/bin/env python3
"""Export native-resolution scoring-review clips with PTS and draft-only labels."""
import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import sys

import av
import cv2
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_scoreboard_review import PARENT_SHA,digest,dump


def read_frame(container,stream,time_s):
    container.seek(int(time_s/float(stream.time_base)),stream=stream,backward=True)
    for frame in container.decode(stream):
        if frame.pts is not None and float(frame.pts*frame.time_base)+1e-6>=time_s:
            return frame
    raise ValueError('Missing source frame')


def export_clip(source,path,start_s,end_s):
    """No -c copy: every clip starts on the exact selected original 30fps frame."""
    count=0; parent_first=None; parent_last=None
    with av.open(str(source)) as src, av.open(str(path),'w',options={'movflags':'+faststart'}) as dst:
        video=src.streams.video[0];video.thread_type='AUTO'
        output=dst.add_stream('libx264',rate=30)
        output.width=1920;output.height=1080;output.pix_fmt='yuv420p'
        output.options={'crf':'21','preset':'veryfast','threads':'2'}
        src.seek(int(start_s/float(video.time_base)),stream=video,backward=True)
        for frame in src.decode(video):
            if frame.pts is None:raise ValueError('Missing original PTS')
            pts=float(frame.pts*frame.time_base)
            if pts+1e-6<start_s:continue
            if pts+1e-6>=end_s:break
            if parent_first is None:parent_first=pts
            parent_last=pts
            frame.pts=count;frame.time_base=Fraction(1,30)
            for packet in output.encode(frame):dst.mux(packet)
            count+=1
        for packet in output.encode():dst.mux(packet)
    if count!=round((end_s-start_s)*30):raise ValueError('Unexpected source frame count')
    with av.open(str(path)) as check:
        pts=[float(f.pts*f.time_base) for f in check.decode(video=0)]
    error=max(abs(t-i/30) for i,t in enumerate(pts)) if pts else math.inf
    if len(pts)!=count or error>2e-6:raise ValueError('Clip PTS validation failed')
    return dict(frames=count,parent_first_pts_s=parent_first,parent_last_pts_s=parent_last,
                clip_first_pts_s=pts[0],clip_last_pts_s=pts[-1],max_pts_error_s=error,
                sha256=digest(path),bytes=path.stat().st_size,audio=False,
                resolution=[1920,1080],fps=30,transcoded=True,pixel_identical=False)


def build(args):
    source=Path(args.source).resolve();out=Path(args.output_dir).resolve()
    scan_dir=Path(args.scan_dir).resolve()
    if digest(source)!=PARENT_SHA:raise ValueError('Wrong source')
    if (out/'review-manifest.json').exists():raise FileExistsError('Do not overwrite a review packet')
    states=json.loads((scan_dir/'score-states.json').read_text())
    candidates=json.loads((scan_dir/'score-change-candidates.json').read_text())
    if any(e['kind']!='single_team_score_increase' or e['gap_s']>15 for e in candidates):
        raise ValueError('Resolve score gaps/anomalies before exporting scoring-review packet')
    for directory in ('clips','frames','score-evidence'):(out/directory).mkdir(exist_ok=True)
    preferred=set(args.priority_ids.split(',')) if args.priority_ids else set()
    roster=json.loads(Path(args.roster).read_text(encoding='utf-8'))
    entries=[]
    with av.open(str(source)) as container:
        stream=container.streams.video[0];stream.thread_type='AUTO'
        for index,event in enumerate(candidates,1):
            event_id=f'play_{index:03d}'
            end=event['after']['start_s']+5.
            start=max(0.,event['before']['last_s']-12.)
            start=round(start*30)/30;end=round(end*30)/30
            name=f'clips/{event_id}.mp4'
            print(json.dumps(dict(exporting=event_id,start_s=start,end_s=end)),flush=True)
            integrity=export_clip(source,out/name,start,end)
            keyframes=[]
            # Uniform frames are navigation aids, not inferred release/basket labels.
            for n,offset in enumerate((0.,.25,.45,.6,.75,1.)):
                t=round((start+offset*(end-start-1/30))*30)/30
                frame=read_frame(container,stream,t)
                image=frame.to_ndarray(format='bgr24')
                relative=f'frames/{event_id}_{n}.jpg'
                cv2.imwrite(str(out/relative),image,[cv2.IMWRITE_JPEG_QUALITY,95])
                keyframes.append(dict(image=relative,source_time_s=t,clip_time_s=t-start,
                                      source_frame_index=round(t*30)))
            evidence={}
            for label,state,key in [('before',event['before'],'last_image'),('after',event['after'],'first_image')]:
                rel=f'score-evidence/{event_id}-{label}.jpg'
                (out/rel).write_bytes((scan_dir/state[key]).read_bytes());evidence[label]=rel
            entry=dict(id=event_id,candidate_id=event['candidate_id'],video=name,
                 start_s=start,end_s=end,duration_s=end-start,source_time_offset_s=start,
                 time_mapping='parent_time_s = clip_time_s + source_time_offset_s',
                 before_score_tga_vie=event['before']['score'],after_score_tga_vie=event['after']['score'],
                 draft_scoring_team='team_b' if event['delta'][0] else 'team_a',
                 draft_points=max(event['delta']),scoreboard_update_bracket_s=event['scoreboard_update_bracket_s'],
                 evidence=evidence,keyframes=keyframes,integrity=integrity,
                 recommended=event_id in preferred,review_status='pending',
                 release_time_s=None,basket_time_s=None,shooter_id=None,
                 warning='Score change identifies a review candidate, not a proven made field goal; FT, replay and visibility need review')
            entries.append(entry)
            dump(out/'build-progress.json',dict(completed=len(entries),entries=entries))
    manifest=dict(schema_version='scoreboard-shot-review-1',status='pending_user_review',
         source_video=str(source),source_sha256=PARENT_SHA,source_frames=41432,source_fps=30,
         source_group='vietnam_tonga_same_match_exposed_development',
         selection='Source scoreboard changes; annotation aid only, prohibited as recognition input',
         source_scan_sha256=digest(scan_dir/'scoreboard-samples.jsonl'),
         candidates_sha256=digest(scan_dir/'score-change-candidates.json'),
         roster_sha256=digest(args.roster),players=roster['players'],entries=entries,
         initial_score_tga_vie=states[0]['score'],final_score_tga_vie=states[-1]['score'],
         global_recall_claim=False,precision_requires_negative_cases=True,
         limitations=['Scoreboard may update late; its timestamp is not the basket timestamp',
             'No automatically inferred shooter/release/basket/made-miss labels',
             'Replay/close-up may occur within a clip; user reviews actual action',
             'No independent holdout or realtime measurement','Audio omitted; original 1080p spatial size retained'])
    dump(out/'review-manifest.json',manifest)
    template=Path(__file__).with_name('scoreboard_shot_review.html').read_text(encoding='utf-8')
    payload=json.dumps(manifest,ensure_ascii=False).replace('<','\\u003c')
    template=template.replace('__PACKET__',payload).replace('__MANIFEST_SHA__',digest(out/'review-manifest.json'))
    (out/'review.html').write_text(template,encoding='utf-8')
    (out/'Mo-review-bang-trinh-duyet.cmd').write_bytes(
        b'@echo off\r\n"%~dp0..\\..\\.venv\\Scripts\\python.exe" "%~dp0..\\..\\scripts\\open_scoreboard_review.py" --packet-dir "%~dp0."\r\nif errorlevel 1 pause\r\n')
    print(json.dumps(dict(status='completed',clips=len(entries),recommended=sum(e['recommended'] for e in entries))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',default='codebase/assets_test/vietnam-tonga.mp4')
    parser.add_argument('--roster',default='codebase/configs/rosters/vietnam_tonga.json')
    parser.add_argument('--scan-dir',required=True)
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--priority-ids',default='')
    build(parser.parse_args())
