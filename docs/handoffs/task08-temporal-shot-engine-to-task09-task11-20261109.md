# Bàn Giao Kỹ Thuật: Từ Temporal Shot Engine Sang Task09 (Rebound / Possession) & Task11 (Event Ledger)

**Ngày bàn giao:** 2026-11-09  
**Người bàn giao:** Senior AI/Python Engineer (Task08 Temporal Shot Engine)  
**Trạng thái Task07:** `IN_PROGRESS` (Detector background fine-tuning tiếp tục duy trì trạng thái kiểm soát).  
**Trạng thái Task08:** `IN_PROGRESS` (Pha Động cơ Ném bóng Chuỗi thời gian đã hoàn tất; mã nguồn, kiểm thử, artifacts và negative cohort đã sẵn sàng bàn giao).  
**Tài liệu tham chiếu:**
- [Báo Cáo Kỹ Thuật Động Cơ Ném Bóng Chuỗi Thời Gian](../reports/task08-temporal-shot-engine.md)
- [Báo Cáo Baseline Chẩn Đoán Task08](../reports/task08-critical-moments-baseline.md)
- Artifacts thư mục: [`codebase/outputs/task08-temporal-engine-20261109/`](file:///c:/Users/Admin/OneDrive%20-%20National%20Economics%20University/Documents/object%20tracking/codebase/outputs/task08-temporal-engine-20261109/)

---

## 1. Mục Đích Bàn Giao

Tài liệu này chuẩn hóa giao diện dữ liệu (data contract), các sự kiện đầu ra tự động, và các điều kiện kích hoạt giữa **Task08 (Temporal Shot & Points Engine)** với:
1. **Task09:** Module phát hiện Rebound (Bóng bật bảng/vành), Turnover (Mất bóng), và Assist (Kiến tạo).
2. **Task11:** Hệ thống sổ cái sự kiện thống nhất (Unified Event Ledger) và Multimodal Adjudication.

---

## 2. Tài Sản Mã Nguồn & Cấu Trúc Hợp Đồng Bàn Giao

### 2.1 Các Modules Đã Triển Khai & Kiểm Thử
- [shots.py](file:///c:/Users/Admin/OneDrive%20-%20National%20Economics%20University/Documents/object%20tracking/codebase/src/basketball_scoreboard/shots.py):
  * `TemporalShotFSM`: Máy trạng thái hữu hạn 4 pha (`READY -> RELEASE -> FLIGHT_ARC -> OUTCOME (BASKET | MISS)`).
  * `RimApertureGeometry`: Quản lý hình học khẩu độ vành rổ, dải vào trên ($y \le y_1 + 0.35 h$), dải thoát dưới ($y \ge y_{\text{center}}$), và giới hạn ngang.
  * `ShotCandidateRecord`: Bản ghi dữ liệu cú ném chuẩn hóa.
- [points.py](file:///c:/Users/Admin/OneDrive%20-%20National%20Economics%20University/Documents/object%20tracking/codebase/src/basketball_scoreboard/points.py):
  * `BoundedShooterHistoryResolver`: Truy tìm danh tính cầu thủ nhân quả trong $[t_{\text{release}} - 2.0\text{s}, t_{\text{release}}]$ và phân cụm màu áo dự phòng cấp đội (`team_a` / `team_b`).
  * `PointsEngine`: Xử lý giá trị điểm FIBA 3x3 (1pt / 2pt) và quản lý sổ cái điểm bất biến (idempotent ledger).
- **Bộ kiểm thử toàn diện:**
  * [test_task08_temporal_shot_engine.py](file:///c:/Users/Admin/OneDrive%20-%20National%20Economics%20University/Documents/object%20tracking/codebase/tests/test_task08_temporal_shot_engine.py): 10 unit tests kiểm thử chuỗi thời gian, từ chối nảy bóng, từ chối bóng đi từ dưới lên, chống lặp điểm replay, và gán đội dự phòng.

---

## 3. Giao Diện Handoff Cho Task09 (Rebound / Possession / Assist)

Khi một cú ném không thành bàn thắng hoặc chạm vành/bảng, Task08 không tự ý gán chỉ số rebound cho cầu thủ, mà phát tín hiệu chuyển pha cho Task09:

### 3.1 Dữ Liệu Miss Event & Rebound Window Handoff
Mỗi khi FSM kết luận `phase == ShotPhase.MISS`, bản ghi `ShotCandidateRecord` cung cấp:
- `outcome_time_s`: Thời điểm bóng va chạm vành rổ hoặc đập bảng và bật ra.
- `outcome_frame_idx`: Số khung hình tương ứng.
- `reason_codes`: Gồm `rim_bounce_upward_deflection` (chạm vành nảy lên) hoặc `wide_rim_miss_descending_outside_aperture` (trượt vành rơi xuống).
- `evidence_details`: Tọa độ rổ, độ cao bóng tại thời điểm bật ra.

```json
{
  "shot_id": "shot_play_001_0001",
  "outcome": "miss",
  "phase": "miss",
  "release_time_s": 138.967,
  "outcome_time_s": 139.467,
  "shooter_track_id": "trk_play_001_0005",
  "shooter_team_id": "team_b",
  "attribution_level": "team",
  "reason_codes": ["rim_bounce_upward_deflection"],
  "evidence_details": {
    "is_miss": true,
    "reason": "rim_bounce_upward_deflection"
  }
}
```

### 3.2 Khởi Đầu Cửa Sổ Phân Tích Rebound Trong Task09
- **Cửa sổ Rebound bắt đầu:** Tại $t_{\text{start}} = \text{shot.outcome\_time\_s}$.
- **Cửa sổ kết thúc:** Khi có cầu thủ kiểm soát bóng ổn định ($t \le t_{\text{start}} + 3.0\text{s}$) hoặc bóng chết / ra ngoài biên.
- **Phân loại Rebound:**
  * *Offensive Rebound (Tấn công):* Nếu cầu thủ bắt bóng có `team_id == shot.shooter_team_id`.
  * *Defensive Rebound (Phòng thủ):* Nếu cầu thủ bắt bóng có `team_id != shot.shooter_team_id`.

### 3.3 Khởi Đầu Cửa Sổ Phân Tích Assist (Kiến Tạo)
Khi một cú ném được xác nhận `outcome == "made"`:
- Task09 truy vết đường chuyền (pass event) trong khoảng $[t_{\text{release}} - 4.0\text{s}, t_{\text{release}}]$.
- Cầu thủ thực hiện đường chuyền trực tiếp cho `shooter_track_id` dẫn đến bàn thắng mà không bị ngắt quyền kiểm soát sẽ được đề xuất gán chỉ số Kiến tạo (Assist).

---

## 4. Giao Diện Handoff Cho Task11 (Unified Event Ledger)

Task11 tiếp nhận các luồng sự kiện đa phương thức (detector, scoreboard, whistle, commentary) và duy trì sổ cái đồng thuận:

### 4.1 Hợp Đồng Bản Ghi Điểm (`PointEventRecord`)
Định dạng JSON chuẩn xuất xưởng tại `candidate_c/points_auto.jsonl`:
```json
{
  "event_id": "score_play_003_0001",
  "shot_id": "shot_play_003_0001",
  "video_id": "play_003",
  "source_time_s": 165.8,
  "confirmation_time_s": 165.8,
  "status": "auto_confirmed",
  "scoring_team_id": "team_b",
  "scoring_player_id": null,
  "attribution_level": "team",
  "point_value": 1,
  "value_reason": "fiba_3x3_1pt_inside_arc",
  "evidence_refs": {
    "shot_evidence": {
      "is_made": true,
      "v_y": 39.53,
      "delta_y": 97.5,
      "delta_t": 2.467,
      "observed_samples_near_rim": 58,
      "decel_ratio": 14.144,
      "net_cue_passed": true
    },
    "history_evidence": {
      "query_window_s": [163.167, 165.167],
      "target_track_id": "trk_play_003_0002",
      "ocr_readings_evaluated": 0,
      "team_observations_evaluated": 61,
      "candidate_votes": {},
      "team_votes": {
        "team_a": 0.0,
        "team_b": 50.96
      }
    }
  },
  "is_idempotent": true,
  "revision": 1
}
```

### 4.2 Nguyên Tắc Đồng Thuận & Tinh Chỉnh (Refinement Protocol)
1. **Idempotency Key:** `event_id` được sinh theo mẫu `score_{video_id}_{counter:04d}` và liên kết cứng với `shot_id`.
2. **Không ghi trùng điểm (No Double Counting):** Nếu một tác vụ sau đó (ví dụ OCR nâng cao hoặc trọng tài xem lại) xác định được số áo của cầu thủ ghi điểm, Task11 **phải cập nhật trường `scoring_player_id` trên bản ghi hiện có** với `revision = revision + 1`, tuyệt đối không phát hành thêm một sự kiện tính điểm mới làm sai lệch tỷ số trận đấu.
3. **Phân Định Cấp Độ Bằng Chứng (Attribution Confidence Hierarchy):**
   * `attribution_level = "player"`: Đã có độ đồng thuận OCR số áo và kiểm tra đối chiếu roster 2 đội.
   * `attribution_level = "team"`: Chỉ có bằng chứng màu áo; an toàn để cập nhật tỷ số trận đấu nhưng chưa ghi stat cá nhân.
   * `attribution_level = "unknown"`: Đang tranh chấp; giữ điểm tạm thời ở trạng thái provisional.

---

## 5. Danh Sách Kiểm Tra Khi Tiếp Nhận (Checklist For Receiver)

- [x] Đã kiểm tra 10/10 unit tests chuỗi thời gian chạy đạt: `test_task08_temporal_shot_engine.py`.
- [x] Đã bảo lưu toàn bộ artifacts của Baseline chẩn đoán tại `codebase/outputs/task08-critical-baseline-20261108/`.
- [x] Đã xác nhận tập đối chứng âm bản 30 tình huống tại `codebase/outputs/task08-temporal-engine-20261109/negative_cohort/negative_manifest.json` đạt $100\%$ Specificity.
- [x] Tiến trình huấn luyện fine-tune YOLO26s tại `codebase/outputs/task07a-finetune-20261108/` được giữ nguyên vẹn, không bị tác động.
- [x] Trạng thái Task07 và Task08 giữ đúng quy ước: **`IN_PROGRESS`**.

