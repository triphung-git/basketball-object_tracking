# Quy trình thực thi và checkpoint bắt buộc

Áp dụng cho mọi prompt trong thư mục này. Đọc trước khi sửa code. Tất cả đường dẫn trong phần nội dung là tương đối với workspace root, trừ các lệnh ghi rõ chạy từ `codebase`.

Nếu người dùng giao [prompt tổng toàn bộ phần còn lại](00-execute-all-remaining.md), cả đợt 02–06 đã được giao. Các giới hạn không chuyển đợt trong prompt riêng chỉ áp dụng khi giao từng đợt độc lập; khi chạy prompt tổng, sau checkpoint PASS phải tiếp tục task/đợt kế tiếp mà không hỏi lại. Quy tắc này không thay đổi test/input/quality gates hoặc quyền đối với dữ liệu/model/tài nguyên.

## 1. Phạm vi và kiểm kê

- Thực thi task được giao: sửa code/config, viết tests có ý nghĩa, chạy tests, chạy thử, đối chiếu output và bàn giao. Không kết thúc ở kế hoạch/pseudocode/prompt mới.
- Đọc AGENTS.md áp dụng nếu có, `docs/reports/project-status-review-20261115.md`, PLAN/MVP, task/specs liên quan và source/tests hiện tại. Các số 405 pass/12 probes fail là snapshot cần xác minh, không phải số phải làm cho khớp.
- Tái sử dụng runtime/core modules hiện có. Inference mặc định: `codebase/.venv/Scripts/python.exe`, approved model `phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1`, ONNX CPU; class mapping phải lấy từ runtime, baseline 0=ball/1=human/2=rim. Không lấy mapping sai trong benchmark làm chuẩn.
- Không tự git init/commit/push. Khi không có Git, lưu SHA-256 source/config thay commit. Không đọc `.env` ra tool output; code local có thể đọc credentials trong bộ nhớ.
- Kiểm tra authorization hiện hành trước inference/evaluation/training. Quyền đã có được giữ; không xin lại review hoặc roster đã được xác nhận. Không tự mở job training mới, đổi default model, cài GPU stack/dependencies lớn, upload media, trả phí, publish hoặc sửa locked data ngoài phạm vi đã cho phép.
- Các prompt là phạm vi giao việc, không tự cấp quyền thay đổi nhãn/split đã khóa hoặc chạy test holdout để debug. Giữ exposure history và các quyết định clip04 hiện hành; không gọi nguồn đã dùng phát triển là untouched holdout.

## 2. Trình tự cho TỪNG task

1. **Preflight:** kiểm checkpoint task trước, inputs, contracts, versions, approvals và tests liên quan. Tạo checklist acceptance riêng; nếu thiếu dependency bắt buộc, dừng trước phần phụ thuộc.
2. **Reproduce:** tái hiện lỗi/task requirement bằng entrypoint/API production và case độc lập phù hợp. Ghi kết quả trước sửa; không ép tests fail khi code hiện tại đã được sửa.
3. **Implement:** thay đổi đúng phạm vi; giữ public contracts hoặc migration/backward compatibility có giải thích. Không dùng GT/notes/window ID làm recognition hints.
4. **Verify:** chạy tests mục tiêu và các probes bắt buộc của task. Task sửa production/shared code phải chạy full suite một lần sau thay đổi cuối; nếu sửa tiếp vì failure thì chạy lại phần bị ảnh hưởng và full suite trước chốt.
5. **Run thực tế:** gọi entrypoint thật với input phát triển hợp lệ trong phạm vi đã duyệt; xuất thư mục mới. Diagnostic/cache/synthetic phải gắn nhãn đúng; không thay chạy video thật bằng mock rồi gọi E2E.
6. **Inspect outputs:** kiểm nội dung/schema/source PTS/hashes/totals/dependencies/coverage/status theo task; ít nhất một phép kiểm độc lập ngoài assertion của implementation. Kiểm zero-event, unknown và failed paths khi liên quan; không ép model phải sinh event để pass smoke.
7. **Close checkpoint:** ghi report, commands/logs, artifact manifest, trạng thái và handoff. Chỉ mở task sau khi những bằng chứng bắt buộc đã có và checkpoint PASS.

Không mở task sau khi test mới fail, regression chưa giải quyết, real-run fail, report còn placeholder hoặc output chưa được kiểm. Không xóa/skip/xfail tests chỉ để qua gate, không hạ ngưỡng sản phẩm và không sửa golden outputs để khớp lỗi.

Nếu baseline đã có failures, phân loại và xử lý các failures ảnh hưởng gate hiện tại; failures không thuộc scope phải ghi cụ thể và không được tuyên bố full suite PASS. Không vượt checkpoint yêu cầu full-suite PASS khi kết quả vẫn fail.

## 3. Lệnh test và logs

Chạy từ `codebase`; dùng đúng interpreter, không dùng bare `python` hệ thống. Đặt `PYTHONIOENCODING=utf-8` khi cần cho tiếng Việt trên Windows; kiểm `--help` trước khi dùng flags chưa có. Tạo mới thư mục `outputs/sequence-<batch>-<run_id>/<task>/`, không overwrite evidence cũ.

```powershell
# Ví dụ full suite; tạo thư mục output mới trước khi chạy.
.venv/Scripts/python.exe -m pytest tests -q --junitxml=outputs/<new-run>/<task>/full-suite.xml
```

`<new-run>` và `<task>` là placeholder: thay bằng đường dẫn thật trong commands.json. Không bàn giao nguyên placeholder như một lệnh đã chạy. Lưu stdout/stderr và exit code của test runner gốc, kể cả khi dùng Tee-Object hoặc wrapper; đừng dùng exit code của lệnh đọc log để kết luận tests PASS.

Tests under `outputs/acceptance-demo-20261110/` không thuộc mặc định `pytest tests`: khi task yêu cầu phải gọi chúng tường minh. Không sửa các probes độc lập nguồn để né failure. Có thể thêm regression tương đương vào `codebase/tests` gọi production APIs; nếu API đổi có chủ ý, giữ probe cũ và ghi compatibility/migration, xác minh hành vi bằng case độc lập tương đương.

Không lặp full suite chỉ vì sửa prose hoặc links sau khi code/tests không đổi. Task chỉ dữ liệu/docs chạy validators/link checks phù hợp; không chạy lại GPU training hoặc toàn bộ inference nếu không có lý do.

## 4. Bằng chứng bắt buộc trước chuyển task

Mỗi task tạo trong thư mục run riêng:

- `checkpoint.json`: task ID, scope, status `PASS|FAIL|PENDING_INPUT`, predecessor và hash, acceptance checks với evidence paths; nếu có quality measurement thì ghi riêng quality gate và N/A reason.
- `commands.json`: command thực tế, cwd, interpreter, start/end/duration, exit code, stdout/stderr paths. Không lưu secrets/signed URLs.
- Test logs và JUnit cho pytest; validators có JSON và exit code.
- `artifacts.json`: danh sách file bắt buộc/thực có, SHA-256, source/model/config/data/rules/code versions và phạm vi technical/diagnostic/quality. Fingerprint các inputs liên quan; không cần hash lại toàn bộ dataset không liên quan ở mọi task.
- Output nghiệp vụ của task; report `docs/reports/sequence-<task>-<run_id>.md` và handoff `docs/handoffs/sequence-<task>-<run_id>.md`.

Report/handoff có: requirement → implementation → executed command → evidence → verdict; files thay đổi và lý do; counts/metrics/limitations; lỗi đã sửa/còn mở; command/config/input cụ thể cho task sau. Không nhúng secrets/media/base64.

`checkpoint.json=PASS` chỉ xác nhận phạm vi task nhỏ được mô tả. Nó không tự nâng Task04–15 hay toàn MVP thành DONE. Phân biệt implemented, executed, measured và accepted; metrics chưa tính được ghi null/N/A kèm lý do.

## 5. Input blocker và giao tiếp

- Hỏi thông tin còn thiếu theo video/timestamp/actor/rule case cụ thể, nêu ảnh hưởng gate; không hỏi lại thứ đã có trong review/authorization nguồn.
- Khi chưa đủ đầu vào cho task hiện tại: hoàn thành code/tooling/tests/report có thể làm trong task đó, ghi `PENDING_INPUT`, liệt kê phần chưa chạy, giữ task hiện tại. Không bắt đầu task mới và không báo chuỗi đã hoàn tất.
- Không dùng synthetic GT, approval giả hoặc manual correction để vượt gate. Không coi im lặng là approval.
- Sau mỗi checkpoint PASS, thông báo ngắn rồi tự tiếp tục task tiếp theo TRONG prompt đang được giao; không dừng để hỏi lại có tiếp tục hay không.
- Nếu một lệnh dài đang chạy, dùng session/log progress để cập nhật; không coi launch process hoặc file heartbeat cũ là hoàn tất. Job cần PID + process identity + freshness + epoch/artifacts thực.

## 6. Bàn giao cuối mỗi prompt

Trả lời tiếng Việt: từng task PASS/FAIL/PENDING_INPUT; tests đã chạy và số thực tế; real-run/artifacts/report/handoff links; chất lượng còn thiếu; điểm vào đợt kế tiếp. Chỉ tuyên bố cả prompt hoàn tất khi mọi task trong prompt đủ output và checkpoint theo định nghĩa. Không tự thực thi prompt đợt sau chưa được giao.
