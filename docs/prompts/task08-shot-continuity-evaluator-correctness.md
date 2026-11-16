# Prompt thực thi Task08 — Shot continuity, production evaluator và negative cohort

Ngày tạo: **2026-11-12**. Ưu tiên kế tiếp sau đợt sửa core Ledger/Box Score ngày 11/11. Đây là prompt để agent sửa code, chạy kiểm chứng và bàn giao bằng chứng; việc tạo prompt không thay đổi trạng thái nghiệm thu.

## 1. Vai trò, mục tiêu và phạm vi

Bạn là Senior AI/Python Engineer chịu trách nhiệm sửa Task08 theo các lỗi **P1-B, P1-C, P1-D** trong báo cáo nghiệm thu 10/11. Hãy thực thi đến khi hoàn thành các phần có thể làm bằng code và dữ liệu hiện có; không chỉ trả lời kế hoạch hoặc viết lại prompt này.

Mục tiêu: xác nhận made basket từ chuỗi quan sát bóng hợp lệ, dùng chung một evaluator production có matching đúng, chạy lại trên dữ liệu có nguồn gốc xác minh được và bàn giao tập negative có trạng thái review trung thực. Bảo vệ OCR/identity/ROI và tính đúng đắn của Ledger/Box Score vừa sửa. Không lấy tổng score khớp hoặc tests xanh làm bằng chứng recognition đạt chất lượng.

Phạm vi chính là `shots.py`, evaluator dùng trong runner Task08, adapter liên quan, tests và công cụ review/provenance cho negative cohort. Chỉ sửa `points.py` hay caller khác khi cần giữ đúng hợp đồng thời gian, attribution hoặc integration. Không gộp vào đợt này việc fine-tune, đổi model/backend/GPU stack, triển khai toàn bộ REB/AST, dashboard hoặc continuous MP4 runner.

## 2. Đọc hiện trạng trước khi sửa

Tìm và tuân thủ `AGENTS.md` áp dụng nếu có. Đọc:

- `docs/DEVELOPMENT.md`, `PLAN.md`, `docs/tasks/task08.md`, `docs/tasks/task11.md`.
- `docs/reports/demo-completion-acceptance-20261110.md`, nhất là P1-B/C/D, metrics diagnostic và điều kiện tái nghiệm thu.
- `docs/reports/task11-ledger-correctness-20261111.md` cùng logs/artifacts tương ứng. Báo cáo ghi nhận 21 acceptance probes, 33 Task11 tests và 393 tests toàn codebase; đây là snapshot cần đối chiếu, không phải số phải sao chép vào kết quả mới.
- `docs/prompts/task08-temporal-shot-engine.md`, các báo cáo Task08 và handoffs gần nhất. Các claim specificity 100% trước audit không phải kết quả được nghiệm thu.
- `codebase/src/basketball_scoreboard/shots.py`, `points.py`, `events.py`, `boxscore.py` và contracts ball/rim/tracking/identity mà chúng dùng.
- `codebase/scripts/run_task08_temporal_shot_engine.py`, `mine_negative_cohort.py`, `generate_negative_cohort_observations.py` và các scripts baseline/evaluation có liên quan.
- `codebase/tests/test_task08_temporal_shot_engine.py`, `test_task08_evaluator.py`, `test_task11_ledger_and_boxscore.py` và `codebase/outputs/acceptance-demo-20261110/test_acceptance_requirements.py`.
- Protocol/rules/splits đang có, scoring intake `codebase/outputs/task08-scoring-intake-20261107/adjudicated-v3/`, diagnostic caches và negative manifests thực tế. Tìm đúng schema/path bằng code, không đoán từ tên thư mục.

Chạy baseline phù hợp và lưu kết quả trước khi chỉnh. Kiểm tra source/artifact mới hơn các báo cáo; nếu một lỗi đã được sửa, giữ regression và tập trung phần còn thiếu. Không lùi bản sửa hợp lệ. Bảo toàn nhãn, frozen protocol, acceptance probes và outputs cũ.

Tạo thư mục output mới `codebase/outputs/task08-shot-correctness-<run-id>/`; lưu source/config hashes trước/sau, input manifest, commands/exit codes và logs. Không ghi đè các run cũ hoặc sửa expected hash của experiment trước.

## 3. Sửa xác nhận bóng vào rổ từ chuỗi quan sát thật

### 3.1. FSM và hợp đồng thời gian

Giữ kiến trúc `Ready -> Release -> Flight Arc -> Outcome (Basket | Miss)` cùng abort/reset. Release, flight và crossing phải thuộc cùng source/segment/camera context và có thứ tự PTS hợp lệ. Dùng source timestamps, không dùng thời gian chạy chương trình hoặc giả định mọi video là CFR.

Phân biệt rõ `observed`, `predicted`, missing, stale và invalid. Adapter không được tự nâng prediction thành observation hoặc mặc định mẫu không rõ nguồn là observed. Prediction có thể hỗ trợ continuity/tracking, nhưng không tự tạo bằng chứng entry/exit cho made basket.

Giữ source event time, confirmation time và decision latency riêng. Duplicate frame/PTS không được làm tăng số quan sát hoặc thời gian control. Timestamp đảo chiều, seek, discontinuity/cut và source change phải có xử lý rõ, không kéo trajectory qua đoạn không liên tục.

### 3.2. Observed crossing qua khẩu độ vành

- Entry phía trên và exit phía dưới phải được hỗ trợ bởi các ball observations thật, đúng track hoặc association đã kiểm chứng, đủ confidence, trong cùng chuỗi hợp lệ.
- Áp giới hạn thời gian giữa observations dựa trên **last observed timestamp**, kể cả khi tracker liên tục có predicted center. Probe khoảng trống 0,8 s với giới hạn 0,35 s phải bị chặn; không hard-code chỉ riêng ví dụ này.
- Xác minh hướng trên xuống theo geometry và aperture, spatial continuity và độ hợp lý của chuyển động. Chỉ giao với bbox rim, đi ngang bbox hoặc đi từ dưới lên không đủ điều kiện.
- Không ghép entry từ bóng/track khác với exit. Nếu có association đổi ID, cần evidence và policy rõ; không dùng ID đổi hoặc khoảng cách gần rổ để suy ra made.
- Rim detection cần confidence/quality/geometry validity và camera context. Số đo 10/10 ở vài keyframe không chứng minh detector luôn chính xác 100%. Rim mất/stale hoặc geometry không hợp lệ phải dẫn tới trạng thái chưa xác định hay reset phù hợp.
- Rebound/deflection/blocked shot và rim bounce không được tạo score từ suy diễn trajectory. Thiếu observations không tự đổi thành miss chắc chắn; phân biệt miss có evidence với unknown/aborted/timeout.
- Giữ một physical shot một confirmation/event; repeated frames, cache replay hoặc observation lặp không phát sinh thêm điểm. Không dùng cooldown toàn cục quá rộng khiến bỏ hai cú ném thật liên tiếp.

Mỗi quyết định phải xuất evidence refs: observed entry/exit frame và PTS, confidence, gap thực tế, aperture/config, track/segment và lý do confirm/reject/unresolved. Bằng chứng chỉ ra đúng observation đã được dùng, không lấy frame đẹp khác để minh họa sau quyết định.

### 3.3. Net/deceleration cue

Loại bỏ đường `net_cue_passed=True` cố định nếu còn tồn tại. Nếu đo được cue, tính từ observations hợp lệ theo source time, ghi phép đo/đơn vị/quality và lý do pass/fail. Camera movement, perspective, occlusion và thay đổi sampling làm tốc độ ảnh không đồng nhất với ma sát lưới; không gán cue thành bằng chứng vật lý tuyệt đối.

Khi không đủ dữ liệu, dùng `unavailable/unknown` riêng. Cue chỉ là tín hiệu bổ trợ theo policy được ghi rõ; không thay observed crossing. Có ablation ON/OFF nếu giữ tính năng, cùng predictions và config để tái lập. Không tăng recall bằng cách bỏ guard continuity hoặc hạ confidence tùy từng play.

## 4. Một production evaluator dùng chung

Tách logic evaluation thành module production tái sử dụng nếu cần; runner, CLI và tests phải gọi đúng implementation đó. Xóa hoặc thay class evaluator riêng trong test hiện đang kiểm một thuật toán khác. Giữ compatibility wrapper nếu caller/acceptance probes dùng API cũ và kiểm wrapper thật sự ủy quyền cho implementation mới.

### 4.1. Protocol và event matching

Đọc protocol đã freeze trước. Nếu chưa có tolerance chính thức đủ cho Task08, tạo protocol diagnostic versioned có cấu hình rõ; ví dụ ±0,5 s của audit chỉ là diagnostic, không tự nhận đã được duyệt. Không sửa frozen protocol hoặc chọn tolerance theo kết quả để đạt gate.

Matching có các yêu cầu:

1. Chỉ xét sự kiện trong coverage/source/segment hợp lệ; release và basket phải đồng thời thỏa điều kiện thời gian đã định nghĩa. Sự kiện ở đầu window không match GT cuối window chỉ vì cùng window ID.
2. One-to-one matching **maximum cardinality** trên các cặp hợp lệ; tie-break deterministic theo sai lệch thời gian và stable ID. Có fixture mà greedy theo cặp gần nhất làm mất một match hợp lệ. Không cần thêm dependency lớn nếu code hiện có đủ.
3. Prediction chưa ghép là FP, GT chưa ghép là FN; duplicate prediction cho cùng GT tạo FP. Không loại duplicate bằng cách nhìn GT trước khi tính metric.
4. Tách event detection với correctness của actor/team/value. Made đúng thời gian nhưng sai actor/value không được biến thành strict TP. Định nghĩa strict TP/FP/FN và denominators theo protocol, tránh chỉ bỏ prediction sai khỏi báo cáo; cho phép nhiều metric views trên cùng frozen predictions nhưng không ghép lại tùy metric để che lỗi.
5. Team-only fallback có thể đúng team, không được tính là strict player đúng. Unknown actor/value là thiếu coverage ở chiều đó, không tự đúng và không gán giá trị mặc định. Không cộng window miss vào team-attribution matches của made events.
6. Empty sets, background-only và unresolved có định nghĩa tường minh. Mẫu số 0 trả `null`/N/A kèm lý do và counts, không tự thành 100%. Negative specificity là metric segment-level trên cohort reviewed; không trộn số FP event với số negative segments như cùng một đơn vị.
7. Xuất matched pairs, unmatched predictions/GT, timestamp deltas, attribution/value disagreements và lý do loại ngoài coverage. Kết quả deterministic khi input bị đảo thứ tự và vẫn giữ timestamp precision đủ cho boundary.

### 4.2. Ngăn GT leakage

Recognition chỉ nhận video/observations và cấu hình kỹ thuật hợp lệ. Không đưa scorer, outcome, score delta, review timestamps, free-throw/replay/camera flags suy từ play ID hoặc negative category vào FSM. Scoring intake dùng cho evaluation/selection có ghi rõ tính diagnostic, không trở thành runtime oracle.

Tách input recognition khỏi labels cả về schema lẫn call graph. Lưu predictions tự động trước khi load GT để evaluation; ghi hash/version và dùng lại cùng predictions cho các metric views. Test đổi labels/notes/window names phải không làm đổi predictions. Điều kiện FT/camera/replay chỉ được phát hiện từ runtime evidence hoặc được khai báo là external context có provenance đúng scope; không ngụy trang GT thành metadata kỹ thuật.

## 5. Negative cohort: từ draft đến tập có thể nghiệm thu

Audit 10/11 chỉ chứng minh runner đã đi qua 30 caches / 4.050 frames, chưa chứng minh đó là các tình huống đúng nhãn. Một số mẫu đầu trông như giới thiệu cầu thủ. Không tái sử dụng mô tả airball/rim miss dựa vào tên `neg_*` như sự thật.

Thực hiện:

- Kiểm kê toàn bộ segments; decode nguồn thật để tạo clip đủ trước/sau sự kiện, contact sheet và timeline. Contact sheet không thay việc review toàn segment.
- Bind source path/hash, source PTS range, frame IDs và hash phù hợp, model weights/hash/class map, preprocessing/ROI/config/code version, FPS/time base và cache schema. Kiểm cache khớp video và nội dung segment; thiếu provenance phải đánh dấu hoặc regenerate từ source, không điền hash giả để hợp thức hóa cache cũ.
- Chuẩn bị tối thiểu 30 tình huống duy nhất, hướng tới phân bổ cũ 10 clean misses, 8 rim/backboard misses, 6 turnovers/non-shots, 6 replays nếu footage có đủ. Nêu rõ phần thiếu nếu không đủ; không nhân bản/cắt chồng cùng pha để đủ quota. Group replay với pha gốc và split theo source/physical play để tránh leakage.
- Lưu riêng predicted category và reviewed category/status, reviewer, thời điểm, evidence refs, uncertain/excluded reason. Pregame/background có thể hữu ích như nhóm riêng, không tự đổi thành miss/turnover.
- Tạo review packet có clips và manifest để người có thẩm quyền review; không tự gán reviewer/sign-off hoặc đổi `draft_unreviewed` thành approved. Nếu thiếu review độc lập thì hoàn tất code/artifacts còn lại và bàn giao phần review đang chờ.
- Chạy FSM thật trên observations của từng segment, lưu predictions/rejection reasons; không đặt FP=0 bằng nhánh dựa vào nhãn category. Replay suppression/camera-cut logic phải có runtime evidence; một clip replay được bắt đầu độc lập cần trạng thái unknown khi chưa đủ context.

Báo riêng reviewed cohort và draft diagnostics. Chỉ công bố official specificity khi protocol, labels, provenance và coverage đủ điều kiện. Nếu chưa đủ thì N/A kèm số segments, made predictions, số reviewed và lý do; 0 made trên draft segments không tương đương specificity 100%.

## 6. Bảo vệ OCR, ROI, identity, points và ledger

Không thay model/checkpoint, OCR provider/weights, roster, identity thresholds, team-color mapping, ROI/court geometry hay frozen splits để làm đẹp kết quả Task08. Lưu hash các cấu hình liên quan và so sánh trước/sau; nếu cần sửa adapter thì mô tả tác động và paired evidence.

Shooter history chỉ đọc dữ liệu có sẵn trong `[t_release - 2,0 s, t_release]`; OCR nhận được sau release không được hồi tố thành bằng chứng đã biết tại release. Tách source timestamp của crop với thời điểm kết quả OCR có sẵn nếu pipeline xử lý bất đồng bộ. Không lấy người gần rổ tại basket thay shooter. Unknown player có thể giữ team-only nếu team có evidence đáng tin; unknown team giữ unassigned. Không lấy màu áo chưa kiểm chứng làm attribution chắc chắn.

Giữ `point_value=None` và trạng thái unresolved khi thiếu geometry/FT context; không default 1 hoặc 2 điểm. Không kéo geometry qua camera cut. Basket detection đúng, shooter đúng và point value đúng là ba kết quả riêng.

Qua adapter production, kiểm source/confirmation time, stable physical/source identity, refinement và void/dependency lifecycle. Confirmed team-only có value hợp lệ được tổng hợp đúng; candidate/provisional/unresolved/VOID không làm tăng stats. Nạp lại cùng shot không cộng điểm hai lần; replay raw log/checkpoint phải giữ kết quả. Không đổi core Task11 để chấp nhận payload Task08 thiếu bằng chứng.

Chạy paired regression trên cùng input/config trước và sau: OCR/identity outputs và causal attribution, observed ball coverage, rim/crossing evidence, event status và point totals. Nếu không có OCR GT đủ thì chỉ kết luận contract/output regression trong coverage đã kiểm, không tuyên bố OCR accuracy được đảm bảo tuyệt đối.

## 7. Kiểm thử bắt buộc

Viết tests vào production path, ưu tiên tái hiện lỗi audit rồi sửa. Các nhóm tối thiểu:

1. Predicted entry/exit, missing sample type, observed point nằm ngoài crossing; không được made. Long gap bị chặn dù predicted center vẫn cập nhật. Test sát giới hạn và PTS không đều, duplicate/out-of-order samples.
2. Observed crossing hợp lệ xác nhận một lần; reverse/sideways/bbox-only/deflection/track mismatch/stale rim/cut không tự xác nhận. Hai physical shots thật gần nhau vẫn phân biệt được. Net cue unavailable không được xuất pass giả.
3. Production evaluator: ngoài tolerance, đúng boundary, duplicate FP, greedy trap, empty/background sets, sai source/segment, deterministic order, wrong actor/team/value, team-only và unresolved; không dùng evaluator tự định nghĩa riêng trong test.
4. GT isolation: đổi nhãn/notes/play IDs không đổi raw predictions. Runtime không nhận flags lấy từ GT. Missing/corrupt cache hoặc video không tạo thành một run thành công có metric chính thức.
5. Negative provenance/schema, duplicate physical play/replay grouping, draft không sinh official specificity; runner thật gọi FSM cho mỗi segment có coverage hợp lệ.
6. Integration Task08 → Points → Ledger/BoxScore: unresolved không cộng điểm, confirmed hợp lệ cộng đúng một lần, history không đọc tương lai, source/confirmation timestamps đúng, refinement/replay không nhân đôi. Giữ toàn bộ Task11 regressions.

Synthetic fixtures kiểm logic; real cache replay kiểm behavior trên observations; decoded-video evidence kiểm binding nguồn. Gắn nhãn rõ từng loại, không gọi replay là continuous full-video inference hoặc dùng latency replay làm FPS E2E.

Lệnh kiểm tra từ workspace root trên PowerShell, điều chỉnh theo CLI/path thật sau khi đọc code:

```powershell
$env:PYTHONPATH='codebase/src;codebase/scripts'
$env:PYTHONIOENCODING='utf-8'

codebase/.venv/Scripts/python.exe -m pytest codebase/tests/test_task08_temporal_shot_engine.py codebase/tests/test_task08_evaluator.py codebase/tests/test_task11_ledger_and_boxscore.py -q

codebase/.venv/Scripts/python.exe -m pytest codebase/outputs/acceptance-demo-20261110/test_acceptance_requirements.py -q -k 'predicted_entry_exit_cannot_confirm_made or crossing_cannot_bridge_long_observation_gap or production_evaluator_rejects_out_of_tolerance_made or production_evaluator_counts_duplicate_as_fp or points_without_geometry_stay_unresolved or only_confirmed_events_contribute or refined_event_cannot_be_reingested_under_new_id or team_revision_invalidates_incompatible_assist or status_revision_invalidates_assist or late_child_of_void_parent_is_not_counted or caller_cannot_mutate_recorded_raw_event'

codebase/.venv/Scripts/python.exe -m pytest codebase/tests -q
```

Ghi số collected/deselected và exit codes để tránh selector chạy 0 tests. Chạy các tests mới ở module mới nếu có. Các probes ngoài phạm vi REB/AST/UI còn fail phải được liệt kê đúng, không sửa/xóa probe để toàn bộ acceptance xanh. Không cài lại môi trường hoặc chạy training chỉ để xử lý Task08.

## 8. Chạy lại thực nghiệm và đầu ra

Sau khi tests liên quan pass, chạy production runner trên đúng 10 positive windows đã review theo intake hiện hành và toàn bộ negative segments có cache/provenance hợp lệ. Không mặc định play_001…010 là danh sách đúng. Xuất actual coverage và skip/failure reasons. Recognition không được đọc nhãn dù window selection là diagnostic có điều kiện.

Dùng cùng weights/input/config cho paired before/after; chỉ thay phần sửa đã khai báo. Chạy một đợt cần thiết, phân tích failures; chỉ lặp khi có code/config thay đổi với lý do rõ. Không grid search trên holdout. Recall giảm vì bỏ false confirmation phải báo cùng TP/FP/FN và lý do, không lén nới guard để khôi phục con số cũ.

Trong output mới, bàn giao tối thiểu:

- `run.json`, input/config/source snapshots, commands/logs và manifest hashes.
- Raw `shots_auto.jsonl`, `points_auto.jsonl`, transitions và observation/evidence references trước evaluation.
- Protocol diagnostic/frozen reference, match table, unmatched events và metric report với denominators, coverage, N/A reasons.
- Bảng before/after, failure taxonomy: detector dropout, gap/cut, invalid crossing, actor/team unknown, geometry/FT unresolved, evaluator correction.
- Negative inventory/review packet, provenance validation, actual category counts và pending-review list.
- Integration ledger/boxscore artifacts và paired OCR/ROI/identity regression summary.
- Test results và các phần chưa đủ điều kiện, phân biệt implemented / executed / measured / accepted.

Tạo `docs/reports/task08-shot-correctness-20261112.md` và handoff bước tiếp theo. Cập nhật `docs/tasks/task08.md`, `PLAN.md` và chỉ mục/handoff liên quan ở mức cần thiết; đánh dấu các claim cũ bị thay thế bằng bằng chứng mới, giữ lịch sử audit. Không ghi “pipeline thực tế” khi chỉ replay cache.

## 9. Điều kiện hoàn tất và cách bàn giao

Phần sửa core chỉ được coi VERIFIED khi probes liên quan pass trên production APIs; test evaluator gọi implementation thật; observed continuity và GT isolation có regression; downstream Task11 không hồi quy; kết quả thực nghiệm/artifacts tái lập được. Tests xanh không tự chứng minh đạt strict P≥95%, R≥90%.

Negative cohort chỉ nghiệm thu khi đủ số lượng/category theo protocol, evidence, provenance và review hợp lệ. Thiếu review/GT không cản sửa code, tests và tạo packet; phải bàn giao rõ phần phụ thuộc đó thay vì giả định được duyệt. Giữ Task08/MVP IN_PROGRESS cho tới khi các gate recognition, geometry, GT và full pipeline thực sự đạt. Không hạ scope PRA, hạ gate hoặc lấy human corrections thay automatic predictions.

Final response ngắn gọn bằng tiếng Việt: đã sửa gì, lệnh/test và số đo thật, links report/artifacts, phần còn chờ và task kế tiếp dựa trên bằng chứng. Không tuyên bố detector đã fine-tune, OCR accuracy tăng hoặc full demo hoàn tất từ kết quả của Task08.
