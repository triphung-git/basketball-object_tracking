"""Tests for source-bound Task07 checkpoint-A review subsets."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from basketball_scoreboard.dataset_review_validation import (
    merge_task07a_checkpoint_subset,
    validate_task07a_checkpoint_subset,
)


class CheckpointSubsetTests(unittest.TestCase):
    def setUp(self):
        self.source = dict(
            schema_version='task07a-pilot-labels-1',
            source_sha256='a' * 64,
            source_group='fixture-match',
            samples=[
                dict(sample_id='pilot_0000', image='images/0000.jpg', image_sha256='b' * 64,
                     pixel_sha256='c' * 64, source_group='fixture-match', window_id='window',
                     parent_source_time_s=1., segment_time_s=0., raw_pts=30, time_base='1/30',
                     original_wh=[100, 100], cfr_frame_index=30,
                     frame_index_policy='PTS', split='unassigned', review_status='unreviewed',
                     boxes=None, classes_required=['ball', 'human', 'rim']),
                dict(sample_id='pilot_0001', image='images/0001.jpg', image_sha256='d' * 64,
                     pixel_sha256='e' * 64, source_group='fixture-match', window_id='window',
                     parent_source_time_s=2., segment_time_s=1., raw_pts=60, time_base='1/30',
                     original_wh=[100, 100], cfr_frame_index=60,
                     frame_index_policy='PTS', split='unassigned', review_status='unreviewed',
                     boxes=None, classes_required=['ball', 'human', 'rim']),
            ],
        )
        self.progress = copy.deepcopy(self.source)
        self.progress['samples'][0].update(
            review_status='approved', scene_status='play', ball_visibility='visible',
            boxes=[dict(class_name='ball', xyxy=[10, 10, 20, 20])],
        )
        self.identity_source = dict(
            video_sha256='f' * 64,
            samples=[dict(sample_id='crop_0000', frame_index=0, source_time_s=0.,
                          track_id='track-0', source_bbox=[1., 2., 30., 40.])],
        )
        source_binding = {key: copy.deepcopy(self.source['samples'][1][key]) for key in (
            'sample_id', 'image', 'image_sha256', 'pixel_sha256', 'source_group', 'window_id',
            'parent_source_time_s', 'segment_time_s', 'raw_pts', 'time_base', 'original_wh',
            'cfr_frame_index', 'frame_index_policy', 'split', 'classes_required',
        )}
        identity_binding = dict(
            sample_id='crop_0000', frame_index=0, source_time_s=0.,
            track_id='track-0', source_bbox=[1., 2., 30., 40.],
            crop_sha256='1' * 64, context_sha256='2' * 64,
        )
        self.manifest = dict(
            schema_version='task07a-checkpoint-a-manifest-1',
            source_bindings=dict(
                video_sha256='a' * 64, progress_sha256='3' * 64,
                identity=dict(video_sha256='f' * 64, parent_video_sha256='a' * 64),
            ),
            selected_frames=[dict(sample_id='pilot_0001', source_binding=source_binding,
                                  prediction=dict(raw_candidates=[], selected_ball=None))],
            selected_identities=[dict(sample_id='crop_0000', source_binding=identity_binding,
                                      predictions=dict(ocr_readings=[], team=None))],
        )
        self.reviewed = dict(
            schema_version='task07a-checkpoint-a-review-1',
            review_status='draft',
            manifest_sha256='9' * 64,
            source_sha256='a' * 64,
            source_group='fixture-match',
            progress_sha256='3' * 64,
            identity_video_sha256='f' * 64,
            training_authorized=False,
            frames=[dict(
                sample_id='pilot_0001', source_binding=copy.deepcopy(source_binding),
                prediction=dict(raw_candidates=[], selected_ball=None),
                review_status='unreviewed', scene_status='unreviewed',
                scope_decision='unreviewed', ball_visibility='unreviewed', boxes=None,
                skip_reason=None,
            )],
            identities=[dict(
                sample_id='crop_0000', source_binding=copy.deepcopy(identity_binding),
                predictions=dict(ocr_readings=[], team=None),
                review_status='unreviewed',
                labels=dict(crop_assessment='unreviewed', jersey_visibility='unreviewed',
                            role_review='unreviewed', track_association='unreviewed',
                            actual_number=None, actual_team_id=None),
            )],
        )

    def validate(self):
        return validate_task07a_checkpoint_subset(
            self.reviewed, self.manifest, self.source, self.progress,
            self.identity_source, '9' * 64,
        )

    def test_initial_subset_is_bound_and_not_training_ready(self):
        result = self.validate()
        self.assertEqual(result['reviewed_frames'], 1)
        self.assertEqual(result['reviewed_identity_crops'], 1)
        self.assertEqual(result['reused_approved_sample_ids'], ['pilot_0000'])
        self.assertEqual(result['still_unreviewed_source_samples'], 0)
        self.assertFalse(result['training_authorized'])

    def test_manifest_source_scope_and_prior_progress_are_enforced(self):
        cases = []
        packet = copy.deepcopy(self.reviewed)
        packet['manifest_sha256'] = '8' * 64
        cases.append(packet)
        packet = copy.deepcopy(self.reviewed)
        packet['frames'][0]['sample_id'] = 'pilot_9999'
        cases.append(packet)
        packet = copy.deepcopy(self.reviewed)
        packet['frames'][0]['source_binding']['raw_pts'] += 1
        cases.append(packet)
        packet = copy.deepcopy(self.reviewed)
        packet['frames'][0]['prediction']['selected_ball'] = {'xyxy': [1, 1, 2, 2]}
        cases.append(packet)
        for packet in cases:
            with self.subTest(packet=packet):
                with self.assertRaises(ValueError):
                    validate_task07a_checkpoint_subset(
                        packet, self.manifest, self.source, self.progress,
                        self.identity_source, '9' * 64,
                    )

    def test_only_previously_unreviewed_samples_can_be_added(self):
        progress = copy.deepcopy(self.progress)
        progress['samples'][1]['review_status'] = 'approved'
        progress['samples'][1]['scene_status'] = 'play'
        progress['samples'][1]['ball_visibility'] = 'visible'
        progress['samples'][1]['boxes'] = [dict(class_name='ball', xyxy=[1, 1, 2, 2])]
        with self.assertRaises(ValueError):
            validate_task07a_checkpoint_subset(
                self.reviewed, self.manifest, self.source, progress,
                self.identity_source, '9' * 64,
            )

    def test_bbox_scope_and_visibility_are_validated(self):
        self.reviewed['reviewer'] = 'reviewer'
        self.reviewed['label_policy_confirmed'] = True
        self.reviewed['frames'][0].update(
            review_status='approved', scene_status='play', scope_decision='include',
            ball_visibility='visible', reviewer='reviewer',
            boxes=[dict(class_name='ball', xyxy=[10, 10, 20, 20])],
        )
        self.assertTrue(self.validate()['status'].endswith('structural_QA_only'))
        self.reviewed['frames'][0]['boxes'][0]['xyxy'] = [10, 10, 101, 20]
        with self.assertRaises(ValueError):
            self.validate()
        self.reviewed['frames'][0]['boxes'][0]['xyxy'] = [10, 10, 20, 20]
        self.reviewed['frames'][0]['ball_visibility'] = 'not_visible'
        with self.assertRaises(ValueError):
            self.validate()

    def test_identity_predictions_cannot_become_user_labels(self):
        self.reviewed['identities'][0]['predictions']['ocr_readings'] = [
            dict(detected_number='2', confidence=1.0)
        ]
        with self.assertRaises(ValueError):
            self.validate()
        self.reviewed['identities'][0]['predictions'] = dict(ocr_readings=[], team=None)
        self.reviewed['identities'][0]['review_status'] = 'reviewed'
        self.reviewed['identities'][0]['labels']['actual_number'] = '123'
        with self.assertRaises(ValueError):
            self.validate()

    def test_merge_preserves_old_approved_rows_and_only_adds_finished_labels(self):
        self.reviewed['frames'][0].update(
            review_status='approved', scene_status='play', scope_decision='include',
            ball_visibility='visible', reviewer='new-reviewer',
            reviewer_note='Preserve source-review note for future label QA',
            boxes=[dict(class_name='ball', xyxy=[25, 25, 35, 35])],
        )
        self.reviewed['reviewer'] = 'new-reviewer'
        self.reviewed['label_policy_confirmed'] = True
        before = copy.deepcopy(self.progress['samples'][0])
        merged = merge_task07a_checkpoint_subset(
            self.reviewed, self.manifest, self.source, self.progress,
            self.identity_source, '9' * 64,
        )
        self.assertEqual(merged['samples'][0], before)
        self.assertEqual(merged['samples'][1]['review_status'], 'approved')
        self.assertEqual(merged['samples'][1]['boxes'][0]['xyxy'], [25, 25, 35, 35])
        self.assertEqual(merged['samples'][1]['reviewer_note'], 'Preserve source-review note for future label QA')
        self.assertEqual(merged['samples'][1]['reviewer'], 'new-reviewer')
        self.assertEqual(merged['samples'][1]['scope_decision'], 'include')
        self.assertFalse(merged['training_ready'])


if __name__ == '__main__':
    unittest.main()
