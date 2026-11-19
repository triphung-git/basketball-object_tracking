# Quản lý Tài nguyên, Mô hình & Dữ liệu Mẫu (Resources & Provenance)

Tài liệu kiểm kê xuất xứ, kích thước tệp, mã băm SHA-256 và quy trình xác thực toàn vẹn cho toàn bộ mô hình máy học và dữ liệu mẫu trong dự án.

---

## 1. Danh mục Mô hình Trí tuệ Nhân tạo (Model Zoo)

Mọi tệp trọng số (weights) được phân phối kèm repository hoặc tải về trong bước `setup.bat` đều được kiểm tra tính toàn vẹn bằng hàm băm SHA-256 nghiêm ngặt trước khi nạp vào bộ nhớ.

| Thành phần | Model ID / Nguồn | Tệp tin trên đĩa | Kích thước (bytes) | SHA-256 Checksum |
|---|---|---|---|---|
| **YOLO26s Detector** | `phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1` | `codebase/models/detector/weights.onnx` | 38.851.269 | `07044f5d08f37848f7d61f49d16b03407daad025919d63f0dfe195cd30f56b33` |
| **EasyOCR CRAFT** | [CRAFT Text Detector](https://github.com/JaidedAI/EasyOCR/releases/tag/pre-v1.1.6) | `~/.EasyOCR/model/craft_mlt_25k.pth` | 83.152.330 | `f7572719543e3d4c0a5a5448abfa419fe0e73fb2a9876251b5e523f89eeec34e` |
| **EasyOCR Recognizer** | [English G2 Model](https://github.com/JaidedAI/EasyOCR/releases/tag/v1.3) | `~/.EasyOCR/model/english_g2.pth` | 15.143.997 | `f4019bf80db2665e75871f30833a6931fbdf82b45037d4f938f36c535ee6168e` |

### Thông số Thực thi của Detector
- **Runtime:** ONNX Runtime (`CPUExecutionProvider`), tối ưu hóa luồng CPU cục bộ.
- **Tiền xử lý:** Letterbox resize với cạnh dài tối đa 1280 px, giữ nguyên tỷ lệ khung hình gốc (aspect ratio), chuẩn hóa RGB `[0.0, 1.0]`.
- **Ngưỡng tin cậy (Confidence Threshold):** `0.20` khi quét rộng; `0.25` chuẩn xác định.
- **Ánh xạ nhãn (Class Mapping):**
  - `0`: `ball` (Quả bóng rổ).
  - `1`: `human` (Cầu thủ, trọng tài, người trên sân).
  - `2`: `rim` (Vành rổ).

---

## 2. Dữ liệu Trận đấu & Bộ Demo (Datasets & Demos)

### 2.1. Demo Chuẩn 14 giây Đóng gói (`codebase/demo/`)
- **Nguồn:** Trận tứ kết FIBA 3x3 World Tour Zaisan (UB vs Ulaanbaatar MMC Energy).
- **Video:** `input.mp4` (13.451.784 bytes), 840 frame, 60 FPS, độ phân giải 1920 × 1080.
- **Mã băm SHA-256:** `b0c5f9e24f6fee9652be01d8a6ace0450e41593ecbc5d9873af026eb7a818bb4`.
- **Thống kê xử lý:**
  - 840 khung hình phát hiện đối tượng liên tục.
  - 31 track cầu thủ duy nhất được khởi tạo.
  - 743 khung hình có hỗ trợ hình học tự động (88,5%).
  - 4.587 quan sát chiếu thành công lên mặt sân 3×3 (tỷ lệ chiếu 59,5%).
  - 0 giây trùng lặp danh tính (`identity_overlap_seconds: 0.0`).

### 2.2. Dữ liệu Toàn trận 23 phút 18 giây (`D:\new\video demo.mp4`)
- **Tập tin nguồn:** `D:\new\video demo.mp4` (858.151.732 bytes).
- **Codec & Thông số:** H.264 High Profile, 1920 × 1080, 60.0 FPS CFR, thời lượng stream: 1.397,75 giây (83.865 frame).
- **Mã băm SHA-256:** `ae83eb316347e0925263c93ca00d8a145ebbc961857415904ffd7fd049c1d99e`.
- **Thống kê pipeline toàn trận:**
  - Số lượng detection: 635.297 (507.039 người, 59.695 bóng, 68.563 vành rổ).
  - Số quan sát tracking: 804.400 quan sát trên 2.299 track IDs.
  - Số khung hình overlay web: 6.989 frame (tần số 5 Hz).
  - Số vị trí chiếu sân 2D: 371.799 vị trí (tỷ lệ phủ 74,72%).
  - Đội hình theo dõi: Phủ kín 8 cầu thủ của hai đội UB và Ulaanbaatar MMC Energy.

---

## 3. Quy trình Kiểm tra Toàn vẹn & Khôi phục (Integrity & Recovery)

### 3.1. Cơ chế Kiểm tra Toàn vẹn
Khi chạy `setup.bat`, script thực hiện các bước kiểm tra tự động:
1. Tính hàm băm SHA-256 của `weights.onnx` và đối chiếu với manifest. Nếu sai lệch, quá trình dừng với thông báo lỗi rõ ràng.
2. Kiểm tra bundle demo trong `codebase/demo/` qua `manifest.json`.
3. Sao chép bản làm việc độc lập của demo vào thư mục `codebase/outputs/web-uploads/` để người dùng có thể tự do gán nhãn, chỉnh sửa khoảng thời gian mà không làm hỏng dữ liệu gốc.

### 3.2. Quy trình Khôi phục Về Trạng thái Gốc (Reset)
Nếu bản làm việc của demo hoặc thư mục upload bị cấu hình sai:
1. Đóng toàn bộ cửa sổ dashboard đang chạy (tổ hợp phím `Ctrl + C`).
2. Xóa hoặc di chuyển thư mục job cần đặt lại trong `codebase/outputs/web-uploads/<job_id>`.
3. Chạy lại script cài đặt:
   ```powershell
   .\setup.bat
   ```
4. `setup.bat` sẽ tái tạo lại bản sao demo chuẩn từ `codebase/demo/` với đầy đủ trạng thái ban đầu.
5. Để khôi phục các tệp mã nguồn hoặc weights bị thay đổi ngoài ý muốn, sử dụng Git:
   ```powershell
   git checkout -- codebase/models/ codebase/demo/
   ```
