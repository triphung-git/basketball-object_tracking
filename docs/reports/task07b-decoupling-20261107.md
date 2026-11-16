# Task07B — Tách Biệt Actor/Body Evidence, Paired Replay và Truy Nguyên Lỗi Kiểm Soát/Chuyền Bóng

Ngày: 2026-11-07.  
Trạng thái: **Task07 tiếp tục IN_PROGRESS. Candidate CHƯA ĐỦ ĐIỀU KIỆN FREEZE CHO 07C.**  
Báo cáo đối chiếu source/artifacts thực tế tại `codebase/outputs/task07b-decoupling-20261107/`. Toàn bộ 309 tests unit/regression PASS.

---

## 1. Tóm Tắt Kết Quả và Quyết Định

### 1.1. Mục Tiêu Đã Thực Hiện
1. **Tách biệt ngữ nghĩa Actor/Body cho Ball Association:** Đã cập nhật `codebase/src/basketball_scoreboard/ball_pipeline.py` để lựa chọn actor context dựa trên điều kiện `sample_type == 'observed' and role != 'non_player'`, thay vì ràng buộc cứng `role == 'player'`. Điều này cho phép các cơ thể người trên sân chưa qua nhận diện OCR/jersey hoặc đang có `role == 'unknown'` vẫn cung cấp đầy đủ ngữ cảnh không gian (human body context) cho ball tracker mà không bị gán nhãn tùy tiện thành `player`, bảo đảm tính causal timing và provenance.
2. **Khắc phục triệt để hiện tượng Regression của Full Guard:** 
   - Trong phiên Task07B trước (2026-11-06), cấu hình Full Guard (`recovery-final`) bị sụt giảm ball observed recall từ 36/72 (50.00%) xuống 33/72 (45.83%) do các track bị chặn crop rơi về `role == 'unknown'`, làm giảm số lượng context actors và khiến bóng bị loại do vượt ngưỡng `max_initial_body_distance`.
   - Với cơ chế tách biệt (decoupling) mới, **Full Guard đạt 36/72 (50.00%) ball recall, loại bỏ 100% sự sụt giảm (regression eliminated)**.
3. **Giữ Candidate phát triển an toàn:** Tiếp tục duy trì candidate `--team-crop-region jersey --reset-on-team-conflict` cho phát triển cục bộ, không bật Full Guard làm mặc định toàn hệ thống.
4. **Truy nguyên lỗi 7 tầng (7-layer root cause failure trace):** Phân tích chi tiết toàn bộ 8 khoảng thời gian kiểm soát (control intervals) và 5 đường chuyền (passes) theo Ground Truth reviewed v2.

---

## 2. Bảng So Sánh Trước / Sau (Paired A/B Replay)

Cùng đầu vào (detections tiled v2, run.json, video `vt_development.mp4`, policy `vt_development-policy-ball-roi-v4.json`, config `ball-possession-vietnam-tonga-spatial.json`, GT `reviewed-vt_development-v2.json`, profile `task07_vietnam_tonga.json`):

| Chỉ số / Tiêu chí | Baseline (Legacy Defaults) | Candidate (`jersey + conflict-reset`) | Full Guard (`recovery-final` + Decoupling) | Ghi chú & Diễn giải |
|---|---:|---:|---:|---|
| **Ball Observed Recall** | **36/72 (50.00%)** | **36/72 (50.00%)** | **36/72 (50.00%)** | Decoupling đã khôi phục hoàn toàn recall (trước đó là 33/72) |
| **Strict Controller Accuracy** | **0.0%** (0.0s / 14.30s) | **0.0%** (0.0s / 14.30s) | **0.0%** (0.0s / 14.30s) | Các track kiểm soát thiếu số áo OCR hợp lệ nên `player_id` là `None` |
| **Confirmed Team Error Time** | **0.633s** | **0.067s** (giảm **89.5%**) | N/A (chưa promote) | Cơ chế reset khi xung đột màu giúp sửa trôi team trên track 24 |
| **Strict Pass Precision** | **N/A** (0 dự đoán) | **N/A** (0 dự đoán) | **N/A** (0 dự đoán) | Không có pass nào được xác nhận hoàn chỉnh |
| **Strict Pass Recall** | **0.0%** (0 / 5) | **0.0%** (0 / 5) | **0.0%** (0 / 5) | TP = 0, FP = 0, FN = 5 |
| **Event-only Pass Recall** | **0.0%** (0 / 5) | **0.0%** (0 / 5) | **0.0%** (0 / 5) | TP = 0, FP = 0, FN = 5 |
| **Continuous Trajectory Identity** | **N/A** | **N/A** | **N/A** | GT không có nhãn trajectory player liên tục theo từng frame |
| **Team Accuracy (Reviewed Crops Cohort)** | 5/7 (71.4%) | **7/7 (100.0%)** | 7/7 (100.0%) | Trên 7 mốc snapshot crop được reviewer xác nhận đúng người/vùng |
| **Integrity: Prediction-only Confirmed Control** | **0 frame (PASS)** | **0 frame (PASS)** | **0 frame (PASS)** | Guard ngăn chặn hoàn toàn việc xác nhận kiểm soát chỉ bằng bóng dự đoán |
| **Integrity: Pass Crossing Cut** | **0 pass (PASS)** | **0 pass (PASS)** | **0 pass (PASS)** | Không có đường chuyền nào cắt qua ranh giới chuyển cảnh |
| **Integrity: PTS Timestamping** | **Hợp lệ (PASS)** | **Hợp lệ (PASS)** | **Hợp lệ (PASS)** | Độ lệch thời gian $\le 2\mu\text{s}$, tăng đơn điệu chặt chẽ |
| **Pipeline Latency (Tracking Total)** | 26.8s (~33.6 FPS) | 26.8s (~33.6 FPS) | 26.9s (~33.5 FPS) | Bao gồm decode, validation, tracking, OCR cache replay; **không gồm raw detector** |
| **Core Ball Tracking Latency** | ~1.5s (~600 FPS) | ~1.5s (~600 FPS) | ~1.5s (~600 FPS) | Tách riêng phần thuật toán liên kết bóng và kiểm soát |

---

## 3. Truy Nguyên Lỗi 7 Tầng (7-Layer Root Cause Failure Trace)

Quá trình truy nguyên chi tiết dựa trên dữ liệu chẩn đoán `candidate-trace/trace.json`:

```
Ground Truth Control: 14.30s (8 khoảng kiểm soát)
├── [Layer 1] Detector Miss (Bóng không phát hiện): 5.767s (40.3% thời lượng)
├── [Layer 2] Ball Selection / Spatial ROI Gate: 5 frames GT bị reject bởi spatial ROI/gate
├── [Layer 3] Actor Association (Tranh chấp / Không rõ): 5.800s (Bóng quan sát được nhưng chưa đủ điều kiện confirm control)
├── [Layer 4] Team Assignment: 0.067s sai/chưa rõ đội (giảm mạnh từ 0.633s ở Baseline nhờ conflict-reset)
├── [Layer 5] Jersey OCR: 2.667s bóng đã được confirm control nhưng người cầm bóng thiếu số áo OCR
├── [Layer 6] Identity Resolution: Strict matching yêu cầu cả player_id + team_id -> strict accuracy 0.0%
└── [Layer 7] Temporal State / Passes: 0 TP, 5 FN do đứt gãy tại các điểm đầu/cuối đường chuyền
```

### 3.1. Chi tiết theo từng khoảng kiểm soát (Control Intervals)
1. **Interval 1 (t = 1.833s - 7.999s, Nguyễn Huỳnh Phú Vinh - team_a):**
   - Bóng không quan sát được: 1.967s.
   - Bóng quan sát được nhưng chưa confirm control: 2.233s.
   - Confirmed control nhưng sai/chưa rõ team: **0.033s** (ở Baseline là **0.600s** do trôi màu trên track 24; Candidate đã loại bỏ 94.4% lỗi này).
   - Confirmed control nhưng thiếu/sai player_id: 1.933s (do track không có đọc số áo OCR hợp lệ).
2. **Interval 2 (t = 8.633s - 9.567s, Nguyễn Phúc Vinh - team_a):**
   - Bóng không quan sát được: 0.667s; chưa confirm: 0.233s; thiếu player_id: 0.033s.
3. **Interval 3 (t = 10.433s - 11.000s, Tonga #11 - team_b):**
   - Bóng không quan sát được: 0.267s; chưa confirm: 0.200s; sai/chưa rõ team: 0.033s; thiếu player_id: 0.067s.
4. **Interval 4 (t = 11.567s - 12.700s, Tonga #18 - team_b):**
   - Bóng không quan sát được: 0.167s; chưa confirm: 0.400s; thiếu player_id: 0.567s (track được gán đúng team_b nhưng thiếu số 18).
5. **Interval 5 (t = 13.567s - 14.500s, Tonga #11 - team_b):**
   - Bóng không quan sát được: 0.467s; chưa confirm: 0.467s.
6. **Interval 6 (t = 15.633s - 18.400s, Nguyễn Phúc Vinh - team_a):**
   - Bóng không quan sát được: 1.700s; chưa confirm: 1.067s.
7. **Interval 7 (t = 18.933s - 19.467s, Huỳnh Thanh Tâm - team_a):**
   - Bóng không quan sát được: 0.267s; chưa confirm: 0.267s.
8. **Interval 8 (t = 20.000s - 20.167s, Nguyễn Phúc Vinh - team_a):**
   - Bóng không quan sát được: 0.167s.

### 3.2. Chi tiết theo từng đường chuyền (Pass Endpoints)
- **Pass 1 (t = 8.067s - 8.533s, Nguyễn Huỳnh Phú Vinh $\rightarrow$ Nguyễn Phúc Vinh):**
  - *Release (frame 242, t = 8.067s):* Bóng quan sát được, nhưng rơi vào trạng thái `contested` (2 cầu thủ ở quá gần nhau trong biên độ `ambiguity_margin`).
  - *Receive (frame 256, t = 8.533s):* Bóng bị miss ở detector (dự đoán chuyển sang `predicted`), ứng viên duy nhất bị loại bởi spatial gate (`spatially_rejected_candidates = 1`). Không thể xác nhận điểm nhận bóng.
- **Pass 2 (t = 10.933s - 11.567s, Tonga #11 $\rightarrow$ Tonga #18):**
  - *Release (frame 328, t = 10.933s):* Bóng ở trạng thái `predicted` (`no_gated_ball_observation`), control là `unknown`.
  - *Receive (frame 347, t = 11.567s):* Bóng quan sát được nhưng rơi vào `contested` / `control_candidate`.
- **Pass 3 (t = 12.700s - 13.567s, Tonga #18 $\rightarrow$ Tonga #11):**
  - *Release (frame 381, t = 12.700s):* Vận tốc tương đối của bóng cao gây `motion_ambiguous_interaction`. Tiếp đó, tại frames 388, 389, 390 (khoảng trống 0.133s > ngưỡng `max_unobserved_gap_s` 0.10s), raw ball detector hoàn toàn mất dấu bóng, kích hoạt `unobserved_gap_exceeded` kết thúc pass tracking.
  - *Receive (frame 407, t = 13.567s):* Điểm nhận bóng chỉ có bóng dự đoán.
- **Pass 4 (t = 18.400s - 18.933s, Nguyễn Phúc Vinh $\rightarrow$ Huỳnh Thanh Tâm):**
  - *Release (frame 552) & Receive (frame 568):* Cả hai đầu mút đều có bóng ở trạng thái `predicted`, không có quan sát thực từ detector.
- **Pass 5 (t = 19.467s - 20.000s, Huỳnh Thanh Tâm $\rightarrow$ Nguyễn Phúc Vinh):**
  - *Release (frame 584):* Bóng bị mất dấu (`ball_track_change`), trạng thái control là `unknown`.
  - *Receive (frame 600):* Bóng ở trạng thái `predicted`.

**Kết luận nguyên nhân:** Không có đường chuyền nào đạt True Positive do:
1. Thiếu quan sát bóng thực tế từ detector tại các điểm release/receive (Layer 1).
2. Thiếu nhận diện số áo OCR để xác nhận danh tính cầu thủ chuyền/nhận (Layer 5 & 6).

---

## 4. Phương Án Huấn Luyện Tinh Chỉnh (Fine-Tuning / Training Proposal) Giải Quyết Blocker Detector

Vì raw ball detector miss là rào cản cốt lõi (31/72 mẫu bóng GT không có bounding box từ detector; 40.3% thời gian kiểm soát thiếu bóng; các điểm release/receive của pass bị mất dấu), chúng tôi đề xuất phương án cụ thể sau trước khi xin phê duyệt thực thi:

### 4.1. Data Readiness (Mức Độ Sẵn Sàng Của Dữ Liệu)
- **Approved Reviewed Labels (v2 corrected):** 40 frames đã qua kiểm duyệt đầy đủ (100% verified ground truth cho ball và player bounding boxes).
- **Unreviewed Draft Candidates:** 319 frames trích xuất từ phân đoạn `vt_development` và footage trận đấu với nhãn tự động cần rà soát nhanh.
- **Định dạng nhãn:** Chuẩn hóa YOLO format (`class x_center y_center width height` chuẩn hóa theo [0, 1]).

### 4.2. Source-Group Splits (Phân Chia Nhóm Nguồn Chống Rò Rỉ Thời Gian)
- **Nguyên tắc:** Phân chia theo nhóm phân đoạn / trận đấu (Group-aware temporal partitioning), tuyệt đối không xáo trộn ngẫu nhiên (random shuffle) các frame liên tiếp để tránh rò rỉ thông tin tương quan thời gian.
- **Phân bổ:**
  - *Train set:* Segment 1 (`vt_development` frames 0-600) + dữ liệu các góc máy bổ trợ.
  - *Validation set:* Segment 2 (`vt_development` frames 601-900).
  - *Test set (Locked Benchmark):* Độc lập hoàn toàn trên video test `vt_test` (không tham gia huấn luyện hoặc validation).

### 4.3. Checkpoint & Kiến Trúc Mô Hình
- **Mô hình cơ sở:** `yolov8n` hoặc `yolov8s` (kích thước siêu nhẹ: 3M - 11M tham số) đã pretrained trên COCO (lớp sports ball - class 32).
- **Ràng buộc suy luận:** Phải xuất được định dạng ONNX FP32/FP16 tương thích với `basketball_scoreboard.detector.YoloOnnxDetector` hiện hành để chạy trực tiếp trên CPU luồng đơn/đa luồng mà không làm tăng độ trễ hệ thống.

### 4.4. Recipe & Siêu Tham Số Huấn Luyện
- **Độ phân giải đầu vào:** 1280x1280 (hoặc letterbox 1920x1080 native tile) nhằm bảo toàn đặc trưng của quả bóng rổ kích thước nhỏ (~15-25px ở cự ly xa).
- **Epochs:** 60 epochs với EarlyStopping (patience = 12).
- **Augmentation:** Mosaic, Mixup (0.1), Motion Blur (mô phỏng bóng bay tốc độ cao), Perspective Jitter, HSV color shift nhẹ.
- **Loss & Optimizer:** AdamW, learning rate ban đầu 0.001 với cosine learning rate decay.
- **Vùng quan tâm (Aerial ROI):** Bổ sung dải biên trên để giữ lại quỹ đạo của các đường chuyền bổng.

### 4.5. Runtime & Chi Phí (Compute & Cost)
- **Phần cứng thực thi:** Huấn luyện hoàn toàn trên môi trường máy trạm cục bộ (Local Workstation GPU hoặc CPU multi-thread).
- **Thời gian huấn luyện dự kiến:** ~1.5 - 2.5 giờ trên GPU cục bộ (hoặc ~6 - 8 giờ trên CPU).
- **Chi phí đám mây:** **0.00 USD** (không sử dụng cloud GPU hay dịch vụ bên ngoài).

---

## 5. Artifacts, Manifest và Tính Toàn Vẹn

Toàn bộ kết quả chạy paired replay, đánh giá và truy nguyên lỗi đã được lưu trữ độc lập tại:
- **Thư mục output mới:** `codebase/outputs/task07b-decoupling-20261107/`
- **Video kiểm tra trực quan:** [debug.mp4](../../codebase/outputs/task07b-decoupling-20261107/candidate-ball/debug.mp4) (11.36 MB, 900 frames, overlay quỹ đạo bóng và trạng thái kiểm soát).
- **Dòng thời gian kiểm soát:** [timeline.png](../../codebase/outputs/task07b-decoupling-20261107/candidate-ball/timeline.png) (73.28 KB).
- **Báo cáo đánh giá JSON:** [evaluation.json](../../codebase/outputs/task07b-decoupling-20261107/candidate-evaluation/evaluation.json).
- **Dữ liệu truy nguyên lỗi:** [trace.json](../../codebase/outputs/task07b-decoupling-20261107/candidate-trace/trace.json).
- **Bảng băm toàn vẹn:** [manifest.json](../../codebase/outputs/task07b-decoupling-20261107/manifest.json) (54 tệp tin với kích thước và mã băm SHA256).

---

## 6. Kết Luận & Quyết Định Freeze

1. **Hiệu quả của Decoupling:** Khẳng định việc tách biệt actor/body context khỏi jersey/identity uncertainty là hoàn toàn chính xác về mặt kiến trúc, giúp loại bỏ 100% hiện tượng regression ball recall của Full Guard (từ 45.83% phục hồi về 50.00%).
2. **Điều kiện Freeze cho 07C:**
   - Tiêu chí nghiệm thu của Task07 yêu cầu: Ball observed recall $\ge 70\%$, Strict controller accuracy $\ge 60\%$, Strict pass recall $\ge 50\%$.
   - Hiện tại: Ball recall đạt 50.00%, Strict controller accuracy đạt 0.0%, Strict pass recall đạt 0.0% (TP = 0, FP = 0, FN = 5).
   - **Kết luận:** Phiên bản Candidate **CHƯA ĐỦ ĐIỀU KIỆN FREEZE CHO 07C**.
3. **Trạng thái nhiệm vụ:** Duy trì **Task07 ở trạng thái IN_PROGRESS**. Tiếp tục hoàn thiện bước chuẩn bị dữ liệu và xin phê duyệt kế hoạch fine-tuning detector.

