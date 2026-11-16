"""Actor support must rank real candidates without hallucination or identity GT."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from basketball_scoreboard.ball import BallConfig, BallTracker
from basketball_scoreboard.ball_actor_context import actor_anchor, current_players


def detection(x, y=150, confidence=.7):
    return dict(class_name='ball', confidence=confidence, xyxy=[x-5, y-5, x+5, y+5])


def person(frame, time, x=50, **kwargs):
    return dict(track_id='a', sample_type='observed', role='player', frame_index=frame,
                source_time_s=time, bbox=[x, 50, x+100, 250], **kwargs)


class ActorContextTests(unittest.TestCase):
    def tracker(self, weight=.6):
        return BallTracker((1000, 500), 'test', BallConfig(actor_continuity_weight=weight))

    def initial(self, tracker):
        return tracker.update(0, 0., [detection(100)], human_observations=[person(0, 0.)])

    def test_actor_motion_can_resolve_confidence_distraction(self):
        tracker = self.tracker(); self.initial(tracker)
        row = tracker.update(1, .1, [detection(100, confidence=.99), detection(170, confidence=.65)],
                             human_observations=[person(1, .1, x=120)])
        self.assertEqual(row['center_image'], [170, 150])
        self.assertEqual(row['sample_type'], 'observed')
        self.assertEqual(len(row['evidence_refs']), 1)

    def test_disabled_option_keeps_existing_ranking(self):
        tracker = self.tracker(0); self.initial(tracker)
        row = tracker.update(1, .1, [detection(100, confidence=.99), detection(170, confidence=.65)],
                             human_observations=[person(1, .1, x=120)])
        self.assertEqual(row['center_image'], [100, 150])

    def test_no_detection_never_creates_observed_ball(self):
        tracker = self.tracker(); self.initial(tracker)
        row = tracker.update(1, .1, [], human_observations=[person(1, .1, x=120)])
        self.assertEqual(row['sample_type'], 'predicted')
        self.assertIsNone(row['xyxy']); self.assertEqual(row['evidence_refs'], [])

    def test_stale_unknown_predicted_duplicate_or_changed_track_is_ignored(self):
        for change in [dict(source_time_s=0.), dict(frame_index=0), dict(role='unknown'),
                       dict(sample_type='predicted'), dict(track_id='new')]:
            tracker = self.tracker(); self.initial(tracker)
            p = person(1, .1, x=120); p.update(change)
            row = tracker.update(1, .1, [detection(100, confidence=.99), detection(170, confidence=.65)],
                                 human_observations=[p])
            self.assertEqual(row['center_image'], [100, 150])
        p = person(1, .1)
        self.assertEqual(current_players([p, p], 1, .1), {})

    def test_flight_is_not_forced_back_to_actor(self):
        tracker = self.tracker(); self.initial(tracker)
        row = tracker.update(1, .1, [detection(300, y=60)], human_observations=[person(1, .1)])
        self.assertEqual(row['sample_type'], 'observed')
        self.assertIsNone(tracker.active['actor_anchor'])

    def test_roi_cannot_be_overridden_by_actor(self):
        tracker = self.tracker(); self.initial(tracker)
        row = tracker.update(1, .1, [detection(170)], human_observations=[person(1, .1, x=120)],
                             ball_roi=[[.5, 0], [1, 0], [1, 1], [.5, 1]])
        self.assertEqual(row['sample_type'], 'missing')

    def test_cut_and_gap_drop_anchor(self):
        for time, reset in [(.1, True), (.5, False)]:
            tracker = self.tracker(); self.initial(tracker)
            row = tracker.update(1, time, [detection(100, confidence=.99), detection(170, confidence=.65)],
                                 reset=reset, human_observations=[person(1, time, x=120)])
            self.assertEqual(row['center_image'], [100, 150])

    def test_contested_nearby_players_do_not_anchor(self):
        self.assertIsNone(actor_anchor([95, 145, 105, 155], {'a': [50, 50, 150, 250], 'b': [55, 50, 155, 250]}))

    def test_invalid_weight_and_gate(self):
        for kwargs in [dict(actor_continuity_weight=1.1), dict(actor_continuity_weight=True),
                       dict(actor_continuity_gate_heights=0), dict(actor_continuity_gate_heights=float('nan'))]:
            with self.assertRaises(ValueError): BallConfig(**kwargs)


if __name__ == '__main__': unittest.main()
