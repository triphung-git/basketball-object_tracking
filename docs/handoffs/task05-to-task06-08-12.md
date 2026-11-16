# Checkpoint bàn giao Task05 → Task06 /08 /12

**Cập nhật 2026-11-04:** [Task07 implementation và demo 3x3](../reports/task07-ball-possession.md) đã có; [handoff task08–10](task07-to-task08-09-10.md). OCR local đã chạy, còn geometry/identity/control GT acceptance. Clip04 development và exposure nhóm cùng trận đã được người dùng [phê duyệt riêng](../decisions/20261104-clip04-development-exposure.md); không coi nhóm này là untouched holdout ở đánh giá mới.

Tái kiểm chứng 2026-11-03. **G05-T PASS; G05-G PENDING; G05-I diagnostic PASS.** Checkpoint này không biến synthetic geometry thành calibration thật. Xem [report task05](../reports/task05-court-heatmap.md) và [nghiệm thu chung](../reports/task05-task06-acceptance.md).

## Input và contracts

Source G03 verified: codebase/outputs/acceptance-20261102/g03-clip02-verified. Dùng source hash/run metadata, source_time_s và original_wh. Clip02 có1089 frames; frame1086–1088 repaired, không gọi là PTS nguyên vẹn.

[Source court](../../codebase/src/basketball_scoreboard/court.py), [heatmap](../../codebase/src/basketball_scoreboard/heatmap.py), [spatial loader](../../codebase/src/basketball_scoreboard/spatial_io.py), [spec](../specs/court-heatmap-v2.md).

Observation lưu raw bbox/image footpoint và source/run/video/segment/camera, projected point nullable, calibration digest, sample/validity/role, optional track/team/player. Bbox bottom là estimate, không phải chân chạm đất đã biết. Empty ROI không phải full image, ROI không xác nhận player role.

## Task06 tiếp nhận gì

Tracker dùng valid source dimensions/clock và ROI; role unknown khi thiếu evidence. Khi missing detection, predicted samples phải được giữ để ngắt chuỗi, không project thành valid observed hoặc bỏ mất rồi nối hai đầu còn lại.

Đầu ra task06 có track IDs thực; trackless G03 observations trước tracker không được ghép theo bbox order để tính mass. Court version có digest; cut/calibration change không nối stream. Task06 không dùng annotations làm identity runtime input.

Checkpoint task05 đã có tests/preview/contracts/readback trước bàn giao phần tracking. Sau review độc lập, các thiếu sót core đã được sửa và toàn bộ153 tests pass; source/outputs mới ở acceptance-20261103-task05-06-review. Không lấy14 tests cũ làm chứng minh mọi edge case đúng.

## Heatmap API cho Task12

HeatmapAccumulator nhận batch trajectories; observed+valid+stable track và player role cho main view. Diagnostic có thể chứa unknown humans nhưng phải gắn scope. Hai endpoints kề nhau phải eligible; prediction/invalid/cut/gap là barriers.

reset/recompute từ raw logs phục vụ replay/seek/reload. Chưa có persisted streaming checkpoint engine; caller không giả định non-overlapping chunks tự nối. Mapping override dict là offline whole-track correction explicit, không phải causal identity inference. Versioned run mới giữ provenance/revisions.

## Geometry cho Task08

Chưa có landmarks/visible-foot GT được duyệt; không có arc/shot-value geometry thật để bàn giao PASS. Các số trong synthetic fixture không phải kích thước đo của clip02. Chọn floor landmarks coplanar, không dùng rim trên cao. Chân airborne/bbox bottom không đủ tự xác định shot value ở release.

## Evidence và điều kiện mở data gate

[Audit](../../codebase/outputs/acceptance-20261103-task05-06-review/audit.json) chứng minh source/dataset preservation, grids/mass và gates. Raw trackless mass0; integrated diagnostic12.116667s chỉ là unknown-human occupancy trên synthetic geometry.

Cần≥4 correspondences mặt sân phân bố tốt, orientation/units/ROI/source kiểm chứng, independent check points và visible-foot GT. G05-G chưa đóng. Team/identity và OCR thuộc gate task06, không kéo toàn task05 về manual stats hoặc bịa matrix để vượt gate.

Handoff tiếp sau task06: [task07/08/12](task06-to-task07-08-12.md).

