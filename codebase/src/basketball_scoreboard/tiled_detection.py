"""Optional multi-crop ball inference using the SAME approved local detector."""
import math

import cv2

from .players import compute_iou as iou
from .contracts import DetectionRecord
from .detector import ObjectDetector


def tile_boxes(width, height, grid=2, overlap=.2):
    if not isinstance(grid,int) or isinstance(grid,bool) or not 1 <= grid <= 3:
        raise ValueError("Tile grid must be 1-3")
    if not math.isfinite(overlap) or not 0 <= overlap < .5:
        raise ValueError("Invalid tile overlap")
    tw,th=math.ceil(width/(grid-(grid-1)*overlap)),math.ceil(height/(grid-(grid-1)*overlap))
    return [(round(ix*(width-tw)/max(1,grid-1)),round(iy*(height-th)/max(1,grid-1)),
             round(ix*(width-tw)/max(1,grid-1))+tw,round(iy*(height-th)/max(1,grid-1))+th)
            for iy in range(grid) for ix in range(grid)]


class TiledBallDetector:
    def __init__(self, config, env_path=None, grid=2, overlap=.2, excluded_boxes=(), onnx_threads=None,
                 tile_scale=1.0):
        tile_boxes(100,100,grid,overlap)
        if isinstance(tile_scale, bool) or not isinstance(tile_scale, (int, float)) or not math.isfinite(tile_scale) or not 1 <= tile_scale <= 4:
            raise ValueError("Tile scale must be finite and in [1, 4]")
        for box in excluded_boxes:
            if len(box)!=4 or not all(math.isfinite(x) for x in box) or not (0<=box[0]<box[2]<=1 and 0<=box[1]<box[3]<=1):
                raise ValueError("Normalized exclusion box required")
        self.base=ObjectDetector(config,env_path=env_path)
        self.onnx_threads=onnx_threads
        if onnx_threads is not None:
            if isinstance(onnx_threads,bool) or not isinstance(onnx_threads,int) or not 1<=onnx_threads<=8:
                raise ValueError("ONNX CPU threads must be 1-8")
            # Reuse the SDK-verified local model file; only CPU session scheduling changes.
            import onnxruntime as ort
            options=ort.SessionOptions();options.intra_op_num_threads=onnx_threads;options.inter_op_num_threads=1
            original=self.base.model._session
            self.base.model._session=ort.InferenceSession(original._model_path,sess_options=options,providers=['CPUExecutionProvider'])
        self.grid,self.overlap,self.excluded_boxes,self.tile_scale=grid,overlap,list(excluded_boxes),float(tile_scale)

    def warmup(self):
        return self.base.warmup()

    def get_runtime_info(self):
        from pathlib import Path
        import hashlib
        return {**self.base.get_runtime_info(),"tiling_implementation_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"ball_tiling":dict(grid=self.grid,overlap=self.overlap,
                excluded_boxes_normalized=self.excluded_boxes,humans_source="full_frame_only",
                dedup_iou=.35,coordinate_system="original_frame_pixels",onnx_intra_op_threads=self.onnx_threads,
                tile_scale=self.tile_scale)}

    def detect(self, image, confidence_threshold=None):
        records,elapsed=self.base.detect(image,confidence_threshold)
        height,width=image.shape[:2]
        balls=[r for r in records if r.class_name=="ball"]
        others=[r for r in records if r.class_name!="ball"]
        for x1,y1,x2,y2 in tile_boxes(width,height,self.grid,self.overlap):
            crop=image[y1:y2,x1:x2]
            if self.tile_scale != 1.0:
                crop=cv2.resize(crop,None,fx=self.tile_scale,fy=self.tile_scale,interpolation=cv2.INTER_CUBIC)
            scale_x=crop.shape[1]/(x2-x1)
            scale_y=crop.shape[0]/(y2-y1)
            local,ms=self.base.detect(crop,confidence_threshold)
            elapsed+=ms
            for record in local:
                if record.class_name!="ball":continue
                a,b,c,d=record.xyxy
                mapped=DetectionRecord([a/scale_x+x1,b/scale_y+y1,
                                        c/scale_x+x1,d/scale_y+y1],
                                       record.class_id,"ball",record.confidence,
                                       class_mapping=self.base.class_mapping)
                mapped.validate_bounds((width,height));balls.append(mapped)
        selected=[]
        for record in sorted(balls,key=lambda r:(-r.confidence,r.xyxy)):
            a,b,c,d=record.xyxy
            x,y=(a+c)/2,(b+d)/2
            if any(a<=x/width<=c and b<=y/height<=d for a,b,c,d in self.excluded_boxes):continue
            if not any(iou(record.xyxy,old.xyxy)>=.35 for old in selected):selected.append(record)
        return others+selected,elapsed
