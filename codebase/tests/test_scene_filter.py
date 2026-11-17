"""Unit tests for SceneFilter heuristic."""
from __future__ import annotations

import numpy as np
import pytest

from basketball_scoreboard.scene_filter import FilterResult, SceneFilter


def test_scene_filter_initialization():
    sf = SceneFilter(motion_threshold=30.0, min_variance=10.0)
    summary = sf.get_summary()
    assert summary["total_inspected"] == 0
    assert summary["total_skipped"] == 0
    assert summary["skip_rate"] == 0.0


def test_scene_filter_normal_frames():
    sf = SceneFilter(motion_threshold=40.0)
    # Generate realistic frame with texture
    rng = np.random.default_rng(42)
    base_frame = rng.integers(50, 200, size=(180, 320, 3), dtype=np.uint8)

    # Frame 0
    r0 = sf.inspect_frame(base_frame, pts_s=0.0, frame_index=0)
    assert not r0.skip
    assert r0.reason is None

    # Frame 1: minor noise/motion (below threshold)
    frame1 = np.clip(base_frame.astype(np.int16) + rng.integers(-5, 5, size=(180, 320, 3)), 0, 255).astype(np.uint8)
    r1 = sf.inspect_frame(frame1, pts_s=0.033, frame_index=1)
    assert not r1.skip
    assert r1.motion_score < 40.0


def test_scene_filter_empty_frame():
    sf = SceneFilter()
    r = sf.inspect_frame(np.array([], dtype=np.uint8), pts_s=1.0, frame_index=10)
    assert r.skip
    assert r.reason == "empty_frame"
    assert sf.get_summary()["total_skipped"] == 1


def test_scene_filter_solid_wash_transition():
    sf = SceneFilter(min_variance=12.0)
    # A solid gray frame has zero variance
    solid_gray = np.full((180, 320, 3), fill_value=128, dtype=np.uint8)
    r = sf.inspect_frame(solid_gray, pts_s=2.0, frame_index=20)
    assert r.skip
    assert r.reason == "low_variance_transition"


def test_scene_filter_extreme_exposure():
    sf = SceneFilter()
    # Almost completely blown out white frame
    white_frame = np.full((180, 320, 3), fill_value=252, dtype=np.uint8)
    r = sf.inspect_frame(white_frame, pts_s=3.0, frame_index=30)
    assert r.skip
    assert r.reason in {"extreme_exposure", "low_variance_transition"}


def test_scene_filter_whip_pan():
    sf = SceneFilter(motion_threshold=25.0)
    rng = np.random.default_rng(123)
    frame1 = rng.integers(60, 180, size=(180, 320, 3), dtype=np.uint8)
    r1 = sf.inspect_frame(frame1, pts_s=4.0, frame_index=40)
    assert not r1.skip

    # Frame 2 is drastically shifted / inverted (huge MAD)
    frame2 = (255 - frame1).astype(np.uint8)
    r2 = sf.inspect_frame(frame2, pts_s=4.033, frame_index=41)
    assert r2.skip
    assert r2.reason == "whip_pan_or_cut"
    assert r2.motion_score > 25.0


def test_scene_filter_reset_and_summary():
    sf = SceneFilter()
    solid = np.full((180, 320, 3), 100, dtype=np.uint8)
    sf.inspect_frame(solid, 1.0, 1)
    sf.inspect_frame(solid, 2.0, 2)
    summary = sf.get_summary()
    assert summary["total_inspected"] == 2
    assert summary["total_skipped"] == 2

    sf.reset()
    assert sf._prev_gray is None
