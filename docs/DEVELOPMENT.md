# Ghi chú phát triển

## Phạm vi đang hỗ trợ

Codebase giữ lại xử lý video, detection, human tracking, danh tính/gán đội thủ
công, hiệu chuẩn court, bản đồ 2D và heatmap. Các thành phần tính/nhận dạng/
hiển thị points, shots, assists, rebounds, possession, event ledger, box score
và benchmark riêng cho các chỉ số đó đã được gỡ khỏi mã nguồn và giao diện.

## Luồng chính

```text
MP4
 └─ app.run_pipeline -> detection/
     └─ track_players_pipeline -> tracking/
         ├─ web_overlay.json
         └─ spatial_analysis + court calibration -> spatial_map.json / heatmap/
```

- `scripts/run_spatial_pipeline.py`: nối detection, tracking và heatmap tùy chọn.
- `src/basketball_scoreboard/web_worker.py`: worker upload video spatial-only.
- `src/basketball_scoreboard/web_jobs.py`: trạng thái upload, cấu hình roster/court,
  và dựng lại spatial map.
- `src/basketball_scoreboard/spatial_analysis.py`: projection và heatmap theo
  khoảng thời gian quan sát hợp lệ.
- `src/basketball_scoreboard/dashboard.py`: API/giao diện local cho video, bbox,
  hiệu chuẩn và spatial visualization.

## Kiểm thử

Từ thư mục gốc:

```powershell
codebase\.venv\Scripts\python.exe -m pytest `
  codebase\tests\test_spatial_analysis.py `
  codebase\tests\test_run_spatial_pipeline.py `
  codebase\tests\test_web_video_upload.py `
  codebase\tests\test_task03_pipeline.py `
  codebase\tests\test_task05_court_heatmap.py `
  codebase\tests\test_task06_players_identity.py -q
```

Các tests bao phủ contracts và regression của phần mềm. Chúng không chứng minh
độ chính xác model trên footage mới. Mỗi camera cần calibration phù hợp và
ground-truth đánh giá riêng; không dùng calibration của một nguồn cho nguồn khác.

## Nguyên tắc phát triển

- Dùng timestamp/frame observations gốc; không tạo tọa độ sân từ bbox không hợp lệ.
- Tách observed và predicted; không nối khoảng mất dấu dài thành quỹ đạo vật lý.
- Giữ output mới theo từng run, không ghi đè artifacts cũ.
- Không đưa media riêng tư, model weights hoặc credentials vào Git.
- Không thêm lại logic game-statistics vào spatial pipeline hoặc dashboard.
