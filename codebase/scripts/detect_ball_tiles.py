#!/usr/bin/env python3
"""Generate normal G03 detection artifacts with optional local ball tiling."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from basketball_scoreboard.app import run_pipeline
from basketball_scoreboard.config import APPROVED_MODEL_ID, PipelineConfig
from basketball_scoreboard.tiled_detection import TiledBallDetector


def load_settings(path):
    settings_path=Path(path).resolve()
    settings=json.loads(settings_path.read_text(encoding="utf-8"))
    if not isinstance(settings,dict):
        raise ValueError("Task07A settings must be a JSON object")
    allowed={"schema_version","model_id","confidence","max_edge","grid","overlap",
             "tile_scale","onnx_threads","excluded_boxes"}
    required={"schema_version","model_id","confidence","max_edge","grid","overlap","tile_scale"}
    if set(settings)-allowed or required-set(settings) or settings.get("schema_version")!="task07a-detection-1":
        raise ValueError("Invalid Task07A settings schema")
    if settings.get("model_id")!=APPROVED_MODEL_ID:
        raise ValueError("Task07A settings must use the approved model")
    confidence=settings.get("confidence")
    if isinstance(confidence,bool) or not isinstance(confidence,(int,float)) or not math.isfinite(confidence) or not 0 < confidence <= 1:
        raise ValueError("Invalid detector confidence")
    max_edge=settings.get("max_edge")
    if isinstance(max_edge,bool) or not isinstance(max_edge,int) or not 320 <= max_edge <= 4096:
        raise ValueError("Invalid detector max edge")
    if not isinstance(settings.get("grid"),int) or isinstance(settings.get("grid"),bool):
        raise ValueError("Invalid tile grid")
    if isinstance(settings.get("overlap"),bool) or not isinstance(settings.get("overlap"),(int,float)) or not math.isfinite(settings["overlap"]):
        raise ValueError("Invalid tile overlap")
    if not isinstance(settings.get("tile_scale"),(int,float)) or isinstance(settings.get("tile_scale"),bool) or not math.isfinite(settings["tile_scale"]):
        raise ValueError("Invalid tile scale")
    if "onnx_threads" in settings and settings["onnx_threads"] is not None and (
            isinstance(settings["onnx_threads"],bool) or not isinstance(settings["onnx_threads"],int)):
        raise ValueError("Invalid ONNX thread count")
    if not isinstance(settings.get("excluded_boxes",[]),list):
        raise ValueError("Invalid excluded boxes")
    return settings,hashlib.sha256(settings_path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--video",required=True);p.add_argument("--output-dir",required=True)
    p.add_argument("--settings",help="Immutable JSON experiment settings")
    p.add_argument("--confidence",type=float,default=.15);p.add_argument("--grid",type=int,default=2)
    p.add_argument("--tile-scale",type=float,default=1.0,help="Upscale each ball crop before inference (1-4)")
    p.add_argument("--max-edge",type=int,default=1920,help="Maximum detector input edge; must accommodate scaled crops")
    p.add_argument("--onnx-threads",type=int)
    p.add_argument("--exclude-boxes",default="[]",help="JSON list of normalized broadcast-overlay boxes")
    args=p.parse_args()
    try:
        settings,settings_hash=load_settings(args.settings) if args.settings else (None,None)
        confidence=settings["confidence"] if settings else args.confidence
        grid=settings["grid"] if settings else args.grid
        overlap=settings["overlap"] if settings else .2
        tile_scale=settings["tile_scale"] if settings else args.tile_scale
        max_edge=settings["max_edge"] if settings else args.max_edge
        onnx_threads=settings.get("onnx_threads") if settings else args.onnx_threads
        boxes=settings.get("excluded_boxes",[]) if settings else json.loads(args.exclude_boxes)
        config=PipelineConfig.default()
        config.model.confidence_threshold=confidence;config.model.max_edge=max_edge
        factory=lambda cfg,env_path:TiledBallDetector(
            cfg,env_path=env_path,grid=grid,overlap=overlap,excluded_boxes=boxes,
            onnx_threads=onnx_threads,tile_scale=tile_scale)
        result=run_pipeline(args.video,args.output_dir,config,export_video=False,detector_factory=factory)
        if settings:
            run_path=Path(result["export"]["run_json_path"])
            metadata=json.loads(run_path.read_text(encoding="utf-8"))
            metadata["experiment_settings"]={**settings,"settings_sha256":settings_hash}
            run_path.write_text(json.dumps(metadata,indent=2)+"\n",encoding="utf-8")
        print(f"Completed {result['counts']['total_frames_read']} frames; same-model tiled ball inference")
        return 0
    except Exception as error:
        print(f"Tiled detection failed ({type(error).__name__})",file=sys.stderr);return 1


if __name__=="__main__":sys.exit(main())
