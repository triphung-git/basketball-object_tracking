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
from .full_match_demo import FULL_MATCH_JOB_ID, full_match_present
from .shared_jobs import SharedJobs

ROOT = Path(__file__).resolve().parents[2]
MAX_UPLOAD_BYTES = 2 * 1024**3
VIETNAM_TONGA_SOURCE_SHA256 = "1443c1d263c8037a5684f3dbc0ef9216beb5097d9a47c4c1c9b94d1363e26865"
PUBLIC_JOB_FIELDS = {
    'id', 'name', 'status', 'progress', 'frames_processed', 'duration_s',
    'fps', 'width', 'height', 'source_sha256', 'roster_matched',
    'roster_configured', 'tracks', 'error', 'stage', 'count', 'total',
    'source_time_s', 'frame_index', 'estimated_remaining', 'verified_player_overlay',
}


def _public_job(job: dict) -> dict:
    return {key: value for key, value in job.items() if key in PUBLIC_JOB_FIELDS}


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


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
        self.shared = SharedJobs(self.root)
        self.owner = uuid.uuid4().hex
        self.worker_tokens = {}

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
        if metadata.sha256 == VIETNAM_TONGA_SOURCE_SHA256:
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
        from .spatial_analysis import default_config, validate_config, config_revision, ConfigurationError
        with self.lock, self.shared.atomic():
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
                    'revision': config_revision(config),
                    'spatial': self.spatial_status(job_id)}

    def configure(self, job_id: str, data: dict) -> dict:
        from .spatial_analysis import validate_config, config_revision, ConfigurationError
        if not isinstance(data,dict):
            raise JobError('Thiết lập phải là một đối tượng JSON.')
        with self.lock, self.shared.atomic():
            job = self._get(job_id)
            if job['status'] not in {'ready', 'completed'}:
                raise JobError('Chờ phân tích hoàn tất trước khi thay đổi cấu hình.', 409)
            if self.spatial_status(job_id).get('status') == 'running':
                raise JobError('Đang cập nhật bản đồ. Hãy chờ hoàn tất.', 409)
            # Bind old jobs before validation, as for GET /api/match.
            current_config = self.match_config(job_id)['config']
            expected = data.get('_expected_revision')
            if expected and expected != config_revision(current_config):
                raise JobError('Thiết lập đã được cập nhật ở dashboard khác. Tải lại trước khi lưu.',409)
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
            spatial = self.rebuild_spatial_map(job_id) if job['status'] == 'completed' else {'status':'unavailable'}
        return {'saved': True, 'revision': config_revision(config), 'config': config, 'spatial':spatial}

    def preview_calibration(self, job_id: str, data: dict) -> dict:
        from .spatial_analysis import validate_config, calibration_preview, ConfigurationError
        with self.lock:
            job = self._get(job_id)
            try:
                config = validate_config(data, job)
                return {'segments': calibration_preview(config), 'config': config}
            except ConfigurationError as exc:
                raise JobError(str(exc)) from exc

    def demo_job(self) -> dict:
        pointer = self.root / 'demo.json'
        if not pointer.is_file():
            return {'job': None}
        data = json.loads(pointer.read_text(encoding='utf-8'))
        job = self._get(data.get('job_id'))
        return {'job': _public_job(job)}

    def full_match_demo_job(self) -> dict:
        if not full_match_present(self.root / FULL_MATCH_JOB_ID):
            return {'job': None}
        return {'job': _public_job(self._get(FULL_MATCH_JOB_ID))}

    def spatial_status(self, job_id: str) -> dict:
        from .spatial_analysis import config_revision
        job = self._get(job_id)
        if job['status'] != 'completed':
            return {'status':'unavailable'}
        lease = self.shared.get('spatial:'+job_id)
        if lease and lease['state'] == 'running':
            if not self.shared.live(lease):
                return {'status':'failed'}
            state = {'status':'running','revision':lease['revision']}
            try:
                detail = json.loads((self.root/job_id/'spatial_map_progress.json').read_text(encoding='utf-8'))
                if detail.get('token') == lease['token']:
                    state.update({k:detail[k] for k in ['stage','count','total'] if k in detail})
            except (OSError,ValueError):
                pass
            return state
        if lease and lease['state'] == 'failed':
            return {'status':'failed','error':'Không cập nhật được bản đồ sân. Vui lòng thử lại.'}
        directory = self.root / job_id
        path = directory / 'spatial_map.json'
        if not path.is_file():
            path = directory / 'match_analysis.json'
        config = directory / 'match_config.json'
        if path.is_file() and config.is_file():
            # A small manifest avoids reading a large frame bundle for polling.
            manifest = directory / 'spatial_map_status.json'
            if not manifest.is_file():
                manifest = directory / 'match_analysis_status.json'
            if manifest.is_file():
                result = json.loads(manifest.read_text(encoding='utf-8'))
                if result.get('revision') != config_revision(json.loads(config.read_text(encoding='utf-8'))):
                    return {'status': 'stale'}
                return {key: result[key] for key in ('status', 'revision', 'calibration_segments') if key in result}
            return {'status': 'stale'}
        return {'status': 'unavailable'}

    def rebuild_spatial_map(self, job_id: str) -> dict:
        from .spatial_analysis import config_revision
        with self.lock, self.shared.atomic():
            job = self._get(job_id)
            if job['status'] != 'completed':
                raise JobError('Cần phân tích video trước khi dựng bản đồ sân.', 409)
            if self.spatial_status(job_id).get('status') == 'running':
                raise JobError('Đang dựng bản đồ sân.', 409)
            config = self.match_config(job_id)['config']
            token = self.shared.claim('spatial:'+job_id,job_id,self.owner,config_revision(config))
            if token is None:
                raise JobError('Đang dựng bản đồ sân.',409)
            write_json(self.root / job_id / 'match_config.json', config)
            self.enrichment[job_id] = {'status': 'running', 'stage': 'projection'}
            threading.Thread(target=self._rebuild_spatial_map, args=(job_id, config, token), daemon=True).start()
            return dict(self.enrichment[job_id])

    def _rebuild_spatial_map(self, job_id: str, config: dict, token: str) -> None:
        from .spatial_analysis import build_spatial_analysis,config_revision
        stopped = threading.Event()
        def heartbeat():
            while not stopped.wait(2):
                if not self.shared.heartbeat('spatial:'+job_id,token):
                    break
        threading.Thread(target=heartbeat,daemon=True).start()
        def progress(stage, count, total):
            with self.lock:
                self.enrichment[job_id] = dict(status='running', stage=stage, count=count, total=total)
                write_json(self.root/job_id/'spatial_map_progress.json',
                           dict(token=token,stage=stage,count=count,total=total))
        try:
            if config.get('geometry_mode') == 'automatic':
                from .automatic_court import ensure_automatic_geometry
                ensure_automatic_geometry(self.root/job_id,config,progress)
            result = build_spatial_analysis(self.root / job_id, config, progress)
            with self.lock, self.shared.atomic() as connection:
                latest = json.loads((self.root/job_id/'match_config.json').read_text(encoding='utf-8'))
                lease = connection.execute('SELECT * FROM leases WHERE slot=?',('spatial:'+job_id,)).fetchone()
                if not lease or lease['token'] != token or config_revision(latest) != config_revision(config):
                    if lease and lease['token'] == token:
                        connection.execute('UPDATE leases SET state=? WHERE slot=? AND token=?',('stale','spatial:'+job_id,token))
                    return
                write_json(self.root / job_id / 'spatial_map.json', result)
                state = {k: result[k] for k in ['status', 'revision', 'calibration_segments']}
                write_json(self.root / job_id / 'spatial_map_status.json', state)
                self.enrichment[job_id] = state
                connection.execute('UPDATE leases SET state=? WHERE slot=? AND token=?',('completed','spatial:'+job_id,token))
        except Exception:
            import traceback
            traceback.print_exc()
            with self.lock:
                self.enrichment[job_id] = {'status': 'failed', 'error': 'Không dựng được bản đồ sân. Kiểm tra dữ liệu và hiệu chuẩn rồi thử lại.'}
                self.shared.finish('spatial:'+job_id,token,'failed')
        finally:
            stopped.set()

    def spatial_map(self, job_id: str) -> dict:
        with self.lock:
            status = self.spatial_status(job_id)
            if status['status'] != 'completed':
                return status
            path = self.root / job_id / 'spatial_map.json'
            if not path.is_file():
                path = self.root / job_id / 'match_analysis.json'
            result = json.loads(path.read_text(encoding='utf-8'))
            fields = (
                'version', 'revision', 'status', 'format', 'bounds', 'roster',
                'tracks', 'frames', 'color_teams', 'color_tracks', 'color_scope',
                'color_classification_enabled', 'color_method', 'heatmaps', 'heatmap_intervals',
                'calibration_segments',
                'unknown_heatmap_intervals', 'quality', 'grid_shape', 'cell_size_xy',
                'court_lines',
                'geometry_mode',
                'identity',
            )
            return {key: result[key] for key in fields if key in result}

    def _get(self, job_id: str) -> dict:
        if not isinstance(job_id, str) or not re.fullmatch(r'[a-f0-9]{32}', job_id):
            raise JobError('Không tìm thấy video. Vui lòng chọn lại.', 404)
        try:
            directory = self.root / job_id
            job = json.loads((directory / 'job.json').read_text(encoding='utf-8'))
            if job['id'] != job_id:
                raise ValueError('Job identity mismatch')
            lease = self.shared.get('analysis')
            matching = lease and lease['job_id'] == job_id
            if matching and lease['state'] == 'cancelled':
                job.update(status='cancelled')
            elif job['status'] in {'running', 'rendering'}:
                local = self.processes.get(job_id)
                live = matching and self.shared.live(lease)
                if not live and not (local and local.poll() is None):
                    outcome = directory/'outcome.json'
                    if outcome.is_file():
                        job.update(json.loads(outcome.read_text(encoding='utf-8')))
                    else:
                        job.update(status='failed', error='Lần phân tích trước bị gián đoạn. Vui lòng chọn lại video.')
            self.jobs[job_id] = job
            return job
        except (OSError, ValueError, KeyError):
            raise JobError('Không tìm thấy video. Vui lòng chọn lại.', 404)

    def active(self) -> dict | None:
        lease = self.shared.get('analysis')
        if self.shared.live(lease):
            return self.status(lease['job_id'])
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
            token = self.shared.claim('analysis',job_id,self.owner)
            if token is None:
                raise JobError('Đang phân tích video khác. Hãy chờ hoặc hủy lần phân tích đó.',409)
            directory = self.root/job_id
            log = (directory/'worker.log').open('wb')
            try:
                job.update(status='running',error=None)
                self._save(job)
                process = subprocess.Popen(
                    [sys.executable,'-m','basketball_scoreboard.web_worker',str(directory)],
                    cwd=ROOT,env={**os.environ,'PYTHONPATH':str(ROOT/'src'),'PYTHONUTF8':'1',
                                  'BASKETBALL_WORKER_TOKEN':token},
                    stdout=log,stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                # The worker may already have bound its actual interpreter PID;
                # do not replace that with the Windows venv launcher PID.
                lease = self.shared.get('analysis')
                if lease and lease['pid'] == os.getpid():
                    self.shared.heartbeat('analysis',token,process.pid)
            except OSError as exc:
                self.shared.finish('analysis',token,'failed')
                job.update(status='ready');self._save(job)
                raise JobError('Không khởi động được phân tích. Vui lòng thử lại.',503) from exc
            finally:
                log.close()
            self.processes[job_id] = process
            self.worker_tokens[job_id] = token
            threading.Thread(target=self._watch,args=(job_id,process),daemon=True).start()
            return _public_job(job)

    def _watch(self, job_id: str, process: subprocess.Popen) -> None:
        code = process.wait()
        token = self.worker_tokens.get(job_id)
        with self.lock, self.shared.atomic() as connection:
            lease = connection.execute('SELECT * FROM leases WHERE slot=?',('analysis',)).fetchone()
            job = self._get(job_id)
            if job['status'] == 'cancelled' or (token and (not lease or lease['token'] != token or lease['state'] == 'cancelled')):
                return
            try:
                result = json.loads((self.root/job_id/'outcome.json').read_text(encoding='utf-8'))
            except (OSError,ValueError):
                result = dict(status='failed',error='Phân tích bị gián đoạn. Vui lòng chọn video và thử lại.')
            if code != 0 and result.get('status') == 'completed':
                result = dict(status='failed',error='Không hoàn tất được phân tích.')
            job.update(result);self._save(job)
            if token:
                connection.execute('UPDATE leases SET state=? WHERE slot=? AND token=? AND state!=?',
                                   (job['status'],'analysis',token,'cancelled'))
            self.results.pop(job_id,None)

    def cancel(self, job_id: str) -> dict:
        with self.lock:
            job = self._get(job_id)
            if job['status'] in {'ready','running','rendering'}:
                with self.shared.atomic() as connection:
                    connection.execute('UPDATE leases SET state=? WHERE slot=? AND job_id=? AND state=?',
                                       ('cancelled','analysis',job_id,'running'))
                    job['status'] = 'cancelled'
                    self._save(job)
                process = self.processes.get(job_id)
                if process and process.poll() is None:
                    if os.name == 'nt':
                        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],
                            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=10)
                    else:
                        process.terminate()
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
                stamp=tuple((result_dir/name).stat().st_mtime_ns if (result_dir/name).is_file() else None
                            for name in ['run.json','spatial_map.json','spatial_map_status.json'])
                cached=self.results.get(job_id)
                if cached is None or cached[0]!=stamp:
                    state,heatmap=load_run_bundle(result_dir)
                    self.results[job_id]=(stamp,state,heatmap)
                else:
                    _,state,heatmap=cached
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

