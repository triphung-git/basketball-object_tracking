"""Conservative temporal control and operational possession; no official PRA stats."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math

from .ball import center


@dataclass(frozen=True)
class PossessionConfig:
    confirmation_samples: int = 3
    confirmation_s: float = 0.10
    max_gap_s: float = 0.25
    dribble_hold_s: float = 0.45
    max_flight_s: float = 2.0
    min_flight_samples: int = 2
    ambiguity_margin: float = 0.12
    max_relative_speed_heights_s: float = 6.0
    dribble_confirmation_samples: int = 2
    dribble_relative_speed_widths_s: float = 3.0
    max_unobserved_gap_s: float = 0.0

    def __post_init__(self):
        for key, value in asdict(self).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 or (value == 0 and key != 'max_unobserved_gap_s'):
                raise ValueError(f"Invalid possession config: {key}")
        for key in ("confirmation_samples", "min_flight_samples", "dribble_confirmation_samples"):
            if not isinstance(getattr(self, key), int) or getattr(self, key) < 2:
                raise ValueError("Temporal confirmation needs at least two integer samples")
        if self.ambiguity_margin >= 1:
            raise ValueError("Invalid interaction ambiguity margin")


def actor(observation):
    return dict(track_id=observation["track_id"], player_id=observation.get("player_id"),
                team_id=observation.get("team_id"),
                identity_at_s=observation["source_time_s"],
                evidence_ref=observation["observation_id"])


class PossessionEngine:
    """BBox interaction heuristics with temporal confirmation and explicit uncertainty.

    Same-team observed flight can complete a pass. Handoffs/deflections remain
    candidates because boxes alone cannot prove intent or a controlled touch.
    """

    def __init__(self, namespace, config=None):
        self.namespace = namespace
        self.config = config or PossessionConfig()
        self.last_time = -1.
        self.segment = None
        self.ball_id = None
        self.controller = None
        self.candidate = None
        self.pending = None
        self.possession = None
        self.possessions = []
        self.passes = []
        self.transitions = []
        self.previous = None
        self.counter = 0
        self.last_observed_ball_s = -1.
        self.had_unobserved_gap = False

    def _id(self, kind):
        self.counter += 1
        return f"{self.namespace}:{kind}:{self.counter}"

    def _event(self, kind, time_s, **fields):
        self.transitions.append(dict(event_id=self._id("transition"), kind=kind,
                                     confirmed_at_s=time_s, **fields))

    def _close(self, time_s, reason):
        if self.possession:
            self.possession["end_time_s"] = self.possession["last_observed_control_s"]
            self.possession["closed_at_s"] = time_s
            self.possession["end_reason"] = reason
            self.possession = None

    def reset(self, time_s, reason):
        if self.pending:
            self._end_pass(time_s, "unresolved", reason)
        self._close(time_s, reason)
        if self.controller:
            self._event("control_interrupted", time_s, actor=self.controller["actor"], reason=reason)
        self.controller = self.candidate = self.pending = self.previous = None
        self.had_unobserved_gap = False

    def _end_pass(self, time_s, outcome, reason, receiver=None):
        item = self.pending
        if not item:
            return
        item.update(status="confirmed" if outcome == "completed" else "unresolved", outcome=outcome,
                    reason=reason, confirmed_at_s=time_s, receiver=receiver,
                    pass_kind="bounce_candidate" if item["bounce_seen"] else "flight_candidate")
        self.passes.append(dict(item))
        self._event("pass_resolved", time_s, pass_id=item["pass_id"], outcome=outcome)
        self.pending = None

    def _interaction(self, ball, observations, time_s):
        bx, by = ball["center_image"]
        scored = []
        geometric_contact = False
        for obs in observations:
            if obs.get("sample_type") != "observed" or obs.get("role") == "non_player" or not obs.get("track_id"):
                continue
            x1, y1, x2, y2 = obs["bbox"]
            w, h = x2-x1, y2-y1
            # Expanded torso/estimated hand region; this is not a pose keypoint.
            dx = max(x1-.2*w-bx, 0., bx-(x2+.2*w))
            dy = max(y1+.08*h-by, 0., by-(y1+.72*h))
            distance = math.hypot(dx, dy) / h
            if distance > .18:
                continue
            geometric_contact = True
            score = 1. - distance / .18
            if self.previous and obs["track_id"] in self.previous["people"]:
                old = self.previous["people"][obs["track_id"]]
                dt = time_s-self.previous["time"]
                old_c, new_c = center(old["bbox"]), center(obs["bbox"])
                movement = ((bx-self.previous["ball"][0])-(new_c[0]-old_c[0]),
                            (by-self.previous["ball"][1])-(new_c[1]-old_c[1]))
                relative_speed = math.hypot(*movement)/h/dt
                if relative_speed > self.config.max_relative_speed_heights_s:
                    score *= .25
            if score >= .35:
                scored.append((score, obs))
        scored.sort(key=lambda item: (-item[0], item[1]["track_id"]))
        if len(scored) > 1 and scored[0][0]-scored[1][0] < self.config.ambiguity_margin:
            return None, "contested", scored[0][0]
        if scored:
            return scored[0][1], "interaction_candidate", scored[0][0]
        if geometric_contact:
            return None, "motion_ambiguous_interaction", None
        return None, "no_interaction", None

    def update(self, ball, observations, rims=(), reset_reason=None):
        time_s, segment = ball["source_time_s"], ball["segment_id"]
        if not math.isfinite(time_s) or time_s < 0 or time_s <= self.last_time:
            raise ValueError("Control timestamps must strictly increase")
        reason = reset_reason or ball.get("reset_reason")
        if self.segment is not None and segment != self.segment:
            reason = "segment_change"
        if self.last_time >= 0 and time_s-self.last_time > self.config.max_gap_s:
            reason = reason or "coverage_gap"
        if self.ball_id and ball.get("ball_track_id") != self.ball_id:
            reason = reason or "ball_track_change"
        if self.had_unobserved_gap and ball['sample_type']=='observed' and time_s-self.last_observed_ball_s > self.config.max_unobserved_gap_s+1e-9:
            reason = reason or 'unobserved_gap_exceeded'
        if reason:
            self.reset(time_s, reason)
        self.last_time, self.segment = time_s, segment
        self.ball_id = ball.get("ball_track_id")
        result = dict(schema_version="2.1.0", control_id=f"{self.namespace}:control:{ball['frame_index']}",
                      frame_index=ball["frame_index"], source_time_s=time_s, segment_id=segment,
                      ball_track_id=self.ball_id, state="unknown", certainty="unresolved",
                      controller=None, candidate_actor=None, possession_id=None,
                      evidence_refs=[ball["observation_id"]], reason=reason or ball["reason"],
                      interaction_score=None, score_kind="heuristic_not_probability",
                      phase=None, shot_candidate=False)
        if ball["sample_type"] != "observed":
            if (not reason and self.last_observed_ball_s >= 0 and self.config.max_unobserved_gap_s > 0 and
                    time_s-self.last_observed_ball_s <= self.config.max_unobserved_gap_s+1e-9):
                self.had_unobserved_gap=True
                self.candidate=None
                self.previous=None
                if self.pending:self.pending['unobserved_gap_samples']=self.pending.get('unobserved_gap_samples',0)+1
                result['reason']='bounded_unobserved_gap_provisional_only'
            else:
                self.reset(time_s, "ball_not_observed")
            return result
        self.last_observed_ball_s=time_s
        self.had_unobserved_gap=False
        observations = [o for o in observations if o.get("sample_type") == "observed"]
        by_id = {o["track_id"]: o for o in observations}
        picked, interaction, score = self._interaction(ball, observations, time_s)
        result.update(interaction_score=score, reason=interaction)
        old_controller = self.controller
        if old_controller:
            current_controller = by_id.get(old_controller["actor"]["track_id"])
            identity_changed = bool(current_controller and (
                current_controller.get("team_id") != old_controller["actor"]["team_id"] or
                (current_controller.get("player_id") and old_controller["actor"]["player_id"] and
                 current_controller["player_id"] != old_controller["actor"]["player_id"])))
            if current_controller is None or current_controller.get("role") != "player" or identity_changed:
                self.reset(time_s, "controller_not_currently_observed_player")
                old_controller = None
        if self.pending:
            self.pending["evidence_refs"].append(ball["observation_id"])
            if time_s-self.pending["release_time_s"] > self.config.max_flight_s:
                self._end_pass(time_s, "unresolved", "flight_timeout")
            else:
                self.pending["observed_flight_samples"] += int(picked is None and interaction == "no_interaction")
                if self.previous:
                    dy = ball["center_image"][1]-self.previous["ball"][1]
                    if self.pending.get("last_dy", 0) > 0 and dy < 0:
                        self.pending["bounce_seen"] = True
                    if abs(dy) > 1e-9:
                        self.pending["last_dy"] = dy
                if interaction == "contested":
                    self.pending["contested_seen"] = True
        if picked:
            result["candidate_actor"] = actor(picked)
            track = picked["track_id"]
            if old_controller and track == old_controller["actor"]["track_id"]:
                self.controller.update(actor=actor(picked), last_contact_s=time_s,dribble_hits=0)
                if self.pending:
                    self._end_pass(time_s, "unresolved", "same_controller_recovered_dribble_or_loose")
                self.candidate = None
            else:
                if (not self.candidate or self.candidate["actor"]["track_id"] != track or
                        self.candidate["actor"]["team_id"] != picked.get("team_id") or
                        (self.candidate["actor"]["player_id"] and picked.get("player_id") and
                         self.candidate["actor"]["player_id"] != picked["player_id"])):
                    self.candidate = dict(actor=actor(picked), start_s=time_s, hits=0, role=picked.get("role"))
                self.candidate["hits"] += 1
                eligible = (picked.get("role") == "player" and self.candidate["role"] == "player" and
                            self.candidate["hits"] >= self.config.confirmation_samples and
                            time_s-self.candidate["start_s"] + 1e-9 >= self.config.confirmation_s)
                if eligible:
                    receiving = dict(self.candidate["actor"])
                    if self.pending:
                        passing = self.pending["passer"]
                        self.pending["receive_time_s"] = self.candidate["start_s"]
                        enough = self.pending["observed_flight_samples"] >= self.config.min_flight_samples
                        same_team = bool(passing["team_id"] and passing["team_id"] == receiving["team_id"])
                        same_player = bool(passing["player_id"] and passing["player_id"] == receiving["player_id"])
                        if (enough and same_team and not same_player and not self.pending["contested_seen"]
                                and not self.pending.get("shot_suspected")):
                            self._end_pass(time_s, "completed", "observed_flight_and_stable_same_team_receiver", receiving)
                        else:
                            self._end_pass(time_s, "unresolved", "interception_or_deflection_or_unknown_transfer", receiving)
                    elif old_controller and old_controller["actor"]["track_id"] != track:
                        self._event("handoff_or_control_switch_candidate", time_s,
                                    passer=old_controller["actor"], receiver=receiving,
                                    reason="no_independent_flight_or_hand_keypoints")
                    previous_team = self.possession["team_id"] if self.possession else None
                    if self.possession and (not previous_team or not receiving["team_id"] or previous_team != receiving["team_id"]):
                        self._close(time_s, "opponent_or_unknown_control")
                    if not self.possession:
                        self.possession = dict(possession_id=self._id("possession"),
                            definition="operational_observed_team_control_not_official_rule_possession",
                            team_id=receiving["team_id"], start_time_s=time_s, confirmed_at_s=time_s,
                            last_observed_control_s=time_s, end_time_s=None, end_reason=None)
                        self.possessions.append(self.possession)
                    self.controller = dict(actor=actor(picked), last_contact_s=time_s,dribble_hits=0)
                    self._event("control_confirmed", time_s, actor=receiving,
                                effective_time_s=self.candidate["start_s"],
                                possession_id=self.possession["possession_id"])
                    self.candidate = None
        else:
            self.candidate = None
            if old_controller:
                previous_obs = by_id.get(old_controller["actor"]["track_id"])
                floor_dribble = False
                if previous_obs and interaction != "contested":
                    x1,y1,x2,y2 = previous_obs["bbox"]
                    bx,by = ball["center_image"]
                    floor_dribble = (x1-.3*(x2-x1) <= bx <= x2+.3*(x2-x1) and
                                     y1+.72*(y2-y1) < by <= y2+.15*(y2-y1) and
                                     time_s-old_controller["last_contact_s"] <= self.config.dribble_hold_s)
                if floor_dribble:
                    result["phase"] = "dribble_candidate"
                    result["certainty"] = "provisional"
                    relative_speed=float('inf')
                    if self.previous and previous_obs['track_id'] in self.previous['people']:
                        old_box=self.previous['people'][previous_obs['track_id']]['bbox']
                        old_relative=self.previous['ball'][0]-center(old_box)[0]
                        new_relative=ball['center_image'][0]-center(previous_obs['bbox'])[0]
                        relative_speed=abs(new_relative-old_relative)/(x2-x1)/(time_s-self.previous['time'])
                    self.controller['dribble_hits'] = (self.controller.get('dribble_hits',0)+1
                        if relative_speed <= self.config.dribble_relative_speed_widths_s else 0)
                    if self.controller['dribble_hits'] >= self.config.dribble_confirmation_samples:
                        result.update(state='controlled',certainty='confirmed',controller=actor(previous_obs),phase='observed_dribble')
                        self.possession['last_observed_control_s']=time_s
                elif interaction == "contested":
                    result["state"] = "contested"
                    self._close(time_s, "contested_control")
                    self.controller = None
                    if self.pending:
                        self._end_pass(time_s, "unresolved", "contested_control")
                else:
                    if not self.pending and interaction == 'no_interaction':
                        releasing = actor(previous_obs) if previous_obs else {**old_controller["actor"], "player_id": None, "team_id": None}
                        self.pending = dict(pass_id=self._id("pass"), status="provisional",
                            passer=releasing, receiver=None, release_time_s=time_s,
                            receive_time_s=None, confirmed_at_s=None, outcome=None,
                            observed_flight_samples=1, contested_seen=False, bounce_seen=False,
                            evidence_refs=[ball["observation_id"]], ball_track_id=self.ball_id,
                            possession_id=self.possession["possession_id"] if self.possession else None)
                        self._event("release_candidate", time_s, actor=releasing, pass_id=self.pending["pass_id"])
                    self.controller = None
            result["state"] = ("contested" if interaction == "contested" else
                               "unknown" if interaction == "motion_ambiguous_interaction" else
                               "pass_candidate" if self.pending else ("loose" if self.counter else "free"))
        if self.controller and picked and picked["track_id"] == self.controller["actor"]["track_id"]:
            result.update(state="controlled", certainty="confirmed", controller=actor(picked))
            self.possession["last_observed_control_s"] = time_s
        elif self.controller and result["phase"] == "dribble_candidate":
            result.update(state="controlled", controller=None, previous_controller=self.controller["actor"])
        elif picked:
            result["state"] = "unknown" if picked.get("role") != "player" else "control_candidate"
            if old_controller and picked["track_id"] != old_controller["actor"]["track_id"]:
                # While a challenger is accumulating evidence, do not report the old actor as confirmed.
                result["reason"] = "controller_change_pending"
        if self.pending and self.previous and rims:
            bx,by = ball["center_image"]
            old_y = self.previous["ball"][1]
            if by < old_y and any(math.dist((bx,by), center(r["xyxy"])) <
                                     .8 * max(r["xyxy"][2]-r["xyxy"][0], r["xyxy"][3]-r["xyxy"][1]) for r in rims):
                result.update(state="shot_candidate", shot_candidate=True)
                self.pending["shot_suspected"] = True
        if self.possession:
            result["possession_id"] = self.possession["possession_id"]
            if not self.controller and not self.pending:
                self._close(time_s, "control_lost")
        self.previous = dict(time=time_s, ball=ball["center_image"], people=by_id)
        return result

    def finish(self):
        if self.last_time >= 0:
            self.reset(self.last_time, "end_of_observed_input")
