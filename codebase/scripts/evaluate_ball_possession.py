#!/usr/bin/env python3
"""Evaluate immutable Task07 outputs against an explicit reviewed GT packet."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from basketball_scoreboard.ball_pipeline import jsonl
from basketball_scoreboard.possession_evaluation import evaluate,apply_acceptance_profile
from basketball_scoreboard.spatial_io import file_hash, new_output, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--ground-truth", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--acceptance-profile")
    args = parser.parse_args()
    output = None
    try:
        source = Path(args.run_dir)
        meta = json.loads((source/"run.json").read_text(encoding="utf-8"))
        if meta["status"] != "completed":
            raise ValueError("Only completed task07 runs may be evaluated")
        packet = json.loads(Path(args.ground_truth).read_text(encoding="utf-8"))
        result = dict(balls=jsonl(source/"ball_tracks.jsonl"), controls=jsonl(source/"ball_control.jsonl"),
                      passes=jsonl(source/"passes.jsonl"))
        metrics = evaluate(result, packet, meta["source_fingerprint_sha256"],
                           meta["config"]["control"]["max_gap_s"], args.diagnostic)
        if args.acceptance_profile:
            profile=json.loads(Path(args.acceptance_profile).read_text(encoding='utf-8'))
            metrics=apply_acceptance_profile(metrics,profile,meta,packet,result)
            metrics['acceptance_profile_sha256']=file_hash(args.acceptance_profile)
        output = new_output(args.output_dir, [source, args.ground_truth,args.acceptance_profile])
        metrics.update(status="completed", ground_truth_sha256=file_hash(args.ground_truth),
                       predictions_sha256={name:file_hash(source/name) for name in ("run.json", "ball_tracks.jsonl", "ball_control.jsonl", "passes.jsonl")})
        write_json(output/"evaluation.json", metrics)
        print(json.dumps(metrics, allow_nan=False))
        return 0
    except Exception as error:
        if output:
            write_json(output/"evaluation.json", dict(status="failed", error_class=type(error).__name__))
        print(f"Evaluation failed ({type(error).__name__})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
