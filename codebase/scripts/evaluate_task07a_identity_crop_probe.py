#!/usr/bin/env python3
"""Evaluate frozen crop predictions after inference; labels never rank OCR reads."""
import argparse
import copy
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from basketball_scoreboard.review_diagnostics import identity_proposal_diagnostics
from basketball_scoreboard.spatial_io import file_hash,new_output,write_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-dir',required=True);p.add_argument('--reviewed',required=True);p.add_argument('--output-dir',required=True)
    args=p.parse_args();run_dir=Path(args.run_dir);meta=json.loads((run_dir/'run.json').read_text())
    reviewed=json.loads(Path(args.reviewed).read_text(encoding='utf-8-sig'))
    predictions=run_dir/'predictions.jsonl'
    if (meta['status']!='completed' or meta['gt_read'] is not False or
        meta['manifest_sha256']!=reviewed['manifest_sha256'] or file_hash(predictions)!=meta['predictions_sha256']):
        raise ValueError('Prediction/manifest freeze differs')
    rows=[json.loads(line) for line in predictions.read_text().splitlines() if line.strip()]
    expected={row['sample_id']:row for row in reviewed['identities']};results={}
    profile_names=[p['name'] for p in meta['profiles']]
    if set(r['profile'] for r in rows)!=set(profile_names):raise ValueError('Unexpected profiles')
    for name in profile_names:
        selected=[r for r in rows if r['profile']==name];lookup={r['sample_id']:r for r in selected}
        if len(lookup)!=len(selected) or set(lookup)!=set(expected):raise ValueError('Crop sample set differs')
        packet=copy.deepcopy(reviewed)
        for row in packet['identities']:
            prediction=lookup[row['sample_id']]
            if prediction['crop_sha256']!=row['source_binding']['crop_source_sha256']:raise ValueError('Crop source changed')
            row['predictions']=dict(ocr_readings=prediction['ocr_readings'],team_id=prediction['team_id'])
        result=identity_proposal_diagnostics(packet)
        result['scope']='fresh_local_OCR_and_color_proposal_agreement_on_fixed_pre_review_crops'
        results[name]=result
    out=new_output(args.output_dir,[args.run_dir,args.reviewed])
    summary=dict(status='completed_diagnostic_only',source_predictions_sha256=file_hash(predictions),
        source_run_sha256=file_hash(run_dir/'run.json'),reviewed_sha256=file_hash(args.reviewed),
        profiles=results,promoted=False,training_started=False,
        limitations=['Only five readable reviewed crops; selected diagnostic cases, same match',
                     'Color uses fixed jersey crop; historical team proposals came from tracker evidence, not an isolated algorithm A/B',
                     'No final resolver, temporal identity or event accuracy measured'])
    write_json(out/'evaluation.json',summary)
    print(json.dumps({name:{k:v for k,v in result.items() if k not in ('rows','visibility_counts','limitation')} for name,result in results.items()}))
    return 0


if __name__=='__main__':sys.exit(main())
