# Môi trường — task01

## Tái kiểm chứng 2026-11-01

Xem [nghiệm thu task01–02](task01-task02-acceptance.md) để biết kết quả mới. 31 tests pass trên môi trường hiện có. Run local ONNX CPU mới trên 3 frame clip02 hoàn thành, median 723,964 ms, mean 609,017 ms; không phải FPS toàn pipeline. Thử OFFLINE_MODE=True thất bại ModelRetrievalError, sau khi người dùng đồng ý kết nối metadata/weights Roboflow thì run với OFFLINE_MODE=False thành công. Chưa cam kết hoàn toàn offline. Không đổi dependency/driver hoặc kích hoạt CUDA. Các số 490,4 ms bên dưới thuộc run lịch sử 18 samples, không phải hằng số tốc độ máy.

Ngày kiểm tra: 2026-10-31. Trạng thái: **Đã nghiệm thu toàn diện** — Đã suy luận mô hình thật `phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1` trên 18 frame từ 3 video thử nghiệm.

| Thành phần | Quan sát |
|---|---|
| OS | Windows, PowerShell |
| GPU | NVIDIA GeForce RTX 2050, 4096 MiB |
| Driver NVIDIA | 610.62 |
| CPU identifier / logical CPUs | Intel64 Family 6 Model 154 Stepping 3; 16 logical CPUs |
| Python mặc định lệnh python | 3.14.6 |
| Python launcher | Có 3.13 và Astral CPython 3.14.7 |
| uv | Có trong PATH |
| Clip mẫu | 3 MP4 trong codebase/assets_test; đã giải mã và suy luận thành công |
| Model inference, schema, class mapping thực tế | Đã xác nhận: `0: ball`, `1: human`, `2: rim` (YOLO26s ONNX) |
| Latency / Tốc độ suy luận CPU | Median: 490.4 ms, Mean: 527.1 ms, Min: 286.0 ms, Max: 909.5 ms |

Công cụ `codebase/scripts/check_environment.py` đã chạy thành công, ghi `codebase/outputs/environment-python312-current.json`.

## Runtime đã chuẩn bị & Kiểm chứng

Đã cài CPython 3.12.14 riêng trong `codebase/.tools/python`, tạo `codebase/.venv`; không thay Python hệ thống. Đã cài `inference-models[onnx-cpu]==0.39.7`. Import `cv2`, `torch`, `onnxruntime` và `AutoModel` thành công. Toàn bộ 5 unittests trong `codebase/tests/test_smoke_contract.py` đạt kết quả PASS.

| Runtime | Phiên bản / trạng thái |
|---|---|
| opencv-python | 5.0.0.93; cv2 runtime 5.0.0 |
| inference-models | 0.39.7; runtime class `YOLO26ForObjectDetectionOnnx` |
| torch | 2.15.0+cpu; cuda.is_available() = False |
| onnxruntime | 1.22.1; CPUExecutionProvider đã kiểm chứng thực thi |
| GPU inference | Chưa kích hoạt; giữ CPU ONNX làm baseline ổn định |

Đã chốt ONNX CPU làm baseline cho Task 01 và các task logic tiếp theo (Task 02, 03, 04).

### Vấn đề cài đặt và tương thích nền tảng đã xử lý

1. **Build cache ban đầu**: Lần đầu cache dài dưới thư mục OneDrive bị lỗi build `antlr4-python3-runtime==4.9.3`. Đã cài với cache ngắn `$env:TEMP/bb-uv` thành công.
2. **Symlink Windows (`WinError 1314`)**: Thư viện `inference-models` yêu cầu symlink khi nạp cached blob; trên Windows non-admin không bật Developer Mode, script đã tự động fallback sang `shutil.copyfile` kèm kiểm tra toàn vẹn mã băm MD5.
3. **Giới hạn đường dẫn dài Windows (`MAX_PATH = 260`)**: Đường dẫn nested cache trên OneDrive vượt 260 ký tự khi tạo file tạm `.model_config.json.*.tmp`. Đã áp dụng tiền tố `\\?\` để vượt qua giới hạn hệ thống.

### Kết quả nghiệm thu

- Script `inspect_videos.py` giải mã 3/3 video toàn bộ bằng FFmpeg và sinh contact sheets.
- 5 unittests contract/credential/compat pass không cần key thật hay mạng.
- Smoke script `smoke_model.py` đã hoàn thành suy luận 18 samples, sinh đầy đủ 18 ảnh overlay và báo cáo nghiệm thu chi tiết tại `docs/reports/task01-smoke.md`. Output lưu tại `codebase/outputs/smoke-20261031-215143/`.
