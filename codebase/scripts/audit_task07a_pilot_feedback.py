#!/usr/bin/env python3
"""Source-bound partial label audit and cached single-active-ball diagnostics."""
import argparse
from collections import Counter
import html
import json
from pathlib import Path
import shutil
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from basketball_scoreboard.ball import BallConfig, BallTracker, center, iou
from basketball_scoreboard.dataset_review_validation import audit_pilot_draft
from basketball_scoreboard.spatial_io import file_hash, new_output, write_json
from basketball_scoreboard.tracking_policy import in_image_roi, validate_image_polygon


def build_previews(source, suggestions, settings):
    """No reviewed labels, control intervals, or player identities enter here."""
    if settings['source_sha256'] != source['source_sha256'] or settings['schema_version'] != 'task07a-context-preview-1':
        raise ValueError('Context policy source mismatch')
    foot = validate_image_polygon(settings['human_footpoint_roi_normalized'])
    aerial = validate_image_polygon(settings['ball_image_roi_normalized'])
    results = {}
    for sample in source['samples']:
        prediction = suggestions[sample['sample_id']]
        if prediction['image_sha256'] != sample['image_sha256']:
            raise ValueError('Suggestions/image hash mismatch')
        if sample['window_id'] != settings['window_id']:
            continue
        records = prediction['boxes']
        humans = [d['xyxy'] for d in records if d['class_name'] == 'human' and
                  in_image_roi({'image_roi_normalized': foot},
                               ((d['xyxy'][0]+d['xyxy'][2])/2, d['xyxy'][3]), sample['original_wh'])]
        # Sparse 1 Hz samples cannot carry a 30 FPS ball trajectory. Deliberately
        # start independent trackers rather than stretching max_gap to fake one.
        tracker = BallTracker(tuple(sample['original_wh']), 'preview', BallConfig(**settings['ball']))
        row = tracker.update(sample['cfr_frame_index'], sample['parent_source_time_s'], records,
                             human_boxes=humans, ball_roi=aerial)
        raw_balls = [d for d in records if d['class_name'] == 'ball']
        top1 = sorted(raw_balls, key=lambda d: (-d['confidence'], d['xyxy']))[:1]
        selected = [] if row['sample_type'] != 'observed' else [dict(class_name='ball', xyxy=row['xyxy'], confidence=row['confidence'])]
        results[sample['sample_id']] = dict(raw=raw_balls, top1=top1, context=selected,
            context_reason=row['reason'], human_proxies=len(humans), spatially_rejected=row['spatially_rejected_candidates'])
    return results


def match_boxes(predicted, expected, threshold=.3):
    """Maximum-cardinality bipartite matching; labels never rank candidates."""
    adjacency = {i: sorted([j for j, g in enumerate(expected) if iou(p['xyxy'], g['xyxy']) >= threshold],
                           key=lambda j: -iou(p['xyxy'], expected[j]['xyxy'])) for i, p in enumerate(predicted)}
    owner = {}
    def assign(i, visited):
        for j in adjacency[i]:
            if j in visited: continue
            visited.add(j)
            if j not in owner or assign(owner[j], visited):
                owner[j] = i
                return True
        return False
    for index in range(len(predicted)): assign(index, set())
    return set(owner.values()), set(owner)


def metrics(tp, fp, fn):
    return dict(tp=tp, fp=fp, fn=fn, precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/(tp+fn) if tp+fn else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pilot-dir', required=True); parser.add_argument('--reviewed', required=True)
    parser.add_argument('--settings', required=True); parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    pilot = Path(args.pilot_dir).resolve()
    source_path, suggestions_path = pilot/'annotations-draft.json', pilot/'model-review/suggestions.jsonl'
    source = json.loads(source_path.read_text(encoding='utf-8'))
    settings = json.loads(Path(args.settings).read_text(encoding='utf-8'))
    suggestions = [json.loads(line) for line in suggestions_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    by_id = {r['sample_id']: r for r in suggestions}
    if len(by_id) != len(source['samples']) or len(suggestions) != len(by_id): raise ValueError('Incomplete/duplicate prediction records')
    out = new_output(args.output_dir, [pilot, args.reviewed, args.settings])
    predictions = build_previews(source, by_id, settings)
    write_json(out/'predictions-before-label-evaluation.json', predictions)
    # The user packet is opened only after predictions are fixed and persisted.
    reviewed = json.loads(Path(args.reviewed).read_text(encoding='utf-8-sig'))
    audit = audit_pilot_draft(reviewed, source)
    write_json(out/'partial-review-audit.json', audit)
    checked = [s for s in reviewed['samples'] if s['sample_id'] in audit['approved_sample_ids']]
    totals = {key: [0, 0, 0] for key in ('raw', 'top1', 'context')}
    strict_totals = {key: [0, 0, 0] for key in totals}
    details, queue, cards = [], [], []
    overlay_dir = out/'overlays'; overlay_dir.mkdir()
    crops = out/'unmatched-review-crops'; crops.mkdir()
    for sample in checked:
        sid = sample['sample_id']
        path = (pilot/sample['image']).resolve()
        if not path.is_relative_to(pilot) or file_hash(path) != sample['image_sha256']:
            raise ValueError('Reviewed source image changed')
        if sid not in predictions: raise ValueError('Reviewed sample outside scoped preview window; use a separate camera policy')
        expected = [b for b in sample['boxes'] if b['class_name'] == 'ball']
        strict = len(expected) <= 1
        im = cv2.imread(str(path))
        source_image = im.copy()
        row = dict(sample_id=sid, time_s=sample['parent_source_time_s'], gt_balls=len(expected),
                   active_ball_evaluation_eligible=strict, profiles={})
        for key in totals:
            ps = predictions[sid][key]
            matched_p, matched_g = match_boxes(ps, expected)
            counts = [len(matched_p), len(ps)-len(matched_p), len(expected)-len(matched_g)]
            totals[key] = [x+y for x,y in zip(totals[key], counts)]
            if strict: strict_totals[key] = [x+y for x,y in zip(strict_totals[key], counts)]
            row['profiles'][key] = dict(tp=counts[0], fp=counts[1], fn=counts[2])
            if key == 'raw':
                for j, box in enumerate(ps):
                    a,b,c,d = map(round,box['xyxy']); cv2.rectangle(im, (a,b), (c,d), (0,0,255), 2)
                    if j not in matched_p:
                        crop_id=f'{sid}-{j:02d}.jpg'
                        x1,y1,x2,y2=box['xyxy']; pad=48
                        crop=source_image[max(0,int(y1)-pad):min(im.shape[0],int(y2)+pad), max(0,int(x1)-pad):min(im.shape[1],int(x2)+pad)]
                        cv2.imwrite(str(crops/crop_id), crop)
                        queue.append(dict(sample_id=sid,image=sample['image'],image_sha256=sample['image_sha256'],
                            candidate=box,crop=f'unmatched-review-crops/{crop_id}',
                            status='unmatched_to_partial_labels_requires_source_review_not_training_negative'))
        for box in expected:
            a,b,c,d=map(round,box['xyxy']);cv2.rectangle(im,(a-3,b-3),(c+3,d+3),(0,255,0),2)
        for box in predictions[sid]['context']:
            a,b,c,d=map(round,box['xyxy']);cv2.rectangle(im,(a-6,b-6),(c+6,d+6),(255,255,0),2)
        for name,color in [('human_footpoint_roi_normalized',(255,160,50)),('ball_image_roi_normalized',(255,80,180))]:
            poly=np.array([[round(x*im.shape[1]),round(y*im.shape[0])] for x,y in settings[name]],np.int32)
            cv2.polylines(im,[poly],True,color,2)
        im=cv2.resize(im,(1280,720));cv2.imwrite(str(overlay_dir/f'{sid}.jpg'),im)
        description=f'{sid} | t={sample["parent_source_time_s"]}s | labels={len(expected)} | raw={len(predictions[sid]["raw"])} | active={len(predictions[sid]["context"])} | {predictions[sid]["context_reason"]}'
        cards.append(f'<article><h2>{html.escape(description)}</h2><img src="overlays/{sid}.jpg" loading="lazy"></article>')
        details.append(row)
    summary = dict(scope='Development diagnostics on human-marked images within a draft packet; not independent acceptance',
        approved_images=len(checked),unreviewed_images=len(audit['unreviewed_sample_ids']),
        scene_counts=dict(Counter(s['scene_status'] for s in checked)),
        visibility_counts=dict(Counter(s['ball_visibility'] for s in checked)),
        gt_ball_boxes=sum(sum(b['class_name']=='ball' for b in s['boxes']) for s in checked),
        profiles_all_reviewed_physical_ball_labels={k:metrics(*v) for k,v in totals.items()},
        profiles_single_ball_label_subset={k:metrics(*v) for k,v in strict_totals.items()},
        single_ball_subset_images=sum(d['active_ball_evaluation_eligible'] for d in details),
        excluded_from_active_subset=audit['multiple_ball_sample_ids'],
        raw_candidates=sum(len(predictions[s['sample_id']]['raw']) for s in checked),
        multiple_raw_candidate_images=sum(len(predictions[s['sample_id']]['raw'])>1 for s in checked),
        prediction_sha256=file_hash(out/'predictions-before-label-evaluation.json'),
        reviewed_input_sha256=file_hash(args.reviewed),source_packet_sha256=file_hash(source_path),
        suggestions_sha256=file_hash(suggestions_path),policy_sha256=file_hash(args.settings),
        temporal_accuracy_measured=False,sampling_interval_s=1.,training_started=False,
        promotion_status='experimental_not_promoted',label_packet_approved=False)
    write_json(out/'evaluation.json',summary);write_json(out/'per-frame-evaluation.json',details)
    write_json(out/'unmatched-review-queue.json',queue)
    (out/'review.html').write_text('<!doctype html><meta charset="utf-8"><title>Task07A review feedback</title>'
        '<style>body{font:15px Segoe UI;max-width:1400px;margin:24px auto}img{width:100%}article{margin:24px 0}</style>'
        '<h1>Partial review — diagnostic preview</h1><p>Green: reviewed ball; red: raw candidates; cyan: experimental single active selection. '
        'Blue line: human footpoint proxy; pink: aerial search region. At most one selected ball; missing is allowed. '
        'Spatial policy is a draft for this camera window. 1 Hz frames do not evaluate temporal tracking. Input labels unchanged; no training.</p>'
        '<p>Đầu ra bóng thi đấu chỉ có tối đa một bbox hoặc missing. Bbox đỏ là các gợi ý ban đầu; không phải nhiều bóng đã được xác nhận. '
        'Bộ lọc thử nghiệm vẫn có thể chọn sai hoặc bỏ sót; đối soát màu xanh lá với màu cyan. Không sử dụng polygon mặt sân để cắt bóng đang bay.</p>'
        +''.join(cards),encoding='utf-8')
    snapshot=out/'source-snapshot';snapshot.mkdir()
    for path in [Path(__file__), ROOT/'src/basketball_scoreboard/ball.py',ROOT/'src/basketball_scoreboard/ball_actor_context.py',
                 ROOT/'src/basketball_scoreboard/dataset_review_validation.py',Path(args.settings)]:
        shutil.copyfile(path,snapshot/path.name)
    print(json.dumps(summary,ensure_ascii=True))
    return 0


if __name__=='__main__':sys.exit(main())
