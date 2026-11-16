# Task 09 & 10: Automatic Rebounds and Assists Modules Report

**Date:** 2026-11-09  
**Modules:** `codebase/src/basketball_scoreboard/rebounds.py`, `codebase/src/basketball_scoreboard/assists.py`  
**Test Suites:** `codebase/tests/test_task09_rebounds.py` (4/4 passed), `codebase/tests/test_task10_assists.py` (5/5 passed)  
**Status:** Implemented, Integrated & Verified  

---

## 1. Executive Summary

Task 09 (Rebounds) and Task 10 (Assists) expand the automatic stats engine beyond shot scoring into comprehensive box-score stat generation. Both modules enforce strict physical and causal rulesets to eliminate synthetic or accidental stat inflation.

---

## 2. Rebounds Engine Specification & Guarantees (Task 09)

1. **Eligibility Guard:**
   - A rebound window opens strictly following a missed field goal or the final missed free throw of a series.
   - Made baskets are strictly excluded (`shot_outcome == 'made' -> None`).
2. **Multi-Frame Control Requirement:**
   - Single-frame glancing contacts or bounding box brushes are filtered out (`min_control_frames >= 4` or `duration >= 0.15s`).
3. **Offensive vs. Defensive Classification:**
   - Recovers by the shooting team are classified as `offensive_rebound`.
   - Recovers by the opposing team are classified as `defensive_rebound`.
   - Ambiguous or non-player recoveries are recorded as `team_rebound`.
4. **Ledger Integration:**
   - Seamlessly converts to `LedgerEventRecord` with `event_type = EventType.REBOUND`, linking to the parent missed shot.

---

## 3. Assists Engine Specification & Guarantees (Task 10)

1. **Eligibility Guard:**
   - Evaluated strictly upon confirmed made baskets (`shot_outcome == 'made'`).
   - Requires confirmed scorer team and player attribution.
2. **Causal Pass Chain & Teammate Verification:**
   - The candidate pass must originate from a verified teammate (`passer_team == scorer_team`) and cannot be a self-pass (`passer_id != scorer_id`).
   - Enforces a temporal window from catch to shot release ($\Delta t \le 4.0$s).
3. **Invalidation Cascade & Chain Breaks:**
   - Any intervening turnover, defensive deflection, loose ball, or offensive rebound (`miss -> offensive rebound -> score`) breaks the assist chain.
4. **Ledger Integration & Invalidation Cascade:**
   - Converts to `LedgerEventRecord` with `event_type = EventType.ASSIST`, setting `parent_event_id` to the parent shot event.
   - If the parent shot is subsequently voided or overturned in the ledger, the assist is automatically invalidated via causal cascade.

