# Hướng dẫn chạy demo sau QA — 16/11/2026

Bản hiện tại là **DEMO_PARTIAL**. Có thể trình diễn video overlay, tracking, OCR, pha ném trượt, heatmap và xuất dữ liệu. Chưa đủ bằng chứng để nghiệm thu tự động cả PTS/REB/AST hoặc chất lượng AI. Xem [báo cáo QA](reports/qa-project-review-20261116.md).

## Mở demo

Tại thư mục gốc, nhấp đúp `run_demo.bat` hoặc chạy:

```powershell
.\run_demo.bat
```

Launcher dùng Python có sẵn trong `codebase/.venv`, mở trình duyệt và ưu tiên bundle `codebase/outputs/demo-completion-20261116/demo-bundle-qa-v2`. Nếu cổng 8080 bận, URL thực tế sẽ được in ra. Ctrl+C để đóng server.

Kiểm tra bundle mà không mở server:

```powershell
codebase/.venv/Scripts/python.exe run_demo.py --check
```

Checksum được kiểm tra thật. Bundle thiếu hoặc bị sửa sẽ báo lỗi; không tự bỏ qua dữ liệu hỏng.

## Nội dung demo đã kiểm tra

- Đoạn nguồn: **300–305 giây**, 151 frame. Clip overlay dài khoảng **5,033 giây**, bắt đầu từ 0.
- Timeline hiển thị thời gian nguồn. Nhấp `SHOT (MISS)` để xem lại pha ném; việc tua được quy đổi sang thời gian clip.
- Heatmap thật: **17,40 person-seconds**, khối lượng được bảo toàn. Có PNG và raw grid để kiểm tra.
- Boxscore của đoạn này: **0 PTS, 0 REB, 0 AST được xác nhận**. Đây là thống kê sự kiện hệ thống chấp nhận trong đoạn đã xử lý, không phải tỷ số toàn trận trên bảng điểm truyền hình.
- `shots_auto.jsonl` có 1 pha ném trượt. `events_auto.jsonl` rỗng là hợp lệ: pha trượt được hiển thị riêng, không tự tăng PTS/REB/AST.
- OCR có 2 lần đọc số 18; chưa đủ để khẳng định đã nhận diện đúng toàn bộ cầu thủ.
- Chỉ số `DEMO_PARTIAL` và `NOT_ACCEPTED` trên giao diện thể hiện giới hạn hiện tại.

Các nút Export tải CSV boxscore, JSONL ledger và JSON summary. `/api/heatmap/image` cung cấp ảnh heatmap. Giao diện hoạt động offline khi môi trường và các weights đã có sẵn.

## Phân tích lại video

Dùng thư mục output mới cho mỗi lần chạy:

```powershell
codebase/.venv/Scripts/python.exe run_demo.py --mode video-analysis --video "codebase/assets_test/vietnam-tonga.mp4" --court "codebase/configs/courts/vt_development_court.json" --roster "codebase/configs/rosters/vietnam_tonga.json" --start-time-s 300 --end-time-s 305 --output "codebase/outputs/my-new-run" --serve --open-browser
```

Lệnh tạo video overlay, raw logs, shots, ledger, boxscore, trajectories, heatmap và summary. `--host`/`--port` áp dụng cho server; `--port 0` để hệ điều hành chọn cổng trống.

Nếu chỉ kiểm tra downstream bằng detection đã có:

```powershell
codebase/.venv/Scripts/python.exe run_demo.py --mode video-analysis --video "codebase/assets_test/vietnam-tonga.mp4" --court "codebase/configs/courts/vt_development_court.json" --roster "codebase/configs/rosters/vietnam_tonga.json" --start-time-s 300 --end-time-s 305 --detections-cache "codebase/outputs/qa-review-20261116/clean-run/detections.jsonl" --disable-ocr --output "codebase/outputs/my-new-cache-run"
```

Cache replay không đo hiệu năng detector và không thay thế kiểm tra OCR. Geometry của clip development chỉ được dùng lại trên nguồn đúng hash và khoảng 300–330 giây theo manifest hiện có. `--require-calibrated` từ chối request nằm ngoài phạm vi này; mặc định có thể chạy diagnostic nhưng không sinh tọa độ mét từ calibration sai nguồn.

## Tốc độ và giới hạn

Không dùng con số 46,2 FPS trong benchmark cũ để công bố tốc độ inference đầy đủ. Đó là profile dùng cached detections. Lần QA chạy trực tiếp có OCR mất 242,70 giây cho request 300–305 giây, gồm khởi tạo và giải mã prefix; chưa đạt realtime. Xem timings từng run, không so các profile như cùng một điều kiện đo.

Những việc còn cần để demo đủ PRA: cải thiện ball/control/identity, có video thật sinh sự kiện được xác nhận cho cả PTS/REB/AST, kiểm tra attribution, rồi đánh giá bằng GT và nguồn độc lập phù hợp. Model fine-tune gần rổ hiện chưa đủ điều kiện thay baseline.

## Khi gặp lỗi

- **Output already exists:** chọn thư mục mới, giữ nguyên evidence cũ.
- **Checksum/SHA mismatch:** giữ bundle lỗi để kiểm tra; tạo bundle mới từ run hợp lệ, không sửa manifest để bỏ qua lỗi.
- **Video/heatmap không có:** đọc `run.json` và `heatmap_summary.json`; geometry không phù hợp sẽ được báo diagnostic.
- **Python không tìm thấy:** dùng đúng `codebase/.venv/Scripts/python.exe`. Không cần cài thêm dependencies để xem bundle đã có.

Chạy toàn bộ kiểm thử từ thư mục gốc:

```powershell
codebase/.venv/Scripts/python.exe -m pytest codebase/tests -q
```

Hoặc từ `codebase`: `.venv/Scripts/python.exe -m pytest tests -q`. Các test artifact đã được sửa để không phụ thuộc thư mục chạy.
