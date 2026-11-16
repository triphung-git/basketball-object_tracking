# Bàn Giao Task07B — Tách Biệt Actor/Body Evidence và Paired Evaluation (2026-11-07)

[Báo cáo chi tiết](../reports/task07b-decoupling-20261107.md).  
Kết quả kiểm thử: **309 unit/regression tests PASS** (bổ sung 4 unit test đặc thù cho decoupling).  
Trạng thái: **Task07 tiếp tục IN_PROGRESS.**

---

## 1. Vị Trí Lưu Trữ Dữ Liệu và Artifacts

Thư mục kết quả độc lập: `codebase/outputs/task07b-decoupling-20261107/`

- `manifest.json`: Bảng băm SHA256 và kích thước của toàn bộ 54 tệp tin trong output.
- `candidate-tracking/`: Kết quả player tracking với candidate `--team-crop-region jersey --reset-on-team-conflict`.
- `candidate-ball/`: Kết quả ball possession tracking gồm `ball_tracks.jsonl`, `ball_control.jsonl`, `debug.mp4` (11.36 MB), và `timeline.png` (73.28 KB).
- `candidate-evaluation/`: Báo cáo đánh giá `evaluation.json` đối chiếu với Ground Truth reviewed v2.
- `candidate-trace/`: Tệp chẩn đoán truy nguyên lỗi 7 tầng `trace.json` phân tách từng khoảng kiểm soát và 5 đầu mút đường chuyền.
- `baseline-tracking/`, `baseline-ball/`, `baseline-evaluation/`, `baseline-trace/`: Cặp chạy đối chứng paired baseline (legacy defaults).
- `fullguard-tracking/`, `fullguard-ball/`, `fullguard-evaluation/`: Cặp chạy kiểm chứng Full Guard có decoupling, chứng minh loại bỏ hoàn toàn hiện tượng tụt giảm ball recall (đạt 36/72 = 50.00%).

---

## 2. Thay Đổi Mã Nguồn Đã Thực Hiện

1. **`codebase/src/basketball_scoreboard/ball_pipeline.py` (dòng 128-130):**
   - Thay đổi: Tách điều kiện lọc `human_boxes` từ `p.get('role') == 'player'` sang:
     ```python
     if p.get('sample_type') == 'observed' and p.get('role') != 'non_player':
         human_boxes.append(p['box'])
     ```
   - Ý nghĩa: Các track cơ thể người trên sân quan sát được (`observed`) có vai trò chưa xác định (`role == 'unknown'`) hoặc đang chờ OCR vẫn cung cấp đầy đủ ngữ cảnh không gian (human body context) cho ball tracker. Điều này ngăn chặn việc loại bỏ bóng hợp lệ do thiếu context actor, đồng thời không gán nhãn tùy tiện thành `player` (giữ vững role validity và causal timing).
2. **`codebase/tests/test_task07_actor_decoupling_and_passes.py`:**
   - Bổ sung bộ 4 bài test unit kiểm thử nghiêm ngặt:
     1. `test_ball_pipeline_actor_selection_rule`: Kiểm tra chỉ nhận on-court observed tracks (`role != 'non_player'`), loại trừ non-player và predicted tracks.
     2. `test_unknown_role_actor_provides_valid_ball_body_context`: Kiểm tra actor role unknown vẫn cung cấp context mà không làm drop bóng.
     3. `test_provenance_and_causal_timing_preserved`: Kiểm tra không làm đột biến ngữ nghĩa vai trò.
     4. `test_decoupling_prevents_guard_ball_recall_regression`: Mô phỏng tình huống full guard và xác nhận không còn bị sụt giảm ball recall.
3. **`codebase/scripts/run_task07b_decoupling_evaluation.py`:**
   - Kịch bản tự động hóa 9 bước chạy paired replay, đánh giá và truy nguyên lỗi, có truyền đúng cấu hình `--config configs/ball-possession-vietnam-tonga-spatial.json`.

---

## 3. Tổng Kết Số Liệu Paired Replay

- **Ball Observed Recall:** Baseline: 36/72 (50.00%) | Candidate: 36/72 (50.00%) | Full Guard: 36/72 (50.00% - đã loại bỏ regression 33/72).
- **Strict Controller Accuracy:** 0.0% (cả 3 phương án). Giải thích: Do thiếu số áo OCR trên các track đang kiểm soát bóng nên `player_id` là `None`.
- **Confirmed Team Error Time:** Baseline: 0.633s $\rightarrow$ Candidate: 0.067s (giảm **89.5%**).
- **Pass Precision / Recall:** 0 TP, 0 FP, 5 FN (Precision N/A, Recall 0.0%). Giải thích: Detector miss bóng tại các điểm release/receive và thiếu OCR identity.
- **Integrity Checks:** Toàn bộ đạt (0 prediction-only confirmed control, 0 pass crossing cut, PTS monotonic $\le 2\mu\text{s}$).

---

## 4. Rào Cản Hiện Tại (Blockers) và Đề Xuất Tiếp Theo

1. **Rào cản lớn nhất là Raw Ball Detector:**
   - Detector bỏ sót bóng ở 31/72 frame GT (43.1%), làm đứt gãy 40.3% thời lượng kiểm soát bóng và hầu hết các điểm release/receive của các đường chuyền.
   - Không thể vượt qua rào cản này bằng cách hạ ngưỡng confidence hoặc dùng bóng predicted thay cho observed.
2. **Kế hoạch huấn luyện tinh chỉnh đã sẵn sàng (đang chờ phê duyệt):**
   - 40 frame GT verified v2 + 319 frame candidate draft.
   - Chia tập theo nhóm nguồn (temporal segment partitioning) tránh rò rỉ dữ liệu.
   - Mô hình YOLOv8n/s, xuất ONNX CPU, chi phí $0.00 USD.
3. **Đề xuất cho bước tiếp theo:**
   - Trình phê duyệt kế hoạch fine-tuning detector theo quy trình.
   - Tiếp tục giữ nguyên nhãn đã review, locked splits và các artifact gốc.
   - Duy trì Task07 ở trạng thái **IN_PROGRESS**.

