import json

import run_spatial_pipeline as runner
from test_spatial_pipeline_regressions import _court


def test_pipeline_runs_detection_tracking_and_optional_heatmap_without_stats(tmp_path, monkeypatch):
    video = tmp_path / "source.mp4"
    video.write_bytes(b"video")
    (tmp_path / 'court.json').write_text(json.dumps(_court(video)), encoding='utf-8')
    output = tmp_path / "run"
    calls = {}

    def run_detection(video_path, output_dir, **kwargs):
        calls["detection"] = kwargs
        output_dir.mkdir(parents=True)
        (output_dir / "detections.jsonl").write_text(
            json.dumps({"source_time_s": 0, "detections": []}), encoding="utf-8"
        )
        (output_dir / "run.json").write_text("{}", encoding="utf-8")
        return {
            "status": "completed",
            "video_id": "video-id",
            "source_fingerprint_sha256": "source-hash",
            "video_metadata": {"fps": 30},
            "counts": {"total_frames_read": 1},
            "timings": {},
        }

    def track_players(detections_path, tracking_dir, **kwargs):
        calls["tracking"] = kwargs
        tracking_dir.mkdir(parents=True)
        (tracking_dir / "tracked_observations.jsonl").write_text(
            json.dumps({
                "source_time_s": 0,
                "sample_type": "observed",
                "role": "player",
                "track_id": "track-1",
                "bbox": [1, 2, 30, 40],
            }),
            encoding="utf-8",
        )
        (tracking_dir / "tracking_summary.json").write_text(
            json.dumps({"status": "completed", "total_tracks_initiated": 1, "total_observations_generated": 1}),
            encoding="utf-8",
        )
        return 0

    def generate_heatmap(court_config, observations, heatmap_dir, **kwargs):
        calls["heatmap"] = (court_config, observations, kwargs)
        heatmap_dir.mkdir(parents=True)
        return 0

    monkeypatch.setattr(runner, "run_pipeline", run_detection)
    monkeypatch.setattr(runner, "track_players_pipeline", track_players)
    monkeypatch.setattr(runner, "generate_heatmap_pipeline", generate_heatmap)

    result = runner.run_spatial_pipeline(
        video, output, court_config_path=tmp_path / "court.json", max_frames=1
    )

    assert calls["detection"]["export_video"] is False
    assert calls["detection"]["config"].video.max_frames == 1
    assert calls["tracking"]["enable_ocr"] is False
    assert calls["tracking"]["allow_uncalibrated"] is True
    assert result["spatial"]["heatmap_status"] == "generated"
    assert result["spatial"]["tracks"] == 1
    overlay = json.loads((output / "web_overlay.json").read_text(encoding="utf-8"))
    assert overlay["frames"][0]["boxes"][0]["id"] == "track-1"
    run = json.loads((output / "run.json").read_text(encoding="utf-8"))
    assert not {"points", "assists", "rebounds", "shots", "events", "boxscore"} & run.keys()
