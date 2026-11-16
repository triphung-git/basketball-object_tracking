# Nghiệm thu và bàn giao task03–04

2026-11-02 — MVP v2 automatic points/rebounds/assists. Người dùng đã đồng ý sửa rule sai, để profile/protocol chờ chốt áp dụng 3x3 và bàn giao công cụ trong khi chờ dữ liệu thật.

## Kết luận từng task

| Task/gate | Kết quả | Phần bàn giao |
|---|---|---|
| Task03 / G03 | **PASS, DONE** | Pipeline offline, contracts, tests và integration/readback trên toàn clip02 |
| Task04 / tooling | **PASS** | Prepare/validator, 9 templates, guide, draft rules/protocol và tests |
| Task04 / data, locked | **Chưa đạt, IN_PROGRESS** | 0 roster/labels/coverage approved, thiếu footage hai đội, rules/protocol/provenance và split freeze |

Không nghiệm thu toàn bộ G04 hoặc tuyên bố đầy đủ luật 3x3. Engines PRA, heatmap, tracking, evaluator/dashboard chưa được triển khai. Task05–15 giữ TODO; chỉ phần kỹ thuật độc lập có thể được chuẩn bị, chưa nghiệm thu phần phụ thuộc dữ liệu.

## Ma trận yêu cầu → bằng chứng

| Yêu cầu | Bằng chứng | Kết quả |
|---|---|---|
| Đọc toàn video, JSONL liên tục, MP4 mở lại | 1089 source/JSON/export frames, 2160×3840; independent audit | PASS |
| Source PTS và VFR export | Per-frame timebase, explicit writer timestamps; VFR readback regression | PASS |
| Tọa độ/mapping/config/runtime | Bounds/confidence/class checks toàn JSONL, run snapshot | PASS |
| Lỗi init/writer không completed giả, không lộ SDK message | Regression tests failed/partial và credential scan | PASS trong phạm vi Python errors/artifacts đã scan |
| Dataset v2 schemas/refs/finite/reviews/coverage | Validator và independent fixtures positive/negative | PASS tooling |
| Split leakage/lock tampering | Session/camera/source_group/hash checks; external lock fixtures | PASS tooling; dữ liệu split thật chưa frozen |
| GT thật đủ PRA, roster và full-reviewed coverage | Manifest 7 video; 0 labels/player approved, test v2 rỗng | PENDING |
| Rules applicability và evaluation protocol | Đã sửa FT-assist; draft/pending, schema extension còn chờ | PENDING |
| V1 không đổi | 6/6 SHA-256 trùng snapshot nghiệm thu 2026-11-01 | PASS |

## Commands và kiểm thử thực tế

Từ workspace root:

```powershell
codebase/.venv/Scripts/python.exe -m unittest discover -s codebase/tests -v
codebase/.venv/Scripts/python.exe codebase/scripts/validate_dataset.py --require-ready
codebase/.venv/Scripts/python.exe codebase/scripts/validate_dataset_v2.py --require-tooling-ready
codebase/.venv/Scripts/python.exe codebase/scripts/validate_dataset_v2.py --require-data-ready
codebase/.venv/Scripts/python.exe codebase/scripts/validate_dataset_v2.py --require-locked
```

| Kiểm tra | Exit thực tế | Kết quả |
|---|---|---|
| 92 unit/contract/regression tests, 57.633s | 0 | PASS |
| V1 pilot ready | 0 | PASS; không chứng minh v2 |
| V2 tooling ready | 0 | PASS |
| V2 data ready | 2 | Từ chối đúng kỳ vọng |
| V2 locked ready | 3 | Từ chối đúng kỳ vọng |
| Full actual-model pipeline | 0 | completed |
| Independent full readback | 0 | PASS |

Logs/evidence: [unittest-verified.log](../../codebase/outputs/acceptance-20261102/unittest-verified.log), [gate-checks.json](../../codebase/outputs/acceptance-20261102/gate-checks.json), [v2 validation](../../codebase/outputs/acceptance-20261102/v2-handoff-validation.json), [G03 audit](../../codebase/outputs/acceptance-20261102/g03-independent-audit.json), [handoff snapshot](../../codebase/outputs/acceptance-20261102/handoff-snapshot.json).

Synthetic tests có một dataset hợp lệ đạt locked gate và các ca missing headers/nonfinite/cross-video refs/duplicate IDs/same-session/source-group leakage/review thiếu/coverage hở/zero positives/lock tamper. Chúng nằm ngoài dữ liệu thật; không tính là labels đã review.

## Integration và hiệu năng

Run mới: [run.json](../../codebase/outputs/acceptance-20261102/g03-clip02-verified/run.json); 1089 frames, 3045 detections, 1.80 pipeline FPS, model-call median/mean 294.65/348.02ms. Timestamp statuses valid=1086, repaired=3, sai số export so JSONL tối đa 0.000000000s. PTS nguồn trùng ở frame1086; frame1086–1088 được sửa theo policy trên đồng hồ microsecond; preserved_vfr_mapping=false. Không khẳng định bảo toàn nguyên vẹn PTS nguồn tại frame đã sửa. [Report G03](task03-pipeline.md) có timing scope, nguồn/hash/config và giới hạn.

Model/backend không đổi; inference local, không upload video hay cloud inference. CPU chưa đạt FPS nguồn. Số 4.52FPS thuộc run lịch sử, không gán cho code mới. Đã giữ nguyên run cũ và run bị ngắt/prefix, phân biệt rõ evidence completed.

## Các lỗi đã sửa và phạm vi thay đổi

- G03: VFR writer, frame timebase, strict missing PTS, microsecond timestamp collision (phát hiện bằng full readback, sửa và rerun), runtime class mapping, safe init failure, override validation, output paths, cleanup và holdout hash safeguards.
- G04: header validation, finite timestamps, actor/team/shot/pass cross-references và chronology, approved dependencies, provenance/source-group leakage, reviewed coverage, lock fingerprints và các readiness gates riêng.
- Prepare: không auto-invent roster/session; không ghi đè manifest kể cả --force; giữ curated metadata theo hash, template không chứa labels giả.
- V2 scaffold: bỏ 6 player ví dụ, thêm positions/identities/control templates, đánh provenance pending và rules/protocol draft. Không sửa dữ liệu v1.
- Docs: sửa diễn giải FT assist, N/A khi mẫu số 0, matching one-to-one và ánh xạ ID prediction↔GT; sửa homography dùng landmarks mặt sân. Protocol vẫn là thiết kế, chưa có evaluator task13.

Source/config/scripts/tests ở codebase; báo cáo/spec/handoff ở docs. Code/docs và dataset hashes được ghi trong acceptance snapshot; không hash .env hoặc đưa key vào report. Credential scan không thấy key trong các files source/docs/new acceptance JSON/logs đã kiểm tra; không phải kiểm toán toàn máy.

## Phần chờ để đóng G04

Footage hai đội mới, development/test tách session, roster và identity evidence, landmarks mặt sân, nhãn PRA/control/pass/positions cùng coverage đã review, rules áp dụng giải và protocol được duyệt. Cần extension typed FT-series/foul/possession trước freeze. Mục tiêu thu thập ≥50 shots/≥30 REB positives/≥30 AST positives và hard negatives chưa đạt.

Unknown provenance phải được review, split/labels không tự locked. Không chuyển holdout v1 thành development; không bịa nhãn hoặc nhập stats thủ công để thay recognition.

## Bàn giao

- [G03 pipeline report](task03-pipeline.md).
- [Task03→04](../handoffs/task03-to-task04.md).
- [Data v2 và readiness](data-v2.md).
- [Task04→05/06, điều kiện mở phần phụ thuộc](../handoffs/task04-to-task05-06.md).
- [Contracts](../specs/contracts-v2.md), [rules draft](../specs/rules-v2.md), [protocol draft](../specs/evaluation-protocol-v2.md), [annotation guide](../data/ANNOTATION_GUIDE-v2.md).

Bàn giao kỹ thuật hoàn tất trong phạm vi nêu trên; **G04 còn mở**, không gọi cả hai task DONE.
