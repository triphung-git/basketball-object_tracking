"""Returned annotations must not silently become incorrect event ground truth."""
import copy
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest

SPEC=importlib.util.spec_from_file_location('ingest_scoring_review',Path(__file__).parents[1]/'scripts/ingest_scoring_review.py')
MODULE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MODULE)


class ScoringReviewIntakeTests(unittest.TestCase):
    def setUp(self):
        self.manifest=dict(source_sha256='source',source_fps=30,players=[
            dict(player_id='a_1',team_id='team_a'),dict(player_id='b_1',team_id='team_b')],entries=[
            dict(id='play_001',duration_s=19.,source_time_offset_s=133.,start_s=133.,end_s=152.,
                 video='clips/play_001.mp4',draft_scoring_team='team_b',draft_points=2,
                 before_score_tga_vie=[0,0],after_score_tga_vie=[2,0])])
        self.review=dict(schema_version='scoreboard-shot-review-1',manifest_sha256='manifest',
            source_sha256='source',purpose='user_review_annotation_only_not_recognition_input',reviews={
            'play_001':dict(decision='confirmed_clear',shot_kind='field_goal',shooter_id='b_1',
                ball_visibility='clear',release_clip_s=7.533333,basket_clip_s=8.8,notes='')})

    def result(self):return MODULE.validate_review(self.review,self.manifest,'manifest')

    def test_source_clock_mapping_and_frame_rounding(self):
        result=self.result();event=result['events'][0]
        self.assertAlmostEqual(event['times']['release']['source_s'],140.533333)
        self.assertEqual(event['times']['release']['source_frame_index'],4216)
        self.assertEqual(len(result['diagnostic_windows']),1)
        self.assertTrue(result['diagnostic_windows'][0]['selection_uses_reviewed_times'])
        self.assertFalse(event['ball_bbox_GT_present'])

    def test_opposite_team_quarantines_actor_and_times_without_rewriting_user(self):
        self.review['reviews']['play_001']['shooter_id']='a_1'
        before=copy.deepcopy(self.review);result=self.result()
        self.assertEqual(self.review,before)
        self.assertEqual(result['counts']['conflicting_target_links'],1)
        self.assertEqual(result['counts']['consistent_event_metadata'],0)
        self.assertEqual(result['diagnostic_windows'],[])
        self.assertEqual(result['events'][0]['review']['shooter_id'],'a_1')

    def test_missing_optional_times_and_actor_remain_null(self):
        r=self.review['reviews']['play_001'];r.update(release_clip_s=None,basket_clip_s=None,shooter_id=None)
        result=self.result();self.assertTrue(result['events'][0]['usable_event_metadata'])
        self.assertIsNone(result['events'][0]['times']['release']['source_s'])
        self.assertEqual(result['diagnostic_windows'],[])

    def test_partial_or_unknown_visibility_not_promoted_to_clear_ball_GT(self):
        for visibility in ('partial','unknown','not_visible'):
            with self.subTest(visibility=visibility):
                self.review['reviews']['play_001']['ball_visibility']=visibility
                result=self.result();self.assertEqual(result['diagnostic_windows'],[])
                self.assertEqual(result['counts']['ball_bbox_GT_samples'],0)
        self.review['reviews']['play_001'].update(ball_visibility='clear',decision='confirmed_partial')
        self.assertEqual(self.result()['diagnostic_windows'],[])

    def test_source_or_manifest_mismatch_rejected(self):
        for field in ('source_sha256','manifest_sha256'):
            with self.subTest(field=field):
                changed=copy.deepcopy(self.review);changed[field]='different'
                with self.assertRaises(ValueError):MODULE.validate_review(changed,self.manifest,'manifest')

    def test_nonfinite_outside_clip_and_reversed_times_rejected(self):
        for value in (True,-1,19.,math.inf,math.nan):
            with self.subTest(value=value):
                changed=copy.deepcopy(self.review);changed['reviews']['play_001']['release_clip_s']=value
                with self.assertRaises(ValueError):MODULE.validate_review(changed,self.manifest,'manifest')
        self.review['reviews']['play_001']['release_clip_s']=9.
        with self.assertRaises(ValueError):self.result()

    def test_other_clip_and_unapproved_actor_rejected(self):
        changed=copy.deepcopy(self.review);changed['reviews']['other']=changed['reviews'].pop('play_001')
        with self.assertRaises(ValueError):MODULE.validate_review(changed,self.manifest,'manifest')
        self.review['reviews']['play_001']['shooter_id']='invented'
        with self.assertRaises(ValueError):self.result()

    def test_free_throw_two_point_conflict_is_not_silently_relabelled(self):
        self.review['reviews']['play_001']['shot_kind']='free_throw'
        result=self.result();self.assertEqual(result['counts']['conflicting_target_links'],1)
        self.assertIn('free_throw_label_conflicts_with_target_increment',result['events'][0]['issues'])

    def test_duplicate_json_keys_and_nan_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'review.json'
            for value in ('{"reviews":{},"reviews":{}}','{"release_clip_s":NaN}'):
                path.write_text(value,encoding='utf-8')
                with self.assertRaises(ValueError):MODULE.strict_json(path)

    def swapped_packet(self):
        second=copy.deepcopy(self.manifest['entries'][0])
        second.update(id='play_002',duration_s=30.,source_time_offset_s=130.,start_s=130.,end_s=160.,
                      draft_scoring_team='team_a',draft_points=1,before_score_tga_vie=[2,0],after_score_tga_vie=[2,1])
        self.manifest['entries'].append(second)
        self.review['reviews']['play_001']['shooter_id']='a_1'
        self.review['reviews']['play_002']=dict(decision='confirmed_clear',shot_kind='field_goal',
            shooter_id='b_1',ball_visibility='clear',release_clip_s=15.2,basket_clip_s=16.5,notes='two events')
        return dict(schema_version='scoring-review-resolution-1',review_sha256='raw',manifest_sha256='manifest',
            confirmation_record='explicit test-user confirmation',actions=[
                dict(kind='transfer_annotations_preserve_source_clock',status='confirmed_by_user',target_event_id=t,source_event_id=s)
                for t,s in [('play_001','play_002'),('play_002','play_001')]])

    def test_confirmed_two_way_transfer_uses_original_and_preserves_source_clocks(self):
        resolutions=self.swapped_packet();before=copy.deepcopy(self.review)
        derived=MODULE.apply_resolutions(self.review,self.manifest,resolutions,'raw','manifest')
        self.assertEqual(self.review,before)
        self.assertEqual(derived['reviews']['play_001']['shooter_id'],'b_1')
        self.assertEqual(derived['reviews']['play_002']['shooter_id'],'a_1')
        self.assertAlmostEqual(derived['reviews']['play_001']['release_clip_s']+133,145.2)
        self.assertAlmostEqual(derived['reviews']['play_002']['release_clip_s']+130,140.533333)
        self.assertEqual(derived['reviews']['play_002']['notes'],'two events')
        self.assertEqual(MODULE.validate_review(derived,self.manifest,'manifest')['conflicts'],[])

    def test_unconfirmed_or_unbound_resolution_rejected(self):
        resolutions=self.swapped_packet()
        resolutions['actions'][0]['status']='pending_user'
        with self.assertRaises(ValueError):MODULE.apply_resolutions(self.review,self.manifest,resolutions,'raw','manifest')
        resolutions['actions'][0]['status']='confirmed_by_user'
        with self.assertRaises(ValueError):MODULE.apply_resolutions(self.review,self.manifest,resolutions,'another_raw','manifest')

    def test_annotation_transfer_outside_target_clip_rejected(self):
        resolutions=self.swapped_packet();self.manifest['entries'][1]['source_time_offset_s']=0
        with self.assertRaises(ValueError):MODULE.apply_resolutions(self.review,self.manifest,resolutions,'raw','manifest')

    def correction(self,clear=True):
        self.review['reviews']['play_001']['shooter_id']='a_1'
        return dict(schema_version='scoring-review-resolution-1',review_sha256='raw',manifest_sha256='manifest',
            confirmation_record='user corrected target actor and shot kind',actions=[
                dict(kind='correct_target_annotations',status='confirmed_by_user',target_event_id='play_001',
                     updates=dict(shooter_id='b_1',shot_kind='field_goal'),clear_unconfirmed_times=clear)])

    def test_correct_target_keeps_raw_and_drops_previous_opponent_times(self):
        resolutions=self.correction();before=copy.deepcopy(self.review)
        derived=MODULE.apply_resolutions(self.review,self.manifest,resolutions,'raw','manifest')
        self.assertEqual(self.review,before)
        self.assertEqual(derived['reviews']['play_001']['shooter_id'],'b_1')
        self.assertIsNone(derived['reviews']['play_001']['release_clip_s'])
        self.assertIsNone(derived['reviews']['play_001']['basket_clip_s'])
        result=MODULE.validate_review(derived,self.manifest,'manifest')
        self.assertEqual(result['conflicts'],[])
        self.assertEqual(result['diagnostic_windows'],[])

    def test_correct_target_cannot_keep_unconfirmed_opponent_times(self):
        with self.assertRaises(ValueError):
            MODULE.apply_resolutions(self.review,self.manifest,self.correction(False),'raw','manifest')

    def test_correction_cannot_invent_timestamps_or_unapproved_actor(self):
        resolutions=self.correction();resolutions['actions'][0]['updates']['release_clip_s']=9.
        with self.assertRaises(ValueError):MODULE.apply_resolutions(self.review,self.manifest,resolutions,'raw','manifest')
        del resolutions['actions'][0]['updates']['release_clip_s']
        resolutions['actions'][0]['updates']['shooter_id']='invented'
        with self.assertRaises(ValueError):MODULE.apply_resolutions(self.review,self.manifest,resolutions,'raw','manifest')


if __name__=='__main__':unittest.main()
