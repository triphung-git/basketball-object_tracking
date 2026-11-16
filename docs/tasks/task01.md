# Task01 — Đầu vào, môi trường và runtime

> Bằng chứng baseline v1 giữ nguyên. Từ 2026-11-02, triển khai tiếp theo theo [PLAN v2](../../PLAN.md) và [task index](README.md); PASS task01 không có nghĩa automatic PRA đã xây xong.

Trạng thái: **DONE**. Dự kiến: ngày 1. Phụ thuộc: không.

## Tái nghiệm thu 2026-11-01

PASS theo [báo cáo nghiệm thu task01–02](../reports/task01-task02-acceptance.md). Đã đối chiếu 18 ảnh/87 detections cũ và chạy mới 3 frame của clip02 sau khi người dùng cho phép xác thực/truy xuất model qua Roboflow; inference local ONNX CPU, median model-call mới 724,0 ms. Chưa nghiệm thu hoàn toàn offline hoặc real-time. Bản vá Windows, chống dùng nhầm holdout và validator đã có regression; tổng suite 31 tests pass. [Bàn giao task03](../handoffs/task03.md) yêu cầu baseline giữ đủ frame, không tự skip-frame.

## Cập nhật triển khai 2026-10-31

- Mã nguồn/cấu hình/scripts nằm trong `codebase/`; tài liệu cần đọc trước sửa code nằm trong `docs/`, bắt đầu từ [DEVELOPMENT.md](../DEVELOPMENT.md).
- Đã tạo công cụ kiểm tra môi trường `codebase/scripts/check_environment.py`, mẫu biến môi trường và quy tắc bảo mật key/video/outputs.
- Đã cài đặt CPython 3.12.14 riêng trong `codebase/.tools/python`, tạo `.venv` và cài đặt `inference-models[onnx-cpu]==0.39.7`.
- Đã thực thi smoke test thành công trên 18 frame từ 3 video thử nghiệm, sinh 18 ảnh overlay và `smoke.json` tại `codebase/outputs/smoke-20261031-215143/`.
- Chi tiết nghiệm thu: xem [báo cáo smoke test](../reports/task01-smoke.md) và [báo cáo môi trường](../reports/environment.md).

## Tiến độ sau khi nhận video mẫu

- [x] Đọc tài liệu hiện có; bổ sung code dưới codebase và báo cáo dưới docs.
- [x] Kiểm tra đủ 3 video tại assets_test, giải mã toàn bộ và xem ảnh lấy mẫu; xem [video-inspection.md](../reports/video-inspection.md).
- [x] Cài Python 3.12.14 riêng, tạo .venv và runtime ONNX CPU; import runtime và dependency check pass.
- [x] Cung cấp script smoke model, kiểm tra 5 contract tests pass và khóa phiên bản môi trường đã cài.
- [x] Cấu hình key cục bộ, chạy đúng model `phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1` và lưu output thật.
- [x] Xác minh class mapping `0: ball`, `1: human`, `2: rim`, kiểm tra bbox trên clip và đo baseline latency (median 490.4 ms).

## Mục tiêu thực hiện

Chứng minh model đã chỉ định có thể inference trong môi trường thực tế; chốt phạm vi và baseline trước khi xây tracking.

## Bạn cần cung cấp

- CPU, GPU/VRAM, RAM, OS; quyền cài dependency trong thư mục dự án.
- 2–3 clip mẫu; chọn camera cố định, một rổ, một bóng.
- Quyền truy cập model; tự đặt API key qua biến môi trường nếu runtime yêu cầu.
- Chế độ tính điểm; mặc định cá nhân, 2 điểm/lượt. Việc chưa có webcam không chặn MP4.

## Tôi sẽ thực hiện

1. Kiểm tra Python, GPU và khả năng đọc video; chọn Python theo compatibility runtime, không cài phiên bản mới nhất một cách mặc định.
2. Tạo môi trường riêng và dependency tối thiểu; kiểm tra tài liệu deployment hiện hành cho đúng YOLO26s/model ID.
3. Thử đúng model trên một số frame có bóng/rổ/người. Kiểm tra schema, class ID/name, tọa độ, confidence và lỗi truy cập.
4. Ưu tiên local nếu hỗ trợ; endpoint mạng chỉ làm phương án phù hợp sau kiểm tra quyền, chi phí và độ trễ. Không thay model khác âm thầm.
5. Đo thời gian khởi tạo riêng, inference sau warm-up riêng; ghi cấu hình ảnh và máy.
6. Chốt runtime, scope, version dependency và quyết định tiếp tục/điều chỉnh.

## Đầu ra

- `docs/reports/environment.md`: máy, runtime, model ID, phiên bản, lỗi và lựa chọn.
- `requirements.txt`, `.env.example`, `.gitignore` ban đầu; không chứa key.
- Smoke test tối thiểu và ảnh kết quả trong `outputs/smoke/`.
- Baseline độ trễ inference; không gọi đó là FPS end-to-end.

## Nghiệm thu
 
- [x] Từ môi trường dự án, gọi được đúng model `phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1` và nhận detections hợp lệ trên cả 3 clip mẫu (18/18 frame, 87 detections).
- [x] Xác nhận mapping `0: ball`, `1: human`, `2: rim` từ metadata mô hình thật; không hard-code ID chưa kiểm tra.
- [x] Ghi rõ local/remote (suy luận local qua ONNX Runtime CPU, tải weights qua Roboflow API một lần duy nhất vào `.model-cache/`).
- [x] Có quyết định về runtime: chọn ONNX CPU (`CPUExecutionProvider`) làm baseline offline; median cũ 490.4 ms, run nhỏ tái kiểm tra 724.0 ms. Skip-frame/tracker chưa được nghiệm thu; không áp dụng mặc định vì có thể mất khoảnh khắc bóng qua rổ.

## Bàn giao và giới hạn

Task03 nhận adapter contract: frame BGR + timestamp đầu vào; detections ở tọa độ frame gốc đầu ra. Chưa yêu cầu tracking hay scoreboard. Nếu không deploy được đúng model, ưu tiên giải quyết trước khi tiếp tục pipeline hoàn chỉnh.
