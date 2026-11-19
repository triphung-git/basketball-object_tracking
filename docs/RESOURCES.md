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

### 2.1. Demo đóng gói HCM1–HN1 (`codebase/demo/`)

- Clip bóng rổ 3×3 dài 48,07 giây, gồm 1.210 khung hình gốc ở độ phân giải 1038 × 480. Tệp `input.mp4` có dung lượng 7.679.483 byte.
- SHA-256 của video là `da95d00d3a7efb72dee77eb86e14cb7f748a9006c8fa3a0038a1ed96c7ebb4b9`.
- Detector xử lý đủ 1.210 khung hình. Phép chiếu sân tự động có dữ liệu ở 783 khung hình (64,7%) và chiếu được 4.143 quan sát. Các khung hình thiếu bằng chứng đường sân không được chiếu lên bản đồ.
- Roster do người dùng cung cấp gồm 4 cầu thủ HCM1 áo trắng và 4 cầu thủ HN1 áo xanh đậm. Sáu cầu thủ có nhãn trong 36 khoảng đã đối chiếu theo số áo. Mặc định video chỉ hiện khung người khớp các khoảng này.
- Clip được chuyển từ tập kiểm thử sang tập demo. Các kết quả trên clip mô tả lần xử lý này và không phải phép đo độ chính xác độc lập.

### 2.2. Demo toàn trận UB–Ulaanbaatar (23 phút 18 giây)
- Tệp `input.mp4` có 858.151.732 byte. Video và các kết quả phân tích được đóng gói trong tệp ZIP của GitHub Release `full-match-demo-v1`.
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
4. Tải ZIP demo toàn trận nếu job chưa có, đối chiếu SHA-256 trong `codebase/full_match_demo.json` và kiểm tra từng tệp trước khi đưa job vào `codebase/outputs/web-uploads/`. Cần khoảng 2,4 GiB trống tạm thời cho bước tải và giải nén, ngoài dung lượng cài thư viện.

### 3.2. Quy trình Khôi phục Về Trạng thái Gốc (Reset)
Nếu bản làm việc của demo hoặc thư mục upload bị cấu hình sai:
1. Đóng toàn bộ cửa sổ dashboard đang chạy (tổ hợp phím `Ctrl + C`).
2. Xóa hoặc di chuyển thư mục job cần đặt lại trong `codebase/outputs/web-uploads/<job_id>`.
3. Chạy lại script cài đặt:
   ```powershell
   .\setup.bat
   ```
4. `setup.bat` tái tạo demo ngắn từ `codebase/demo/` hoặc tải lại demo toàn trận, tùy job đã được di chuyển.
5. Để khôi phục các tệp mã nguồn hoặc weights bị thay đổi ngoài ý muốn, sử dụng Git:
   ```powershell
   git checkout -- codebase/models/ codebase/demo/
   ```
