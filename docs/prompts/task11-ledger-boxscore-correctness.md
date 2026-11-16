# Prompt thực thi Task11 — Ledger/box score đúng trạng thái, idempotency và audit

Ngày: 2026-11-11. Bạn là Senior Python Engineer trực tiếp làm việc trong repository. **Hãy triển khai và kiểm chứng bản sửa Task11**, không chỉ phân tích, lập kế hoạch hay tạo thêm prompt. Sửa code production, tái hiện lỗi, thêm regressions, chạy integration trên artifacts có thật và bàn giao report/evidence.

Mục tiêu: ledger và box score không phát sinh số liệu từ event chưa đủ điều kiện; không cộng trùng sau identity refinement/replay; xử lý dependencies/revisions đúng; raw audit/checkpoint có thể tái lập. Hoàn thành core Task11 không đồng nghĩa đã nghiệm thu detector, shot/rebound/assist recognition hoặc toàn demo.

## 1. Đọc và kiểm tra trước khi sửa

Đọc AGENTS.md áp dụng nếu có, `docs/DEVELOPMENT.md`, `PLAN.md`, `docs/tasks/task11.md`, contracts hiện có và:

- `docs/reports/demo-completion-acceptance-20261110.md`, đặc biệt **P1-E/P1-F**.
- `docs/reports/task11-unified-event-ledger-and-boxscore-20261109.md`; các claim ACCEPTED cũ đã bị nghiệm thu 10/11 thay thế.
- `codebase/src/basketball_scoreboard/events.py` và `boxscore.py`.
- Các callers/adapters trong `points.py`, `rebounds.py`, `assists.py`, `dashboard.py`, `codebase/scripts/run_demo.py` và runner Task08.
- `codebase/tests/test_task11_ledger_and_boxscore.py`.
- `codebase/outputs/acceptance-demo-20261110/test_acceptance_requirements.py` và artifacts nghiệm thu liên quan.

Xác minh hiện trạng thật và không khôi phục đè các thay đổi mới đã đúng. Workspace có thể không có `.git`; lưu source/config SHA-256 trước/sau vào output mới. Giữ nguyên các artifacts nghiệm thu cũ.

Phạm vi sửa chính là ledger/boxscore, tests, persistence và adapters cần thiết để giữ compatibility. Không thay weights/model/OCR/ROI, không restart fine-tune, không sửa dataset/GT/rules approval, không xây lại toàn dashboard hoặc event-recognition engines trong task này. Không tạo chi phí/upload/publish.

## 2. Tái hiện các lỗi hiện có bằng public API

Chạy các tests/probes Task11 liên quan trước sửa, ghi rõ pass/fail ban đầu. Các lỗi cần kiểm chứng:

1. `BoxScoreEngine.compile()` lấy mọi non-void event nên candidate/provisional/unresolved và cả status VOID có thể tăng PTS/REB/AST/TO.
2. Sau team-only → player attribution refinement, cùng physical score được ingest bằng ID mới có thể làm tổng 2 → 4.
3. Team/status revision của score không làm assist phụ thuộc mất eligibility; child đến sau parent đã void vẫn có thể được cộng.
4. Ledger giữ reference của object/evidence do caller truyền vào; mutation bên ngoài có thể đổi thống kê mà không có audit record.
5. Export active events không phải raw append-only transaction log; checkpoint/resume/replay chưa chứng minh tái tạo đầy đủ lịch sử.

Không mặc định cả 40 probes của toàn demo thuộc phạm vi Task11. Lỗi shots/evaluator/REB/AST/UI còn lại phải được báo riêng, không sửa expected assertions/xfail để tạo pass giả.

## 3. Lifecycle và điều kiện được cộng vào box score

- Định nghĩa một eligibility contract dùng chung cho ingestion, queries và aggregation. Chỉ event **AUTO_CONFIRMED, non-void, payload hợp lệ và dependencies đủ điều kiện** mới đóng góp vào confirmed stats.
- CANDIDATE/PROVISIONAL/UNRESOLVED/VOID vẫn lưu được trong ledger/audit/coverage, nhưng không tăng confirmed PTS/REB/AST/TO.
- Chuẩn hóa nhất quán `status` và `is_void`; legacy record mâu thuẫn phải được xử lý bảo thủ và có reason, không được tình cờ tính điểm. Không đổi VOID thành confirmed chỉ vì flag False.
- Made event có point_value chưa rõ không tự trở thành 1 điểm. Validation dữ liệu phải từ chối nonfinite/invalid types/invalid values theo contract; bool không được lẫn thành integer hợp lệ. Rule-specific eligibility giữ theo profile đã có, không phát minh luật mới trong aggregator.
- Team-only score vẫn được cộng đúng vào đội nếu outcome/value/team đủ evidence; player_id null không đồng nghĩa cả event vô hiệu. Giá trị của event và mức attribution là hai trục khác nhau.
- Player không thuộc roster/team không được gán sang người khác để bảo toàn tổng. Giữ unassigned/conflict rõ; team chưa biết phải có bucket/coverage phù hợp, không âm thầm mất record hoặc gán sang đội mặc định.
- Team rebound không tự thành player rebound; unknown subtype không mặc định defensive. Giữ các khoản unassigned/unknown có thể đối soát và không gọi personal AST/TO đã xác minh khi actor thiếu.
- Initial offsets tách khỏi observed increments. Module chưa có coverage hoặc upstream chưa chạy không được xuất số 0 với ý nghĩa đã đo đầy đủ; cung cấp metadata cho UI/evaluator phân biệt zero/pending/unknown.

Kiểm invariants cả về **eligibility** và totals: tổng số bảo toàn vẫn có thể sai nếu nguồn là candidate events. Làm rõ per-team/per-player/unassigned counts và các subtype còn unresolved.

## 4. Định danh ổn định và chống đếm lặp sau refinement

- Tách physical-event/source identity khỏi payload mutable như player/team/value. Ưu tiên source/video/shot/pass/control refs và producer event identity ổn định; không dùng riêng timestamp làm tròn + actor/value làm khóa authoritative.
- Same-ID same-revision/same-payload là duplicate/idempotent. Same-ID payload khác phải qua revision/conflict contract rõ ràng; không âm thầm bỏ một refinement hợp lệ hoặc ghi thêm score mới.
- Different-ID nhưng cùng physical event/alias đã xác minh không được cộng lần hai. Index/aliases phải còn đúng sau unknown→known, known→unknown, đổi team/value/status và checkpoint reload.
- Hai physical shots khác nhau gần thời gian vẫn phải được giữ; không dùng một cooldown/time bucket rộng để xóa nhầm sự kiện thật.
- Với legacy callers thiếu stable refs, có migration/compatibility policy và ambiguous reason rõ. Nếu cần đổi schema/API, cập nhật adapters/fixtures theo semantics hợp lệ; không làm yếu assertions hoặc chỉ special-case IDs của tests.
- Revision API phải phân biệt “không thay trường này” với “xóa về None”; hỗ trợ actor/value/team trở thành unresolved mà không phải mutate object trực tiếp. Revision conflict/stale/no-op handling có policy và tests.
- Preserve source PTS/precision đủ cho replay/matching; format hiển thị làm tròn không được làm mất timestamps hoặc tạo collision trong dữ liệu canonical.

## 5. Dependency và arrival order

- Phân biệt refs đến đối tượng recognition bên ngoài, như source shot_id, với **ledger dependency** cần resolve. Không loại mọi score chỉ vì external shot ref chưa có một LedgerEventRecord cùng ID.
- Assist chỉ được aggregate khi linked score và các điều kiện parent/actor/team liên quan còn hợp lệ. Ledger không tự phát minh eligibility action/pass mà upstream chưa cung cấp.
- Parent void, confirmed→unresolved hoặc team/attribution revision làm child không còn tương thích phải khiến child ngừng đóng góp, có audit/reason và cascade cần thiết.
- Một revision không làm thay đổi eligibility, ví dụ point value hợp lệ đổi nhưng assist vẫn đúng, không được blanket-void child tùy tiện. Xác định policy revalidation/reactivation rõ và lưu history; không tự unvoid một event cũ mà không có transition hợp lệ.
- Child đến trước parent hoặc sau parent đã void không được có “khoảng thời gian cộng sai”. Missing parent giữ pending/blocked cho đến khi đủ evidence; parent hợp lệ đến sau chỉ mở đóng góp đúng một lần.
- Xử lý duplicate/reordered notifications, multi-level dependencies, missing parent và cycle/conflicting refs có kiểm soát; không recursion vô hạn hoặc partial state âm thầm.
- Event time của assist/pass có thể sớm hơn source time của score. Phân biệt source/event time với decision/emission/transaction order, không ép timestamp parent phải nhỏ hơn timestamp mọi child.

## 6. Immutability, audit và checkpoint/replay

- Defensive deep copy hoặc immutable representation tại ingestion; nested evidence không được chia sẻ mutable reference với caller. Read APIs/to_dict/snapshot cũng không mở đường sửa state không qua transaction.
- Mọi mutation hợp lệ phải có transaction/mutation ID, sequence, event ID, revision, before/after state, origin/reason và timestamp. No-op/duplicate/conflict handling được phân biệt, không giả một event confirmed mới.
- Raw automatic log append-only; human corrections là stream/layer riêng có provenance, không sửa raw outputs rồi dùng làm metrics automatic.
- Active/latest-state export chỉ là view, không được thay raw mutation history. Dùng tên/schema rõ cho raw log, audit/corrections và materialized event view; giữ API compatibility có tài liệu nếu phải migrate.
- Có checkpoint/save/load/replay thật: schema/version, ledger/source binding, sequence position, canonical state và indexes/dependencies đủ tái tạo. Verify integrity, missing/duplicate transactions và các refs thay vì tin mọi snapshot.
- Việc lưu checkpoint phải atomic theo policy đã chọn. Interrupted/truncated tail cần fail hoặc recovery policy rõ và đánh dấu partial; không lặng lẽ đọc rác rồi ghi completed.
- Resume checkpoint + replay tail, full-log replay và replay cùng notifications lần nữa phải cho cùng eligible events/totals. Không tái tạo created/source timestamps khác mỗi lần load.
- Nếu ingestion/compile/export có thể chạy đồng thời, aggregate từ snapshot nhất quán; mutation và indexes cập nhật atomic theo contract. Không cần thêm database service hoặc framework nặng để giải quyết local ledger.

## 7. Integration tối thiểu và exports

- Cập nhật point-event adapter/callers để giữ source identity, actual source PTS, confirmation time, status, shot refs, evidence và attribution đúng semantics. Không thay source event time bằng confirmation time mà không khai báo riêng.
- Nối ledger đã sửa vào runner/dashboard hiện có ở mức cần thiết để xuất đúng aggregate/status. Không tuyên bố đã sửa continuous-video runner hoặc nhận diện REB/AST khi chỉ ingest cached event stream.
- Xuất raw automatic log, latest-state view, audit/corrections, checkpoint, `boxscore_auto.csv` và reconciliation/coverage summary vào thư mục output mới.
- CSV/JSON phải đối chiếu được với cùng snapshot, phân biệt offset/observed/team-only/player/subtype và unresolved. Không dùng các dấu gạch/0 như số liệu đã đo khi thật sự unavailable.
- Dùng artifacts points/events có thật để chạy ingestion→revision→export→reload→replay; giữ provenance. Các mutation do test tạo thêm phải được gắn synthetic diagnostic, không gán thành sự kiện mới của trận.

## 8. Tests bắt buộc trên code production

Tái dùng probes làm regressions, không viết một ledger/aggregator khác trong tests rồi chỉ kiểm implementation giả đó. Bao phủ tối thiểu:

1. Bốn loại PTS/REB/AST/TO × bốn status không-confirmed đều không tăng confirmed stats; VOID flag/status mâu thuẫn không được cộng.
2. Team-only → known player → reingest same physical score/new ID: team total giữ nguyên, unassigned giảm và player tăng đúng một lần.
3. Known → unknown, team transfer, value revision, confirmed → unresolved/void và duplicate/stale/no-op revisions.
4. Compatible parent revision giữ child hợp lệ; incompatible team/status/void loại assist đóng góp; late child và reordered parent-child không tạo phantom totals.
5. Input/read-result/nested evidence mutation từ caller không đổi recorded state hoặc lịch sử.
6. Full log replay, checkpoint + tail, repeated reload/seek và shuffled arrival theo contract cho cùng kết quả; malformed checkpoint/log không thành run thành công giả.
7. Hai shots khác nhau sát thời gian vẫn được giữ; cùng event ở hai source namespaces không bị merge tùy tiện.
8. Offsets, team-only/player totals, rebound categories/unassigned và unknown coverage không bị lẫn; export JSON/CSV round-trip consistent.

Lệnh tham khảo từ workspace root, kiểm tra paths trước khi chạy:

```powershell
$env:PYTHONPATH='codebase/src;codebase/scripts'
$env:PYTHONIOENCODING='utf-8'

codebase/.venv/Scripts/python.exe -m pytest codebase/tests/test_task11_ledger_and_boxscore.py -q

codebase/.venv/Scripts/python.exe -m pytest codebase/outputs/acceptance-demo-20261110/test_acceptance_requirements.py -q -k 'only_confirmed_events_contribute or refined_event_cannot_be_reingested_under_new_id or team_revision_invalidates_incompatible_assist or status_revision_invalidates_assist or late_child_of_void_parent_is_not_counted or caller_cannot_mutate_recorded_raw_event'

codebase/.venv/Scripts/python.exe -m pytest codebase/tests -q
```

Giữ nguyên bộ kiểm độc lập cũ để audit; có thể đưa các ca phù hợp vào tests chính với source reference. Chỉ chạy thêm tests/regression khi thay đổi/failure justify, không benchmark hoặc rerun inference không liên quan.

## 9. Bằng chứng và điều kiện bàn giao

Output mới, ví dụ `codebase/outputs/task11-ledger-correctness-<run-id>/`, gồm:

- Source/config snapshot và commands/exit codes; baseline failure và kết quả sau sửa.
- Fixture transaction logs có nhãn synthetic rõ, actual-event replay có provenance riêng.
- Raw/latest/audit/correction/checkpoint/CSV/JSON outputs và reconciliation report.
- Invariant comparisons trước/sau save/load/reorder/refinement/void; test logs/JUnit nếu có.

Viết `docs/reports/task11-ledger-correctness-20261111.md`: nguyên nhân, thay đổi, compatibility/migration, invariants, tests, integration đã chạy, giới hạn và issues ngoài phạm vi. Cập nhật `docs/tasks/task11.md`, report Task11 cũ và PLAN bằng link/trạng thái mới phù hợp; giữ lịch sử.

Đợt sửa core đạt yêu cầu khi các Task11 probes hiện có và regressions mới pass, code production thực sự được integration gọi, exports/replay nhất quán, không có mutation ngoài audit và không có event chưa eligible được cộng. Mỗi trạng thái implemented/executed/measured/accepted phải có evidence.

**Không nâng toàn Task11/full PRA/MVP lên DONE chỉ từ các tests này:** recognition quality và complete engine integration còn là gate riêng. Nêu rõ core ledger nào đã được xác minh, acceptance nào còn phụ thuộc Task08–10/13 và task tiếp theo cần làm.

Tự hoàn tất phần đã giao mà không hỏi lại các lựa chọn triển khai thường lệ. Nếu có blocker thật sự ngoài phạm vi, hoàn thành phần độc lập và báo chính xác; không tự sửa GT/approval hoặc expected assertions để vượt gate. Phản hồi cuối dẫn tới source, tests, actual replay artifacts, report và kết quả các probes.
