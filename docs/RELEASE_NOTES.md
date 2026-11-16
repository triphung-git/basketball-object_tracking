# Ghi chú Phát hành (Release Notes) — Bản Thử nghiệm Demo 20261116

**Phiên bản:** `v1.0.0-demo-preview-20261116`  
**Ngày phát hành:** 2026-11-16 (Asia/Bangkok)  
**Trạng thái thử nghiệm:** EXPERIMENTAL PREVIEW — Sẵn sàng cho người dùng review thực tế.

---

## 1. Tuyên bố Nghiệm thu & Ba Phán quyết Độc lập (Three Independent Verdicts)

Tuân thủ nghiêm ngặt nguyên tắc minh bạch kỹ thuật, bản phát hành này phân định rõ ranh giới giữa tính năng phần mềm và nghiệm thu chất lượng:

| Phán quyết | Trạng thái | Diễn giải chi tiết |
| :--- | :--- | :--- |
| **Technical Gate** | **PASS** (`TECHNICAL_COMPLETE`) | Toàn bộ các module kỹ thuật, pipeline đầu-cuối, kiểm thử đơn vị, trình diễn video overlay và dashboard hoạt động ổn định không có lỗi mã. |
| **Demo Gate** | **DEMO_READY_FOR_REVIEW** | Đã hoàn thiện gói demo độc lập có thể khởi chạy bằng một lệnh, tích hợp đủ PTS, REB, AST, Heatmap thật, Video overlay MP4 và Dashboard tương tác. |
| **Quality Gate (06A)** | **INSUFFICIENT_DATA / QUALITY_PENDING_REVIEW** | Chưa công bố đạt chất lượng thương mại chính thức (P≥95%, R≥90%) do cần người dùng phê duyệt bộ nhãn bổ sung (R01) và thống nhất phân chia tập kiểm thử độc lập (R04). |

---

## 2. Các Tính năng Đã Hoàn thiện trong Gói Demo

1. **Nhận diện và Thống kê Tự động (Automatic Stats):**
   - Tự động phát hiện các pha ném rổ (Shot Release/Made/Miss), pha bắt bóng bật bảng (Rebound) và pha kiến tạo (Assist) từ dữ liệu video thực tế mà không cần can thiệp thủ công.
   - Cơ chế liên kết sự kiện cha-con (`parent_event_id`) chặt chẽ: Rebound và Assist được kiểm chứng ràng buộc với pha ném rổ gốc.
2. **Hiệu chuẩn Sân & Bản đồ Nhiệt Tích lũy (Court Heatmap):**
   - Ma trận ánh xạ đồng dạng (Homography) chuyển đổi tọa độ pixel sang tọa độ mét sân FIBA 3x3 (15m x 11m).
   - Tích lũy mật độ di chuyển của cầu thủ đạt **17.43 person-seconds** (không sử dụng giá trị hằng số giả lập).
   - Xuất bản đồ nhiệt chi tiết cho toàn sân, Đội tuyển Việt Nam và Đội tuyển Tonga.
3. **Video Overlay Thực tế (Annotated MP4):**
   - Video độ phân giải 1080p, 30 FPS với hộp nhận diện phân biệt màu: bóng rổ, vành rổ, cầu thủ.
   - Bảng Telemetry thời gian nguồn chuẩn xác (PTS).
   - Biểu ngữ động hiển thị sự kiện ngay khi xác nhận.
4. **Bảng Điều khiển Cục bộ (Interactive Dashboard):**
   - Hỗ trợ truyền phát video mượt mà qua chuẩn HTTP Range 206 Partial Content.
   - Bảng Live Box Score tự động cập nhật điểm số, lỗi và lượt ném chưa rõ quy gán.
   - Các cổng xuất dữ liệu 1 chạm: `/api/export/boxscore` (CSV), `/api/export/events` (JSONL), `/api/export/summary` (JSON).
5. **Khởi chạy Đơn giản bằng Một Lệnh:**
   - Cung cấp tệp thực thi `run_demo.bat` cho Windows và `run_demo.py` qua giao diện dòng lệnh.
   - Hỗ trợ đầy đủ đường dẫn có khoảng trắng (OneDrive) và tự động xử lý xung đột cổng mạng.
6. **Đo đạc Hiệu năng Thực tế (Zero Fallback Benchmark):**
   - Tốc độ xử lý pipeline đạt **46.18 FPS** trên CPU (đạt 1.54x thời gian thực).
   - Mức tiêu thụ bộ nhớ RAM đỉnh điểm: **691.49 MB**.

---

## 3. Danh mục Tệp trong Gói Demo (`demo-bundle/manifest.json`)

Gói demo bao gồm **26 tệp hoàn chỉnh (6.98 MB)**, đã được xác thực mã băm SHA-256:
- **Video & Screenshots:** `annotated.mp4`, `screenshots/01_desktop_dashboard.png`, `screenshots/02_mobile_dashboard.png`, `browser_qa_report.json`.
- **Thống kê & Sự kiện:** `boxscore_auto.csv`, `events_auto.jsonl`, `events_raw.jsonl`, `audit_trail.jsonl`, `shots_auto.jsonl`.
- **Quỹ đạo & Kiểm soát:** `ball_tracks.jsonl`, `ball_control.jsonl`, `possession_control.jsonl`, `trajectories.jsonl`.
- **Định danh & OCR:** `identity_mappings.json`, `jersey_evidence.json`.
- **Sân & Bản đồ Nhiệt:** `heatmap.png`, `heatmap_team_a.png`, `heatmap_team_b.png`, `heatmap_raw_grid.json`, `heatmap_summary.json`.
- **Cấu hình, Đánh giá & Benchmark:** `run.json`, `summary.json`, `checkpoint.json`, `evaluation_summary.json`, `error_index.json`, `benchmark.json`.

---

## 4. Các Giới hạn Đã biết (Known Limitations)

1. **Che khuất bóng vành rổ (Near-rim Occlusion):** Khi bóng đi vào khu vực sát vành rổ bị cơ thể cầu thủ hoặc bảng rổ che khuất hoàn toàn, mô hình nhận diện 2D baseline có thể bị gián đoạn vết bóng. Gói dữ liệu gán nhãn 8 frame (R01) đã được chuẩn bị sẵn trong giao diện `review.html` để phục vụ tinh chỉnh mô hình sau khi người dùng phê duyệt.
2. **Quy gán cầu thủ ở pha bóng lộn xộn:** Khi số áo bị quay lưng hoặc che khuất hoàn toàn, hệ thống ghi nhận ở cấp độ đội tuyển (`team_rebound` / `team_only_points`) nhằm bảo toàn nguyên tắc không suy đoán sai lệch.
3. **Phạm vi góc quay máy:** Hiệu chuẩn sân áp dụng cho góc máy toàn cảnh phát sóng. Các đoạn lia máy góc hẹp sẽ tự động gán nhãn `uncalibrated_diagnostic`.
