"""Acceptance regressions independent of the implementation's happy-path fixtures."""
from dataclasses import replace
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from basketball_scoreboard.court import CourtConfig, CourtCoordinateSystem, CourtModel, TrajectoryObservation, UncalibratedCourtError
from basketball_scoreboard.heatmap import HeatmapAccumulator, ExclusionInterval
from basketball_scoreboard.identity import IdentityResolver, JerseyEvidenceRecord, RosterConfig, RosterPlayer, enrich_observations_with_identity
from basketball_scoreboard.players import PlayerTracker

BOUNDS = dict(x_min=0., x_max=10., y_min=0., y_max=10.)

def observation(t, **changes):
    values = dict(schema_version='2.0.1', observation_id=f'o{t}', source_run_id='run', video_id='video',
                  source_fingerprint_sha256='a'*64, frame_index=round(t*10), source_time_s=t,
                  timestamp_status='valid', segment_id='s', camera_id='c', bbox=[10.,10.,20.,20.],
                  footpoint_image=(15.,20.), projected_court_xy=(2.,2.), track_id='track', role='player',
                  calibration_version='cal1')
    values.update(changes)
    return TrajectoryObservation(**values)

def roster():
    return RosterConfig('A','B','A','B',(220,30,30),(30,60,220),
                        [RosterPlayer('a7','A','7','fixture'), RosterPlayer('b7','B','7','fixture')])

class HeatmapAcceptanceTests(unittest.TestCase):
    def test_prediction_never_contributes_even_if_projected(self):
        acc = HeatmapAccumulator(BOUNDS)
        self.assertFalse(acc.add_trajectory_interval('p',(2,2),0,1,sample_type='predicted'))
        self.assertEqual(acc.total_grid.sum(),0)

    def test_invalid_and_predicted_observations_break_continuity(self):
        for middle in (observation(.5, validity_status='occluded'), observation(.5,sample_type='predicted')):
            with self.subTest(middle=middle.sample_type):
                acc=HeatmapAccumulator(BOUNDS)
                acc.process_observations_batch([observation(0),middle,observation(1)])
                self.assertEqual(acc.total_grid.sum(),0)

    def test_non_players_are_excluded(self):
        acc=HeatmapAccumulator(BOUNDS)
        acc.process_observations_batch([observation(0,role='non_player'),observation(1,role='non_player')])
        self.assertEqual(acc.total_grid.sum(),0)

    def test_trackless_detections_are_not_one_person(self):
        acc=HeatmapAccumulator(BOUNDS)
        acc.process_observations_batch([observation(0,track_id=None),observation(1,track_id=None)])
        self.assertEqual(acc.total_grid.sum(),0)

    def test_video_and_calibration_changes_do_not_join_streams(self):
        for changes in ({'video_id':'another'}, {'source_run_id':'another'}, {'calibration_version':'cal2'}):
            with self.subTest(changes=changes):
                acc=HeatmapAccumulator(BOUNDS)
                acc.process_observations_batch([observation(0),observation(1,**changes)])
                self.assertEqual(acc.total_grid.sum(),0)

    def test_exclusions_use_union_not_double_subtraction(self):
        acc=HeatmapAccumulator(BOUNDS,exclusions=[ExclusionInterval(.1,.5),ExclusionInterval(.3,.7)])
        acc.add_trajectory_interval('x',(2,2),0,1)
        self.assertAlmostEqual(acc.total_grid.sum(),.4)
        self.assertAlmostEqual(acc.metadata.excluded_player_seconds,.6)

    def test_cut_does_not_carry_a_position_into_another_scene(self):
        acc=HeatmapAccumulator(BOUNDS,exclusions=[ExclusionInterval(.4,.8,'cut')])
        self.assertFalse(acc.add_trajectory_interval('x',(2,2),0,1))
        self.assertEqual(acc.total_grid.sum(),0)
        self.assertEqual(acc.metadata.cut_discarded_seconds,1)

    def test_skipped_intervals_and_batch_counters_are_idempotent(self):
        acc=HeatmapAccumulator(BOUNDS,max_gap_s=.5)
        batch=[observation(0),observation(1)]
        acc.process_observations_batch(batch)
        before=acc.metadata.to_dict()
        acc.process_observations_batch(batch)
        self.assertEqual(acc.metadata.to_dict(),before)

    def test_estimated_clock_is_not_silently_accepted(self):
        acc=HeatmapAccumulator(BOUNDS)
        self.assertFalse(acc.add_trajectory_interval('x',(2,2),0,1,timestamp_status='estimated'))

    def test_invalid_numeric_config_rejected(self):
        for values in ({'max_gap_s':float('nan')},{'grid_shape':(0,2)},{'timestamp_policy':'typo'}):
            with self.subTest(values=values),self.assertRaises(ValueError):
                HeatmapAccumulator(BOUNDS,**values)

class TrackerAcceptanceTests(unittest.TestCase):
    def test_expiry_happens_before_association(self):
        tracker=PlayerTracker('v',min_hits_to_activate=1,max_age_s=.5)
        det=[dict(class_name='human',xyxy=[100,100,150,200],confidence=.9)]
        first=tracker.update_frame(0,0,'valid',det)[0].track_id
        second=tracker.update_frame(1,2,'valid',det)[0].track_id
        self.assertNotEqual(first,second)

    def test_class_name_overrides_baseline_numeric_id(self):
        tracker=PlayerTracker('v')
        obs=tracker.update_frame(0,0,'valid',[dict(class_name='ball',class_id=1,xyxy=[10,10,20,20])])
        self.assertEqual(obs,[])

    def test_duplicate_detection_does_not_create_two_tracks(self):
        tracker=PlayerTracker('v')
        det=dict(class_name='human',xyxy=[100,100,150,200],confidence=.9)
        self.assertEqual(len(tracker.update_frame(0,0,'valid',[det,det])),1)

    def test_duplicate_or_backward_frame_rejected(self):
        for time in (0,-1):
            with self.subTest(time=time):
                tracker=PlayerTracker('v')
                tracker.update_frame(0,0,'valid',[])
                with self.assertRaises(ValueError):
                    tracker.update_frame(1,time,'valid',[])

    def test_roi_alone_does_not_prove_player_role(self):
        config=CourtConfig.from_json_file(str(Path(__file__).parents[1]/'configs/courts/synthetic_half_court.json'))
        model=CourtModel(config)
        model.calibrate(allow_uncalibrated=True)
        tracker=PlayerTracker('v',court_model=model)
        obs=tracker.update_frame(0,0,'valid',[dict(class_name='human',xyxy=[1000,2200,1100,2500])])
        self.assertEqual(obs[0].role,'unknown')

class IdentityAcceptanceTests(unittest.TestCase):
    def test_duplicate_evidence_cannot_confirm_identity(self):
        resolver=IdentityResolver(roster(),confirmation_hits_threshold=3)
        resolver.add_team_observation('t','A',1)
        for _ in range(4):
            resolver.add_jersey_evidence(JerseyEvidenceRecord('same','t',0,0,'7',1))
        self.assertIsNone(resolver.update_track_mapping('t',0).player_id)

    def test_old_evidence_expires(self):
        resolver=IdentityResolver(roster(),confirmation_hits_threshold=1)
        resolver.add_team_observation('t','A',1)
        resolver.add_jersey_evidence(JerseyEvidenceRecord('e','t',0,0,'7',1))
        self.assertEqual(resolver.update_track_mapping('t',0).player_id,'a7')
        late=resolver.update_track_mapping('t',30)
        self.assertIsNone(late.player_id)
        self.assertIsNone(late.team_id)
        self.assertIsNone(resolver.mapping_at('t',10), 'Sparse updates cannot extend stale evidence across the gap')

    def test_fresh_evidence_extends_only_its_own_valid_window(self):
        resolver=IdentityResolver(roster(),confirmation_hits_threshold=1)
        for time in (0,1,2,3):
            resolver.add_team_observation('t','A',1,time)
            resolver.add_jersey_evidence(JerseyEvidenceRecord(str(time),'t',time,time,'7',1))
            resolver.update_track_mapping('t',time)
        resolver.update_track_mapping('t',30)
        self.assertEqual(resolver.mapping_at('t',4).player_id,'a7')
        self.assertIsNone(resolver.mapping_at('t',6))

    def test_inactive_roster_player_is_not_resolved(self):
        config=roster()
        config.players[0].is_active=False
        self.assertIsNone(config.get_player('A','7'))

    def test_prior_mapping_snapshot_is_not_mutated(self):
        resolver=IdentityResolver(roster())
        first=resolver.update_track_mapping('t',0)
        snapshot=first.to_dict()
        resolver.update_track_mapping('t',1)
        self.assertEqual(first.to_dict(),snapshot)

    def test_confirmation_does_not_backfill_past_observations(self):
        resolver=IdentityResolver(roster(),confirmation_hits_threshold=1)
        resolver.update_track_mapping('t',0)
        resolver.add_team_observation('t','A',1)
        resolver.add_jersey_evidence(JerseyEvidenceRecord('e','t',10,1,'7',1))
        resolver.update_track_mapping('t',1)
        old=observation(.5,track_id='t')
        enrich_observations_with_identity([old],resolver)
        self.assertIsNone(old.player_id)

    def test_predicted_sample_is_not_confirmed_identity(self):
        resolver=IdentityResolver(roster(),confirmation_hits_threshold=1)
        resolver.add_team_observation('t','A',1)
        resolver.add_jersey_evidence(JerseyEvidenceRecord('e','t',0,0,'7',1))
        resolver.update_track_mapping('t',0)
        pred=observation(0,track_id='t',sample_type='predicted')
        enrich_observations_with_identity([pred],resolver)
        self.assertIsNone(pred.player_id)

    def test_stronger_duplicate_assignment_clears_the_other_track(self):
        resolver=IdentityResolver(roster(),confirmation_hits_threshold=1)
        for track,readings in [('first',1),('second',4)]:
            resolver.add_team_observation(track,'A',1)
            for i in range(readings):
                resolver.add_jersey_evidence(JerseyEvidenceRecord(track+str(i),track,0,0,'7',1))
            resolver.update_track_mapping(track,0,{'first','second'})
        self.assertEqual(sum(m.player_id=='a7' for m in resolver.current_mappings.values()),1)

class CourtAcceptanceTests(unittest.TestCase):
    def test_synthetic_config_requires_explicit_diagnostic_mode(self):
        config=CourtConfig.from_json_file(str(Path(__file__).parents[1]/'configs/courts/synthetic_half_court.json'))
        with self.assertRaises(UncalibratedCourtError):
            CourtModel(config).calibrate()

    def test_empty_roi_is_not_full_image(self):
        config=CourtConfig.from_json_file(str(Path(__file__).parents[1]/'configs/courts/synthetic_half_court.json'))
        config.court_roi_image=[]
        self.assertFalse(CourtModel(config).is_in_court_roi((500,500)))

    def test_nonfinite_court_bounds_rejected(self):
        with self.assertRaises(ValueError):
            CourtCoordinateSystem('origin',{},'normalized',dict(BOUNDS,x_max=float('nan')))

if __name__=='__main__':
    unittest.main()
