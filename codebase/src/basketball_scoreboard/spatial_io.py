"""Local artifact validation shared by tracking and projection CLIs; no model loading."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
from pathlib import Path

from .app import assert_development_video_allowed
from .config import APPROVED_MODEL_ID


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def load_spatial_input(input_path, run_path, court=None, tracked=False, diagnostic=False, development_authorization=None):
    if run_path is None:
        raise ValueError('Source run metadata required')
    run = json.loads(Path(run_path).read_text(encoding='utf-8'))
    if run.get('status') != 'completed':
        raise ValueError('Only completed source runs may be consumed')
    if run.get('is_synthetic'):
        if not diagnostic:
            raise ValueError('Synthetic source runs require diagnostic mode')
    elif run.get('runtime',{}).get('model_id') != APPROVED_MODEL_ID:
        raise ValueError('Source run must identify the approved detector')
    sha = run.get('source_fingerprint_sha256','')
    if len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
        raise ValueError('Source fingerprint required')
    assert_development_video_allowed(sha, authorization_path=development_authorization)
    wh = (run['video_metadata']['width'],run['video_metadata']['height'])
    if any(not isinstance(v,int) or isinstance(v,bool) or v <= 0 for v in wh):
        raise ValueError('Source dimensions must be positive integers')
    if court:
        if tuple(court.original_image_wh) != wh:
            raise ValueError('Calibration dimensions mismatch')
        if court.source_video_hash and court.source_video_hash != sha:
            raise ValueError('Calibration source fingerprint mismatch')
    records = [json.loads(line) for line in Path(input_path).read_text(encoding='utf-8').splitlines() if line.strip()]
    if not records:
        raise ValueError('Empty spatial input')
    prior_time, prior_index, seen = -1., -1, set()
    for row in records:
        index, time = row['frame_index'],row['source_time_s']
        if not isinstance(index,int) or index < 0 or not math.isfinite(time) or time < 0:
            raise ValueError('Invalid frame index/time')
        if row.get('video_id') != run['video_id']:
            raise ValueError('Input video ID differs from source run')
        if row.get('timestamp_status') not in {'valid','repaired','estimated','irregular'}:
            raise ValueError('Unknown timestamp status')
        if tracked:
            if index < prior_index or time < prior_time or (index == prior_index and time != prior_time):
                raise ValueError('Out-of-order trajectory frames/timestamps')
            if row.get('source_fingerprint_sha256') != sha or row.get('source_run_id') != run['run_id']:
                raise ValueError('Trajectory source run/fingerprint mismatch')
            if court and (row.get('camera_id') != court.camera_id or row.get('segment_id') != court.segment_id):
                raise ValueError('Trajectory camera/segment mismatch; use separate calibrated segments')
            key = row['observation_id']
            if key in seen:
                raise ValueError('Duplicate observation ID')
            seen.add(key)
            prior_time,prior_index = time,index
        else:
            if tuple(row['original_wh']) != wh or index <= prior_index or time <= prior_time:
                raise ValueError('Frame dimensions/order/timestamps mismatch')
            if court and row.get('segment_id',court.segment_id) != court.segment_id:
                raise ValueError('Multiple segments require separate runs')
            for det in row.get('detections',[]):
                cid, name = det.get('class_id'),det.get('class_name')
                mapping = run.get('class_mapping',{})
                if mapping and mapping.get(str(cid)) != name:
                    raise ValueError('Runtime class mapping mismatch')
                box, conf = det['xyxy'],det['confidence']
                if (len(box) != 4 or not all(math.isfinite(v) for v in box) or not math.isfinite(conf)
                        or not 0 <= conf <= 1 or not 0 <= box[0] < box[2] <= wh[0]
                        or not 0 <= box[1] < box[3] <= wh[1]):
                    raise ValueError('Invalid detection coordinates/confidence')
            prior_time,prior_index = time,index
    return run,records


def new_output(path, sources=()):
    output = Path(path).resolve()
    if any(Path(source).resolve().is_relative_to(output) for source in sources if source):
        raise ValueError('Output directory cannot contain input sources')
    output.mkdir(parents=True,exist_ok=False)
    return output


def write_json(path, value):
    Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def emit_observations(path, observations):
    with Path(path).open('x',encoding='utf-8') as handle:
        for obs in observations:
            handle.write(obs.to_json()+'\n')


def runtime_snapshot(script_path):
    root = Path(__file__).resolve().parents[2]
    files = [Path(script_path), *(root/'src/basketball_scoreboard').glob('*.py')]
    return dict(implementation_revision='task56-acceptance-20261103',
                source_sha256={p.relative_to(root).as_posix():file_hash(p) for p in files},
                packages={name:importlib.metadata.version(name) for name in ('numpy','av','scipy','matplotlib','opencv-python')})
