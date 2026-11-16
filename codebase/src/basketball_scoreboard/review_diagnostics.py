"""Post-review proposal diagnostics; no recognition code consumes these labels."""
from collections import Counter
from .ball import iou


def ratio(n, d):
    return n / d if d else None


def ball_proposal_diagnostics(reviewed, iou_threshold=.3):
    rows, excluded, raw, top1 = [], [], [0, 0, 0], [0, 0, 0]
    for row in reviewed['frames']:
        if row['review_status'] != 'approved':
            excluded.append(dict(sample_id=row['sample_id'], reason=row['review_status']))
            continue
        gt = [b for b in row['boxes'] if b['class_name'] == 'ball']
        if len(gt) > 1:
            excluded.append(dict(sample_id=row['sample_id'], reason='multiple_physical_balls_active_ball_unresolved'))
            continue
        proposals = row['prediction']['raw_candidates']
        ordered = sorted(proposals, key=lambda p: (-p['confidence'], p['xyxy']))
        frame = dict(sample_id=row['sample_id'], time_s=row['source_binding']['parent_source_time_s'],
                     visible_balls=len(gt), proposals=len(proposals))
        for name, predicted, totals in [('raw', proposals, raw), ('confidence_top1', ordered[:1], top1)]:
            tp = int(bool(gt) and any(iou(gt[0]['xyxy'], p['xyxy']) >= iou_threshold for p in predicted))
            counts = [tp, len(predicted)-tp, len(gt)-tp]
            for index, count in enumerate(counts): totals[index] += count
            frame[name] = dict(tp=counts[0], fp=counts[1], fn=counts[2])
        rows.append(frame)
    def summary(values):
        tp, fp, fn = values
        return dict(tp=tp, fp=fp, fn=fn, precision=ratio(tp,tp+fp), recall=ratio(tp,tp+fn))
    return dict(scope='targeted_reviewed_new_frames_proposal_diagnostics_not_tracking_acceptance',
                eligible_frames=len(rows), excluded=excluded,
                visible_ball_samples=sum(r['visible_balls'] for r in rows),
                no_visible_ball_samples=sum(r['visible_balls']==0 for r in rows),
                iou_threshold=iou_threshold, raw=summary(raw), confidence_top1=summary(top1),
                historical_selector_evaluation='not_available_for_these_selected_windows', rows=rows)


def identity_proposal_diagnostics(reviewed):
    rows = []
    for row in reviewed['identities']:
        if row['review_status'] != 'reviewed': continue
        labels, prediction = row['labels'], row['predictions']
        reads = [r for r in prediction.get('ocr_readings', []) if r.get('is_valid') is True]
        reads.sort(key=lambda r: (-r['confidence'], str(r['detected_number']), str(r.get('evidence_id', ''))))
        top = str(reads[0]['detected_number']) if reads else None
        good_crop = labels['crop_assessment'] == 'correct' and labels['role_review'] == 'player'
        readable = good_crop and labels['jersey_visibility'] == 'readable' and labels['actual_number'] is not None
        team_eligible = good_crop and labels['actual_team_id'] in {'team_a','team_b'}
        rows.append(dict(sample_id=row['sample_id'], track_id=row['source_binding']['track_id'],
                         crop_assessment=labels['crop_assessment'], role_review=labels['role_review'],
                         visibility=labels['jersey_visibility'], expected_number=labels['actual_number'],
                         expected_team=labels['actual_team_id'], top_ocr_number=top,
                         team_proposal=prediction.get('team_id'),
                         readable_OCR_eligible=readable, team_eligible=team_eligible,
                         OCR_exact=(top == labels['actual_number']) if readable else None,
                         OCR_any_candidate_exact=any(str(r['detected_number']) == labels['actual_number'] for r in reads) if readable else None,
                         team_exact=(prediction.get('team_id') == labels['actual_team_id']) if team_eligible else None,
                         reviewer_note=row.get('reviewer_note')))
    eligible = [r for r in rows if r['readable_OCR_eligible']]
    teams = [r for r in rows if r['team_eligible']]
    return dict(scope='targeted_historical_OCR_and_team_proposal_agreement_not_final_identity_accuracy',
                reviewed_crops=len(rows), crop_assessment_counts=dict(Counter(r['crop_assessment'] for r in rows)),
                visibility_counts=dict(Counter(r['visibility'] for r in rows)),
                readable_OCR=dict(eligible=len(eligible), with_reading=sum(r['top_ocr_number'] is not None for r in eligible),
                                  correct=sum(r['OCR_exact'] is True for r in eligible),
                                  strict_accuracy=ratio(sum(r['OCR_exact'] is True for r in eligible),len(eligible)),
                                  coverage=ratio(sum(r['top_ocr_number'] is not None for r in eligible),len(eligible))),
                team_on_correct_player_crops=dict(eligible=len(teams),correct=sum(r['team_exact'] is True for r in teams),
                    strict_accuracy=ratio(sum(r['team_exact'] is True for r in teams),len(teams))),
                temporal_identity_accuracy=None, ID_switch_count=None,
                limitation='Selected error cases, five/small readable samples; no trajectory intervals or independent match test',
                rows=rows)
