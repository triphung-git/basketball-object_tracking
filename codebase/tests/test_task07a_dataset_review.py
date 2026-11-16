"""Protect source binding and prevent unreviewed proposals becoming train labels."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from basketball_scoreboard.dataset_review_validation import validate_pilot_review, audit_pilot_draft


class PilotReviewTests(unittest.TestCase):
    def setUp(self):
        self.source=dict(schema_version='task07a-pilot-labels-1',source_sha256='a'*64,source_group='fixture',samples=[
            dict(sample_id='p0',image='images/0000.jpg',image_sha256='b'*64,source_group='fixture',window_id='w',
                 parent_source_time_s=1.,raw_pts=30,time_base='1/30',original_wh=[100,100],boxes=None,review_status='unreviewed')])
        self.packet=copy.deepcopy(self.source);self.packet.update(review_status='approved',reviewer='fixture',label_policy_status='approved_by_reviewer')
        self.packet['samples'][0].update(review_status='approved',scene_status='play',ball_visibility='visible',boxes=[dict(class_name='ball',xyxy=[10,10,20,20])])

    def test_valid_labels_do_not_authorize_training(self):
        result=validate_pilot_review(self.packet,self.source)
        self.assertEqual(result['approved_images'],1);self.assertFalse(result['training_authorized'])

    def test_draft_source_rejected(self):
        with self.assertRaises(ValueError):validate_pilot_review(self.source,self.source)

    def test_null_boxes_cannot_become_negative(self):
        self.packet['samples'][0]['boxes']=None
        with self.assertRaises(ValueError):validate_pilot_review(self.packet,self.source)

    def test_source_path_and_hash_tampering_rejected(self):
        for key,value in [('image','../outside.jpg'),('image_sha256','c'*64),('parent_source_time_s',2.)]:
            packet=copy.deepcopy(self.packet);packet['samples'][0][key]=value
            with self.subTest(key=key):
                with self.assertRaises(ValueError):validate_pilot_review(packet,self.source)

    def test_invalid_box_and_visibility_rejected(self):
        for coords in [[10,10,101,20],[True,10,20,20],[10,10,float('nan'),20]]:
            packet=copy.deepcopy(self.packet);packet['samples'][0]['boxes'][0]['xyxy']=coords
            with self.subTest(coords=coords):
                with self.assertRaises(ValueError):validate_pilot_review(packet,self.source)
        self.packet['samples'][0]['ball_visibility']='not_visible'
        with self.assertRaises(ValueError):validate_pilot_review(self.packet,self.source)

    def test_missing_policy_or_all_skipped_cannot_pass(self):
        packet=copy.deepcopy(self.packet);packet.pop('label_policy_status')
        with self.assertRaises(ValueError):validate_pilot_review(packet,self.source)
        self.packet['samples'][0].update(review_status='skipped',skip_reason='uncertain fixture')
        with self.assertRaises(ValueError):validate_pilot_review(self.packet,self.source)

    def test_partial_draft_keeps_unreviewed_out_of_counts(self):
        packet=copy.deepcopy(self.packet);packet['review_status']='draft';packet['reviewer']=None
        result=audit_pilot_draft(packet,self.source)
        self.assertEqual(result['approved_sample_ids'],['p0'])
        self.assertFalse(result['packet_approved']);self.assertFalse(result['training_authorized'])
        result=audit_pilot_draft(self.source,self.source)
        self.assertEqual(result['approved_sample_ids'],[])
        self.assertEqual(result['unreviewed_sample_ids'],['p0'])

    def test_draft_with_edited_labels_or_source_is_rejected(self):
        packet=copy.deepcopy(self.packet);packet['samples'][0]['boxes'][0]['xyxy'][2]=101
        with self.assertRaises(ValueError):audit_pilot_draft(packet,self.source)
        packet=copy.deepcopy(self.packet);packet['samples'][0]['split']='test'
        with self.assertRaises(ValueError):audit_pilot_draft(packet,self.source)

    def test_multiple_real_balls_flagged_without_deleting_labels(self):
        packet=copy.deepcopy(self.packet)
        packet['samples'][0]['boxes'].append(dict(class_name='ball',xyxy=[30,30,40,40]))
        result=audit_pilot_draft(packet,self.source)
        self.assertEqual(result['multiple_ball_sample_ids'],['p0'])
        self.assertEqual(len(packet['samples'][0]['boxes']),2)


if __name__=='__main__':unittest.main()
