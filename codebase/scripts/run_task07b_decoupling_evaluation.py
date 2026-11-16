#!/usr/bin/env python3
"""Run paired evaluation of actor decoupling, candidate team-conflict-reset, and baseline."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from basketball_scoreboard.spatial_io import file_hash, new_output, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', default=str(ROOT / 'outputs/task07b-decoupling-20261107'))
    args = parser.parse_args()
    
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    python = str(ROOT / '.venv/Scripts/python.exe')
    detections = str(ROOT / 'outputs/task07-vietnam-tonga-segments-20261104/development-tiled/detections.jsonl')
    run_json = str(ROOT / 'outputs/task07-vietnam-tonga-segments-20261104/development-tiled/run.json')
    roster = str(ROOT / 'configs/rosters/vietnam_tonga.json')
    video = str(ROOT / 'outputs/task07-vietnam-tonga-segments-20261104/media/vt_development.mp4')
    ocr_cache = str(ROOT / 'outputs/task07-vietnam-tonga-segments-20261104/development-tracking-v2')
    policy = str(ROOT / 'outputs/task07-vietnam-tonga-segments-20261104/vt_development-policy-ball-roi-v4.json')
    gt = str(ROOT / 'data/matches/vietnam_tonga/reviewed-vt_development-v2.json')
    acceptance_profile = str(ROOT / 'configs/evaluation/task07_vietnam_tonga.json')
    guard_config = str(ROOT / 'configs/task07b/identity-recovery-jersey.json')
    ball_config = str(ROOT / 'configs/ball-possession-vietnam-tonga-spatial.json')
    
    t0 = time.perf_counter()
    
    # 1. Candidate tracking (jersey + reset-on-team-conflict)
    print("\n[1/9] Running Candidate Player Tracking...", flush=True)
    cmd_cand_track = [
        python, str(ROOT / 'scripts/track_players.py'),
        '--detections', detections,
        '--run-json', run_json,
        '--roster-config', roster,
        '--video', video,
        '--enable-ocr',
        '--ocr-upscale', '3',
        '--jersey-evidence-ttl-s', '6',
        '--color-method', 'masked',
        '--jersey-evidence-cache', ocr_cache,
        '--tracking-policy', policy,
        '--team-crop-region', 'jersey',
        '--reset-on-team-conflict',
        '--output-dir', str(out_dir / 'candidate-tracking')
    ]
    subprocess.run(cmd_cand_track, check=True)
    
    # 2. Candidate ball tracking (with debug video & timeline)
    print("\n[2/9] Running Candidate Ball Possession Tracking...", flush=True)
    cmd_cand_ball = [
        python, str(ROOT / 'scripts/track_ball_possession.py'),
        '--detections', detections,
        '--run-json', run_json,
        '--tracks', str(out_dir / 'candidate-tracking/tracked_observations.jsonl'),
        '--tracking-run', str(out_dir / 'candidate-tracking/run.json'),
        '--identity-mappings', str(out_dir / 'candidate-tracking/identity_mappings.json'),
        '--exclusions', policy,
        '--config', ball_config,
        '--video', video,
        '--output-dir', str(out_dir / 'candidate-ball')
    ]
    subprocess.run(cmd_cand_ball, check=True)
    
    # 3. Candidate evaluation
    print("\n[3/9] Evaluating Candidate Ball Possession...", flush=True)
    cmd_cand_eval = [
        python, str(ROOT / 'scripts/evaluate_ball_possession.py'),
        '--run-dir', str(out_dir / 'candidate-ball'),
        '--ground-truth', gt,
        '--acceptance-profile', acceptance_profile,
        '--output-dir', str(out_dir / 'candidate-evaluation'),
        '--diagnostic'
    ]
    subprocess.run(cmd_cand_eval, check=True)
    
    # 4. Candidate trace
    print("\n[4/9] Tracing Candidate Control/Pass Failures...", flush=True)
    cmd_cand_trace = [
        python, str(ROOT / 'scripts/trace_task07b_control_failures.py'),
        '--run-dir', str(out_dir / 'candidate-ball'),
        '--ground-truth', gt,
        '--output-dir', str(out_dir / 'candidate-trace')
    ]
    subprocess.run(cmd_cand_trace, check=True)
    
    # 5. Baseline tracking (legacy defaults)
    print("\n[5/9] Running Baseline Player Tracking...", flush=True)
    cmd_base_track = [
        python, str(ROOT / 'scripts/track_players.py'),
        '--detections', detections,
        '--run-json', run_json,
        '--roster-config', roster,
        '--video', video,
        '--enable-ocr',
        '--ocr-upscale', '3',
        '--jersey-evidence-ttl-s', '6',
        '--color-method', 'masked',
        '--jersey-evidence-cache', ocr_cache,
        '--tracking-policy', policy,
        '--output-dir', str(out_dir / 'baseline-tracking')
    ]
    subprocess.run(cmd_base_track, check=True)
    
    # 6. Baseline ball tracking
    print("\n[6/9] Running Baseline Ball Possession Tracking...", flush=True)
    cmd_base_ball = [
        python, str(ROOT / 'scripts/track_ball_possession.py'),
        '--detections', detections,
        '--run-json', run_json,
        '--tracks', str(out_dir / 'baseline-tracking/tracked_observations.jsonl'),
        '--tracking-run', str(out_dir / 'baseline-tracking/run.json'),
        '--identity-mappings', str(out_dir / 'baseline-tracking/identity_mappings.json'),
        '--exclusions', policy,
        '--config', ball_config,
        '--video', video,
        '--output-dir', str(out_dir / 'baseline-ball')
    ]
    subprocess.run(cmd_base_ball, check=True)
    
    # 7. Baseline evaluation
    print("\n[7/9] Evaluating Baseline Ball Possession...", flush=True)
    cmd_base_eval = [
        python, str(ROOT / 'scripts/evaluate_ball_possession.py'),
        '--run-dir', str(out_dir / 'baseline-ball'),
        '--ground-truth', gt,
        '--acceptance-profile', acceptance_profile,
        '--output-dir', str(out_dir / 'baseline-evaluation'),
        '--diagnostic'
    ]
    subprocess.run(cmd_base_eval, check=True)
    
    # 8. Baseline trace
    print("\n[8/9] Tracing Baseline Control/Pass Failures...", flush=True)
    cmd_base_trace = [
        python, str(ROOT / 'scripts/trace_task07b_control_failures.py'),
        '--run-dir', str(out_dir / 'baseline-ball'),
        '--ground-truth', gt,
        '--output-dir', str(out_dir / 'baseline-trace')
    ]
    subprocess.run(cmd_base_trace, check=True)
    
    # 9. Fullguard run (to verify regression elimination under decoupling)
    print("\n[9/9] Running Fullguard Tracking + Ball to Verify Decoupling Regression Fix...", flush=True)
    cmd_guard_track = [
        python, str(ROOT / 'scripts/track_players.py'),
        '--detections', detections,
        '--run-json', run_json,
        '--roster-config', roster,
        '--video', video,
        '--enable-ocr',
        '--ocr-upscale', '3',
        '--jersey-evidence-ttl-s', '6',
        '--color-method', 'masked',
        '--jersey-evidence-cache', ocr_cache,
        '--tracking-policy', policy,
        '--identity-crop-policy', guard_config,
        '--output-dir', str(out_dir / 'fullguard-tracking')
    ]
    subprocess.run(cmd_guard_track, check=True)
    
    cmd_guard_ball = [
        python, str(ROOT / 'scripts/track_ball_possession.py'),
        '--detections', detections,
        '--run-json', run_json,
        '--tracks', str(out_dir / 'fullguard-tracking/tracked_observations.jsonl'),
        '--tracking-run', str(out_dir / 'fullguard-tracking/run.json'),
        '--identity-mappings', str(out_dir / 'fullguard-tracking/identity_mappings.json'),
        '--exclusions', policy,
        '--config', ball_config,
        '--video', video,
        '--output-dir', str(out_dir / 'fullguard-ball')
    ]
    subprocess.run(cmd_guard_ball, check=True)
    
    cmd_guard_eval = [
        python, str(ROOT / 'scripts/evaluate_ball_possession.py'),
        '--run-dir', str(out_dir / 'fullguard-ball'),
        '--ground-truth', gt,
        '--acceptance-profile', acceptance_profile,
        '--output-dir', str(out_dir / 'fullguard-evaluation'),
        '--diagnostic'
    ]
    subprocess.run(cmd_guard_eval, check=True)

    elapsed = time.perf_counter() - t0
    print(f"\nAll paired runs completed in {elapsed:.1f}s!", flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
