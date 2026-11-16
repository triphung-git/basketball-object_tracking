"""Regressions for background ball rejection and conservative OCR consensus."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from basketball_scoreboard.ball import BallTracker,BallConfig
from basketball_scoreboard.identity import IdentityResolver,JerseyEvidenceRecord,RosterConfig
from basketball_scoreboard.tracking_policy import load_ball_roi,validate_image_polygon,in_image_roi


def detection(x,y,score=.9):
    return dict(class_name='ball',xyxy=[x-5,y-5,x+5,y+5],confidence=score)


class SpatialReliabilityTests(unittest.TestCase):
    def test_outside_ball_rejected_without_changing_original_evidence_index(self):
        roi=[[0,.2],[1,.2],[1,1],[0,1]]
        row=BallTracker((1000,500),'roi').update(0,0,[detection(800,30,.99),detection(400,250,.6)],ball_roi=roi)
        self.assertEqual(row['center_image'],[400,250])
        self.assertEqual(row['evidence_refs'],['detection:0:1'])
        self.assertEqual(row['spatially_rejected_candidates'],1)

    def test_aerial_ball_roi_is_separate_from_player_footpoint_roi(self):
        floor=dict(image_roi_normalized=[[0,.5],[1,.5],[1,1],[0,1]])
        self.assertFalse(in_image_roi(floor,(400,150),(1000,500)))
        aerial=[[0,.1],[.6,.1],[1,.5],[1,1],[0,1]]
        row=BallTracker((1000,500),'roi').update(0,0,[detection(400,150)],ball_roi=aerial)
        self.assertEqual(row['sample_type'],'observed')

    def test_prediction_cannot_be_drawn_outside_ball_search_region(self):
        tracker=BallTracker((1000,500),'roi',BallConfig(velocity_smoothing=1))
        roi=[[0,0],[.5,0],[.5,1],[0,1]]
        tracker.update(0,0,[detection(450,250)],ball_roi=roi)
        tracker.update(1,.1,[detection(480,250)],ball_roi=roi)
        self.assertEqual(tracker.update(2,.2,[],ball_roi=roi)['sample_type'],'missing')

    def test_policy_for_other_video_is_rejected(self):
        with patch('basketball_scoreboard.tracking_policy.Path.read_text',return_value=json.dumps(dict(source_video_sha256='a'*64))):
            with self.assertRaises(ValueError):load_ball_roi('fixture','b'*64)

    def test_invalid_polygons_are_rejected(self):
        for roi in ([],[[0,0],[1,1],[.5,.5]],[[0,0],[1,0],[1,float('nan')]],[[False,0],[1,0],[1,1]]):
            with self.subTest(roi=roi):
                with self.assertRaises(ValueError):validate_image_polygon(roi)

    def resolver(self):
        roster=RosterConfig.from_dict(dict(team_a_id='a',team_b_id='b',
            team_a_color_rgb=[200,0,0],team_b_color_rgb=[255,255,255],
            players=[dict(player_id='a1',team_id='a',jersey_number='1',name='fixture1'),
                     dict(player_id='a6',team_id='a',jersey_number='6',name='fixture6')]))
        return IdentityResolver(roster)

    def test_impossible_number_cannot_outvote_supported_roster_number(self):
        resolver=self.resolver()
        for i in range(9):
            resolver.add_jersey_evidence(JerseyEvidenceRecord(str(i),'track',i,i*.1,'99' if i<6 else '6',1.))
        self.assertEqual(resolver.resolve_player('track','a')[0],'a6')

    def test_similarly_supported_roster_numbers_remain_unknown(self):
        resolver=self.resolver()
        for i in range(6):
            resolver.add_jersey_evidence(JerseyEvidenceRecord(str(i),'track',i,i*.1,'1' if i<3 else '6',1.))
        player,_,reason=resolver.resolve_player('track','a')
        self.assertIsNone(player)
        self.assertIn('Ambiguous',reason)


if __name__=='__main__':unittest.main()
