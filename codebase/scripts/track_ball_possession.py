#!/usr/bin/env python3
"""Run Task07 on cached detection/player outputs; no GT or model loading."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from basketball_scoreboard.ball_pipeline import run_ball_pipeline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("detections", "run-json", "tracks", "tracking-run", "output-dir"):
        parser.add_argument("--"+name, required=True)
    for name in ("config", "identity-mappings", "exclusions", "video", "development-authorization"):
        parser.add_argument("--"+name)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    try:
        summary = run_ball_pipeline(**vars(args))
        print(f"Completed {summary['frames']} frames; ball={summary['ball_samples']}; control={summary['control_states']}")
        return 0
    except Exception as error:
        print(f"Task07 failed ({type(error).__name__}); inspect inputs or sanitized run.json", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
