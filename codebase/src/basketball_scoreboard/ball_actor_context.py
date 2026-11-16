"""Optional short-lived actor-relative association cues, never possession GT."""
import math

from .ball import center


def current_players(observations, frame_index, time_s):
    """Only unique, current observed player tracks may support association."""
    players = {}
    duplicate_ids = set()
    for person in observations:
        if (person.get('sample_type') != 'observed' or person.get('role') != 'player' or
                person.get('frame_index') != frame_index or person.get('source_time_s') != time_s):
            continue
        track_id, box = person.get('track_id'), person.get('bbox')
        if not isinstance(track_id, str) or not track_id or not isinstance(box, (list, tuple)) or len(box) != 4:
            continue
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in box):
            continue
        if not (box[0] < box[2] and box[1] < box[3]):
            continue
        if track_id in players:
            duplicate_ids.add(track_id)
        players[track_id] = box
    return {key: box for key, box in players.items() if key not in duplicate_ids}


def actor_anchor(ball_box, players):
    """Remember a unique nearby torso, without asserting that it holds the ball.

    A flying ball may have no nearby actor. Crowded/contested geometry supplies
    no anchor. The next observed ball must still pass the tracker's motion gate.
    """
    bx, by = center(ball_box)
    nearby = []
    for track_id, box in players.items():
        height = box[3] - box[1]
        mx = (box[0] + box[2]) / 2
        if box[0] - .1 * height <= bx <= box[2] + .1 * height and box[1] + .1 * height <= by <= box[1] + .85 * height:
            distance = math.hypot((bx - mx) / height, (by - (box[1] + .5 * height)) / height)
            nearby.append((distance, track_id, (bx - mx) / height, (by - box[1]) / height))
    nearby.sort()
    if not nearby or (len(nearby) > 1 and nearby[1][0] - nearby[0][0] < .10):
        return None
    _, track_id, dx, dy = nearby[0]
    return dict(track_id=track_id, offset_heights=(dx, dy))


def actor_prediction(anchor, players):
    if not anchor or anchor['track_id'] not in players:
        return None
    box = players[anchor['track_id']]
    height = box[3] - box[1]
    dx, dy = anchor['offset_heights']
    return ((box[0] + box[2]) / 2 + dx * height, box[1] + dy * height, height)
