# Báo Cáo Chuẩn Bị Acceptance Package Cho Task07C — Đánh Giá Mức Độ Sẵn Sàng (Readiness)

Ngày: 2026-11-08.  
Trạng thái tổng thể: **CHƯA ĐỦ ĐIỀU KIỆN NGHIỆM THU (ACCEPTANCE BLOCKED). Task07 tiếp tục IN_PROGRESS.**  
Báo cáo này phân định rạch ròi 3 trục: **Sẵn sàng Tooling**, **Sẵn sàng Dữ liệu** và **Sẵn sàng Candidate**, dựa trên dữ liệu và quyền truy cập hiện hữu trong kho mã nguồn.

---

## 1. Tóm Tắt Đánh Giá Mức Độ Sẵn Sàng (Readiness Summary)

| Trục Đánh Giá | Trạng Thái | Kết Quả Chi Tiết & Bằng Chứng |
|---|:---:|---|
| **1. Tooling Readiness (Bộ công cụ)** | <span style="color:green;font-weight:bold">READY</span> | Toàn bộ 309 unit/regression tests PASS. Bộ evaluator độc lập (`possession_evaluation.py`), script đánh giá (`evaluate_ball_possession.py`), công cụ chẩn đoán truy nguyên lỗi 7 tầng (`trace_task07b_control_failures.py`), và các integrity guards (chặn predicted-only control, pass crossing cut, sai số PTS $\le 2\mu\text{s}$) hoạt động chính xác và tuân thủ nghiêm ngặt protocol đã duyệt. |
| **2. Data Readiness (Dữ liệu & Nhãn)** | <span style="color:red;font-weight:bold">BLOCKED</span> | Tập development có GT đã duyệt v2 (`reviewed-vt_development-v2.json`) nhưng đã bị dùng để tune. Tập validation đề xuất (`vt_validation`) **CHƯA CÓ NHÃN ĐÃ DUYỆT** (tệp `annotations-draft.json` có `review_status: draft`, 0 khoảng kiểm soát, 0 đường chuyền). Ngoài ra, không có GT quỹ đạo bounding box cầu thủ liên tục từng frame trên toàn bộ các phân đoạn. |
| **3. Candidate Readiness (Thuật toán)** | <span style="color:red;font-weight:bold">BLOCKED</span> | Candidate hiện hành (`--team-crop-region jersey --reset-on-team-conflict`) trên tập development GT chỉ đạt: **Ball observed recall = 50.00%** (ngưỡng duyệt $\ge 90\%$), **Strict controller accuracy = 0.0%** (ngưỡng duyệt $\ge 90\%$), **Strict pass recall = 0.0%** (ngưỡng duyệt $\ge 90\%$). Kết quả trả về `failed_criteria`. |

**Kết luận chuẩn bị:** Toàn bộ harness, manifest, kịch bản chạy, checklist kiểm tra và gói review bổ sung đã sẵn sàng độc lập. Tuy nhiên, **chưa đủ điều kiện kích hoạt nghiệm thu Task07C** do dữ liệu validation chưa có nhãn được duyệt và độ chính xác của candidate chưa đạt ngưỡng.

---

## 2. Kiểm Tra Nguồn Video, Quyền Truy Cập, Exposure và Policies

### 2.1. Kiểm Kê Toàn Bộ Nguồn Video Trong Repository

| Video / Asset ID | Đường dẫn & SHA-256 | Độ phân giải, FPS, Thời lượng | Exposure & Lịch sử sử dụng | Quyền truy cập & Chính sách |
|---|---|---|---|---|
| **`vietnam-tonga.mp4`** (Parent) | `codebase/assets_test/vietnam-tonga.mp4`<br>`1443c1d263c8037a5684f3dbc0ef9216beb5097d9a47c4c1c9b94d1363e26865` | 1920×1080<br>30.0 FPS<br>23 phút (1.38 GB) | Trận đấu phát sóng Việt Nam vs Tonga. Người dùng đã phê duyệt cắt các đoạn 30s–60s và duyệt danh sách roster `vietnam_tonga.json`. | Đã được cấp quyền sử dụng cho pilot theo các đoạn 30s. |
| **`vt_development.mp4`** (Segment 1) | `codebase/outputs/task07-vietnam-tonga-segments-20261104/media/vt_development.mp4`<br>`8fd370b0668860a5c70d56bf256c76e3783bc1fe6598b529944ad00ca0616b45` | 1920×1080<br>30.0 FPS<br>30.0s (900 frames)<br>Parent: 05:00–05:30 | **100% EXPOSED (Tuned).** Dùng xuyên suốt Task07, 07A, 07B để tune spatial ROI, color thresholds, crop guards và actor decoupling. | Đã có GT canonical duyệt v2 (`reviewed-vt_development-v2.json`). Camera policy: `vt_development-policy-ball-roi-v4.json`. |
| **`vt_validation.mp4`** (Segment 2) | `codebase/outputs/task07-vietnam-tonga-segments-20261104/media/vt_validation.mp4`<br>`88b6f9ce44feed84cb2a2b1fcc6b98d1a88fe38c1b16a6212682f5fa96c41544` | 1920×1080<br>30.0 FPS<br>30.0s (900 frames)<br>Parent: 02:45–03:15 | **VISUALLY INSPECTED.** Đã xem output vào ngày 2026-11-04 (`validation-exposure.json`) để triage lỗi màu và ROI. Cùng trận đấu với development. **Không phải independent holdout.** | Đã có video decode, detection tiled cache, và exclusion policy `vt_validation-policy-masked.json`. **Chưa có GT đã duyệt.** |
| **`clip04`** | `codebase/assets_test/2aOboR9Z2NjQ1XP8HgYdKMG7VVzS44zOdTVVjB5s.mp4`<br>`ae789418b89cfcf868a546eb0a5ce502497bb6d2b61af252978038d7cf8af3c4` | 1038×480<br>25.32 FPS<br>17.65s (447 frames) | U18 3x3 Tournament broadcast. Người dùng đã cho phép chạy development ngày 2026-11-04 (`task07-clip04.json`), ghi nhận exposure cho cả nhóm `clip04–07`. | Đã cấp quyền chạy qua file authorization. Dùng roster giả lập. |
| **`clip05` – `clip07`** | `clip05`: `c22c4cd8...`<br>`clip06`: `da95d00d...`<br>`clip07`: `56437c05...` | 1038×480<br>~25.3 FPS<br>20s–48s | Thuộc cùng giải đấu U18 với `clip04`. Đã ghi nhận group exposure ngày 2026-11-04. | Bị hạn chế bởi cơ chế **default-deny** trong CLI. Chưa có phê duyệt mở khóa riêng. Chưa có GT Task07. |
| **`clip01` – `clip03`** | `clip01`: `c8e1ac7c...` (đêm)<br>`clip02`: `3ed25e1b...` (ngày solo)<br>`clip03`: `affa3105...` (moving cam) | Độ phân giải cao (UHD 4K)<br>18s–28s | Được sử dụng trong Task01 smoke test và Task05 calibration. | `clip01`/`clip03` không đủ điều kiện cho fixed ROI. `clip02` là calibration split cho rổ/hoop scoring. |

### 2.2. Xác Định Bộ Validation Chưa Dùng Để Tuning
- **Hiện trạng thực tế:** Phân đoạn `vt_validation.mp4` là ứng viên validation duy nhất được định nghĩa trong protocol pilot `task07_vietnam_tonga.json`. Tuy nhiên:
  1. Phân đoạn này nằm trong cùng một video nguồn/trận đấu với phân đoạn `vt_development`.
  2. Ngày 2026-11-04, output của phân đoạn này đã được mở để kiểm tra trực quan (triage) và điều chỉnh vùng mask/ROI (ghi rõ tại `codebase/outputs/task07-vietnam-tonga-segments-20261104/validation-exposure.json`).
  3. **Cam kết tuân thủ:** Báo cáo này tuyệt đối **không gọi `vt_validation` là independent holdout**. Nó được xác định chính xác là **same-match diagnostic pilot**.
  4. Trong repository hiện tại, **hoàn toàn chưa có một tập dữ liệu kiểm thử độc lập (untouched independent match test)** có nhãn Task07 đã được duyệt.

---

## 3. Kiểm Tra Tính Đầy Đủ Của Ground Truth

### 3.1. Đối Chiếu Ground Truth Phân Đoạn Development (`reviewed-vt_development-v2.json`)
- **Ball Samples:** 108 mẫu, trong đó có 72 mẫu nằm trong vùng coverage hợp lệ (đáp ứng tiêu chuẩn tối thiểu $\ge 60$ mẫu bóng nhìn thấy của protocol).
- **Control Intervals:** 8 khoảng kiểm soát (tổng thời lượng 14.30s hợp lệ, xác định rõ team_id và player_id). Đáp ứng điều kiện mẫu kiểm soát $> 0\text{s}$.
- **Passes:** 5 đường chuyền hoàn thành (xác định rõ release/receive, passer và receiver). Đáp ứng tiêu chuẩn tối thiểu $\ge 5$ passes.
- **Actor Identity Trajectory:** **KHÔNG CÓ (N/A).** GT không chứa bounding box hoặc track trajectory của cầu thủ theo từng frame. Do đó, chỉ số continuous trajectory identity không thể đo lường.

### 3.2. Đối Chiếu Ground Truth Phân Đoạn Validation (`annotations-draft.json`)
- **Ball Samples:** 94 mẫu dự thảo sinh từ HSV, chưa được reviewer xác nhận (`reviewed: false`, `uncertain: true`).
- **Control Intervals:** **0 khoảng kiểm soát (Hoàn toàn trống).**
- **Passes:** **0 đường chuyền (Hoàn toàn trống).**
- **Review Metadata:** `review_status: "draft"`, `reviewer: null`.
- **Hành vi Tooling:** Khi chạy `evaluate_ball_possession.py`, bộ đánh giá kích hoạt kiểm tra nghiêm ngặt tại `possession_evaluation.py` (L56–58):
  ```python
  if not synthetic and (packet.get("review_status") != "approved" or not packet.get("reviewer")):
      raise ValueError("Reviewed GT and approved protocol required")
  ```
  Hệ thống lập tức **từ chối đánh giá** với lỗi `ValueError`.
- **Tuân thủ đạo đức dữ liệu:** Chúng tôi tuyệt đối **không sửa metadata thành `approved`** và **không tự điền đáp án/suy đoán nhãn từ output của model**.

---

## 4. Acceptance Manifest & Tiêu Chuẩn Protocol Đã Duyệt

Acceptance manifest chuẩn tắc đã được khởi tạo độc lập tại:  
[`codebase/outputs/task07c-acceptance-package-20261107/acceptance_manifest.json`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task07c-acceptance-package-20261107/acceptance_manifest.json)

### 4.1. Bảng Băm Tính Toàn Vẹn Của Các Thành Phần Tham Chiếu

| Thành phần | Đường dẫn tệp tin | Mã băm SHA-256 |
|---|---|---|
| **Parent Video** | `codebase/assets_test/vietnam-tonga.mp4` | `1443c1d263c8037a5684f3dbc0ef9216beb5097d9a47c4c1c9b94d1363e26865` |
| **Validation Video** | `codebase/outputs/task07-vietnam-tonga-segments-20261104/media/vt_validation.mp4` | `88b6f9ce44feed84cb2a2b1fcc6b98d1a88fe38c1b16a6212682f5fa96c41544` |
| **Development Video** | `codebase/outputs/task07-vietnam-tonga-segments-20261104/media/vt_development.mp4` | `8fd370b0668860a5c70d56bf256c76e3783bc1fe6598b529944ad00ca0616b45` |
| **Acceptance Profile** | `codebase/configs/evaluation/task07_vietnam_tonga.json` | `1a79aa9a6697b3eea63c9e07d53b9058ea927ce961e9f45f7396e6b7f51da097` |
| **Approved Roster** | `codebase/configs/rosters/vietnam_tonga.json` | `9b6cf63456076d51874d1846011ddb0321ad28a0a0c14cd7a20e9d6a5dc0163d` |
| **Ball Config** | `codebase/configs/ball-possession-vietnam-tonga-spatial.json` | `45120d972c122eaf9e8c7516199d13ed85cb15726299c20a6ae71410151a0412` |
| **Validation Policy** | `codebase/outputs/task07-vietnam-tonga-segments-20261104/vt_validation-policy-masked.json` | `5e913e7d45459132aa4b0bbc8d999c3874925bbb9e4a9e4b2c52b06b99701f99` |
| **Canonical Dev GT** | `codebase/data/matches/vietnam_tonga/reviewed-vt_development-v2.json` | `ee3f10d78164fe4d1b3301e80cb77896ddf3717fae87c45424721c068506b81d` |
| **Draft Val GT** | `codebase/outputs/task07-vietnam-tonga-segments-20261104/review-validation-final/annotations-draft.json` | `a39fb8c575a7c293630f9a764d84c3be9466ad505c2a1c0d4a9425ef42ba1594` |
| **Evaluator Core** | `codebase/src/basketball_scoreboard/possession_evaluation.py` | `0528e19253457dbba50c821360bb81e7d5a57007aa22a7620eb5a6f236058097` |
| **Evaluator CLI** | `codebase/scripts/evaluate_ball_possession.py` | `8c60cecf222e96d1163e72f3e9a7e3ca6f634ae76cb127bc9eb980e18585e510` |

### 4.2. Mẫu Số & Ngưỡng Nghiệm Thu Theo Protocol Đã Duyệt
1. **Ball Observed Recall:**
   - Mẫu số yêu cầu: $\ge 60$ mẫu bóng nhìn thấy (`minimum_visible_ball_samples: 60`).
   - Ngưỡng IoU: $\ge 0.30$. Ngưỡng recall đạt: $\ge 90\%$.
2. **Strict Controller Accuracy:**
   - Mẫu số yêu cầu: Thời lượng kiểm soát hợp lệ $> 0\text{s}$ (không tính khoảng `uncertain`).
   - Khớp strict: Bắt buộc đúng cả `player_id` và `team_id` của cầu thủ kiểm soát. Ngưỡng đạt: $\ge 90\%$.
3. **Strict Completed Pass:**
   - Mẫu số yêu cầu: $\ge 5$ đường chuyền hoàn thành (`minimum_completed_pass_gt: 5`).
   - Dung sai thời gian: $|\Delta t| \le 0.25\text{s}$ cho cả mốc release và receive.
   - Khớp strict: Đúng cả passer (`player_id`, `team_id`) và receiver (`player_id`, `team_id`).
   - Ngưỡng đạt: Precision $\ge 95\%$, Recall $\ge 90\%$.
4. **Integrity Guards (Bắt buộc 100%):**
   - Số frame xác nhận kiểm soát chỉ bằng bóng dự đoán (`prediction_only_control_frames`): **bằng 0**.
   - Số đường chuyền hoàn thành cắt qua ranh giới đổi cảnh (`completed_passes_crossing_cut`): **bằng 0**.
   - Độ lệch thời gian giải mã PTS (`max_pts_error_s`): **$\le 2\mu\text{s}$**.

---

## 5. Lệnh Chạy Thực Thi, Cấu Trúc Thư Mục và Checklists

### 5.1. Cấu Trúc Thư Mục Mới
Toàn bộ quy trình Task07C được cấu hình xuất ra thư mục chuyên biệt:
```
codebase/outputs/task07c-acceptance-package-20261107/
├── acceptance_manifest.json          # Bảng băm và tiêu chuẩn nghiệm thu
├── readiness_audit.json              # Kết quả audit tự động bằng tooling
├── review_packet/                    # Gói giao diện và hướng dẫn review bổ sung GT
│   ├── annotations-draft.json
│   ├── review.html
│   └── instructions.md
└── runs/                             # Thư mục đích cho các lệnh chạy (được bảo lưu)
    ├── validation-tracking/
    ├── validation-ball/
    ├── validation-evaluation/
    └── validation-trace/
```

### 5.2. Lệnh Chạy Chuẩn Tắc (Run Commands)

```powershell
# 1. Player Tracking trên tập validation (Candidate: jersey + team-conflict-reset)
codebase/.venv/Scripts/python.exe codebase/scripts/track_players.py `
  --detections codebase/outputs/task07-vietnam-tonga-segments-20261104/validation-tiled/detections.jsonl `
  --run-json codebase/outputs/task07-vietnam-tonga-segments-20261104/validation-tiled/run.json `
  --roster-config codebase/configs/rosters/vietnam_tonga.json `
  --video codebase/outputs/task07-vietnam-tonga-segments-20261104/media/vt_validation.mp4 `
  --enable-ocr --ocr-upscale 3 --jersey-evidence-ttl-s 6 --color-method masked `
  --jersey-evidence-cache codebase/outputs/task07-vietnam-tonga-segments-20261104/validation-tracking-masked `
  --tracking-policy codebase/outputs/task07-vietnam-tonga-segments-20261104/vt_validation-policy-masked.json `
  --team-crop-region jersey --reset-on-team-conflict `
  --output-dir codebase/outputs/task07c-acceptance-package-20261107/runs/validation-tracking

# 2. Ball Possession Tracking (sử dụng cấu hình spatial chuẩn và xuất debug video / timeline)
codebase/.venv/Scripts/python.exe codebase/scripts/track_ball_possession.py `
  --detections codebase/outputs/task07-vietnam-tonga-segments-20261104/validation-tiled/detections.jsonl `
  --run-json codebase/outputs/task07-vietnam-tonga-segments-20261104/validation-tiled/run.json `
  --tracks codebase/outputs/task07c-acceptance-package-20261107/runs/validation-tracking/tracked_observations.jsonl `
  --tracking-run codebase/outputs/task07c-acceptance-package-20261107/runs/validation-tracking/run.json `
  --identity-mappings codebase/outputs/task07c-acceptance-package-20261107/runs/validation-tracking/identity_mappings.json `
  --exclusions codebase/outputs/task07-vietnam-tonga-segments-20261104/vt_validation-policy-masked.json `
  --config codebase/configs/ball-possession-vietnam-tonga-spatial.json `
  --video codebase/outputs/task07-vietnam-tonga-segments-20261104/media/vt_validation.mp4 `
  --output-dir codebase/outputs/task07c-acceptance-package-20261107/runs/validation-ball

# 3. Ball Possession Evaluation (kích hoạt sau khi GT validation được duyệt)
codebase/.venv/Scripts/python.exe codebase/scripts/evaluate_ball_possession.py `
  --run-dir codebase/outputs/task07c-acceptance-package-20261107/runs/validation-ball `
  --ground-truth codebase/data/matches/vietnam_tonga/reviewed-vt_validation-v1.json `
  --acceptance-profile codebase/configs/evaluation/task07_vietnam_tonga.json `
  --output-dir codebase/outputs/task07c-acceptance-package-20261107/runs/validation-evaluation `
  --diagnostic

# 4. Truy nguyên lỗi 7 tầng
codebase/.venv/Scripts/python.exe codebase/scripts/trace_task07b_control_failures.py `
  --run-dir codebase/outputs/task07c-acceptance-package-20261107/runs/validation-ball `
  --ground-truth codebase/data/matches/vietnam_tonga/reviewed-vt_validation-v1.json `
  --output-dir codebase/outputs/task07c-acceptance-package-20261107/runs/validation-trace
```

### 5.3. Checklist Kiểm Tra Toàn Vẹn Hệ Thống (Video/PTS/Cut/Gap/Replay)

- [x] **Video Container & Stream Check:**
  - Định dạng: MP4, H.264/AVC, 1920×1080 @ 30.0 FPS, 900 frames.
  - Khớp mã băm bit-for-bit SHA256 với danh sách `allowed_video_sha256` trong acceptance profile (`88b6f9ce44...` cho validation, `8fd370b06...` cho dev).
- [x] **PTS Monotonic & Alignment Check:**
  - Khớp thời gian với parent video: $t_{\text{parent}} = t_{\text{source}} + 165.0\text{s}$ cho validation ($+300.0\text{s}$ cho dev).
  - Sai số PTS giải mã $\le 2\mu\text{s}$ trên toàn bộ 900 frames. Thời gian tăng đơn điệu chặt chẽ.
- [x] **Cut Exclusions & Boundary State Check:**
  - Khoảng loại trừ vận hành được áp dụng: $t = 21.567\text{s} - 26.433\text{s}$ (cận cảnh khán giả).
  - Reset trạng thái qua ranh giới cắt cảnh: Ball track ID và Possession ID phải đóng và reset, không tạo completed pass cắt qua cut.
- [x] **Temporal Gap & Hypothesis Check:**
  - Khoảng mất dấu tối đa cho phép duy trì giả thuyết bóng bay $\le 100\text{ms}$ (`max_unobserved_gap_s: 0.10`). Nếu vượt quá, chuyển về trạng thái `unknown`.
  - Nghiêm cấm xác nhận kiểm soát (`confirmed control`) khi bóng đang ở trạng thái `predicted`.
- [x] **Replay Checksums & Cache Integrity Check:**
  - Replay chỉ sử dụng bằng chứng OCR local đã được xác minh (`replayed_verified_local_ocr_evidence`).
  - Kiểm tra tính tương thích giữa bounding box của track và cache OCR, từ chối mọi cache không trùng mã băm nguồn.

---

## 6. Gói Review Bổ Sung Nhãn Thiếu (Supplementary Review Packet)

Nhằm tuân thủ nguyên tắc không tự bịa đặt dữ liệu và không yêu cầu review lại các nội dung đã xác nhận, gói công cụ review bổ sung tập trung đã được thiết lập tại:  
[`codebase/outputs/task07c-acceptance-package-20261107/review_packet/`](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/codebase/outputs/task07c-acceptance-package-20261107/review_packet/)

Gói bao gồm:
1. **`review.html`:** Giao diện web tương tác trực tiếp với video `vt_validation.mp4`, cho phép reviewer tua từng frame ($\pm 1$), kiểm tra và điều chỉnh 94 mẫu bóng, gắn nhãn các khoảng kiểm soát bóng (start, end, player, team) và các đường chuyền (release, receive, passer, receiver).
2. **`annotations-draft.json`:** Tệp nhãn dự thảo sẵn sàng nạp vào giao diện để reviewer rà soát.
3. **`instructions.md`:** Hướng dẫn chi tiết từng bước, nêu rõ các ràng buộc kỹ thuật và giải thích vì sao các chỉ số validation chưa thể đo lường nếu thiếu bộ nhãn này.

---

## 7. Kết Luận Và Đề Xuất Hành Động Tiếp Theo

1. **Về mặt kỹ thuật và chuẩn bị:** Acceptance package cho Task07C đã hoàn tất 100% về mặt tooling, harness, manifest, checklists và tài liệu hướng dẫn.
2. **Về rào cản (Blockers) hiện tại:**
   - **Rào cản Dữ liệu:** Phân đoạn validation chưa có nhãn Ground Truth được duyệt. Không thể chạy nghiệm thu tự động khi thiếu GT hợp lệ.
   - **Rào cản Thuật toán:** Candidate hiện tại chưa đạt độ chính xác yêu cầu (ball recall 50%, strict control 0%, pass recall 0% trên tập development) do raw detector miss và thiếu số áo OCR.
3. **Đề xuất bước tiếp theo:**
   - Người dùng tiến hành review và ký duyệt bộ nhãn `annotations-draft.json` cho phân đoạn `vt_validation` thông qua giao diện `review.html` (hoặc ủy quyền kế hoạch rà soát).
   - Xem xét phê duyệt phương án huấn luyện tinh chỉnh (fine-tuning proposal) cho raw ball detector đã trình bày ở báo cáo Task07B để giải quyết triệt để nút thắt nhận diện bóng trước khi chạy freeze test chính thức.
   - **Duy trì Task07 ở trạng thái IN_PROGRESS.** Tuyệt đối không mở các holdout bị hạn chế (`clip05–clip07`) khi chưa có phê duyệt freeze chính thức.

