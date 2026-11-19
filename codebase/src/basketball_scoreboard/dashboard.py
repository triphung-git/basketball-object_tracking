"""Spatial video dashboard with isolated uploads and sample playback."""
from __future__ import annotations

from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
import json
from pathlib import Path
import re
from typing import Any, Dict, Optional, Tuple
import urllib.parse

from basketball_scoreboard.demo_bundle import summarize_run, verify_bundle_manifest
from basketball_scoreboard.identity import RosterConfig
from basketball_scoreboard.web_jobs import JobError, VideoJobs
from basketball_scoreboard.spatial_analysis import SPATIAL_ALGORITHM_VERSION


DASHBOARD_HTML = Path(__file__).with_name("dashboard.html").read_text(encoding="utf-8")


class RequestBody:
    """Bound reads and account for unread request bytes before an HTTP rejection."""
    def __init__(self, stream, length):
        self.stream = stream
        self.remaining = max(0, length)

    def read(self, count):
        data = self.stream.read(min(count, self.remaining))
        self.remaining -= len(data)
        return data

    def discard_small(self, connection):
        if not 0 < self.remaining <= 2 * 1024**2:
            return
        timeout = connection.gettimeout()
        try:
            connection.settimeout(1)
            while self.remaining:
                if not self.read(min(65536, self.remaining)):
                    break
        except OSError:
            pass
        finally:
            connection.settimeout(timeout)


def spatial_overlay(data: Dict[str, Any]) -> Dict[str, Any]:
    """Keep video-frame bbox data and identity/role metadata when serving run artifacts."""
    frames = []
    for frame in data.get("frames", []):
        if not isinstance(frame, dict) or not isinstance(frame.get("time"), (int, float)):
            continue
        boxes = []
        for item in frame.get("boxes", []):
            if not isinstance(item, dict) or not isinstance(item.get("box"), list):
                continue
            box = {"box": item["box"]}
            if isinstance(item.get("id"), str):
                box["id"] = item["id"]
            if item.get("kind") in {"ball", "rim"}:
                box["kind"] = item["kind"]
            if item.get("role") in {"player", "referee", "non_player", "unknown"}:
                box["role"] = item["role"]
            if isinstance(item.get("team_id"), str):
                box["team_id"] = item["team_id"]
            if isinstance(item.get("player_id"), str):
                box["player_id"] = item["player_id"]
            for key in ("segment_id", "sample_type", "continuity_start_s"):
                if isinstance(item.get(key), (str, int, float)):
                    box[key] = item[key]
            boxes.append(box)
        frames.append({"time": frame["time"], "boxes": boxes})
    return {"frames": frames}


def overlay_with_spatial_identity(data,spatial=None,config=None):
    """Serve current identities over immutable bbox geometry and source clock."""
    result=spatial_overlay(data)
    if not spatial or spatial.get('status')!='completed' or spatial.get('geometry_mode')!='automatic':
        return result
    people={round(frame['time'],6):{p['id']:p for p in frame['players']} for frame in spatial.get('frames',[])}
    assignments={}
    for assignment in (config or {}).get('assignments',[]):
        assignments.setdefault(assignment['track_id'],[]).append(assignment)
    for frame in result['frames']:
        current=people.get(round(frame['time'],6),{})
        boxes=[]
        for box in frame['boxes']:
            if not box.get('id'):
                boxes.append(box)
                continue
            person=current.get(box['id'])
            person=next((a for a in assignments.get(box['id'],[]) if a['start_s']<=frame['time']<a['end_s']),person)
            if person and person.get('role')=='non_player':
                continue
            # A previous cached identity cannot survive an unresolved new
            # result just because it was embedded in the original overlay.
            box.pop('player_id',None);box.pop('team_id',None)
            box['role']=person.get('role','unknown') if person else 'unknown'
            if person:
                for key in ['player_id','team_id']:
                    if person.get(key):box[key]=person[key]
            boxes.append(box)
        frame['boxes']=boxes
    return result


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """Serve the video, tracking overlay and spatial map APIs."""

    def __init__(
        self,
        request: Any,
        client_address: Tuple[str, int],
        server: HTTPServer,
        video_path: Optional[Path] = None,
        roster: Optional[RosterConfig] = None,
        run_state: Optional[Dict[str, Any]] = None,
        heatmap_data: Optional[Dict[str, Any]] = None,
        run_dir: Optional[Path] = None,
        jobs: Optional[VideoJobs] = None,
        startup_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.video_path = video_path
        self.roster = roster
        self.run_state = run_state or {}
        self.heatmap_data = heatmap_data or {}
        self.run_dir = run_dir
        self.jobs = jobs
        self.startup_context = startup_context or {}
        super().__init__(request, client_address, server)

    def log_message(self, format: str, *args: Any) -> None:
        pass

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        job_id = query.get("job", [None])[0]
        if path == '/api/health':
            self._send_json({'application':'basketball-spatial-dashboard','status':'ready','spatial_version':SPATIAL_ALGORITHM_VERSION})
            return
        if path == '/api/startup':
            self._send_json(self.startup_context)
            return
        try:
            if path == "/api/active-job":
                self._send_json({"job": self.jobs.active()})
                return
            if path == '/api/demo-job':
                self._send_json(self.jobs.demo_job())
                return
            if path == "/api/job":
                self._send_json(self.jobs.status(job_id))
                return
            if job_id:
                for key, value in self.jobs.snapshot(job_id).items():
                    setattr(self, key, value)
        except JobError as exc:
            self._send_json({"error": str(exc)}, exc.status)
            return

        if path in {"/", "/index.html"}:
            self._serve_html()
        elif path == "/api/status":
            self._serve_status()
        elif path in {"/match-dashboard.js", "/overlay-playback.js", '/calibration-editor.js', '/spatial-playback.js'}:
            name = path[1:].replace('-', '_')
            data = Path(__file__).with_name(name).read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)
        elif path == "/api/match":
            static = self.run_dir/'spatial_config.json' if self.run_dir and not job_id else None
            if static and static.is_file():
                config = json.loads(static.read_text(encoding='utf-8'))
                self._send_json(dict(config=config,duration_s=self.run_state.get('duration_s',0),readonly=True))
            else:
                self._send_job_result(self.jobs.match_config, job_id)
        elif path == "/api/spatial":
            static = self.run_dir/'spatial_map.json' if self.run_dir and not job_id else None
            if static and static.is_file():
                self._send_json(json.loads(static.read_text(encoding='utf-8')))
            else:
                self._send_job_result(self.jobs.spatial_map, job_id)
        elif path == "/api/spatial/status":
            self._send_job_result(self.jobs.spatial_status, job_id)
        elif path == "/api/heatmap":
            self._serve_heatmap()
        elif path == "/api/heatmap/grid":
            self._serve_heatmap_grid()
        elif path == "/api/heatmap/image":
            self._serve_heatmap_image()
        elif path == "/api/run_info":
            self._send_json(self.run_state)
        elif path == "/api/export/summary":
            self._serve_export_summary()
        elif path == "/api/video":
            self._serve_video()
        elif path == "/api/overlay":
            overlay = self.run_dir / "web_overlay.json" if self.run_dir else None
            data = json.loads(overlay.read_text(encoding="utf-8")) if overlay and overlay.is_file() else {"frames": []}
            spatial,config=None,None
            if job_id:
                spatial=self.jobs.spatial_map(job_id)
                config_path=self.jobs.root/job_id/'match_config.json'
            else:
                spatial_path=self.run_dir/'spatial_map.json' if self.run_dir else None
                if spatial_path and spatial_path.is_file():
                    spatial=json.loads(spatial_path.read_text(encoding='utf-8'))
                config_path=self.run_dir/'spatial_config.json' if self.run_dir else None
            if config_path and config_path.is_file():
                config=json.loads(config_path.read_text(encoding='utf-8'))
            self._send_json(overlay_with_spatial_identity(data,spatial,config))
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def _send_job_result(self, method, job_id: str | None) -> None:
        try:
            self._send_json(method(job_id))
        except JobError as exc:
            self._send_json({"error": str(exc)}, exc.status)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        origin = self.headers.get("Origin")
        try:
            body_length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            body_length = 0
        body = RequestBody(self.rfile, body_length)
        if (
            self.headers.get("X-Demo-Request") != "1"
            or (origin and urllib.parse.urlparse(origin).netloc != self.headers.get("Host"))
        ):
            # Closing a Windows socket with unread request bytes can reset it
            # before the client receives the 403 response. Drain small bodies
            # with a short deadline; never buffer or wait for a large upload.
            body.discard_small(self.connection)
            self._send_json({"error": "Yêu cầu không hợp lệ."}, 403)
            return
        try:
            if parsed.path == "/api/upload":
                self.connection.settimeout(60)
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    raise JobError("Dung lượng video không hợp lệ.")
                result = self.jobs.upload(body, length, query.get("name", ["video.mp4"])[0])
                self._send_json(result, 201)
            elif parsed.path == "/api/analyze":
                self._send_json(self.jobs.start(query.get("job", [""])[0]), 202)
            elif parsed.path == "/api/cancel":
                self._send_json(self.jobs.cancel(query.get("job", [""])[0]))
            elif parsed.path in {"/api/configure", '/api/calibration/preview'}:
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 2 * 1024**2:
                        raise ValueError()
                    data = json.loads(body.read(length))
                except (ValueError, UnicodeDecodeError):
                    raise JobError("Cấu hình không hợp lệ hoặc quá lớn.")
                method = self.jobs.configure if parsed.path == '/api/configure' else self.jobs.preview_calibration
                self._send_json(method(query.get("job", [""])[0], data))
            elif parsed.path == "/api/rebuild":
                self._send_json(self.jobs.rebuild_spatial_map(query.get("job", [""])[0]), 202)
            else:
                body.discard_small(self.connection)
                self._send_json({"error": "Không tìm thấy thao tác."}, 404)
        except JobError as exc:
            body.discard_small(self.connection)
            self._send_json({"error": str(exc)}, exc.status)
        except (OSError, TimeoutError):
            self._send_json({"error": "Tải video bị gián đoạn. Vui lòng thử lại."}, 400)

    def _serve_html(self) -> None:
        data = DASHBOARD_HTML.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_status(self) -> None:
        self._send_json({
            "status": self.run_state.get("status", "ready"),
            "video_path": str(self.video_path) if self.video_path else None,
            "video_exists": self.video_path.is_file() if self.video_path else False,
            "server_utc": datetime.now(timezone.utc).isoformat(),
            "geometry_status": self.run_state.get("geometry", {}).get("status", "uncalibrated"),
            "spatial_mode": self.run_state.get('spatial_mode'),
            "quality_gate": self.run_state.get("quality_gate", "in_progress"),
            "demo_verdict": self.run_state.get("demo_verdict", "DEMO_PARTIAL"),
            "playback_source_start_s": self.run_state.get("playback", {}).get("source_start_s", 0.0),
            "job": self.run_state.get("job"),
            "roster_matched": self.run_state.get("roster_matched", self.roster is not None),
            "video_name": self.run_state.get("job", {}).get(
                "name", self.video_path.name if self.video_path else ""
            ),
        })

    def _serve_heatmap(self) -> None:
        status = "generated" if self.heatmap_data.get("status") == "generated" else "unavailable"
        self._send_json({"status": status})

    def _serve_heatmap_grid(self) -> None:
        spatial = None
        job_id = self.run_state.get('job',{}).get('id')
        if job_id:
            spatial = self.jobs.spatial_map(job_id)
        elif self.run_dir and (self.run_dir/'spatial_map.json').is_file():
            spatial = json.loads((self.run_dir/'spatial_map.json').read_text(encoding='utf-8'))
        if spatial and spatial.get('geometry_mode') == 'automatic':
            self._send_json(dict(total_grid=spatial['heatmaps']['all'],
                metadata=dict(court_bounds=spatial['bounds'],grid_shape=spatial['grid_shape'],
                              total_player_seconds=spatial['quality']['total_player_seconds'])))
            return
        grid = None
        if self.run_dir:
            grid = self.run_dir / "heatmap" / "heatmap_raw_grid.json"
            if not grid.is_file():
                grid = self.run_dir / "heatmap_raw_grid.json"
        self._send_json(json.loads(grid.read_text(encoding="utf-8")) if grid and grid.is_file() else {})

    def _serve_heatmap_image(self) -> None:
        image = None
        if self.run_dir:
            image = self.run_dir / "heatmap" / "heatmap_total.png"
            if not image.is_file():
                image = self.run_dir / "heatmap.png"
        if not image or not image.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Heatmap image unavailable")
            return
        data = image.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_export_summary(self) -> None:
        payload = json.dumps(self.run_state, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="summary.json"')
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _serve_video(self) -> None:
        if not self.video_path or not self.video_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Video file not found on local storage")
            return

        file_size = self.video_path.stat().st_size
        range_header = self.headers.get("Range")
        start, end = 0, file_size - 1
        if range_header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
            valid = bool(match and any(match.groups()) and file_size)
            if valid:
                first, last = match.groups()
                if first:
                    start = int(first)
                    end = min(int(last), file_size - 1) if last else file_size - 1
                    valid = start < file_size and end >= start
                else:
                    suffix = int(last)
                    start = max(0, file_size - suffix)
                    valid = suffix > 0
            if not valid:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{file_size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
        length = end - start + 1
        self.send_response(HTTPStatus.PARTIAL_CONTENT if range_header else HTTPStatus.OK)
        self.send_header("Content-Type", "video/mp4")
        if range_header:
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        try:
            with self.video_path.open("rb") as handle:
                handle.seek(start)
                remaining = length
                while remaining:
                    chunk = handle.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return

    def _send_json(self, data: Any, status: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def load_run_bundle(run_dir: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Load spatial metadata and optional heatmap artifacts from a run directory."""
    run_dir = Path(run_dir)
    verify_bundle_manifest(run_dir)
    run_path = run_dir / "run.json"
    if not run_path.is_file():
        run_path = run_dir / "summary.json"
    run = json.loads(run_path.read_text(encoding="utf-8")) if run_path.is_file() else {}
    summary_path = run_dir / "heatmap" / "heatmap_summary.json"
    if not summary_path.is_file():
        summary_path = run_dir / "heatmap_summary.json"
    heatmap = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else {}
    safe_run = summarize_run(run, heatmap)
    safe_heatmap = {"status": "generated"} if heatmap.get('status') in {'completed', 'generated'} else {}
    spatial_path=run_dir/'spatial_map.json'
    if spatial_path.is_file():
        spatial=json.loads(spatial_path.read_text(encoding='utf-8'))
        if spatial.get('geometry_mode')=='automatic':
            generated=spatial.get('status')=='completed' and spatial.get('quality',{}).get('projection_fraction',0)>0
            safe_run.update(spatial_mode='automatic',heatmap_status='generated' if generated else 'unavailable')
            safe_heatmap={'status':'generated'} if generated else {}
    return safe_run, safe_heatmap


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def server_close(self):
        if hasattr(self, "jobs"):
            self.jobs.close()
        super().server_close()


def make_dashboard_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    video_path: Optional[Path] = None,
    roster: Optional[RosterConfig] = None,
    run_dir: Optional[Path] = None,
    run_state: Optional[Dict[str, Any]] = None,
    heatmap_data: Optional[Dict[str, Any]] = None,
    jobs_root: Optional[Path] = None,
    explicit_context: bool | None = None,
) -> HTTPServer:
    """Create the local video/tracking/spatial map server."""
    if run_dir:
        loaded_state, loaded_heatmap = load_run_bundle(Path(run_dir))
        if run_state is None:
            run_state = loaded_state
        if heatmap_data is None:
            heatmap_data = loaded_heatmap

    jobs = VideoJobs(jobs_root)
    startup = dict(explicit=bool(run_dir or video_path) if explicit_context is None else explicit_context,
                   job_id=None,has_video=bool(video_path and Path(video_path).is_file()),
                   has_spatial=bool(run_dir and (Path(run_dir)/'spatial_map.json').is_file()))
    if run_dir:
        parent = Path(run_dir).resolve().parent
        if parent.parent == jobs.root and (parent/'job.json').is_file():
            startup['job_id'] = parent.name

    def handler_factory(*args, **kwargs):
        return DashboardRequestHandler(
            *args,
            video_path=video_path,
            roster=roster,
            run_state=run_state,
            heatmap_data=heatmap_data,
            run_dir=Path(run_dir) if run_dir else None,
            jobs=jobs,
            startup_context=startup,
            **kwargs,
        )

    server = DashboardServer((host, port), handler_factory)
    server.jobs = jobs
    return server
