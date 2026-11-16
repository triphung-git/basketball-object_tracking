#!/usr/bin/env python3
"""Prepare a small source-bound Task07 review packet; never changes labels or weights."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

import av
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from basketball_scoreboard.dataset_review_validation import audit_pilot_draft
from basketball_scoreboard.spatial_io import file_hash, new_output, write_json
from basketball_scoreboard.video import probe_video


FRAME_SOURCE_KEYS = (
    'sample_id', 'image', 'image_sha256', 'pixel_sha256', 'source_group',
    'window_id', 'parent_source_time_s', 'segment_time_s', 'raw_pts',
    'time_base', 'original_wh', 'cfr_frame_index', 'frame_index_policy',
    'split', 'classes_required',
)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8-sig').splitlines()
            if line.strip()]


def resolve_input(codebase, relative):
    path = (codebase / relative).resolve()
    if not path.is_relative_to(codebase.resolve()) or not path.is_file():
        raise ValueError(f'Input is missing or outside codebase: {relative}')
    return path


def decode_frame_at(video_path, target_s):
    with av.open(str(video_path)) as container:
        stream = container.streams.video[0]
        container.seek(int(target_s / float(stream.time_base)), stream=stream,
                       backward=True, any_frame=False)
        for frame in container.decode(stream):
            if frame.pts is None:
                continue
            timestamp = float(frame.pts * frame.time_base)
            if timestamp + 1e-6 < target_s:
                continue
            return frame.to_ndarray(format='gray'), int(frame.pts), str(frame.time_base), timestamp
    raise ValueError(f'Could not decode frame at {target_s:.6f}s from {video_path.name}')


def verify_video_alignment(parent_video, child_video, offset_s, local_times):
    checks = []
    fps = probe_video(parent_video).fps
    for local_s in sorted(set(local_times)):
        child, child_pts, child_tb, child_actual_s = decode_frame_at(child_video, local_s)
        parent_target = offset_s + local_s
        parent, parent_pts, parent_tb, parent_actual_s = decode_frame_at(parent_video, parent_target)
        if abs(child_actual_s - local_s) > 0.51 / fps or abs(parent_actual_s - parent_target) > 0.51 / fps:
            raise ValueError('Identity segment frame PTS does not map to the declared parent offset')
        child_small = cv2.resize(child, (320, 180), interpolation=cv2.INTER_AREA).astype(np.float32)
        parent_small = cv2.resize(parent, (320, 180), interpolation=cv2.INTER_AREA).astype(np.float32)
        correlation = float(np.corrcoef(child_small.ravel(), parent_small.ravel())[0, 1])
        if not np.isfinite(correlation) or correlation < 0.98:
            raise ValueError(
                f'Identity video alignment failed at {local_s:.3f}s '
                f'(parent {parent_target:.3f}s, correlation {correlation:.4f})'
            )
        checks.append(dict(
            segment_time_s=local_s,
            segment_pts=child_pts,
            segment_time_base=child_tb,
            segment_actual_time_s=child_actual_s,
            parent_time_s=parent_target,
            parent_pts=parent_pts,
            parent_time_base=parent_tb,
            parent_actual_time_s=parent_actual_s,
            downsampled_gray_correlation=correlation,
        ))
    return checks


def make_context_clip(ffmpeg, source_video, output_path, start_s, duration_s):
    command = [
        str(ffmpeg), '-nostdin', '-hide_banner', '-v', 'error', '-y',
        '-ss', f'{start_s:.6f}', '-i', str(source_video), '-t', f'{duration_s:.6f}',
        '-map', '0:v:0', '-an', '-vf', 'scale=960:-2:flags=lanczos',
        '-c:v', 'libvpx', '-deadline', 'realtime', '-cpu-used', '5',
        '-crf', '30', '-b:v', '0', '-pix_fmt', 'yuv420p',
        '-fps_mode', 'passthrough', str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    if result.returncode:
        raise RuntimeError(f'ffmpeg failed for {output_path.name}: {result.stderr.strip()}')
    metadata = probe_video(output_path)
    if metadata.width != 960 or abs(metadata.duration_s - duration_s) > 1 / metadata.fps:
        raise ValueError(f'Context clip validation failed: {output_path.name}')
    return metadata


def make_context_preview(ffmpeg, source_video, output_path, start_s, duration_s):
    command = [
        str(ffmpeg), '-nostdin', '-hide_banner', '-v', 'error', '-y',
        '-ss', f'{start_s:.6f}', '-i', str(source_video), '-t', f'{duration_s:.6f}',
        '-map', '0:v:0', '-an',
        '-vf', 'fps=10,scale=640:-2:flags=lanczos',
        '-loop', '0', '-f', 'gif', str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    if result.returncode:
        raise RuntimeError(f'ffmpeg failed for {output_path.name}: {result.stderr.strip()}')
    metadata = probe_video(output_path)
    if metadata.width != 640 or abs(metadata.duration_s - duration_s) > 1 / metadata.fps:
        raise ValueError(f'Context preview validation failed: {output_path.name}')
    return metadata


def validate_progress_counts(audit, expected_sample_count):
    if (len(audit['approved_sample_ids']) != 40 or
            len(audit['unreviewed_sample_ids']) != expected_sample_count - 40 or
            audit['skipped_sample_ids']):
        raise ValueError('Prior review progress differs from the verified 40/319 baseline')


def prepare(args):
    codebase = Path(args.codebase).resolve()
    settings_path = Path(args.settings).resolve()
    settings = read_json(settings_path)
    if settings.get('schema_version') != 'task07-checkpoint-a-settings-1':
        raise ValueError('Unknown checkpoint-A settings schema')
    paths = {
        key: resolve_input(codebase, settings[value])
        for key, value in {
            'video': 'source_video',
            'pilot': 'pilot_source',
            'progress': 'prior_progress',
            'sampling_audit': 'pilot_sampling_audit',
            'suggestions': 'detector_suggestions',
            'prior_predictions': 'prior_selector_predictions',
            'identity_video': 'identity_video',
            'identity_packet': 'identity_packet',
            'identity_manifest': 'identity_preparation_manifest',
            'identity_evidence': 'identity_source_evidence',
            'identity_tracking_run': 'identity_tracking_run',
            'observations': 'identity_observations',
            'team_evidence': 'identity_team_evidence',
            'jersey_evidence': 'identity_jersey_evidence',
        }.items()
    }
    parent_meta = probe_video(paths['video'])
    if parent_meta.sha256 != '1443c1d263c8037a5684f3dbc0ef9216beb5097d9a47c4c1c9b94d1363e26865':
        raise ValueError('Basketball source video hash differs from the audited source')
    source = read_json(paths['pilot'])
    progress = read_json(paths['progress'])
    sampling_audit = read_json(paths['sampling_audit'])
    audit = audit_pilot_draft(progress, source)
    validate_progress_counts(audit, len(source['samples']))
    if (sampling_audit.get('saved') != len(source['samples']) or
            sampling_audit.get('original_labels_read') is not False or
            sampling_audit.get('training_started') is not False):
        raise ValueError('Pilot sampling audit does not match the source-only packet')
    if source.get('source_sha256') != parent_meta.sha256:
        raise ValueError('Pilot packet does not bind to the audited source video')

    sample_by_id = {row['sample_id']: row for row in source['samples']}
    progress_by_id = {row['sample_id']: row for row in progress['samples']}
    suggestion_rows = read_jsonl(paths['suggestions'])
    suggestions = {row['sample_id']: row for row in suggestion_rows}
    if len(suggestions) != len(suggestion_rows) or set(suggestions) != set(sample_by_id):
        raise ValueError('Detector suggestion coverage is incomplete or duplicated')
    prior_predictions = read_json(paths['prior_predictions'])
    frame_settings = settings['frames']
    frame_ids = [row['sample_id'] for row in frame_settings]
    if len(frame_ids) != len(set(frame_ids)) or not 12 <= len(frame_ids) <= 16:
        raise ValueError('New frame review budget must be 12-16 unique samples')
    if len(frame_ids) > settings['review_policy']['new_frame_hard_cap']:
        raise ValueError('New frame review exceeds the hard cap')
    for sample_id in frame_ids:
        if sample_id not in sample_by_id or progress_by_id[sample_id]['review_status'] != 'unreviewed':
            raise ValueError(f'Frame is missing or already reviewed: {sample_id}')

    identity_source = read_json(paths['identity_packet'])
    identity_manifest = read_json(paths['identity_manifest'])
    identity_evidence = read_json(paths['identity_evidence'])
    if (identity_source.get('review_status') != 'draft' or
            identity_source.get('video_sha256') != probe_video(paths['identity_video']).sha256 or
            identity_source.get('video_sha256') != identity_manifest.get('source_video_sha256') or
            identity_manifest.get('gt_read') is not False or
            identity_manifest.get('ocr_calls') != 0):
        raise ValueError('Identity preparation source binding/GT isolation check failed')
    if (identity_evidence.get('tracking_run_sha256') != file_hash(paths['identity_tracking_run']) or
            identity_evidence.get('jersey_evidence_sha256') != file_hash(paths['jersey_evidence'])):
        raise ValueError('Historical tracking/OCR evidence hashes do not match their source artifacts')
    identity_rows = {row['sample_id']: row for row in identity_source.get('samples', [])}
    identity_metrics = {row['sample_id']: row for row in identity_evidence.get('crop_metrics', [])}
    identity_settings = settings['identity_samples']
    identity_ids = [row['sample_id'] for row in identity_settings]
    if len(identity_ids) != len(set(identity_ids)) or not 12 <= len(identity_ids) <= 16:
        raise ValueError('Identity review budget must be 12-16 unique crops')
    if identity_manifest.get('ocr_calls') != 0:
        raise ValueError('Identity crop preparation unexpectedly ran OCR')
    if len(identity_rows) != 204:
        raise ValueError('Identity source packet is not the expected 204-crop preparation')
    for sample_id in identity_ids:
        original = identity_rows.get(sample_id)
        if (original is None or original.get('reviewed') is not False or
                original.get('actual_number') is not None or original.get('actual_team_id') is not None):
            raise ValueError(f'Identity crop is missing, reviewed or already labeled: {sample_id}')

    if not shutil.which(str(args.ffmpeg)) and not Path(args.ffmpeg).is_file():
        raise FileNotFoundError(f'ffmpeg executable not found: {args.ffmpeg}')
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = codebase / output_dir
    inputs = [*paths.values(), settings_path]
    out = new_output(output_dir, inputs)
    for name in ('frames', 'identity', 'clips'):
        (out / name).mkdir()
    (out / 'identity' / 'crops').mkdir()
    (out / 'identity' / 'context').mkdir()
    write_json(out / 'run.json', dict(status='running', settings_sha256=file_hash(settings_path)))
    try:
        identity_video_meta = probe_video(paths['identity_video'])
        offset = float(settings['identity_parent_offset_s'])
        if identity_video_meta.sha256 != identity_source['video_sha256']:
            raise ValueError('Identity video hash differs from preparation metadata')
        alignment = verify_video_alignment(
            paths['video'], paths['identity_video'], offset,
            [identity_rows[sample_id]['source_time_s'] for sample_id in identity_ids],
        )

        selected_frames = []
        review_frames = []
        for selection in frame_settings:
            sample = sample_by_id[selection['sample_id']]
            suggestion = suggestions[sample['sample_id']]
            if suggestion.get('image_sha256') != sample['image_sha256']:
                raise ValueError(f'Detector suggestion image hash mismatch: {sample["sample_id"]}')
            image_source = (paths['pilot'].parent / sample['image']).resolve()
            if not image_source.is_relative_to(paths['pilot'].parent.resolve()) or file_hash(image_source) != sample['image_sha256']:
                raise ValueError(f'Source image hash mismatch: {sample["sample_id"]}')
            image_name = f'frames/{sample["sample_id"]}.jpg'
            shutil.copy2(image_source, out / image_name)
            if file_hash(out / image_name) != sample['image_sha256']:
                raise ValueError(f'Copied frame hash mismatch: {sample["sample_id"]}')
            selected_ball = None
            selector_status = 'not_evaluated_in_existing_selector_artifact'
            if sample['sample_id'] in prior_predictions:
                selected = prior_predictions[sample['sample_id']].get('context', [])
                selected_ball = selected[0] if selected else None
                selector_status = 'existing_selector_output'
            prediction = dict(
                raw_candidates=[row for row in suggestion['boxes'] if row.get('class_name') == 'ball'],
                all_detector_suggestions=suggestion['boxes'],
                selected_ball=selected_ball,
                selected_ball_status=selector_status,
                model_suggestion_status=suggestion.get('review_status'),
            )
            binding = {key: sample[key] for key in FRAME_SOURCE_KEYS}
            clip = next(row for row in settings['ball_context_clips']
                        if sample['sample_id'] in row['sample_ids'])
            entry = dict(
                sample_id=sample['sample_id'], image=image_name, clip_id=clip['clip_id'],
                source_binding=binding, selection_reason=selection['reason'],
                scene_triage=next(
                    (row for row in settings['scene_windows'] if row['window_id'] == sample['window_id']),
                    None,
                ),
                prediction=prediction,
                prior_label_status=progress_by_id[sample['sample_id']]['review_status'],
                prior_boxes=progress_by_id[sample['sample_id']]['boxes'],
            )
            selected_frames.append(entry)
            review_frames.append(dict(
                **entry, review_status='unreviewed', scene_status='unreviewed',
                scope_decision='unreviewed', ball_visibility='unreviewed', boxes=None,
                skip_reason=None, reviewer=None,
            ))

        tracked = read_jsonl(paths['observations'])
        team_rows = read_json(paths['team_evidence'])
        jersey_rows = read_json(paths['jersey_evidence'])
        tracked_by_key = {}
        for row in tracked:
            tracked_by_key.setdefault((row.get('frame_index'), row.get('track_id')), []).append(row)
        jersey_by_id = {row['evidence_id']: row for row in jersey_rows}
        crop_metrics_by_id = {row['sample_id']: row for row in identity_evidence['crop_metrics']}
        selected_identities = []
        review_identities = []
        identity_alignment_by_time = {round(row['segment_time_s'], 6): row for row in alignment}
        for selection in identity_settings:
            sample = identity_rows[selection['sample_id']]
            metric = crop_metrics_by_id.get(sample['sample_id'])
            if metric is None:
                raise ValueError(f'Missing identity crop quality evidence: {sample["sample_id"]}')
            crop_source = (paths['identity_packet'].parent / sample['crop']).resolve()
            context_source = (paths['identity_packet'].parent / sample['context']).resolve()
            if (not crop_source.is_relative_to(paths['identity_packet'].parent.resolve()) or
                    not context_source.is_relative_to(paths['identity_packet'].parent.resolve())):
                raise ValueError('Identity image path escapes the source preparation folder')
            crop_hash = file_hash(crop_source)
            context_hash = file_hash(context_source)
            crop_name = f'identity/crops/{sample["sample_id"]}.jpg'
            context_name = f'identity/context/{sample["sample_id"]}.jpg'
            shutil.copy2(crop_source, out / crop_name)
            shutil.copy2(context_source, out / context_name)
            if file_hash(out / crop_name) != crop_hash or file_hash(out / context_name) != context_hash:
                raise ValueError(f'Identity image copy hash mismatch: {sample["sample_id"]}')
            observations = tracked_by_key.get((sample['frame_index'], sample['track_id']), [])
            if len(observations) != 1:
                raise ValueError(f'Identity track observation is missing/ambiguous: {sample["sample_id"]}')
            observation = observations[0]
            if observation.get('source_fingerprint_sha256') != identity_source['video_sha256']:
                raise ValueError('Identity tracking observation is bound to another video')
            time_matches = [
                row for row in team_rows
                if row.get('track_id') == sample['track_id'] and
                abs(float(row.get('source_time_s', -1000)) - sample['source_time_s']) <= 1 / 30 + 1e-6
            ]
            team_evidence = min(
                time_matches,
                key=lambda row: abs(float(row['source_time_s']) - sample['source_time_s']),
            ) if time_matches else None
            if team_evidence and abs(float(team_evidence['source_time_s']) - sample['source_time_s']) > 1 / 30 + 1e-6:
                team_evidence = None
            evidence_ids = metric.get('evidence_ids', [])
            if any(evidence_id not in jersey_by_id for evidence_id in evidence_ids):
                raise ValueError(f'Identity OCR evidence is missing: {sample["sample_id"]}')
            readings = [jersey_by_id[evidence_id] for evidence_id in evidence_ids]
            parent_time = offset + float(sample['source_time_s'])
            alignment_row = identity_alignment_by_time.get(round(float(sample['source_time_s']), 6))
            if alignment_row is None:
                raise ValueError('Selected identity sample has no verified parent PTS alignment')
            source_binding = dict(
                sample_id=sample['sample_id'], frame_index=sample['frame_index'],
                source_time_s=sample['source_time_s'], parent_source_time_s=parent_time,
                parent_raw_pts=alignment_row['parent_pts'],
                parent_time_base=alignment_row['parent_time_base'],
                track_id=sample['track_id'], source_bbox=sample['source_bbox'],
                jersey_crop_xyxy=sample['jersey_crop_xyxy'],
                crop_source_sha256=crop_hash, context_source_sha256=context_hash,
                crop_wh=metric['crop_wh'], evidence_ids=evidence_ids,
                sampling_source=sample['sampling_source'],
            )
            predictions = dict(
                track_id=sample['track_id'],
                team_id=observation.get('team_id'),
                team_score=team_evidence.get('score') if team_evidence else None,
                team_score_kind=team_evidence.get('score_kind') if team_evidence else None,
                team_method=team_evidence.get('color_method') if team_evidence else None,
                role=observation.get('role'),
                sample_type=observation.get('sample_type'),
                ocr_readings=[
                    {key: row.get(key) for key in (
                        'evidence_id', 'detected_number', 'confidence', 'ocr_engine',
                        'is_valid', 'rejection_reason',
                    )} for row in readings
                ],
                crop_quality={
                    key: metric.get(key) for key in (
                        'crop_wh', 'gray_laplacian_variance', 'contrast_std',
                    )
                },
            )
            clip = next(row for row in settings['identity_context_clips']
                        if sample['sample_id'] in row['sample_ids'])
            entry = dict(
                sample_id=sample['sample_id'], crop=crop_name, context=context_name,
                clip_id=clip['clip_id'], source_binding=source_binding,
                selection_reason=selection['reason'], predictions=predictions,
            )
            selected_identities.append(entry)
            review_identities.append(dict(
                **entry, review_status='unreviewed',
                labels=dict(
                    crop_assessment='unreviewed', jersey_visibility='unreviewed',
                    role_review='unreviewed', track_association='unreviewed',
                    actual_number=None, actual_team_id=None,
                ),
            ))

        clip_records = []
        all_clips = settings['ball_context_clips'] + settings['identity_context_clips']
        for clip in all_clips:
            destination = out / 'clips' / f'{clip["clip_id"]}.webm'
            preview_destination = out / 'clips' / f'{clip["clip_id"]}.gif'
            parent_time = clip['start_s']
            if clip['clip_id'].startswith('identity-'):
                parent_time += offset
            metadata = make_context_clip(
                args.ffmpeg, paths['video'], destination, parent_time, clip['duration_s']
            )
            preview_metadata = make_context_preview(
                args.ffmpeg, paths['video'], preview_destination, parent_time, clip['duration_s']
            )
            clip_records.append(dict(
                **clip, file=f'clips/{destination.name}',
                file_sha256=file_hash(destination),
                preview_file=f'clips/{preview_destination.name}',
                preview_file_sha256=file_hash(preview_destination),
                preview_media=preview_metadata.to_dict(),
                source_start_s=parent_time, source_duration_s=clip['duration_s'],
                source_video_sha256=parent_meta.sha256, media=metadata.to_dict(),
                timeline='clip_time_s maps to source_start_s + clip_time_s',
            ))

        source_hashes = {key: file_hash(path) for key, path in paths.items()}
        source_hashes['settings'] = file_hash(settings_path)
        manifest = dict(
            schema_version='task07a-checkpoint-a-manifest-1',
            status='review_subset_prepared_not_reviewed',
            source_bindings=dict(
                video_sha256=parent_meta.sha256,
                pilot_packet_sha256=source_hashes['pilot'],
                progress_sha256=source_hashes['progress'],
                detector_suggestions_sha256=source_hashes['suggestions'],
                prior_selector_predictions_sha256=source_hashes['prior_predictions'],
                identity=dict(
                    video_sha256=identity_source['video_sha256'],
                    parent_video_sha256=parent_meta.sha256,
                    parent_offset_s=offset,
                    tracking_run_sha256=identity_evidence['tracking_run_sha256'],
                    jersey_evidence_sha256=identity_evidence['jersey_evidence_sha256'],
                    source_evidence_sha256=source_hashes['identity_evidence'],
                    gt_read=False,
                    alignment_checks=alignment,
                ),
            ),
            source_video=parent_meta.to_dict(),
            prior_review=dict(
                approved_count=len(audit['approved_sample_ids']),
                approved_sample_ids=audit['approved_sample_ids'],
                unreviewed_count=len(audit['unreviewed_sample_ids']),
                skipped_count=len(audit['skipped_sample_ids']),
            ),
            selected_frame_sample_ids=frame_ids,
            selected_frames=selected_frames,
            selected_identity_sample_ids=identity_ids,
            selected_identities=selected_identities,
            context_clips=clip_records,
            scene_windows=settings['scene_windows'],
            scope=dict(
                source_packet_samples=len(source['samples']),
                selected_new_frames=len(frame_ids),
                remaining_unreviewed_sample_ids=[
                    sample_id for sample_id in audit['unreviewed_sample_ids']
                    if sample_id not in set(frame_ids)
                ],
                remaining_unreviewed_count=len(audit['unreviewed_sample_ids']) - len(frame_ids),
                identity_source_crops=len(identity_source['samples']),
                selected_identity_crops=len(identity_ids),
                remaining_identity_crops=len(identity_source['samples']) - len(identity_ids),
                no_samples_marked_skipped=True,
                no_labels_or_splits_changed=True,
                source_groups=['vietnam_tonga_same_match_2025'],
                independent_match_test=False,
            ),
            input_paths={key: path.relative_to(codebase).as_posix() for key, path in paths.items()},
            input_sha256=source_hashes,
            sampling_audit=dict(
                saved=sampling_audit['saved'],
                requested=sampling_audit['requested_samples'],
                exact_duplicate_pixels_removed=sampling_audit['exact_duplicate_pixels_removed'],
            ),
            detector_run=dict(
                samples=len(suggestion_rows),
                model_id='phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1',
                backend='onnx', device='cpu', training_started=False,
                training_labels_exported=False,
            ),
        )
        write_json(out / 'review-manifest.json', manifest)
        manifest_sha = file_hash(out / 'review-manifest.json')
        review_packet = dict(
            schema_version='task07a-checkpoint-a-review-1',
            review_status='draft',
            manifest_file='review-manifest.json',
            manifest_sha256=manifest_sha,
            source_sha256=parent_meta.sha256,
            source_group=source['source_group'],
            progress_sha256=source_hashes['progress'],
            identity_video_sha256=identity_source['video_sha256'],
            reviewer=None,
            label_policy_confirmed=False,
            training_authorized=False,
            frames=review_frames,
            identities=review_identities,
        )
        write_json(out / 'review-packet.json', review_packet)
        report_data = dict(packet=review_packet, clips=clip_records)
        template = (ROOT / 'scripts' / 'task07a_checkpoint_a_review_simple.html').read_text(encoding='utf-8')
        safe_json = json.dumps(report_data, ensure_ascii=False).replace('</', '<\\/')
        (out / 'review.html').write_text(
            template.replace('__REVIEW_DATA__', safe_json), encoding='utf-8'
        )
        window_ranges = []
        for scene in settings['scene_windows']:
            rows = [row for row in source['samples'] if row['window_id'] == scene['window_id']]
            window_ranges.append(dict(
                window_id=scene['window_id'],
                start_s=min(row['parent_source_time_s'] for row in rows),
                end_s=max(row['parent_source_time_s'] for row in rows),
                source_samples=len(rows),
            ))
        selected_by_id = {row['sample_id']: row for row in frame_settings}
        approved_ids = set(audit['approved_sample_ids'])
        sample_decisions = []
        for sample in source['samples']:
            sample_id = sample['sample_id']
            if sample_id in approved_ids:
                decision = 'reuse_existing_approved'
                reason = 'Preserve the previously reviewed label; do not request this frame again.'
            elif sample_id in selected_by_id:
                decision = 'selected_for_new_review'
                reason = selected_by_id[sample_id]['reason']
            else:
                decision = 'not_selected_remains_unreviewed'
                reason = 'Outside the bounded review subset; not excluded, skipped, or used as a negative.'
            sample_decisions.append(dict(
                sample_id=sample_id,
                parent_source_time_s=sample['parent_source_time_s'],
                raw_pts=sample['raw_pts'],
                time_base=sample['time_base'],
                image_sha256=sample['image_sha256'],
                window_id=sample['window_id'],
                prior_review_status=progress_by_id[sample_id]['review_status'],
                decision=decision,
                reason=reason,
            ))
        write_json(out / 'scene-manifest.json', dict(
            source_sha256=parent_meta.sha256,
            sampling_windows=window_ranges,
            assessments=settings['scene_windows'],
            selected_frames=frame_ids,
            reused_approved_sample_ids=audit['approved_sample_ids'],
            sample_decisions=sample_decisions,
            exact_duplicate_audit=sampling_audit['exact_duplicate_pixels_removed'],
            unselected_unreviewed_count=len(audit['unreviewed_sample_ids']) - len(frame_ids),
            replay_policy='No sample is classified as replay from a still image alone; uncertain scenes remain needs_review.',
        ))
        result = dict(
            status='completed',
            output_dir=str(out),
            manifest_sha256=manifest_sha,
            source_sha256=parent_meta.sha256,
            reviewed_before=len(audit['approved_sample_ids']),
            still_unreviewed_before=len(audit['unreviewed_sample_ids']),
            new_frames=len(frame_ids),
            identity_crops=len(identity_ids),
            remaining_unreviewed=len(audit['unreviewed_sample_ids']) - len(frame_ids),
            remaining_identity_crops=len(identity_source['samples']) - len(identity_ids),
            training_authorized=False,
            source_hashes=source_hashes,
        )
        write_json(out / 'run.json', result)
        return result
    except Exception as error:
        write_json(out / 'run.json', dict(status='failed', error_class=type(error).__name__,
                                          error=str(error)))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codebase', default=str(ROOT))
    parser.add_argument('--settings', default=str(ROOT / 'configs' / 'task07a' / 'checkpoint-a-review-20261105.json'))
    parser.add_argument('--output-dir', default='outputs/task07-checkpoint-a-review-20261105')
    parser.add_argument('--ffmpeg', default=shutil.which('ffmpeg') or 'ffmpeg')
    args = parser.parse_args()
    try:
        result = prepare(args)
        print(json.dumps(result, indent=2))
        return 0
    except Exception as error:
        print(f'Checkpoint-A packet preparation failed ({type(error).__name__}): {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
