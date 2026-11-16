#!/usr/bin/env python3
"""Post-inference candidate diagnostics; never imported by the inference runner."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from basketball_scoreboard.ball import iou
from basketball_scoreboard.possession_evaluation import validate_packet
from basketball_scoreboard.spatial_io import file_hash,new_output,write_json


def rows(path):return [json.loads(x) for x in Path(path).read_text(encoding='utf-8').splitlines() if x.strip()]


def equivalent(a,b):
    a=sorted(a,key=lambda d:(-d['confidence'],d['xyxy']))
    b=sorted(b,key=lambda d:(-d['confidence'],d['xyxy']))
    return len(a)==len(b) and all(np.allclose(x['xyxy'],y['xyxy'],atol=1e-6,rtol=0) and
        abs(x['confidence']-y['confidence'])<=1e-4 for x,y in zip(a,b))


def evaluate_candidates(experiment_dir,ground_truth,baseline_detections,output_dir):
    experiment=Path(experiment_dir)
    run=json.loads((experiment/'run.json').read_text(encoding='utf-8'))
    if run.get('status')!='completed':raise ValueError('Only completed inference may be evaluated')
    packet=json.loads(Path(ground_truth).read_text(encoding='utf-8'))
    validate_packet(packet,run['video_sha256'])
    gt=[s for s in packet['ball_samples'] if s.get('visible',True) and not s.get('uncertain')]
    if not gt:raise ValueError('No reviewed visible ball labels')
    baseline={r['frame_index']:r for r in rows(baseline_detections)}
    comparisons={};profiles={};details={}
    for profile in run['settings']['profiles']:
        data=rows(experiment/(profile['name']+'.jsonl'));by_frame={r['frame_index']:r for r in data}
        if len(data)!=113 or len(by_frame)!=113 or sorted(by_frame)!=list(range(0,900,8)):
            raise ValueError('Incomplete fixed-schedule frame stream')
        for r in data:
            if r['source_time_s']!=baseline[r['frame_index']]['source_time_s']:raise ValueError('Source PTS differs')
            expected=640 if profile['image_size'] is None else profile['image_size'][0]
            if len(r['network_traces'])!=5:raise ValueError('Missing full/tile tensor traces')
            for trace in r['network_traces']:
                shapes=[shape for call in trace['network_feeds'] for shape in call.values()]
                if not shapes or any(shape!=[1,3,expected,expected] for shape in shapes):
                    raise ValueError('Real ONNX input shape differs from profile')
        counts=dict(eligible_samples=len(gt),candidate_hit_frames=0,matched_candidates=0,unmatched_candidates=0)
        per_sample=[]
        for s in gt:
            if s['frame_index'] not in by_frame:raise ValueError('GT frame was not inferred')
            r=by_frame[s['frame_index']]
            matches=[iou(c['xyxy'],s['xyxy'])>=packet['ball_iou_threshold'] for c in r['ball_candidates']]
            counts['candidate_hit_frames']+=int(any(matches))
            counts['matched_candidates']+=sum(matches)
            counts['unmatched_candidates']+=len(matches)-sum(matches)
            per_sample.append(dict(frame_index=s['frame_index'],candidate_hit=any(matches),candidate_count=len(matches)))
        counts.update(candidate_recall=counts['candidate_hit_frames']/len(gt),
            sampled_frames=len(data),model_calls=len(data)*5,detection_time_s=run['detection_time_by_profile_s'][profile['name']],
            observed_tracking_recall=None,scope='Candidate diagnostics at reviewed visible frames; not full-video precision or tracking acceptance')
        profiles[profile['name']]=counts;details[profile['name']]=per_sample
        if profile['name']=='baseline-default':
            differences=[]
            for r in data:
                original=[c for c in baseline[r['frame_index']]['detections'] if c['class_name']=='ball']
                if not equivalent(r['ball_candidates'],original):differences.append(r['frame_index'])
            comparisons=dict(compared_frames=len(data),equivalent_frames=len(data)-len(differences),different_frame_indices=differences,
                             bbox_tolerance_px=1e-6,confidence_tolerance=1e-4)
    output=new_output(output_dir,[experiment,ground_truth,baseline_detections])
    summary=dict(status='completed',scope='controlled_development_candidate_ablation_not_accuracy_acceptance',
        source_video_sha256=run['video_sha256'],gt_sha256=file_hash(ground_truth),inference_run_sha256=file_hash(experiment/'run.json'),
        baseline_detections_sha256=file_hash(baseline_detections),baseline_reproduction=comparisons,profiles=profiles,
        acceptance_pass=None,task07_status='IN_PROGRESS',gt_loaded_by_inference=False)
    write_json(output/'evaluation.json',summary);write_json(output/'per-sample.json',details)
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('experiment-dir','ground-truth','baseline-detections','output-dir'):p.add_argument('--'+name,required=True)
    try:print(json.dumps(evaluate_candidates(**vars(p.parse_args()))));sys.exit(0)
    except Exception as error:print('Candidate evaluation failed ('+type(error).__name__+')',file=sys.stderr);sys.exit(1)
