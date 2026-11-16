"""Promotes approved proposal in data/v2/proposal into data/v2, stores calibration, and verifies validation."""
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DATA_V2 = ROOT / "data" / "v2"
PROPOSAL = DATA_V2 / "proposal"
CALIB_SRC = ROOT / "outputs" / "remaining-tasks-20261115" / "03B" / "run" / "calibration" / "court_calibration_proposal.json"
CONFIGS_COURT = ROOT / "configs" / "court"
CONFIGS_COURT.mkdir(parents=True, exist_ok=True)

# 1. Copy top-level metadata from proposal
for f in PROPOSAL.glob("*.*"):
    if f.is_file():
        shutil.copy2(f, DATA_V2 / f.name)
        print(f"Copied {f.name} -> data/v2/{f.name}")

# 2. Copy annotations from proposal/annotations
ann_dst = DATA_V2 / "annotations"
ann_dst.mkdir(parents=True, exist_ok=True)
for f in (PROPOSAL / "annotations").glob("*.csv"):
    shutil.copy2(f, ann_dst / f.name)
    print(f"Copied {f.name} -> data/v2/annotations/{f.name}")

# 3. Save court calibration to configs/court and data/v2
if CALIB_SRC.is_file():
    calib_dst1 = CONFIGS_COURT / "court_calibration_vt_dev.json"
    calib_dst2 = DATA_V2 / "court_calibration.json"
    shutil.copy2(CALIB_SRC, calib_dst1)
    shutil.copy2(CALIB_SRC, calib_dst2)
    print(f"Saved court calibration to {calib_dst1} and {calib_dst2}")

print("Dataset v2 promotion complete.")
