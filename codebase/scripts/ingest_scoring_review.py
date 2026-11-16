#!/usr/bin/env python3
"""Validate returned shot reviews, preserve ambiguous target links, never infer stats.

This writes separate annotation/audit artifacts. It does not modify the review
packet, locked dataset, recognition configs, or canonical control ground truth.
"""
import argparse
import copy
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path


def sha256(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''):result.update(chunk)
    return result.hexdigest()


def strict_json(path):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Duplicate JSON key')
            result[key]=value
        return result
    def invalid(value):raise ValueError('Nonfinite JSON number')
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),object_pairs_hook=pairs,parse_constant=invalid)


def write(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')


def apply_resolutions(review,manifest,resolutions,raw_sha,manifest_sha):
    """Transfer only explicitly confirmed annotations, retaining source timestamps.

    Read all transfers from the immutable original, so a two-way swap cannot
    accidentally copy the first result back over the second event.
    """
    if (resolutions.get('schema_version')!='scoring-review-resolution-1' or
            resolutions.get('review_sha256')!=raw_sha or resolutions.get('manifest_sha256')!=manifest_sha or
            not resolutions.get('confirmation_record')):
        raise ValueError('Resolution document is not bound to this returned review')
    result=copy.deepcopy(review);entries={e['id']:e for e in manifest['entries']};seen=set()
    for action in resolutions.get('actions',[]):
        target,source=action.get('target_event_id'),action.get('source_event_id')
        if action.get('status')!='confirmed_by_user' or target not in entries or target in seen:
            raise ValueError('Invalid or unconfirmed annotation resolution')
        seen.add(target)
        destination=result['reviews'][target]
        if action.get('kind')=='transfer_annotations_preserve_source_clock':
            if source not in entries or target==source:raise ValueError('Invalid annotation transfer source')
            original=review['reviews'][source]
            for name in ('shot_kind','shooter_id','ball_visibility'):destination[name]=original[name]
            for name in ('release_clip_s','basket_clip_s'):
                t=original[name]
                destination[name]=None if t is None else round(t+entries[source]['source_time_offset_s']-entries[target]['source_time_offset_s'],6)
        elif action.get('kind')=='correct_target_annotations':
            updates=action.get('updates')
            clear_times=action.get('clear_unconfirmed_times',False)
            if (not isinstance(updates,dict) or not updates or not set(updates)<={'shooter_id','shot_kind'} or
                    not isinstance(clear_times,bool)):
                raise ValueError('Unsupported target annotation update')
            original=review['reviews'][target]
            players={p['player_id']:p for p in manifest['players']}
            old_player=players.get(original['shooter_id'])
            retargets_opponent=('shooter_id' in updates and updates['shooter_id']!=original['shooter_id'] and
                               old_player and old_player['team_id']!=entries[target]['draft_scoring_team'])
            if retargets_opponent and any(original[k] is not None for k in ('release_clip_s','basket_clip_s')) and not clear_times:
                raise ValueError('Do not reuse opponent-event timestamps for the corrected target')
            destination.update(updates)
            if clear_times:
                destination['release_clip_s']=destination['basket_clip_s']=None
        else:
            raise ValueError('Unsupported annotation resolution kind')
    validate_review(result,manifest,manifest_sha)
    return result


def validate_review(review,manifest,manifest_sha):
    if review.get('schema_version')!='scoreboard-shot-review-1':raise ValueError('Unsupported review schema')
    if review.get('manifest_sha256')!=manifest_sha:raise ValueError('Review belongs to another manifest')
    if review.get('source_sha256')!=manifest['source_sha256']:raise ValueError('Review belongs to another source')
    if review.get('purpose')!='user_review_annotation_only_not_recognition_input':raise ValueError('Unexpected review purpose')
    entries=manifest['entries'];ids=[e['id'] for e in entries]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate manifest IDs')
    labels=review.get('reviews')
    if not isinstance(labels,dict) or set(labels)!=set(ids):raise ValueError('Review IDs must match the complete packet')
    players={p['player_id']:p for p in manifest['players']}
    decisions={'pending','confirmed_clear','confirmed_partial','not_score','replay','uncertain'}
    shot_kinds={'unknown','field_goal','free_throw','other'}
    visibility={'unknown','clear','partial','not_visible'}
    expected={'decision','shot_kind','shooter_id','ball_visibility','release_clip_s','basket_clip_s','notes'}
    normalized=[];conflicts=[];windows=[]
    for e in entries:
        r=labels[e['id']]
        if not isinstance(r,dict) or set(r)!=expected:raise ValueError('Unexpected review fields')
        if r['decision'] not in decisions or r['shot_kind'] not in shot_kinds or r['ball_visibility'] not in visibility:
            raise ValueError('Invalid review label')
        if r['shooter_id'] is not None and r['shooter_id'] not in players:raise ValueError('Shooter not in approved roster')
        if not isinstance(r['notes'],str) or len(r['notes'])>4000:raise ValueError('Invalid note')
        for name in ('release_clip_s','basket_clip_s'):
            t=r[name]
            if t is not None and (isinstance(t,bool) or not isinstance(t,(int,float)) or not math.isfinite(t) or not 0<=t<e['duration_s']):
                raise ValueError('Review time outside clip')
        release,basket=r['release_clip_s'],r['basket_clip_s']
        if release is not None and basket is not None and release>basket:raise ValueError('Release follows basket')
        issues=[];confirmed=r['decision'] in {'confirmed_clear','confirmed_partial'}
        shooter=players.get(r['shooter_id'])
        if confirmed and shooter and shooter['team_id']!=e['draft_scoring_team']:
            issues.append('reviewed_shooter_team_opposes_target_score_change')
        if confirmed and r['shot_kind']=='free_throw' and e['draft_points']!=1:
            issues.append('free_throw_label_conflicts_with_target_increment')
        source_times={}
        for name in ('release','basket'):
            local=r[name+'_clip_s']
            absolute=None if local is None else round(e['source_time_offset_s']+local,6)
            index=None if absolute is None else round(absolute*manifest['source_fps'])
            source_times[name]=dict(clip_s=local,source_s=absolute,source_frame_index=index,
                nearest_frame_time_s=None if index is None else index/manifest['source_fps'])
        known_pair=release is not None and basket is not None
        record=dict(event_id=e['id'],review=dict(r),
            target=dict(before_score_tga_vie=e['before_score_tga_vie'],after_score_tga_vie=e['after_score_tga_vie'],
                        scoring_team_proposed_from_scoreboard=e['draft_scoring_team'],points_proposed_from_scoreboard=e['draft_points']),
            original_clip=e['video'],source_time_offset_s=e['source_time_offset_s'],times=source_times,
            target_link_status='needs_user_resolution' if issues else 'consistent_with_packet',
            issues=issues,user_confirmed_event=confirmed,
            usable_event_metadata=confirmed and not issues,
            precise_times_present=known_pair,
            ball_visibility_reviewed=r['ball_visibility']!='unknown',
            ball_bbox_GT_present=False,trajectory_identity_GT_present=False,
            official_shot_value_geometry_verified=False)
        normalized.append(record)
        if issues:conflicts.append(record)
        if confirmed and not issues and r['decision']=='confirmed_clear' and r['ball_visibility']=='clear' and known_pair:
            start=max(e['start_s'],source_times['release']['source_s']-2.)
            end=min(e['end_s'],source_times['basket']['source_s']+1.5)
            windows.append(dict(window_id=e['id'],source_start_s=start,source_end_s=end,
                source_start_frame=math.floor(start*manifest['source_fps']),
                source_end_frame_exclusive=math.ceil(end*manifest['source_fps']),
                evaluation_times=source_times,reviewed_shooter_id=r['shooter_id'],
                shot_kind=r['shot_kind'],selection_uses_reviewed_times=True,
                purpose='conditional_detector_diagnostic_only_not_end_to_end_shot_discovery',
                ball_bbox_GT_available=False))
    counts=dict(total=len(normalized),decisions=dict(Counter(r['decision'] for r in labels.values())),
        shot_kinds=dict(Counter(r['shot_kind'] for r in labels.values())),
        ball_visibility=dict(Counter(r['ball_visibility'] for r in labels.values())),
        user_confirmed_events=sum(e['user_confirmed_event'] for e in normalized),
        conflicting_target_links=len(conflicts),consistent_event_metadata=sum(e['usable_event_metadata'] for e in normalized),
        shooter_unspecified=sum(r['shooter_id'] is None for r in labels.values()),
        consistent_known_shooters=sum(e['usable_event_metadata'] and e['review']['shooter_id'] is not None for e in normalized),
        paired_times_total=sum(e['precise_times_present'] for e in normalized),
        paired_times_consistent=sum(e['usable_event_metadata'] and e['precise_times_present'] for e in normalized),
        clear_timed_diagnostic_windows=len(windows),missing_paired_times=sum(not e['precise_times_present'] for e in normalized),
        ball_bbox_GT_samples=0,miss_or_negative_events=0)
    return dict(counts=counts,events=normalized,conflicts=conflicts,diagnostic_windows=windows)


def ingest(args):
    raw=Path(args.review).resolve();packet=Path(args.packet_dir).resolve();out=Path(args.output_dir).resolve()
    if out==packet or out.is_relative_to(packet):raise ValueError('Use an output outside the original packet')
    if raw.stat().st_size>2_000_000:raise ValueError('Review too large')
    manifest_path=packet/'review-manifest.json';manifest=strict_json(manifest_path)
    review=strict_json(raw);manifest_sha=sha256(manifest_path)
    validate_review(review,manifest,manifest_sha)
    resolutions=None
    if args.resolutions:
        resolutions=strict_json(args.resolutions)
        review=apply_resolutions(review,manifest,resolutions,sha256(raw),manifest_sha)
    result=validate_review(review,manifest,manifest_sha)
    source=Path(manifest['source_video'])
    if sha256(source)!=manifest['source_sha256']:raise ValueError('Source media fingerprint mismatch')
    for entry in manifest['entries']:
        clip=(packet/entry['video']).resolve()
        if not clip.is_relative_to(packet) or sha256(clip)!=entry['integrity']['sha256']:
            raise ValueError('Clip integrity failure')
    out.mkdir(parents=True,exist_ok=True)
    if any((out/name).exists() for name in ('summary.json','events-reviewed.json','user-review-original.json')):
        raise FileExistsError('Use a fresh intake directory')
    raw_hash=sha256(raw);(out/'user-review-original.json').write_bytes(raw.read_bytes())
    if resolutions:
        write(out/'user-confirmed-resolutions.json',resolutions)
        write(out/'review-derived-after-resolutions.json',review)
    provenance=dict(schema_version='scoring-review-intake-1',ingested_at=datetime.now(timezone.utc).isoformat(),
        review_path=str(raw),review_sha256=raw_hash,manifest_sha256=sha256(manifest_path),
        source_sha256=manifest['source_sha256'],source_group=manifest['source_group'],
        labels_origin='user_returned_review_with_explicit_user_resolutions' if resolutions else 'user_returned_review',recognition_input_allowed=False,
        resolution_sha256=None if not args.resolutions else sha256(args.resolutions),
        scoreboard_proposed_points_not_independently_verified=True,independent_holdout=False,
        bbox_or_event_accuracy_measured=False)
    write(out/'events-reviewed.json',dict(provenance=provenance,events=result['events']))
    write(out/'events-consistent-subset.json',dict(provenance=provenance,events=[e for e in result['events'] if e['usable_event_metadata']]))
    write(out/'conflicts.json',dict(provenance=provenance,events=result['conflicts']))
    write(out/'critical-windows-draft.json',dict(provenance=provenance,windows=result['diagnostic_windows']))
    summary=dict(provenance=provenance,status='ingested_with_target_link_conflicts' if result['conflicts'] else 'ingested',
                 counts=result['counts'],conflict_ids=[e['event_id'] for e in result['conflicts']],
                 task07_status='IN_PROGRESS',task08_status='TODO',
                 automatic_ball_recall=None,automatic_points_precision=None,
                 reason_metrics_unavailable='No new recognition run, no ball bbox GT or negative-event cohort',
                 input_review_preserved=sha256(raw)==raw_hash==sha256(out/'user-review-original.json'))
    write(out/'summary.json',summary)
    print(json.dumps(dict(status=summary['status'],counts=summary['counts'],conflict_ids=summary['conflict_ids']),ensure_ascii=True))
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('review','packet-dir','output-dir'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--resolutions')
    ingest(parser.parse_args())
