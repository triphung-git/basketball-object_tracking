"""Per-video image ROI and operational exclusions; no homography or GT access."""
import json
import math
from decimal import Decimal,ROUND_FLOOR,ROUND_CEILING
from pathlib import Path

import cv2
import numpy as np


def validate_image_polygon(polygon):
    if (not isinstance(polygon,list) or len(polygon)<3 or
            any(not isinstance(p,(list,tuple)) or len(p)!=2 or
                not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) and 0<=x<=1 for x in p)
                for p in polygon)):
        raise ValueError('Normalized image polygon required')
    if abs(cv2.contourArea(np.asarray(polygon,dtype=np.float32)))<.01:
        raise ValueError('Degenerate image polygon')
    return polygon


def load_ball_roi(path, source_hash):
    """An optional aerial search region, separate from player footpoint ROI."""
    if not path:return None
    raw=json.loads(Path(path).read_text(encoding='utf-8'))
    if raw.get('source_video_sha256')!=source_hash:
        raise ValueError('Ball search policy source mismatch')
    polygon=raw.get('ball_image_roi_normalized')
    return validate_image_polygon(polygon) if polygon is not None else None


def normalize_interval(interval):
    """Align operational boundaries to G03 microsecond clock, conservatively."""
    a,b=interval['start_time_s'],interval['end_time_s']
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in (a,b)) or not 0<=a<=b:
        raise ValueError('Invalid operational interval')
    tick=Decimal('1000000')
    start=float((Decimal(str(a))*tick).to_integral_value(rounding=ROUND_FLOOR)/tick)
    end=start if a==b else float((Decimal(str(b))*tick).to_integral_value(rounding=ROUND_CEILING)/tick)
    return {**interval,'start_time_s':start,'end_time_s':end}


def load_tracking_policy(path, source_hash):
    if not path:return None
    raw=json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("source_video_sha256") != source_hash:
        raise ValueError("Tracking policy source mismatch")
    polygon=raw.get("image_roi_normalized",[])
    if len(polygon)<3 or any(len(p)!=2 or not all(math.isfinite(x) and 0<=x<=1 for x in p) for p in polygon):
        raise ValueError("Normalized image polygon required")
    if abs(cv2.contourArea(np.asarray(polygon,dtype=np.float32)))<.01:
        raise ValueError("Degenerate tracking ROI")
    for item in raw.get("intervals",[]):
        a,b=item["start_time_s"],item["end_time_s"]
        if not all(math.isfinite(x) for x in (a,b)) or not 0<=a<=b or not item.get("reason"):
            raise ValueError("Invalid tracking exclusion")
    raw['intervals']=[normalize_interval(i) for i in raw.get('intervals',[])]
    return raw


def in_image_roi(policy, footpoint, dimensions):
    if policy is None:return True
    width,height=dimensions
    point=(footpoint[0]/width,footpoint[1]/height)
    return cv2.pointPolygonTest(np.asarray(policy["image_roi_normalized"],dtype=np.float32),point,False)>=0


def interval_flags(policy, previous_time, time_s):
    intervals=[normalize_interval(i) for i in policy.get("intervals",[])] if policy else []
    excluded=any(i["start_time_s"]<=time_s<i["end_time_s"] for i in intervals)
    boundary=any(previous_time<edge<=time_s for i in intervals for edge in (i["start_time_s"],i["end_time_s"]))
    return excluded,boundary
