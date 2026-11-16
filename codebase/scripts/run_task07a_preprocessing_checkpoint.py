#!/usr/bin/env python3
"""GT-free input-shape probe and controlled square-resolution candidate run."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import sys
import time

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from basketball_scoreboard.config import APPROVED_MODEL_ID,ModelConfig
from basketball_scoreboard.detector import private_library_output
from basketball_scoreboard.preprocessing_diagnostics import observe_cpu_session,serializable_metadata,letterbox_image,unletterbox_xyxy
from basketball_scoreboard.spatial_io import file_hash,new_output,write_json
from basketball_scoreboard.tiled_detection import TiledBallDetector,tile_boxes
from basketball_scoreboard.contracts import DetectionRecord
from basketball_scoreboard.ball import center,iou
from basketball_scoreboard.video import VideoReader


def same_predictions(a,b):
    key=lambda d:(d.class_name,tuple(d.xyxy),d.confidence)
    a,b=sorted(a,key=key),sorted(b,key=key)
    return len(a)==len(b) and all(x.class_name==y.class_name and
        np.allclose(x.xyxy,y.xyxy,atol=1e-6,rtol=0) and abs(x.confidence-y.confidence)<=1e-6 for x,y in zip(a,b))


def infer_region(detector,image,size,trace_metadata=False):
    metadata=None
    if trace_metadata:
        options={'image_size':tuple(size)} if size is not None else {}
        with private_library_output():
            tensor,meta=detector.model.pre_process(image,**options)
        metadata=dict(inspected_tensor_shape=list(tensor.shape),metadata=serializable_metadata(meta),
                      scope='SDK pre_process with same source image/options; independently checked against real ONNX feeds')
        del tensor
    with observe_cpu_session(detector.model) as feeds:
        records,ms=detector.detect(image,image_size=size)
    if not feeds:raise ValueError('ONNX execution input was not observed')
    shapes=[shape for call in feeds for shape in call.values()]
    if metadata and any(shape!=metadata['inspected_tensor_shape'] for shape in shapes):
        raise ValueError('Inspected tensor differs from real network feed')
    return records,ms,dict(source_wh=[image.shape[1],image.shape[0]],requested_wh=size,
                          network_feeds=feeds,preprocessing=metadata)


def infer_tiled(detector,image,size,settings,trace_metadata=False,pre_resize_mode='sdk-stretch'):
    height,width=image.shape[:2]
    regions=[(0,0,width,height)]+tile_boxes(width,height,settings['grid'],settings['overlap'])
    balls=[];traces=[];elapsed=0.
    for x1,y1,x2,y2 in regions:
        region=image[y1:y2,x1:x2];transform=None
        if pre_resize_mode=='external-letterbox':
            if size!=[640,640]:raise ValueError('Controlled letterbox comparison requires 640 square')
            region,transform=letterbox_image(region,640)
        elif pre_resize_mode!='sdk-stretch':raise ValueError('Unknown controlled preprocessing')
        records,ms,trace=infer_region(detector,region,size,trace_metadata)
        trace['external_letterbox']=transform
        elapsed+=ms;trace['region_xyxy']=[x1,y1,x2,y2];traces.append(trace)
        for d in records:
            if d.class_name=='ball':
                box=unletterbox_xyxy(d.xyxy,transform) if transform else d.xyxy
                if box is None:continue
                a,b,c,e=box
                mapped=DetectionRecord([a+x1,b+y1,c+x1,e+y1],d.class_id,'ball',d.confidence,class_mapping=detector.class_mapping)
                mapped.validate_bounds((width,height));balls.append(mapped)
    selected=[]
    for d in sorted(balls,key=lambda r:(-r.confidence,r.xyxy)):
        x,y=center(d.xyxy)
        if any(a<=x/width<=c and b<=y/height<=e for a,b,c,e in settings['excluded_boxes']):continue
        if not any(iou(d.xyxy,old.xyxy)>=.35 for old in selected):selected.append(d)
    return [asdict(d) for d in selected],elapsed,traces


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video',required=True);parser.add_argument('--settings',required=True)
    parser.add_argument('--output-dir',required=True);parser.add_argument('--stage',choices=['probe','compare'],required=True)
    args=parser.parse_args();output=None
    try:
        settings=json.loads(Path(args.settings).read_text(encoding='utf-8'))
        if settings['schema_version']!='task07a-preprocessing-checkpoint-1' or settings['model_id']!=APPROVED_MODEL_ID:
            raise ValueError('Unapproved experiment/model')
        source_hash=file_hash(args.video)
        if source_hash!=settings['source_video_sha256']:raise ValueError('Source hash differs')
        if settings['frame_step']!=8:raise ValueError('Use fixed source-only sampling every 8 frames')
        output=new_output(args.output_dir,[args.video,args.settings])
        snapshot=output/'source-snapshot';snapshot.mkdir()
        sources=[Path(__file__),*(ROOT/'src/basketball_scoreboard').glob('*.py')]
        hashes={p.relative_to(ROOT).as_posix():file_hash(p) for p in sources}
        for p in sources:
            target=snapshot/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        write_json(output/'run.json',dict(status='running',stage=args.stage,settings=settings,
            source_sha256=hashes,video_sha256=source_hash,settings_sha256=file_hash(args.settings),
            source_sampling='frame_index % 8 == 0 across full clip; no GT file loaded'))
        config=ModelConfig(confidence_threshold=settings['confidence'],max_edge=1920)
        tiled=TiledBallDetector(config,grid=settings['grid'],overlap=settings['overlap'],
            excluded_boxes=settings['excluded_boxes'],onnx_threads=settings['onnx_threads'])
        detector=tiled.base;detector.warmup()
        sdk_config=detector.model._inference_config
        metadata=dict(runtime=tiled.get_runtime_info(),onnx_input_shapes=[x.shape for x in detector.model._session.get_inputs()],
            onnx_weights_sha256=file_hash(detector.model._session._model_path),
            sdk_network_input=serializable_metadata(sdk_config.network_input),
            sdk_image_preprocessing=serializable_metadata(sdk_config.image_pre_processing))
        write_json(output/'runtime.json',metadata)
        started=time.perf_counter();count=0;times={p['name']:0. for p in settings['profiles']}
        if args.stage=='probe':
            with VideoReader(args.video) as reader:frame,image=next(reader.frames())
            rows={};traces={}
            for name,size in [('default',None),('explicit-640',[640,640]),('square-960',[960,960])]:
                records,ms,trace=infer_region(detector,image,size,True)
                rows[name]=records;traces[name]=trace
            if not same_predictions(rows['default'],rows['explicit-640']):
                raise ValueError('Default/explicit640 outputs differ; baseline not equivalent')
            write_json(output/'probe.json',dict(frame_index=frame.frame_index,source_time_s=frame.source_time_s,
                default_explicit640_equivalent=True,traces=traces,source_sample='first decoded frame, not GT-selected'))
            count=1
        else:
            handles={p['name']:(output/(p['name']+'.jsonl')).open('x',encoding='utf-8') for p in settings['profiles']}
            try:
                with VideoReader(args.video) as reader:
                    for frame,image in reader.frames():
                        if frame.frame_index%settings['frame_step']:continue
                        for profile in settings['profiles']:
                            records,ms,traces=infer_tiled(detector,image,profile['image_size'],settings,count==0,
                                pre_resize_mode=profile.get('pre_resize_mode','sdk-stretch'))
                            times[profile['name']]+=ms/1000
                            row=dict(frame_index=frame.frame_index,source_time_s=frame.source_time_s,original_wh=[image.shape[1],image.shape[0]],
                                timestamp_status=frame.timestamp_status,ball_candidates=records,network_traces=traces,model_call_ms=ms)
                            handles[profile['name']].write(json.dumps(row,allow_nan=False)+'\n');handles[profile['name']].flush()
                        count+=1
                        if count%4==0:
                            write_json(output/'progress.json',dict(status='running',sampled_frames=count,last_frame=frame.frame_index))
                            print('Sampled',count,'frames; last source frame',frame.frame_index,flush=True)
            finally:
                for handle in handles.values():handle.close()
        run=json.loads((output/'run.json').read_text())
        run.update(status='completed',sampled_frames=count,detection_time_by_profile_s=times,
            processing_wall_s=time.perf_counter()-started,scope='source-sampled candidate diagnostics only; no tracking/OCR/acceptance')
        write_json(output/'run.json',run)
        print('Completed',args.stage,count,'sampled frames');return 0
    except Exception as error:
        if output:
            run=json.loads((output/'run.json').read_text()) if (output/'run.json').exists() else {}
            run.update(status='failed',error_class=type(error).__name__);write_json(output/'run.json',run)
        print('Checkpoint failed ('+type(error).__name__+')',file=sys.stderr);return 1


if __name__=='__main__':sys.exit(main())
