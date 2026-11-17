# Tái nghiệm thu Task05 — court/heatmap

2026-11-03. **IN_PROGRESS — công cụ được kiểm chứng, geometry/GT thật còn pending.**

| Gate | Kết quả | Evidence |
|---|---|---|
| G05-T | PASS trong phạm vi công cụ | 14 tests task05 và regressions mới trong suite153 tests |
| G05-G | PENDING | Chưa có landmarks/visible-foot GT độc lập được duyệt |
| G05-I | PASS diagnostic; chưa nghiệm thu court thật | Readback JSON/grid/PNG và independent integration |

## Thay đổi sau review

Đã sửa lỗi nối các observation còn lại sau khi filter invalid, cộng predicted samples, ghép trackless humans thành một trajectory, namespace thiếu video/calibration, trừ exclusions overlap hai lần và counters replay tăng lặp. Cut là ranh giới ngắt interval; generic exclusions mới được clip theo union.

Court synthetic trước đây đi qua production guard; giờ cần --allow-uncalibrated. Empty ROI không phải toàn ảnh. Source hash/dimensions/runtime mapping và thứ tự PTS được kiểm tra bởi spatial_io.py. Projection không nâng predicted/occluded thành valid. Config digest phân biệt các calibration cùng schema; CLI không ghi đè directory/preview.

Bản guide cũ có origin/landmark coordinates không nhất quán đã được sửa. Không có kết luận sân clip02 đúng scale chỉ từ fixture.

## Input và output nghiệm thu mới

Nguồn detections giữ nguyên tại outputs/acceptance-20261102/g03-clip02-verified; 1089 frames,1135 human detections. Không inference lại model.

Output mới: outputs/acceptance-20261103-task05-06-review/.
- raw-trackless-verified/:1135 observations, mass0. Không có stable track IDs nên không tích lũy trajectory.
- tracking-handoff/ → heatmap-handoff/:1416 tracked observations,1100 observed/316 predicted.
- court-preview.png: preview synthetic với points/ROI/grid, không phải calibration thật.
- audit.json: independent numeric verification; tests-verified.log:153 tests PASS,7.748s.

Independent audit chọn727 intervals hợp lệ trên timeline, loại predicted/invalid boundaries và kiểm tra mass **12.116667s**. Đây là **diagnostic unknown-human occupancy** trên synthetic court, chưa là player-seconds của trận đã nhận diện. Configured blue-color group11.750000s; unknown0.366667s; red0s. Không dùng các số này làm team/player accuracy.

PNG mở lại được, đã xem hình; grid/readback/source fingerprints khớp. Unknown role được cho vào diagnostic bằng flag; production main heatmap chỉ nhận role=player có evidence. Geometry/position error thật=N/A. Fixture check residual190px vượt threshold10px, không được dùng để PASS G05-G.

## Lệnh từ workspace root

```powershell
codebase/.venv/Scripts/python.exe -m unittest discover -s codebase/tests -v
codebase/.venv/Scripts/python.exe codebase/scripts/court_tool.py --config codebase/configs/courts/synthetic_half_court.json
codebase/.venv/Scripts/python.exe codebase/scripts/court_tool.py --config codebase/configs/courts/synthetic_half_court.json --allow-uncalibrated --preview codebase/outputs/new-court-preview.png
codebase/.venv/Scripts/python.exe codebase/scripts/generate_heatmap.py --court-config codebase/configs/courts/synthetic_half_court.json --detections codebase/outputs/acceptance-20261103-task05-06-review/tracking-handoff/tracked_observations.jsonl --run-json codebase/outputs/acceptance-20261102/g03-clip02-verified/run.json --allow-uncalibrated --verify-replay --output-dir codebase/outputs/new-heatmap-run
```

Court synthetic production guard exit2; diagnostic preview/heatmap exit0. Output paths new-* là hướng dẫn tái chạy, phải dùng directory mới. Các paths thực đã chạy nằm trong [audit](../../codebase/outputs/acceptance-20261103-task05-06-review/audit.json).

## Checkpoint và phần chờ

Checkpoint G05 bàn giao contracts/API/fixtures cho task06, không giả G05-G PASS để vượt phụ thuộc. Cần ≥4 correspondences mặt sân phân bố tốt, orientation/units/scale/source xác minh, independent check points và reviewed visible-foot GT. Median error≤5% chưa đo.

outputs/task05-court-heatmap và task05-06-integrated cũ được giữ làm lịch sử. Mass12.1500/20.1667 cũ không dùng nghiệm thu do trackless/prediction/continuity defects.

[Court calibration guide](../guides/court-calibration.md) · [Spatial contract](../specs/court-heatmap-v2.md).

