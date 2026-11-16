# Prompt tổng — Thực thi toàn bộ phần còn lại để bàn giao demo hoàn thiện

Bạn phụ trách thực thi project trong workspace này. **Đọc và thực thi cả D01–D12, không chỉ viết kế hoạch.** Người dùng yêu cầu tự chuyển task, báo cáo sau từng task và tập trung các mục cần duyệt vào một Plan mới để review sau. Đích là demo offline đủ luồng Automatic PTS/REB/AST + Heatmap đúng brief; không cần 100% mọi output nhưng không được thay automatic recognition bằng manual entry, placeholders hoặc chờ người bấm xác nhận từng pha.

## 1. Nguồn yêu cầu và phạm vi đã giao

Đọc [Plan mới](../../../PLAN-DEMO-20261116.md), [brief](../../MVP-v2-proposal.md), PLAN nghiệm thu gốc, specs/rules/protocol và AGENTS.md áp dụng. Đọc reports/handoffs/checkpoints mới nhất theo source hiện tại, đặc biệt revision 20261116 và run 0–1000s đang có. Không coi reports PASS cũ là chứng nhận source hiện tại đầy đủ.

Nhóm prompt chi tiết phải thực thi:

1. [D01–D03: core/identity/spatial](01-core-identity-spatial.md).
2. [D04–D06: PRA/training](02-pra-training.md).
3. [D07–D08: evaluation/dashboard](03-evaluation-dashboard.md).
4. [D09–D10: benchmark/package](04-benchmark-package.md).
5. [D11–D12: QA/review/handoff](05-qa-review-handoff.md).

Tất cả nhóm đã được giao qua prompt này. Không dừng sau một nhóm để hỏi tiếp. Bộ mới thay giới hạn điều phối “dừng cả chuỗi khi một approval pending” và “không mở đợt sau” ở bộ cũ, theo yêu cầu mới của người dùng: **giữ phase bị chặn pending nhưng tiếp tục các task độc lập có đủ predecessor kỹ thuật**. Nó không cho phép vượt gate tests, dùng dữ liệu chưa duyệt như approved, bỏ chức năng hay hạ ngưỡng quality.

Đóng gói bản thử nghiệm cho người dùng review là nhiệm vụ riêng; không mở/tuyên bố PASS 06B nghiệm thu chính thức khi 06A chưa đạt. Phân biệt technical/demo/quality/approval verdict theo Plan. Nếu không thể có đầy đủ chức năng vì input chưa được duyệt, bàn giao build/packet có thể kiểm tra với verdict partial, không gọi demo hoàn thiện.

## 2. Preflight, reuse và bảo vệ job đang chạy

- Inventory code/tests/config/data/media và approvals. Giữ quyền/confirmation đã có: roster, local OCR/weights, các batch review, local GPU/train và protocol revision tương ứng; không hỏi lại toàn bộ.
- Default runtime/model giữ nguyên nếu chưa có evidence/quyền promote. Experimental candidates có profile/output/version riêng; source/model/rules/GT hashes rõ.
- Kiểm status `quality-revision-20261116/full-match-01` và process command identity/heartbeat/logs. Không khởi động trùng hoặc dừng job đang khỏe chỉ vì task mới. Snapshot nguồn job đang dùng; tránh đổi files nó còn đọc. Nếu không thể xác định các files job đã load, làm code ở snapshot/copy cô lập, chỉ tích hợp khi safe; không git init/commit/push tự động.
- Nếu state cũ malformed, backup nguyên file và tái dựng từ checkpoint/evidence có kiểm; không đoán PASS bằng regex xóa dòng. Tạo state mới parse được; giữ references lịch sử.
- Không đọc `.env` ra hội thoại/logs, không upload media, trả phí, publish, đổi driver/GPU stack/dependencies lớn hoặc locked datasets ngoài authorization đã có. Quyết định mới chưa có quyền phải vào Plan với proposal reviewable; không tạo permission flow cho việc đã được giao.
- Không dùng GT/scoring notes/scoreboard labels/window IDs làm runtime hints. Review/training/evaluator tách khỏi recognition.

## 3. Scheduler tự động theo dependency

Tạo run root mới `codebase/outputs/demo-completion-<run_id>/`. Lưu atomic JSON state: task/phase/dependencies/status/attempt/input+code hashes/commands/evidence/report/handoff/blockers/next action. Task states: NOT_STARTED, IN_PROGRESS, PASS, FAIL, WAITING_REVIEW, WAITING_INPUT; long jobs dùng phase RUNNING và actual PID/artifacts.

Lặp đến khi không còn task thực thi được trong scope:

1. Chọn task sớm nhất trong Plan có predecessor kỹ thuật PASS. Không dùng approval pending của phase khác làm global stop.
2. Chốt scope và acceptance checklist của task/phase; reproduce bug/requirement bằng production entrypoint/API.
3. Implement, chạy tests mục tiêu/independent probes, chạy integration thật và kiểm output độc lập.
4. Khi task/phase đủ evidence: ghi report/handoff/checkpoint, cập nhật Plan và state rồi tự chọn task kế tiếp. Không dùng prose “sẽ test” để đóng task.
5. Nếu code/test/run fail trong phạm vi sửa được, sửa task hiện tại và reverify; không skip/xfail/delete tests hoặc sửa GT/threshold để chuyển tiếp.
6. Nếu approval/input thật sự thiếu: hoàn tất proposal/UI/tooling/tests của phase chuẩn bị, ghi pending và tạo Rxx trong Plan. Chỉ tiếp tục task độc lập; phase phụ thuộc chưa được PASS và không dùng fake inputs.
7. D12 aggregation được cập nhật sau mọi task, kể cả khi D11 hoặc training pending. Chỉ kết thúc khi đủ demo/QA/review outputs hoặc mọi phần còn lại thực sự phụ thuộc review/input không có. Khi còn việc độc lập thực thi được, không kết thúc chỉ bằng blocker list.

Ưu tiên D01→D02→D03→D04→D05, sau đó chọn D06/D07/D08/D09 theo dependency thực. D06 có phase chuẩn bị và phase train; hoàn tất preparation không phải train xong. D03 có thể tách calibration proposal và verified accumulation; thiếu duyệt góc mới không được giả geometry valid. Task nào chưa đủ input phải thể hiện đúng trạng thái rộng hơn dù một phase đã PASS.

## 4. Checkpoint trước chuyển task

Mỗi task có thư mục riêng và bắt buộc:

- `checkpoint.json`: scope, predecessor refs/hashes, từng acceptance check, evidence path, task/phase status và bốn verdict khi liên quan.
- `commands.json`: lệnh thật, cwd/interpreter, duration/exit code, stdout/stderr và JUnit. Capture exit code gốc; output directory mới, không overwrite.
- `artifacts.json`: required vs actual files, SHA-256/versions/source/model/config/data/rules, technical/diagnostic/quality scope.
- Outputs nghiệp vụ parse được, ít nhất một phép đối soát độc lập: timing/source/counts/geometry mass/ledger totals/dependencies/replay theo task.
- Report `docs/reports/demo-<task>-<run_id>.md` và handoff `docs/handoffs/demo-<task>-<run_id>.md`, cập nhật bảng task và Rxx trong Plan.

Task sửa production/shared code chạy tests mục tiêu + required regressions + full suite sau thay đổi cuối. Nếu sửa tiếp vì fail, chạy lại checks bị ảnh hưởng và full suite trước chốt. Sau khi chỉ sửa prose/links không đổi code, không chạy lại toàn suite/inference vô ích.

Tests dưới historical outputs phải được gọi tường minh khi liên quan; không chỉnh independent probes để che lỗi. Synthetic fixtures chỉ kiểm contracts/plumbing, labels rõ; real-video smoke và real QA vẫn bắt buộc. Test đo performance phải kiểm actual measurements/coverage, không ép FPS>30 bằng constants/cache hoặc golden artifact cũ.

Từ `codebase`, dùng `.venv/Scripts/python.exe`; `.venv-train` cho local CUDA training đúng recipe đã có. Xác minh CLI `--help` trước flags mới; không bàn giao placeholder command như đã chạy. Tests baseline cũ là context, không phải mục tiêu số lượng.

## 5. Gom approval vào Plan để người dùng review sau

`PLAN-DEMO-20261116.md` là sổ review duy nhất. Đồng bộ `approval-register.json` với IDs R01…R07 và chỉ thêm quyết định mới có thực. Mỗi item có: trạng thái, scope, exact artifact/hash/version, lý do cần review, options/tradeoffs/recommendation, ảnh hưởng khi chưa duyệt, việc agent đã làm, thao tác apply/rollback và test lại sau apply.

Không hỏi rải rác giữa tasks. Chuẩn bị trước clips/evidence/annotation UI/exports, calibration overlay, split/protocol diff, candidate comparison và bundle demo rồi đưa vào Plan. Người dùng chỉ review phần cụ thể; không yêu cầu tự làm labels CSV, homography matrix hoặc lock manifest mà agent có thể chuẩn bị.

Không xin lại authorization đã có và không suy approval từ Plan DRAFT hoặc im lặng. Nếu chỉ còn action cần quyền mới hoặc input không có thì ghi pending với Plan review packet hoàn chỉnh; không thực hiện action phụ thuộc. Phần agent được phép làm tiếp vẫn tiếp tục. Sau review, chỉ áp dụng các mục thực sự được xác nhận và reverify ảnh hưởng.

Không yêu cầu người dùng phê duyệt toàn Plan trước khi bắt đầu các task đã được giao. Việc review Plan được gom sau khi chuẩn bị concrete outputs, theo yêu cầu người dùng; chỉ phase cần quyết định mới phải chờ quyết định đó.

## 6. Tiêu chuẩn đầu ra demo và quality

- Đủ PTS/REB/AST tự sinh từ evidence video thật và heatmap/time-weighted grid thật với source-bound calibration. Không nhận zero REB/AST mãi, jersey evidence luôn `[]`, heatmap mass luôn 0 hay chỉ có config file là hoàn thiện chức năng.
- Có unknown/unresolved với lý do, coverage/attribution metrics; team-only credits hợp lệ không được gán ngẫu nhiên cho cá nhân. Không cần 100% mọi output, cũng không che các pha bỏ sót để làm precision đẹp.
- Overlay MP4/source PTS, dashboard video/timeline/boxscore/court/heatmap/evidence/status/cancel/export; corrected results riêng raw auto.
- One-command launcher, user guide, exact input constraints/configs, output bundle manifest và clean-run/browser evidence. Không yêu cầu chi phí/cloud/live mới cho demo offline.
- Quality giữ original targets P≥95%, R≥90% cho từng stat và geometry/team/coverage gates hiện hành; basket-primary revision so song song với profile cũ, không gọi thay matcher là detector đã tốt lên. Sparse/exposed diagnostic không tự được gọi independent test.
- `DEMO_READY_FOR_REVIEW` là bản thử nghiệm hoàn thiện để người dùng review, không phải `QUALITY_ACCEPTED` hay 06B PASS. Nếu còn thiếu chức năng/real-data proof bắt buộc, verdict phải partial và có exact remediation.

## 7. Kết thúc và resume

Không cam kết prompt tồn tại qua shutdown hoặc tự có review reply. Job chạy nền có status/heartbeat/checkpoint và resume command; không coi launch thành completed. Context bị compact thì đọc state/Plan/report task cuối, tiếp tục phase chưa xong; không khởi động lại toàn chuỗi.

Bàn giao tiếng Việt: launcher/URL và guide; từng task/phase với tests/run/report links; demo vs quality verdict; auto metrics trước correction và limitations; một Plan review với các Rxx có thể quyết định; pending/next action và exact resume command. Chỉ nói hoàn tất toàn bộ khi đủ evidence tương ứng, không lấy tổng số tests hoặc thời gian làm thay acceptance.

**Bắt đầu D01 ngay. Tự tiếp tục toàn chuỗi trong quyền đã có, báo cáo sau từng task và gom review vào Plan; không chỉ trả một kế hoạch khác.**
