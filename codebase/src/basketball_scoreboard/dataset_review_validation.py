"""Fail-closed validation of supplemental labels; never authorizes training."""
import copy
import math


FRAME_SOURCE_KEYS = (
    'sample_id', 'image', 'image_sha256', 'pixel_sha256', 'source_group',
    'window_id', 'parent_source_time_s', 'segment_time_s', 'raw_pts',
    'time_base', 'original_wh', 'cfr_frame_index', 'frame_index_policy',
    'split', 'classes_required',
)


def _validate_boxes(boxes, original_wh):
    if not isinstance(boxes, list):
        raise ValueError('Boxes must be a list')
    width, height = original_wh
    seen = set()
    for box in boxes:
        coords = box.get('xyxy')
        name = box.get('class_name')
        if name not in {'ball', 'human', 'rim'} or not isinstance(coords, list) or len(coords) != 4:
            raise ValueError('Invalid class/box')
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in coords):
            raise ValueError('Finite numeric bbox required')
        x1, y1, x2, y2 = coords
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            raise ValueError('BBox out of bounds')
        key = (name, *coords)
        if key in seen:
            raise ValueError('Duplicate annotation box')
        seen.add(key)


def validate_task07a_checkpoint_subset(reviewed, manifest, source, progress, identity_source,
                                       manifest_sha256):
    """Validate a small, source-bound review export without authorizing training."""
    if reviewed.get('schema_version') != 'task07a-checkpoint-a-review-1':
        raise ValueError('Unknown checkpoint-A review schema')
    if manifest.get('schema_version') != 'task07a-checkpoint-a-manifest-1':
        raise ValueError('Unknown checkpoint-A manifest schema')
    if reviewed.get('manifest_sha256') != manifest_sha256:
        raise ValueError('Review export is not bound to this manifest')
    if reviewed.get('review_status') != 'draft':
        raise ValueError('Subset exports must remain draft')
    if reviewed.get('training_authorized') is not False:
        raise ValueError('Subset review cannot authorize training')

    source_binding = manifest.get('source_bindings', {})
    if (source_binding.get('video_sha256') != source.get('source_sha256') or
            reviewed.get('source_sha256') != source.get('source_sha256') or
            reviewed.get('source_group') != source.get('source_group')):
        raise ValueError('Ball-review source binding differs')
    progress_audit = audit_pilot_draft(progress, source)
    if source_binding.get('progress_sha256') != reviewed.get('progress_sha256'):
        raise ValueError('Prior review progress snapshot differs')

    selected_frames = manifest.get('selected_frames', [])
    review_frames = reviewed.get('frames', [])
    expected_frame_ids = [row.get('sample_id') for row in selected_frames]
    actual_frame_ids = [row.get('sample_id') for row in review_frames]
    if not expected_frame_ids or len(set(expected_frame_ids)) != len(expected_frame_ids):
        raise ValueError('Manifest frame scope is empty or duplicated')
    if actual_frame_ids != expected_frame_ids:
        raise ValueError('Frame review scope differs from manifest')

    source_samples = {row['sample_id']: row for row in source.get('samples', [])}
    progress_samples = {row['sample_id']: row for row in progress.get('samples', [])}
    for manifest_row, review_row in zip(selected_frames, review_frames):
        sample_id = manifest_row['sample_id']
        expected = source_samples.get(sample_id)
        prior = progress_samples.get(sample_id)
        if expected is None or prior is None:
            raise ValueError('Review sample is outside the bound source packet')
        if any(manifest_row.get('source_binding', {}).get(key) != expected.get(key)
               for key in FRAME_SOURCE_KEYS):
            raise ValueError('Manifest frame source metadata changed')
        if review_row.get('source_binding') != manifest_row.get('source_binding'):
            raise ValueError('Reviewed frame source metadata changed')
        if review_row.get('prediction') != manifest_row.get('prediction'):
            raise ValueError('Detector predictions must remain separate and immutable')
        if prior.get('review_status') != 'unreviewed' or prior.get('boxes') is not None:
            raise ValueError('Subset may only add labels to previously unreviewed samples')
        _validate_frame_review(review_row, expected, source)

    identity_binding = source_binding.get('identity', {})
    if (identity_binding.get('video_sha256') != identity_source.get('video_sha256') or
            reviewed.get('identity_video_sha256') != identity_source.get('video_sha256')):
        raise ValueError('Identity-review video binding differs')
    if identity_binding.get('parent_video_sha256') != source.get('source_sha256'):
        raise ValueError('Identity crop parent video differs')

    selected_identities = manifest.get('selected_identities', [])
    review_identities = reviewed.get('identities', [])
    expected_identity_ids = [row.get('sample_id') for row in selected_identities]
    actual_identity_ids = [row.get('sample_id') for row in review_identities]
    if not expected_identity_ids or len(set(expected_identity_ids)) != len(expected_identity_ids):
        raise ValueError('Manifest identity scope is empty or duplicated')
    if actual_identity_ids != expected_identity_ids:
        raise ValueError('Identity review scope differs from manifest')
    original_identities = {row['sample_id']: row for row in identity_source.get('samples', [])}
    for manifest_row, review_row in zip(selected_identities, review_identities):
        original = original_identities.get(manifest_row['sample_id'])
        if original is None:
            raise ValueError('Identity sample is outside the source packet')
        if review_row.get('source_binding') != manifest_row.get('source_binding'):
            raise ValueError('Identity source metadata changed')
        if review_row.get('predictions') != manifest_row.get('predictions'):
            raise ValueError('OCR/team predictions must remain separate and immutable')
        binding = manifest_row['source_binding']
        if (binding.get('frame_index') != original.get('frame_index') or
                binding.get('source_time_s') != original.get('source_time_s') or
                binding.get('track_id') != original.get('track_id') or
                binding.get('source_bbox') != original.get('source_bbox')):
            raise ValueError('Identity crop is not bound to its original observation')
        _validate_identity_review(review_row)

    completed = (
        any(row['review_status'] in {'approved', 'skipped'} for row in review_frames) or
        any(row['review_status'] == 'reviewed' for row in review_identities)
    )
    if completed and (not str(reviewed.get('reviewer') or '').strip() or
                      reviewed.get('label_policy_confirmed') is not True):
        raise ValueError('Completed labels require reviewer and policy confirmation')

    return dict(
        status='checkpoint_a_subset_structural_QA_only',
        reviewed_frames=len(review_frames),
        reviewed_identity_crops=len(review_identities),
        reused_approved_sample_ids=progress_audit['approved_sample_ids'],
        still_unreviewed_source_samples=len(progress_audit['unreviewed_sample_ids']) - len(review_frames),
        training_authorized=False,
        packet_approved=False,
        independent_test_ready=False,
    )


def _validate_frame_review(review_row, expected, source):
    state = review_row.get('review_status')
    scene = review_row.get('scene_status')
    scope = review_row.get('scope_decision')
    visibility = review_row.get('ball_visibility')
    boxes = review_row.get('boxes')
    if state not in {'unreviewed', 'needs_review', 'approved', 'skipped'}:
        raise ValueError('Unknown frame review state')
    if scene not in {'unreviewed', 'play', 'closeup', 'replay', 'background',
                     'camera_transition', 'needs_review'}:
        raise ValueError('Unknown scene status')
    if scope not in {'unreviewed', 'include', 'exclude', 'needs_review'}:
        raise ValueError('Unknown scope decision')
    if visibility not in {'unreviewed', 'visible', 'not_visible', 'uncertain'}:
        raise ValueError('Unknown ball visibility')
    if state in {'unreviewed', 'needs_review'}:
        if boxes is not None:
            _validate_boxes(boxes, expected['original_wh'])
        return
    if state == 'skipped':
        if scope != 'exclude' or boxes is not None or not str(review_row.get('skip_reason') or '').strip():
            raise ValueError('Excluded samples require an explicit reason and no labels')
        return
    if (scope != 'include' or scene in {'unreviewed', 'needs_review'} or
            visibility not in {'visible', 'not_visible'} or not isinstance(boxes, list)):
        raise ValueError('Approved frames require reviewed scene, scope, visibility and boxes')
    envelope_sample = dict(expected)
    envelope_sample.update(review_status='approved', scene_status=scene,
                           ball_visibility=visibility, boxes=boxes)
    envelope = dict(schema_version='task07a-pilot-labels-1', review_status='approved',
                    reviewer=review_row.get('reviewer'), label_policy_status='approved_by_reviewer',
                    source_sha256=source['source_sha256'], source_group=source['source_group'],
                    samples=[envelope_sample])
    validate_pilot_review(envelope, {**source, 'samples': [expected]})


def _validate_identity_review(review_row):
    state = review_row.get('review_status')
    if state not in {'unreviewed', 'needs_review', 'reviewed'}:
        raise ValueError('Unknown identity review state')
    labels = review_row.get('labels', {})
    if not isinstance(labels, dict):
        raise ValueError('Identity labels must be an object')
    number = labels.get('actual_number')
    team = labels.get('actual_team_id')
    allowed = {
        'crop_assessment': {'unreviewed', 'correct', 'wrong_person', 'wrong_region', 'uncertain'},
        'jersey_visibility': {'unreviewed', 'readable', 'partial', 'unreadable', 'occluded', 'uncertain'},
        'role_review': {'unreviewed', 'player', 'non_player', 'uncertain'},
        'track_association': {'unreviewed', 'correct', 'wrong_track', 'uncertain'},
    }
    for key, values in allowed.items():
        if labels.get(key) not in values:
            raise ValueError(f'Invalid identity label: {key}')
    if number is not None and (not isinstance(number, str) or not number.isdigit() or len(number) > 2):
        raise ValueError('Actual jersey number must be one or two digits, or unknown')
    if team not in {None, 'team_a', 'team_b', 'unknown'}:
        raise ValueError('Actual team must be team_a, team_b or unknown')
    if state == 'reviewed' and any(labels[key] == 'unreviewed' for key in allowed):
        raise ValueError('Reviewed identity crops require all review fields')
    if state == 'reviewed' and not str(review_row.get('reviewer') or '').strip():
        raise ValueError('Reviewed identity crops require a reviewer')
    if state == 'unreviewed' and any(
            labels.get(key) != value for key, value in {
                'crop_assessment': 'unreviewed',
                'jersey_visibility': 'unreviewed',
                'role_review': 'unreviewed',
                'track_association': 'unreviewed',
                'actual_number': None,
                'actual_team_id': None,
            }.items()):
        raise ValueError('Unreviewed identity crop contains user labels')


def merge_task07a_checkpoint_subset(reviewed, manifest, source, progress, identity_source,
                                    manifest_sha256):
    """Merge completed frame labels only; preserve every existing reviewed row."""
    validate_task07a_checkpoint_subset(reviewed, manifest, source, progress, identity_source,
                                       manifest_sha256)
    merged = copy.deepcopy(progress)
    by_id = {row['sample_id']: row for row in merged['samples']}
    for review_row in reviewed['frames']:
        if review_row['review_status'] not in {'approved', 'skipped'}:
            continue
        sample = by_id[review_row['sample_id']]
        sample['review_status'] = review_row['review_status']
        sample['scene_status'] = review_row['scene_status']
        sample['ball_visibility'] = review_row['ball_visibility']
        sample['boxes'] = copy.deepcopy(review_row['boxes'])
        for key in ('reviewer', 'reviewer_note', 'scope_decision'):
            if key in review_row:
                sample[key] = copy.deepcopy(review_row[key])
        if review_row['review_status'] == 'skipped':
            sample['skip_reason'] = review_row['skip_reason']
        else:
            sample.pop('skip_reason', None)
    merged['review_status'] = 'draft'
    merged['reviewer'] = reviewed.get('reviewer')
    merged['label_policy_status'] = (
        'approved_by_reviewer' if reviewed.get('label_policy_confirmed') is True else 'draft'
    )
    merged['training_ready'] = False
    audit = audit_pilot_draft(merged, source)
    prior_approved = {
        row['sample_id'] for row in progress['samples'] if row.get('review_status') == 'approved'
    }
    if not prior_approved.issubset(set(audit['approved_sample_ids'])):
        raise ValueError('Existing approved labels were not preserved')
    return merged


def audit_pilot_draft(packet, source):
    """Validate completed images in a partial review without approving the packet.

    The full, ordered source list must survive even when only a few images have
    been reviewed. Unreviewed labels are deliberately excluded from statistics.
    """
    if packet.get('schema_version') != source.get('schema_version') or packet.get('schema_version') != 'task07a-pilot-labels-1':
        raise ValueError('Unknown pilot schema')
    for key in ('source_sha256', 'source_group'):
        if packet.get(key) != source.get(key):
            raise ValueError('Pilot source group/hash differs')
    samples, original = packet.get('samples'), source.get('samples')
    if not isinstance(samples, list) or not samples or len(samples) != len(original):
        raise ValueError('Incomplete source sample list')
    immutable = ('sample_id', 'image', 'image_sha256', 'pixel_sha256', 'source_group', 'window_id',
                 'parent_source_time_s', 'segment_time_s', 'raw_pts', 'time_base', 'original_wh',
                 'cfr_frame_index', 'frame_index_policy', 'split', 'classes_required')
    approved, skipped, unreviewed, multiple = [], [], [], []
    for sample, expected in zip(samples, original):
        if any(sample.get(k) != expected.get(k) for k in immutable):
            raise ValueError('Immutable source sample changed')
        state = sample.get('review_status')
        if state not in {'approved', 'skipped', 'unreviewed'}:
            raise ValueError('Unknown image review state')
        if state == 'unreviewed':
            unreviewed.append(sample['sample_id'])
            continue
        # Reuse strict image checks on a separate local envelope. Neither the
        # user packet nor its policy/reviewer status is modified or exported.
        envelope = dict(schema_version='task07a-pilot-labels-1', review_status='approved',
                        reviewer='structural-check-only', label_policy_status='approved_by_reviewer',
                        source_sha256=source['source_sha256'], source_group=source['source_group'], samples=[sample])
        if state == 'skipped':
            if not str(sample.get('skip_reason') or '').strip():
                raise ValueError('Skip requires explicit reason')
            skipped.append(sample['sample_id'])
            continue
        validate_pilot_review(envelope, {**source, 'samples': [expected]})
        approved.append(sample['sample_id'])
        if sum(b['class_name'] == 'ball' for b in sample['boxes']) > 1:
            multiple.append(sample['sample_id'])
    return dict(status='partial_review_structural_QA_only', approved_sample_ids=approved,
                skipped_sample_ids=skipped, unreviewed_sample_ids=unreviewed,
                multiple_ball_sample_ids=multiple, training_authorized=False,
                packet_approved=False, independent_test_ready=False)


def validate_pilot_review(packet,source):
    if (packet.get('schema_version')!='task07a-pilot-labels-1' or packet.get('review_status')!='approved' or
            not str(packet.get('reviewer') or '').strip() or packet.get('label_policy_status')!='approved_by_reviewer'):
        raise ValueError('Reviewed packet, reviewer and label policy confirmation required')
    if packet.get('source_sha256')!=source.get('source_sha256') or packet.get('source_group')!=source.get('source_group'):
        raise ValueError('Pilot source group/hash differs')
    samples=packet.get('samples',[]);original=source.get('samples',[])
    if not samples or len(samples)!=len(original):raise ValueError('Incomplete source sample list')
    immutable=('sample_id','image','image_sha256','source_group','window_id','parent_source_time_s','raw_pts','time_base','original_wh')
    kept=skipped=boxes=0
    for sample,expected in zip(samples,original):
        if any(sample.get(k)!=expected.get(k) for k in immutable):raise ValueError('Immutable source sample changed')
        if sample.get('review_status')=='skipped':
            if not str(sample.get('skip_reason') or '').strip():raise ValueError('Skip requires explicit reason')
            skipped+=1;continue
        if sample.get('review_status')!='approved':raise ValueError('Unreviewed image cannot become training data')
        if sample.get('scene_status') not in {'play','closeup','replay','background'}:raise ValueError('Scene review required')
        if sample.get('ball_visibility') not in {'visible','not_visible'}:raise ValueError('Visibility unresolved')
        if not isinstance(sample.get('boxes'),list):raise ValueError('Null boxes are unreviewed, never a negative label')
        width,height=sample['original_wh'];seen=set();ball_count=0
        for box in sample['boxes']:
            coords=box.get('xyxy');name=box.get('class_name')
            if name not in {'ball','human','rim'} or not isinstance(coords,list) or len(coords)!=4:
                raise ValueError('Invalid class/box')
            if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in coords):
                raise ValueError('Finite numeric bbox required')
            a,b,c,d=coords
            if not (0<=a<c<=width and 0<=b<d<=height):raise ValueError('BBox out of bounds')
            key=(name,*coords)
            if key in seen:raise ValueError('Duplicate annotation box')
            seen.add(key);ball_count+=name=='ball';boxes+=1
        if (sample['ball_visibility']=='visible')!=(ball_count>0):raise ValueError('Ball visibility disagrees with labels')
        kept+=1
    if not kept:raise ValueError('No approved images retained')
    return dict(status='structural_label_QA_passed',approved_images=kept,skipped_images=skipped,boxes=boxes,
                training_authorized=False,independent_test_ready=False,
                note='Human review fields do not prove annotation correctness; all pilot windows share one source group')
