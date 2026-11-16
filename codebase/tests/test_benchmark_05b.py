"""Unit and integration tests for Task 05B: Production Benchmark."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from basketball_scoreboard.contracts import CLASS_MAPPING
from basketball_scoreboard.config import APPROVED_MODEL_ID


def test_benchmark_class_mapping_and_contracts():
    assert CLASS_MAPPING[0] == "ball"
    assert CLASS_MAPPING[1] == "human"
    assert CLASS_MAPPING[2] == "rim"


def test_benchmark_results_structure():
    bench_file = Path(__file__).resolve().parents[1] / "outputs/remaining-tasks-20261115/05B/benchmark.json"
    assert bench_file.is_file(), "benchmark.json must exist"

    data = json.loads(bench_file.read_text(encoding="utf-8"))
    assert data["schema_version"] == "benchmark-v1"
    assert "hardware" in data
    assert data["hardware"]["execution_device"] is not None

    # Verify run configuration
    run_cfg = data["run_configuration"]
    assert run_cfg["model_id"] == APPROVED_MODEL_ID
    assert run_cfg["class_mapping"]["0"] == "ball" or run_cfg["class_mapping"][0] == "ball"

    # Verify execution summary
    summary = data["execution_summary"]
    assert summary["total_frames_processed"] == 900
    assert summary["pipeline_fps"] > 30.0  # Faster than real-time

    # Verify two distinct profiles
    profiles = data["profiles"]
    assert "profile_a_online_cpu_inference" in profiles
    assert "profile_b_production_pipeline" in profiles
    assert profiles["profile_a_online_cpu_inference"]["fps"] < 10.0
    assert profiles["profile_b_production_pipeline"]["fps"] > 30.0

    # Verify stage stats have p50 and p95
    stages = data["per_stage_latencies_ms"]
    for s_name in ["decode", "detect_ingestion", "tracking", "temporal_shot_fsm", "total_frame"]:
        assert s_name in stages
        assert "p50" in stages[s_name]
        assert "p95" in stages[s_name]
        assert "mean" in stages[s_name]

    # Verify confirmation delay honors null for unobserved events
    delays = data["event_confirmation_delays"]
    assert delays["shot_made_vt_dev_0009"]["confirmation_delay_s"] == 1.1
    assert delays["rebound_confirmation_delay"] is None
    assert delays["assist_confirmation_delay"] is None

    # Verify offline status
    boundary = data["offline_vs_live_boundary"]
    assert boundary["status"] == "OFFLINE_VERIFIED"
    assert boundary["is_live_ready"] is False
