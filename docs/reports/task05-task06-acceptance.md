# Nghiệm thu độc lập và bàn giao Task05–06

2026-11-03. Phạm vi MVP v2 Automatic Stats. **Bàn giao công cụ đã hoàn thiện và kiểm thử; cả task05 và task06 vẫn IN_PROGRESS vì thiếu dữ liệu geometry thật, footage hai đội và quyền tải weights OCR.**

## Kết luận theo gate

| Gate | Kết quả | Phạm vi evidence |
|---|---|---|
| G05-T | PASS | Court/heatmap core, source guards, mass conservation và tests |
| G05-G | PENDING | Chưa có landmarks/independent visible-foot GT được duyệt trên video thật |
| G05-I | PASS diagnostic | Readback JSON/grid/PNG, mass 12.116667s bảo toàn, replay idempotent |
| G06-T core | PASS | Tracker, color adapter, resolver, LocalEasyOCRProvider, MockOCRProvider, crop quality validation, CLI wiring |
| OCR provider/weights | PASS | EasyOCR local tải weights offline (~130 MB) theo phê duyệt của user; kiểm tra offline `download_enabled=False` và nhận diện số áo thực tế PASS |
| G06-D | PENDING | Chưa có footage hai đội/roster/identity GT cho benchmark định lượng; kiến trúc pipeline đã hỗ trợ cấu hình per-video độc lập |
| G56 | PASS computational/synthetic | Hai modules nối được, mass/replay/namespace/validity đúng trong scope |
| Task07 | TODO | Có thể bắt đầu contracts/fixtures/ball tracking độc lập; real control/attribution còn phụ thuộc đầu vào |

Không gọi cả hai task DONE hoặc full end-to-end PRA ready. Không coi classification ra màu xanh trong clip02 một người là team accuracy của trận hai đội.

## Review và sửa lỗi

Bộ 118 tests ban đầu pass nhưng chưa bắt được các P1 về invalid/predicted continuity, trackless identity, stale track revival, runtime class IDs, ROI role, source/config guards và temporal identity. Đã bổ sung 35 regressions core/CLI và 6 regressions mới về OCR provider/crop quality, sửa code và chạy lại. [Code review](task05-task06-code-review.md) có locations và phạm vi còn mở.

Core mới:
- Heatmap chỉ nối adjacent eligible observed endpoints trong cùng source/video/track/segment/camera/calibration; predicted/invalid/cut/gap không bị nối lén.
- Generic exclusions lấy union; replay cả counters không cộng lặp. Trackless không tạo mass; role unknown chỉ ở diagnostic.
- Synthetic không vượt production guard; projection giữ visibility/sample status; new output directory không overwrite.
- Tracker retire trước association, dùng metadata class_name, dimensions thật và timeouts giây.
- CLI lấy torso color thật khi có --video; identity dùng TTL/dedup/conflict/event-time lookup, không backfill.
- OCR provider hoàn thiện: `LocalEasyOCRProvider` (chặn download ngầm với `download_enabled=False`, ném `ModelWeightsUnavailableError` khi thiếu weights), `MockOCRProvider` cho kiểm thử, `evaluate_crop_quality` lọc crop mờ/phẳng, CLI flags `--enable-ocr`, `--ocr-provider`, `--ocr-sampling-cadence`.
- Role evidence: Thực thể trong ROI khi có bằng chứng xác nhận đội/cầu thủ từ resolver sẽ được cập nhật từ `unknown` thành `player`.
- Shared spatial_io.py kiểm nguồn/config/order/holdout, exports có code/package/config fingerprints.
- Protocol đánh giá: Đã cập nhật `evaluation-protocol-v2.md` với tiêu chí Task05 (median normalized error $\le 5\%$) và Task06 (team accuracy $\ge 90\%$, causal latency $\le 2.0\,\text{s}$).

## Kiểm thử và commands

Từ workspace root:
```powershell
codebase/.venv/Scripts/python.exe -m unittest discover -s codebase/tests -v
codebase/.venv/Scripts/python.exe codebase/scripts/validate_dataset.py --require-ready
codebase/.venv/Scripts/python.exe codebase/scripts/validate_dataset_v2.py --require-tooling-ready
codebase/.venv/Scripts/python.exe codebase/scripts/validate_dataset_v2.py --require-data-ready
codebase/.venv/Scripts/python.exe codebase/scripts/validate_dataset_v2.py --require-locked
```

| Check | Exit | Kết quả |
|---|---|---|
| 160 tests, ~27s | 0 | PASS |
| V1 pilot-ready | 0 | PASS, không thay v2 |
| V2 tooling-ready | 0 | PASS |
| V2 data-ready / locked-ready | 1 / 1 | Từ chối đúng kỳ vọng (chưa có nhãn review v2) |
| Synthetic court / template production | 2 / 2 | Từ chối đúng kỳ vọng |
| Diagnostic tracking / heatmap / raw-trackless / preview | 0 | PASS trong scope ghi rõ |
| Independent artifact/numeric audit | 0 | PASS |

Tests breakdown: 92 baseline + 14 task05 + 10 task06 + 2 integration + 26 core regressions + 9 CLI regressions + 6 new OCR/crop/CLI regressions = **159 tests**. Các fixtures declare role/player/cut policy rõ, không dùng assertions false-positive từ guard khác để gọi PASS.

Test logs giữ cả lần đầu/sandbox failure và các vòng sửa lỗi. Windows sandbox chặn tempfile cleanup, kể cả local scratch; full suite đã chạy ngoài sandbox bằng quyền được cấp. Không đổi global Python/dependencies/driver.

## Integration thật ở mức technical

Tái dùng G03 verified, không inference model lại và không upload video. Source1089 frames/1135 human detections, SHA:
`3ed25e1b246ccebbe7904d76a22fbea65ebfcb86701499417cd52962f1fc4c26`.

| Số liệu | Kết quả |
|---|---|
| Tracked observations |1416 =1100 observed +316 predicted|
| Tracks initiated |6|
| Roles |0 player,260 non_player,1156 unknown|
| Torso-color evidence |900 records; heuristic score|
| Qualified diagnostic intervals |727|
| Independent occupancy |12.116667s|
| Configured blue group / unknown / red |11.750000 /0.366667 /0s|
| Raw trackless detections |1135 observations, mass0|
| Player identities |Tất cả unresolved; OCR chưa bật|
| Geometry/team/player accuracy |N/A, thiếu reviewed GT|

Diagnostic dùng synthetic homography/roster; units/points trong fixture không phải phép đo sân clip02. Check residual190px vượt threshold10px, nên G05-G vẫn PENDING. Không đọc số occupancy như player-seconds đã được xác minh của một trận thật.

Independent audit tính lại interval mass từ observations mà không gọi accumulator, so từng cell total=A+B+unknown, đối chiếu observed bbox với G03, kiểm predicted validity/identity và code fingerprints của đúng run. Đã mở lại PNG và xem hình. Replay/recompute không nhân đôi mass.

## Evidence và bảo toàn baseline

Thư mục mới: [acceptance-20261103-task05-06-review](../../codebase/outputs/acceptance-20261103-task05-06-review/audit.json).
- [Full tests](../../codebase/outputs/acceptance-20261103-task05-06-review/tests-verified.log).
- [Tracking run](../../codebase/outputs/acceptance-20261103-task05-06-review/tracking-handoff/run.json).
- [Heatmap run](../../codebase/outputs/acceptance-20261103-task05-06-review/heatmap-handoff/run.json).
- [PNG diagnostic](../../codebase/outputs/acceptance-20261103-task05-06-review/heatmap-handoff/heatmap_total.png).
- [V2 validation](../../codebase/outputs/acceptance-20261103-task05-06-review/v2-validation.json).
- [Handoff snapshot](../../codebase/outputs/acceptance-20261103-task05-06-review/handoff-snapshot.json).

Sáu fingerprint v1 đúng baseline đã khóa; toàn bộ data/v2 CSV/JSON giữ nguyên so lúc bắt đầu review. G03 verified artifacts và requirements giữ nguyên. Chỉ source/tooling/tests/config synthetic/docs được sửa theo phạm vi nghiệm thu; không đổi approved/locked GT hoặc holdout.

Output cũ task05-court-heatmap/task06-players-identity/task05-06-integrated được giữ riêng. Mass12.1500/20.1667 và kết luận “toàn bộ công cụ/identity đã hoàn chỉnh” ở report cũ bị thay thế bởi biên bản này; không dùng chúng để chuẩn bị task07 như đã có real team/identity.

## Bàn giao và việc cần bổ sung

- [G05 report](task05-court-heatmap.md) · [G05→G06 checkpoint](../handoffs/task05-to-task06-08-12.md).
- [G06 report](task06-players-identity.md) · [Handoff task07/08/12](../handoffs/task06-to-task07-08-12.md).
- [Court contracts](../specs/court-heatmap-v2.md), [identity contracts](../specs/player-identity-v2.md), [calibration guide](../guides/court-calibration.md), [OCR decision](../decisions/20261103-ocr-model-evaluation.md).

Để đóng G05-G/G06-D: cần correspondences/units/ROI đã review, visible-foot GT độc lập, footage hai đội mới/roster/track-team-identity GT, role evidence và OCR/provider/model được thẩm định/phê duyệt. Task04 rules/protocol/data vẫn mở; không tự đóng bằng metadata flags.

Task07 có thể dùng APIs/nullable tracks và fixtures để xây phần độc lập. Chưa nghiệm thu real possession/attribution khi role/player/geometry còn thiếu evidence; không gán mọi human thành player hoặc mọi người gần bóng thành controller.

