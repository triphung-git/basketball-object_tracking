"""Sparse local jersey OCR on immutable tracks; roster names require evidence."""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
import hashlib
from itertools import groupby
import json
from pathlib import Path

from .identity import IdentityResolver,JerseyEvidenceRecord,LocalEasyOCRProvider,ModelWeightsUnavailableError
from .identity_crops import jersey_region,overlap_fraction

JERSEY_EVIDENCE_VERSION=1


def _rows(path):
    with Path(path).open(encoding='utf-8') as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def extract_jersey_evidence(directory,observations,source_sha256,teams,*,video_path=None,progress=None,provider_factory=None):
    """Cache pixel observations independently of names/numbers in the roster."""
    from .video import VideoReader
    from .web_jobs import write_json
    directory=Path(directory)
    with Path(observations).open('rb') as source:
        digest=hashlib.file_digest(source,'sha256').hexdigest()
    signature=hashlib.sha256(json.dumps(dict(version=JERSEY_EVIDENCE_VERSION,
        source_sha256=source_sha256,observations=digest,teams=teams),sort_keys=True).encode()).hexdigest()
    cache=Path(observations).parent/'automatic_jersey_evidence.json'
    try:
        previous=json.loads(cache.read_text(encoding='utf-8'))
        if previous.get('signature')==signature and previous.get('status')=='completed':
            return previous
    except (OSError,ValueError):
        pass
    if progress:
        progress('jersey_identity',0,0)
    try:
        provider=(provider_factory or LocalEasyOCRProvider)(confidence_threshold=.85,crop_upscale=2,
                                                          min_number_height_fraction=.18)
        if isinstance(provider,LocalEasyOCRProvider):
            _=provider.reader
    except (ModelWeightsUnavailableError,ModuleNotFoundError):
        return dict(status='unavailable',reason='local_ocr_weights_or_dependency_unavailable',records=[])
    selected=[]
    last={}
    for index,frame in groupby(_rows(observations),key=lambda r:r.get('frame_index')):
        if index is None:
            return dict(status='unavailable',reason='source_frame_clock_missing',records=[])
        frame=list(frame)
        observed=[r for r in frame if r.get('sample_type')=='observed']
        candidates=[]
        for row in observed:
            tid,t=row['track_id'],row['source_time_s']
            if (not teams.get(tid) or row.get('role') in {'non_player','referee'}
                    or row.get('timestamp_status','valid') not in {'valid','repaired'}
                    or t-last.get(tid,-1)<.3 or row['bbox'][3]-row['bbox'][1]<90):
                continue
            last[tid]=t
            candidates.append(row)
        if candidates:
            selected.append((index,observed,candidates))
    records=[];attempts=0;blocked=0
    total=sum(len(c) for _,_,c in selected)
    if progress:
        progress('jersey_identity',0,total)
    with VideoReader(video_path or directory/'input.mp4') as reader:
        if reader.metadata.sha256 != source_sha256:
            raise ValueError('Jersey OCR video fingerprint mismatch')
        decoded=iter(reader.frames());current=None
        for index,observed,candidates in selected:
            while current is None or current[0].frame_index<index:
                current=next(decoded)
            frame,image=current
            if frame.frame_index!=index:
                raise ValueError('Jersey OCR source frame mismatch')
            h,w=image.shape[:2]
            for row in candidates:
                if abs(frame.source_time_s-row['source_time_s'])>1e-6:
                    raise ValueError('Jersey OCR source timestamp mismatch')
                region=jersey_region(row['bbox'],w,h)
                if any(other['track_id']!=row['track_id'] and overlap_fraction(region,other['bbox'])>.25
                       for other in observed):
                    blocked+=1
                    continue
                left,top,right,bottom=region
                crop=image[top:bottom,left:right]
                evidence=provider.read_jersey(crop,row['track_id'],index,row['source_time_s'])
                records.extend(r.to_dict() for r in evidence)
                attempts+=1
                if progress and attempts%5==0:
                    progress('jersey_identity',attempts+blocked,total)
    result=dict(status='completed',signature=signature,source_sha256=source_sha256,
                records=records,attempts=attempts,overlap_blocked=blocked,provider='easyocr_local',
                engine_stats=getattr(provider,'stats',{}))
    write_json(cache,result)
    if progress:
        progress('jersey_identity',total,total)
    return result


class JerseyIdentityTimeline:
    def __init__(self,observations,roster,teams,evidence):
        self.intervals=defaultdict(list)
        self.starts={}
        self.summary=dict(status=evidence['status'],reason=evidence.get('reason'),
            evidence_records=len(evidence.get('records',[])),named_tracks=0,named_players=0,
            attempts=evidence.get('attempts',0),overlap_blocked=evidence.get('overlap_blocked',0))
        if not evidence.get('records'):
            return
        resolver=IdentityResolver(roster,min_ocr_confidence=.85,confirmation_hits_threshold=3,
                                  jersey_evidence_ttl_s=3.)
        records=defaultdict(list)
        for item in evidence.get('records',[]):
            records[(item['frame_index'],item['track_id'])].append(item)
        for index,frame in groupby(_rows(observations),key=lambda r:r['frame_index']):
            frame=[r for r in frame if r.get('sample_type')=='observed'
                   and r.get('timestamp_status','valid') in {'valid','repaired'}
                   and r.get('role') not in {'non_player','referee'}]
            active={r['track_id'] for r in frame}
            for row in frame:
                tid,t=row['track_id'],row['source_time_s']
                team=teams.get(tid)
                resolver.add_team_observation(tid,team,.99 if team else 0.,t)
                for item in records.get((index,tid),[]):
                    if abs(item['source_time_s']-t)>1e-6:
                        raise ValueError('Jersey evidence clock mismatch')
                    resolver.add_jersey_evidence(JerseyEvidenceRecord(**item))
                resolver.update_track_mapping(tid,t,active)
        for mapping in resolver.mapping_ledger:
            if mapping.player_id:
                self.intervals[mapping.track_id].append(mapping)
        for tid,intervals in self.intervals.items():
            self.starts[tid]=[m.start_time_s for m in intervals]
        self.summary=dict(status=evidence['status'],reason=evidence.get('reason'),
            evidence_records=len(evidence.get('records',[])),
            named_tracks=len(self.intervals),named_players=len({m.player_id for rows in self.intervals.values() for m in rows}),
            attempts=evidence.get('attempts',0),overlap_blocked=evidence.get('overlap_blocked',0))

    def at(self,track,time_s):
        index=bisect_right(self.starts.get(track,[]),time_s)-1
        if index>=0:
            mapping=self.intervals[track][index]
            if time_s<=mapping.end_time_s and time_s<=mapping.evidence_summary.get('valid_until_s',time_s):
                return mapping.player_id
        return None
