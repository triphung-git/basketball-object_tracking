import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from basketball_scoreboard.court import CourtConfig, CourtModel

cfg = CourtConfig.from_json_file(str(ROOT / "configs/courts/vt_development_court.json"))
m = CourtModel(cfg)
m.calibrate()

tracks_path = ROOT / "outputs/remaining-tasks-20261115/04A/run/baseline/tracked_observations.jsonl"
with tracks_path.open() as f:
    tracks = [json.loads(line) for line in f if line.strip()]

shooter_obs = [
    o for o in tracks
    if o.get("track_id") == "trk_session_vietnam_tonga_dev_0033"
    and 8.5 <= o.get("source_time_s", 0) <= 10.0
]

print(f"Found {len(shooter_obs)} shooter obs for trk_session_vietnam_tonga_dev_0033")
for o in shooter_obs[:10]:
    fp = o.get("footpoint_image")
    t = o.get("source_time_s")
    court_xy = m.project_image_to_court(fp)
    if court_xy:
        dist = math.dist(court_xy, (0.0, 1.575))
        val = 2 if dist > 6.75 else 1
        print(f"t={t:.3f}s: img={fp} -> court=({court_xy[0]:.2f}m, {court_xy[1]:.2f}m), dist={dist:.2f}m -> {val}PT")
    else:
        print(f"t={t:.3f}s: img={fp} -> court=None")
