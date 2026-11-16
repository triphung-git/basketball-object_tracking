"""Temporal behavior regressions; fixture players/ball coordinates are synthetic."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]/"src"))
from basketball_scoreboard.ball import BallTracker, BallConfig
from basketball_scoreboard.possession import PossessionEngine, PossessionConfig
from basketball_scoreboard.possession_evaluation import evaluate, match_passes, rates


def detection(x=100, y=170, confidence=.9, name="ball"):
    return dict(class_name=name, class_id=9, confidence=confidence, xyxy=[x-5,y-5,x+5,y+5])


def person(track="a", x=50, team="red", role="player", player=None, time_s=0, sample="observed"):
    return dict(track_id=track, observation_id=f"person:{track}:{time_s}", source_time_s=time_s,
                bbox=[x,100,x+100,300], team_id=team, player_id=player or f"player_{track}", role=role, sample_type=sample)


def ball(index, x=100, y=170, sample="observed", t=None, segment="s"):
    return dict(frame_index=index, source_time_s=index*.1 if t is None else t, segment_id=segment,
                observation_id=f"ball:{index}", ball_track_id="ball_a", sample_type=sample,
                center_image=[x,y] if sample != "missing" else None,
                xyxy=[x-5,y-5,x+5,y+5] if sample == "observed" else None,
                reason="fixture", reset_reason=None)


def people(t, **kwargs):
    return [person(time_s=t, **kwargs), person("b", x=500, time_s=t)]


class BallTests(unittest.TestCase):
    def test_class_name_and_motion_association(self):
        tracker = BallTracker((1000,500), "test")
        first = tracker.update(0,0,[detection(), detection(700,name="human")])
        second = tracker.update(1,.1,[detection(700,confidence=.99),detection(120,confidence=.7)])
        self.assertEqual(first["ball_track_id"], second["ball_track_id"])
        self.assertEqual(second["center_image"], [120,170])

    def test_ambiguity_no_arbitrary_initial_ball(self):
        tracker=BallTracker((1000,500),"test")
        row=tracker.update(0,0,[detection(100),detection(500)])
        self.assertEqual(row["sample_type"],"missing")
        self.assertEqual(row["reason"],"ambiguous_ball_candidates")

    def test_prediction_horizon_and_expiry_before_reassociation(self):
        tracker=BallTracker((1000,500),"test")
        initial=tracker.update(0,0,[detection()])
        self.assertEqual(tracker.update(1,.1,[])["sample_type"],"predicted")
        self.assertEqual(tracker.update(2,.2,[])["sample_type"],"missing")
        self.assertNotEqual(tracker.update(3,.5,[detection()])["ball_track_id"],initial["ball_track_id"])

    def test_duplicate_candidates_deduplicated(self):
        self.assertEqual(BallTracker((1000,500),"t").update(0,0,[detection(),detection()])["candidate_count"],1)

    def test_candidate_order_deterministic(self):
        ds=[detection(100,confidence=.9),detection(500,confidence=.5)]
        # Detection evidence indices follow the input, but selected geometry/track are stable.
        a=BallTracker((1000,500),"t").update(0,0,ds)
        b=BallTracker((1000,500),"t").update(0,0,list(reversed(ds)))
        self.assertEqual(a["center_image"],b["center_image"])

    def test_cut_and_clock_reset(self):
        tracker=BallTracker((1000,500),"t")
        a=tracker.update(0,0,[detection()])
        self.assertEqual(tracker.update(1,.1,[detection()],clock_valid=False)["sample_type"],"missing")
        b=tracker.update(2,.2,[detection()],segment="new")
        self.assertNotEqual(a["ball_track_id"],b["ball_track_id"])

    def test_vfr_and_backward_time(self):
        tracker=BallTracker((1000,500),"t")
        tracker.update(0,0,[detection()])
        tracker.update(1,.037,[detection(103)])
        tracker.update(2,.091,[detection(108)])
        with self.assertRaises(ValueError):tracker.update(3,.091,[])

    def test_nonfinite_config_and_invalid_box(self):
        with self.assertRaises(ValueError):BallConfig(max_gap_s=float("nan"))
        with self.assertRaises(ValueError):PossessionConfig(confirmation_samples=2.5)
        with self.assertRaises(ValueError):BallTracker((1000,500),"t").update(0,0,[detection(-10)])


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.engine=PossessionEngine("fixture")

    def initial_control(self):
        rows=[]
        for i in range(3):rows.append(self.engine.update(ball(i),people(i*.1)))
        self.assertEqual(rows[-1]["certainty"],"confirmed")
        return rows

    def test_requires_temporal_evidence(self):
        rows=self.initial_control()
        self.assertIsNone(rows[0]["controller"])
        self.assertEqual(rows[-1]["controller"]["track_id"],"a")

    def test_unknown_role_cannot_confirm(self):
        for i in range(6):
            row=self.engine.update(ball(i),people(i*.1,role="unknown"))
            self.assertIsNone(row["controller"])
        self.assertFalse(self.engine.possessions)

    def test_predicted_players_cannot_confirm(self):
        for i in range(5):
            row=self.engine.update(ball(i),people(i*.1,sample="predicted"))
            self.assertIsNone(row["controller"])

    def test_ambiguous_two_people_remain_contested(self):
        for i in range(5):
            row=self.engine.update(ball(i),[person(time_s=i*.1),person("b",x=55,time_s=i*.1)])
            self.assertEqual(row["state"],"contested")
            self.assertIsNone(row["controller"])

    def test_observed_flight_and_stable_receiver(self):
        self.initial_control()
        old_possession=self.engine.possession["possession_id"]
        for i,x in enumerate((240,340,440,550,550,550),3):
            row=self.engine.update(ball(i,x=x),people(i*.1))
        self.assertEqual(row["controller"]["track_id"],"b")
        self.assertEqual(self.engine.passes[-1]["outcome"],"completed")
        self.assertEqual(self.engine.passes[-1]["passer"]["player_id"],"player_a")
        self.assertEqual(self.engine.possession["possession_id"],old_possession)

    def test_missing_ball_never_bridges_pass(self):
        self.initial_control()
        self.engine.update(ball(3,x=240),people(.3))
        self.engine.update(ball(4,sample="predicted"),people(.4))
        for i in (5,6,7):self.engine.update(ball(i,x=550),people(i*.1))
        self.assertTrue(all(p["outcome"] != "completed" for p in self.engine.passes))

    def test_opponent_receive_is_not_confirmed_pass(self):
        self.initial_control()
        for i,x in enumerate((240,340,440,550,550,550),3):
            ps=people(i*.1);ps[1]["team_id"]="blue"
            self.engine.update(ball(i,x=x),ps)
        self.assertEqual(self.engine.passes[-1]["outcome"],"unresolved")
        self.assertEqual(len(self.engine.possessions),2)

    def test_no_identity_backfill_to_receive_time(self):
        self.initial_control()
        for i,x in enumerate((240,340,440,550,550,550),3):
            ps=people(i*.1)
            if i <= 6:ps[1]["player_id"]=None
            self.engine.update(ball(i,x=x),ps)
        self.assertIsNone(self.engine.passes[-1]["receiver"]["player_id"])

    def test_same_identity_on_new_track_is_not_pass(self):
        self.initial_control()
        for i,x in enumerate((240,340,440,550,550,550),3):
            ps=people(i*.1);ps[1]["player_id"]="player_a"
            self.engine.update(ball(i,x=x),ps)
        self.assertNotEqual(self.engine.passes[-1]["outcome"],"completed")

    def test_cut_resets_pending_flight(self):
        self.initial_control()
        self.engine.update(ball(3,x=240),people(.3))
        for i in (4,5,6):self.engine.update(ball(i,x=550,segment="other"),people(i*.1))
        self.assertTrue(all(p["outcome"] != "completed" for p in self.engine.passes))

    def test_contested_control_closes_old_actor(self):
        self.initial_control()
        row=self.engine.update(ball(3),[person(time_s=.3),person("new_occluded_track",x=50,time_s=.3)])
        self.assertEqual(row["state"],"contested")
        self.assertIsNone(row["controller"])

    def test_dribble_is_provisional_not_a_pass(self):
        self.initial_control()
        row=self.engine.update(ball(3,y=295),people(.3))
        self.assertEqual(row["phase"],"dribble_candidate")
        self.assertEqual(row["certainty"],"provisional")
        self.engine.update(ball(4,y=270),people(.4))
        self.engine.update(ball(5),people(.5))
        self.assertFalse(any(p["outcome"] == "completed" for p in self.engine.passes))

    def test_vfr_confirmation_and_gap(self):
        for i,t in enumerate((0,.03,.06,.101)):
            row=self.engine.update(ball(i,t=t),people(t))
        self.assertEqual(row["certainty"],"confirmed")
        row=self.engine.update(ball(4,x=550,t=1.0),people(1.))
        self.assertIsNone(row["controller"])

    def test_replay_is_deterministic(self):
        outputs=[]
        for _ in range(2):
            engine=PossessionEngine("replay")
            rows=[engine.update(ball(i,x=x),people(i*.1)) for i,x in enumerate((100,100,100,240,340,440,550,550,550))]
            engine.finish()
            outputs.append((rows,engine.passes,engine.possessions,engine.transitions))
        self.assertEqual(outputs[0],outputs[1])

    def test_role_expiry_interrupts_confirmed_control(self):
        self.initial_control()
        row=self.engine.update(ball(3),people(.3,role="unknown"))
        self.assertIsNone(row["controller"])
        self.assertIsNone(self.engine.possession)

    def test_team_change_requires_new_control_confirmation(self):
        self.initial_control()
        row=self.engine.update(ball(3),people(.3,team="blue"))
        self.assertIsNone(row["controller"])
        self.assertIsNone(self.engine.possession)
        for i in (4,5):row=self.engine.update(ball(i),people(i*.1,team="blue"))
        self.assertEqual(row["controller"]["team_id"],"blue")
        self.assertEqual(self.engine.possession["team_id"],"blue")

    def test_shot_suspected_cannot_complete_as_pass(self):
        self.initial_control()
        self.engine.update(ball(3,x=240,y=120),people(.3))
        row=self.engine.update(ball(4,x=300,y=70),people(.4),rims=[dict(xyxy=[280,40,320,80])])
        self.assertTrue(row["shot_candidate"])
        for i in (5,6,7):self.engine.update(ball(i,x=550),people(i*.1))
        self.assertTrue(all(p["outcome"] != "completed" for p in self.engine.passes))

    def test_short_handoff_has_no_completed_flight_pass(self):
        close_people = lambda t: [person(time_s=t),person("b",x=200,time_s=t)]
        for i in range(3):self.engine.update(ball(i),close_people(i*.1))
        for i in (3,4,5):
            self.engine.update(ball(i,x=210),close_people(i*.1))
        self.assertFalse(self.engine.passes)
        self.assertTrue(any(t["kind"]=="handoff_or_control_switch_candidate" for t in self.engine.transitions))

    def test_bounce_flight_is_marked_candidate(self):
        self.initial_control()
        for i,(x,y) in enumerate(((240,280),(340,320),(440,270),(550,170),(550,170),(550,170),(550,170)),3):
            self.engine.update(ball(i,x=x,y=y),people(i*.1))
        self.assertEqual(self.engine.passes[-1]["pass_kind"],"bounce_candidate")


class EvaluatorTests(unittest.TestCase):
    def test_empty_denominators_are_null(self):
        self.assertIsNone(rates(0,0,0)["precision"])
        self.assertEqual(rates(0,0,1)["recall"],0)

    def test_cardinality_before_nearest_time(self):
        pred=[dict(pass_id="p1",release_time_s=.4),dict(pass_id="p2",release_time_s=0.)]
        gt=[dict(pass_id="g1",release_time_s=.1),dict(pass_id="g2",release_time_s=.8)]
        self.assertEqual(match_passes(pred,gt,.5,strict=False)["tp"],2)

    def test_wrong_actor_is_fp_and_fn(self):
        p=dict(pass_id="p",release_time_s=1.,passer=dict(player_id="wrong",team_id="r"),receiver=dict(player_id="b",team_id="r"))
        gt=copy.deepcopy(p);gt["pass_id"]="g";gt["passer"]["player_id"]="a"
        self.assertEqual(match_passes([p],[gt],.5,strict=False)["tp"],1)
        strict=match_passes([p],[gt],.5)
        self.assertEqual((strict["tp"],strict["fp"],strict["fn"]),(0,1,1))

    def test_unknown_control_in_denominator(self):
        packet=dict(schema_version="task07-evaluation-1",source_video_sha256="s",is_synthetic=True,
                    coverage=[dict(start_time_s=0,end_time_s=1)],control_intervals=[dict(start_time_s=0,end_time_s=1,player_id="a",team_id="r")],
                    passes=[],ball_samples=[],pass_tolerance_s=.5,ball_iou_threshold=.3)
        result=dict(controls=[dict(source_time_s=0,certainty="unresolved",controller=None),dict(source_time_s=1,certainty="unresolved",controller=None)],balls=[],passes=[])
        metrics=evaluate(result,packet,"s",diagnostic=True)
        self.assertEqual(metrics["control"]["strict_accuracy"],0)
        self.assertEqual(metrics["control"]["unknown_or_missed_seconds"],1)
        self.assertIsNone(metrics["ball"]["recall"])
        with self.assertRaises(ValueError):evaluate(result,packet,"s")

    def test_prediction_does_not_improve_observed_ball_recall(self):
        packet=dict(schema_version="task07-evaluation-1",source_video_sha256="s",is_synthetic=True,
                    coverage=[dict(start_time_s=0,end_time_s=1)],control_intervals=[],passes=[],
                    ball_samples=[dict(frame_index=0,source_time_s=0,xyxy=[95,165,105,175],visible=True)],
                    pass_tolerance_s=.5,ball_iou_threshold=.3)
        result=dict(controls=[],passes=[],balls=[ball(0,sample="predicted")])
        self.assertEqual(evaluate(result,packet,"s",diagnostic=True)["ball"]["recall"],0)
        result["balls"]=[ball(0)]
        self.assertEqual(evaluate(result,packet,"s",diagnostic=True)["ball"]["recall"],1)

    def test_duplicate_pass_is_false_positive(self):
        p=dict(pass_id="p",release_time_s=1.)
        metrics=match_passes([p,{**p,"pass_id":"duplicate"}],[{**p,"pass_id":"gt"}],.5,strict=False)
        self.assertEqual((metrics["tp"],metrics["fp"],metrics["fn"]),(1,1,0))

    def test_time_weighted_control_counts_unknown_interval(self):
        packet=dict(schema_version="task07-evaluation-1",source_video_sha256="s",is_synthetic=True,
                    coverage=[dict(start_time_s=0,end_time_s=1)],
                    control_intervals=[dict(start_time_s=0,end_time_s=1,player_id="a",team_id="r")],
                    passes=[],ball_samples=[],pass_tolerance_s=.5,ball_iou_threshold=.3)
        controls=[dict(source_time_s=t,certainty="confirmed" if t<.5 else "unresolved",
                       controller=dict(player_id="a",team_id="r") if t<.5 else None) for t in (0,.25,.5,.75,1)]
        metrics=evaluate(dict(controls=controls,balls=[],passes=[]),packet,"s",diagnostic=True)
        self.assertEqual(metrics["control"]["strict_accuracy"],.5)
        self.assertEqual(metrics["control"]["unknown_or_missed_seconds"],.5)


if __name__ == "__main__":unittest.main()
