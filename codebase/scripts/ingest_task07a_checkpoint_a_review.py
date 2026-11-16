#!/usr/bin/env python3
"""Validate a human-returned subset, merge completed labels, and diagnose caches."""
import argparse
from collections import Counter
import html
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from basketball_scoreboard.dataset_review_validation import validate_task07a_checkpoint_subset, merge_task07a_checkpoint_subset, audit_pilot_draft
from basketball_scoreboard.review_diagnostics import ball_proposal_diagnostics, identity_proposal_diagnostics
from basketball_scoreboard.spatial_io import file_hash, new_output, write_json


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reviewed',required=True); p.add_argument('--manifest',required=True)
    p.add_argument('--decisions'); p.add_argument('--output-dir',required=True)
    args = p.parse_args()
    reviewed, manifest = read(args.reviewed), read(args.manifest)
    inputs = {}
    for key, relative in manifest['input_paths'].items():
        path = (ROOT/relative).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file() or file_hash(path) != manifest['input_sha256'][key]:
            raise ValueError('Bound source input differs: '+key)
        inputs[key] = path
    source, progress, identity = read(inputs['pilot']), read(inputs['progress']), read(inputs['identity_packet'])
    validation = validate_task07a_checkpoint_subset(reviewed, manifest, source, progress, identity, file_hash(args.manifest))
    if args.decisions and read(args.decisions)['corrected_sha256'] != file_hash(args.reviewed):
        raise ValueError('User decision provenance differs from reviewed input')
    merged = merge_task07a_checkpoint_subset(reviewed, manifest, source, progress, identity, file_hash(args.manifest))
    prior = {r['sample_id']:r for r in progress['samples'] if r['review_status']=='approved'}
    current = {r['sample_id']:r for r in merged['samples']}
    if any(current[sid] != row for sid,row in prior.items()): raise ValueError('Prior labels changed')
    folder = new_output(args.output_dir,[args.reviewed,args.manifest,args.decisions,*inputs.values()])
    write_json(folder/'merged-progress-v3.json',merged)
    write_json(folder/'subset-validation.json',validation)
    write_json(folder/'merged-progress-audit.json',audit_pilot_draft(merged,source))
    shutil.copyfile(args.reviewed,folder/'reviewed-subset.json')
    if args.decisions: shutil.copyfile(args.decisions,folder/'user-label-decisions.json')
    write_json(folder/'identity-reviewed-subset.json',dict(schema_version='task07a-identity-reviewed-subset-1',
        source_review_sha256=file_hash(args.reviewed),manifest_sha256=file_hash(args.manifest),
        source_video_sha256=reviewed['identity_video_sha256'],reviewer=reviewed['reviewer'],
        training_authorized=False,samples=reviewed['identities']))
    ball, people = ball_proposal_diagnostics(reviewed), identity_proposal_diagnostics(reviewed)
    write_json(folder/'ball-proposal-evaluation.json',ball);write_json(folder/'identity-proposal-evaluation.json',people)
    media_root = Path(args.manifest).resolve().parent
    evidence = folder/'identity-evidence';evidence.mkdir();cards=[]
    rows_by_id = {r['sample_id']:r for r in people['rows']}
    for row in reviewed['identities']:
        for key, hash_key in [('crop','crop_source_sha256'),('context','context_source_sha256')]:
            path = (media_root/row[key]).resolve()
            if not path.is_relative_to(media_root) or file_hash(path)!=row['source_binding'][hash_key]: raise ValueError('Identity media changed')
            shutil.copyfile(path,evidence/(row['sample_id']+'-'+key+'.jpg'))
        sid=row['sample_id'];d=rows_by_id[sid]
        text=json.dumps(d,ensure_ascii=False,indent=2)
        cards.append('<article><h2>'+html.escape(sid)+'</h2><div class="pair"><img src="identity-evidence/'+sid+'-context.jpg"><img src="identity-evidence/'+sid+'-crop.jpg"></div><pre>'+html.escape(text)+'</pre></article>')
    (folder/'identity-diagnosis.html').write_text('<!doctype html><meta charset="utf-8"><title>Identity reviewed diagnosis</title><style>body{font:15px Segoe UI;max-width:1100px;margin:24px auto}.pair{display:flex;gap:20px}.pair img{max-width:45%;height:260px;object-fit:contain}article{border-top:1px solid #ccc;margin-top:24px}pre{white-space:pre-wrap}</style><h1>Identity — nhãn đã review và dự đoán lịch sử</h1><p>Chỉ đối soát proposal trên batch được chọn; không phải temporal identity accuracy hoặc dữ liệu đã dùng để train.</p>'+''.join(cards),encoding='utf-8')
    counts=dict(Counter(r['review_status'] for r in merged['samples']))
    readiness=dict(training_ready=False,training_authorized=False,weights_changed=False,inference_performed=False,
        source_group=reviewed['source_group'],independent_match_test=False,
        pending_frame_sample_ids=[r['sample_id'] for r in reviewed['frames'] if r['review_status'] in {'needs_review','unreviewed'}],
        remaining_requirements=['Full original dataset label/split QA','Supplemental label policy consistency and source-group split','Concrete native checkpoint/recipe/resources and explicit training approval'],
        note='One uncertain frame remains in corrected subset; not merged as an empty negative. Identity labels stay available separately.')
    write_json(folder/'training-readiness.json',readiness)
    summary=dict(status='accepted_review_subset_with_uncertainty_quarantine',source_review_sha256=file_hash(args.reviewed),
        manifest_sha256=file_hash(args.manifest),prior_approved_labels_preserved=len(prior),merged_states=counts,
        incoming_frames=dict(Counter(r['review_status'] for r in reviewed['frames'])),
        incoming_identity=dict(Counter(r['review_status'] for r in reviewed['identities'])),
        ball_summary={k:v for k,v in ball.items() if k!='rows'},identity_summary={k:v for k,v in people.items() if k!='rows'},
        pending_frames=readiness['pending_frame_sample_ids'],task07_status='IN_PROGRESS',training_started=False)
    write_json(folder/'run.json',summary)
    snapshot=folder/'source-snapshot';snapshot.mkdir()
    for path in [Path(__file__),ROOT/'src/basketball_scoreboard/dataset_review_validation.py',ROOT/'src/basketball_scoreboard/review_diagnostics.py']:
        shutil.copyfile(path,snapshot/path.name)
    print(json.dumps(summary,ensure_ascii=True))
    return 0


if __name__=='__main__':sys.exit(main())
