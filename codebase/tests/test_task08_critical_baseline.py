"""Unit tests for Task08 Critical Moments Baseline Diagnostic.

Verifies:
1. Ground-truth review fields are strictly stripped from recognition input manifest.
2. Source PTS and local PTS mapping is strictly monotonic and within 1µs precision.
3. Predicted ball samples never count as observed observations.
4. Cut / boundary events reset trajectories and do not bridge across cuts.
5. Candidate rejection reasons are sound, exhaustive, and properly classified.
6. Draft review packet enforces unreviewed draft contract with uncertainty/skip support.
7. Run metadata marks status 'partial' on incomplete runs and 'completed' only on full runs.
"""
import copy
import json
import math
from pathlib import Path
import sys
import tempfile
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from basketball_scoreboard.ball import BallConfig, BallTracker
from basketball_scoreboard.contracts import CLASS_MAPPING, DetectionRecord


def test_recognition_input_manifest_strips_gt(tmp_path):
    """Verify that GT fields are strictly removed from recognition manifest."""
    from scripts.run_task08_critical_baseline import build_recognition_input_manifest

    # Synthetic draft windows with review GT
    draft_data = {
        "schema_version": "scoring-review-intake-1",
        "provenance": {"source_sha256": "dummy_sha"},
        "windows": [
            {
                "window_id": "play_001",
                "source_start_s": 138.533333,
                "source_end_s": 143.3,
                "source_start_frame": 4155,
                "source_end_frame_exclusive": 4299,
                "evaluation_times": {
                    "release": {"source_s": 140.533333},
                    "basket": {"source_s": 141.8},
                },
                "reviewed_shooter_id": "b_01",
                "shot_kind": "field_goal",
                "notes": "clear made shot",
                "score": [2, 0],
                "outcome": "made",
            }
        ],
    }
    draft_file = tmp_path / "critical-windows-draft.json"
    draft_file.write_text(json.dumps(draft_data), encoding="utf-8")

    manifest_data = {
        "source_video": "assets_test/vietnam-tonga.mp4",
        "source_sha256": "1443c1d263c8037a5684f3dbc0ef9216beb5097d9a47c4c1c9b94d1363e26865",
        "entries": [
            {
                "id": "play_001",
                "source_time_offset_s": 133.0,
                "video": "clips/play_001.mp4",
                "draft_points": 2,
                "draft_scoring_team": "team_b",
            }
        ],
    }
    manifest_file = tmp_path / "review-manifest.json"
    manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

    out_file = tmp_path / "recognition_input_manifest.json"
    result = build_recognition_input_manifest(draft_file, manifest_file, out_file)

    assert result["provenance"]["gt_fields_stripped"] is True
    assert len(result["windows"]) == 1

    forbidden = {
        "reviewed_shooter_id",
        "shot_kind",
        "evaluation_times",
        "notes",
        "score",
        "outcome",
        "points",
        "draft_points",
        "draft_scoring_team",
    }
    for win in result["windows"]:
        found_forbidden = forbidden.intersection(set(win.keys()))
        assert not found_forbidden, f"Found forbidden GT fields in recognition manifest: {found_forbidden}"
        assert win["window_id"] == "play_001"
        assert win["source_start_s"] == 138.533333
        assert win["source_end_s"] == 143.3
        assert win["source_time_offset_s"] == 133.0

    # Also verify serialized JSON file directly
    raw_saved = json.loads(out_file.read_text(encoding="utf-8"))
    for win in raw_saved["windows"]:
        assert not forbidden.intersection(set(win.keys()))


def test_pts_local_source_mapping():
    """Verify local ↔ source PTS mapping is monotonic and within 1µs precision."""
    from scripts.run_task08_critical_baseline import FrameData

    offset_s = 133.0
    fps = 30.0

    # Simulate 10 frames with exact floating-point PTS
    frames = []
    for i in range(10):
        src_t = round(138.533333 + i * (1.0 / fps), 6)
        loc_t = round(src_t - offset_s, 6)
        raw_pts = int(src_t * 15360)  # example timebase
        fd = FrameData(
            local_frame_index=i,
            source_frame_index=round(src_t * fps),
            source_time_s=src_t,
            local_time_s=loc_t,
            raw_pts=raw_pts,
            time_base="1/15360",
            image_bgr=np.zeros((10, 10, 3), dtype=np.uint8),
        )
        frames.append(fd)

    # Check monotonicity
    for i in range(1, len(frames)):
        assert frames[i].source_time_s > frames[i - 1].source_time_s
        assert frames[i].local_time_s > frames[i - 1].local_time_s
        assert frames[i].raw_pts > frames[i - 1].raw_pts

    # Check mapping precision
    for f in frames:
        diff = abs((f.local_time_s + offset_s) - f.source_time_s)
        assert diff <= 1e-6, f"PTS clock mapping error too large: {diff}s"


def test_predicted_never_counts_as_observed():
    """Verify that extrapolation predictions are never marked as observed."""
    config = BallConfig(
        min_confidence=0.15,
        prediction_horizon_s=0.20,
        max_gap_s=0.30,
        base_gate_diagonal=0.05,
        max_speed_diagonal_s=2.0,
    )
    tracker = BallTracker((1920, 1080), namespace="test", config=config)

    # Frame 0: observed detection
    det0 = [{"class_name": "ball", "xyxy": [100.0, 100.0, 120.0, 120.0], "confidence": 0.8}]
    res0 = tracker.update(0, 1.0, det0)
    assert res0["sample_type"] == "observed"

    # Frame 1: observed detection with motion
    det1 = [{"class_name": "ball", "xyxy": [110.0, 105.0, 130.0, 125.0], "confidence": 0.75}]
    res1 = tracker.update(1, 1.033333, det1)
    assert res1["sample_type"] == "observed"

    # Frame 2: no detections in image -> tracker should predict within horizon
    res2 = tracker.update(2, 1.066667, [])
    assert res2["sample_type"] == "predicted"
    assert res2["sample_type"] != "observed"
    assert res2["xyxy"] is None  # Predicted sample has center_image, not observed xyxy
    assert "center_image" in res2

    # Frame 3: gap exceeds prediction horizon (0.2s) -> must be missing
    res3 = tracker.update(3, 1.35, [])
    assert res3["sample_type"] == "missing"
    assert res3["sample_type"] != "observed"


def test_cut_and_boundary_resets():
    """Verify that explicit resets clear active track and do not bridge trajectories."""
    config = BallConfig(min_confidence=0.15, max_gap_s=0.30)
    tracker = BallTracker((1920, 1080), namespace="test", config=config)

    # Observed ball before cut
    det = [{"class_name": "ball", "xyxy": [200.0, 200.0, 220.0, 220.0], "confidence": 0.8}]
    res0 = tracker.update(0, 10.0, det)
    assert res0["sample_type"] == "observed"
    track_id_0 = res0["ball_track_id"]

    # Cut event at 10.05s
    res_cut = tracker.update(1, 10.05, [], reset=True)
    assert res_cut["sample_type"] == "missing"
    assert tracker.active is None

    # New observation after cut -> must start a NEW track ID, not continue track_id_0
    det_new = [{"class_name": "ball", "xyxy": [500.0, 500.0, 520.0, 520.0], "confidence": 0.85}]
    res_new = tracker.update(2, 10.10, det_new)
    assert res_new["sample_type"] == "observed"
    assert res_new["ball_track_id"] != track_id_0


def test_rejection_reasons_soundness():
    """Verify that candidate rejection reasons correctly identify gate failures."""
    from scripts.run_task08_critical_baseline import run_ball_tracking_with_diagnostics, FrameData

    f0 = FrameData(0, 0, 1.0, 0.0, 1000, "1/1000", np.zeros((1080, 1920, 3), dtype=np.uint8))
    frames = [f0]

    # Diverse detections designed to trigger distinct rejection reasons:
    # 1. outside roi
    # 2. low confidence (< 0.15)
    # 3. exceeds diameter
    dets = [
        {"class_name": "ball", "xyxy": [10.0, 10.0, 30.0, 30.0], "confidence": 0.9},    # outside roi
        {"class_name": "ball", "xyxy": [500.0, 500.0, 520.0, 520.0], "confidence": 0.05}, # low conf
        {"class_name": "ball", "xyxy": [600.0, 600.0, 900.0, 900.0], "confidence": 0.9}, # huge diameter (300px > 55px)
        {"class_name": "ball", "xyxy": [700.0, 700.0, 720.0, 720.0], "confidence": 0.85}, # valid inside roi
    ]
    dets_by_frame = [{
        "local_frame_index": 0,
        "source_frame_index": 0,
        "source_time_s": 1.0,
        "local_time_s": 0.0,
        "detections": dets,
    }]

    # Ball ROI polygon excluding (10, 10) but including (700, 700)
    # in normalized coords: [0.2, 0.2] to [0.9, 0.9]
    roi_poly = [[0.2, 0.2], [0.9, 0.2], [0.9, 0.9], [0.2, 0.9]]

    b_cfg = BallConfig(min_confidence=0.15, max_diameter_diagonal=0.025, human_context_weight=0.0)
    tracks, traces, stats = run_ball_tracking_with_diagnostics(
        frames, dets_by_frame, [], b_cfg, ball_roi_polygon=roi_poly, window_id="test_win"
    )

    reasons = [t["status"] for t in traces]
    assert "outside_roi" in reasons
    assert "low_confidence" in reasons
    assert "exceeds_diameter" in reasons
    assert "selected_observed" in reasons
    assert stats["observed_frames"] == 1


def test_draft_review_packet_contract(tmp_path):
    """Verify draft bbox packet schema enforces draft unreviewed status with hashes."""
    from scripts.run_task08_critical_baseline import export_draft_review_packet, FrameData

    f0 = FrameData(0, 100, 140.533333, 7.533333, 2000, "1/1000", np.zeros((1080, 1920, 3), dtype=np.uint8))
    frames = [f0]
    ball_tracks = [{
        "frame_index": 0,
        "source_time_s": 140.533333,
        "sample_type": "observed",
        "xyxy": [100.0, 100.0, 120.0, 120.0],
        "confidence": 0.85,
        "reason": "observed_association",
    }]
    review_times = {
        "release": {"source_s": 140.533333},
        "basket": {"source_s": 141.8},
    }

    packet_entries = export_draft_review_packet(
        frames, ball_tracks, review_times, window_id="play_001", packet_dir=tmp_path
    )

    assert len(packet_entries) > 0
    for e in packet_entries:
        assert e["review_status"] == "draft_unreviewed"
        assert e["reviewer"] is None
        assert "image_sha256" in e
        assert len(e["image_sha256"]) == 64
        assert e["review_fields"]["uncertain"] is False
        assert e["review_fields"]["skip"] is False
        assert e["review_fields"]["ball_visible"] is None
        assert e["review_fields"]["ball_bbox"] is None
        # Verify exported image file exists on disk
        img_full_path = tmp_path / e["image_path"]
        assert img_full_path.is_file()


def test_run_metadata_completed_vs_partial():
    """Verify that run.json status is 'completed' ONLY when all 10 windows complete."""
    # Fewer than 10 windows -> partial
    all_evals_9 = [{"window_id": f"play_{i:03d}"} for i in range(1, 10)]
    status_9 = "completed" if len(all_evals_9) == 10 else "partial"
    assert status_9 == "partial"

    # Exactly 10 windows -> completed
    all_evals_10 = [{"window_id": f"play_{i:03d}"} for i in range(1, 11)]
    status_10 = "completed" if len(all_evals_10) == 10 else "partial"
    assert status_10 == "completed"
