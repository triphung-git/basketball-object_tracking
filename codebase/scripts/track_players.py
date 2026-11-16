#!/usr/bin/env python3
"""Track local G03 observations; optional video crops supply real team color evidence."""
from __future__ import annotations
import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import sys
from time import perf_counter
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from basketball_scoreboard.court import CourtConfig,CourtModel
from basketball_scoreboard.identity import (
    IdentityResolver,
    LocalEasyOCRProvider,
    MockOCRProvider,
    ModelWeightsUnavailableError,
    OCRProvider,
    RosterConfig,
    TeamColorClassifier,
    enrich_observations_with_identity,
    evaluate_crop_quality,
    extract_jersey_rgb,
    JerseyEvidenceRecord,
)
from basketball_scoreboard.players import PlayerTracker
from basketball_scoreboard.spatial_io import load_spatial_input,new_output,file_hash,write_json,emit_observations,runtime_snapshot
from basketball_scoreboard.video import VideoReader
from basketball_scoreboard.tracking_policy import load_tracking_policy,in_image_roi,interval_flags
from basketball_scoreboard.identity_crops import load_identity_crop_policy,IdentityCropGuard,jersey_region


def track_players_pipeline(detections_jsonl_path,output_dir,court_config_path=None,roster_config_path=None,
                           run_json_path=None,allow_uncalibrated=False,max_age_s=1.,min_hits=3,video_path=None,
                           enable_ocr=False,ocr_provider='easyocr',ocr_weights_dir=None,
                           ocr_sampling_cadence=5,min_ocr_crop_height=24,development_authorization=None,
                           tracking_policy=None,ocr_upscale=1,jersey_evidence_ttl_s=None,
                           color_method='median',jersey_evidence_cache=None,identity_crop_policy=None,team_crop_region='legacy',reset_on_team_conflict=False):
    output = None
    started = perf_counter()
    try:
        runtime = runtime_snapshot(__file__)
        court = CourtConfig.from_json_file(court_config_path) if court_config_path else None
        run,frames = load_spatial_input(detections_jsonl_path,run_json_path,court,diagnostic=allow_uncalibrated,
                                       development_authorization=development_authorization)
        policy=load_tracking_policy(tracking_policy,run['source_fingerprint_sha256'])
        model = CourtModel(court) if court else None
        if model:
            model.calibrate(allow_uncalibrated=allow_uncalibrated)
        roster_data = json.loads(Path(roster_config_path).read_text(encoding='utf-8')) if roster_config_path else None
        if roster_data and not allow_uncalibrated and (roster_data.get('provenance_status') != 'approved' or roster_data.get('is_synthetic')):
            raise ValueError('Draft/synthetic roster requires diagnostic mode')
        roster = RosterConfig.from_dict(roster_data) if roster_data else None
        crop_policy=load_identity_crop_policy(identity_crop_policy,run['source_fingerprint_sha256'])
        if crop_policy and (not video_path or not roster):raise ValueError('Identity guard requires source video and roster')
        crop_guard=IdentityCropGuard(crop_policy,[roster.team_a_color_rgb,roster.team_b_color_rgb]) if crop_policy else None
        if team_crop_region not in {'legacy','jersey'}:raise ValueError('Unknown team crop region')
        if team_crop_region!='legacy' and (crop_guard or not video_path or not roster):
            raise ValueError('Isolated team region trial requires video/roster and no crop guard')
        if reset_on_team_conflict and (not video_path or not roster):raise ValueError('Team conflict reset requires source video and roster')
        classifier = TeamColorClassifier(roster.team_a_id,roster.team_b_id,roster.team_a_color_rgb,roster.team_b_color_rgb) if roster else None
        resolver = IdentityResolver(roster,classifier,jersey_evidence_ttl_s=jersey_evidence_ttl_s) if roster else None
        if color_method not in {'median','masked'}:raise ValueError('Unknown color method')
        cached_jerseys={};cached_boxes={};cache_meta=None
        if jersey_evidence_cache:
            if not enable_ocr:raise ValueError('Explicit enable-ocr required for evidence replay')
            cache=Path(jersey_evidence_cache)
            cache_meta=json.loads((cache/'run.json').read_text(encoding='utf-8'))
            if (cache_meta.get('status')!='completed' or cache_meta.get('ocr_status')!='enabled_easyocr_local' or
                    cache_meta.get('source_fingerprint_sha256')!=run['source_fingerprint_sha256'] or
                    cache_meta.get('input_detections_sha256')!=file_hash(detections_jsonl_path) or
                    cache_meta.get('runtime_config',{}).get('max_age_s')!=max_age_s or
                    cache_meta.get('runtime_config',{}).get('min_hits')!=min_hits):
                raise ValueError('OCR cache source/tracker provenance mismatch')
            for line in (cache/'tracked_observations.jsonl').read_text(encoding='utf-8').splitlines():
                row=json.loads(line);cached_boxes[(row['frame_index'],row['track_id'])]=row
            for row in json.loads((cache/'jersey_evidence.json').read_text(encoding='utf-8')):
                cached_jerseys.setdefault((row['frame_index'],row['track_id']),[]).append(row)
        if video_path and file_hash(video_path) != run['source_fingerprint_sha256']:
            raise ValueError('Video fingerprint differs from source run')

        ocr_engine = None
        ocr_status = 'not_enabled_pending_model_decision'
        if enable_ocr and not jersey_evidence_cache:
            if ocr_provider == 'mock':
                if not allow_uncalibrated:
                    raise ValueError('Mock OCR provider is forbidden in production/calibrated runs')
                ocr_engine = MockOCRProvider()
                ocr_status = 'enabled_mock'
            elif ocr_provider == 'easyocr':
                try:
                    ocr_engine = LocalEasyOCRProvider(model_storage_directory=ocr_weights_dir,crop_upscale=ocr_upscale)
                    ocr_status = 'enabled_easyocr_local'
                except ModelWeightsUnavailableError as mwe:
                    if not allow_uncalibrated:
                        raise
                    ocr_status = f'uncalibrated_warning_weights_unavailable: {mwe}'
                    ocr_engine = None
            else:
                raise ValueError(f'Unknown OCR provider: {ocr_provider}')
        if jersey_evidence_cache:ocr_status='replayed_verified_local_ocr_evidence'

        output = new_output(output_dir,[detections_jsonl_path,run_json_path,court_config_path,roster_config_path,video_path,tracking_policy,identity_crop_policy])
        tracker = PlayerTracker(run['video_id'],segment_id=court.segment_id if court else 'default',
                                camera_id=court.camera_id if court else 'unknown',court_model=model,
                                min_hits_to_activate=min_hits,max_age_s=max_age_s,
                                original_wh=(run['video_metadata']['width'],run['video_metadata']['height']))
        observations,evidence,jersey_evidence_records = [],[],[]
        crop_audit=[]
        prior_ledgers=[];previous_time=-1.;excluded_frames=0
        with ExitStack() as stack:
            decoded = iter(stack.enter_context(VideoReader(video_path)).frames()) if video_path else None
            current = None
            for record in frames:
                index,time = record['frame_index'],record['source_time_s']
                image = None
                if decoded:
                    while current is None or current[0].frame_index < index:
                        current = next(decoded)
                    if current[0].frame_index != index or abs(current[0].source_time_s-time) > 1e-6:
                        raise ValueError('Decoded video does not match source frame clock')
                    image = current[1]
                excluded,boundary=interval_flags(policy,previous_time,time)
                previous_time=time
                if boundary or excluded:
                    tracker.reset()
                    if crop_guard:crop_guard.reset()
                    if resolver:
                        prior_ledgers.extend(resolver.mapping_ledger)
                        resolver=IdentityResolver(roster,classifier,jersey_evidence_ttl_s=jersey_evidence_ttl_s)
                if excluded:
                    excluded_frames+=1
                    continue
                frame_obs = tracker.update_frame(index,time,record['timestamp_status'],record.get('detections',[]),
                                                run['source_fingerprint_sha256'],run['run_id'])
                if policy:
                    for obs in frame_obs:
                        if not in_image_roi(policy,obs.footpoint_image,tracker.original_wh):obs.role='non_player'
                if resolver:
                    for obs in frame_obs:
                        guarded_crop=guarded_rgb=guard_info=None
                        if crop_guard and obs.sample_type=='observed':
                            guarded_crop,guarded_rgb,guard_info=crop_guard.assess(obs,image,record.get('detections',[]),
                                clock_valid=record['timestamp_status'] in {'valid','repaired'})
                            crop_audit.append(guard_info)
                            if not guard_info['allowed']:
                                resolver.invalidate_track_evidence(obs.track_id,time,guard_info['reason'])
                                if obs.role!='non_player':obs.role='unknown'
                                continue
                        if obs.sample_type == 'observed' and obs.role != 'non_player' and image is not None:
                            x1,y1,x2,y2=obs.bbox
                            width,height=x2-x1,y2-y1
                            crop=image[max(0,int(y1+.15*height)):min(image.shape[0],int(y1+.6*height)),
                                       max(0,int(x1+.2*width)):min(image.shape[1],int(x2-.2*width))]
                            if team_crop_region=='jersey':
                                ca,cb,cc,cd=jersey_region(obs.bbox,image.shape[1],image.shape[0]);crop=image[cb:cd,ca:cc]
                            if crop_guard and crop_policy.team_region=='jersey':crop=guarded_crop
                            if crop.size:
                                quality={}
                                if crop_guard and crop_policy.team_region=='jersey':
                                    rgb,quality=guarded_rgb,guard_info['color_quality']
                                elif color_method=='masked':
                                    rgb,quality=extract_jersey_rgb(crop,[roster.team_a_color_rgb,roster.team_b_color_rgb])
                                else:rgb=tuple(float(v) for v in np.median(crop.reshape(-1,3),axis=0)[::-1])
                                team,score,reason=classifier.classify_rgb(rgb) if rgb is not None else (None,0.,quality['reason'])
                                existing=resolver.current_mappings.get(obs.track_id)
                                if (((crop_policy and crop_policy.suspend_team_conflict) or reset_on_team_conflict) and existing and existing.team_id and
                                        team and team!=existing.team_id and score>=.75):
                                    resolver.invalidate_track_evidence(obs.track_id,time,'contradictory_observed_team')
                                resolver.add_team_observation(obs.track_id,team,score,time)
                                evidence.append(dict(track_id=obs.track_id,source_time_s=time,
                                                     observed_rgb=rgb,team_id=team,score=score,
                                                     score_kind='heuristic_not_probability',reason=reason,
                                                     color_method=color_method,color_quality=quality))
                            if jersey_evidence_cache and guard_info and guard_info['mask_changed']:
                                guard_info['OCR_cache_status']='masked_pixels_require_fresh_OCR_cache_not_reused'
                            if jersey_evidence_cache and (index,obs.track_id) in cached_jerseys and not (guard_info and guard_info['mask_changed']):
                                original=cached_boxes.get((index,obs.track_id))
                                if (not original or original.get('sample_type')!='observed' or
                                        any(abs(a-b)>1e-6 for a,b in zip(original['bbox'],obs.bbox))):
                                    raise ValueError('OCR replay crop/track association differs from source')
                                for item in cached_jerseys[(index,obs.track_id)]:
                                    r=JerseyEvidenceRecord(**item)
                                    resolver.add_jersey_evidence(r);jersey_evidence_records.append(r.to_dict())
                            # OCR evaluation on jersey crop if enabled and at cadence
                            if ocr_engine is not None and height >= min_ocr_crop_height and (index % max(1, ocr_sampling_cadence) == 0):
                                jersey_crop = guarded_crop if crop_guard else image[max(0, int(y1 + .15 * height)):min(image.shape[0], int(y1 + .55 * height)),
                                                    max(0, int(x1 + .15 * width)):min(image.shape[1], int(x2 - .15 * width))]
                                readings = ocr_engine.read_jersey(jersey_crop, obs.track_id, index, time)
                                for r in readings:
                                    resolver.add_jersey_evidence(r)
                                    jersey_evidence_records.append(r.to_dict())
                        resolver.update_track_mapping(obs.track_id,time,set(tracker.tracks))
                    enrich_observations_with_identity(frame_obs,resolver)
                observations.extend(frame_obs)
                if enable_ocr and index % 100 == 0:
                    stats=getattr(ocr_engine,'stats',{})
                    progress=dict(status='running',frame_index=index,source_time_s=time,
                                  observations=len(observations),ocr_provider_stats=stats)
                    write_json(output/'progress.json',progress)
                    print(f"Tracking frame {index}/{len(frames)}; OCR attempts={stats.get('attempts',0)}",flush=True)
        emit_observations(output/'tracked_observations.jsonl',observations)
        ledger=prior_ledgers+(resolver.mapping_ledger if resolver else [])
        write_json(output/'identity_mappings.json',[m.to_dict() for m in ledger])
        write_json(output/'team_evidence.json',evidence)
        write_json(output/'jersey_evidence.json',jersey_evidence_records)
        if crop_guard:write_json(output/'identity_crop_audit.json',crop_audit)
        roles={name:sum(o.role==name for o in observations) for name in ('player','non_player','unknown')}
        has_resolved_player = any(m.player_id for m in ledger)
        summary=dict(status='completed',runtime=runtime,acceptance_scope='diagnostic' if allow_uncalibrated else 'technical',
                     video_id=run['video_id'],source_run_id=run['run_id'],source_fingerprint_sha256=run['source_fingerprint_sha256'],
                     input_detections_sha256=file_hash(detections_jsonl_path),source_run_json_sha256=file_hash(run_json_path),
                     court_config=court.to_dict() if court else None,roster_config=roster_data,
                     total_frames_processed=len(frames),total_observations_generated=len(observations),
                     total_tracks_initiated=tracker._next_track_number-1,active_tracks_at_end=len(tracker.tracks),
                     retired_tracks_count=len(tracker.retired_tracks),roles=roles,
                     sample_types={name:sum(o.sample_type==name for o in observations) for name in ('observed','predicted')},
                     team_ids=[roster.team_a_id,roster.team_b_id] if roster else ['team_a','team_b'],
                     team_color_evidence_count=len(evidence),
                     ocr_status=ocr_status,
                     ocr_provider=ocr_provider if enable_ocr else 'disabled',
                     ocr_sampling_cadence=ocr_sampling_cadence if enable_ocr else None,
                     total_jersey_evidence_count=len(jersey_evidence_records),
                     ocr_provider_stats=getattr(ocr_engine,'stats',None),
                     tracking_policy=policy,excluded_frames=excluded_frames,
                     tracking_policy_sha256=file_hash(tracking_policy) if tracking_policy else None,
                     color_method=color_method,
                     team_crop_region=team_crop_region,
                     reset_on_team_conflict=reset_on_team_conflict,
                     identity_crop_policy_sha256=file_hash(identity_crop_policy) if identity_crop_policy else None,
                     identity_crop_guard=dict(enabled=bool(crop_guard),observations_audited=len(crop_audit),
                         allowed=sum(r['allowed'] for r in crop_audit),blocked=sum(not r['allowed'] for r in crop_audit)),
                     ocr_evidence_replay=dict(source_run_sha256=file_hash(Path(jersey_evidence_cache)/'run.json'),
                         source_jersey_sha256=file_hash(Path(jersey_evidence_cache)/'jersey_evidence.json'),fresh_ocr_calls=0,
                         source_provider_stats=cache_meta.get('ocr_provider_stats'),crop_boxes_verified=True) if cache_meta else None,
                     timings=dict(tracking_total_s=perf_counter()-started,scope='validation, decode, tracking, OCR and exports; detector excluded'),
                     player_identity_status='resolved_with_consensus' if has_resolved_player else 'unresolved_without_jersey_evidence',
                     role_policy='ROI_alone_is_unknown',
                     metrics=dict(team_accuracy=None,player_accuracy=None,reason='No independently reviewed GT'),
                     runtime_config=dict(max_age_s=max_age_s,min_hits=min_hits,ocr_upscale=ocr_upscale,
                                         jersey_evidence_ttl_s=resolver.jersey_evidence_ttl_s if resolver else None,
                                         team_evidence_ttl_s=resolver.evidence_ttl_s if resolver else None))
        if development_authorization:
            summary['development_authorization'] = json.loads(Path(development_authorization).read_text(encoding='utf-8'))
        write_json(output/'tracking_summary.json',summary)
        write_json(output/'run.json',summary)
        print(f"Completed: {len(frames)} frames, {len(observations)} observations; OCR {ocr_status}")
        return 0
    except Exception as error:
        if output:
            write_json(output/'run.json',dict(status='failed',error_class=type(error).__name__))
        print(f"Tracking failed ({type(error).__name__}); input/config validation or processing failed",file=sys.stderr)
        return 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--detections',required=True)
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--court-config')
    parser.add_argument('--roster-config')
    parser.add_argument('--run-json',required=True)
    parser.add_argument('--video',help='Optional local source video for torso color extraction')
    parser.add_argument('--allow-uncalibrated',action='store_true',help='Explicit diagnostic mode for draft/synthetic inputs')
    parser.add_argument('--max-age-s',type=float,default=1.)
    parser.add_argument('--min-hits',type=int,default=3)
    parser.add_argument('--enable-ocr',action='store_true',help='Enable OCR evidence collection for jersey numbers')
    parser.add_argument('--ocr-provider',default='easyocr',choices=['easyocr','mock'],help='OCR engine backend (default: easyocr; mock requires --allow-uncalibrated)')
    parser.add_argument('--ocr-weights-dir',help='Custom local directory containing EasyOCR model weights')
    parser.add_argument('--ocr-sampling-cadence',type=int,default=5,help='Run OCR every N frames per track to manage CPU budget')
    parser.add_argument('--min-ocr-crop-height',type=int,default=24,help='Minimum pixel height for jersey crop quality validation')
    parser.add_argument('--development-authorization')
    parser.add_argument('--tracking-policy')
    parser.add_argument('--ocr-upscale',type=int,default=1)
    parser.add_argument('--jersey-evidence-ttl-s',type=float)
    parser.add_argument('--color-method',choices=['median','masked'],default='median')
    parser.add_argument('--jersey-evidence-cache')
    parser.add_argument('--identity-crop-policy')
    parser.add_argument('--team-crop-region',choices=['legacy','jersey'],default='legacy')
    parser.add_argument('--reset-on-team-conflict',action='store_true')
    args=parser.parse_args()
    return track_players_pipeline(args.detections,args.output_dir,args.court_config,args.roster_config,
                                  args.run_json,args.allow_uncalibrated,args.max_age_s,args.min_hits,args.video,
                                  enable_ocr=args.enable_ocr,ocr_provider=args.ocr_provider,
                                  ocr_weights_dir=args.ocr_weights_dir,ocr_sampling_cadence=args.ocr_sampling_cadence,
                                  min_ocr_crop_height=args.min_ocr_crop_height,
                                  development_authorization=args.development_authorization,
                                  tracking_policy=args.tracking_policy,ocr_upscale=args.ocr_upscale,
                                  jersey_evidence_ttl_s=args.jersey_evidence_ttl_s,
                                  color_method=args.color_method,jersey_evidence_cache=args.jersey_evidence_cache,
                                  identity_crop_policy=args.identity_crop_policy,team_crop_region=args.team_crop_region,
                                  reset_on_team_conflict=args.reset_on_team_conflict)


if __name__=='__main__':
    sys.exit(main())

