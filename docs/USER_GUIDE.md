# Hướng dẫn sử dụng

Ứng dụng xử lý video và spatial analysis: detection, bbox, human tracking, hiệu
chuẩn sân, bản đồ 2D và heatmap. Ứng dụng không tính hoặc hiển thị points,
assists, rebounds, shots, possession, event timeline hay box score.

## Chạy phân tích video

Từ PowerShell tại thư mục gốc, dùng video nguồn và output directory mới:

```powershell
.\run_demo.bat --mode video-analysis `
  --video "C:\path\to\game.mp4" `
  --output "codebase\outputs\spatial-run" `
  --court "codebase\configs\courts\vt_development_court.json" `
  --serve --open-browser
```

`--court` là tùy chọn. Chỉ dùng cấu hình đúng camera/nguồn video. Không có hiệu
chuẩn phù hợp thì detection và tracking vẫn chạy, nhưng không sinh tọa độ sân
hoặc heatmap. Mỗi lần chạy cần một output directory chưa tồn tại để tránh ghi
đè artifacts cũ.

Để chạy mà không mở dashboard, bỏ `--serve --open-browser`. Có thể giới hạn
khung hình với `--max-frames` khi kiểm tra nhanh; kết quả giới hạn không đại diện
cho toàn bộ video.

## Mở dashboard cục bộ

```powershell
codebase\.venv\Scripts\python.exe codebase\scripts\run_dashboard.py `
  --host 127.0.0.1 --port 8080
```

Mở URL được in trên terminal. Dashboard cho phép tải MP4, chạy detection và
tracking, xem video cùng bbox, gán người/đội thủ công, hiệu chuẩn sân và dựng
bản đồ không gian. Nếu cấu hình hiệu chuẩn hoặc danh tính thay đổi, hãy lưu cấu
hình rồi cập nhật spatial map.

Để mở kết quả đã lưu:

```powershell
codebase\.venv\Scripts\python.exe codebase\scripts\run_dashboard.py `
  --run-dir "codebase\outputs\spatial-run"
```

Video có thể phát song song với overlay bbox. Heatmap và tọa độ 2D chỉ có ý nghĩa
khi calibration hợp lệ, các quan sát có timestamp hợp lệ và track đủ ổn định.
Các track dự đoán, khoảng mất dấu dài hoặc điểm chân không hợp lệ không được nối
thành vị trí vật lý.

## Kết quả và giới hạn

- Detection: `detection/detections.jsonl`.
- Human tracking: `tracking/tracked_observations.jsonl`.
- Bbox overlay: `web_overlay.json`.
- Heatmap/summary: `heatmap/` khi có court configuration.
- Bản đồ 2D được dựng riêng từ tracking và hiệu chuẩn đã lưu.

Không có pipeline sự kiện hoặc bảng thống kê trong giao diện/API hiện hành.
Kiểm thử phần mềm không chứng minh độ chính xác của model. Muốn xác nhận chất
lượng detection, tracking, projection hoặc heatmap cần ground truth đã rà soát,
đo precision/recall, ID switches và sai số vị trí trên video/camera đích.
