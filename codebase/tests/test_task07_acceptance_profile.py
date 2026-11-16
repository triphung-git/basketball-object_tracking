"""Acceptance cannot pass from empty samples, synthetic GT or integrity errors."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from basketball_scoreboard.possession_evaluation import apply_acceptance_profile


class AcceptanceProfileTests(unittest.TestCase):
    def setUp(self):
        self.profile=dict(review_status='approved',approved_by='user',protocol_version='fixture',allowed_video_sha256=['a'*64],
             minimum_visible_ball_samples=60,minimum_completed_pass_gt=5,ball_recall_min=.9,control_accuracy_min=.9,
             pass_precision_min=.95,pass_recall_min=.9,max_pts_error_s=2e-6,ball_iou_threshold=.3,pass_tolerance_s=.25)
        self.packet=dict(is_synthetic=False,review_status='approved',reviewer='unit-test-fixture',protocol_version='fixture',
                         ball_iou_threshold=.3,pass_tolerance_s=.25)
        self.run=dict(source_fingerprint_sha256='a'*64,video_export=dict(max_pts_error_s=0),exclusions=[])
        self.metrics=dict(ball=dict(eligible_samples=60,recall=1.),control=dict(eligible_seconds=10.,strict_accuracy=1.),
                          passes_strict=dict(tp=5,fp=0,fn=0,precision=1.,recall=1.))
        self.result=dict(balls=[dict(frame_index=0,sample_type='observed')],controls=[dict(frame_index=0,certainty='confirmed')],
                         passes=[dict(outcome='completed',release_time_s=.2,confirmed_at_s=.5)])

    def check(self):
        return apply_acceptance_profile(copy.deepcopy(self.metrics),self.profile,self.run,self.packet,self.result)

    def test_approved_source_bound_fixture_meets_profile(self):
        result=self.check();self.assertTrue(result['acceptance_pass'])
        self.assertEqual(result['acceptance_status'],'passed_pilot')

    def test_small_sample_never_passes_despite_perfect_ratios(self):
        self.metrics['passes_strict']['tp']=4
        self.assertEqual(self.check()['acceptance_status'],'insufficient_samples')
        self.assertFalse(self.check()['acceptance_pass'])

    def test_na_metric_does_not_become_one_hundred_percent(self):
        self.metrics['passes_strict']['precision']=None
        self.assertFalse(self.check()['acceptance_pass'])

    def test_unapproved_or_synthetic_gt_cannot_use_real_acceptance(self):
        self.packet['is_synthetic']=True
        with self.assertRaises(ValueError):self.check()
        self.packet['is_synthetic']=False;self.packet['review_status']='draft'
        with self.assertRaises(ValueError):self.check()

    def test_wrong_match_source_cannot_use_profile(self):
        self.run['source_fingerprint_sha256']='b'*64
        with self.assertRaises(ValueError):self.check()

    def test_matching_rules_cannot_be_relaxed_in_gt_packet(self):
        for key,value in (('ball_iou_threshold',.01),('pass_tolerance_s',2.)):
            with self.subTest(key=key):
                packet=self.packet.copy();self.packet[key]=value
                with self.assertRaises(ValueError):self.check()
                self.packet=packet

    def test_missing_matching_rules_cannot_silently_pass(self):
        del self.packet['ball_iou_threshold']
        with self.assertRaises(ValueError):self.check()

    def test_prediction_only_control_and_cut_crossing_fail_integrity(self):
        self.result['balls'][0]['sample_type']='predicted'
        self.run['exclusions']=[dict(start_time_s=.3,end_time_s=.4)]
        result=self.check()
        self.assertFalse(result['acceptance_pass'])
        self.assertEqual(result['integrity']['prediction_only_control_frames'],1)
        self.assertEqual(result['integrity']['completed_passes_crossing_cut'],1)


if __name__=='__main__':unittest.main()
