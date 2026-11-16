#!/usr/bin/env python3
"""GT-free local OCR/team probe on the fixed pre-review 14-crop subset."""
import argparse
from dataclasses import asdict
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys
import time
import warnings
import cv2

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from basketball_scoreboard.identity import LocalEasyOCRProvider, RosterConfig, TeamColorClassifier, extract_jersey_rgb
from basketball_scoreboard.spatial_io import file_hash,new_output,write_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',required=True);p.add_argument('--roster-config',required=True);p.add_argument('--output-dir',required=True)
    p.add_argument('--scales',nargs='+',type=int,choices=[1,2,3,4],default=[1,2])
    args=p.parse_args();manifest=json.loads(Path(args.manifest).read_text(encoding='utf-8'))
    if manifest['schema_version']!='task07a-checkpoint-a-manifest-1':raise ValueError('Unknown manifest')
    media=Path(args.manifest).resolve().parent
    roster=RosterConfig.from_dict(json.loads(Path(args.roster_config).read_text(encoding='utf-8')))
    out=new_output(args.output_dir,[args.manifest,args.roster_config])
    provider=LocalEasyOCRProvider(model_storage_directory=ROOT/'.model-cache/easyocr',gpu=False,crop_upscale=1)
    classifier=TeamColorClassifier(roster.team_a_id,roster.team_b_id,roster.team_a_color_rgb,roster.team_b_color_rgb)
    runtime=dict(manifest_sha256=file_hash(args.manifest),roster_sha256=file_hash(args.roster_config),
        source_identity_video_sha256=manifest['source_bindings']['identity']['video_sha256'],
        profiles=[dict(name='native' if scale==1 else 'upscale'+str(scale),crop_upscale=scale) for scale in args.scales],
        weights_sha256={name:file_hash(provider.storage_dir/name) for name in ['craft_mlt_25k.pth','english_g2.pth']},
        packages={name:importlib.metadata.version(name) for name in ['easyocr','torch','opencv-python']},
        gpu=False,download_enabled=False,gt_read=False,training_started=False,
        note='All selected crops fixed before human labels. Explicit OCR scale profiles; color extraction identical across profiles. Not tracking or final identity.')
    write_json(out/'run.json',dict(status='running',**runtime));started=time.perf_counter()
    with (out/'predictions.jsonl').open('x',encoding='utf-8') as handle,warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for profile in runtime['profiles']:
            provider.crop_upscale=profile['crop_upscale']
            for row in manifest['selected_identities']:
                path=(media/row['crop']).resolve();binding=row['source_binding']
                if not path.is_relative_to(media) or file_hash(path)!=binding['crop_source_sha256']:raise ValueError('Crop binding differs')
                crop=cv2.imread(str(path));call_start=time.perf_counter()
                readings=provider.read_jersey(crop,binding['track_id'],binding['frame_index'],binding['source_time_s'])
                rgb,quality=extract_jersey_rgb(crop,[roster.team_a_color_rgb,roster.team_b_color_rgb])
                team,score,reason=classifier.classify_rgb(rgb) if rgb is not None else (None,None,'insufficient_color_pixels')
                result=dict(profile=profile['name'],sample_id=row['sample_id'],crop_sha256=file_hash(path),
                    ocr_readings=[asdict(r) for r in readings],team_id=team,team_score=score,team_reason=reason,
                    color_quality=quality,call_s=time.perf_counter()-call_start)
                handle.write(json.dumps(result)+'\n');handle.flush()
            print('Completed fixed crop profile',profile['name'],flush=True)
    write_json(out/'run.json',dict(status='completed',**runtime,wall_s=time.perf_counter()-started,
        calls=len(runtime['profiles'])*len(manifest['selected_identities']),provider_stats=provider.stats,
        predictions_sha256=file_hash(out/'predictions.jsonl')))
    shutil.copyfile(__file__,out/'script-snapshot.py');shutil.copyfile(ROOT/'src/basketball_scoreboard/identity.py',out/'identity-source-snapshot.py')
    return 0


if __name__=='__main__':sys.exit(main())
