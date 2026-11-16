#!/usr/bin/env python3
"""Post-inference control duration decomposition and pass endpoint traces."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from basketball_scoreboard.spatial_io import file_hash,new_output,write_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['run-dir','ground-truth','output-dir']:p.add_argument('--'+name,required=True)
    args=p.parse_args();folder=Path(args.run_dir);meta=json.loads((folder/'run.json').read_text())
    gt=json.loads(Path(args.ground_truth).read_text())
    if meta['status']!='completed' or meta['source_fingerprint_sha256']!=gt['source_video_sha256']:raise ValueError('Source mismatch')
    controls=[json.loads(x) for x in (folder/'ball_control.jsonl').read_text().splitlines()]
    balls={r['frame_index']:r for r in map(json.loads,(folder/'ball_tracks.jsonl').read_text().splitlines())}
    total=Counter();intervals=[]
    for label in gt['control_intervals']:
        if label.get('uncertain'):continue
        parts=Counter();expected=label['end_time_s']-label['start_time_s']
        for left,right in zip(controls,controls[1:]):
            if right['source_time_s']-left['source_time_s']>.25:continue
            dt=max(0,min(right['source_time_s'],label['end_time_s'])-max(left['source_time_s'],label['start_time_s']))
            if not dt:continue
            actor=left.get('controller') or {};ball=balls[left['frame_index']]
            if ball['sample_type']!='observed':reason='ball_not_observed'
            elif left['certainty']!='confirmed':reason='control_unconfirmed_with_observed_ball'
            elif actor.get('team_id')!=label['team_id']:reason='confirmed_controller_team_wrong_or_unknown'
            elif actor.get('player_id')!=label['player_id']:reason='confirmed_controller_player_wrong_or_unknown'
            else:reason='strict_correct'
            parts[reason]+=dt
        parts['uncovered_time']+=max(0,expected-sum(parts.values()))
        total.update(parts);intervals.append(dict(ground_truth=label,seconds=dict(parts)))
    endpoints=[]
    for label in gt['passes']:
        trace=dict(pass_id=label['pass_id'],ground_truth=label,observations={})
        for key in ['release_time_s','receive_time_s']:
            row=min(controls,key=lambda r:abs(r['source_time_s']-label[key]))
            trace['observations'][key]=dict(control=row,ball=balls[row['frame_index']])
        endpoints.append(trace)
    out=new_output(args.output_dir,[args.run_dir,args.ground_truth]);write_json(out/'trace.json',dict(
        status='post_inference_diagnostic',source_run_sha256=file_hash(folder/'run.json'),ground_truth_sha256=file_hash(args.ground_truth),
        control_seconds=dict(total),intervals=intervals,pass_endpoint_traces=endpoints,
        limitation='Observed ball does not mean correctly localized on every frame; these categories describe evidence availability, not independently proven causal attribution'))
    print(json.dumps(dict(total)));return 0


if __name__=='__main__':sys.exit(main())
