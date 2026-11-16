#!/usr/bin/env python3
"""Prepare bounded source-only frame candidates, without GT, inference or labels."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import av
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from basketball_scoreboard.spatial_io import file_hash,new_output,write_json
from basketball_scoreboard.video import probe_video


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','settings','output-dir'):p.add_argument('--'+name,required=True)
    args=p.parse_args();settings=json.loads(Path(args.settings).read_text(encoding='utf-8'));meta=probe_video(args.source)
    if settings.get('schema_version')!='task07a-local-pilot-1' or settings['parent_sha256']!=meta.sha256:
        raise ValueError('Source/settings mismatch')
    if settings['sampling_interval_s']!=1.:raise ValueError('Use one-second source sampling')
    windows=settings['windows'];prior=-1.
    for w in windows:
        a,b=w['start_s'],w['duration_s']
        if not 30<=b<=60 or a<prior or a+b>meta.duration_s:raise ValueError('Invalid or overlapping source window')
        prior=a+b
    out=new_output(args.output_dir,[args.source,args.settings]);(out/'images').mkdir()
    write_json(out/'run.json',dict(status='running',source_sha256=meta.sha256,settings_sha256=file_hash(args.settings)))
    samples=[];seen={};duplicates=[];thumbs=[]
    with av.open(args.source) as container:
        stream=container.streams.video[0]
        for w in windows:
            start,end=w['start_s'],w['start_s']+w['duration_s'];target=float(start)
            container.seek(int(start/stream.time_base),stream=stream,backward=True,any_frame=False)
            count=0
            for frame in container.decode(stream):
                if frame.pts is None:continue
                t=float(frame.pts*frame.time_base)
                if t<start-1e-6:continue
                if t>=end-1e-6:break
                if t+1e-6<target:continue
                target+=settings['sampling_interval_s']
                image=frame.to_ndarray(format='bgr24');raw_hash=hashlib.sha256(image.tobytes()).hexdigest()
                if raw_hash in seen:
                    duplicates.append(dict(source_time_s=t,duplicate_of=seen[raw_hash]));continue
                index=len(samples);filename=f'images/{index:04d}.jpg'
                if not cv2.imwrite(str(out/filename),image,[cv2.IMWRITE_JPEG_QUALITY,95]):raise OSError('Frame write failed')
                sample=dict(sample_id=f'pilot_{index:04d}',image=filename,image_sha256=file_hash(out/filename),pixel_sha256=raw_hash,
                    source_group=settings['source_group'],window_id=w['window_id'],parent_source_time_s=t,segment_time_s=t-start,
                    raw_pts=frame.pts,time_base=str(frame.time_base),original_wh=[image.shape[1],image.shape[0]],
                    cfr_frame_index=round(t*meta.fps),frame_index_policy='CFR index derived from PTS; raw PTS retained',
                    split='unassigned',review_status='unreviewed',scene_status='unreviewed',ball_visibility='unreviewed',
                    boxes=None,classes_required=['ball','human','rim'])
                seen[raw_hash]=sample['sample_id'];samples.append(sample);count+=1
                if count%10==1:
                    tile=cv2.resize(image,(384,216));cv2.putText(tile,f'{sample["sample_id"]} parent {t:.1f}s',(5,18),cv2.FONT_HERSHEY_SIMPLEX,.45,(0,255,255),1);thumbs.append(tile)
            print(w['window_id'],count,'source frames prepared',flush=True)
            write_json(out/'progress.json',dict(status='running',completed_window=w['window_id'],samples=len(samples)))
    write_json(out/'annotations-draft.json',dict(schema_version='task07a-pilot-labels-1',review_status='draft',reviewer=None,
        source_sha256=meta.sha256,source_group=settings['source_group'],samples=samples,training_ready=False,
        note='Null boxes mean unreviewed, never an empty/negative training label. No YOLO labels exported.'))
    write_json(out/'sampling-audit.json',dict(requested_samples=sum(w['duration_s'] for w in windows),saved=len(samples),
        exact_duplicate_pixels_removed=duplicates,temporal_interval_s=1.,all_one_source_group=True,
        original_labels_read=False,inference_performed=False,cloud_upload=False,training_started=False))
    if thumbs:
        while len(thumbs)%4:thumbs.append(np.zeros_like(thumbs[0]))
        assert cv2.imwrite(str(out/'contact-sheet.jpg'),np.vstack([np.hstack(thumbs[i:i+4]) for i in range(0,len(thumbs),4)]))
    html=['<!doctype html><meta charset="utf-8"><title>Local pilot - unreviewed</title><style>body{font:15px Segoe UI;margin:24px}article{display:inline-block;vertical-align:top;margin:6px}img{width:360px}</style><h1>Local pilot source frames - UNREVIEWED</h1><p>No detection labels or splits approved. Closeups, replay, tiny-ball and background cases must be reviewed; no training labels exported.</p>']
    for s in samples:html.append(f'<article><p>{s["sample_id"]} / {s["parent_source_time_s"]:.3f}s</p><img loading="lazy" src="{s["image"]}"></article>')
    (out/'review.html').write_text('\n'.join(html),encoding='utf-8')
    write_json(out/'run.json',dict(status='completed',source_sha256=meta.sha256,settings_sha256=file_hash(args.settings),
        sampling_windows=windows,samples=len(samples),training_ready=False,split_status='unassigned_same_source_group'))
    write_json(out/'progress.json',dict(status='completed',samples=len(samples)))
    print('Completed source-only pilot',len(samples));return 0


if __name__=='__main__':
    try:sys.exit(main())
    except Exception as error:print('Pilot preparation failed ('+type(error).__name__+')',file=sys.stderr);sys.exit(1)
