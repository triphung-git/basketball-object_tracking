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


DASHBOARD_HTML = Path(__file__).with_name("dashboard.html").read_text(encoding="utf-8")


def spatial_overlay(data: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only video-frame bbox data when serving legacy run artifacts."""
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
            boxes.append(box)
        frames.append({"time": frame["time"], "boxes": boxes})
    return {"frames": frames}


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
    ) -> None:
        self.video_path = video_path
        self.roster = roster
        self.run_state = run_state or {}
        self.heatmap_data = heatmap_data or {}
        self.run_dir = run_dir
        self.jobs = jobs
        super().__init__(request, client_address, server)

    def log_message(self, format: str, *args: Any) -> None:
        pass

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        job_id = query.get("job", [None])[0]
        try:
            if path == "/api/active-job":
                self._send_json({"job": self.jobs.active()})
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
        elif path == "/match-dashboard.js":
            data = Path(__file__).with_name("match_dashboard.js").read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif path == "/api/match":
            self._send_job_result(self.jobs.match_config, job_id)
        elif path == "/api/spatial":
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
            self._send_json(spatial_overlay(data))
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
        if (
            self.headers.get("X-Demo-Request") != "1"
            or (origin and urllib.parse.urlparse(origin).netloc != self.headers.get("Host"))
        ):
            # Closing a Windows socket with unread request bytes can reset it
            # before the client receives the 403 response. Drain small bodies
            # with a short deadline; never buffer or wait for a large upload.
            try:
                remaining = int(self.headers.get("Content-Length", "0"))
                if 0 < remaining <= 2 * 1024**2:
                    self.connection.settimeout(1)
                    while remaining:
                        chunk = self.rfile.read(min(65536, remaining))
                        if not chunk:
                            break
                        remaining -= len(chunk)
            except (ValueError, OSError):
                pass
            self._send_json({"error": "Yêu cầu không hợp lệ."}, 403)
            return
        try:
            if parsed.path == "/api/upload":
                self.connection.settimeout(60)
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    raise JobError("Dung lượng video không hợp lệ.")
                result = self.jobs.upload(self.rfile, length, query.get("name", ["video.mp4"])[0])
                self._send_json(result, 201)
            elif parsed.path == "/api/analyze":
                self._send_json(self.jobs.start(query.get("job", [""])[0]), 202)
            elif parsed.path == "/api/cancel":
                self._send_json(self.jobs.cancel(query.get("job", [""])[0]))
            elif parsed.path == "/api/configure":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 2 * 1024**2:
                        raise ValueError()
                    data = json.loads(self.rfile.read(length))
                except (ValueError, UnicodeDecodeError):
                    raise JobError("Cấu hình không hợp lệ hoặc quá lớn.")
                self._send_json(self.jobs.configure(query.get("job", [""])[0], data))
            elif parsed.path == "/api/rebuild":
                self._send_json(self.jobs.rebuild_spatial_map(query.get("job", [""])[0]), 202)
            else:
                self._send_json({"error": "Không tìm thấy thao tác."}, 404)
        except JobError as exc:
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
    safe_heatmap = {"status": "generated"} if heatmap else {}
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
) -> HTTPServer:
    """Create the local video/tracking/spatial map server."""
    if run_dir:
        loaded_state, loaded_heatmap = load_run_bundle(Path(run_dir))
        if run_state is None:
            run_state = loaded_state
        if heatmap_data is None:
            heatmap_data = loaded_heatmap

    jobs = VideoJobs(jobs_root)

    def handler_factory(*args, **kwargs):
        return DashboardRequestHandler(
            *args,
            video_path=video_path,
            roster=roster,
            run_state=run_state,
            heatmap_data=heatmap_data,
            run_dir=Path(run_dir) if run_dir else None,
            jobs=jobs,
            **kwargs,
        )

    server = DashboardServer((host, port), handler_factory)
    server.jobs = jobs
    return server
