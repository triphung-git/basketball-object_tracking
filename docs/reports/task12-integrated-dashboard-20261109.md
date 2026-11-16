# Task 12: Integrated Local Dashboard Report

> **2026-11-10 — Chưa nghiệm thu:** [Acceptance audit](demo-completion-acceptance-20261110.md) có browser evidence 10 pass / 8 fail; heatmap minh họa và missing/unknown run state còn lỗi. Báo cáo dưới đây là lịch sử implementation.

**Date:** 2026-11-09  
**Module:** `codebase/src/basketball_scoreboard/dashboard.py`, `codebase/scripts/run_dashboard.py`  
**Test Suite:** `codebase/tests/test_task12_dashboard.py` (4/4 passed)  
**Status:** Implemented, Integrated & Verified  

---

## 1. Executive Summary

Task 12 provides an offline-first, browser-accessible local dashboard that integrates all upstream pipeline streams (video playback, synchronized PTS timeline, court shot heatmap, live box score, and event ledger).

It relies exclusively on Python standard library HTTP capabilities (`http.server`) and vanilla HTML5/SVG/JavaScript, requiring zero third-party web frameworks (FastAPI/Flask) or internet connection to function.

---

## 2. Key Capabilities & Endpoints

### A. Dashboard Features
- **Video & PTS Scrubbing:** HTML5 video player synchronized with sub-second timestamps and interactive seeking.
- **Color-Coded Event Timeline:** Visual markers for Shots (green), Rebounds (orange), Assists (purple), and Turnovers (red). Clicking any marker automatically seeks video playback to 1.0s before the event.
- **FIBA 3x3 Court Heatmap:** 2D SVG court with regulation markings (perimeter, key, free-throw circle, 2-point arc, and rim). Interactive shot locations colored by scoring team.
- **Live Box Score Table:** Displays conservation-law totals:
  $$\text{Offset} + \text{Observed} = \text{Total Score}$$
  along with detailed per-player stats and team-unassigned rows.
- **Export Actions:** Download buttons for `events_auto.jsonl` and `boxscore_auto.csv`.

### B. HTTP Server API Contract
| Endpoint | Method | Format | Description |
| :--- | :---: | :---: | :--- |
| `/` | GET | `text/html` | Complete single-page dashboard application |
| `/api/status` | GET | `application/json` | Server status, video file existence, total active event count |
| `/api/events` | GET | `application/json` | Active confirmed and unresolved events from `EventLedger` |
| `/api/boxscore` | GET | `application/json` | Compiled TeamBoxScores (Vietnam & Tonga) with player lines |
| `/api/export/events` | GET | `application/x-jsonlines` | Direct download of `events_auto.jsonl` |
| `/api/export/boxscore` | GET | `text/csv` | Direct download of `boxscore_auto.csv` |
| `/api/video` | GET | `video/mp4` | Video stream supporting byte-range HTTP 206 Partial Content |

---

## 3. Verification

- Tested via `codebase/tests/test_task12_dashboard.py`:
  - Ephemeral port server startup.
  - HTML structure verification.
  - JSON API schema validation.
  - CSV and JSONL file export streaming.
  - Byte-range video chunk delivery (HTTP 206).

