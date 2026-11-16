"""Verify the downloaded raw checkpoint using an isolated Ultralytics environment."""
import argparse
import json
from pathlib import Path
import sys
from prepare_task07a_finetune import class_names, sha256

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    import torch
    import ultralytics
    from ultralytics import YOLO
    model = YOLO(args.checkpoint)
    names = class_names(model.names)
    # Exercise actual CPU inference without consuming target media/GT.
    import numpy as np
    results = model.predict(np.zeros((640,640,3),dtype=np.uint8), device='cpu', verbose=False)
    report = dict(status='checkpoint_load_and_synthetic_inference_passed',
                  checkpoint=str(Path(args.checkpoint).resolve()), sha256=sha256(args.checkpoint),
                  bytes=Path(args.checkpoint).stat().st_size, classes=names, task=model.task,
                  parameters=sum(p.numel() for p in model.model.parameters()),
                  torch=torch.__version__, ultralytics=ultralytics.__version__,
                  python=sys.version, cuda_available=torch.cuda.is_available(),
                  synthetic_results=len(results), training_started=False,
                  synthetic_inference_is_accuracy_evidence=False)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
