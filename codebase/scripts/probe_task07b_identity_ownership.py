#!/usr/bin/env python3
"""Decode the fixed source stream; compare legacy and guarded crops without GT."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
import warnings
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from basketball_scoreboard.identity import LocalEasyOCRProvider,RosterConfig,TeamColorClassifier,extract_jersey_rgb
from basketball_scoreboard.identity_crops import IdentityCropGuard,load_identity_crop_policy,jersey_region
from basketball_scoreboard.spatial_io import file_hash,new_output,write_json
from basketball_scoreboard.video import VideoReader


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['manifest','video','detections','tracks','policy','roster','output-dir']:p.add_argument('--'+name,required=True)
    p.add_argument('--legacy-predictions',help='Reuse frozen legacy rows from the identical source-crop probe')
    args=p.parse_args();manifest=json.loads(Path(args.manifest).read_text());source_hash=file_hash(args.video)
    if source_hash!=manifest['source_bindings']['identity']['video_sha256']:raise ValueError('Wrong identity source')
    roster=RosterConfig.from_dict(json.loads(Path(args.roster).read_text(encoding='utf-8')))
    policy=load_identity_crop_policy(args.policy,source_hash)
    guard=IdentityCropGuard(policy,[roster.team_a_color_rgb,roster.team_b_color_rgb])
    classifier=TeamColorClassifier(roster.team_a_id,roster.team_b_id,roster.team_a_color_rgb,roster.team_b_color_rgb)
    source_frames={r['frame_index']:r for r in map(json.loads,Path(args.detections).read_text().splitlines())}
    observations={}
    for r in map(json.loads,Path(args.tracks).read_text().splitlines()):observations.setdefault(r['frame_index'],[]).append(r)
    selected={(r['source_binding']['frame_index'],r['source_binding']['track_id']):r for r in manifest['selected_identities']}
    out=new_output(args.output_dir,[args.manifest,args.video,args.detections,args.tracks,args.policy,args.roster]);(out/'crops').mkdir()
    provider=LocalEasyOCRProvider(model_storage_directory=ROOT/'.model-cache/easyocr',gpu=False,crop_upscale=3)
    legacy={}
    if args.legacy_predictions:
        path=Path(args.legacy_predictions);meta=json.loads((path.parent/'run.json').read_text())
        if (meta['status']!='completed' or meta['predictions_sha256']!=file_hash(path) or
            meta['source_video_sha256']!=source_hash or meta['source_detections_sha256']!=file_hash(args.detections) or
            meta['source_tracks_sha256']!=file_hash(args.tracks) or meta['OCR_upscale']!=3):
            raise ValueError('Legacy OCR cache source differs')
        legacy={r['sample_id']:r for r in map(json.loads,path.read_text().splitlines()) if r['profile']=='legacy'}
        if set(legacy)!={s['sample_id'] for s in selected.values()}:raise ValueError('Legacy crop scope differs')
        if meta['weights_sha256']!={n:file_hash(provider.storage_dir/n) for n in ['craft_mlt_25k.pth','english_g2.pth']}:
            raise ValueError('Legacy OCR cache weights differ')
    rows=[]
    with warnings.catch_warnings(),VideoReader(args.video) as video:
        warnings.simplefilter('ignore')
        for f,image in video.frames():
            if f.frame_index not in source_frames:continue
            detections=source_frames[f.frame_index]['detections']
            for obs in observations.get(f.frame_index,[]):
                o=SimpleNamespace(**obs)
                if o.sample_type!='observed':continue
                processed,rgb,info=guard.assess(o,image,detections)
                sample=selected.get((o.frame_index,o.track_id))
                if not sample:continue
                a,b,c,d=jersey_region(o.bbox,image.shape[1],image.shape[0]);raw=image[b:d,a:c]
                if [a,b,c,d]!=sample['source_binding']['jersey_crop_xyxy']:raise ValueError('Original crop differs')
                x1,y1,x2,y2=o.bbox;w,h=x2-x1,y2-y1
                legacy_color=image[max(0,int(y1+.15*h)):min(image.shape[0],int(y1+.6*h)),max(0,int(x1+.2*w)):min(image.shape[1],int(x2-.2*w))]
                old_rgb,_=extract_jersey_rgb(legacy_color,[roster.team_a_color_rgb,roster.team_b_color_rgb])
                for profile,crop,team_rgb,allowed in [('legacy',raw,old_rgb,True),('guarded',processed,rgb,info['allowed'])]:
                    if profile=='legacy' and legacy:
                        rows.append(legacy[sample['sample_id']]);cv2.imwrite(str(out/'crops'/f'{sample["sample_id"]}-{profile}.png'),crop)
                        continue
                    readings=provider.read_jersey(crop,o.track_id,o.frame_index,o.source_time_s) if allowed else []
                    team,score,reason=classifier.classify_rgb(team_rgb) if team_rgb is not None else (None,None,'no_color_support')
                    row=dict(profile=profile,sample_id=sample['sample_id'],ocr_readings=[asdict(r) for r in readings],
                        team_id=team,team_score=score,allowed=allowed,guard=info if profile=='guarded' else None)
                    if crop is not None:cv2.imwrite(str(out/'crops'/f'{sample["sample_id"]}-{profile}.png'),crop)
                    rows.append(row)
                print('Compared source crop',sample['sample_id'],info['reason'],flush=True)
    with (out/'predictions.jsonl').open('x',encoding='utf-8') as handle:
        for row in rows:handle.write(json.dumps(row)+'\n')
    if len(rows)!=2*len(selected):raise ValueError('Not all source samples processed')
    write_json(out/'run.json',dict(status='completed',gt_read=False,manifest_sha256=file_hash(args.manifest),
        policy_sha256=file_hash(args.policy),predictions_sha256=file_hash(out/'predictions.jsonl'),source_video_sha256=source_hash,
        source_detections_sha256=file_hash(args.detections),source_tracks_sha256=file_hash(args.tracks),
        OCR_upscale=3,provider_stats=provider.stats,weights_sha256={n:file_hash(provider.storage_dir/n) for n in ['craft_mlt_25k.pth','english_g2.pth']},
        legacy_predictions_sha256=file_hash(args.legacy_predictions) if args.legacy_predictions else None,
        note='Legacy/guarded same decoded pixels. Team region differs explicitly; no final identity measured.'))
    for path in [Path(__file__),ROOT/'src/basketball_scoreboard/identity_crops.py']:shutil.copyfile(path,out/path.name)
    return 0


if __name__=='__main__':sys.exit(main())
