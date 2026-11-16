#!/usr/bin/env python3
"""Render review from cached suggestions, with source/policy guards; no inference."""
import argparse
import json
from pathlib import Path
import sys

from suggest_task07a_pilot_labels import PAGE

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from basketball_scoreboard.spatial_io import file_hash,write_json


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pilot-dir',required=True);p.add_argument('--model-dir',required=True);args=p.parse_args()
    pilot,model=Path(args.pilot_dir).resolve(),Path(args.model_dir).resolve()
    packet=json.loads((pilot/'annotations-draft.json').read_text(encoding='utf-8'))
    run=json.loads((model/'run.json').read_text(encoding='utf-8'))
    if run.get('status')!='completed' or run['pilot_packet_sha256']!=file_hash(pilot/'annotations-draft.json'):
        raise ValueError('Only complete source-bound model suggestions may be reviewed')
    rows=[json.loads(x) for x in (model/'suggestions.jsonl').read_text(encoding='utf-8').splitlines()]
    if len(rows)!=len(packet['samples']):raise ValueError('Incomplete suggestion stream')
    for row,sample in zip(rows,packet['samples']):
        if row['sample_id']!=sample['sample_id'] or row['image_sha256']!=sample['image_sha256']:
            raise ValueError('Suggestion/source image binding differs')
    packet['label_policy_version']='task07a-three-class-policy-v1'
    packet['label_policy_status']='draft'
    page=PAGE.replace('<p>Reviewer ',
        '<p><label><input id="policyReviewed" type="checkbox">Đã đọc và áp dụng nhất quán tiêu chuẩn ball/human/rim trong hướng dẫn review</label></p><p>Reviewer ')
    page=page.replace("if(approved){const r=document.getElementById('reviewer').value.trim();",
        "if(approved){if(!document.getElementById('policyReviewed').checked)throw Error('Cần xác nhận tiêu chuẩn nhãn');x.label_policy_status='approved_by_reviewer';const r=document.getElementById('reviewer').value.trim();")
    page=page.replace("s.image_sha256!==data.samples[i].image_sha256",
        "['sample_id','image','image_sha256','source_group','window_id','parent_source_time_s','raw_pts','time_base','original_wh'].some(k=>JSON.stringify(s[k])!==JSON.stringify(data.samples[i][k]))")
    safe=lambda x:json.dumps(x,ensure_ascii=False).replace('</','<\\/')
    page=page.replace('PACKET_JSON',safe(packet)).replace('SUGGESTIONS_JSON',safe({r['sample_id']:r['boxes'] for r in rows}))
    (model/'review.html').write_text(page,encoding='utf-8')
    write_json(model/'review-ui.json',dict(status='rendered_with_source_policy_guards',renderer_sha256=file_hash(__file__),
        suggestion_run_sha256=file_hash(model/'run.json'),html_sha256=file_hash(model/'review.html'),
        inference_performed=False,training_labels_exported=False,browser_interactions_tested=False))
    print('Rendered guarded review UI',len(rows));return 0


if __name__=='__main__':
    try:sys.exit(main())
    except Exception as error:print('Review rendering failed ('+type(error).__name__+')',file=sys.stderr);sys.exit(1)
