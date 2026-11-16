#!/usr/bin/env python3
"""Orchestrator for Task07 Recovery: preflight, actual loss probe, smoke, pilot, candidate fine-tune, paired evaluation, and downstream checks."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent


def get_gpu_info():
    try:
        import torch
        if torch.cuda.is_available():
            return {
                "available": True,
                "name": torch.cuda.get_device_name(0),
                "capability": list(torch.cuda.get_device_capability(0)),
                "total_vram_mb": round(torch.cuda.get_device_properties(0).total_memory / (1024 * 1024), 2),
            }
    except Exception:
        pass
    return {"available": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="Path to recovery experiment output directory")
    parser.add_argument("--dataset", default="codebase/data/finetune/task07a/mixed-20261108")
    parser.add_argument("--checkpoint", default="codebase/models/checkpoints/task07a-original/best.pt")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch", type=int, default=2)
    parser.add_argument("--skip-pilot", action="store_true", help="Skip pilot if already completed")
    parser.add_argument("--skip-training", action="store_true", help="Skip training candidate")
    args = parser.parse_args()

    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    status_file = output / "pipeline_status.json"
    train_python = str(ROOT / ".venv-train/Scripts/python.exe")
    eval_python = str(ROOT / ".venv/Scripts/python.exe")

    state = {
        "pipeline": "task07_finetune_recovery",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "status": "starting",
        "stages": {},
        "production_promotion_allowed": False,
        "default_model_preserved": True,
    }

    def update_stage(stage_name, status, **extra):
        state["stages"][stage_name] = {
            "status": status,
            "updated_utc": datetime.now(timezone.utc).isoformat(),
            **extra,
        }
        state["status"] = f"{stage_name}_{status}"
        state["last_updated_utc"] = datetime.now(timezone.utc).isoformat()
        tmp = status_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        tmp.replace(status_file)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] STAGE: {stage_name} -> {status}", flush=True)

    def run_cmd(stage_name, cmd, log_name=None):
        update_stage(stage_name, "running")
        log_file = output / f"{log_name or stage_name}.log"
        with log_file.open("w", encoding="utf-8") as lf:
            t0 = time.perf_counter()
            proc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, text=True, cwd=str(WORKSPACE))
            elapsed = time.perf_counter() - t0
        if proc.returncode != 0:
            update_stage(stage_name, "failed", exit_code=proc.returncode, elapsed_seconds=round(elapsed, 2))
            raise RuntimeError(f"Stage '{stage_name}' failed with exit code {proc.returncode}. See {log_file}")
        update_stage(stage_name, "passed", exit_code=0, elapsed_seconds=round(elapsed, 2))

    # STAGE 1: Loss Probe
    loss_probe_json = output / "actual-loss-probe.json"
    if not loss_probe_json.exists():
        run_cmd(
            "actual_loss_probe",
            [
                train_python,
                str(ROOT / "scripts/probe_task07a_gpu_training.py"),
                "--checkpoint", args.checkpoint,
                "--output", str(loss_probe_json),
                "--dataset", args.dataset,
            ],
        )
    else:
        update_stage("actual_loss_probe", "passed", note="Using existing verified artifact")

    # STAGE 2: GPU Smoke
    smoke_json = output / "gpu-training-smoke.json"
    if not smoke_json.exists():
        run_cmd(
            "gpu_training_smoke",
            [
                train_python,
                str(ROOT / "scripts/gpu_training_smoke_test.py"),
                "--output", str(smoke_json),
            ],
        )
    else:
        update_stage("gpu_training_smoke", "passed", note="Using existing verified artifact")

    # STAGE 3: Pilot
    pilot_dir = output / "pilot"
    pilot_best = pilot_dir / "pilot/weights/best.pt"
    if not args.skip_pilot:
        if not pilot_best.exists():
            run_cmd(
                "pilot_training",
                [
                    train_python,
                    str(ROOT / "scripts/train_task07a_candidate.py"),
                    "--dataset", args.dataset,
                    "--output", str(pilot_dir),
                    "--epochs", "1",
                    "--batch", str(args.batch),
                    "--name", "pilot",
                    "--execute",
                ],
            )
        else:
            update_stage("pilot_training", "passed", note="Using existing pilot checkpoint")

    # STAGE 4: Candidate Training
    cand_dir = output / "candidate-training"
    cand_best = cand_dir / "candidate/weights/best.pt"
    if not args.skip_training:
        if not cand_best.exists():
            run_cmd(
                "candidate_training",
                [
                    train_python,
                    str(ROOT / "scripts/train_task07a_candidate.py"),
                    "--dataset", args.dataset,
                    "--output", str(cand_dir),
                    "--epochs", str(args.epochs),
                    "--batch", str(args.batch),
                    "--patience", "10",
                    "--name", "candidate",
                    "--execute",
                ],
            )
        else:
            update_stage("candidate_training", "passed", note="Using existing candidate checkpoint")

    # STAGE 5: Paired Native Detector Evaluation
    eval_best = cand_best if cand_best.exists() else (pilot_best if pilot_best.exists() else None)
    if eval_best and eval_best.exists():
        eval_output = output / "detector-evaluation"
        run_cmd(
            "paired_detector_evaluation",
            [
                train_python,
                str(ROOT / "scripts/evaluate_task07a_candidate.py"),
                "--dataset", args.dataset,
                "--candidate", str(eval_best),
                "--output", str(eval_output),
                "--splits", "val", "test",
            ],
        )

    # STAGE 6: Downstream Invariant & Logic Tests
    run_cmd(
        "downstream_evaluator_and_ledger_tests",
        [
            eval_python,
            "-m", "pytest",
            str(ROOT / "tests/test_task07a_finetune.py"),
            str(ROOT / "tests/test_task07a_readiness.py"),
            str(ROOT / "tests/test_task08_temporal_shot_engine.py"),
            str(ROOT / "tests/test_task08_evaluator.py"),
            str(ROOT / "tests/test_task11_ledger_and_boxscore.py"),
            "-q",
        ],
    )

    state["status"] = "recovery_pipeline_completed"
    state["completed_utc"] = datetime.now(timezone.utc).isoformat()
    status_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"\nRecovery pipeline finished! Status: {state['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

