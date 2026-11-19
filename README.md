# Basketball Spatial Tracking & Analytics

Hệ thống phân tích thị giác máy tính và bản đồ sân 2D cho video bóng rổ, hoạt động 100% trên CPU (không yêu cầu GPU, không cần API key ngoài). Hệ thống cung cấp pipeline xử lý hoàn chỉnh từ nhận diện đối tượng, theo dõi cầu thủ, dựng bản đồ sân 3×3/5×5, phân tích danh tính đến trực quan hóa heatmap động trên nền web dashboard.

---

## Điểm nổi bật & Tính năng chính

- **Object Detection (YOLO26s ONNX CPU):** Nhận diện 3 lớp chuẩn thi đấu: `ball` (bóng), `human` (người) và `rim` (vành rổ) ở độ phân giải cạnh cực đại 1280 px.
- **Kinematic Player Tracking:** Thuật toán theo dõi chuyển động với mô hình vận tốc không đổi giảm chấn (damped constant-velocity) và quản lý vòng đời tường minh (`observed` vs `predicted`), chống gán nhầm khi che khuất (occlusion).
- **Phép chiếu sân 2D (Court Projection):**
  - **Tự động (Automatic 3×3):** Nhận diện vạch sân (lane 4.90 × 5.80 m, vòng 2 điểm, bán nguyệt không lỗi va chạm) qua `AutomaticCourtEstimator`, tự động xác định góc quay camera và ngắt phép chiếu khi chuyển cảnh.
  - **Hiệu chuẩn thủ công (Calibrated Segments):** Hỗ trợ nạp 5+ điểm tương ứng mặt sân qua ma trận Homography với sai số cực nhỏ (< 0.1 px).
- **Đồng bộ Overlay 5 Hz:** Lớp phủ bounding box bám sát hình ảnh nguồn ở nhịp 5 Hz (bước nhảy 0.2s), lọc mượt khi tua và dừng video.
- **Heatmap & Phân bố di chuyển:**
  - Lưới không gian độ phân giải 0,25 × 0,25 m theo chuẩn FIBA 3×3.
  - Thang đo thời lượng hiện diện tuyệt đối (giây trên mỗi ô) hoặc phần trăm.
  - Lọc động đa chiều: theo toàn trận, theo từng đội (`team_a`, `team_b`), theo từng cầu thủ (8 cầu thủ) hoặc theo khoảng thời gian tùy chọn `[start_s, end_s]`.
- **Dashboard Web cục bộ:** Giao diện điều khiển đầy đủ trên trình duyệt: video player H.264, canvas sân 2D với vị trí và vệt di chuyển (trails), công cụ sửa khoảng gán danh tính trực tiếp trên khung hình dừng.

---

## Kiến trúc Pipeline

```
                     ┌───────────────────────────────────┐
                     │          Video Nguồn MP4          │
                     │          (MP4 / H.264)           │
                     └─────────────────┬─────────────────┘
                                       │
                                       ▼
                     ┌───────────────────────────────────┐
                     │    1. Object Detection (ONNX)     │
                     │  Lớp: ball (0), human (1), rim (2)│
                     └─────────────────┬─────────────────┘
                                       │
                                       ▼
                     ┌───────────────────────────────────┐
                     │    2. Human Tracking & Lifecycle  │
                     │    Liên kết bbox & gán track_id   │
                     └────────┬─────────────────┬────────┘
                              │                 │
            ┌─────────────────┴─┐             ┌─┴─────────────────┐
            ▼                   │             │                   ▼
┌───────────────────────┐       │             │       ┌───────────────────────┐
│ 3. Team & Identity    │       │             │       │ 4. Court Registration │
│ Phân loại màu áo RGB  │       │             │       │ Phép chiếu Homography │
│ Đối chiếu số áo OCR   │       │             │       │ 3x3 Court Coordinate  │
└───────────┬───────────┘       │             │       └───────────┬───────────┘
            │                   │             │                   │
            └─────────────────┐ │             │ ┌─────────────────┘
                              ▼ ▼             ▼ ▼
                     ┌───────────────────────────────────┐
                     │  5. Spatial Map & Dynamic Heatmap │
                     │ Lưới 0.25m, 69.645+ intervals lọc │
                     └─────────────────┬─────────────────┘
                                       │
                                       ▼
                     ┌───────────────────────────────────┐
                     │   6. Interactive Web Dashboard    │
                     │   Video + Canvas 2D + Controller  │
                     └───────────────────────────────────┘
```

---

## Trải nghiệm Demo

Kho mã nguồn đi kèm clip HCM1–HN1 dài 48,07 giây. Lần đầu chạy `setup.bat`, trình cài đặt tải thêm demo toàn trận UB–Ulaanbaatar (~903 MB) từ GitHub Releases. Sau đó cả hai demo dùng được offline.

### 1. Demo đóng gói HCM1–HN1 (48 giây)
- **Tệp:** `codebase/demo/` (1.210 khung hình, 1038 × 480).
- **Nội dung:** Video, khung bao, roster hai đội, bản đồ sân 3×3 và heatmap cho các đoạn có hiệu chuẩn phù hợp.
- **Cách mở:** Chạy `run_demo.bat`, bấm **Xem mẫu** trên dashboard hoặc truy cập:
  ```
  http://127.0.0.1:8081/?job=9b441192d32c5495946707131ca103d3
  ```

### 2. Demo toàn bộ trận đấu 23 phút 18 giây (Full Match)
- **Dữ liệu thực tế:** 83.865 frame (1.397,75 giây, 60 FPS).
- **Quy mô xử lý:**
  - 635.297 detection hợp lệ (507.039 người, 59.695 bóng, 68.563 vành rổ).
  - 804.400 quan sát tracking (497.566 observed, 306.834 kinematic prediction) trên 2.299 track IDs.
  - 6.989 frame overlay đồng bộ 5 Hz.
  - 371.799 vị trí chiếu sân hợp lệ (tỷ lệ chiếu đạt **74,72%**).
  - Phân tích đầy đủ 8 cầu thủ của hai đội UB và Ulaanbaatar MMC Energy.
- **Cách mở:** Chạy `start_dashboard.bat` và bấm **Xem demo toàn trận**, hoặc mở địa chỉ sau:
  ```
  http://127.0.0.1:8081/?job=d21759aefdd948ff967fc5fe2dadd2a8
  ```

---

## Hướng dẫn Cài đặt & Khởi chạy

### Yêu cầu hệ thống
- Hệ điều hành: Windows 10 / 11 (64-bit).
- Python: **3.12 (64-bit)**.
- Git: Phiên bản 2.30 trở lên.
- Phần cứng: CPU x86_64 tối thiểu 4 nhân, 8 GB RAM (khuyến nghị 16 GB khi chạy full trận).

### Các bước cài đặt nhanh

Mở PowerShell tại thư mục làm việc và thực hiện:

```powershell
# 1. Clone repository
git clone https://github.com/triphung-git/basketball-object_tracking.git
cd basketball-object_tracking

# 2. Khởi tạo môi trường ảo và xác minh model
.\setup.bat

# 3. Khởi động Web Dashboard
.\start_dashboard.bat
```

> [!NOTE]
> `setup.bat` tạo môi trường ảo tại `codebase/.venv`, cài thư viện, kiểm tra mô hình và cài cả hai demo. Cần Internet trong lần cài đầu để tải thư viện và demo toàn trận. Lần chạy lại giữ các chỉnh sửa đã lưu của demo.

Mở trình duyệt tại địa chỉ: **`http://127.0.0.1:8081`** (hoặc `http://127.0.0.1:8080` nếu cổng 8081 đang bận).

---

## Hướng dẫn Sử dụng

### 1. Xem và Tương tác trên Dashboard

| Thao tác | Cách thực hiện trên giao diện |
|---|---|
| **Mở video demo** | Bấm nút **Xem mẫu** ở thanh điều khiển trên cùng. |
| **Phát và tua video** | Dùng thanh trượt thời gian hoặc phím cách (Space) để phát/dừng; phím mũi tên trái/phải để tua từng khung hình. Bounding box tự động đồng bộ theo thời gian thực. |
| **Lọc bản đồ sân** | Trong bảng **Sân và di chuyển**, chọn hiển thị: toàn bộ (`all`), theo đội (`team_a`, `team_b`), hoặc chọn riêng từng cầu thủ. |
| **Lọc thời gian heatmap** | Nhập mốc thời gian bắt đầu (`Từ giây`) và kết thúc (`Đến giây`) để xem mật độ di chuyển trong một hiệp hoặc một pha tấn công cụ thể. |
| **Chỉnh sửa khoảng gán** | Dừng video tại khung hình có cầu thủ cần sửa, bấm **Chọn box ở khung hình đang dừng**, nhấp chuột vào box trên video, chọn cầu thủ hoặc vai trò (`referee`, `non_player`), bấm **Áp dụng khoảng gán** và **Lưu thiết lập**. |

### 2. Phân tích Video Mới qua Dashboard
1. Bấm **Chọn video** và chọn tệp MP4 (chuẩn nén H.264).
2. Thiết lập thông tin hai đội: tên đội, mã màu áo RGB đại diện (chọn màu tương phản để thuật toán tự động phân loại đội).
3. Nhập danh sách cầu thủ theo cú pháp: `<số_áo>, <tên_cầu_thủ>` (mỗi dòng một cầu thủ).
4. Bấm **Lưu thiết lập**, sau đó bấm **Phân tích**. Hệ thống hiển thị tiến độ và số frame đã xử lý theo thời gian thực.

### 3. Phân tích qua Giao diện Dòng lệnh (CLI)

Chạy pipeline phân tích không cần giao diện web:

```powershell
# Phân tích video với hình học sân tự động và mở dashboard sau khi xong
.\run_demo.bat --mode video-analysis --video "D:/videos/match.mp4" --output "codebase/outputs/match-run" --serve --open-browser

# Phân tích với cấu hình hiệu chuẩn sân thủ công và danh sách đội hình
.\run_demo.bat --mode video-analysis --video "D:/videos/match.mp4" --output "codebase/outputs/match-run" --court "codebase/configs/courts/ub_ulaanbaatar_court.json" --roster "codebase/configs/rosters/sample_roster.json"
```

---

## Cấu trúc Thư mục Dự án

```
basketball-object_tracking/
├── codebase/
│   ├── configs/courts/          # Cấu hình kích thước và tọa độ sân (3x3, 5x5)
│   ├── demo/                    # Bundle demo 14s chuẩn (video, run.json, geometry, overlay)
│   ├── models/                  # Checksum manifest và trọng số detector ONNX
│   │   └── detector/            # File weights.onnx đã được phê duyệt
│   ├── outputs/web-uploads/     # Thư mục lưu trữ các job phân tích cục bộ
│   ├── scripts/                 # Entrypoints: run_dashboard.py, run_spatial_pipeline.py, track_players.py
│   ├── src/basketball_scoreboard/
│   │   ├── app.py               # Quản lý pipeline chính và điều phối decode
│   │   ├── automatic_court.py   # Nhận diện đường sân 3x3 và ước lượng homography tự động
│   │   ├── dashboard.py         # HTTP Server, REST APIs và video streaming byte-range
│   │   ├── detector.py          # Wrapper suy luận YOLO26s ONNX CPU
│   │   ├── players.py           # Quản lý track, vận tốc và vòng đời thực thể
│   │   ├── spatial_analysis.py  # Dựng bản đồ tọa độ sân và tích hợp heatmap
│   │   ├── spatial_intervals.py # Thuật toán xử lý khoảng thời gian và giải quyết xung đột danh tính
│   │   ├── match_dashboard.js   # Logic hiển thị và điều khiển dashboard frontend
│   │   ├── overlay_playback.js  # Đồng bộ bounding box theo đồng hồ video
│   │   └── spatial_playback.js  # Nội suy và hiển thị tọa độ trên canvas sân
│   └── tests/                   # Bộ kiểm thử hồi quy unit test & JavaScript
├── docs/
│   ├── USER_GUIDE.md            # Sổ tay hướng dẫn chi tiết người dùng
│   ├── DATA.md                  # Quy cách định dạng schema JSON và JSONL
│   └── RESOURCES.md             # Xuất xứ mô hình, hash checksum và tài nguyên
├── run_demo.bat                 # Script chạy nhanh pipeline phân tích CLI
├── setup.bat                    # Script cài đặt môi trường và kiểm tra model
└── start_dashboard.bat          # Script khởi chạy web dashboard cục bộ
```

---

## Kiểm thử & Xác thực Hồi quy

Dự án duy trì bộ kiểm thử tự động cho cả tầng thuật toán Python và tầng trình diễn giao diện JavaScript:

```powershell
# Chạy bộ test hồi quy đồng bộ khung hình và phát lại không gian (Node.js)
node codebase/tests/overlay_playback_regressions.cjs
node codebase/tests/spatial_playback_regressions.cjs

# Chạy kiểm thử tự động toàn bộ pipeline Python (PyTest)
.\codebase\.venv\Scripts\python.exe -m pytest codebase/tests/test_run_spatial_pipeline.py codebase/tests/test_automatic_pipeline.py codebase/tests/test_spatial_analysis.py -q
```

---

## Tài liệu Kỹ thuật Chi tiết

- [Sổ tay Hướng dẫn Người dùng (User Guide)](docs/USER_GUIDE.md): Chi tiết từng chức năng trên màn hình, cấu hình cổng mạng và các tình huống xử lý.
- [Đặc tả Schema Dữ liệu (Data Specification)](docs/DATA.md): Cấu trúc chi tiết của các tệp `run.json`, `detections.jsonl`, `tracked_observations.jsonl`, `web_overlay.json` và `spatial_map.json`.
- [Tài nguyên & Xuất xứ Model (Resources & Provenance)](docs/RESOURCES.md): Nguồn gốc, dung lượng byte và mã băm SHA-256 chuẩn của model ONNX, weights OCR và bundle demo.
