"""Source-only crop ownership and broadcast mask checks; no label access."""
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from .players import compute_iou as iou
from .identity import extract_jersey_rgb


@dataclass(frozen=True)
class IdentityCropPolicy:
    excluded_boxes: list = field(default_factory=list)
    max_other_overlap: float = .5
    ambiguity_hold_s: float = .75
    duplicate_iou: float = .8
    min_visible_pixels: int = 256
    min_visible_fraction: float = .15
    team_region: str = 'jersey'
    suspend_team_conflict: bool = True
    recover_clear_crop: bool = False
    reject_side_clipped: bool = False

    def __post_init__(self):
        for name in ('max_other_overlap','duplicate_iou','min_visible_fraction'):
            value=getattr(self,name)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<value<=1:
                raise ValueError('Invalid crop policy '+name)
        if isinstance(self.ambiguity_hold_s,bool) or not math.isfinite(self.ambiguity_hold_s) or self.ambiguity_hold_s<0:
            raise ValueError('Invalid ambiguity hold')
        if isinstance(self.min_visible_pixels,bool) or not isinstance(self.min_visible_pixels,int) or self.min_visible_pixels<1:
            raise ValueError('Invalid minimum pixels')
        if self.team_region not in {'jersey','legacy'} or not all(isinstance(v,bool) for v in [self.suspend_team_conflict,self.recover_clear_crop,self.reject_side_clipped]):
            raise ValueError('Invalid team policy')
        for b in self.excluded_boxes:
            if len(b)!=4 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in b) or not 0<=b[0]<b[2]<=1 or not 0<=b[1]<b[3]<=1:
                raise ValueError('Normalized identity exclusion required')


def load_identity_crop_policy(path,source_hash):
    if not path:return None
    raw=json.loads(Path(path).read_text(encoding='utf-8'))
    if raw.get('schema_version')!='task07b-identity-crop-policy-1' or raw.get('source_video_sha256')!=source_hash:
        raise ValueError('Identity policy source/schema mismatch')
    return IdentityCropPolicy(**raw['policy'])


def overlap_fraction(a,b):
    area=max(0.,min(a[2],b[2])-max(a[0],b[0]))*max(0.,min(a[3],b[3])-max(a[1],b[1]))
    return area/((a[2]-a[0])*(a[3]-a[1]))


def jersey_region(box,width,height):
    a,b,c,d=box;w,h=c-a,d-b
    return [max(0,int(a+.15*w)),max(0,int(b+.15*h)),min(width,int(c-.15*w)),min(height,int(b+.55*h))]


class IdentityCropGuard:
    def __init__(self,policy,prototypes):
        self.policy=policy;self.prototypes=prototypes;self.until={};self.clock={}

    def reset(self):
        self.until.clear();self.clock.clear()

    def assess(self,observation,image,detections,clock_valid=True):
        tid,t=observation.track_id,observation.source_time_s
        if not math.isfinite(t) or t<self.clock.get(tid,0):raise ValueError('Invalid crop clock')
        self.clock[tid]=t
        info=dict(track_id=tid,frame_index=observation.frame_index,source_time_s=t,allowed=False,
                  reason=None,crop_xyxy=None,mask_changed=False,other_overlap=0.,color_quality={},source_detection_index=None)
        def reject(reason):
            info['reason']=reason
            return None,None,info
        if not clock_valid:return reject('untrusted_clock')
        if observation.sample_type!='observed':return reject('predicted_person')
        if observation.role=='non_player':return reject('non_player_role')
        if image is None:return reject('no_source_image')
        humans=[(i,d['xyxy']) for i,d in enumerate(detections) if d.get('class_name')=='human']
        best=max([(iou(observation.bbox,b),i) for i,b in humans],default=(0.,None))
        if best[0]<.99:return reject('no_matching_observed_human')
        info['source_detection_index']=best[1]
        height,width=image.shape[:2];region=jersey_region(observation.bbox,width,height)
        if self.policy.reject_side_clipped and (observation.bbox[0]<=1 or observation.bbox[2]>=width-1):
            return reject('side_clipped_person_ownership_uncertain')
        a,b,c,d=region;info['crop_xyxy']=region
        if c<=a or d<=b:return reject('empty_jersey_region')
        others=[box for _,box in humans if iou(observation.bbox,box)<self.policy.duplicate_iou]
        info['other_overlap']=max([overlap_fraction(region,box) for box in others],default=0.)
        if info['other_overlap']>self.policy.max_other_overlap:
            self.until[tid]=t+self.policy.ambiguity_hold_s
            return reject('ambiguous_crop_ownership')
        recently_ambiguous=t<self.until.get(tid,-1)
        if recently_ambiguous and not self.policy.recover_clear_crop:return reject('recent_ownership_ambiguity')
        crop=image[b:d,a:c].copy();visible=np.ones(crop.shape[:2],dtype=bool)
        for x1,y1,x2,y2 in self.policy.excluded_boxes:
            left,top=max(a,int(math.floor(x1*width))),max(b,int(math.floor(y1*height)))
            right,bottom=min(c,int(math.ceil(x2*width))),min(d,int(math.ceil(y2*height)))
            if left<right and top<bottom:visible[top-b:bottom-b,left-a:right-a]=False
        info['mask_changed']=not bool(visible.all());info['visible_fraction']=float(visible.mean())
        if visible.sum()<self.policy.min_visible_pixels or visible.mean()<self.policy.min_visible_fraction:
            return reject('insufficient_visible_jersey_area')
        rgb,quality=extract_jersey_rgb(crop,self.prototypes,valid_mask=visible)
        info['color_quality']=quality
        if rgb is None:return reject('recent_ownership_ambiguity' if recently_ambiguous else 'insufficient_jersey_color_support')
        if recently_ambiguous:
            fractions=sorted(quality['fractions'],reverse=True)
            # Relative color dominance tolerates exposed skin/dark jersey pixels;
            # absolute coverage alone rejected readable shirts after occlusion.
            if not (info['other_overlap']<=.4 and fractions[0]>=3*max(fractions[1],1e-6) and fractions[1]<=.15):
                return reject('recent_ownership_ambiguity')
            info['ownership_recovered_from_current_pixels']=True
        crop[~visible]=127
        info.update(allowed=True,reason='source_crop_supported',crop_sha256=hashlib.sha256(crop.tobytes()).hexdigest(),
                    score_kind='geometric_and_color_cues_not_person_verification')
        return crop,rgb,info
