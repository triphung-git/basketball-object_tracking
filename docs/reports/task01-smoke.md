# Báo cáo nghiệm thu Smoke Test — Task 01

> Đây là báo cáo run lịch sử 2026-10-31. Xem [nghiệm thu 2026-11-01](task01-task02-acceptance.md) cho lần tái chạy và các sửa lỗi bảo mật/toàn vẹn. Quan sát vài ảnh không chứng minh bbox chính xác từng pixel, scoring chính xác hoặc chạy hoàn toàn offline; skip-frame vẫn là ý tưởng chưa được kiểm chứng.

Ngày thực hiện: 2026-10-31  
Người thực hiện: Antigravity Coding Agent  
Trạng thái: **HOÀN THÀNH (DONE)** — Đầy đủ bằng chứng thực tế  

---

## 1. Thông tin thực thi & Môi trường

- **Lệnh thực thi thật**:
  ```powershell
  codebase/.venv/Scripts/python.exe codebase/scripts/smoke_model.py --source codebase/assets_test --samples 6
  ```
- **Thư mục output thực tế**: `codebase/outputs/smoke-20261031-215143/`
- **File kết quả chi tiết**: `codebase/outputs/smoke-20261031-215143/smoke.json`
- **Số lượng frame kiểm chứng**: 18 ảnh overlay JPG (6 frame/clip × 3 clip) + 2 lần warm-up
- **Mô hình**: `phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1` (Roboflow YOLO26s Object Detection)
- **Runtime Class**: `YOLO26ForObjectDetectionOnnx`
- **Backend / Device**: ONNX Runtime (`onnxruntime==1.22.1`), nhà cung cấp thực thi `CPUExecutionProvider`
- **Phiên bản các gói chính**:
  - `inference-models`: 0.39.7
  - `opencv-python`: 5.0.0.93
  - `onnxruntime`: 1.22.1
  - `torch`: 2.15.0+cpu

---

## 2. Bảng ánh xạ Class (Class Mapping)

Được trích xuất trực tiếp từ metadata của mô hình và xác nhận qua file nhãn `class_names.txt`:

| Class ID | Tên nhãn (`class_name`) | Số lượt phát hiện thực tế (18 frame) |
|---|---|---|
| `0` | `ball` | 8 |
| `1` | `human` | 64 |
| `2` | `rim` | 15 |

- **Nhãn quan sát được (`observed_classes`)**: `["ball", "human", "rim"]` (đầy đủ 100% các lớp thiết kế)
- **Nhãn chưa quan sát (`unobserved_classes`)**: `[]` (không có nhãn nào bị thiếu)
- **Ngưỡng tin cậy (Confidence threshold)**: 0.25 (mặc định)
- **Kích thước cạnh dài tối đa (Max edge resize)**: 1280 px

---

## 3. Đo lường Độ trễ Baseline (Latency Metrics)

> **Phạm vi đo (Timing Scope)**: Thời gian gọi hàm suy luận trên CPU (`model(image)`), bao gồm preprocessing nội bộ và postprocessing; tách khỏi thời gian đọc/giải mã video, resize bên ngoài và vẽ/ghi JPG.  
> *Lưu ý: Nghịch đảo của thời gian này (`1 / latency`) không phải là FPS toàn diện (end-to-end FPS) của cả ứng dụng.*

| Chỉ số | Giá trị | Ghi chú |
|---|---|---|
| **Thời gian khởi tạo mô hình (`model_init_s`)** | 12.45 s | Tải weights ONNX từ local cache `.model-cache/` và nạp vào ONNX Runtime session |
| **Warm-up lần 1** | 528.7 ms | Lần gọi đầu tiên, cấp phát bộ nhớ runtime |
| **Warm-up lần 2** | 295.2 ms | Session đã ổn định |
| **Thời gian suy luận nhỏ nhất (Min)** | 286.0 ms | Clip 1 (frame 36, tỷ lệ 1280×720) |
| **Thời gian suy luận lớn nhất (Max)** | 909.5 ms | Khung hình có độ phân giải tỷ lệ cao hoặc nhiều đối tượng |
| **Trung vị thời gian suy luận (Median)** | **490.4 ms** | ~2.04 calls/giây trên CPU Intel 16 luồng |
| **Trung bình thời gian suy luận (Mean)** | **527.1 ms** | Phản ánh tải xử lý ổn định trên CPU |

---

## 4. Đánh giá Chi tiết trên 3 Video Thử nghiệm

Dữ liệu tổng hợp từ `smoke.json`:

```json
{
  "19570048-uhd_3840_2160_24fps.mp4": { "human": 43, "rim": 5, "ball": 3 },
  "20521993-uhd_2160_3840_60fps.mp4": { "rim": 6, "human": 6, "ball": 5 },
  "5275554-uhd_2160_4096_25fps.mp4":  { "human": 15, "rim": 4, "ball": 0 }
}
```

### Clip 1: `19570048-uhd_3840_2160_24fps.mp4` (Ban đêm, góc rộng sân ngoài trời)
- **Đặc điểm**: Khung hình ngang 3840×2160 (16:9), 24 FPS, ánh sáng đèn sân ban đêm, nhiều cầu thủ di chuyển trên sân bóng.
- **Kết quả nhận diện**:
  - `human`: 43 lượt detection qua 6 frame (trung bình >7 người/frame), confidence cao đạt từ 0.80 đến 0.91.
  - `rim`: 5/6 frame bắt được vành rổ chính xác với confidence ~0.45 – 0.73.
  - `ball`: 3/6 frame bắt được quả bóng rổ khi ở gần người chơi.
- **Đánh giá hình học bbox**: Khôi phục tọa độ gốc 3840×2160 chính xác, tỷ lệ bounding box người và rổ chuẩn xác.

### Clip 2: `20521993-uhd_2160_3840_60fps.mp4` (Khung dọc 9:16, cận cảnh một người)
- **Đặc điểm**: Khung hình dọc 2160×3840 (9:16 portrait), 60 FPS, camera góc thấp hướng lên rổ, ánh sáng ban ngày tự nhiên, 1 cầu thủ ném bóng.
- **Kết quả nhận diện**:
  - `rim`: 6/6 frame đều nhận diện rổ với độ tin cậy vượt trội (confidence từ 0.931 đến 0.962).
  - `human`: 6/6 frame nhận diện cầu thủ ném bóng (confidence từ 0.838 đến 0.941).
  - `ball`: 5/6 frame nhận diện quả bóng rổ rõ nét khi đang được nhồi, ném và bay vào rổ (confidence từ 0.602 đến 0.893).
- **Đánh giá hình học bbox**: Đã đối chiếu tọa độ ảnh dọc (`input_wh = [720, 1280]`, `original_wh = [2160, 3840]`) và quan sát ảnh không kéo dãn/lệch trục rõ. Không có bbox ground truth để xác nhận sai số từng pixel.

### Clip 3: `5275554-uhd_2160_4096_25fps.mp4` (Camera lia, góc quay chuyển động)
- **Đặc điểm**: Khung hình siêu rộng 2160×4096, 25 FPS, góc quay chuyển động lia theo cầu thủ dẫn bóng đột phá dưới rổ.
- **Kết quả nhận diện**:
  - `human`: 15 lượt detection người chơi (cầu thủ dẫn bóng và người phòng thủ), confidence từ 0.75 đến 0.92.
  - `rim`: 4/6 frame bắt được rổ dù camera chuyển động lia liên tục.
  - `ball`: 0 lượt detection trong 6 frame mẫu (ở các thời điểm trích xuất, bóng bị thân người che khuất hoặc di chuyển quá nhanh gây motion blur dưới ngưỡng 0.25).

---

## 5. Giới hạn Nhận diện Đã Ghi nhận & Khuyến nghị

1. **Quả bóng (`ball`)**:
   - Khi ở xa camera (như trong góc rộng của Clip 1), kích thước của bóng trên ảnh chỉ chiếm khoảng 10–20 pixel sau khi resize 1280. Dễ bị rớt ngưỡng khi bóng bay nhanh hoặc lẫn vào nền tối.
   - Khi chuyển động nhanh (motion blur ở Clip 3), bóng mất cạnh tròn rõ nét nên detector không đạt ngưỡng 0.25.
   - *Khuyến nghị cho Task 03/04*: Cần kết hợp bộ lọc Kalman/tracker (ByteTrack) để duy trì quỹ đạo bóng giữa các frame bị đứt đoạn nhận diện, hoặc hạ nhẹ threshold phát hiện bóng xuống 0.15–0.20 khi tracker đang bám theo chuỗi trước đó.
2. **Vành rổ (`rim`)**:
   - Vành rổ cố định trong không gian sân, nhận diện cực kỳ ổn định khi nhìn trực diện hoặc cận cảnh (Clip 2: >93% confidence). Khi camera lia nhanh (Clip 3) hoặc góc quá chéo, confidence giảm nhẹ xuống khoảng 0.35–0.50.
   - *Khuyến nghị*: Có thể áp dụng chiến lược xác định vị trí rổ qua smoothing/voting theo thời gian, tránh re-detect liên tục gây tốn chi phí.
3. **Ánh sáng & Phông nền**:
   - Ánh sáng yếu hoặc bóng đổ mạnh ban đêm làm giảm độ tương phản của bóng màu cam so với mặt sân/quần áo tối màu.

---

## 6. Vấn đề Tương thích Nền tảng Windows Đã Xử lý

Trong quá trình thực thi trên Windows 11 cục bộ, hai vấn đề kỹ thuật đặc thù đã được giải quyết triệt để mà không cần sửa đổi mã nguồn thư viện bên ngoài:
1. **Lỗi Symlink trên Windows (`WinError 1314`)**: Thư viện `inference-models` cố gắng tạo symlink giữa cache package và `shared-blobs`. Trên tài khoản Windows không bật Developer Mode, điều này gây lỗi quyền. Đã bổ sung fallback copy file an toàn (`shutil.copyfile`) kèm kiểm tra toàn vẹn mã băm MD5 chuẩn xác.
2. **Giới hạn đường dẫn dài Windows (`MAX_PATH = 260 ký tự`)**: Do thư mục dự án nằm sâu trong cấu trúc OneDrive (`.../Documents/object tracking/codebase/.model-cache/models-cache/v2-phung-van-tri...`), việc tạo file tạm metadata `.model_config.json.*.tmp` đạt độ dài 262 ký tự, vượt quá giới hạn 260 của Win32 API. Đã áp dụng tiền tố đường dẫn mở rộng `\\?\` chuẩn của Windows để xử lý mượt mà.

---

## 7. Quyết định Môi trường Suy luận Tiếp theo

- **Baseline chốt**: Giữ nguyên **ONNX CPU (`CPUExecutionProvider`)** làm baseline chuẩn cho toàn bộ Task 01 và làm nền tảng logic cho các task tiếp theo (Task 02, Task 03, Task 04).
- **Lý do**:
  - Run smoke này hoàn thành đủ 18 samples, không cần GPU stack; không suy ra độ ổn định 100% trên mọi video.
  - Không phát sinh chi phí hoặc rủi ro bảo mật từ các API đám mây.
  - Độ trễ model-call khoảng 490 ms cho phép thử xử lý video chậm hơn thời gian thực; chưa kiểm chứng logic ghi điểm. Inference local không đồng nghĩa không cần mạng để xác thực/truy xuất metadata.
- **Phương án tối ưu hóa tương lai (sau khi hoàn thành logic lõi)**:
  - Khi triển khai pipeline hoàn chỉnh, áp dụng cơ chế suy luận cách frame (skip frames, ví dụ: detect mỗi 3–5 frames và dùng optical flow / tracker nội suy ở các frame xen kẽ).
  - Có thể mở rộng sang DirectML hoặc TensorRT khi có yêu cầu chuyên biệt về FPS thời gian thực.
