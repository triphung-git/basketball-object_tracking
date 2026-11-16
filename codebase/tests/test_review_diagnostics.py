"""Keep diagnostic denominators honest and predictions independent of labels."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from basketball_scoreboard.review_diagnostics import ball_proposal_diagnostics, identity_proposal_diagnostics


class ReviewDiagnosticsTests(unittest.TestCase):
    def test_missing_OCR_counts_as_error_and_wrong_crop_is_separate(self):
        row=dict(sample_id='one',review_status='reviewed',source_binding=dict(track_id='t'),
                 labels=dict(crop_assessment='correct',role_review='player',jersey_visibility='readable',actual_number='2',actual_team_id='team_a'),
                 predictions=dict(team_id='team_b',ocr_readings=[]))
        wrong=copy.deepcopy(row);wrong['sample_id']='two';wrong['labels']['crop_assessment']='wrong_region'
        result=identity_proposal_diagnostics(dict(identities=[row,wrong]))
        self.assertEqual(result['readable_OCR']['eligible'],1)
        self.assertEqual(result['readable_OCR']['strict_accuracy'],0)
        self.assertEqual(result['readable_OCR']['coverage'],0)
        self.assertEqual(result['crop_assessment_counts']['wrong_region'],1)

    def test_top_candidate_is_selected_without_consulting_actual_number(self):
        row=dict(sample_id='one',review_status='reviewed',source_binding=dict(track_id='t'),
                 labels=dict(crop_assessment='correct',role_review='player',jersey_visibility='readable',actual_number='1',actual_team_id='team_a'),
                 predictions=dict(team_id='team_a',ocr_readings=[dict(detected_number='0',confidence=.9,is_valid=True),dict(detected_number='1',confidence=.8,is_valid=True)]))
        result=identity_proposal_diagnostics(dict(identities=[row]))
        self.assertEqual(result['readable_OCR']['correct'],0)
        self.assertTrue(result['rows'][0]['OCR_any_candidate_exact'])

    def test_uncertain_frame_is_neither_negative_nor_recall_sample(self):
        row=dict(sample_id='one',review_status='needs_review',prediction=dict(raw_candidates=[]))
        result=ball_proposal_diagnostics(dict(frames=[row]))
        self.assertEqual(result['eligible_frames'],0)
        self.assertIsNone(result['raw']['precision']);self.assertIsNone(result['raw']['recall'])


if __name__=='__main__':unittest.main()
