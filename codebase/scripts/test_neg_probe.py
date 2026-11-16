#!/usr/bin/env python3
"""Test extracting and inferring one negative segment on GPU."""
import time
from pathlib import Path
import cv2
import numpy as np
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
VIDEO_PATH = ROOT / "assets_test/vietnam-tonga.mp4"
MODEL_PATH = ROOT / "models/checkpoints/task07a-original/best.pt"

cap = cv2.VideoCapture(str(VIDEO_PATH))
fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
print(f"Video FPS: {fps}")

# neg_miss_001: 42.0 to 46.5s
start_s, end_s = 42.0, 46.5
start_f = int(start_s * fps)
end_f = int(end_s * fps)
total_frames = end_f - start_f
print(f"Target frames: {start_f} to {end_f} ({total_frames} frames)")

cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
frames = []
t0 = time.perf_counter()
for f in range(start_f, end_f):
    ret, frame = cap.read()
    if not ret:
        break
    frames.append(frame)
cap.release()
print(f"Decoded {len(frames)} frames in {time.perf_counter() - t0:.2f}s")

model = YOLO(str(MODEL_PATH))
t1 = time.perf_counter()
results = model.predict(frames, device="cuda:0", imgsz=640, batch=16, verbose=False)
t_infer = time.perf_counter() - t1
print(f"Inference on {len(frames)} frames: {t_infer:.2f}s ({len(frames)/t_infer:.1f} FPS)")
print(f"Sample detections in frame 0: {len(results[0].boxes)} boxes")
