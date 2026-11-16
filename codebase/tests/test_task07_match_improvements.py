"""Regressions for real-match threshold forwarding, crop/TTL/ROI and tiling."""
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock

import numpy as np

ROOT=Path(__file__).parents[1]
sys.path.insert(0,str(ROOT/'src'))
from basketball_scoreboard.config import ModelConfig
from basketball_scoreboard.contracts import DetectionRecord
from basketball_scoreboard.detector import ObjectDetector
from basketball_scoreboard.identity import LocalEasyOCRProvider,IdentityResolver,JerseyEvidenceRecord,RosterConfig,extract_jersey_rgb
from basketball_scoreboard.tiled_detection import TiledBallDetector,tile_boxes
from basketball_scoreboard.tracking_policy import interval_flags,in_image_roi,normalize_interval
from basketball_scoreboard.possession import PossessionEngine,PossessionConfig
from basketball_scoreboard.ball import BallTracker,BallConfig
from test_task07_ball_possession import ball,people


class MatchImprovementTests(unittest.TestCase):
    def test_masked_color_finds_white_shirt_among_skin_pixels(self):
        crop=np.zeros((20,20,3),dtype=np.uint8)
        crop[:]=(110,150,190)
        crop[:8]=(225,225,225)
        rgb,quality=extract_jersey_rgb(crop,[(180,35,45),(220,220,225)])
        self.assertEqual(rgb,(225.,225.,225.))
        self.assertEqual(quality['fractions'],[0.,.4])

    def test_masked_color_rejects_gray_and_equal_team_evidence(self):
        prototypes=[(180,35,45),(220,220,225)]
        crop=np.full((20,20,3),150,dtype=np.uint8)
        self.assertIsNone(extract_jersey_rgb(crop,prototypes)[0])
        crop[:10]=(45,35,180);crop[10:]=(225,225,225)
        self.assertIsNone(extract_jersey_rgb(crop,prototypes)[0])

    def test_masked_color_preserves_red_prototype(self):
        crop=np.zeros((20,20,3),dtype=np.uint8);crop[:]=(45,35,180)
        self.assertEqual(extract_jersey_rgb(crop,[(180,35,45),(220,220,225)])[0],(180.,35.,45.))

    def test_configured_threshold_reaches_sdk_before_filtering(self):
        detector=ObjectDetector.__new__(ObjectDetector)
        detector.config=ModelConfig(confidence_threshold=.15,max_edge=1280)
        detector.class_mapping={0:'ball',1:'human',2:'rim'}
        prediction=SimpleNamespace(to_supervision=lambda:SimpleNamespace(
            xyxy=np.array([[10,10,20,20]]),class_id=np.array([0]),confidence=np.array([.2])))
        detector.model=Mock(return_value=[prediction])
        rows,_=detector.detect(np.zeros((100,100,3),dtype=np.uint8))
        self.assertEqual(detector.model.call_args.kwargs,{'confidence':.15})
        self.assertEqual(len(rows),1)

    def test_player_context_rejects_high_confidence_background_ball_seed(self):
        tracker=BallTracker((1000,500),'context',BallConfig(human_context_weight=.5,max_initial_body_distance=.75))
        dets=[dict(class_name='ball',confidence=.99,xyxy=[795,15,805,25]),
              dict(class_name='ball',confidence=.6,xyxy=[95,165,105,175])]
        row=tracker.update(0,0,dets,human_boxes=[[50,100,150,300]])
        self.assertEqual(row['center_image'],[100,170])

    def test_context_mode_does_not_seed_without_observed_players(self):
        tracker=BallTracker((1000,500),'context',BallConfig(human_context_weight=.5))
        row=tracker.update(0,0,[dict(class_name='ball',confidence=.99,xyxy=[95,165,105,175])])
        self.assertEqual(row['sample_type'],'missing')

    def test_tile_coordinates_cover_image_and_overlap(self):
        boxes=tile_boxes(1920,1080)
        self.assertEqual(len(boxes),4)
        self.assertEqual(min(x[0] for x in boxes),0)
        self.assertEqual(max(x[2] for x in boxes),1920)
        self.assertEqual(max(x[3] for x in boxes),1080)
        with self.assertRaises(ValueError):tile_boxes(100,100,True)
        with self.assertRaises(ValueError):tile_boxes(100,100,2,.8)

    def test_tiles_keep_full_frame_humans_and_remap_ball_boxes(self):
        mapping={0:'ball',1:'human',2:'rim'}
        class Base:
            class_mapping=mapping
            def detect(self,image,threshold):
                h,w=image.shape[:2]
                if w==100:return [DetectionRecord([0,0,40,90],1,'human',.9)],1.
                return [DetectionRecord([5,5,15,15],0,'ball',.9)],1.
        model=TiledBallDetector.__new__(TiledBallDetector)
        model.base=Base();model.grid=2;model.overlap=0;model.excluded_boxes=[];model.tile_scale=1.
        rows,ms=model.detect(np.zeros((100,100,3),dtype=np.uint8),.15)
        self.assertEqual(ms,5.)
        self.assertEqual(sum(r.class_name=='human' for r in rows),1)
        self.assertIn([55.,55.,65.,65.],[r.xyxy for r in rows if r.class_name=='ball'])
        for row in rows:row.validate_bounds((100,100))

    def test_upscaled_tiles_map_ball_coordinates_back_to_source(self):
        mapping={0:'ball',1:'human',2:'rim'}
        class Base:
            class_mapping=mapping
            def __init__(self):self.calls=0
            def detect(self,image,threshold):
                self.calls+=1
                if self.calls==1:return [],1.
                return [DetectionRecord([10,10,20,20],0,'ball',.9)],1.
        model=TiledBallDetector.__new__(TiledBallDetector)
        model.base=Base();model.grid=2;model.overlap=0;model.excluded_boxes=[];model.tile_scale=2.
        rows,ms=model.detect(np.zeros((100,100,3),dtype=np.uint8),.15)
        self.assertEqual(ms,5.)
        self.assertEqual([row.xyxy for row in rows],[
            [5.,5.,10.,10.],[5.,55.,10.,60.],[55.,5.,60.,10.],[55.,55.,60.,60.]])
        for row in rows:row.validate_bounds((100,100))

    def test_upscaled_tile_scale_is_bounded_before_model_load(self):
        with self.assertRaises(ValueError):
            TiledBallDetector(ModelConfig(),tile_scale=0.5)
        with self.assertRaises(ValueError):
            TiledBallDetector(ModelConfig(),tile_scale=4.1)

    def test_same_frame_ocr_duplicate_is_one_vote_and_crop_upscaled(self):
        provider=LocalEasyOCRProvider.__new__(LocalEasyOCRProvider)
        provider.confidence_threshold=.5;provider.crop_upscale=3
        provider.stats=dict(attempts=0,rejected_crops=0,runtime_errors=0)
        provider._reader=SimpleNamespace(readtext=Mock(return_value=[([], '13',.8),([], '13',.9),([], '1',float('nan'))]))
        pattern=(np.indices((30,20)).sum(axis=0)%2*200).astype(np.uint8)
        crop=np.repeat(pattern[:,:,None],3,axis=2)
        records=provider.read_jersey(crop,'track',1,.1)
        self.assertEqual([(x.detected_number,x.confidence) for x in records],[('13',.9)])
        self.assertEqual(provider._reader.readtext.call_args.args[0].shape[:2],(90,60))

    def test_ocr_errors_are_observable(self):
        provider=LocalEasyOCRProvider.__new__(LocalEasyOCRProvider)
        provider.confidence_threshold=.5;provider.crop_upscale=1
        provider.stats=dict(attempts=0,rejected_crops=0,runtime_errors=0)
        provider._reader=SimpleNamespace(readtext=Mock(side_effect=RuntimeError('fixture')))
        crop=np.random.default_rng(1).integers(0,255,(40,40,3),dtype=np.uint8)
        self.assertEqual(provider.read_jersey(crop,'track',1,.1),[])
        self.assertEqual(provider.stats['runtime_errors'],1)

    def test_jersey_ttl_does_not_extend_stale_team_evidence(self):
        roster=RosterConfig.from_dict(dict(team_a_id='r',team_b_id='w',team_a_color_rgb=[200,20,20],team_b_color_rgb=[220,220,220],
             players=[dict(player_id='r13',team_id='r',jersey_number='13',name='fixture')]))
        resolver=IdentityResolver(roster,confirmation_hits_threshold=1,evidence_ttl_s=2,jersey_evidence_ttl_s=6)
        resolver.add_team_observation('a','r',1.,0.)
        resolver.add_jersey_evidence(JerseyEvidenceRecord('j','a',0,0.,'13',1.))
        self.assertEqual(resolver.update_track_mapping('a',0.).player_id,'r13')
        self.assertIsNone(resolver.update_track_mapping('a',3.).team_id)
        resolver.add_team_observation('a','r',1.,3.1)
        self.assertEqual(resolver.update_track_mapping('a',3.1).player_id,'r13')
        resolver.add_team_observation('a','r',1.,7.)
        self.assertIsNone(resolver.update_track_mapping('a',7.).player_id)

    def test_policy_cut_boundaries_and_image_only_roi(self):
        policy={'image_roi_normalized':[[0,.5],[1,.5],[1,1],[0,1]],
                'intervals':[dict(start_time_s=1.,end_time_s=2.,reason='closeup')]}
        self.assertFalse(in_image_roi(policy,(50,20),(100,100)))
        self.assertTrue(in_image_roi(policy,(50,80),(100,100)))
        self.assertEqual(interval_flags(policy,.9,1.),(True,True))
        self.assertEqual(interval_flags(policy,1.9,2.),(False,True))

    def test_cut_boundary_quantization_excludes_first_new_scene_frame(self):
        interval=dict(start_time_s=856/30,end_time_s=30.,reason='closeup')
        self.assertEqual(interval_flags({'intervals':[interval]},28.5,28.533333),(True,True))
        normalized=normalize_interval(interval)
        self.assertEqual(normalize_interval(normalized),normalized)
        point=normalize_interval(dict(start_time_s=856/30,end_time_s=856/30,reason='cut'))
        self.assertEqual(point['start_time_s'],point['end_time_s'])

    def test_observed_dribble_requires_multiple_real_samples(self):
        engine=PossessionEngine('dribble')
        for i in range(3):engine.update(ball(i),people(i*.1))
        first=engine.update(ball(3,y=295),people(.3))
        self.assertEqual(first['certainty'],'provisional')
        second=engine.update(ball(4,y=270),people(.4))
        self.assertEqual(second['phase'],'observed_dribble')
        self.assertEqual(second['certainty'],'confirmed')
        missing=engine.update(ball(5,y=270,sample='predicted'),people(.5))
        self.assertIsNone(missing['controller'])

    def test_short_gap_keeps_hypothesis_but_never_confirms_from_prediction(self):
        engine=PossessionEngine('short',PossessionConfig(max_unobserved_gap_s=.15))
        for i in range(3):engine.update(ball(i),people(i*.1))
        engine.update(ball(3,x=240),people(.3))
        engine.update(ball(4,x=340),people(.4))
        row=engine.update(ball(5,x=440,sample='predicted'),people(.5))
        self.assertIsNone(row['controller'])
        self.assertFalse(engine.passes)
        for i in (6,7,8):engine.update(ball(i,x=550),people(i*.1))
        self.assertFalse(any(p['outcome']=='completed' for p in engine.passes))

    def test_bounded_missing_frame_with_observed_flight_evidence_can_complete(self):
        engine=PossessionEngine('short',PossessionConfig(max_unobserved_gap_s=.21))
        for i in range(3):engine.update(ball(i),people(i*.1))
        engine.update(ball(3,x=240),people(.3))
        engine.update(ball(4,x=340),people(.4))
        engine.update(ball(5,x=400,sample='predicted'),people(.5))
        for i in (6,7,8):engine.update(ball(i,x=550),people(i*.1))
        self.assertEqual(engine.passes[-1]['outcome'],'completed')
        self.assertGreaterEqual(engine.passes[-1]['observed_flight_samples'],2)
        self.assertEqual(engine.passes[-1]['unobserved_gap_samples'],1)


if __name__=='__main__':unittest.main()
