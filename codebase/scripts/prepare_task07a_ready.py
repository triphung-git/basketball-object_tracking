"""Complete local fine-tune readiness, with live status and real GPU backward smoke."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import zipfile
import urllib.parse
import urllib.request

from resumable_artifact_download import atomic_json, file_digest
from train_task07a_candidate import runtime_snapshot

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent


def resolve_dataset_export():
    # The standalone worker cannot call the chat connector. Use the already
    # configured local Roboflow credential; never persist or log a signed URL.
    sys.path.insert(0,str(ROOT/'src'))
    from basketball_scoreboard.detector import load_roboflow_api_key
    key = load_roboflow_api_key()
    url = 'https://api.roboflow.com/phung-van-tri/basketball-xil7x-y8g6u/1/yolov8?'
    url += urllib.parse.urlencode({'api_key':key})
    with urllib.request.urlopen(url,timeout=90) as response:
        result = json.load(response)
    link = result.get('export',{}).get('link')
    if not link or not link.startswith('https://'):
        raise ValueError('Existing YOLO export is not ready')
    return link


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def downloads_complete(stages, wheel_manifest):
    """Completed progress can precede cleanup and the final wheel manifest."""
    if any(stages.get(name,{}).get('status') != 'completed' for name in ('dataset','torchvision','torch')):
        return False
    path = Path(wheel_manifest)
    if not path.is_file():
        return False
    return {row.get('package') for row in load(path)} == {'torch','torchvision'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', required=True)
    parser.add_argument('--manage-downloads',action='store_true')
    args = parser.parse_args()
    folder = Path(args.run_dir).resolve()
    folder.mkdir(parents=True,exist_ok=True)
    status_path = folder.parent/'status.json'
    original_status = load(status_path) if status_path.is_file() else None
    if original_status and original_status.get('pid') and original_status.get('pid') != os.getpid():
        import psutil
        try:
            existing = psutil.Process(original_status.get('pid'))
            if existing.is_running() and any('prepare_task07a_ready.py' in arg for arg in existing.cmdline()):
                raise RuntimeError('A preparation supervisor is already running')
        except (psutil.NoSuchProcess,TypeError):
            pass
    if original_status:
        atomic_json(folder/'previous-status.json', original_status)
    baseline = runtime_snapshot()
    atomic_json(folder/'runtime-before.json', baseline)
    state = dict(pid=os.getpid(), status='preparing_finetune', training_started=False,
                 production_promotion_allowed=False, run_dir=str(folder),
                 downstream_acceptance_pending=True)
    status_lock = threading.RLock()
    heartbeat_stop = threading.Event()

    def update(stage, **values):
        with status_lock:
            state.update(values, status=stage, updated_utc=datetime.now(timezone.utc).isoformat())
            atomic_json(status_path, state)

    def heartbeat():
        while not heartbeat_stop.wait(5):
            with status_lock:
                update(state['status'])

    heartbeat_thread = threading.Thread(target=heartbeat,daemon=True)
    heartbeat_thread.start()

    def run(stage, command):
        update(stage)
        with (folder/(stage+'.log')).open('w', encoding='utf-8') as log:
            process = subprocess.Popen([str(x) for x in command], cwd=WORKSPACE,
                                       stdout=log, stderr=subprocess.STDOUT,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            while process.poll() is None:
                update(stage, child_pid=process.pid)
                time.sleep(3)
            if process.returncode:
                raise RuntimeError(f'{stage} failed; see {stage}.log')

    base_python = ROOT/'.venv/Scripts/python.exe'
    train_python = ROOT/'.venv-train/Scripts/python.exe'
    archive = ROOT/'data/finetune/task07a/original/dataset.zip'
    original = archive.parent/'export'
    dataset = ROOT/'data/finetune/task07a/mixed-ready-01'
    checkpoint = ROOT/'models/checkpoints/task07a-original/best.pt'
    wheel_dir = ROOT/'.tools/training-wheels'
    managed = []
    logs = []
    try:
        import psutil
        if args.manage_downloads:
            update('starting_managed_downloads')
            url = resolve_dataset_export()
            environment = os.environ.copy()
            environment['TASK07A_ARTIFACT_URL'] = url
            for label, command, child_environment in [
                ('dataset',[base_python,'-u',ROOT/'scripts/resumable_artifact_download.py',
                            '--output',archive,'--progress',folder/'dataset-download.json','--workers','12'],environment),
                ('cuda',[base_python,'-u',ROOT/'scripts/fetch_task07a_cuda_wheels.py',
                         '--directory',wheel_dir,'--progress-dir',folder,'--workers','12'],None)]:
                log = (folder/(label+'-download.log')).open('w',encoding='utf-8')
                logs.append(log)
                managed.append(subprocess.Popen([str(x) for x in command],cwd=WORKSPACE,
                    stdout=log,stderr=subprocess.STDOUT,env=child_environment,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)))
        update('downloading_dataset_and_cuda')
        while True:
            for child in managed:
                if child.poll() not in (None,0):
                    raise RuntimeError('Managed download failed; see download logs')
            stages = {}
            for name in ('dataset','torchvision','torch'):
                path = folder/(name+'-download.json')
                progress = load(path) if path.is_file() else dict(status='pending')
                if progress.get('status') not in ('completed','pending'):
                    try:
                        process = psutil.Process(progress['pid'])
                        alive = process.is_running() and process.status() != psutil.STATUS_ZOMBIE
                    except (psutil.NoSuchProcess, KeyError):
                        alive = False
                    if not alive:
                        raise RuntimeError(name+' download stopped before completion')
                    if progress.get('status') in ('failed','interrupted'):
                        raise RuntimeError(name+' download reported failure')
                stages[name] = progress
            update('downloading_dataset_and_cuda', downloads=stages)
            if downloads_complete(stages,wheel_dir/'manifest.json'):
                break
            time.sleep(5)
        wheels = load(wheel_dir/'manifest.json')
        if {row['package'] for row in wheels} != {'torch','torchvision'}:
            raise ValueError('Both verified CUDA wheels are required')
        for row in wheels:
            if file_digest(row['path']) != row['sha256']:
                raise ValueError('CUDA wheel checksum changed')
        run('installing_cuda', ['uv','pip','install','--offline','--no-deps','--python',train_python,
                                *[row['path'] for row in wheels]])
        update('validating_archive')
        if not zipfile.is_zipfile(archive):
            raise ValueError('Dataset archive is incomplete')
        atomic_json(folder/'archive.json',dict(bytes=archive.stat().st_size,sha256=file_digest(archive)))
        if original.exists():
            raise ValueError('Existing original export requires verification before reuse')
        original.mkdir()
        with zipfile.ZipFile(archive) as packed:
            for item in packed.infolist():
                if not (original/item.filename).resolve().is_relative_to(original.resolve()):
                    raise ValueError('Archive contains an unsafe path')
            if packed.testzip():
                raise ValueError('Dataset archive CRC validation failed')
            update('extracting_dataset')
            packed.extractall(original)
        run('preparing_mixed_dataset', [base_python,ROOT/'scripts/prepare_task07a_finetune.py',
            '--original',original,'--progress',ROOT/'outputs/task07-checkpoint-a-return-20261105/accepted-v2/merged-progress-v3.json',
            '--source',ROOT/'outputs/task07a-dataset-first-20261105/pilot-candidate/annotations-draft.json',
            '--checkpoint',checkpoint,'--output',dataset])
        run('gpu_backward_smoke', [train_python,ROOT/'scripts/probe_task07a_gpu_training.py',
                                  '--checkpoint',checkpoint,'--output',folder/'gpu-training-probe.json'])
        run('training_preflight', [train_python,ROOT/'scripts/train_task07a_candidate.py',
            '--dataset',dataset,'--output',folder/'candidate-training','--epochs','30','--batch','2'])
        with (folder/'requirements-train.lock.txt').open('w',encoding='utf-8') as lock:
            subprocess.run(['uv','pip','freeze','--python',str(train_python)],cwd=WORKSPACE,
                           stdout=lock,check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        manifest = load(dataset/'manifest.json')
        after = runtime_snapshot()
        changed = sorted(key for key in set(baseline)|set(after) if baseline.get(key) != after.get(key))
        report = dict(status='ready_for_finetune', dataset=str(dataset), counts=manifest['counts'],
                      checkpoint=str(checkpoint), checkpoint_sha256=file_digest(checkpoint),
                      gpu_probe=load(folder/'gpu-training-probe.json'), runtime_unchanged=not changed,
                      runtime_changed_files=changed, training_started=False,
                      production_promotion_allowed=False, limitations=manifest['limitations'])
        atomic_json(folder/'readiness.json',report)
        update('ready_for_finetune', dataset=str(dataset), counts=manifest['counts'],
               cuda_available=True, readiness_report=str(folder/'readiness.json'), runtime_unchanged=not changed)
    except BaseException as error:
        update('interrupted' if isinstance(error,KeyboardInterrupt) else 'preparation_failed',
               error_type=type(error).__name__,
               error=str(error) if isinstance(error,(ValueError,RuntimeError)) else 'See stage logs; private request details suppressed.')
        return 1
    finally:
        heartbeat_stop.set()
        heartbeat_thread.join(timeout=2)
        for child in managed:
            if child.poll() is None:
                import psutil
                try:
                    parent = psutil.Process(child.pid)
                    owned = parent.children(recursive=True) + [parent]
                    for process in owned:
                        try:
                            process.terminate()
                        except psutil.NoSuchProcess:
                            pass
                    _, survivors = psutil.wait_procs(owned,timeout=15)
                    for process in survivors:
                        process.kill()
                except psutil.NoSuchProcess:
                    pass
        for log in logs:
            log.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
