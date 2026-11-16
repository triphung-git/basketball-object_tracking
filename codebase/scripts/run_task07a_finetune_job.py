#!/usr/bin/env python3
"""Finish downloads, prepare mixed data, and train one isolated local candidate.

Long-running job with on-disk status/logs. Never promotes a candidate: native
detector metrics cannot certify downstream OCR, identity, ROI, or pass accuracy.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wait-pid', type=int, action='append', default=[])
    parser.add_argument('--epochs', type=int, default=30)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    status_file = output/'status.json'
    state = dict(status='starting', pid=os.getpid(), training_started=False,
                 production_promotion_allowed=False, epochs=args.epochs,
                 promotion_blockers=['Paired OCR/crop/identity/ROI/full-pipeline evaluation pending.',
                                     'No independent-match test supplied.'])

    def update(stage, **values):
        state.update(status=stage, updated_utc=datetime.now(timezone.utc).isoformat(), **values)
        temp = status_file.with_suffix('.tmp')
        temp.write_text(json.dumps(state, indent=2), encoding='utf-8')
        temp.replace(status_file)

    def run(stage, command):
        update(stage)
        with (output/(stage+'.log')).open('w', encoding='utf-8') as log:
            result = subprocess.run([str(x) for x in command], cwd=WORKSPACE,
                                    stdout=log, stderr=subprocess.STDOUT,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            raise RuntimeError(f'{stage} exited {result.returncode}; see stage log')

    base_python = ROOT/'.venv/Scripts/python.exe'
    train_python = ROOT/'.venv-train/Scripts/python.exe'
    archive = ROOT/'data/finetune/task07a/original/dataset.zip'
    original = archive.parent/'export'
    dataset = ROOT/'data/finetune/task07a/mixed-20261108'
    checkpoint = ROOT/'models/checkpoints/task07a-original/best.pt'
    try:
        import psutil
        waiting = []
        for pid in args.wait_pid:
            try:
                waiting.append(psutil.Process(pid))
            except psutil.NoSuchProcess:
                pass
        update('waiting_for_dataset_and_cuda_downloads', dependency_pids=args.wait_pid)
        deadline = time.monotonic() + 4 * 3600
        while any(p.is_running() for p in waiting):
            if time.monotonic() > deadline:
                raise TimeoutError('Dependency downloads exceeded four hours; no training launched')
            time.sleep(10)
        if not zipfile.is_zipfile(archive):
            run('retry_dataset_download', [base_python, ROOT/'scripts/download_task07a_artifact.py',
                                          '--output', archive, '--workers', '16'])
        update('checking_and_extracting_original_dataset')
        if original.exists():
            raise ValueError('Original extraction destination already exists; inspect before resuming')
        original.mkdir()
        with zipfile.ZipFile(archive) as packed:
            for item in packed.infolist():
                target = (original/item.filename).resolve()
                if not target.is_relative_to(original.resolve()):
                    raise ValueError('Archive path escapes extraction directory')
            bad = packed.testzip()
            if bad:
                raise ValueError('Dataset ZIP CRC validation failed')
            packed.extractall(original)
        run('prepare_mixed_dataset', [base_python, ROOT/'scripts/prepare_task07a_finetune.py',
            '--original', original, '--checkpoint', checkpoint,
            '--progress', ROOT/'outputs/task07-checkpoint-a-return-20261105/accepted-v2/merged-progress-v3.json',
            '--source', ROOT/'outputs/task07a-dataset-first-20261105/pilot-candidate/annotations-draft.json',
            '--output', dataset])
        run('checkpoint_gpu_probe', [train_python, ROOT/'scripts/inspect_task07a_checkpoint.py',
            '--checkpoint', checkpoint, '--output', output/'gpu-probe.json'])
        probe = json.loads((output/'gpu-probe.json').read_text())
        if not probe['cuda_available']:
            raise ValueError('CUDA installation did not become usable; no CPU training fallback')
        with (output/'requirements-train.lock.txt').open('w', encoding='utf-8') as lock:
            subprocess.run(['uv', 'pip', 'freeze', '--python', str(train_python)],
                           cwd=WORKSPACE, stdout=lock, check=True,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        run('training_preflight', [train_python, ROOT/'scripts/train_task07a_candidate.py',
            '--dataset', dataset, '--output', output/'training', '--epochs', args.epochs, '--batch', '2'])
        update('training_candidate', training_started=True)
        run('training_candidate', [train_python, ROOT/'scripts/train_task07a_candidate.py',
            '--dataset', dataset, '--output', output/'training', '--epochs', args.epochs,
            '--batch', '2', '--execute'])
        run('paired_detector_evaluation', [train_python, ROOT/'scripts/evaluate_task07a_candidate.py',
            '--dataset', dataset, '--candidate', output/'training/candidate/weights/best.pt',
            '--output', output/'detector-evaluation'])
        update('trained_pending_downstream_evaluation',
               candidate=str(output/'training/candidate/weights/best.pt'))
    except Exception as error:
        update('stopped_before_promotion', error_type=type(error).__name__, error=str(error))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
