"""Isolated local video uploads and cancellable analysis processes."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import uuid

ROOT = Path(__file__).resolve().parents[2]
MAX_UPLOAD_BYTES = 2 * 1024**3
PUBLIC_JOB_FIELDS = {
    'id', 'name', 'status', 'progress', 'frames_processed', 'duration_s',
    'fps', 'width', 'height', 'source_sha256', 'roster_matched',
    'roster_configured', 'tracks', 'error', 'stage', 'count', 'total',
    'source_time_s', 'frame_index', 'estimated_remaining',
}


def _public_job(job: dict) -> dict:
    return {key: value for key, value in job.items() if key in PUBLIC_JOB_FIELDS}


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)


class JobError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


class VideoJobs:
    def __init__(self, root: Path | None = None):
        self.root = Path(root or ROOT / 'outputs' / 'web-uploads').resolve()
        self.lock = threading.RLock()
        self.jobs: dict[str, dict] = {}
        self.processes: dict[str, subprocess.Popen] = {}
        self.results: dict[str, tuple] = {}
        self.enrichment: dict[str, dict] = {}

    def upload(self, source, length: int, name: str) -> dict:
        if not name.lower().endswith('.mp4'):
            raise JobError('Vui lòng chọn video MP4.')
        if not 0 < length <= MAX_UPLOAD_BYTES:
            raise JobError('Video phải có dung lượng từ 1 byte đến 2 GB.', 413)
        job_id = uuid.uuid4().hex
        directory = self.root / job_id
        directory.mkdir(parents=True)
        video = directory / 'input.mp4'
        try:
            remaining = length
            with video.open('xb') as target:
                while remaining:
                    chunk = source.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise JobError('Tải video bị gián đoạn. Vui lòng thử lại.')
                    target.write(chunk)
                    remaining -= len(chunk)
            from .video import probe_video
            import av
            metadata = probe_video(video)
            with av.open(str(video)) as container:
                next(container.decode(video=0))
            if metadata.duration_s <= 0:
                raise ValueError('Video has no duration')
        except Exception as exc:
            video.unlink(missing_ok=True)
            if isinstance(exc, JobError):
                raise
            raise JobError('Không đọc được video. Vui lòng chọn tệp MP4 hợp lệ.') from exc

        # An empty roster is intentional: never attribute a new match to sample players.
        roster = {
            'team_a_id': 'team_a', 'team_b_id': 'team_b',
            'team_a_name': 'Đội A', 'team_b_name': 'Đội B',
            'team_a_color_rgb': [128, 128, 128], 'team_b_color_rgb': [128, 128, 128],
            'players': [], 'provenance_status': 'unconfigured',
            'team_assignment_enabled': False,
        }
        matched = False
        sample = ROOT / 'outputs/demo-completion-20261116/demo-bundle-qa-v2/run.json'
        if sample.is_file():
            sample_run = json.loads(sample.read_text(encoding='utf-8'))
            if metadata.sha256 == sample_run.get('source_fingerprint_sha256'):
                roster = json.loads((ROOT / 'configs/rosters/vietnam_tonga.json').read_text(encoding='utf-8'))
                matched = True
        write_json(directory / 'roster.json', roster)
        job = {'id': job_id, 'name': name.replace('\\', '/').split('/')[-1][:180],
               'status': 'ready', 'progress': 0, 'frames_processed': 0,
               'duration_s': metadata.duration_s, 'fps': metadata.fps,
               'width': metadata.width, 'height': metadata.height,
               'source_sha256': metadata.sha256,
               'roster_matched': matched, 'error': None}
        with self.lock:
            self.jobs[job_id] = job
            self._save(job)
        return _public_job(job)

    def _save(self, job: dict) -> None:
        write_json(self.root / job['id'] / 'job.json', job)

    def match_config(self, job_id: str) -> dict:
        from .spatial_analysis import default_config, validate_config, ConfigurationError
        with self.lock:
            job = self._get(job_id)
            directory = self.root / job_id
            # Older uploads predate the source hash in job.json.
            if not job.get('source_sha256') and (directory / 'analysis/run.json').is_file():
                run = json.loads((directory / 'analysis/run.json').read_text(encoding='utf-8'))
                job['source_sha256'] = run.get('source_fingerprint_sha256')
                self._save(job)
            if not job.get('source_sha256'):
                from .video import compute_file_sha256
                job['source_sha256'] = compute_file_sha256(directory / 'input.mp4')
                self._save(job)
            path = directory / 'match_config.json'
            if path.is_file():
                config = json.loads(path.read_text(encoding='utf-8'))
            else:
                config = default_config(job, json.loads((directory / 'roster.json').read_text(encoding='utf-8')))
            try:
                config = validate_config(config, job)
            except ConfigurationError as exc:
                raise JobError('Cấu hình sân hoặc danh tính không hợp lệ. Hãy lưu cấu hình mới.') from exc
            write_json(path, config)
            return {'config': config, 'duration_s': job['duration_s'],
                    'spatial': self.spatial_status(job_id)}

    def configure(self, job_id: str, data: dict) -> dict:
        from .spatial_analysis import validate_config, config_revision, ConfigurationError
        with self.lock:
            job = self._get(job_id)
            if job['status'] not in {'ready', 'completed'}:
                raise JobError('Chờ phân tích hoàn tất trước khi thay đổi cấu hình.', 409)
            if self.spatial_status(job_id).get('status') == 'running':
                raise JobError('Đang cập nhật bản đồ. Hãy chờ hoàn tất.', 409)
            # Bind old jobs before validation, as for GET /api/match.
            self.match_config(job_id)
            try:
                config = validate_config(data, job)
            except ConfigurationError as exc:
                raise JobError(str(exc)) from exc
            directory = self.root / job_id
            write_json(directory / 'match_config.json', config)
            roster = dict(config['roster'], team_assignment_enabled=True)
            write_json(directory / 'roster.json', roster)
            job.update(roster_matched=True, roster_configured=True)
            self._save(job)
            self.results.pop(job_id, None)
            return {'saved': True, 'revision': config_revision(config), 'config': config}

    def spatial_status(self, job_id: str) -> dict:
        from .spatial_analysis import config_revision
        self._get(job_id)
        current = self.enrichment.get(job_id)
        if current and current.get('status') in {'running', 'failed'}:
            return dict(current)
        directory = self.root / job_id
        path = directory / 'spatial_map.json'
        config = directory / 'match_config.json'
        if path.is_file() and config.is_file():
            # A small manifest avoids reading a large frame bundle for polling.
            manifest = directory / 'spatial_map_status.json'
            if manifest.is_file():
                result = json.loads(manifest.read_text(encoding='utf-8'))
                if result['revision'] != config_revision(json.loads(config.read_text(encoding='utf-8'))):
                    return {'status': 'stale'}
                return {key: result[key] for key in ('status', 'revision', 'calibration_segments') if key in result}
        return {'status': 'unavailable'}

    def rebuild_spatial_map(self, job_id: str) -> dict:
        with self.lock:
            job = self._get(job_id)
            if job['status'] != 'completed':
                raise JobError('Cần phân tích video trước khi dựng bản đồ sân.', 409)
            if self.spatial_status(job_id).get('status') == 'running':
                raise JobError('Đang dựng bản đồ sân.', 409)
            config = self.match_config(job_id)['config']
            write_json(self.root / job_id / 'match_config.json', config)
            self.enrichment[job_id] = {'status': 'running', 'stage': 'projection'}
            threading.Thread(target=self._rebuild_spatial_map, args=(job_id, config), daemon=True).start()
            return dict(self.enrichment[job_id])

    def _rebuild_spatial_map(self, job_id: str, config: dict) -> None:
        from .spatial_analysis import build_spatial_analysis
        def progress(stage, count, total):
            with self.lock:
                self.enrichment[job_id] = dict(status='running', stage=stage, count=count, total=total)
        try:
            result = build_spatial_analysis(self.root / job_id, config, progress)
            with self.lock:
                write_json(self.root / job_id / 'spatial_map.json', result)
                state = {k: result[k] for k in ['status', 'revision', 'calibration_segments']}
                write_json(self.root / job_id / 'spatial_map_status.json', state)
                self.enrichment[job_id] = state
        except Exception:
            import traceback
            traceback.print_exc()
            with self.lock:
                self.enrichment[job_id] = {'status': 'failed', 'error': 'Không dựng được bản đồ sân. Kiểm tra dữ liệu và hiệu chuẩn rồi thử lại.'}

    def spatial_map(self, job_id: str) -> dict:
        with self.lock:
            status = self.spatial_status(job_id)
            if status['status'] != 'completed':
                return status
            result = json.loads((self.root / job_id / 'spatial_map.json').read_text(encoding='utf-8'))
            fields = (
                'version', 'revision', 'status', 'format', 'bounds', 'roster',
                'tracks', 'frames', 'color_teams', 'color_tracks', 'color_scope',
                'color_classification_enabled', 'color_method', 'heatmaps', 'heatmap_intervals',
                'calibration_segments',
            )
            return {key: result[key] for key in fields if key in result}

    def _get(self, job_id: str) -> dict:
        if job_id not in self.jobs:
            if not isinstance(job_id, str) or not re.fullmatch(r'[a-f0-9]{32}', job_id):
                raise JobError('Không tìm thấy video. Vui lòng chọn lại.', 404)
            try:
                directory = self.root / job_id
                job = json.loads((directory / 'job.json').read_text(encoding='utf-8'))
                if job['id'] != job_id:
                    raise ValueError('Job identity mismatch')
                if job['status'] in {'running', 'rendering'}:
                    outcome = directory / 'outcome.json'
                    if outcome.is_file():
                        job.update(json.loads(outcome.read_text(encoding='utf-8')))
                    else:
                        job.update(status='failed', error='Lần phân tích trước bị gián đoạn. Vui lòng chọn lại video.')
                self.jobs[job_id] = job
            except (OSError, ValueError, KeyError):
                raise JobError('Không tìm thấy video. Vui lòng chọn lại.', 404)
        return self.jobs[job_id]

    def active(self) -> dict | None:
        with self.lock:
            for job_id, process in self.processes.items():
                if process.poll() is None and self.jobs[job_id]['status'] != 'cancelled':
                    return self.status(job_id)
        return None

    def status(self, job_id: str) -> dict:
        with self.lock:
            job = self._get(job_id)
            if job['status'] in {'running', 'rendering'}:
                progress_file = self.root / job_id / 'progress.json'
                try:
                    progress = json.loads(progress_file.read_text(encoding='utf-8'))
                    job.update(progress)
                except (OSError, ValueError):
                    pass
            return _public_job(job)

    def start(self, job_id: str) -> dict:
        with self.lock:
            job = self._get(job_id)
            if job['status'] != 'ready':
                raise JobError('Video này đã được xử lý. Vui lòng chọn lại để phân tích mới.', 409)
            if any(p.poll() is None for p in self.processes.values()):
                raise JobError('Đang phân tích video khác. Hãy chờ hoặc hủy lần phân tích đó.', 409)
            directory = self.root / job_id
            log = (directory / 'worker.log').open('wb')
            try:
                process = subprocess.Popen(
                    [sys.executable, '-m', 'basketball_scoreboard.web_worker', str(directory)],
                    cwd=ROOT, env={**os.environ, 'PYTHONPATH': str(ROOT / 'src'), 'PYTHONUTF8': '1'},
                    stdout=log, stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                )
            except OSError as exc:
                raise JobError('Không khởi động được phân tích. Vui lòng thử lại.', 503) from exc
            finally:
                log.close()
            job['status'] = 'running'
            self.processes[job_id] = process
            self._save(job)
            threading.Thread(target=self._watch, args=(job_id, process), daemon=True).start()
            return _public_job(job)

    def _watch(self, job_id: str, process: subprocess.Popen) -> None:
        code = process.wait()
        with self.lock:
            job = self.jobs[job_id]
            if job['status'] == 'cancelled':
                return
            outcome = self.root / job_id / 'outcome.json'
            try:
                result = json.loads(outcome.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                result = {'status': 'failed', 'error': 'Phân tích bị gián đoạn. Vui lòng chọn video và thử lại.'}
            if code != 0 and result.get('status') == 'completed':
                result = {'status': 'failed', 'error': 'Không hoàn tất được phân tích.'}
            job.update(result)
            self._save(job)

    def cancel(self, job_id: str) -> dict:
        with self.lock:
            job = self._get(job_id)
            if job['status'] in {'ready', 'running', 'rendering'}:
                job['status'] = 'cancelled'
                process = self.processes.get(job_id)
                if process and process.poll() is None:
                    if os.name == 'nt':
                        # The Windows venv launcher can own a child interpreter.
                        # Terminate only this job's process tree, including that child.
                        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=10)
                    else:
                        process.terminate()
                self._save(job)
            return _public_job(job)

    def snapshot(self, job_id: str) -> dict:
        from .dashboard import load_run_bundle
        from .identity import RosterConfig
        job = self.status(job_id)
        directory = self.root / job_id
        roster = RosterConfig.from_dict(json.loads((directory / 'roster.json').read_text(encoding='utf-8')))
        result_dir = directory / 'analysis'
        if job['status'] == 'completed':
            with self.lock:
                if job_id not in self.results:
                    self.results[job_id] = load_run_bundle(result_dir)
                state, heatmap = self.results[job_id]
            state = dict(state)
        else:
            state, heatmap = {}, {}
        state.update({'status': job['status'], 'job': job, 'roster_matched': job['roster_matched']})
        # Imported input plays from zero; no offset from an unrelated sample clip.
        state['playback'] = {'source_start_s': 0}
        return dict(video_path=directory / 'input.mp4', roster=roster, run_state=state,
                    heatmap_data=heatmap, run_dir=result_dir if job['status'] == 'completed' else None)

    def close(self) -> None:
        for job_id in list(self.processes):
            self.cancel(job_id)

