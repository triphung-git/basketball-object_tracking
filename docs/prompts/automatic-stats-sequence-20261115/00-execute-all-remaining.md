# Prompt tổng — Thực thi toàn bộ phần còn lại sau đợt 01

Bạn là kỹ sư phụ trách hoàn thiện project Automatic Basketball Stats trong workspace hiện tại. **Thực thi trực tiếp toàn bộ 9 task còn lại từ 02A đến 06B**, theo chuỗi dưới đây. Sửa code/config, chạy tests và pipeline thật, kiểm outputs, viết report/handoff và tiếp tục đến nghiệm thu trong phạm vi đã duyệt. Không dừng ở kế hoạch, tạo thêm prompt hoặc bàn giao sau một đợt đã PASS.

Đợt 01 đã được người dùng thông báo hoàn tất. Xác minh checkpoint/handoff một lần; không làm lại toàn bộ 01A/01B/01C. Nếu có regression thật ảnh hưởng chuỗi mới, tái hiện và khắc phục trước khi đi tiếp, lưu evidence mới.

## 1. Phạm vi giao việc và thứ tự bắt buộc

Đọc [execution-contract.md](execution-contract.md), [review hiện trạng](../../reports/project-status-review-20261115.md), PLAN/MVP, AGENTS.md áp dụng nếu có và các quyết định/authorization hiện hành. Sau đó đọc prompt chi tiết tương ứng khi bắt đầu mỗi đợt:

| Thứ tự | Task | Công việc | Prompt chi tiết |
|---|---|---|---|
| 1 | 02A | Continuous MP4 → detection/tracking/team/OCR/identity/ball/control/pass | [Đợt 02](02-continuous-video-pipeline.md) |
| 2 | 02B | Orchestration shots/points/rebounds/assists → ledger/heatmap/output bundle | [Đợt 02](02-continuous-video-pipeline.md) |
| 3 | 03A | Shared production evaluator đầy đủ PTS/REB/AST | [Đợt 03](03-evaluator-dataset-freeze.md) |
| 4 | 03B | Hợp nhất reviewed GT/roster/geometry/rules/protocol, data readiness và freeze | [Đợt 03](03-evaluator-dataset-freeze.md) |
| 5 | 04A | Baseline → error analysis → cải thiện có giới hạn → paired downstream decision | [Đợt 04](04-recognition-quality.md) |
| 6 | 05A | Dashboard/video/evidence/heatmap thật, API/export/browser checks | [Đợt 05](05-dashboard-benchmark.md) |
| 7 | 05B | Benchmark toàn production pipeline, latencies và giới hạn runtime | [Đợt 05](05-dashboard-benchmark.md) |
| 8 | 06A | Frozen strict quality evaluation trước correction | [Đợt 06](06-final-evaluation-delivery.md) |
| 9 | 06B | Đóng gói, tài liệu, clean-run và nghiệm thu cuối | [Đợt 06](06-final-evaluation-delivery.md) |

**Lệnh này giao cả đợt 02–06.** Các câu “không tự triển khai đợt sau”, “không mở đợt X trong lượt này” hoặc “chưa được giao đợt sau” trong prompt chi tiết chỉ giới hạn cách giao từng đợt riêng lẻ; không phải lý do dừng khi đang thực thi prompt tổng này. Sau checkpoint PASS, tự chuyển đến task kế tiếp trong bảng mà không hỏi lại có tiếp tục hay không.

Ngoại lệ này chỉ mở rộng phạm vi task được giao. Mọi requirements, test gates, input/quality gates, bảo vệ dữ liệu/model/authorization và điều kiện 06B vẫn giữ nguyên. Không được bỏ qua gate vì mục tiêu “hoàn thành tất cả”.

Chuỗi này hoàn thiện các phần còn mở của Task04–15 trong PLAN, không phải chạy lại baseline Task01–03. Duy trì acceptance crosswalk giữa task nhỏ 02A–06B và Task04–15 để không bỏ sót geometry/team/identity/control/pass, FT/rules, REB/AST, ledger, UI, quality, runtime và packaging. Hạng mục chưa có evidence vẫn IN_PROGRESS dù module đã tồn tại.

## 2. Preflight một lần và điểm bắt đầu

1. Đọc `docs/handoffs/sequence-01C-20261115.md`, reports 01A/B/C, checkpoints và logs/JUnit dưới `codebase/outputs/sequence-01-20261115/`. Đối chiếu checkpoint với file thực, không tin mỗi chữ PASS trong Markdown.
2. Inventory source/config/runtime/authorization hiện tại; kiểm có thay đổi sau snapshot hay không. Test count 439 pass/1 skip và 12 snapshot defects đã sửa là evidence lịch sử cần đối chiếu, không phải số bắt buộc đạt đúng.
3. Không chạy lại mọi inference/test cũ ở preflight. Tái sử dụng evidence còn áp dụng; recheck phần bị source/config/data changes ảnh hưởng. Chạy tests bắt buộc của task hiện tại theo execution contract.
4. Inputs khởi đầu đã biết, xác minh lại sự tồn tại/hash/binding trước dùng:
   - Source: `codebase/assets_test/vietnam-tonga.mp4`.
   - Development clip: `codebase/outputs/task07-vietnam-tonga-segments-20261104/media/vt_development.mp4`, đoạn parent 300–330s; giữ clip-local/source-global offsets rõ.
   - Roster: `codebase/configs/rosters/vietnam_tonga.json`.
   - Segment declaration: `codebase/configs/segments/vietnam_tonga_task07.json`.
   - ROI/cut policy: `codebase/outputs/task07-vietnam-tonga-segments-20261104/vt_development-policy-masked.json`; ROI ảnh không phải metric court calibration. Áp dụng cuts đúng PTS/source binding.
   - Interpreter: `codebase/.venv/Scripts/python.exe`; approved detector mặc định ONNX CPU; OCR local/weights và authorization đọc từ handoff hiện hành.
5. Chưa cần footage mới hoặc fine-tune để xây integration đợt 02. Chọn continuous development range trước khi xem recognition results. Không dùng validation/test như calibration hoặc ngầm fallback sang cached selected windows.
6. Court reviewed/source-matched geometry thiếu thì đợt 02 được xuất diagnostic/unavailable đúng phạm vi. Không dùng việc đó để vượt geometry/data/quality gates ở 03B và 06A.

## 3. Vòng thực thi bắt buộc cho từng task

Với MỖI task, thực hiện đúng trình tự:

1. Xác minh predecessor checkpoint và inputs của task hiện tại.
2. Ghi acceptance checklist cụ thể, tái hiện requirement/defect trên production path.
3. Implement đầy đủ phần task; tái sử dụng core contracts/APIs hiện có.
4. Chạy tests mục tiêu và independent probes được yêu cầu. Nếu sửa production/shared code, chạy full suite sau thay đổi cuối theo execution contract. Lưu stdout/stderr/JUnit/exit code gốc.
5. Chạy entrypoint thật với input phù hợp, output directory mới. Synthetic chỉ cho logic/plumbing có nhãn rõ, không thay real-video integration hoặc real GT accuracy.
6. Kiểm nghiệp vụ output độc lập: source PTS/frame counts/binding, event dependencies/lifecycle, auto totals, checkpoint/raw replay, coverage/unresolved và trạng thái failed/partial/completed theo scope.
7. Lưu đủ `checkpoint.json`, `commands.json`, `artifacts.json`, raw outputs, report và handoff. Đối chiếu file bắt buộc tồn tại, parse được và hashes/version đúng.
8. Chỉ khi checklist của task PASS mới cập nhật tiến độ và mở task kế tiếp. Test fail, smoke fail, missing artifacts hoặc report placeholder thì tiếp tục sửa task hiện tại.

Không “implement cả chuỗi rồi test cuối”. Không coi hoàn thành code là hoàn thành task. Không xóa/skip/xfail probes, sửa GT/golden/threshold hoặc bịa events để đạt PASS. No-events run hợp lệ cho plumbing phải báo no-events, không tự suy là recognition đạt.

Từ stream tới REB/AST, shot-kind/FT-series/action context cần evidence runtime/rules profile. Thiếu context phải unknown/unresolved; không dùng defaults, tên pha hoặc review metadata để tự tạo sự chắc chắn.

## 4. Trạng thái bền vững để tiếp tục qua nhiều lượt

Tạo một run root mới, ví dụ `codebase/outputs/remaining-tasks-<run_id>/`, lưu `execution-state.json` và `acceptance-matrix.json`. Thay `<run_id>` bằng giá trị thật, không overwrite evidence cũ.

`execution-state.json` tối thiểu gồm:

- `schema_version`, `run_id`, `updated_utc`, `current_task`, `next_task`.
- Danh sách 9 task theo thứ tự: status `NOT_STARTED|IN_PROGRESS|PASS|FAIL|PENDING_INPUT`, attempt, checkpoint/report/handoff paths và hashes.
- Predecessor reference; code/config/model/data/rules/protocol fingerprints phù hợp mỗi task.
- Tests/real-run evidence references, quality gate riêng, unresolved blockers và next concrete action.

Cập nhật an toàn sau checkpoint hoặc blocker; state file là mục lục evidence, không thay checkpoint/tests. Report/handoff đặt dưới docs theo quy trình chung và link về run root.

Nếu context bị thu gọn, tiến trình gián đoạn hoặc chuyển lượt: đọc lại prompt tổng, state và checkpoint task cuối. Resume task chưa hoàn tất đầu tiên; không khởi động lại toàn chuỗi và không bỏ qua failures. Nếu có thay đổi thực sự làm evidence cũ mất hiệu lực, revalidate các checks/dependencies bị ảnh hưởng và tạo attempt mới; giữ lịch sử cũ.

Sau mỗi task PASS, thông báo ngắn kết quả tests/run và task tiếp theo rồi tiếp tục làm việc. Không kết thúc chỉ vì hết một đợt, phải chờ process dài hoặc cần cập nhật tài liệu. Một prompt không bảo đảm process tồn tại qua shutdown; ghi state/log/checkpoint để có thể resume chính xác.

## 5. Khi thiếu đầu vào hoặc quality gate chưa đạt

- Thiếu đầu vào: trước hết tìm trong source/review packets/decisions/authorization và tận dụng confirmations đã có. Chỉ hỏi phần thật sự chưa có bằng video/timestamp/actor/rule case cụ thể; không yêu cầu xác nhận lại roster/nhãn đã được duyệt.
- Riêng 03B, thực hiện [bổ sung chuẩn bị review packets](03B-prepare-review-packets.md) để phân biệt collection target với hard policy, validate đúng proposal/active revision và tạo clips/rules/split/calibration proposal có thể review trước khi yêu cầu người dùng xử lý. Công việc này vẫn thuộc 03B, không cho phép mở 04A trước gate.
- Có thể hỏi sớm inputs cho task sau trong khi hoàn thiện task hiện tại; không bắt đầu task mới trước predecessor PASS. Thời gian chờ không thay approval.
- Hoàn thành tooling/tests/review packet/report thuộc task hiện tại trong phạm vi làm được. Nếu thiếu input bắt buộc vẫn chưa giải quyết được, ghi `PENDING_INPUT`, missing list/evidence/next action đầy đủ và dừng ở đúng gate. Không mở task sau hoặc báo “toàn bộ hoàn tất”.
- Fail do lỗi code/runtime trong phạm vi đã giao: tái hiện, sửa, chạy lại checks phù hợp rồi tiếp tục; không chỉ báo fail và dừng khi vẫn có thể khắc phục.
- 04A là một experiment task có phạm vi hữu hạn. Measurement bundle có thể hoàn tất với `quality_gate=FAIL` và giữ baseline; được tiếp tục UI/benchmark 05A/05B đúng định nghĩa gate kỹ thuật. Không được từ đó suy ra recognition đã accepted.
- 06A là gate sản phẩm: thiếu GT hợp lệ hoặc strict PTS/REB/AST chưa đạt thì không mở 06B. Lưu failed evaluation đầy đủ; sửa trên calibration trong quyền đã có và chỉ tái nghiệm thu bằng protocol/reserve phù hợp. Không tuning trên test vừa thất bại rồi gọi lại independent PASS; cần revision/input mới thì giữ blocker cụ thể.
- Không tự mở training job dài, đổi default model/backend, cài GPU stack/dependency lớn, sửa locked datasets, upload/charge/publish. Dùng authorization đã có đúng phạm vi; nếu cần quyền mới, chuẩn bị đề xuất cụ thể có thể review và chỉ hỏi phần phụ thuộc đó.

## 6. Điều kiện hoàn tất toàn chuỗi

Chỉ báo hoàn tất khi mọi task 02A–06B có checkpoint phù hợp và đủ artifacts, đồng thời:

1. Continuous video path thực sự gọi detection/tracking/identity/control/pass và đủ shots/points/rebounds/assists, không chỉ cache replay.
2. Dataset/rules/protocol/geometry/roster và exposure/lock hợp lệ; full PRA evaluator dùng chung production/tests; predictions trước correction có provenance.
3. Frozen quality gate đạt từng PTS/REB/AST precision ≥95%, recall ≥90% theo protocol và các gate identity/team/heatmap hiện hành; N/A không được PASS.
4. Ledger/boxscore/audit/checkpoint/replay đúng; UI/video/evidence/export/browser checks PASS; E2E benchmark dùng đúng production profile với giới hạn offline/live minh bạch.
5. Clean-run theo README/user guide thành công, output bundle đầy đủ, required suite/probes PASS sau thay đổi cuối, report/acceptance matrix/PLAN/task statuses khớp evidence và links hợp lệ.

Bàn giao cuối bằng tiếng Việt: bảng từng task với verdict và links; tests thực tế; raw quality/performance; demo/clean-run command; run bundle/user guide/final report/acceptance links; limitations và blockers nếu chưa đạt. Không lấy output corrected thay auto, không tuyên bố hoàn tất từ số lượng tests hoặc thời gian đã làm.

**Bắt đầu ngay bằng preflight và 02A; sau mỗi checkpoint PASS tiếp tục task kế tiếp đến 06B, trừ blocker/gate thực sự chưa thể đáp ứng. Không chỉ trả lời kế hoạch và không tạo thêm prompt thay việc thực thi.**
