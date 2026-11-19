"""Shared continuity and physical-identity rules for CLI and web occupancy."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
import heapq
import math


def grid_shape_for_bounds(bounds, cell_size_m=.25):
    return (max(1, math.ceil((bounds['y_max']-bounds['y_min'])/cell_size_m)),
            max(1, math.ceil((bounds['x_max']-bounds['x_min'])/cell_size_m)))


def source_scope(obs):
    return tuple(obs.get(k) for k in ('source_run_id', 'video_id', 'source_fingerprint_sha256',
                                      'camera_id', 'segment_id', 'calibration_version'))


def continuity_reason(a, b, max_gap_s, max_speed_m_s=12., allow_unknown_role=False):
    """Return a reason for refusing an interval. Coordinates are never repaired here."""
    dt = b['t']-a['t']
    if dt <= 0:
        return 'non_increasing_time'
    if dt > max_gap_s + 1e-9:
        return 'long_gap'
    if a.get('scope') != b.get('scope') or a.get('segment') != b.get('segment'):
        return 'camera_or_calibration_change'
    if any(a.get(k) != b.get(k) for k in ('player_id', 'team_id', 'role')):
        return 'identity_change'
    roles = {'player', 'unknown'} if allow_unknown_role else {'player'}
    if a.get('role') not in roles:
        return 'unconfirmed_role'
    if a.get('xy') is None or b.get('xy') is None:
        return 'invalid_position'
    if max_speed_m_s is not None and math.dist(a['xy'], b['xy']) > max_speed_m_s*dt + 1e-9:
        return 'speed_outlier'
    return None


@dataclass(frozen=True, slots=True)
class OccupancyInterval:
    start: float
    end: float
    sample: dict
    timestamp_status: str = 'valid'


def resolve_identity_overlaps(intervals):
    """Resolve each identity's timeline by quality, splitting partial overlaps.

    Half-open intervals and deterministic tie breaks make the result independent
    of track/JSONL ordering. Unknown people remain separate track identities.
    """
    actors = defaultdict(list)
    for interval in intervals:
        s = interval.sample
        source = tuple(s.get('scope', ())[:3])
        actor = ('player', s['player_id']) if s.get('player_id') else ('track', s['track_id'])
        actors[(source, actor)].append(interval)
    resolved = []
    for candidates in actors.values():
        if len(candidates) == 1:
            resolved.extend(candidates)
            continue
        events = defaultdict(lambda: [[], []])
        for index, item in enumerate(candidates):
            events[item.start][1].append(index)
            events[item.end][0].append(index)
        active, heap = set(), []
        previous = None
        for t in sorted(events):
            while heap and heap[0][-1] not in active:
                heapq.heappop(heap)
            if previous is not None and t > previous and heap:
                winner = candidates[heap[0][-1]]
                resolved.append(replace(winner, start=previous, end=t))
            ends, starts = events[t]
            active.difference_update(ends)
            for index in starts:
                active.add(index)
                s = candidates[index].sample
                priority = (-int(s.get('origin') == 'manual'), -float(s.get('confidence', 0)),
                            s['track_id'], candidates[index].start, index)
                heapq.heappush(heap, priority)
            previous = t
    return sorted(resolved, key=lambda item: (item.start, item.end, item.sample['track_id']))


def unique_position_markers(people):
    """Retain all image observations, but expose one physical marker per player."""
    winners = {}
    for person in people:
        if person.get('xy') is None or not person.get('player_id'):
            continue
        pid = person['player_id']
        priority = (-int(person.get('origin') == 'manual'), -float(person.get('confidence', 0)), person['id'])
        if pid not in winners or priority < winners[pid][0]:
            winners[pid] = (priority, person)
    conflicts = 0
    for person in people:
        winner = winners.get(person.get('player_id'))
        if person.get('xy') is not None and winner and person is not winner[1]:
            person['xy'] = None
            person['position_status'] = 'duplicate_identity'
            conflicts += 1
    return conflicts
