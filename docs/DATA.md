# Đặc tả Cấu trúc & Định dạng Dữ liệu (Data Specification)

Tài liệu quy định chi tiết cấu trúc, lược đồ (schema) và quy ước định dạng cho toàn bộ dữ liệu đầu vào và các artifact đầu ra trong pipeline phân tích bóng rổ.

---

## 1. Dữ liệu Đầu vào (Inputs)

### 1.1. Video Nguồn (`input.mp4`)
- **Định dạng container:** MPEG-4 (.mp4).
- **Video Codec:** H.264 / AVC (Advanced Video Coding), tương thích phát trực tiếp trên trình duyệt qua HTML5 Video.
- **Pixel Format:** YUV420p.
- **Kích thước ảnh:** Hệ thống sử dụng độ phân giải của video nguồn. Demo HCM1–HN1 dùng ảnh 1038 × 480.
- **Tốc độ khung hình:** Video có thể dùng tốc độ cố định hoặc thay đổi. Pipeline dùng dấu thời gian của nguồn để đồng bộ kết quả.

### 1.2. Cấu hình Đội hình & Danh tính (`roster.json`)
Lưu trữ thông tin hai đội bóng, màu áo đồng phục dùng để trích xuất màu sắc và danh sách cầu thủ phục vụ nhận diện số áo OCR.

```json
{
  "team_a_id": "team_a",
  "team_b_id": "team_b",
  "team_a_name": "UB",
  "team_b_name": "Ulaanbaatar MMC Energy",
  "team_a_color_rgb": [200, 25, 35],
  "team_b_color_rgb": [235, 210, 30],
  "provenance_status": "user_configured",
  "team_assignment_enabled": true,
  "players": [
    {
      "player_id": "team_a_jersey_1",
      "team_id": "team_a",
      "jersey_number": "1",
      "name": "Enkhbaatar Onolbaatar",
      "is_active": true,
      "aliases": []
    },
    {
      "player_id": "team_b_jersey_3",
      "team_id": "team_b",
      "jersey_number": "3",
      "name": "Strahinja Stojacic",
      "is_active": true,
      "aliases": []
    }
  ]
}
```

### 1.3. Cấu hình Hiệu chuẩn & Thiết lập Trận đấu (`match_config.json`)
Định nghĩa thể thức sân, chế độ hình học, các đoạn hiệu chuẩn thủ công và các khoảng gán danh tính người dùng:

```json
{
  "version": 1,
  "format": "3x3",
  "geometry_mode": "legacy_manual",
  "classify_teams": true,
  "source_sha256": "ae83eb316347e0925263c93ca00d8a145ebbc961857415904ffd7fd049c1d99e",
  "width": 1920,
  "height": 1080,
  "fps": 60.0,
  "roster": { "...": "Cấu trúc RosterConfig" },
  "segments": [
    {
      "start_s": 0.0,
      "end_s": 1397.75,
      "anchor_s": 0.0,
      "points": [
        {"image": [575.0, 597.0], "court": [-2.45, 0.0]},
        {"image": [981.0, 522.0], "court": [2.45, 0.0]},
        {"image": [927.0, 789.0], "court": [-2.45, 5.8]},
        {"image": [1383.0, 647.0], "court": [2.45, 5.8]},
        {"image": [1184.0, 709.0], "court": [0.0, 5.8]}
      ],
      "max_residual_px": 0.085
    }
  ],
  "assignments": [
    {
      "track_id": "trk_default_0003",
      "role": "player",
      "player_id": "team_a_jersey_1",
      "team_id": "team_a",
      "start_s": 0.0,
      "end_s": 3.866667
    }
  ],
  "exclusions": []
}
```

---

## 2. Dữ liệu Đầu ra & Artifacts (Outputs)

Các tệp được lưu trữ theo từng công việc (job) trong `codebase/outputs/web-uploads/<job_id>/`:

| Tệp tin | Định dạng | Mục đích |
|---|---|---|
| `job.json` | JSON | Trạng thái công việc, số frame đã xử lý, FPS, duration, sha256 nguồn. |
| `analysis/run.json` | JSON | Tổng hợp báo cáo kỹ thuật, cấu hình runtime, thời gian các bước và metadata video. |
| `analysis/detections.jsonl` | JSON Lines | Danh sách các đối tượng nhận diện trên từng khung hình nguồn. |
| `analysis/tracked_observations.jsonl` | JSON Lines | Chuỗi quan sát chuyển động của từng thực thể qua thời gian. |
| `analysis/automatic_geometry.json` | JSON | Dòng thời gian ma trận Homography tự động và các điểm cắt cảnh. |
| `analysis/web_overlay.json` | JSON | Dữ liệu bounding box lấy mẫu tần số 5 Hz phục vụ vẽ lớp phủ canvas trên video. |
| `spatial_map.json` | JSON | Mô hình không gian 2D đầy đủ: tọa độ mét, lưới heatmap và khoảng phân bố. |
| `spatial_map_status.json` | JSON | Manifest trạng thái và mã băm revision của bản đồ sân. |

---

## 3. Chi tiết Schema các Tệp Dữ liệu Lõi

### 3.1. Detections Stream (`detections.jsonl`)
Mỗi dòng đại diện cho một khung hình, xuất hiện liên tục không đứt đoạn (kể cả frame không có đối tượng nào):

```json
{
  "video_id": "input",
  "frame_index": 0,
  "source_time_s": 0.0,
  "original_wh": [1920, 1080],
  "raw_pts": 0,
  "time_base": "1/15360",
  "timestamp_status": "valid",
  "timestamp_policy": "pts_normalized",
  "model_call_ms": 182.4,
  "detections": [
    {
      "xyxy": [589.5, 318.0, 996.0, 1078.5],
      "class_id": 1,
      "class_name": "human",
      "confidence": 0.9078
    },
    {
      "xyxy": [513.0, 357.0, 604.5, 438.0],
      "class_id": 0,
      "class_name": "ball",
      "confidence": 0.8251
    }
  ]
}
```

### 3.2. Tracked Observations (`tracked_observations.jsonl`)
Lưu giữ toàn bộ chuỗi quan sát thực thể sau khi lọc và liên kết chuyển động:

```json
{
  "observation_id": "obs_0000000001",
  "track_id": "trk_default_0003",
  "frame_index": 12,
  "source_time_s": 0.2,
  "segment_id": "default",
  "camera_id": "cam0",
  "sample_type": "observed",
  "role": "player",
  "team_id": "team_a",
  "player_id": "team_a_jersey_1",
  "bbox": [1122.0, 348.0, 1531.5, 1018.5],
  "footpoint_image": [1326.75, 1018.5],
  "confidence": 0.895,
  "timestamp_status": "valid",
  "source_fingerprint_sha256": "ae83eb316347e0925263c93ca00d8a145ebbc961857415904ffd7fd049c1d99e"
}
```
- `sample_type`:
  - `"observed"`: Thực thể phát hiện trực tiếp từ model detector.
  - `"predicted"`: Thực thể nội suy động học trong khoảng thời gian mất dấu ngắn (dưới 1 giây).

### 3.3. Web Overlay (`web_overlay.json`)
Tệp tối ưu dung lượng cho web dashboard, lấy mẫu ở tần số 5 Hz (mỗi 0.2 giây một khung hình):

```json
{
  "frames": [
    {
      "time": 0.2,
      "boxes": [
        {
          "box": [1122.0, 348.0, 1531.5, 1018.5],
          "id": "trk_default_0003",
          "continuity_start_s": 0.0,
          "sample_type": "observed",
          "team_id": "team_a",
          "player_id": "team_a_jersey_1"
        },
        {
          "box": [907.5, 264.0, 969.0, 333.0],
          "kind": "rim"
        }
      ]
    }
  ]
}
```

### 3.4. Mô hình Không gian & Heatmap (`spatial_map.json`)
Lưu trữ toàn bộ tọa độ trên mặt sân 2D và lưới heatmap:

- **Hệ tọa độ sân chuẩn FIBA 3×3:**
  - Gốc tọa độ `(0, 0)` đặt tại tâm đường biên cuối sân (baseline) ngay dưới chân rổ.
  - Trục hoành $X \in [-7.5, 7.5]$ mét (chiều rộng sân 15 mét).
  - Trục tung $Y \in [0.0, 11.0]$ mét (chiều dài sân thi đấu 3×3).
  - Kích thước ô lưới heatmap: $0,25 \times 0,25$ mét (tạo thành ma trận $44 \times 60$ ô).
- **Cấu trúc trường `quality`:**
  - `observations`: Tổng số lượt quan sát đầu vào.
  - `observed`: Số quan sát trực tiếp.
  - `projectable`: Số quan sát chiếu hợp lệ lên mặt sân.
  - `projection_fraction`: Tỷ lệ chiếu thành công (`projectable / observed`).
  - `speed_outlier_intervals`: Số khoảng nhảy vận tốc bất thường (> 12 m/s).
  - `identity_overlap_seconds`: Số giây trùng lặp danh tính (phải bằng 0.0 sau khi lọc).
- **Cấu trúc trường `heatmap_intervals`:** Mảng chứa các bộ 7 phần tử `[start_s, end_s, row_idx, col_idx, track_id, team_id, player_id]` để lọc dữ liệu theo khoảng thời gian trên giao diện.
