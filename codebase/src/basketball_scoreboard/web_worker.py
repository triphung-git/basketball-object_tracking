"""Background entry point for the spatial video-analysis job."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import traceback

from .web_jobs import write_json

CODEBASE_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = CODEBASE_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
from run_spatial_pipeline import run_spatial_pipeline


def main(directory: Path) -> int:
    job = json.loads((directory / "job.json").read_text(encoding="utf-8"))

    def progress(value):
        fraction = value.get("source_time_s", 0) / max(job["duration_s"], 0.001)
        # Detection and tracking each visit the source clock from zero.
        # Give both stages their own range so progress never jumps backwards.
        stage_progress = 85 * fraction if value.get("stage") == "detection" else 85 + 14 * fraction
        write_json(directory / "progress.json", {
            **value,
            "status": "running",
            "progress": min(99, round(stage_progress, 1)),
        })

    try:
        result = run_spatial_pipeline(
            directory / "input.mp4",
            directory / "analysis",
            progress_callback=progress,
        )
        if result.get("status") != "completed":
            raise RuntimeError("Analysis did not complete")
        tracking = json.loads(
            (directory / "analysis" / "tracking" / "tracking_summary.json").read_text(encoding="utf-8")
        )
        write_json(directory / "outcome.json", {
            "status": "completed",
            "progress": 100,
            "frames_processed": result["counts"]["total_frames_read"],
            "tracks": tracking["total_tracks_initiated"],
            "error": None,
        })
        return 0
    except Exception as exc:
        traceback.print_exc()
        message = "Không phân tích được video. Vui lòng kiểm tra môi trường xử lý và thử lại."
        if isinstance(exc, ModuleNotFoundError):
            message = "Chưa cài đủ thư viện phân tích video trên máy chủ."
        elif "api key" in str(exc).lower() or "roboflow_api_key" in str(exc).lower():
            message = "Chưa cấu hình khóa truy cập mô hình trên máy chủ."
        write_json(directory / "outcome.json", {"status": "failed", "error": message})
        return 1


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]).resolve()))
