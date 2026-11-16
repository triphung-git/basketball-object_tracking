# Handoff task03 → task04

Ngày 2026-11-02. G03 pipeline được kiểm thử; G04 nhận contracts kỹ thuật, không nhận predictions như ground truth. Trạng thái integration/timing mới nhất tại [report G03](../reports/task03-pipeline.md) và [nghiệm thu chung](../reports/task03-task04-acceptance.md).

## Files cần đọc

- [Contracts v2.0.1](../specs/contracts-v2.md).
- [Source package](../../codebase/src/basketball_scoreboard/app.py) và [default config](../../codebase/configs/default.yaml).
- [Annotation guide](../data/ANNOTATION_GUIDE-v2.md), [rule profile draft](../specs/rules-v2.md), [protocol draft](../specs/evaluation-protocol-v2.md).

## Input bàn giao

Clip02: assets_test/20521993-uhd_2160_3840_60fps.mp4, SHA-256
`3ed25e1b246ccebbe7904d76a22fbea65ebfcb86701499417cd52962f1fc4c26`.

Run gốc task03-clip02-full được giữ làm lịch sử; run sau sửa lỗi nằm ở outputs/acceptance-20261102/g03-clip02-verified. Dùng run.json của đúng run, không trộn metrics/artifacts giữa hai phiên bản.

Mỗi dòng detections.jsonl tương ứng một frame, kể cả rỗng. Tọa độ theo original_wh. Map class từ runtime run.json; baseline hiện ball/human/rim=0/1/2. Source time dùng frame.pts × frame.time_base chuẩn hóa, không raw_pts × stream.time_base cho mọi frame. Đọc timestamp_status và timestamp_policy trước dùng làm nhãn.

MP4 mới xuất timestamp tường minh microsecond, có regression VFR đọc lại; không dàn đều theo FPS trung bình. Flag repaired/estimated không phải bằng chứng PTS gốc. Kết quả full-run và readback phải xem report, không khẳng định mọi video đều PTS hợp lệ.

## Lệnh từ codebase

```powershell
.venv/Scripts/python.exe src/basketball_scoreboard/app.py --video assets_test/20521993-uhd_2160_3840_60fps.mp4 --output-dir outputs/new-clip02-run
.venv/Scripts/python.exe scripts/validate_dataset_v2.py --require-tooling-ready
```

Output directory phải mới. --max-frames chỉ là prefix test, không chứng minh đọc toàn clip. Không inference clip04–07/test/reserve; app kiểm tra hash, không chỉ filename. Key giữ cục bộ; runtime chỉ tải metadata/weights đúng model rồi inference local.

## Ranh giới GT

Gán nhãn độc lập từ video và source PTS; detections chỉ hỗ trợ quan sát. Không suy made/rebound/assist hay tên cầu thủ từ metadata/notes của manifest. V2 manifest ID trên clip02 trùng filename stem, v1 dùng clip02; liên kết bằng source hash.

G04 hiện nhận đủ 9 templates và validator nhưng roster/labels/coverage thật bằng 0. Rules/protocol còn draft; handoff này không phê duyệt dữ liệu hoặc tự khóa split.
