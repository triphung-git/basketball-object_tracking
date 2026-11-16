#!/usr/bin/env python3
"""Download approved read-only raster QA samples; private URLs stay in stdin only."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlparse

import cv2
import numpy as np
import requests

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from basketball_scoreboard.spatial_io import new_output,write_json


def allowed(url):
    parsed=urlparse(url)
    if parsed.scheme!='https' or parsed.hostname not in {'source.roboflow.com','storage.googleapis.com','images.roboflow.com'}:
        raise ValueError('Only approved image CDN hosts allowed')


def download(url):
    for _ in range(4):
        allowed(url)
        response=requests.get(url,stream=True,allow_redirects=False,timeout=(15,45))
        if response.status_code in {301,302,303,307,308}:
            url=response.headers['Location'];response.close();continue
        if response.status_code!=200:
            code=response.status_code;response.close();raise ValueError('HTTP_'+str(code))
        parts=[];size=0
        try:
            for chunk in response.iter_content(65536):
                size+=len(chunk)
                if size>25*1024*1024:raise ValueError('Raster too large')
                parts.append(chunk)
        finally:response.close()
        return b''.join(parts)
    raise ValueError('Too many redirects')


def phash(image):
    gray=cv2.resize(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY),(32,32)).astype(np.float32)
    values=cv2.dct(gray)[:8,:8].flatten();bits=values>np.median(values[1:])
    return ''.join('1' if b else '0' for b in bits)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',required=True);args=p.parse_args()
    records=json.loads(base64.b64decode(sys.stdin.read().strip()).decode('utf-8'))
    if not isinstance(records,list) or not 1<=len(records)<=50:raise ValueError('Bounded QA sample required')
    if not Path(args.output_dir).resolve().is_relative_to((ROOT/'outputs').resolve()):raise ValueError('QA output must stay in codebase/outputs')
    out=new_output(args.output_dir);(out/'originals').mkdir();(out/'overlays').mkdir()
    saved=[];failed=[];thumbs=[]
    colors={'ball':(0,255,0),'human':(255,120,0),'rim':(0,220,255)}
    for index,row in enumerate(records):
        try:
            payload=download(row['url']);image=cv2.imdecode(np.frombuffer(payload,np.uint8),cv2.IMREAD_COLOR)
            if image is None:raise ValueError('Not a raster image')
            height,width=image.shape[:2]
            if width*height>40000000:raise ValueError('Raster dimensions too large')
            original=f'originals/{index:03d}.jpg';(out/original).write_bytes(payload)
            annotation=row['annotation'];overlay=image.copy()
            sx,sy=width/annotation['width'],height/annotation['height']
            for box in annotation.get('boxes',[]):
                x,y,w,h=box['x'],box['y'],box['width'],box['height']
                a,b,c,d=map(round,[(x-w/2)*sx,(y-h/2)*sy,(x+w/2)*sx,(y+h/2)*sy])
                cv2.rectangle(overlay,(a,b),(c,d),colors.get(box['label'],(255,255,255)),2)
                cv2.putText(overlay,box['label'],(max(0,a),max(15,b)),cv2.FONT_HERSHEY_SIMPLEX,.45,colors.get(box['label'],(255,255,255)),1)
            overlay_path=f'overlays/{index:03d}.jpg';assert cv2.imwrite(str(out/overlay_path),overlay)
            saved.append(dict(index=index,image_id=row['image_id'],split=row['split'],filename=row['filename'],sampling_scope=row['sampling_scope'],
                original=original,overlay=overlay_path,pixel_wh=[width,height],annotation_wh=[annotation['width'],annotation['height']],
                annotation=annotation,download_sha256=hashlib.sha256(payload).hexdigest(),phash=phash(image),
                aspect_ratio_matches=abs(width/height-annotation['width']/annotation['height'])<.005,
                review_status='draft',pixel_label_quality='unreviewed'))
            scale=min(320/width,220/height);small=cv2.resize(overlay,(max(1,round(width*scale)),max(1,round(height*scale))))
            tile=np.zeros((250,320,3),dtype=np.uint8);tile[30:30+small.shape[0],:small.shape[1]]=small
            cv2.putText(tile,f'{index:03d} {row["split"]}',(6,20),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1);thumbs.append(tile)
        except Exception as error:
            failed.append(dict(index=index,image_id=row.get('image_id'),error_class=type(error).__name__))
    pairs=[]
    for i,a in enumerate(saved):
        for b in saved[i+1:]:
            if a['split']==b['split']:continue
            distance=sum(x!=y for x,y in zip(a['phash'],b['phash']))
            if a['download_sha256']==b['download_sha256'] or distance<=6:
                pairs.append(dict(image_ids=[a['image_id'],b['image_id']],indices=[a['index'],b['index']],splits=[a['split'],b['split']],
                    exact_bytes=a['download_sha256']==b['download_sha256'],phash_distance=distance,
                    status='candidate_requires_visual_review'))
    if thumbs:
        while len(thumbs)%4:thumbs.append(np.zeros_like(thumbs[0]))
        assert cv2.imwrite(str(out/'contact-sheet.jpg'),np.vstack([np.hstack(thumbs[i:i+4]) for i in range(0,len(thumbs),4)]))
    write_json(out/'manifest.json',dict(status='downloaded_for_readonly_QA',requested=len(records),saved=len(saved),failed=failed,images=saved,
        cross_split_similarity_candidates=pairs,private_urls_saved=False,annotations_changed=False,training_started=False,
        scope='24ordered split samples plus targeted source family; not full-version audit'))
    html=['<!doctype html><meta charset="utf-8"><title>Original dataset label QA</title><style>body{font:15px Segoe UI;margin:24px}article{display:inline-block;vertical-align:top;margin:8px;padding:8px;border:1px solid #aaa}img{max-width:450px;max-height:350px}</style><h1>Original image and stored annotation - QA draft</h1><p>Read-only samples. Labels are not changed or approved by this gallery.</p>']
    for s in saved:html.append(f'<article><p>{s["index"]:03d} / {s["split"]}</p><img src="{s["original"]}"><img src="{s["overlay"]}"></article>')
    (out/'review.html').write_text('\n'.join(html),encoding='utf-8')
    print(json.dumps(dict(requested=len(records),saved=len(saved),failed=len(failed),cross_split_candidates=len(pairs))))
    return 0 if len(saved)==len(records) else 1


if __name__=='__main__':
    try:sys.exit(main())
    except Exception as error:print('Dataset QA preparation failed ('+type(error).__name__+')',file=sys.stderr);sys.exit(1)
