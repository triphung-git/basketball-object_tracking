# Báo Cáo Nghiệm Thu Task07C — Đánh Giá Tiêu Chuẩn Thực Tế Theo Protocol Đã Duyệt

Ngày thực hiện: 2026-11-08.  
Trạng thái nghiệm thu: **FAILED CRITERIA (KHÔNG ĐẠT NGHIỆM THU).**  
Trạng thái nhiệm vụ: **Task07 tiếp tục IN_PROGRESS. Các Task04, Task05, Task06 giữ nguyên trạng thái hiện tại.**  
Mọi kết quả được lưu trữ độc lập tại [`codebase/outputs/task07c-acceptance-20261107/`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task07c-acceptance-20261107/).

---

## 1. Kết Quả Nghiệm Thu Theo Từng Cổng Tiêu Chí (Gate Acceptance Summary)

Căn cứ theo acceptance profile đã được người dùng phê duyệt [`codebase/configs/evaluation/task07_vietnam_tonga.json`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/configs/evaluation/task07_vietnam_tonga.json) (SHA-256 `1a79aa9a6697b3eea63c9e07d53b9058ea927ce961e9f45f7396e6b7f51da097`):

| Cổng Nghiệm Thu (Gate) | Tiêu Chuẩn Duyệt | Kết Quả Trên Development (`vt_development`) | Kết Quả Trên Validation (`vt_validation`) | Đánh Giá Chung |
|---|:---:|:---:|:---:|:---:|
| **Gate 1: Observed Ball Recall** | $\ge 90.0\%$ (IoU $\ge 0.30$) | **50.00%** (36 / 72 mẫu hợp lệ) | **N/A** (GT draft chưa review) | <span style="color:red;font-weight:bold">FAIL</span> |
| **Gate 2: Strict Controller Accuracy** | $\ge 90.0\%$ (đúng player & team) | **0.00%** (0.0s / 14.30s eligible) | **N/A** (0 khoảng kiểm soát GT) | <span style="color:red;font-weight:bold">FAIL</span> |
| **Gate 3: Strict Pass Precision** | $\ge 95.0\%$ ($|\Delta t| \le 0.25\text{s}$) | **N/A** (0 đường chuyền dự đoán) | **N/A** (0 đường chuyền dự đoán) | **N/A** |
| **Gate 4: Strict Pass Recall** | $\ge 90.0\%$ (TP / [TP + FN]) | **0.00%** (0 TP, 0 FP, 5 FN) | **N/A** (0 đường chuyền GT) | <span style="color:red;font-weight:bold">FAIL</span> |
| **Gate 5: Event-Only Pass Recall** | Chẩn đoán | **0.00%** (0 TP, 0 FP, 5 FN) | **N/A** (0 đường chuyền GT) | <span style="color:red;font-weight:bold">FAIL</span> |
| **Gate 6.1: No Prediction-Only Control** | 0 frame | **0 frame (PASS)** | **0 frame (PASS)** | <span style="color:green;font-weight:bold">PASS</span> |
| **Gate 6.2: No Pass Crossing Cut** | 0 pass | **0 pass (PASS)** | **0 pass (PASS)** | <span style="color:green;font-weight:bold">PASS</span> |
| **Gate 6.3: PTS Export Timestamp Error** | $\le 2\mu\text{s}$, tăng đơn điệu | **$\approx 0.33\mu\text{s}$ (PASS)** | **$\approx 0.33\mu\text{s}$ (PASS)** | <span style="color:green;font-weight:bold">PASS</span> |

**Kết luận tổng thể:** Hệ thống đạt tuyệt đối 100% các tiêu chí về tính toàn vẹn hệ thống (Integrity Guards Gate 6.1 - 6.3). Tuy nhiên, các tiêu chí cốt lõi về nhận diện bóng và kiểm soát/chuyền bóng (Gates 1, 2, 4) **không đạt ngưỡng**, đồng thời tập validation thiếu nhãn được duyệt. Vì vậy, phiên bản candidate **KHÔNG ĐỦ ĐIỀU KIỆN ĐÓNG TASK07**.

---

## 2. Xác Minh Tiền Điều Kiện (Pre-Condition Verification)

1. **Revision & Config & Model:**
   - Candidate code: `codebase/src/basketball_scoreboard/ball_pipeline.py` (L128–130) áp dụng decoupling `sample_type == 'observed' and role != 'non_player'`.
   - Cấu hình chạy: `--team-crop-region jersey --reset-on-team-conflict`, kết hợp `--config codebase/configs/ball-possession-vietnam-tonga-spatial.json` (SHA-256 `45120d97...`).
   - Roster chính thức: `codebase/configs/rosters/vietnam_tonga.json` (SHA-256 `9b6cf634...`).
   - Detector Model: Approved ONNX CPU `phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1`.
2. **Acceptance Manifest & Hashes:**
   - Acceptance profile hash: `1a79aa9a6697b3eea63c9e07d53b9058ea927ce961e9f45f7396e6b7f51da097` (Khớp tuyệt đối).
   - Video nguồn parent `vietnam-tonga.mp4`: `1443c1d263c8037a5684f3dbc0ef9216beb5097d9a47c4c1c9b94d1363e26865` (Khớp tuyệt đối).
   - Video development `vt_development.mp4`: `8fd370b0668860a5c70d56bf256c76e3783bc1fe6598b529944ad00ca0616b45` (Khớp tuyệt đối).
   - Video validation `vt_validation.mp4`: `88b6f9ce44feed84cb2a2b1fcc6b98d1a88fe38c1b16a6212682f5fa96c41544` (Khớp tuyệt đối).
3. **Quyền Truy Cập & Rào Cản Ground Truth:**
   - **Tập Development:** Đã có GT canonical duyệt v2 (`reviewed-vt_development-v2.json`, SHA-256 `ee3f10d7...`). Tuy nhiên tập này đã bị dùng để tune thuật toán.
   - **Tập Validation:** Tệp `annotations-draft.json` trong kho có `review_status: draft`, `reviewer: null`, 94 mẫu bóng dự thảo chưa review, 0 khoảng kiểm soát, 0 đường chuyền.
   - Khi chạy script nghiệm thu độc lập `evaluate_ball_possession.py`, bộ đánh giá đã chặn và từ chối xử lý:
     ```
     ValueError: Reviewed GT and approved protocol required
     ```
     Ghi nhận chi tiết tại [`validation-eval-attempt.json`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task07c-acceptance-20261107/validation-eval-attempt.json).

---

## 3. Kết Quả Chạy Pipeline & Đóng Băng Dự Đoán (Prediction Freeze)

Trước khi đọc Ground Truth, pipeline đã thực thi trên cả hai phân đoạn và xuất đầy đủ dự đoán thô (raw predictions):

### 3.1. Phân Đoạn Validation (`vt_validation.mp4`, 900 frames, 30.0s)
- **Player Tracking:** [`validation-tracking/tracked_observations.jsonl`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task07c-acceptance-20261107/validation-tracking/tracked_observations.jsonl) (12,403 observations, replay OCR verified).
- **Ball & Possession:**
  - `ball_tracks.jsonl`: 900 frames (Missing = 202, Observed = 532, Predicted = 166).
  - `ball_control.jsonl`: 900 frames (Unknown = 430, Controlled = 180, Contested = 128, Control Candidate = 117, Loose = 32, Free = 13).
  - `passes.jsonl`: 0 đường chuyền hoàn thành.
  - Video debug: [`validation-ball/debug.mp4`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task07c-acceptance-20261107/validation-ball/debug.mp4) (10.52 MB).
  - Biểu đồ thời gian: [`validation-ball/timeline.png`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task07c-acceptance-20261107/validation-ball/timeline.png) (66.32 KB).

### 3.2. Phân Đoạn Development (`vt_development.mp4`, 900 frames, 30.0s)
- **Player Tracking:** [`development-tracking/tracked_observations.jsonl`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task07c-acceptance-20261107/development-tracking/tracked_observations.jsonl) (14,007 observations).
- **Ball & Possession:**
  - `ball_tracks.jsonl`: 900 frames (Missing = 172, Observed = 475, Predicted = 253).
  - `ball_control.jsonl`: 900 frames (Unknown = 482, Control Candidate = 155, Controlled = 98, Loose = 83, Contested = 69, Free = 13).
  - `passes.jsonl`: 0 đường chuyền hoàn thành.
  - Video debug: [`development-ball/debug.mp4`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task07c-acceptance-20261107/development-ball/debug.mp4) (11.36 MB).
  - Biểu đồ thời gian: [`development-ball/timeline.png`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task07c-acceptance-20261107/development-ball/timeline.png) (73.28 KB).

---

## 4. Truy Nguyên Lỗi Thất Bại & Nút Thắt Kỹ Thuật (Error Traces)

Dữ liệu chẩn đoán truy nguyên chi tiết tại [`development-trace/trace.json`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task07c-acceptance-20261107/development-trace/trace.json):

```
Tổng thời lượng kiểm soát GT: 14.30s (8 khoảng kiểm soát)
├── [L1 - Detector Miss]: 5.767s (40.3% thời lượng) bóng hoàn toàn không được phát hiện bởi raw detector
├── [L2 - Spatial ROI Gate]: 5 frames GT bị reject bởi spatial ROI/gate
├── [L3 - Actor Association]: 5.800s bóng quan sát được nhưng chưa đủ điều kiện confirm control (tranh chấp/dribble)
├── [L4 - Team Evidence]: 0.067s sai/chưa rõ team (Candidate đã giảm 89.5% lỗi này so với baseline 0.633s)
├── [L5 - Jersey OCR]: 2.667s bóng đã confirm control nhưng track cầm bóng thiếu đọc số áo OCR hợp lệ
├── [L6 - Identity Resolution]: Strict matching yêu cầu cả player_id + team_id -> Strict accuracy đạt 0.0%
└── [L7 - Temporal Passes]: 0 TP, 5 FN do detector miss bóng tại các mốc release/receive và thiếu OCR identity
```

### Chi tiết 5 đường chuyền bị FN (False Negative)
1. **Pass 1 (t = 8.067s $\rightarrow$ 8.533s, Việt Nam):** Release rơi vào `contested` (2 cầu thủ quá gần nhau); receive bị miss ở detector (`spatially_rejected_candidates = 1`).
2. **Pass 2 (t = 10.933s $\rightarrow$ 11.567s, Tonga):** Release có bóng ở trạng thái `predicted`, control `unknown`; receive bóng rơi vào `contested`.
3. **Pass 3 (t = 12.700s $\rightarrow$ 13.567s, Tonga):** Release bị motion ambiguity. Từ frame 388 đến 390 (0.133s > ngưỡng gap 0.10s), detector miss bóng liên tiếp, kích hoạt `unobserved_gap_exceeded` ngắt pass tracking; receive có bóng `predicted`.
4. **Pass 4 & 5 (t = 18.400s $\rightarrow$ 18.933s và 19.467s $\rightarrow$ 20.000s):** Cả hai đầu release/receive đều thiếu quan sát bóng thực tế từ raw detector.

---

## 5. Báo Cáo Đo Lường Độ Trễ (Latency Benchmark)

Được đo lường trên môi trường trạm làm việc chuẩn (Windows, Python 3.12, ONNX CPU Backend):

| Thành Phần Thực Thi | Phân Đoạn Validation (900 frames, 30.0s) | Phân Đoạn Development (900 frames, 30.0s) | Ghi Chú Kỹ Thuật |
|---|---:|---:|---|
| **Player Tracking (gồm OCR cache replay)** | 27.2s (~33.1 FPS) | 26.8s (~33.6 FPS) | Bao gồm decode video, tracker, lọc ROI, và nạp bằng chứng màu/OCR |
| **Core Ball Tracking Algorithm** | **~1.5s (~600 FPS)** | **~1.5s (~600 FPS)** | Tách riêng thuật toán liên kết bóng và máy trạng thái kiểm soát |
| **Muxing & Export Debug Video / Timeline** | ~31.2s | ~30.0s | Sử dụng FFmpeg để render visual overlay và matplotlib cho timeline |
| **Tổng Thời Gian Pipeline (End-to-End)** | **59.90s (~15.0 FPS)** | **58.34s (~15.4 FPS)** | **Chưa bao gồm raw object detector**. Full-frame tiled detector mất ~560s trên CPU. |

---

## 6. Lệnh Tái Chạy & Bảng Băm Manifest

Toàn bộ 35 tệp tin sinh ra từ đợt chạy nghiệm thu Task07C được lưu trong [`codebase/outputs/task07c-acceptance-20261107/manifest.json`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task07c-acceptance-20261107/manifest.json).

Lệnh tái lập toàn bộ quy trình:
```powershell
codebase/.venv/Scripts/python.exe codebase/scripts/run_task07c_acceptance_evaluation.py
```

---

## 7. Kết Luận Nghiệm Thu & Khuyến Nghị

1. **Kết Luận Cổng Nghiệm Thu Task07C:**
   - **FAILED CRITERIA.** Không thể nghiệm thu Task07C do:
     - Observed ball recall đạt 50.00% (chưa đạt ngưỡng $\ge 90\%$).
     - Strict controller accuracy đạt 0.00% (chưa đạt ngưỡng $\ge 90\%$).
     - Strict pass recall đạt 0.00% (chưa đạt ngưỡng $\ge 90\%$).
     - Tập validation chưa có nhãn Ground Truth được phê duyệt.
2. **Trạng Thái Nhiệm Vụ:**
   - Duy trì **Task07 ở trạng thái IN_PROGRESS**.
   - Tuyệt đối không đóng Task04, Task05, Task06 khi Task07 chưa hoàn thành.
3. **Kế Hoạch Khắc Phục:**
   - Hoàn thành quy trình review bổ sung cho tập validation qua gói giao diện [`review_packet/review.html`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task07c-acceptance-package-20261107/review_packet/review.html).
   - Đệ trình phê duyệt phương án huấn luyện tinh chỉnh (fine-tuning) cho mô hình phát hiện bóng rổ nhằm khắc phục triệt để tỷ lệ 40.3% thời lượng mất dấu bóng của raw detector.

