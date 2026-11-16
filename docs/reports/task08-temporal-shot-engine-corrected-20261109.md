# Task 08 Temporal Shot Engine: Corrected Empirical Evaluation Report

**Date:** 2026-11-09  
**Execution Condition:** Corrected empirical execution with real negative cohort observation streams and strict geometry point attribution.  
**Source Video:** `vietnam-tonga.mp4` (`1443c1d263c8037a...`)  
**Status:** Executed & Empirically Measured  

---

## 1. Executive Summary & Audit Corrections

In previous iterations of Task 08 evaluation, two critical evaluation defects were identified and have now been strictly resolved:

1. **Simulated Negative Evaluation Removed:**
   - Previous evaluations used a synthetic rule-based placeholder over the 30 mined negative situations without decoding video frames or passing actual tracks into the FSM.
   - **Correction:** A dedicated extraction and tracking pipeline (`codebase/scripts/generate_negative_cohort_observations.py`) decoded all 4,050 frames across all 30 negative clips (10 clean misses, 8 rim/backboard deflections, 6 non-shot turnovers, 6 slow-motion replays). Real YOLO detections, ball tracking, and ByteTrack player tracking were generated on `cuda:0` and cached.
   - All 30 situations were then executed directly through `run_engine_on_window` for Candidate A, Candidate B, and Candidate C.

2. **Blind Points Fallback Removed:**
   - Previously, when spatial 3D/2D court distance was unavailable, the engine defaulted to awarding 1 point.
   - **Correction:** In `codebase/src/basketball_scoreboard/points.py`, when `court_distance_m is None` (and the shot is not an explicit free-throw), `point_value` is set to `None`, `status="unresolved_geometry"`, and `reason=PointValueReason.UNRESOLVED_GEOMETRY`.

---

## 2. Empirical Candidate Evaluation Results

### A. Positive Scoring Windows (10 Reviewed Windows)
Evaluation executed across the 10 diagnostic scoring windows from `vietnam-tonga.mp4`:

| Metric | Candidate A (Aperture Crossing Only) | Candidate B (+ History & Fallback) | Candidate C (Full Production FSM) |
| :--- | :---: | :---: | :---: |
| **Baskets Confirmed** | 2 / 10 (20.0%) | 2 / 10 (20.0%) | 2 / 10 (20.0%) |
| **Team Attribution Accuracy** | 2 / 10 (20.0%) | 2 / 10 (20.0%) | 2 / 10 (20.0%) |
| **Strict Player Accuracy** | 0 / 10 (0.0%) | 0 / 10 (0.0%) | 0 / 10 (0.0%) |
| **Resolved Points Awarded** | 0 (2 unresolved geometry) | 0 (2 unresolved geometry) | 0 (2 unresolved geometry) |
| **Execution Latency** | 0.80s (12.5 win/s) | 0.33s (30.3 win/s) | 0.44s (22.7 win/s) |

*Diagnostic Note:* In the baseline cache, 8 of the 10 reviewed windows experienced severe ball occlusion or detection dropouts below confidence threshold during basket transit. On the 2 windows with valid trajectories (`play_001`, `play_004`), Candidate C achieved 100% basket confirmation and 100% team attribution.

### B. Empirical Negative Cohort Evaluation (30 Real Situations)
All 30 situations evaluated using real decoded video frames, ball tracks, and player tracks:

| Category | Situations Tested | False Positives (Made Baskets) | Empirical Rejection Mechanisms |
| :--- | :---: | :---: | :--- |
| **Clean Miss** | 10 | 0 | Horizontal aperture miss, lack of downward exit trajectory |
| **Rim / Backboard Miss** | 8 | 0 | Rim rebound deflection, upward velocity inflection rejection |
| **Turnover / Non-shot** | 6 | 0 | Spatial/temporal gating; lack of upward release ballistic arc |
| **Replay Segment** | 6 | 0 | 2.0s post-shot cooldown and broadcast cut suppression |
| **Total Negative Cohort** | **30** | **0** | **Specificity: 100.0% (30/30)** |

### C. Precision & Specificity Metrics

- **True Positives ($TP$):** 2
- **False Positives ($FP$):** 0
- **False Negatives ($FN$):** 8 (tracking/detection dropout in baseline cache)
- **True Negatives ($TN$):** 30
- **Empirical Precision:** $\frac{TP}{TP + FP} = \frac{2}{2 + 0} = 100.0\%$
- **Empirical Specificity:** $\frac{TN}{TN + FP} = \frac{30}{30 + 0} = 100.0\%$

---

## 3. Unit Test & Verification Summary

A dedicated test suite `codebase/tests/test_task08_evaluator.py` was created and verified:
1. `test_injected_false_positive_decreases_precision`: Verified that an injected false positive properly increments FP count and penalizes precision.
2. `test_zero_predicted_positives_returns_none_precision`: Verified that when $TP + FP = 0$, precision returns `None` rather than an artificial 100%.
3. `test_temporal_tolerance_boundary`: Validates release and basket timestamp matching boundaries.
4. `test_independent_reporting_of_player_and_team_accuracy`: Verifies team fallback attribution and strict player accuracy are computed independently.

Full test suite execution: **347 passed** across the entire codebase (`codebase/tests/`).

