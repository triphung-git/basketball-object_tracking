from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from basketball_scoreboard.identity_crops import IdentityCropGuard,IdentityCropPolicy
from basketball_scoreboard.identity import IdentityResolver,RosterConfig,RosterPlayer,JerseyEvidenceRecord,extract_jersey_rgb


class CropGuardTests(unittest.TestCase):
    def setUp(self):
        self.image=np.full((400,400,3),(30,30,180),np.uint8)
        self.image[::4,::4]=(30,30,240)
        self.obs=SimpleNamespace(track_id='t',source_time_s=0.,frame_index=0,bbox=[100,50,200,350],sample_type='observed',role='unknown')
        self.ds=[dict(class_name='human',xyxy=self.obs.bbox)]
        self.guard=IdentityCropGuard(IdentityCropPolicy(),[(180,30,30),(220,220,220)])

    def test_standing_player_and_duplicate_detection_allowed(self):
        self.ds.append(dict(class_name='human',xyxy=[101,51,201,351]))
        self.assertTrue(self.guard.assess(self.obs,self.image,self.ds)[2]['allowed'])

    def test_predicted_wrong_source_and_no_color_are_untrusted(self):
        self.obs.sample_type='predicted'
        self.assertEqual(self.guard.assess(self.obs,self.image,self.ds)[2]['reason'],'predicted_person')
        self.obs.sample_type='observed'
        self.assertFalse(self.guard.assess(self.obs,self.image,[])[2]['allowed'])
        image=np.full((400,400,3),90,np.uint8)
        self.assertEqual(self.guard.assess(self.obs,image,self.ds)[2]['reason'],'insufficient_jersey_color_support')

    def test_ambiguity_has_short_causal_hold_and_cut_reset(self):
        ds=self.ds+[dict(class_name='human',xyxy=[120,50,220,350])]
        self.assertEqual(self.guard.assess(self.obs,self.image,ds)[2]['reason'],'ambiguous_crop_ownership')
        self.obs.source_time_s=.5
        self.assertEqual(self.guard.assess(self.obs,self.image,self.ds)[2]['reason'],'recent_ownership_ambiguity')
        self.guard.reset()
        self.assertTrue(self.guard.assess(self.obs,self.image,self.ds)[2]['allowed'])

    def test_small_defender_overlap_does_not_always_reject_crossing(self):
        ds=self.ds+[dict(class_name='human',xyxy=[180,50,280,350])]
        self.assertTrue(self.guard.assess(self.obs,self.image,ds)[2]['allowed'])

    def test_mask_changes_only_crop_and_preserves_color_on_valid_pixels(self):
        guard=IdentityCropGuard(IdentityCropPolicy(excluded_boxes=[[0,.3,1,.6]]),[(180,30,30),(220,220,220)])
        original=self.image.copy();crop,rgb,info=guard.assess(self.obs,self.image,self.ds)
        self.assertTrue(info['mask_changed']);self.assertTrue(info['allowed'])
        self.assertTrue(np.array_equal(self.image,original));self.assertTrue(np.any(crop==127))
        self.assertEqual(tuple(map(round,rgb)),(180,30,30))

    def test_fully_masked_crop_rejected(self):
        guard=IdentityCropGuard(IdentityCropPolicy(excluded_boxes=[[0,0,1,1]]),[(180,30,30),(220,220,220)])
        self.assertFalse(guard.assess(self.obs,self.image,self.ds)[2]['allowed'])

    def test_recovery_requires_clear_current_pixels(self):
        guard=IdentityCropGuard(IdentityCropPolicy(recover_clear_crop=True),[(180,30,30),(220,220,220)])
        guard.assess(self.obs,self.image,self.ds+[dict(class_name='human',xyxy=[120,50,220,350])])
        self.obs.source_time_s=.5
        crop,rgb,info=guard.assess(self.obs,self.image,self.ds)
        self.assertTrue(info['allowed']);self.assertTrue(info['ownership_recovered_from_current_pixels'])

    def test_side_clipping_does_not_reject_only_clipped_feet(self):
        guard=IdentityCropGuard(IdentityCropPolicy(reject_side_clipped=True),[(180,30,30),(220,220,220)])
        self.obs.bbox=[100,50,200,400];self.ds[0]['xyxy']=self.obs.bbox
        self.assertTrue(guard.assess(self.obs,self.image,self.ds)[2]['allowed'])
        self.obs.bbox=[300,50,400,350];self.ds[0]['xyxy']=self.obs.bbox
        self.assertFalse(guard.assess(self.obs,self.image,self.ds)[2]['allowed'])

    def test_pixel_mask_excludes_broadcast_color_from_team_vote(self):
        image=self.image.copy();image[:300]=(230,230,230)
        valid=np.zeros((400,400),dtype=bool);valid[300:]=True
        rgb,_=extract_jersey_rgb(image,[(180,30,30),(220,220,220)],valid_mask=valid)
        self.assertEqual(tuple(map(round,rgb)),(180,30,30))

    def test_invalid_pixel_mask_is_unresolved(self):
        rgb,info=extract_jersey_rgb(self.image,[(180,30,30),(220,220,220)],valid_mask=np.zeros((2,2),dtype=bool))
        self.assertIsNone(rgb);self.assertEqual(info['reason'],'invalid_visible_pixel_mask')

    def test_invalidation_closes_identity_without_backfill(self):
        roster=RosterConfig('a','b','A','B',(180,30,30),(220,220,220),[RosterPlayer('p','a','1','P')])
        resolver=IdentityResolver(roster,confirmation_hits_threshold=1)
        resolver.add_team_observation('t','a',1.,0.)
        resolver.add_jersey_evidence(JerseyEvidenceRecord('e','t',0,0.,'1',1.,'fixture'))
        resolver.update_track_mapping('t',0.)
        resolver.update_track_mapping('t',.1)
        self.assertEqual(resolver.mapping_at('t',.05).player_id,'p')
        resolver.invalidate_track_evidence('t',.2,'ambiguous_crop')
        self.assertIsNone(resolver.mapping_at('t',.2).player_id)
        self.assertEqual(resolver.mapping_at('t',.05).player_id,'p')
        with self.assertRaises(ValueError):resolver.invalidate_track_evidence('t',.1,'backwards')

    def test_opponent_same_number_cannot_inherit_previous_jersey_evidence(self):
        roster=RosterConfig('a','b','A','B',(180,30,30),(220,220,220),[RosterPlayer('pa','a','1','A1'),RosterPlayer('pb','b','1','B1')])
        resolver=IdentityResolver(roster,confirmation_hits_threshold=1)
        resolver.add_team_observation('t','a',1.,0.)
        resolver.add_jersey_evidence(JerseyEvidenceRecord('e','t',0,0.,'1',1.,'fixture'))
        self.assertEqual(resolver.update_track_mapping('t',0.).player_id,'pa')
        resolver.invalidate_track_evidence('t',.1,'contradictory_observed_team')
        resolver.add_team_observation('t','b',1.,.1)
        current=resolver.update_track_mapping('t',.1)
        self.assertEqual(current.team_id,'b');self.assertIsNone(current.player_id)


if __name__=='__main__':unittest.main()
