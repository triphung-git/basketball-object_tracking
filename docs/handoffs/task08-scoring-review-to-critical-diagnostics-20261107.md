# Bàn giao review scoring → diagnostic các thời điểm quan trọng

Ngày 2026-11-07. [Report tiếp nhận](../reports/task08-scoring-review-intake-20261107.md). Người dùng đã review đủ 34 clip, xác nhận liên kết lại play_027/028 và cung cấp các case còn lại. **34 metadata nhất quán; không còn case chờ đội/người ném đối lập.** Không train, đổi model hoặc sửa engine trong đợt này.

## Nguồn hiện hành

- Raw review: `codebase/outputs/task08-scoreboard-review-20261106/vietnam-tonga-scoring-review.json`, SHA `1ca130edea0c9b6862fd210476256dba8dfda05dbf80baa3dda095313918a696`. Không sửa trực tiếp.
- Packet gốc/manifest cùng folder, SHA manifest `153eb12d779add28dff51d38c873107913d2eb1955bd36d63cfff2da9a5ce665`. Media source/clip hashes đã kiểm.
- Root intake: `codebase/outputs/task08-scoring-intake-20261107/`. Root summary giữ 29/5, adjudicated-v2 giữ 31/3; **latest là `adjudicated-v3/summary.json` với 34/0**.
- `adjudicated-v3/events-reviewed.json` giữ tất cả, `events-consistent-subset.json` có cả 34 metadata; `conflicts.json` không còn event.
- `resolutions-confirmed-v3-20261107.json`: toàn bộ xác nhận user, ràng buộc raw hash/manifest. Dẫn xuất `review-derived-after-resolutions.json` giữ timestamp source khi đổi clip, không được ghi đè raw export.
- `adjudicated-v3/critical-windows-draft.json`: 10 cửa sổ không đổi; `evidence-reuse.json` trỏ tới `adjudicated-v2/critical-frame-index.json`, `critical-frames/`, `critical-moments-1/2/3.jpg`: 40 ảnh nguồn được tái sử dụng, không phải predictions/bbox GT.

## Các xác nhận đã chốt

1. play_009: Tonga #11 (TGA4–VIE6→TGA5–VIE6).
2. play_024: Tonga #9 (12–15→13–15).
3. play_034: Việt Nam #6, field goal (19–20→19–21); bỏ mốc FT Tonga ở đầu clip trong bản dẫn xuất, release/basket target hiện null.

Không hỏi lại các xác nhận trên hoặc swap 027/028. Còn 2 shooter null ở 002/005 và 21 clip không có paired times là optional fields, không phải lỗi schema. Không bắt người dùng review lại 34 clip. Loại cú ném hiện là 26 field goal / 8 FT theo nhãn đã sửa, không phải automatic stats.

## Việc độc lập tiếp theo

1. Freeze config/model/runtime trước diagnostic; dùng approved ONNX CPU cùng weights, không thêm pose/ReID/model mới âm thầm.
2. Chạy baseline trên 10 cửa sổ đã có mốc rõ: 001/003/004/006/008/015/021/023/027/028. Ghi rõ selection dựa trên review times, nên đây là conditional diagnostic, không phải blind test hay end-to-end shot discovery.
3. Tách raw ball candidates, selected observed ball, predicted/missing và actor evidence; không dùng expected shooter/score/notes hoặc bbox GT trong recognition. Bóng có thể rời người trong flight; FT006 có thay đổi bố cục camera.
4. Chuẩn bị nhãn bbox tối thiểu tại release/rim sau khi xem raw predictions; báo coverage partial/unknown, không đo recall bằng cách coi mọi ball candidate là đúng. Hiện bbox GT=0 nên chưa có IoU metric mới.
5. Phân loại thiếu candidate vs association chọn sai vs actor/identity sai trước sửa. Giữ observed/predicted tách biệt và chỉ xác nhận score bằng bằng chứng quan sát nhiều frame.
6. Cần negative cohort miss/rim-bounce/replay trước made/miss precision; tập hiện tại chỉ có user-confirmed positives. Không đổi gate Task07/08 hoặc đánh dấu DONE vì importer tests pass.

Importer mới: `codebase/scripts/ingest_scoring_review.py`; tests `codebase/tests/test_scoring_review_intake.py` đạt 15 tests +10 subtests. Source của engine tracking/detection/identity và nhãn control cũ giữ nguyên. Task07 IN_PROGRESS, Task08 TODO.
