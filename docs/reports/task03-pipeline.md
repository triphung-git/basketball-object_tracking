# Nghiệm thu task03 — pipeline video/PTS/detection

Ngày 2026-11-02. **G03 PASS / Task03 DONE** cho nền MP4 offline. Không phải nghiệm thu tracking, heatmap hoặc spatial accuracy.

## Bằng chứng mới sau review

Run: [g03-clip02-verified](../../codebase/outputs/acceptance-20261102/g03-clip02-verified/run.json).
Audit độc lập: [g03-independent-audit.json](../../codebase/outputs/acceptance-20261102/g03-independent-audit.json).
Ảnh source/export: [contact sheet](../../codebase/outputs/acceptance-20261102/g03-readback-contact-sheet.jpg).

| Chỉ số | Kết quả run mới |
|---|---|
| Status / CLI exit | completed / 0 |
| Source decode / JSONL / export decode | 1089 / 1089 / 1089 |
| Kích thước source/export | 2160×3840 |
| Source duration | 18.15 s |
| Detections | 3045; rim=1090, human=1135, ball=820 |
| Timestamp status | valid=1086, repaired=3 |
| Max sai số JSONL so với source PTS (tất cả / chỉ valid) | 0.016667333 / 3.333e-7 s |
| Max sai số export PTS so với JSONL | 0.000000000 s |
| Tổng pipeline | 605.0075 s |
| Pipeline throughput | 1.80 FPS |
| Model-call median / mean | 294.65 / 348.02 ms |
| Model init | 15.6702 s |

Timing model-call gồm runtime preprocessing/inference/postprocessing. Pipeline gồm probe, model init/warmup, decode/resize/draw/JSON/encode và flush; không suy FPS toàn pipeline từ 1/model_latency. Lần này chạy trên máy dùng chung, có kiểm thử đồng thời trong một phần thời gian; đây là run thực tế, chưa là benchmark cô lập để quy nguyên nhân hiệu năng.

Đã decode lại source và MP4 bằng PyAV, so mọi timestamp với JSONL, kiểm tra index/count/kích thước, class mapping, confidence và bbox bounds. Decoder nguồn có PTS trùng tại frame1086 và timeline muộn sau đó; reader sửa các frame1086–1088 trên đồng hồ microsecond, lần lượt thành 18.100000/18.116667/18.133334s. Sai lệch với PTS quan sát khoảng 0.016667s; các frame valid chỉ có sai số làm tròn microsecond. Export khớp timeline sau sửa và run.json ghi preserved_vfr_mapping=false, không tuyên bố giữ nguyên toàn bộ PTS nguồn. Các mẫu frame 0/253/500/1086 có ảnh đối chiếu để review; kiểm tra này không chứng minh detection accuracy hoặc pixel-identical overlay.

## Input, runtime và cấu hình

- Source clip02: assets_test/20521993-uhd_2160_3840_60fps.mp4.
- SHA-256: `3ed25e1b246ccebbe7904d76a22fbea65ebfcb86701499417cd52962f1fc4c26`.
- Model: `phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1`, YOLO26ForObjectDetectionOnnx, CPUExecutionProvider; không đổi model/backend.
- Runtime versions: Python 3.12.14; av 19.0.2; inference-models 0.39.7; opencv-python 5.0.0.93; onnxruntime 1.22.1; torch 2.15.0.
- Config: confidence=0.25, max_edge=1280, warmup=2, cpu_threads=1 (PyTorch), repair_with_audit, H264/yuv420p/veryfast, explicit timestamp timebase 1/1000000.
- Mapping runtime: 0=ball, 1=human, 2=rim; downstream đọc mapping hoặc class_name.
- Source code/config fingerprints và export hashes: [handoff snapshot](../../codebase/outputs/acceptance-20261102/handoff-snapshot.json). Credentials giữ cục bộ, không đưa key vào artifacts.

## Sửa lỗi trong lần nghiệm thu

1. Writer trước đây dàn đều theo FPS trung bình trong khi tài liệu nhận bảo toàn VFR. Đã gán PTS tường minh từ source_time_s, có fixture VFR export/readback.
2. Reader dùng stream timebase cố định; đổi sang frame.time_base, thêm strict reject missing PTS và audit khi phải ước lượng/sửa. Không coi “repaired” là PTS gốc hợp lệ.
3. App đưa model init vào error lifecycle, ghi sanitized stage/exception-class thay raw SDK traceback, đảm bảo cleanup writer/reader với lỗi bắt được.
4. CLI revalidate config sau overrides, chặn export path escape/trùng filename, output directory mới; max-frame prefix có trạng thái partial.
5. Runtime class mapping truyền xuống detection contract; app bảo vệ holdout theo source hash kể cả đổi tên video.
6. Sửa lỗi so sánh float cho phép timestamp tăng 3e-15s nhưng trùng tick microsecond; reader so cùng độ chính xác với JSON/export, writer từ chối tick trùng, có regression chuỗi PTS cuối clip và sub-tick collision.
7. Snapshot timing gồm flush; CPU threads và encoder preset được ghi rõ, không khẳng định thay đổi này làm đạt real-time.

## Kiểm thử

Lệnh từ workspace root:

```powershell
codebase/.venv/Scripts/python.exe -m unittest discover -s codebase/tests -v
codebase/.venv/Scripts/python.exe codebase/src/basketball_scoreboard/app.py --video codebase/assets_test/20521993-uhd_2160_3840_60fps.mp4 --output-dir codebase/outputs/acceptance-20261102/g03-clip02-verified
```

Bộ chung **92 tests PASS**, 57.633s, exit0; [log](../../codebase/outputs/acceptance-20261102/unittest-verified.log). Gồm 31 baseline, 23 pipeline cũ, 11 regressions G03 mới, 9 validator cũ và 18 regressions G04 mới. Không dùng fixtures làm dữ liệu thật.

## Run lịch sử và giới hạn

outputs/task03-clip02-full giữ nguyên: 1089 frames, 3045 detections, 241.01s / 4.52 FPS, median/mean 87.04/96.84ms. Những số này thuộc code/run cũ, không thay số mới và không chứng minh writer cũ bảo toàn VFR. Repair frame1086 đã được tái hiện và xác minh riêng với PTS decoder nguồn. Khẳng định cũ “khớp từng pixel” vượt bằng chứng; report hiện tại dùng timestamp/bbox audit và ảnh mẫu, không cam kết pixel-identical.

outputs/acceptance-20261102/g03-clip02-final đã chạy đủ frame nhưng FAIL audit do timestamp trùng sau lượng tử hóa; giữ nguyên để đối chiếu, được thay bằng g03-clip02-verified sau sửa reader/writer và thêm regression. outputs/acceptance-20261102/g03-clip02 là lần chạy chậm đã ngắt, không dùng nghiệm thu; process bị dừng trên Windows có thể không ghi run.json. g03-thread-check là prefix 5 frame, status partial. Không ghi đè/xóa các output này để che lịch sử.

Chưa đạt real-time 60FPS. Detection/tracking accuracy chưa được đo trên ground truth độc lập. File bị kill/native crash có thể thiếu cleanup/metadata; chỉ run completed và readback pass được coi là evidence đầy đủ.

Tiếp tục theo [kế hoạch spatial-only](../../PLAN.md), [court calibration guide](../guides/court-calibration.md) và [spatial contract](../specs/court-heatmap-v2.md).
