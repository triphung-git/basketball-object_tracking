# Bàn giao để bắt đầu task03 — 2026-11-01

## Trạng thái đầu vào

Task01 PASS và task02 PASS cho pilot, xem [nghiệm thu](../reports/task01-task02-acceptance.md). Task03 vẫn TODO, chưa có pipeline app hoàn chỉnh. Bàn giao này xác định hợp đồng triển khai, không phải tính năng đã được xây.

Đọc DEVELOPMENT.md, PLAN.md, tasks/task03.md, báo cáo nghiệm thu và docs dữ liệu trước sửa code. Mã nguồn/config/tests trong codebase; tài liệu trong docs. Không đọc/in nội dung .env.

## Những gì đã sẵn sàng

| Thành phần | Giá trị / vị trí |
|---|---|
| Python | codebase/.venv/Scripts/python.exe, 3.12.14 |
| Model | phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1 |
| Runtime | inference-models 0.39.7, ONNX CPU, CPUExecutionProvider |
| Class metadata đã kiểm chứng | 0 ball, 1 human, 2 rim; vẫn lấy mapping từ runtime khi load |
| Runtime tham khảo | codebase/scripts/smoke_model.py; có compatibility cache Windows đã test |
| Clip phát triển mặc định | clip02: assets_test/20521993-uhd_2160_3840_60fps.mp4 |
| Clip02 metadata | 2160×3840, 60 FPS, 1089 frames, 18,15s; PTS đều |
| Nhãn và coverage | codebase/data/annotations/*.csv, không dùng làm input detector |
| Split khóa | codebase/data/splits.json; calibration clip02, test clip04–07 |
| Model-call CPU | Cũ median 490 ms; tái chạy 3 samples median 724 ms; không phải end-to-end |

Tải/auth metadata Roboflow có thể cần mạng dù inference local. Lần offline hoàn toàn gần nhất chưa thành công. Hỏi người dùng nếu muốn đổi deployment/backend hoặc cài CUDA; không đổi model để né lỗi.

## Công việc task03

1. Xây reader đọc frame tuần tự, ghi index và source_time_s đúng nguồn. Với clip02 CFR có thể đối chiếu index/FPS với PTS; với clip04–07 VFR phải dùng PTS. Dùng decoder hiện có hỗ trợ timestamps (PyAV đã nằm trong môi trường) nếu phù hợp; không tự thêm dependency nặng.
2. Tách detector adapter khỏi CLI: nhận frame BGR và source timestamp, trả detections xyxy ở frame gốc, class_id/class_name/confidence. Chia sẻ loader/compatibility đã kiểm thử khi cần, tránh nhân bản monkeypatch hoặc tắt checksum.
3. Config có input/output, đúng model ID, threshold, inference resize, backend/device và policy export. Chưa có cơ sở áp dụng threshold riêng hoặc skip-frame tự động.
4. Overlay bbox/class/confidence, index và source time; giữ tỷ lệ dọc, không kéo dãn ảnh.
5. CLI app chạy hết một video, tạo run directory mới, xuất annotated.mp4, detections.jsonl và run.json; cleanup EOF/lỗi/quit.
6. Ghi latency của toàn pipeline đúng phạm vi, tách model-call. Mục tiêu đầu là offline đúng và tái lập, chưa cam kết live real-time.

## Hợp đồng thời gian và video export

- source_time_s là thời gian nội dung video, không phải thời gian inference trên máy. Không dùng time.time() làm đồng hồ scoring.
- Clip04–07 có bước PTS khoảng 33,3–70,0 ms; avg_fps chỉ là metadata trung bình. Các số frame trong notes nhãn không phải timebase chuẩn.
- Với baseline task03 trên clip02, giữ mọi frame, export 60 FPS để giữ thời lượng nội dung dù xử lý chậm. Audio không bắt buộc theo MVP.
- Nếu hỗ trợ export VFR, phải bảo toàn timestamps hoặc ghi rõ policy resample và mapping; không chỉ ghi mọi frame VFR bằng avg_fps rồi tuyên bố giữ đúng timing. Chưa cần chạy holdout để phát triển phần này: dùng fixture VFR tổng hợp hoặc metadata audit.

## Các artifact cần có

- src/basketball_scoreboard/{app,config,video,detector,overlay}.py và configs/default.yaml, đường dẫn tương đối codebase.
- outputs/<run_id>/annotated.mp4: mở được, đúng tỷ lệ/nhịp nội dung baseline.
- detections.jsonl: video_id/filename, frame_index, source_time_s, original_wh, detections; không bỏ dòng frame có 0 detections nếu cần truy vết đầy đủ.
- run.json: model/backend/device/versions, input fingerprint, frame counts, resize/threshold, timebase/export policy, timings, status completed/failed; không key hoặc URL auth.
- README lệnh chạy thực tế và báo cáo task03; tests tập trung contract tọa độ/timestamp/lỗi, không mirror implementation.

## Chặn rò rỉ và bảo vệ dữ liệu

Không chạy detector/scoring trên clip04–07 để debug hoặc chọn threshold. Chỉ dùng chúng khi bước evaluation đã được chốt. Smoke script hiện tự chặn locked test nhưng pipeline mới cũng phải tuân thủ split/policy.

Manifest notes có mô tả kết quả từng pha. Detector/scoring không được đọc notes, events hoặc reviews để suy kết quả; chỉ dùng source path và metadata kỹ thuật. Evaluation mới so sánh với labels.

Không chỉnh nhãn/coverage/split để làm kết quả đẹp hơn. Chỉnh dữ liệu đã khóa phải có revision và người dùng duyệt. Không tự chia nhỏ session test sang calibration; không dùng replay như pha mới. Giữ video, outputs task01 và snapshots nghiệm thu.

## Bước bắt đầu có thể tái chạy

Từ gốc workspace:

```powershell
codebase/.venv/Scripts/python.exe codebase/scripts/validate_dataset.py --require-ready
codebase/.venv/Scripts/python.exe -m unittest discover -s codebase/tests -v
```

Validator phải pass với cảnh báo pilot nhỏ. Nếu chạy lại model để kiểm tra sau sửa loader, dùng clip02 qua --video-name và run directory mới; key chỉ cấu hình local. Không cần inference lại toàn bộ smoke chỉ để bắt đầu viết pipeline.

## Tiêu chí nghiệm thu task03

- Chạy hết clip02 và đọc lại MP4 đầu ra; frame count/độ phân giải/tỷ lệ/timebase hợp lệ.
- Bbox overlay và JSON thống nhất, mapping từ metadata, source timestamps tăng đơn điệu.
- Không detection, input sai, lỗi model và lỗi writer được xử lý rõ; không sinh success report cho run thiếu.
- Ghi đủ config/versions/fingerprint/thời gian cho tái chạy; không lộ secrets.
- Báo FPS xử lý thật và phạm vi đo; không gán video phát mượt thành inference real-time.

Không thêm tracking hoặc scoring vào task03. Bàn giao detections + source timestamp để task04 dùng tiếp.
