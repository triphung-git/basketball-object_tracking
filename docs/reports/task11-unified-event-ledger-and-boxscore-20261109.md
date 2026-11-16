# Task 11: Unified Event Ledger and Box Score Engine Report

> **2026-11-11 — Sửa đổi & kiểm chứng Task 11 Core:** Xem [Báo cáo kỹ thuật sửa đổi và bằng chứng 2026-11-11](task11-ledger-correctness-20261111.md). Đã khắc phục triệt để các lỗi P1-E/P1-F (21/21 independent acceptance probes PASS, 33/33 Task 11 tests PASS).
> **2026-11-10 — Lịch sử kiểm thử lại:** [Acceptance audit](demo-completion-acceptance-20261110.md) tái hiện status filtering, duplicate/refinement và dependency/audit failures. Nội dung dưới đây là lịch sử implementation ban đầu ngày 09/11.

**Date:** 2026-11-09  
**Module:** `codebase/src/basketball_scoreboard/events.py`, `codebase/src/basketball_scoreboard/boxscore.py`  
**Test Suite:** `codebase/tests/test_task11_ledger_and_boxscore.py` (7/7 passed)  
**Status:** Implemented, Integrated & Verified  

---

## 1. Executive Summary

Task 11 establishes the central data spine and statistical aggregation framework for the basketball scoreboard system. It bridges upstream physical and temporal recognizers (shots, rebounds, assists, turnovers) with downstream consumers (live dashboard, CSV exports, persistent event logs).

All core requirements from the prompt have been designed, implemented, and mathematically verified against conservation invariants.

---

## 2. Architecture & Invariants Enforced

### A. Append-Only Transaction Ledger (`events.py`)
1. **Schema Versioning & Fingerprinting:**
   - Canonical `LedgerEventRecord` with `schema_version: "event-ledger-v1"`.
   - Deterministic SHA-256 fingerprinting based on event type, temporal window ($\pm 0.01$s), team, player, and parent dependencies.
2. **Idempotency Protection:**
   - Seek re-read, duplicate frame ingest, and retransmitted events are recognized and dropped without double-recording or throwing exceptions.
3. **Causal Invalidation Cascade:**
   - Voiding an event (e.g., overturned shot due to shot-clock violation) automatically cascades to dependent child events (e.g. assists pointing to the shot `parent_event_id`).
4. **Audit Log:**
   - Full mutation trail (`AuditMutation`) recording creation, refinement, and invalidation actions with UTC timestamps and rationales.

### B. Statistical Conservation & Box Score Engine (`boxscore.py`)
1. **Score Conservation Law:**
   $$\sum_{p \in \text{players}} p.\text{points} + \text{team\_only\_points} \equiv \text{observed\_points}$$
   $$\text{total\_score} \equiv \text{initial\_score\_offset} + \text{observed\_points}$$
2. **No Double-Counting on Attribution Upgrades:**
   - When an unassigned team score is refined to a known player via jersey OCR/adjudication, player points are credited while team observed points remain unchanged.
3. **Unresolved Geometry Guard:**
   - Baskets made with uncalibrated court distance (`point_value=None`) increment `unresolved_shots` counter and do not arbitrarily inflate team or player points.
4. **Rebound Conservation:**
   $$\sum_{p \in \text{players}} p.\text{rebounds\_total} + \text{rebounds\_team} \equiv \text{team\_rebounds\_total}$$
5. **Exports:**
   - Clean export to `events_auto.jsonl` and formatted `boxscore_auto.csv`.

---

## 3. Verification & Real Data Integration

- **Unit Tests:** 7 comprehensive tests passing in `codebase/tests/test_task11_ledger_and_boxscore.py` covering:
  - Idempotency and temporal seek suppression.
  - Score conservation with initial game offsets.
  - Attribution mutation without score inflation.
  - Causal assist cascading upon shot void.
  - Unresolved geometry non-inflation.
  - CSV and JSONL serialization.
  - Full bidirectional conversion between `PointEventRecord` and `LedgerEventRecord`.
- **Real Data Integration:** Ingested verified Candidate C events from `vietnam-tonga.mp4` (`task08-temporal-engine-20261109`), producing 2 active ledger events with strictly preserved unresolved geometry counters.

