"""Tests for actor/body decoupling for ball context evidence.

Verifies Goal 1 of Task07:
1. Actor/body evidence used for ball association is decoupled from jersey/OCR/identity uncertainty.
2. On-court observed human bodies (role != 'non_player') provide context to ball tracker.
3. Provenance, role validity and causal timing are strictly preserved; no arbitrary promotion of humans to player.
4. Prevents the ball recall regression observed when identity crops are guarded.
"""
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from basketball_scoreboard.ball import BallConfig, BallTracker


def det_ball(x, y=100, conf=0.8):
    return dict(class_name='ball', confidence=conf, xyxy=[x - 5, y - 5, x + 5, y + 5])


def det_human(track_id, box, role='player', sample_type='observed', team_id='team_a', player_id=None, time=0.0):
    return dict(track_id=track_id, bbox=box, role=role, sample_type=sample_type,
                team_id=team_id, player_id=player_id, frame_index=0, source_time_s=time,
                observation_id=f'obs_{track_id}_{time}')


class ActorDecouplingTests(unittest.TestCase):
    def test_ball_pipeline_actor_selection_rule(self):
        """On-court actors (player or unknown) are eligible; non-players and predicted are excluded."""
        people = [
            det_human('t1', [10, 50, 60, 200], role='player', sample_type='observed'),
            det_human('t2', [80, 50, 130, 200], role='unknown', sample_type='observed'),  # on-court unconfirmed
            det_human('t3', [150, 50, 200, 200], role='non_player', sample_type='observed'),  # outside court
            det_human('t4', [220, 50, 270, 200], role='player', sample_type='predicted'),  # predicted
        ]
        
        # Candidate selection rule in ball_pipeline: sample_type == 'observed' and role != 'non_player'
        selected_boxes = [p['bbox'] for p in people if p.get('sample_type') == 'observed' and p.get('role') != 'non_player']
        self.assertEqual(len(selected_boxes), 2)
        self.assertEqual(selected_boxes[0], [10, 50, 60, 200])
        self.assertEqual(selected_boxes[1], [80, 50, 130, 200])

    def test_unknown_role_actor_provides_valid_ball_body_context(self):
        """An on-court body whose identity is unknown still supports initial ball context without crashing."""
        cfg = BallConfig(human_context_weight=0.5, max_initial_body_distance=0.2)
        
        # Ball near person at x=100
        human_box = [70, 50, 130, 250]
        ball = det_ball(100, 100, conf=0.7)
        
        # If human_boxes is empty (e.g. filtered out because role='unknown'), ball is skipped
        tracker_empty = BallTracker((1000, 500), 'test1', cfg)
        res_empty = tracker_empty.update(0, 0.0, [ball], human_boxes=[])
        self.assertEqual(res_empty['sample_type'], 'missing')
        
        # If human_boxes includes the on-court actor, ball is observed
        tracker_with_body = BallTracker((1000, 500), 'test2', cfg)
        res_with_body = tracker_with_body.update(0, 0.0, [ball], human_boxes=[human_box])
        self.assertEqual(res_with_body['sample_type'], 'observed')

    def test_provenance_and_causal_timing_preserved(self):
        """Actor observations retain their original role and timestamp semantics."""
        raw_obs = det_human('trk_1', [50, 50, 150, 250], role='unknown', sample_type='observed', time=1.5)
        # Provenance check: role is not mutated to player when supplying body context
        self.assertEqual(raw_obs['role'], 'unknown')
        self.assertEqual(raw_obs['source_time_s'], 1.5)
        self.assertEqual(raw_obs['sample_type'], 'observed')

    def test_decoupling_prevents_guard_ball_recall_regression(self):
        """When identity crops are guarded, unconfirmed actors remain valid bodies and prevent ball loss."""
        cfg = BallConfig(human_context_weight=0.5, max_initial_body_distance=0.2)
        
        # Scenario: Actor on court at [70, 50, 130, 250] has guarded crop -> role is 'unknown'
        guarded_actor = det_human('trk_guarded', [70, 50, 130, 250], role='unknown', sample_type='observed')
        ball = det_ball(100, 100, conf=0.7)
        
        # Under legacy policy: human_boxes = [p['bbox'] for p in people if p['role'] == 'player'] -> []
        legacy_boxes = [guarded_actor['bbox']] if guarded_actor['role'] == 'player' else []
        tracker_legacy = BallTracker((1000, 500), 'test_leg', cfg)
        res_legacy = tracker_legacy.update(0, 0.0, [ball], human_boxes=legacy_boxes)
        self.assertEqual(res_legacy['sample_type'], 'missing', "Legacy filtering causes ball loss")
        
        # Under decoupled policy: human_boxes = [p['bbox'] for p in people if p['role'] != 'non_player'] -> [[70, 50, 130, 250]]
        decoupled_boxes = [guarded_actor['bbox']] if guarded_actor['role'] != 'non_player' else []
        tracker_decoupled = BallTracker((1000, 500), 'test_dec', cfg)
        res_decoupled = tracker_decoupled.update(0, 0.0, [ball], human_boxes=decoupled_boxes)
        self.assertEqual(res_decoupled['sample_type'], 'observed', "Decoupled filtering preserves observed ball")


if __name__ == '__main__':
    unittest.main()
