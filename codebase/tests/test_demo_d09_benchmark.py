import json
from pathlib import Path
import pytest


def test_d09_benchmark_json_structure():
    benchmark_file = (Path(__file__).resolve().parents[1] / "outputs/demo-completion-20261116/D09/benchmark/benchmark.json")
    assert benchmark_file.exists(), f"Benchmark file does not exist at {benchmark_file}"

    with open(benchmark_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["schema_version"] == "benchmark-v1"
    assert "hardware" in data
    assert "run_configuration" in data
    assert "execution_summary" in data
    assert "profiles" in data
    assert "per_stage_latencies_ms" in data

    # Execution summary
    summary = data["execution_summary"]
    assert summary["total_frames_processed"] > 0
    assert summary["pipeline_fps"] > 0
    assert summary["memory"]["peak_rss_mb"] > 0

    # Profiles A and B
    profiles = data["profiles"]
    assert "profile_a_online_cpu_inference" in profiles
    assert "profile_b_production_pipeline" in profiles
    assert profiles["profile_a_online_cpu_inference"]["mean_ms_per_frame"] > 0
    assert profiles["profile_b_production_pipeline"]["fps"] > 0
    assert profiles["profile_b_production_pipeline"]["status"] == "OFFLINE_VERIFIED"


def test_d09_per_stage_timings_structure():
    benchmark_file = (Path(__file__).resolve().parents[1] / "outputs/demo-completion-20261116/D09/benchmark/benchmark.json")
    with open(benchmark_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    per_stage = data["per_stage_latencies_ms"]
    required_stages = [
        "decode",
        "detect_ingestion",
        "tracking",
        "identity",
        "control_possession",
        "temporal_shot_fsm",
        "points_reb_ast",
        "boxscore_ledger",
        "total_frame"
    ]
    for stage in required_stages:
        assert stage in per_stage, f"Stage {stage} missing from benchmark per_stage_latencies_ms"
        assert per_stage[stage]["mean"] >= 0.0, f"Stage {stage} has negative mean latency"
        assert per_stage[stage]["p95"] >= per_stage[stage]["p50"], f"Stage {stage} p95 must be >= p50"

    # Invariants on main compute stages: decode, tracking, identity must be > 0
    assert per_stage["decode"]["mean"] > 0.0
    assert per_stage["tracking"]["mean"] > 0.0
    assert per_stage["identity"]["mean"] > 0.0
    assert per_stage["total_frame"]["mean"] > 0.0


def test_d09_per_stage_jsonl_log():
    jsonl_file = (Path(__file__).resolve().parents[1] / "outputs/demo-completion-20261116/D09/benchmark/per_stage_timings.jsonl")
    assert jsonl_file.exists(), f"Timing jsonl missing at {jsonl_file}"
    
    line_count = 0
    with open(jsonl_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                assert "frame_index" in item
                assert "total_frame_ms" in item
                assert item["total_frame_ms"] > 0
                line_count += 1
                
    assert line_count == 200, f"Expected 200 frame timings, got {line_count}"
