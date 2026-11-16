#!/usr/bin/env python3
"""Evaluate frozen source-only ownership trials against the reviewed subset."""
import argparse
import copy
from collections import Counter
import html
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from basketball_scoreboard.review_diagnostics import identity_proposal_diagnostics
from basketball_scoreboard.identity import RosterConfig
from basketball_scoreboard.spatial_io import file_hash,new_output,write_json


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def jsonl(path):return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['experiment-dir','manifest','reviewed','roster','output-dir']:p.add_argument('--'+name,required=True)
    args=p.parse_args();base=Path(args.experiment_dir);manifest=read(args.manifest);reviewed=read(args.reviewed)
    if reviewed['manifest_sha256']!=file_hash(args.manifest):raise ValueError('Reviewed source differs')
    out=new_output(args.output_dir,[args.experiment_dir,args.manifest,args.reviewed,args.roster])
    summary={};all_rows=[]
    for probe_name in ['source-crop-probe','recovery-crop-probe','final-crop-probe']:
        meta=read(base/probe_name/'run.json');pred_path=base/probe_name/'predictions.jsonl'
        if meta['status']!='completed' or meta['gt_read'] is not False or meta['manifest_sha256']!=file_hash(args.manifest) or meta['predictions_sha256']!=file_hash(pred_path):
            raise ValueError('Probe freeze differs')
        predictions=jsonl(pred_path);bykey={(r['profile'],r['sample_id']):r for r in predictions}
        if len(bykey)!=2*len(reviewed['identities']):raise ValueError('Prediction scope differs')
        profiles={}
        for profile in ['legacy','guarded']:
            packet=copy.deepcopy(reviewed);kept_good=blocked_bad=good=bad=0
            for row in packet['identities']:
                pred=bykey[(profile,row['sample_id'])]
                row['predictions']=dict(ocr_readings=pred['ocr_readings'],team_id=pred['team_id'])
                correct=row['labels']['crop_assessment']=='correct'
                good+=correct;bad+=not correct;kept_good+=correct and pred['allowed'];blocked_bad+=not correct and not pred['allowed']
            diag=identity_proposal_diagnostics(packet)
            diag.update(scope='same_decoded_source_crop_proposals_not_temporal_identity_acceptance',
                        good_crops_kept=kept_good,good_crops_total=good,bad_crops_blocked=blocked_bad,bad_crops_total=bad)
            profiles[profile]=diag
        summary[probe_name]=profiles
    runs={};roster=RosterConfig.from_dict(read(args.roster))
    for name in ['baseline-replay','guard-only','guard-jersey','recovery-jersey','recovery-final','team-region-only','team-conflict-reset','disabled-regression']:
        meta=read(base/name/'run.json');obs=jsonl(base/name/'tracked_observations.jsonl')
        lookup={(r['frame_index'],r['track_id']):r for r in obs}
        points=[]
        for row in reviewed['identities']:
            binding=row['source_binding'];actual=lookup[(binding['frame_index'],binding['track_id'])];labels=row['labels']
            expected=roster.get_player(labels['actual_team_id'],labels['actual_number']) if labels['actual_team_id'] in {'team_a','team_b'} and labels['actual_number'] else None
            points.append(dict(sample_id=row['sample_id'],actual_role=actual['role'],team=actual.get('team_id'),
                player=actual.get('player_id'),expected_player=expected.player_id if expected else None,
                player_exact=(actual.get('player_id')==expected.player_id) if expected else None,
                team_exact=(actual.get('team_id')==labels['actual_team_id']) if labels['actual_team_id'] in {'team_a','team_b'} else None))
        runs[name]=dict(observations=len(obs),roles=meta['roles'],identity_nonnull=sum(bool(r.get('player_id')) for r in obs),
            guard_reasons=dict(Counter(r['reason'] for r in read(base/name/'identity_crop_audit.json'))) if (base/name/'identity_crop_audit.json').exists() else {},
            selected_timestamp_observations=points,temporal_accuracy=None,ID_switch_count=None,
            limitation='Selected snapshots are not a trajectory benchmark; unknowns retained in point denominators')
    baseline=jsonl(base/'baseline-replay/tracked_observations.jsonl');disabled=jsonl(base/'disabled-regression/tracked_observations.jsonl')
    fields=['frame_index','track_id','bbox','sample_type','role','team_id','player_id']
    equivalent=len(baseline)==len(disabled) and all(all(a.get(k)==b.get(k) for k in fields) for a,b in zip(baseline,disabled))
    if not equivalent:raise ValueError('Disabled guard changed baseline behavior')
    ball={}
    for name in ['baseline-replay','guard-jersey','recovery-final','team-region-only','team-conflict-reset']:
        path=base/('ball-'+name+'-evaluation')/'evaluation.json'
        if path.exists():ball[name]=read(path)
    result=dict(status='diagnostic_evaluation_completed',crop_probes=summary,continuous_runs=runs,
                disabled_regression_equivalent=True,ball_control_evaluations=ball,
                input_sha256=dict(manifest=file_hash(args.manifest),reviewed=file_hash(args.reviewed)),
                promoted=False,training_started=False,task07_status='IN_PROGRESS')
    write_json(out/'evaluation.json',result)
    rows=[];final_rows=jsonl(base/'final-crop-probe/predictions.jsonl');pred={(r['profile'],r['sample_id']):r for r in final_rows}
    for row in reviewed['identities']:
        sid=row['sample_id'];g=pred[('guarded',sid)]
        images=''.join('<figure><figcaption>'+title+'</figcaption><img src="'+html.escape(str(Path('..')/'final-crop-probe/crops'/f'{sid}-{profile}.png').replace('\\','/'))+'"></figure>' for title,profile in [('Crop gốc','legacy'),('Crop sau guard','guarded')] if (base/'final-crop-probe/crops'/f'{sid}-{profile}.png').exists())
        rows.append('<article><h2>'+html.escape(sid)+'</h2><div>'+images+'</div><pre>'+html.escape(json.dumps(dict(labels=row['labels'],allowed=g['allowed'],guard=g['guard'],ocr=g['ocr_readings']),ensure_ascii=False,indent=2))+'</pre></article>')
    (out/'comparison.html').write_text('<!doctype html><meta charset="utf-8"><title>Crop ownership comparison</title><style>body{font:15px Segoe UI;max-width:1100px;margin:24px auto}article{border-top:1px solid #ccc;margin:20px 0}article div{display:flex;gap:20px}figure{margin:0}img{height:240px;max-width:450px;object-fit:contain}pre{white-space:pre-wrap}</style><h1>Đối chiếu crop trước/sau</h1><p>Development cùng trận; nhãn chỉ dùng sau recognition. Không phải nghiệm thu identity theo thời gian.</p>'+''.join(rows),encoding='utf-8')
    print(json.dumps({name:{profile:{k:v for k,v in data.items() if k in ['readable_OCR','team_on_correct_player_crops','good_crops_kept','bad_crops_blocked']} for profile,data in profiles.items()} for name,profiles in summary.items()}))
    return 0


if __name__=='__main__':sys.exit(main())
