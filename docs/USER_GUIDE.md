# Hướng dẫn Sử dụng Hệ thống Phân tích Bóng rổ

Tài liệu hướng dẫn vận hành chi tiết giao diện Dashboard phân tích không gian và các công cụ dòng lệnh (CLI) trong hệ thống.

---

## 1. Khởi động Web Dashboard

### Lệnh khởi chạy cơ bản
Sau khi hoàn tất bước cài đặt ban đầu bằng `.\setup.bat`, mở PowerShell tại thư mục gốc và chạy:

```powershell
.\start_dashboard.bat
```

Hệ thống sẽ liên kết giao diện vào cổng mặc định `8081` và mở trình duyệt tại:
```
http://127.0.0.1:8081
```

### Các tùy chọn dòng lệnh nâng cao

Bạn có thể truyền thêm các tham số khi chạy `start_dashboard.bat`:

| Tham số | Giá trị mặc định | Mô tả |
|---|---|---|
| `--port <số_cổng>` | `8081` | Đổi cổng lắng nghe khi cổng 8081 bị ứng dụng khác chiếm dụng (ví dụ: `--port 8090`). |
| `--host <địa_chỉ>` | `127.0.0.1` | Địa chỉ mạng bind socket (dùng `0.0.0.0` nếu muốn truy cập từ mạng nội bộ). |
| `--run-dir <thư_mục>` | *None* | Mở trực tiếp một thư mục kết quả phân tích cụ thể mà không qua danh sách uploads. |
| `--video <tệp_mp4>` | *None* | Chỉ định đường dẫn video nguồn khi mở thư mục kết quả độc lập. |
| `--no-open-browser` | *Tự mở* | Không tự động bật cửa sổ trình duyệt sau khi máy chủ sẵn sàng. |

*Ví dụ khởi chạy trên cổng riêng:*
```powershell
.\start_dashboard.bat --port 8095 --host 127.0.0.1
```

---

## 2. Demo đóng gói và demo toàn trận

Kho mã nguồn đi kèm clip HCM1–HN1 dài 48,07 giây. Demo toàn trận UB–Ulaanbaatar dùng dữ liệu phân tích đã lưu trên máy.

### A. Demo đóng gói HCM1–HN1 (48 giây)
- **Mục đích:** Kiểm tra nhanh toàn bộ tính năng và giao diện sau khi cài đặt.
- **Dữ liệu:** Clip bóng rổ 3×3 HCM1–HN1 gồm 1.210 khung hình và roster 8 cầu thủ. HCM1 mặc áo trắng, HN1 mặc áo xanh đậm.
- Trên video mẫu, **Chỉ hiện cầu thủ đã xác minh** được bật sẵn. Khung cầu thủ hiện tên đội, số áo và tên. Bỏ chọn mục này để xem các mã theo dõi chưa gắn tên khi đối chiếu.
- **Cách mở:** Chạy `run_demo.bat`, bấm **Xem mẫu** trên thanh điều hướng hoặc truy cập:
  ```
  http://127.0.0.1:8081/?job=9b441192d32c5495946707131ca103d3
  ```

### B. Demo Toàn trận 23 phút 18 giây (Full Match)
- **Mục đích:** Đánh giá độ ổn định và năng lực xử lý dữ liệu lớn (Big Data Tracking).
- **Dữ liệu:** 83.865 frame, 635.297 detection, 804.400 quan sát tracking trên 2.299 track, 6.989 frame overlay.
- **Cách mở:** Trên máy đã lưu job toàn trận trong `codebase/outputs/web-uploads/`, mở địa chỉ sau:
  ```
  http://127.0.0.1:8081/?job=d21759aefdd948ff967fc5fe2dadd2a8
  ```

---

## 3. Thao tác trên Giao diện Phân tích

Giao diện dashboard được chia thành 3 khu vực chức năng chính:

```
┌──────────────────────────────────────────────┬───────────────────────────────┐
│              VIDEO PLAYER                    │       2D COURT CANVAS         │
│  - Phát/Dừng (Phím cách / Spacebar)         │  - Sân bóng rổ 3x3 FIBA       │
│  - Tua tiến/lùi (Phím mũi tên)              │  - Vị trí cầu thủ theo màu áo │
│  - Lớp phủ bounding box 5 Hz                │  - Vệt di chuyển (Trails)     │
├──────────────────────────────────────────────┴───────────────────────────────┤
│                             BẢNG ĐIỀU KHIỂN                                   │
│  [Bộ lọc đối tượng]     [Bộ lọc thời gian]        [Chế độ Heatmap]           │
│  - Toàn sân (All)       - Từ giây: 0.0            - Thang đo: Giây / Tỷ lệ % │
│  - Đội A / Đội B        - Đến giây: 1397.75       - Vẽ mật độ không gian     │
│  - Từng cầu thủ cụ thể  - Áp dụng phạm vi pha bóng - Hiện/Ẩn vệt di chuyển    │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 1. Đồng bộ Video & Lớp phủ Bounding Box
- **Phát và dừng:** Nhấp chuột vào video hoặc bấm phím `Space`.
- **Tua khung hình:** Phím `←` (lùi 1 frame / 0.016s) và `→` (tiến 1 frame). Phím `Shift + ← / →` để tua nhanh 1 giây.
- **Nhãn hiển thị trên bbox:**
  - Viền đỏ / vàng / xám tương ứng với Đội A, Đội B hoặc chưa xác định.
  - Tên cầu thủ hoặc mã theo dõi hiển thị rõ trên đỉnh hộp bao.
  - Hộp bao màu cam nhỏ biểu thị vị trí quả bóng rổ (`ball`), hộp bao màu tím biểu thị vành rổ (`rim`).

### 2. Bản đồ Sân 2D & Lọc Heatmap Động
- **Lựa chọn đối tượng:**
  - Chọn **Tất cả cầu thủ trên sân** để xem tổng thể trận đấu.
  - Chọn **Đội A** hoặc **Đội B** để phân tích mật độ chiếm lĩnh không gian của từng đội.
  - Chọn **Cầu thủ cụ thể** để xem bản đồ nhiệt vị trí di chuyển cá nhân (hữu ích để đánh giá phạm vi di chuyển, vị trí ném và khả năng phòng thủ).
- **Lọc theo khoảng thời gian:**
  - Nhập mốc thời gian bắt đầu và kết thúc vào hai ô `Từ giây` và `Đến giây`.
  - Hệ thống tính toán tức thì từ 69.645+ khoảng thời gian tích lũy (`heatmap_intervals`) mà không cần tải lại trang.
- **Thang đo Heatmap:**
  - **Tuyệt đối (giây):** Thể hiện tổng số giây cầu thủ hiện diện trong ô 0,25 × 0,25 m.
  - **Tương đối (%):** Chuẩn hóa theo tỷ lệ phần trăm thời gian xuất hiện nhiều nhất.

---

## 4. Biên tập & Hiệu chỉnh Danh tính Cầu thủ (Manual Track Assignment)

Trong một số tình huống góc máy xa, số áo bị che khuất hoặc cầu thủ va chạm dẫn đến đổi mã track, bạn có thể can thiệp hiệu chỉnh trực tiếp trên giao diện:

1. **Dừng video** tại khung hình nhìn rõ mặt hoặc số áo của cầu thủ cần sửa.
2. Bấm nút **Chọn box ở khung hình đang dừng**.
3. **Nhấp chuột trực tiếp vào bounding box** của cầu thủ đó trên khung video. Bảng điều khiển sẽ tự động nhận diện `track_id` tương ứng.
4. **Chọn đích gán:**
   - Chọn tên cầu thủ tương ứng trong danh sách đội hình.
   - Hoặc gán vai trò: `Trọng tài (referee)` hoặc `Không phải cầu thủ (non_player)` để loại bỏ người ngoài biên ra khỏi heatmap.
5. **Chọn phạm vi gán:**
   - **Áp dụng cho toàn mã:** Gán toàn bộ thời gian tồn tại của track đó cho cầu thủ được chọn.
   - **Khoảng thời gian:** Chỉ gán trong đoạn từ giây A đến giây B.
6. Bấm **Áp dụng khoảng gán**, sau đó bấm **Lưu thiết lập**.
7. Dashboard sẽ tự động cập nhật lại bản đồ sân 2D và heatmap từ dữ liệu tracking đã có mà không cần chạy lại bước nhận diện hình ảnh.

---

## 5. Quy trình Phân tích Video Mới

Để phân tích một trận đấu mới tải lên:

1. Tại màn hình chính, bấm **Chọn video** và chọn tệp `.mp4` từ máy tính (yêu cầu định dạng nén H.264, độ phân giải tối đa 1920 × 1080).
2. Mở mục **Thông tin đội và danh tính cầu thủ**:
   - Nhập tên Đội A và Đội B.
   - Chọn màu áo đại diện bằng công cụ chọn màu RGB (chọn màu đồng nhất và có độ tương phản cao, ví dụ: Đỏ vs Vàng, Xanh vs Trắng).
   - Nhập danh sách cầu thủ theo từng dòng: `<số_áo>, <họ_tên>`.
3. Bấm **Lưu thiết lập**.
4. Bấm **Phân tích** để bắt đầu quy trình:
   - Bước 1: Trích xuất metadata và kiểm tra video.
   - Bước 2: Chạy bộ dò tìm YOLO26s ONNX trên CPU từng khung hình.
   - Bước 3: Theo dõi chuyển động và liên kết thực thể (kinematic tracking).
   - Bước 4: Tự động nhận diện đường sân 3x3 và dựng bản đồ không gian.
   - Bước 5: Phân đội theo màu áo và đối chiếu số áo OCR.
   - Bước 6: Khởi tạo web overlay và hoàn tất.
5. Bạn có thể theo dõi thanh tiến độ phần trăm, số khung hình đã đọc, thời gian dự kiến còn lại, hoặc bấm **Hủy** nếu muốn dừng.

---

## 6. Sử dụng Giao diện Dòng lệnh (CLI)

Hệ thống cung cấp script batch `run_demo.bat` điều phối pipeline xử lý hàng loạt:

### Lệnh phân tích cơ bản
```powershell
.\run_demo.bat --mode video-analysis --video "D:/data/match01.mp4" --output "codebase/outputs/match01-run" --serve --open-browser
```

### Các cờ lệnh hỗ trợ

| Cờ lệnh | Ý nghĩa |
|---|---|
| `--mode` | Chế độ chạy: `video-analysis` (phân tích video) hoặc `demo` (mở demo). |
| `--video <path>` | Đường dẫn tệp video nguồn MP4. |
| `--output <path>` | Thư mục lưu kết quả phân tích (phải là thư mục mới). |
| `--court <path>` | Đường dẫn tệp JSON hiệu chuẩn sân thủ công (khi không dùng auto-geometry). |
| `--roster <path>` | Đường dẫn tệp JSON danh sách đội hình và mã màu áo. |
| `--format` | Thể thức sân: `3x3` (mặc định) hoặc `5x5`. |
| `--max-frames <N>` | Giới hạn phân tích N khung hình đầu tiên (dùng để test nhanh). |
| `--serve` | Tự động khởi động máy chủ web dashboard sau khi chạy xong pipeline. |
| `--open-browser` | Tự động mở trình duyệt sau khi máy chủ bật. |

---

## 7. Xử lý Sự cố Thường gặp

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| **Cổng mạng bị chiếm (`8081` hoặc `8080`)** | Có tiến trình khác đang chạy trên cổng này. | Chạy `.\start_dashboard.bat --port 8090` để đổi sang cổng mới. |
| **Video không phát trên trình duyệt** | Video dùng codec không được trình duyệt hỗ trợ (HEVC/H.265, AV1). | Chuyển đổi video sang chuẩn **H.264 / AVC** và audio AAC bằng ffmpeg: `ffmpeg -i input.mp4 -c:v libx264 -c:a aac output.mp4`. |
| **Bản đồ báo "Thiết lập đã đổi" hoặc "stale"** | Revision thuật toán bản đồ sân chưa khớp với cấu hình mới lưu. | Bấm nút **Cập nhật bản đồ** trên giao diện, máy chủ sẽ tự động tính toán lại trong nền trong 30–60 giây. |
| **Thiếu hình học sân ở một số đoạn** | Góc quay quay cận cảnh, chuyển máy hoặc góc quay không thấy đủ vạch sân. | Đây là hành vi an toàn của pipeline: hệ thống từ chối ngoại suy điểm ảo khi thiếu cơ sở hình ảnh. Tracking vẫn hiển thị bình thường trên video. |
