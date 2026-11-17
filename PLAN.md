# Kế hoạch spatial-only

## Mục tiêu

Giữ một pipeline gọn để:

1. Đọc video và phát hiện đối tượng theo từng frame.
2. Theo dõi người, duy trì bbox/track ID và hỗ trợ gán danh tính thủ công.
3. Hiệu chuẩn court theo đúng video/camera.
4. Chiếu quan sát lên bản đồ 2D và tạo heatmap chỉ từ vị trí hợp lệ.
5. Xem video, bbox và kết quả không gian trong dashboard local.

Pipeline không xử lý points, shots, assists, rebounds, possession, event ledger,
box score hay các chỉ số thi đấu khác. Những module, API, UI, tests, configs,
scripts và tài liệu kỹ thuật của pipeline đó đã được đưa ra khỏi scope.

## Kiến trúc hiện tại

```text
MP4
 └─ detection: app.run_pipeline
     └─ human tracking: track_players_pipeline
         ├─ bbox overlay: web_overlay.json
         ├─ court calibration: source-bound geometry
         ├─ spatial map: projected track positions
         └─ heatmap: valid observed occupancy
```

Entrypoints:

- `run_demo.bat --mode video-analysis ...`: phân tích video và tùy chọn mở dashboard.
- `codebase/scripts/run_spatial_pipeline.py`: nối detection, tracking và heatmap.
- `codebase/scripts/run_dashboard.py`: mở dashboard cho video hoặc output đã có.

## Bảo toàn chất lượng không gian

- Không suy diễn court coordinates khi thiếu calibration đúng nguồn.
- Giữ observed/predicted phân biệt; dự đoán không tạo vị trí vật lý.
- Bỏ các quan sát timestamp/footpoint không hợp lệ và không nối qua gap dài.
- Gán danh tính/đội không được làm thay đổi bbox hoặc vị trí ảnh gốc.
- Tái dựng spatial map phải tái lập được từ tracking artifacts và cấu hình đã lưu.

Đây là các guard của pipeline, không phải bằng chứng rằng độ chính xác đã đạt
ngưỡng cụ thể. Chưa có benchmark ground-truth mới chứng minh độ chính xác trên
video thực sau thay đổi. Muốn công bố chất lượng cần tập kiểm tra độc lập theo
camera, GT bbox/track/footpoint, coverage và sai số projection/heatmap.

## Kiểm chứng tối thiểu

```powershell
codebase\.venv\Scripts\python.exe -m pytest `
  codebase\tests\test_spatial_analysis.py `
  codebase\tests\test_run_spatial_pipeline.py `
  codebase\tests\test_web_video_upload.py `
  codebase\tests\test_task03_pipeline.py `
  codebase\tests\test_task05_court_heatmap.py `
  codebase\tests\test_task06_players_identity.py -q
```

## Lộ trình

1. Chạy regression suite cho detection, tracking, calibration, spatial map,
   upload và dashboard.
2. Tạo/duyệt ground truth độc lập cho các camera mục tiêu.
3. Đo detection precision/recall, tracking ID switches/fragmentation, footpoint
   coverage, projection error và heatmap agreement.
4. Chỉ tối ưu model hoặc threshold sau khi có baseline định lượng; không đánh đổi
   detection/tracking để cải thiện heatmap bằng cách lọc dữ liệu quá mức.
