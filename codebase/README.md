# Spatial video pipeline

Codebase hiện chỉ xử lý video, phát hiện đối tượng, human tracking, hiệu chuẩn
mặt sân, bản đồ 2D và heatmap. Pipeline không tính hoặc hiển thị points, shots,
assists, rebounds, possession, event ledger hay box score.

## Luồng xử lý

1. `src/basketball_scoreboard/app.py`: đọc video và ghi detection artifacts.
2. `scripts/track_players.py`: tạo track, bbox và quan sát người.
3. `src/basketball_scoreboard/spatial_analysis.py`: chiếu vị trí lên mặt sân
   theo hiệu chuẩn và dựng heatmap từ các quan sát hợp lệ.
4. `src/basketball_scoreboard/dashboard.py`: phục vụ video, bbox, bản đồ 2D
   và heatmap trong giao diện cục bộ.

Orchestration gọn nằm tại `scripts/run_spatial_pipeline.py`; `scripts/run_demo.py`
khởi chạy phân tích hoặc dashboard. Hiệu chuẩn chỉ hợp lệ cho nguồn/camera tương
ứng. Khi không có hiệu chuẩn phù hợp, tracking vẫn chạy nhưng không sinh tọa độ
vật lý hoặc heatmap.

## Kiểm thử

```powershell
.venv\Scripts\python.exe -m pytest `
  tests\test_spatial_analysis.py `
  tests\test_run_spatial_pipeline.py `
  tests\test_web_video_upload.py `
  tests\test_task03_pipeline.py `
  tests\test_task05_court_heatmap.py `
  tests\test_task06_players_identity.py -q
```

Các bài kiểm thử xác minh hành vi phần mềm, không thay thế benchmark độ chính xác
trên ground truth của video thực tế. Không có kết quả benchmark mới nào được suy
ra từ lần loại bỏ pipeline thống kê này.
