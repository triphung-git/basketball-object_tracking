# Task03 — Pipeline detection và video

Trạng thái: TODO. Dự kiến: ngày 2. Phụ thuộc: task01 và clip từ task02.

Đầu vào đã bàn giao 2026-11-01: task01 PASS, task02 PASS cho pilot. Đọc [hợp đồng triển khai task03](../handoffs/task03.md) và [nghiệm thu](../reports/task01-task02-acceptance.md). Bắt đầu bằng clip02; không dùng clip04–07 đã khóa để debug. Broadcast là VFR, cần PTS khi hỗ trợ nguồn này. Chưa triển khai task03 trong đợt nghiệm thu.

## Mục tiêu

Chạy hết một video bằng đúng model và xuất kết quả có thể kiểm tra, trước khi thêm logic ghi điểm.

## Bạn cần cung cấp

Clip mẫu hợp lệ, cấu hình truy cập model từ task01; phản hồi nếu bóng/rổ trong overlay bị gán sai rõ ràng.

## Tôi sẽ xây dựng

1. `video.py`: đọc frame theo thứ tự, frame index, source timestamp; xử lý EOF và giải phóng tài nguyên.
2. `detector.py`: adapter runtime đã chốt; chuẩn hóa `xyxy`, class, confidence; đổi tọa độ crop/resize về frame gốc.
3. `config.py`: cấu hình model ID, input/output, threshold và kích thước inference; kiểm tra dữ liệu đầu vào.
4. `overlay.py`: bbox, class/confidence, số frame và thời gian video.
5. `app.py`: nối pipeline, tạo run directory riêng, ghi video đầu ra và metadata; lỗi đọc/ghi/inference phải rõ nguyên nhân.
6. Log detections tối thiểu có timestamp để phân tích bóng mất ở đâu; tránh log ảnh/base64 hoặc bí mật.

## Đầu ra

- Các module trên, `configs/default.yaml`.
- `outputs/<run_id>/annotated.mp4`, `detections.jsonl`, `run.json` chứa cấu hình, model và thống kê xử lý.
- Câu lệnh chạy trong README; giao diện CLI cụ thể chốt khi triển khai.

## Nghiệm thu

- [ ] Chạy hết ít nhất một MP4, video đầu ra mở được, đúng tỷ lệ khung hình.
- [ ] Bbox nằm đúng đối tượng sau resize/crop; class mapping đúng.
- [ ] Frame không có detection không gây crash; đường dẫn sai và lỗi model có thông báo hữu ích.
- [ ] Thứ tự frame và source timestamp ổn định, không phụ thuộc tốc độ xử lý máy.
- [ ] Ghi tốc độ toàn pipeline sơ bộ; chưa suy diễn thành live real-time.

## Kiểm tra và bàn giao

Xem trực tiếp frame có bóng nhỏ, bóng gần vành và không có bóng. So sánh tọa độ log với overlay. Task04 nhận detections và timestamp thống nhất. Chưa thêm web UI, async phức tạp hay scoring vào adapter.
