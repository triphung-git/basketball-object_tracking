# Báo cáo kỹ thuật: Khắc phục và kiểm chứng tính đúng đắn của Temporal Shot Engine, Rim Crossing Continuity & Production Evaluator (Task 08)

**Ngày thực hiện:** 2026-11-12  
**Tác giả:** Senior Computer Vision & Systems Engineer  
**Trạng thái phần việc:** **Core Shot Engine & Production Evaluator IMPLEMENTED, EXECUTED & VERIFIED (4/4 Acceptance Probes PASS, 14/14 Task 08 Suite PASS, 11/11 Evaluator Suite PASS, 404/404 Full Codebase PASS)**  
**Trạng thái toàn bộ Task 08 / Demo MVP:** **IN_PROGRESS** (Chưa nghiệm thu toàn bộ MVP: recognition quality PRA P>=95%/R>=90% yêu cầu model fine-tune/retraining; pipeline video continuous MP4 và rebound/assist contracts thuộc các gate Task 09–10, 13–15).  
**Thư mục bằng chứng:** [`codebase/outputs/task08-shot-correctness-20261112`](../../codebase/outputs/task08-shot-correctness-20261112)

---

## 1. Tóm tắt điều hành (Executive Summary)

Đợt triển khai này giải quyết triệt để các khiếm khuyết cốt lõi thuộc nhóm **P1-B**, **P1-C** và **P1-D** được chỉ ra trong [Báo cáo nghiệm thu 2026-11-10](demo-completion-acceptance-20261110.md):

1. **Ràng buộc tính liên tục vật lý và mẫu quan sát thực (`P1-B`):**
   - Phân biệt triệt để giữa mẫu bóng quan sát thực (`observed`) và mẫu ước lượng nội suy/ngoại suy (`predicted`, `missing`, `stale`).
   - Kiểm tra khoảng trống quan sát (`last_observed_ball_time_s`): nếu khoảng trống giữa hai quan sát thực vượt quá ngưỡng cho phép (`max_flight_gap_seconds = 0.35s`), FSM lập tức bị hủy (`abort`) về trạng thái `idle`, kể cả khi tracker vẫn liên tục phát ra tâm bóng ước lượng.
   - Ràng buộc mặt cắt rổ (`_check_rim_aperture_crossing`): yêu cầu tối thiểu 2 mẫu quan sát thực nằm trong aperture trong suốt thời gian bay tính từ thời điểm thả bóng (`source_time_s >= release_time_s`), xác thực điểm vào ở nửa trên và điểm ra ở nửa dưới rổ, vận tốc rơi thẳng đứng xuống dưới $v_y > 30\text{ px/s}$, khoảng trống giữa các quan sát trong quá trình đi qua rổ $\le 0.35\text{s}$, độ tươi của rổ $\le 1.5\text{s}$, và bảo đảm toàn bộ quỹ đạo thuộc cùng một track bóng duy nhất.
   - Loại bỏ hoàn toàn giá trị gán cứng `net_cue_passed = True`; thay thế bằng đo lường độ giảm tốc thực của bóng dưới đáy vành rổ (`measured_pass`, `measured_no_decel`, hoặc `unavailable_insufficient_samples`).

2. **Xây dựng Production Evaluator chuẩn hóa (`P1-C`):**
   - Xây dựng module dùng chung [`codebase/src/basketball_scoreboard/shot_evaluator.py`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/src/basketball_scoreboard/shot_evaluator.py) dùng cho cả runner, CLI, và test suite.
   - Áp dụng thuật toán **Ghép cặp hai phía cực đại có chi phí cực tiểu (Maximum Cardinality Min-Cost Bipartite Matching)** giải bằng đường tăng luồng ngắn nhất (SPFA/MCMF) với cơ chế giải quyết xung đột tất định (ưu tiên tổng độ lệch thời gian release + basket nhỏ nhất, sau đó đến ID sự kiện), loại bỏ hoàn toàn bẫy thuật toán tham lam (greedy trap).
   - Tách bạch rõ ràng 5 góc nhìn đánh giá: Phát hiện sự kiện (Event Detection), Gán đội (Team Attribution), Gán cầu thủ nghiêm ngặt (Strict Player), Giá trị điểm (Point Value), và Đầy đủ thuộc tính (Strict All-Correct).
   - Xử lý toán học nghiêm ngặt cho các trường hợp mẫu số bằng 0 (trả về `None` kèm lý do thay vì giá trị mặc định gây hiểu lầm).

3. **Chân thực hóa kết quả Negative Cohort (`P1-D`):**
   - Đánh giá 30 tình huống phủ định thực tế trên 4 nhóm: ném trượt không chạm rổ (10), ném trượt bật vành/bảng (8), mất bóng/không ném (6), và phân đoạn quay chậm (6).
   - Phân định rõ ràng: `manifest_status = "draft_unreviewed"` dẫn đến `official_specificity = None` (chờ nghiệm thu độc lập có chữ ký con người); tỷ lệ loại trừ chẩn đoán sơ bộ (draft diagnostic rejection rate) đạt $100.0\%$ ($30/30$ tình huống bị từ chối thành công, 0 False Positive).

4. **Tách biệt triệt để Inference và Ground Truth:**
   - Xóa bỏ toàn bộ các cờ gán cứng dựa vào window ID trong runner (`is_play_006 = (wid == "play_006")` và `is_ft = (wid in {"play_006", "play_015"})`).
   - Bộ máy FSM và Points Engine chạy thuần túy trên luồng quan sát thô mà không có bất kỳ thông tin nào về Ground Truth. Nhờ logic mặt cắt rổ mới, `play_006` tự động được phân loại là không hợp lệ mà không cần cờ can thiệp.
   - Dự đoán được xuất ra đĩa (`shots_auto.jsonl`, `points_auto.jsonl`, `shot_state_transitions.jsonl`) trước khi nạp GT review metadata để chấm điểm.

5. **Tích hợp Downstream (Event Ledger & Box Score):**
   - Các điểm số được xác nhận từ Candidate C được nạp trực tiếp vào [`EventLedger`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/src/basketball_scoreboard/events.py) và tổng hợp bởi [`BoxScoreEngine`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/src/basketball_scoreboard/boxscore.py).
   - Kiểm chứng tính idempotent (nạp lặp lại không làm tăng số sự kiện) và các định luật bảo toàn điểm số/thống kê đạt $100\%$.

---

## 2. Phân tích nguyên nhân gốc rễ (Root Cause Analysis)

Đối chiếu với các lỗi được ghi nhận trong audit ngày 2026-11-10:

| Khiếm khuyết | Mã kiểm thử Audit Probe | Nguyên nhân kỹ thuật trong mã nguồn cũ |
|---|---|---|
| **P1-B: Tâm bóng nội suy xác nhận quả ném thành công** | `test_predicted_entry_exit_cannot_confirm_made` | `_check_rim_aperture_crossing` trong `shots.py` chấp nhận cả mẫu `predicted` làm điểm vào và điểm ra ở miệng rổ. Bộ gom điểm nội suy tổng hợp quỹ đạo giả và cho phép xác nhận quả ném thành công dù không có pixel bóng thực nào đi qua rổ. |
| **P1-B: Cầu nối thời gian bỏ qua khoảng trống quan sát** | `test_crossing_cannot_bridge_long_observation_gap` | Bộ kiểm tra khoảng cách mẫu chỉ kích hoạt khi thiếu mẫu (`ball_obs is None`). Khi tracker tiếp tục phát ra các mẫu nội suy liên tục (`sample_type="predicted"`), FSM không phát hiện ra việc mất dấu vết bóng thực, cho phép các quan sát cách nhau hàng giây được nối liền nhau. |
| **P1-C: Bẫy thuật toán tham lam trong Evaluator** | `test_production_evaluator_rejects_out_of_tolerance_made` & `test_evaluator_greedy_trap` | Hàm đánh giá cũ trong runner sắp xếp tham lam theo thời gian release/basket gần nhất từng cặp độc lập. Khi một shot dự đoán có thể ghép với 2 GT, thuật toán chọn cục bộ làm mất đi cặp ghép toàn cục tối ưu, hoặc chấp nhận các shot nằm ngoài dung sai $\pm 0.50\text{s}$. |
| **P1-C: Đếm trùng shot bị tính thành 1 TP** | `test_production_evaluator_counts_duplicate_as_fp` | Hàm đánh giá cũ chỉ kiểm tra `len(made_shots) > 0` cho toàn bộ cửa sổ. Khi một cửa sổ có 2 shot dự đoán cùng gắn nhãn made, thuật toán gán cả cửa sổ là đúng và không tính shot dư thừa là False Positive. |
| **P1-D: Tuyên bố Specificity 100% trên tập nháp** | `negative_manifest.json` status vs report | Báo cáo cũ tuyên bố độ đặc hiệu chính thức đạt 100% trên 30 tình huống âm tính trong khi tệp manifest có trạng thái `draft_unreviewed` và chưa có biên bản nghiệm thu độc lập có chữ ký chuyên gia. |
| **Leakage: Window ID rò rỉ vào Runtime** | `run_task08_temporal_shot_engine.py` | Runner cũ truyền `is_play_006 = (wid == "play_006")` vào `camera_layout_invalid` và `is_ft = (wid in {"play_006", "play_015"})` vào `is_free_throw`. Đây là hình thức rò rỉ nhãn Ground Truth trực tiếp vào mã thực thi. |

---

## 3. Chi tiết các thay đổi trong Production Code

### 3.1. `codebase/src/basketball_scoreboard/shots.py`
- **Quản lý khoảng trống quan sát thực:**
  - Bổ sung trường `self.last_observed_ball_time_s: Optional[float] = None` và `self.last_observed_ball_frame_idx: Optional[int] = None` vào FSM.
  - Trong phương thức `step()`: nếu bóng có `sample_type == "observed"`, cập nhật thời gian quan sát cuối.
  - Nếu FSM đang ở các pha `RELEASE`, `FLIGHT`, hoặc `APERTURE_CROSSING`, FSM tính khoảng cách thời gian từ quan sát thực gần nhất: `flight_gap = source_time_s - self.last_observed_ball_time_s`. Nếu `flight_gap > self.config.max_flight_gap_seconds` (mặc định $0.35\text{s}$), FSM lập tức kích hoạt `_abort_shot(reason="ball_flight_gap_exceeded")` và chuyển về `ShotPhase.IDLE`. Cơ chế này ngăn chặn tuyệt đối việc tracker tự sinh các tâm bóng nội suy để kéo dài quỹ đạo bay vô căn cứ.
- **Tái thiết kế logic xuyên tâm vành rổ (`_check_rim_aperture_crossing`):**
  - Chỉ lọc các mẫu bóng thỏa mãn cả 3 điều kiện:
    1. `source_time_s >= (self.release_time_s or 0.0)` (chỉ lấy quỹ đạo sau khi bóng đã rời tay).
    2. `b.get("sample_type", "observed") == "observed"` (bắt buộc phải là quan sát thực từ detector/tracker, loại trừ hoàn toàn `predicted`, `interpolated`, `stale`).
    3. `b.get("confidence", 0.0) >= self.config.min_ball_confidence` (mặc định $0.15$).
  - Yêu cầu tối thiểu $2$ mẫu quan sát thực nằm trong aperture hình học của rổ.
  - Kiểm tra độ tươi của rổ: $t_{\text{crossing}} - t_{\text{rim}} \le 1.5\text{s}$.
  - Xác nhận mẫu vào (`entry_sample`) nằm ở nửa trên vành rổ ($y_{\text{entry}} < y_{\text{rim}}$) và mẫu ra (`exit_sample`) nằm ở hoặc dưới tâm vành rổ ($y_{\text{exit}} \ge y_{\text{rim}}$).
  - Vận tốc thẳng đứng trung bình giữa điểm vào và điểm ra phải hướng xuống dưới rõ rệt: $v_y = \frac{\Delta y}{\Delta t} > 30\text{ px/s}$.
  - Khoảng trống tối đa giữa 2 mẫu quan sát liên tiếp trong suốt quá trình đi qua rổ không được vượt quá $0.35\text{s}$.
  - Đảm bảo tất cả các mẫu bóng trong quá trình đi qua rổ thuộc cùng một `ball_track_id` duy nhất.
- **Đo lường độ giảm tốc lưới rổ (`net_cue`):**
  - Loại bỏ hoàn toàn giá trị gán cứng `net_cue_passed = True`.
  - Triển khai hàm `_measure_net_deceleration_cue()`: thu thập các mẫu bóng quan sát thực sau khi đi qua mặt phẳng rổ, đo lường tỷ lệ giảm tốc $r_{\text{decel}} = \frac{v_{\text{approach}}}{v_{\text{net}}}$.
  - Trả về mã trạng thái tường minh:
    * `"disabled"`: khi cấu hình tắt net cue.
    * `"measured_pass"`: khi phát hiện giảm tốc rõ rệt ($r_{\text{decel}} \ge 1.15$).
    * `"measured_no_decel"`: khi bóng đi qua mà không giảm tốc.
    * `"unavailable_insufficient_samples"`: khi không đủ mẫu bóng dưới rổ để đo lường.
- **Phòng thủ thứ tự thời gian:**
  - Kiểm tra frame trùng lặp hoặc thời gian quay lui ($t \le t_{\text{prev}}$): nếu phát hiện, FSM bỏ qua an toàn mà không làm hỏng chuỗi trạng thái.

### 3.2. `codebase/src/basketball_scoreboard/shot_evaluator.py`
- **Cấu hình giao thức chuẩn hóa (`EvaluationProtocolConfig`):**
  - Dung sai thời gian bóng rời tay (`release_tolerance_s = 0.50s`).
  - Dung sai thời gian bóng vào rổ (`basket_tolerance_s = 0.50s`).
  - Giao thức giải quyết xung đột: `"maximum_cardinality_min_cost"`.
- **Cấu trúc dữ liệu quy chuẩn:**
  - `GroundTruthPlay`: Chuẩn hóa thời gian `release_s`, `basket_s`, `shooter_id`, `team_id`, `point_value` từ metadata review (`events-reviewed.json`).
  - `EventMatch`: Biểu diễn cặp ghép 1-1 giữa dự đoán và thực tế, kèm toàn bộ chênh lệch thời gian và cờ kiểm tra từng thuộc tính.
- **Thuật toán ghép cặp cực đại min-cost:**
  - Hàm `solve_max_cardinality_min_cost_matching()`:
    * Xây dựng đồ thị luồng hai phía (bipartite flow network) giữa tập dự đoán made shots và tập GT scoring plays.
    * Cạnh $(i, j)$ tồn tại nếu và chỉ nếu $|\Delta t_{\text{release}}| \le 0.50\text{s}$ VÀ $|\Delta t_{\text{basket}}| \le 0.50\text{s}$.
    * Trọng số chi phí cạnh $c_{ij} = |\Delta t_{\text{release}}| + |\Delta t_{\text{basket}}|$.
    * Tìm luồng cực đại có chi phí cực tiểu qua thuật toán Successive Shortest Path (SPFA).
    * Phá vỡ thế hòa (tie-breaking) tất định theo chi phí và ID sự kiện.
- **Hạch toán đa góc nhìn (Multi-view Metrics):**
  - **Detection Only:** $\text{TP}_{\text{event}}$, $\text{FP}_{\text{event}}$, $\text{FN}_{\text{event}}$, $\text{Precision}$, $\text{Recall}$, $\text{F1}$.
  - **Team Attribution:** Độ chính xác gán đội trong số các event đã match đúng.
  - **Strict Player:** Độ chính xác nhận diện đúng cầu thủ (AttributionLevel = PLAYER và player_id khớp GT).
  - **Point Value:** Độ chính xác giá trị điểm (1PT, 2PT, FT).
  - **Strict All-Correct:** Tỷ lệ shot thỏa mãn đồng thời cả Event, Team, Player và Point Value.
- **Phương thức đánh giá tập âm tính (`evaluate_negative_cohort`):**
  - Phân định rõ giữa `official_specificity` (chỉ trả về giá trị số khi `manifest_status == "reviewed"`) và `draft_specificity` (ghi nhận kết quả chẩn đoán sơ bộ khi status là `draft_unreviewed`).

### 3.3. `codebase/scripts/run_task08_temporal_shot_engine.py`
- **Xóa bỏ hoàn toàn Ground Truth Leakage:**
  - `run_engine_on_window` không còn nhận `is_play_006` hay `is_free_throw` từ bên ngoài; FSM và Points Engine chạy thuần túy trên luồng nhận dạng không nhãn.
- **Ghi nhận dự đoán trước khi đánh giá:**
  - Các tệp `shots_auto.jsonl`, `points_auto.jsonl`, `shot_state_transitions.jsonl` được ghi xuống đĩa ở từng thư mục candidate trước khi gọi evaluator.
- **Xuất bảng match chi tiết và review packet:**
  - Sinh tệp `match_table_candidate_c.json` và `match_table_candidate_c.csv` thể hiện chi tiết từng cặp TP, từng shot FP và từng tình huống FN kèm phân loại nguyên nhân lỗi.
  - Sinh gói kiểm duyệt tập âm tính `negative_review_packet/` gồm `negative_manifest.json`, `negative_eval_candidate_c.json` và `.csv`.
- **Tích hợp Downstream:**
  - Nạp các điểm số được xác nhận vào `EventLedger`, kiểm tra tính bảo toàn (conservation) và tính bất biến khi lặp (idempotency), xuất báo cáo box score qua `BoxScoreEngine`.

---

## 4. Bảng so sánh kết quả thực nghiệm Trước và Sau khi sửa

Đối chiếu kết quả chạy thực tế của Candidate C trên 10 cửa sổ ghi điểm dương tính và 30 tình huống âm tính:

| Chỉ số / Tiêu chí | Trước khi sửa (Audit Baseline 2026-11-10) | Sau khi sửa (Current Run 2026-11-12) | Đánh giá & Diễn giải |
|---|---|---|---|
| **Mã nguồn FSM (`shots.py`)** | Cho phép tâm nội suy bridging gap, net cue gán cứng `True` | Bắt buộc mẫu quan sát thực, gap > 0.35s abort FSM, đo lường net cue | **Khắc phục triệt để P1-B** |
| **Evaluator** | Ad-hoc, greedy trap, không bắt lỗi duplicate FP | Chuẩn hóa bipartite matching (SPFA min-cost), đa góc nhìn | **Khắc phục triệt để P1-C** |
| **Leakage trong Runner** | Truyền `is_play_006`, `is_free_throw` theo ID | Loại bỏ 100% tham số GT, inference hoàn toàn độc lập | **Cách ly GT hoàn toàn** |
| **Candidate C - Dự đoán Made** | 2 (`play_003`, `play_021`) | 2 (`play_003`, `play_021`) | Kết quả nhận dạng vật lý nhất quán |
| **True Positives (TP)** | 1 (`play_003`, $\Delta t_{\text{rel}}=0.20\text{s}, \Delta t_{\text{bsk}}=0.03\text{s}$) | 1 (`play_003`, $\Delta t_{\text{rel}}=0.20\text{s}, \Delta t_{\text{bsk}}=0.03\text{s}$) | Match chính xác trong dung sai $\pm 0.50\text{s}$ |
| **False Positives (FP)** | 1 (`play_021`, $\Delta t_{\text{rel}}=1.10\text{s} > 0.50\text{s}$) | 1 (`play_021`, $\Delta t_{\text{rel}}=1.10\text{s} > 0.50\text{s}$) | Phân loại chính xác là FP do lỗi thời gian |
| **False Negatives (FN)** | 9 | 9 | Phân loại lỗi theo bảng taxonomy |
| **Precision (Event)** | 50.0% ($1 / 2$) | 50.0% ($1 / 2$) | Tính toán minh bạch toán học |
| **Recall (Event)** | 10.0% ($1 / 10$) | 10.0% ($1 / 10$) | Giữ nguyên do model YOLO chưa retraining |
| **F1 Score** | 16.67% | 16.67% | Phản ánh đúng năng lực hiện tại của detector |
| **Negative Cohort Rejection** | 30 / 30 bị từ chối | 30 / 30 bị từ chối | Không có False Positive trong 30 ca âm tính |
| **Official Specificity** | 100.0% *(Tuyên bố sai)* | **None (N/A)** | **Khắc phục P1-D: Chân thực hóa theo manifest draft** |
| **Draft Rejection Rate** | Không phân biệt | 100.0% (Chẩn đoán nội bộ) | Tách biệt rành mạch với chỉ số chính thức |
| **Acceptance Probes (P1-B, C)** | **4 FAILED** | **4 PASSED** (0 failed) | 100% lỗi probe của Task 08 được xử lý |
| **Full Codebase Tests** | 393 passed | **404 passed, 0 failed** (+11 tests) | Không gây ra bất kỳ hồi quy nào |

---

## 5. Phân tích phân loại lỗi (Failure Taxonomy Analysis)

Dựa trên bảng match chi tiết [`codebase/outputs/task08-shot-correctness-20261112/match_table_candidate_c.csv`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task08-shot-correctness-20261112/match_table_candidate_c.csv):

### 5.1. True Positive (TP = 1)
- **`play_003` (`shot_play_003_0001`):**
  - Thời gian dự đoán: Release = $165.17\text{s}$, Basket = $165.80\text{s}$.
  - Ground Truth: Release = $164.97\text{s}$, Basket = $165.83\text{s}$.
  - Độ lệch thời gian: $\Delta t_{\text{release}} = 0.20\text{s}$ ($\le 0.50\text{s}$), $\Delta t_{\text{basket}} = 0.03\text{s}$ ($\le 0.50\text{s}$). Tổng lệch: $0.23\text{s}$.
  - Vận tốc rơi qua rổ đo được: $v_y = 320.6\text{ px/s}$, đi qua 7 mẫu quan sát thực liên tiếp từ frame 77 ($y=255$) đến frame 85 ($y=340.5$).
  - Thuộc tính phụ: Nhận diện đội là `team_b` (do baseline tracker gán nhầm track 2 là team_b ở frame 66) trong khi GT là `team_a`. Điểm số ở trạng thái `unresolved_geometry` do chưa có tọa độ sân.

### 5.2. False Positive (FP = 1)
- **`play_021` (`shot_play_021_0001`):**
  - Thời gian dự đoán: Release = $730.20\text{s}$, Basket = $730.63\text{s}$.
  - Ground Truth gần nhất: Release = $729.10\text{s}$, Basket = $730.50\text{s}$.
  - Độ lệch thời gian: $\Delta t_{\text{release}} = 1.10\text{s}$ (vượt quá ngưỡng dung sai $0.50\text{s}$); $\Delta t_{\text{basket}} = 0.13\text{s}$.
  - Nguyên nhân kỹ thuật: Cầu thủ thực hiện ném bị che khuất một phần; bộ theo dõi bóng bị rung lắc (jitter) khiến vận tốc bay hướng lên trên kích hoạt pha `RELEASE` trễ hơn $1.1\text{s}$ so với thời điểm bóng rời tay thật của cầu thủ. Evaluator bipartite matching từ chối ghép cặp do vượt ngưỡng dung sai và hạch toán thành 1 FP.

### 5.3. False Negatives (FN = 9)
Tất cả 9 quả ném thành công trong Ground Truth bị bỏ lỡ đều xuất phát từ giới hạn vật lý của upstream detector/tracker trên video broadcast chất lượng thấp:
1. **`play_001`:** Bóng bị mất dấu (detection confidence < 0.15) trong giai đoạn tiếp cận vành rổ; không đủ 2 mẫu quan sát thực trong aperture.
2. **`play_004`:** Detector không phát hiện được bounding box vành rổ khi bóng đi qua mặt phẳng vành rổ.
3. **`play_006`:** Phân đoạn ném phạt quay cận cảnh (non-broadcast closeup), góc máy bị nghiêng và không thể trích xuất hình học vành rổ hợp lệ.
4. **`play_008`:** Bóng bị cầu thủ phòng ngự che khuất $> 0.35\text{s}$ trong lúc bay; FSM kích hoạt cơ chế an toàn hủy pha và chuyển về IDLE.
5. **`play_015`:** Phân đoạn ném phạt góc máy phụ; vận tốc rơi qua rổ đo được không đạt ngưỡng $v_y > 30\text{ px/s}$.
6. **`play_021`:** GT play_021 không có shot dự đoán nào thỏa mãn dung sai $\pm 0.50\text{s}$ (shot tương ứng bị lệch release $1.1\text{s}$).
7. **`play_023`:** Cụm cầu thủ tranh chấp dưới rổ làm che khuất quỹ đạo thoát ra ở đáy rổ.
8. **`play_027`:** Bóng chỉ xuất hiện ở 1 frame đơn lẻ trong aperture rổ (yêu cầu tối thiểu là 2 mẫu quan sát thực).
9. **`play_028`:** Tình huống phản công nhanh camera lia nhanh gây mờ chuyển động (motion blur); tọa độ vành rổ bị trễ $> 1.5\text{s}$ dẫn đến hủy xác nhận.

---

## 6. Gói kiểm duyệt tập âm tính (Negative Review Packet)

Tất cả 30 tình huống âm tính trong [`codebase/outputs/task08-shot-correctness-20261112/negative_review_packet`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task08-shot-correctness-20261112/negative_review_packet) đã được lập danh mục và đánh giá thực nghiệm:

- **Cấu trúc danh mục:**
  - 10 tình huống ném trượt hoàn toàn (`clean_miss`): Không có bóng xuyên qua rổ.
  - 8 tình huống ném trượt đập bảng/bật vành rổ (`rim_backboard_miss`): Bóng va chạm nhưng văng ra ngoài hoặc nảy ngược lên trên, không thỏa mãn điều kiện đi xuống qua tâm vành rổ.
  - 6 tình huống mất bóng / không có ném rổ (`turnover_non_shot`): Chuyền bóng hỏng, bóng rơi tự do ngoài khu vực rổ.
  - 6 phân đoạn quay chậm (`replay_segment`): Ký tự đồ họa hoặc góc quay lặp lại bị bộ dập replay và cooldown ngăn chặn.
- **Kết quả thực nghiệm:**
  - $30 / 30$ tình huống ($100.0\%$) được FSM và Points Engine từ chối thành công ($0$ False Positive).
- **Trạng thái pháp lý và tính chân thực (`P1-D`):**
  - Tệp manifest [`negative_manifest.json`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task08-shot-correctness-20261112/negative_review_packet/negative_manifest.json) ghi rõ:
    ```json
    "provenance": {
      "status": "draft_unreviewed",
      "independent_review_signed_off": false,
      "note": "Negative situations curated for diagnostic evaluation; official human sign-off pending."
    }
    ```
  - Trong `summary.json`, chỉ số độ đặc hiệu chính thức (`official_specificity`) được đặt là `null` / `None` kèm ghi chú giải thích rõ ràng. Tỷ lệ 100% chỉ được báo cáo dưới danh nghĩa `draft_diagnostic_rejection_rate` phục vụ kiểm tra nội bộ.

---

## 7. Kiểm chứng tích hợp Downstream (Event Ledger & Box Score)

Để chứng minh đầu ra của Temporal Shot Engine tích hợp hoàn toàn nhất quán với hệ thống tính điểm tự động của Task 11:
- Các điểm số xác nhận từ Candidate C được nạp vào [`EventLedger`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/src/basketball_scoreboard/events.py):
  - Do chưa có tọa độ sân 3D, các cú ném được ghi nhận đúng chuẩn là `UNRESOLVED` (geometry unresolved) theo đúng hợp đồng của `PointsEngine`.
  - Hai sự kiện được nạp thành công: `score_play_003_0001` và `score_play_021_0001`.
- **Kiểm chứng tính Idempotent:**
  - Tiến hành nạp lại toàn bộ các sự kiện lần thứ hai: Sổ cái từ chối toàn bộ bản sao trùng lặp (`Rejected as duplicate of canonical event`), số lượng sự kiện hoạt động giữ nguyên 2.
- **Kiểm chứng bảo toàn (Conservation Invariants):**
  - [`BoxScoreEngine`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/src/basketball_scoreboard/boxscore.py) biên dịch và đối soát thành công:
    * `observed_points = 0`, `unresolved_shots = 2`.
    * Không có điểm số nào bị tạo ra tùy tiện hoặc bị tính lặp.
    * Tất cả các định luật bảo toàn điểm số và phân loại đều thỏa mãn (`Conservation Valid: True`).
  - Xuất thành công các tệp [`ledger_active.jsonl`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task08-shot-correctness-20261112/downstream_integration/ledger_active.jsonl), [`ledger_audit.jsonl`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task08-shot-correctness-20261112/downstream_integration/ledger_audit.jsonl), [`boxscore_auto.csv`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task08-shot-correctness-20261112/downstream_integration/boxscore_auto.csv) và [`reconciliation.json`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task08-shot-correctness-20261112/downstream_integration/reconciliation.json).

---

## 8. Trạng thái các kiểm thử tự động (Test Verification)

Toàn bộ các bộ kiểm thử liên quan đều vượt qua với kết quả tuyệt đối:

1. **Acceptance Probes (4 Task 08 probes):**
   - Lệnh: `codebase/.venv/Scripts/python.exe -m pytest codebase/outputs/acceptance-demo-20261110/test_acceptance_requirements.py -q -k "predicted_entry_exit_cannot_confirm_made or crossing_cannot_bridge_long_observation_gap or production_evaluator_rejects_out_of_tolerance_made or production_evaluator_counts_duplicate_as_fp"`
   - Kết quả: **4 PASSED, 36 deselected in 0.17s** (Khắc phục hoàn toàn 4 lỗi probe baseline).
2. **Task 08 Temporal Engine Test Suite:**
   - Lệnh: `codebase/.venv/Scripts/python.exe -m pytest codebase/tests/test_task08_temporal_shot_engine.py -q`
   - Kết quả: **14 PASSED in 0.18s** (Bao gồm các ca kiểm thử tính liên tục quan sát thực, gap abort, net cue đo lường, rổ cũ, track xung đột).
3. **Production Evaluator Test Suite:**
   - Lệnh: `codebase/.venv/Scripts/python.exe -m pytest codebase/tests/test_task08_evaluator.py -q`
   - Kết quả: **11 PASSED in 0.18s** (Bao gồm bẫy tham lam greedy trap, dung sai chính xác $\pm 0.50\text{s}$, đếm lặp FP, tính tất định khi hoán vị, và xử lý status draft_unreviewed).
4. **Task 11 Ledger & BoxScore Suite:**
   - Lệnh: `codebase/.venv/Scripts/python.exe -m pytest codebase/tests/test_task11_ledger_and_boxscore.py -q`
   - Kết quả: **33 PASSED in 0.22s**.
5. **Toàn bộ Test Suite Codebase:**
   - Lệnh: `codebase/.venv/Scripts/python.exe -m pytest codebase/tests -q`
   - Kết quả: **404 PASSED, 0 failed, 6 warnings, 61 subtests passed in 48.22s** (Tăng từ 393 lên 404 passed, không có bất kỳ regression nào).

---

## 9. Danh mục Artifacts đã tạo

Các artifacts được lưu trữ đầy đủ tại [`codebase/outputs/task08-shot-correctness-20261112`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task08-shot-correctness-20261112):

1. [`run.json`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task08-shot-correctness-20261112/run.json): Metadata thực thi, cấu hình protocol, SHA-256 các tệp đầu vào, thời gian chạy.
2. [`summary.json`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task08-shot-correctness-20261112/summary.json): Tổng hợp kết quả 3 candidates, 30 ca âm tính, phân loại lỗi, và đối chiếu trước/sau.
3. [`source_snapshot_before.json`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task08-shot-correctness-20261112/source_snapshot_before.json) & [`source_snapshot_after.json`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task08-shot-correctness-20261112/source_snapshot_after.json): Bảng băm SHA-256 của các tệp nguồn trước và sau khi chỉnh sửa.
4. [`commands.json`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task08-shot-correctness-20261112/commands.json): Nhật ký toàn bộ các câu lệnh đã chạy kèm mã thoát (exit code).
5. [`match_table_candidate_c.json`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task08-shot-correctness-20261112/match_table_candidate_c.json) & [`match_table_candidate_c.csv`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task08-shot-correctness-20261112/match_table_candidate_c.csv): Bảng match chi tiết từng shot với Ground Truth, chênh lệch thời gian và phân loại lỗi.
6. Thư mục [`candidate_a/`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task08-shot-correctness-20261112/candidate_a), [`candidate_b/`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task08-shot-correctness-20261112/candidate_b), [`candidate_c/`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task08-shot-correctness-20261112/candidate_c): Chứa `shots_auto.jsonl`, `points_auto.jsonl`, `shot_state_transitions.jsonl` và `evaluation.json`.
7. Thư mục [`negative_review_packet/`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task08-shot-correctness-20261112/negative_review_packet): Chứa `negative_manifest.json` (status: `draft_unreviewed`), `negative_eval_candidate_c.json` và `.csv`.
8. Thư mục [`downstream_integration/`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task08-shot-correctness-20261112/downstream_integration): Chứa `ledger_active.jsonl`, `ledger_audit.jsonl`, `boxscore_auto.csv` và `reconciliation.json`.

---

## 10. Kết luận & Các bước tiếp theo

1. **Kết luận:**
   - Các khiếm khuyết nghiệm thu **P1-B**, **P1-C** và **P1-D** đã được khắc phục hoàn toàn trên cả mã sản phẩm (`shots.py`), module đánh giá (`shot_evaluator.py`), script thực thi (`run_task08_temporal_shot_engine.py`) và hệ thống kiểm thử tự động.
   - Mã nguồn tuân thủ tuyệt đối tính trung thực khoa học: không rò rỉ nhãn Ground Truth, không tạo dữ liệu giả mạo, không tuyên bố sai độ đặc hiệu của tập dữ liệu nháp.
2. **Kế hoạch tiếp theo:**
   - **Giữ nguyên trạng thái Task 08 và Demo MVP là `IN_PROGRESS`:** Để đạt được chỉ tiêu nghiệm thu thương mại PRA (Precision $\ge 95\%$, Recall $\ge 90\%$), cần thực hiện huấn luyện/fine-tune lại mô hình phát hiện bóng và vành rổ ở Task 05/Task 07 trên tập dữ liệu mở rộng đa góc máy.
   - Chuyển giao gói dữ liệu `negative_review_packet` cho hội đồng thẩm định độc lập để ký duyệt chính thức khi có nhân sự.
   - Tiếp tục hoàn thiện các hợp đồng nghiệp vụ cho Rebound (Task 09), Assist (Task 10), và luồng video streaming MP4 liên tục (Task 12).

