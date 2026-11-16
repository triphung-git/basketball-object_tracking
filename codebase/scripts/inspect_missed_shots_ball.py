import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ball_tracks_path = ROOT / "outputs/remaining-tasks-20261115/04A/run/baseline/ball_tracks.jsonl"

with ball_tracks_path.open() as f:
    ball_frames = [json.loads(line) for line in f if line.strip()]

print(f"Total ball frames: {len(ball_frames)}")
if ball_frames:
    print("Keys in frame 0:", ball_frames[0].keys())
    print("Sample frame 100:", ball_frames[100])

w1 = [b for b in ball_frames if 3.0 <= b.get("source_time_s", 0) <= 4.5]
print("\n--- Window 1 (t=3.0 to 4.5s) ---")
for b in w1:
    print(f"f={b.get('frame_index')}, t={b.get('source_time_s'):.3f}s, sample={b.get('sample_type')}, center={b.get('center_image')}")

# Window 2: t=24.5 to 26.5s
w2 = [b for b in ball_frames if 24.5 <= b.get("source_time_s", 0) <= 26.5]
print("\n--- Window 2 (t=24.5 to 26.5s) ---")
for b in w2:
    print(f"f={b.get('frame_index')}, t={b.get('source_time_s'):.3f}s, sample={b.get('sample_type')}, center={b.get('center_image')}")
