# Báo cáo kỹ thuật: Khắc phục và kiểm chứng tính đúng đắn của Unified Event Ledger & Box Score Engine (Task 11)

**Ngày thực hiện:** 2026-11-11  
**Tác giả:** Senior Python Engineer  
**Trạng thái phần việc:** **Core Ledger/BoxScore IMPLEMENTED, EXECUTED & VERIFIED (21/21 Acceptance Probes PASS, 33/33 Task 11 Suite PASS, 393/393 Full Codebase PASS)**  
**Trạng thái toàn bộ Task 11 / Demo MVP:** **IN_PROGRESS** (Chưa nghiệm thu toàn bộ MVP: recognition quality PRA, shot continuity và full video pipeline thuộc các gate Task 07–10, 13–15).  
**Thư mục bằng chứng:** [`codebase/outputs/task11-ledger-correctness-20261111`](../../codebase/outputs/task11-ledger-correctness-20261111)

---

## 1. Tóm tắt điều hành (Executive Summary)

Đợt triển khai này giải quyết triệt để các khiếm khuyết cốt lõi thuộc nhóm **P1-E** và **P1-F** được chỉ ra trong [Báo cáo nghiệm thu 2026-11-10](demo-completion-acceptance-20261110.md):
1. **Lọc trạng thái nghiêm ngặt (Eligibility Contract):** Box score chỉ tổng hợp các sự kiện `AUTO_CONFIRMED`, không void, payload hợp lệ và dependencies thỏa mãn. Các sự kiện `CANDIDATE`, `PROVISIONAL`, `UNRESOLVED`, `VOID` không còn làm tăng PTS, REB, AST, TO.
2. **Định danh vật lý ổn định & chống đếm lặp (Refinement Idempotency):** Tách biệt định danh vật lý (loại sự kiện, namespace, tọa độ thời gian/frame) khỏi payload thay đổi (player, team, point value). Việc refine từ team-only sang cầu thủ cụ thể và sau đó nạp lại sự kiện dưới ID mới không còn làm nhân đôi điểm số (giữ nguyên 2 điểm, không tăng thành 4).
3. **Quản lý ràng buộc nhân quả (Causal Dependency & Revalidation):** Assist chỉ được ghi nhận khi shot cha còn hiệu lực, cùng đội và khác cầu thủ ghi điểm. Khi shot cha bị đổi sang đội khác, chuyển sang `UNRESOLVED`, hoặc bị `VOID`, assist lập tức mất eligibility. Trẻ đến sau sự kiện cha đã void hoặc đến trước khi cha xuất hiện đều không tạo ra số liệu sai lệch.
4. **Tính bất biến (Immutability & Defensive Copying):** Áp dụng sao chép sâu phòng thủ (`copy.deepcopy`) tại cổng nạp `record_event` và các hàm truy vấn (`get_event`, `get_active_events`). Việc caller sửa đổi trực tiếp object bên ngoài không còn làm thay đổi trạng thái sổ cái.
5. **Sổ cái giao dịch append-only & Checkpoint/Replay:** Triển khai checkpoint nguyên tử kèm checksum SHA-256, ghi nhật ký giao dịch append-only đầy đủ (`events_raw.jsonl`), và hỗ trợ tái lập trạng thái 100% nhất quán qua full log replay hoặc checkpoint + tail.

---

## 2. Phân tích nguyên nhân gốc rễ (Root Cause Analysis)

Đối chiếu với các failure trong [báo cáo 2026-11-10](demo-completion-acceptance-20261110.md) và kết quả tái hiện ban đầu (`baseline_failures.log`):

| Khiếm khuyết | Mã kiểm thử | Nguyên nhân kỹ thuật trong mã nguồn cũ |
|---|---|---|
| **P1-E: Cộng dồn sự kiện chưa confirmed** | `test_only_confirmed_events_contribute` (16 cases) | `BoxScoreEngine.compile()` chỉ kiểm tra `not ev.is_void`, không lọc theo `status == EventStatus.AUTO_CONFIRMED`. Ngoài ra, nếu `status=VOID` nhưng cờ `is_void=False`, sự kiện vẫn bị cộng điểm. |
| **P1-F: Đếm trùng sau refinement** | `test_refined_event_cannot_be_reingested_under_new_id` | `EventLedger` chỉ tính fingerprint một lần tại thời điểm nạp ban đầu (với `player_id="noplayer"`). Khi gọi `revise_event(new_player_id="a1")`, fingerprint mới không được cập nhật vào chỉ mục, và sổ cái không có khái niệm `physical_event_key`. Khi sự kiện được nạp lại dưới ID mới (`s_reloaded`), nó vượt qua kiểm tra và được tính lần 2 làm điểm tăng từ 2 lên 4. |
| **P1-F: Assist mồ côi / không tương thích** | `test_team_revision_invalidates_incompatible_assist`, `test_status_revision_invalidates_assist`, `test_late_child_of_void_parent_is_not_counted` | `BoxScoreEngine` cộng assist mà không đối soát tính tương thích thời gian thực với sự kiện cha trong sổ cái. Khi shot cha đổi đội hoặc đổi sang `UNRESOLVED`, assist vẫn giữ nguyên. Khi shot cha bị void trước, assist đến muộn vẫn được cộng. |
| **P1-F: Caller mutation làm sai lệch sổ cái** | `test_caller_cannot_mutate_recorded_raw_event` | `EventLedger.record_event()` lưu trực tiếp tham chiếu của object do caller truyền vào (`self._events[id] = event`). Khi caller thay đổi `original.point_value = 1`, giá trị trong sổ cái bị thay đổi âm thầm ngoài luồng giao dịch. |
| **P1-F: Thiếu raw transaction audit & checkpoint replay** | `export_jsonl` view vs transaction log | Phiên bản cũ chỉ xuất view sự kiện hiện hành (`events_auto.jsonl`), không có raw mutation log append-only, không có lưu checkpoint nguyên tử có checksum và không có cơ chế replay transaction log. |

---

## 3. Chi tiết các thay đổi trong Production Code

### 3.1. `codebase/src/basketball_scoreboard/events.py`
- **Validation chặt chẽ và đồng bộ trạng thái:**
  - `point_value` được kiểm tra nghiêm ngặt: từ chối kiểu `bool` (`isinstance(val, bool)` bị từ chối), chỉ chấp nhận `int` trong `{1, 2, 3}` hoặc `None`.
  - Đồng bộ hai chiều giữa `status` và `is_void`: nếu `status == EventStatus.VOID` thì `is_void = True`; nếu `is_void is True` thì `status = EventStatus.VOID`.
  - Xác thực thời gian hữu hạn (`math.isfinite`) cho `source_time_s` và `confirmation_time_s`.
- **Khóa định danh vật lý (Physical Event Identity) & Aliases:**
  - Hàm `_compute_physical_keys()` kết hợp `source_namespace`, `event_type`, tọa độ thời gian (làm tròn 0.02s / frame index) và team context.
  - Khi một sự kiện được nạp, sổ cái lập chỉ mục cả ID, alias, fingerprint và physical keys. Khi sự kiện được sửa đổi (refinement), chỉ mục mới được thêm vào mà vẫn giữ các liên kết cũ. Sự kiện nạp lại dưới ID mới sẽ bị phát hiện là alias trùng lặp và từ chối (`return False`).
- **Sentinel `_UNSET` trong `revise_event`:**
  - Phân biệt rõ giữa việc "không thay đổi trường này" (`_UNSET`) và "xóa trường này về None" (`None`), cho phép đưa `player_id` từ đã biết về chưa xác định (`unresolved`).
  - Hỗ trợ kiểm tra `expected_revision` để phát hiện xung đột ghi đè đồng thời (optimistic locking).
  - Tự động nhận diện `no-op` khi các giá trị mới không thay đổi so với hiện tại.
- **Bất biến và phòng thủ đối tượng (Defensive Copying):**
  - `record_event` tạo bản sao sâu `copy.deepcopy(event)`.
  - `get_event`, `get_active_events`, `get_all_events` trả về bản sao sâu, ngăn chặn hoàn toàn việc sửa đổi trạng thái ngoài giao dịch.
- **Hợp đồng kiểm tra điều kiện (Eligibility Contract):**
  - Hàm `is_event_eligible(ev)` tập trung: kiểm tra `not ev.is_void`, `status == EventStatus.AUTO_CONFIRMED`, payload hợp lệ và đối soát sự kiện cha (đối với `ASSIST`: cha phải tồn tại, confirmed, non-void, cùng đội và khác cầu thủ).
- **Audit Mutation & Checkpoint / Replay:**
  - `AuditMutation` ghi lại mọi hành động (`created`, `revised`, `voided`, `cascaded_void`, `dependency_invalidated`, `duplicate_rejected`, `no_op`) kèm sequence, revision, previous state, new state và provenance (`automatic`, `adjudication`, `human_correction`).
  - `save_checkpoint(path)` ghi file tạm `.tmp` có checksum SHA-256 và thay thế nguyên tử (`os.replace`).
  - `load_checkpoint(path)` xác thực toàn vẹn checksum và phục hồi toàn bộ chỉ mục.
  - `replay_transactions(log_path)` và `from_raw_log(log_path)` tái tạo chính xác trạng thái từ nhật ký giao dịch.

### 3.2. `codebase/src/basketball_scoreboard/boxscore.py`
- **Lọc Eligibility khi tổng hợp:**
  - `compile()` chỉ tổng hợp các sự kiện vượt qua `ledger.is_event_eligible(ev)`.
  - Các sự kiện không đủ điều kiện (CANDIDATE, PROVISIONAL, UNRESOLVED, VOID) không làm tăng `observed_points`, `rebounds_total`, `assists`, `turnovers`.
  - Riêng các shot có `point_value is None` hoặc `status == EventStatus.UNRESOLVED` được ghi nhận vào biến đếm `unresolved_shots` để phục vụ audit/coverage, điểm số thực tế giữ 0.
- **Bảo toàn thống kê (Conservation Invariants):**
  - $\sum \text{player.points} + \text{team\_only\_points} \equiv \text{observed\_points}$.
  - $\text{total\_score} \equiv \text{initial\_score\_offset} + \text{observed\_points}$.
  - $\sum \text{player.rebounds} + \text{rebounds\_team} \equiv \text{rebounds\_total}$.
  - $\text{rebounds\_offensive} + \text{rebounds\_defensive} + \text{rebounds\_unclassified} \equiv \text{rebounds\_total}$.
  - $\sum \text{player.assists} + \text{assists\_team\_only} \equiv \text{assists\_total}$.
  - $\sum \text{player.turnovers} + \text{turnovers\_team\_only} \equiv \text{turnovers\_total}$.
- **Xuất dữ liệu đối soát:**
  - Bổ sung các hàng `TEAM_UNASSIGNED` trong CSV khi có điểm/rebound/assist chưa gán cầu thủ cụ thể, bảo đảm không gán tùy tiện sang cầu thủ khác trong danh sách.

### 3.3. Adapters & Runners
- **`point_event_to_ledger_record`:**
  - Lưu trữ thời gian sự kiện gốc `source_time_s` từ shot candidate thật; lưu thời gian xác nhận `confirmation_time_s` vào trường riêng và metadata evidence mà không làm mất thời gian gốc.
- **`codebase/scripts/run_demo.py`:**
  - Cập nhật luồng xuất deliverables: xuất đầy đủ cả `events_auto.jsonl` (active view), `events_raw.jsonl` (raw append-only transactions), `audit_trail.jsonl`, `checkpoint.json`, `boxscore_auto.csv` và `summary.json`.

---

## 4. Kết quả kiểm thử và nghiệm thu kỹ thuật

### 4.1. Bảng đối chiếu trước và sau sửa lỗi

| Bộ kiểm tra | Trước sửa (Baseline) | Sau sửa (Post-fix) | Kết luận |
|---|---|---|---|
| **Independent Acceptance Probes (Task 11 subset)** | **21 FAILED / 21 run** (`baseline_failures.log`) | **21 PASSED / 21 run** (`acceptance_probes_post_fix.log`) | Khắc phục hoàn toàn 5/5 nhóm lỗi P1-E & P1-F |
| **Comprehensive Task 11 Test Suite** | 7 passed (bản cũ thiếu case) | **33 PASSED / 33 run** (`test_task11_post_fix.log`) | Bao phủ đầy đủ 8 nhóm kiểm thử bắt buộc |
| **Toàn bộ Codebase Tests (`codebase/tests`)** | 367 passed | **393 PASSED, 61 subtests PASS** (`full_tests_post_fix.log`) | 0 regressions, toàn bộ các module khác hoạt động bình thường |
| **Chạy Pipeline thực tế trên video demo** | N/A (chưa xuất raw log/chk) | **EXIT 0 (1.10s), 6 deliverables hoàn tất** | 1 unresolved shot được ghi nhận, điểm 0-0 bảo toàn |

### 4.2. Bằng chứng kiểm tra tính bất biến (Mathematical Invariants)

Từ kết quả chạy thực nghiệm [`invariant_verification_report.json`](../../codebase/outputs/task11-ledger-correctness-20261111/invariant_verification_report.json):
```json
{
  "actual_checkpoint_reload_identity": true,
  "refinement_preserves_score_conservation": true,
  "reingest_under_new_id_rejected": true,
  "void_cascade_verified": true,
  "full_log_replay_identity": true
}
```

### 4.3. Hash SHA-256 các tệp nguồn trước và sau

| Tệp nguồn | SHA-256 Trước sửa (`source_snapshot_before.json`) | SHA-256 Sau sửa (`source_snapshot_after.json`) |
|---|---|---|
| `events.py` | `d124ba219a16f6b15e21e427210e7ee9cf5fc01cf4a0b6567ce293c6ae1eec30` | `4fa89f815049cf19a3d463d12d46e001e44f83693e5a59654efbe6ce457e5b0d` |
| `boxscore.py` | `c0fc572c6cf3977efccca3a67d0cf9b7161b96a17b077a0c0e7b7e28b2a5df61` | `75cb082d244fbe29f27c81aa99c8f6ea0f367e94627d35caae593c6c198a213a` |
| `run_demo.py` | `08aa80df7c6792694dbfb1c6be26f58f5c35b8005b4b10fa2e8966cfd4f26b4d` | `6267f56d09c629fb84f7fa3f6db0d26857cb3eeb6d2b4f9d2d0b27b3e10fa653` |
| `test_task11_ledger_and_boxscore.py` | `771fe0e3fca4cfb489ef2db529759d99787ffea8dd228966a3ca4ba7130be766` | `bbcf48039f37c35d9472eec9a78e792f3bce553eeb1168444a159ea4be3747eb` |

---

## 5. Artifacts bàn giao trong đợt này

Thư mục: `codebase/outputs/task11-ledger-correctness-20261111/`
1. `source_snapshot_before.json` & `source_snapshot_after.json`: Lưu vết băm SHA-256 của các tệp nguồn.
2. `commands.json`: Danh mục các lệnh đã chạy kèm mã thoát và tóm tắt kết quả.
3. `baseline_failures.log` & `baseline_requirements.xml`: Nhật ký tái hiện 21 ca thất bại ban đầu.
4. `acceptance_probes_post_fix.log` & `acceptance_probes_post_fix.xml`: Kết quả 21/21 ca nghiệm thu độc lập đạt yêu cầu.
5. `test_task11_post_fix.log` & `test_task11_post_fix.xml`: Kết quả 33/33 ca kiểm thử toàn diện Task 11 đạt yêu cầu.
6. `full_tests_post_fix.log` & `full_tests_post_fix.xml`: Kết quả 393 ca kiểm thử toàn codebase không phát sinh lỗi hồi quy.
7. `actual_*`: Các tệp xuất từ quá trình nạp dữ liệu thật (`actual_events_raw.jsonl`, `actual_events_active.jsonl`, `actual_audit_trail.jsonl`, `actual_checkpoint.json`, `actual_boxscore_auto.csv`, `actual_reconciliation_summary.json`).
8. `synthetic_*`: Các tệp xuất từ kịch bản chẩn đoán giả lập có gắn nhãn `provenance="synthetic_diagnostic"`.
9. `demo_run/`: Thư mục chạy demo thực tế trên `vietnam-tonga.mp4` với runner production.

---

## 6. Giới hạn và các vấn đề ngoài phạm vi Task 11

Theo đúng chỉ đạo của đề bài và báo cáo nghiệm thu 2026-11-10:
- **Không tự ý nâng Task 11 lên DONE hoặc tuyên bố nghiệm thu toàn bộ MVP:** Việc hoàn thành core ledger và box score correctness là điều kiện cần, nhưng chưa phải là điều kiện đủ để nghiệm thu toàn bộ demo MVP.
- **Các gate độc lập chưa nghiệm thu tiếp tục giữ nguyên:**
  1. *Task 07 / Fine-tune Detector:* Candidate model loss smoke test và epoch evaluation chưa hoàn tất.
  2. *Task 08 / Shot Recognition & Production Evaluator:* Shot FSM crossing cần observed continuity; evaluator production cần được chuẩn hóa one-to-one matching theo frozen protocol.
  3. *Task 09 & Task 10 / Rebounds & Assists Engine:* Cần kiểm soát sustained control và quy tắc FT applicability trên video liên tục, chưa kết nối vào full continuous video pipeline.
  4. *Task 12 / Dashboard:* Heatmap cần chiếu tọa độ sân thực thay cho marker minh họa.
  5. *Task 13 / Evaluation PRA:* Formal strict PRA metrics hiện là N/A do đang chờ hoàn thiện continuous video pipeline và GT annotations đầy đủ.

---

## 7. Kết luận và bước tiếp theo

Phần việc **Task 11 Core: Ledger, Box Score Correctness, Idempotency & Audit** đã hoàn thành xuất sắc, vượt qua toàn bộ 21 probes của đợt nghiệm thu độc lập và 33 regression tests mới mà không gây bất kỳ tác dụng phụ nào lên codebase.

**Bước tiếp theo khuyến nghị:**
1. Tiến hành sửa Task 08 (P1-B: Shot continuity và P1-C: Production Evaluator).
2. Xử lý training readiness của detector (P1-K).
3. Hoàn thiện các guards của Rebound (Task 09) và Assist (Task 10) trước khi tích hợp vào continuous video runner (Task 15).

