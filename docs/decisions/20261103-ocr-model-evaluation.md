# OCR decision record — Hồ sơ kỹ thuật và thẩm định mô hình local

Ngày cập nhật: 2026-11-04. **APPROVED BY USER & FULLY FUNCTIONAL OFFLINE**.
Bộ weights EasyOCR đã được người dùng phê duyệt tải chính thức và đã được kiểm tra tính toàn vẹn, lưu trữ cục bộ tại máy trạm. Engine OCR chạy hoàn toàn offline (`download_enabled=False`), tuyệt đối không tải ngầm qua mạng và không gửi dữ liệu ra bên ngoài.

## 1. Hiện trạng môi trường & gói cài đặt cục bộ

Đã kiểm tra thực tế trong môi trường ảo `codebase/.venv`:
- `easyocr`: Đã cài đặt (`easyocr: True`).
- `torch`: Đã cài đặt (`torch: True`, PyTorch 2.15 CPU).
- `cv2`: Đã cài đặt (`cv2: True`, OpenCV 5.0).
- **Trạng thái weights cục bộ:** **ĐÃ TẢI VÀ CACHE THÀNH CÔNG**.
  + Thư mục mặc định: `~/.EasyOCR/model/`
  + Thư mục cache dự án: `codebase/.model-cache/easyocr/`

## 2. Đặc tả kỹ thuật mô hình đã cài đặt (EasyOCR CPU Local)

| Thuộc tính | Chi tiết xác minh từ mã nguồn chính thức | Trạng thái thực tế |
|---|---|---|
| Mã nguồn & Engine | JaidedAI / EasyOCR (Chạy hoàn toàn offline trên CPU) | Đã tích hợp và hoạt động |
| Detector Network | CRAFT text detector (`craft_mlt_25k.pth`) | Đã lưu, 83,152,330 bytes |
| Detector Nguồn & Hash | `https://github.com/JaidedAI/EasyOCR/releases/download/pre-v1.1.6/craft_mlt_25k.zip` | MD5: `2f8227d2def4037cdb3b34389dcf9ec1` (Khớp tuyệt đối) |
| Recognizer Network | Standard English Recognition Model Gen2 (`english_g2.pth`) | Đã lưu, 15,143,997 bytes |
| Recognizer Nguồn | `https://github.com/JaidedAI/EasyOCR/releases/download/v1.3/english_g2.zip` | Đã giải nén vào thư mục model |
| Quyền phê duyệt | Đã được User phê duyệt tại lượt trao đổi 2026-11-03 | ĐÃ PHÊ DUYỆT |
| License | **Apache License 2.0** (cho cả code và weights chính thức) | Hợp lệ cho dự án |
| Chế độ hoạt động | Offline (`download_enabled=False`, `verbose=False`) | Đã kiểm chứng qua unit test |

## 3. Kiến trúc Provider đã hiện thực trong Codebase

Đã hiện thực trong `codebase/src/basketball_scoreboard/identity.py`:
1. **Kiểm tra chất lượng crop (`evaluate_crop_quality`):**
   - Loại trừ crop rỗng hoặc kích thước nhỏ hơn $16\times 24\,\text{px}$.
   - Kiểm tra phương sai màu (độ lệch chuẩn cường độ sáng $\ge 8.0$) để loại trừ các mảng màu áo phẳng không có số hoặc phông nền trơn.
2. **Local Provider bảo mật (`LocalEasyOCRProvider`):**
   - Thiết lập `download_enabled=False` triệt để nhằm ngăn chặn EasyOCR ngầm tải dữ liệu qua mạng.
   - Tự động kiểm tra file `craft_mlt_25k.pth` và `english_g2.pth` tại `--ocr-weights-dir`, `~/.EasyOCR/model/` hoặc `codebase/.model-cache/easyocr/`.
   - Nếu thiếu weights: ném lỗi `ModelWeightsUnavailableError` tường minh kèm thông báo hướng dẫn xin quyền tải; tuyệt đối không tạo lỗi âm thầm.
   - Bộ lọc số áo: Giới hạn chỉ nhận diện ký số (`allowlist='0123456789'`), định dạng 1–2 chữ số bóng rổ hợp lệ ($0$–$99$).
3. **Mock Provider chẩn đoán (`MockOCRProvider`):**
   - Sử dụng cho kiểm thử tự động và chế độ chẩn đoán (`--allow-uncalibrated`).
   - Bị từ chối tự động (exit != 0) nếu cố tình kích hoạt trong chế độ production.
4. **CLI wiring (`codebase/scripts/track_players.py`):**
   - Hỗ trợ các tham số: `--enable-ocr`, `--ocr-provider {easyocr,mock}`, `--ocr-weights-dir`, `--ocr-sampling-cadence`, `--min-ocr-crop-height`.
   - Cơ chế lấy mẫu theo chu kỳ (`--ocr-sampling-cadence`, mặc định 5 frame/track) để tối ưu ngân sách CPU, tránh nghẽn luồng xử lý video.

## 4. Kết quả kiểm chứng thực tế

1. **Unit & Contract Test (`codebase/tests/test_task06_players_identity.py`):**
   - `test_crop_quality_evaluation`: PASS
   - `test_local_easyocr_rejects_missing_weights_without_download`: PASS
   - `test_local_easyocr_initializes_with_cached_weights`: PASS (kiểm tra nhận diện số áo `23` từ ảnh crop tổng hợp đạt độ tin cậy 1.0)
   - `test_mock_ocr_provider_drives_identity_resolution`: PASS
2. **CLI Test (`codebase/tests/test_task56_cli_acceptance.py`):**
   - `test_track_players_cli_with_mock_ocr_in_diagnostic_mode`: PASS
   - `test_track_players_cli_mock_ocr_forbidden_in_production`: PASS
   - `test_track_players_cli_easyocr_production_fails_when_weights_missing`: PASS
3. **Thực thi trên video clip02 (1089 frames 4K):**
   - Pipeline hoàn thành: 1089 frames, 1416 observations, 900 bản ghi team color evidence.
   - EasyOCR trích xuất đúng torso crops và kiểm tra chất lượng tự động; không ghi nhận ảo số áo khi áo đấu trơn.
4. **Toàn bộ test suite:** **160 tests passed** (100% OK).
