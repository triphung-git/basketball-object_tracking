# D04–D06 — Temporal PRA và dữ liệu/model gần rổ

Đọc [prompt tổng](00-master-execution.md), [Plan mới](../../../PLAN-DEMO-20261116.md), actual rules/protocol/user decisions hiện hành. Giữ per-task checkpoints, tự chuyển dependency-ready task và gom approvals vào Plan.

## D04 — Release/made/miss và ball/control/pass continuity

Điểm vào: `shots.py`, `points.py`, `ball.py`, `possession.py`, continuous adapters, reviewed development failures và current auto traces.

1. Error analysis từ detector→ball tracking→control/flight→release/crossing/outcome, dùng source PTS và bounded causal history. Phân biệt lift với release; không sửa timestamp bằng GT hoặc window-specific correction.
2. Made confirmation phải từ observed crossing và continuity đã chốt. Giữ max observed gap 0,35s trong profile hiện hành; không nới hoặc dùng predicted samples để giải timeout khi chưa có quyết định mới. Nếu cần đổi semantics ngoài quyền đã có, đưa exact ablation/cost/error proposal vào Plan, giữ baseline.
3. Miss eligibility và uncertain outcome phải có evidence, không biến mọi aborted trajectory thành miss chỉ để bật rebound. Missed shot có outcome/parent identity usable cho downstream; missing ball phải giữ reason/times/coverage.
4. Control/pass evidence từ observed bóng-người/relative motion/sustained actor sequence; xử lý dribble/flight/receive/ambiguity/cuts. Không nearest-player heuristic làm confirmed control, không loại hard frames để precision đẹp.
5. Với shot value, dùng release-time valid foot position/geometry và FT context/rule profile phù hợp. Không fallback 1PT khi distance missing; không dùng landing position hoặc metadata GT.
6. Bảo toàn FSM phase/replay/cooldown và reason codes; export raw observations/transitions/source refs để audit cả positives và negatives.

Tests: genuine positive/negative release/made/miss/control/pass, predicted crossing reject, max gap boundary, cut/track switch/scene change, uncertain/FT/value geometry, duplicated timestamps và monotonic PTS; required independent shot probes + full suite.

Real-run development có reviewed made/miss/control/pass, lưu matched traces/error index; so cùng source/config với baseline. Không chọn matching profile chỉ theo score tốt nhất rồi gọi quality gain. Các ca vẫn sai phải có evidence và remediation; không hard-code theo `play_id`.

**D04 PASS:** contracts/integrity/tests và causal video evidence đủ; temporal outputs dùng được cho D05. Technical PASS không thay P/R acceptance. Nếu chất lượng quá thấp để có demo PRA thật, tiếp tục cải thiện trong scope hoặc R01/R03, không gọi recognition feature complete từ synthetic positives.

## D05 — REB/AST orchestration, action rules và lifecycle

1. Reuse engines đã sửa đợt 01, nhưng xác minh production stream thực sự gọi chúng với shot/control/pass/identity/action context đầy đủ. Không chỉ constructors hoặc malformed dictionaries bị bỏ qua.
2. Rebound: eligible miss/final FT theo profile đã duyệt → observed sustained control/controlled tip có bằng chứng → team/player/subtype đúng. Team rebound `actor_id` rỗng; touch/loose/predicted/long-gap/dead-ball không tự credit.
3. Assist: confirmed pass/receiver/scorer/possession/team/action continuity và eligible parent score; apply current approved dribble/time/FT scope. Không đổi custom demo profile thành claim mọi luật FIBA đều như vậy. Thiếu action evidence cần thiết thì unresolved; không default `confirmed` hay confidence=0.9 để bù thiếu.
4. Parent links/physical IDs phải nhất quán ở engines→ledger→boxscore. Cho missed-shot dependency có typed contract riêng khi cần; không giả một made score để ledger chấp nhận rebound. Assist parent revision/team/scorer/void phải cascade đúng; late child/reload/replay không cộng lặp.
5. Xuất đủ event candidates/auto_confirmed/unresolved/raw audit/dependencies. Boxscore player + team-unassigned = totals và subtype conservation đúng; corrections không trộn raw auto.

Tests: 12 snapshot-defect probes đợt 01 qua production APIs, positive chains, FT/context/action boundaries, actor/conflict/cut/turnover, parent ordering/refinement/void, immutable records và checkpoint replay; full suite.

Real-run trên footage/context thật có các tình huống PRA được phép phát triển; hand-check evidence refs và totals. Muốn demo READY phải có genuine automatic positive cho PTS, REB, AST trong selected declared demo set, không chỉ all-zero files. Mở rộng clips/source hoặc review mới vào R02/R03 khi cần, không tạo events từ labels.

**D05 PASS:** technical tests/orchestration/invariants/outputs đầy đủ. Bằng chứng demo positives ghi riêng; nếu chưa có thì gate demo PRA pending dù tests đã pass. Agent tiếp tục candidate/data review preparation và việc độc lập thay vì báo đủ sản phẩm.

## D06 — Near-rim data review, local training và candidate decision

### Phase D06-PREPARE — làm ngay trong quyền hiện có

1. Tái sử dụng 49 supplementals và packet 8 frames đã trích dưới `quality-revision-20261116`; không xuất lại media/inference nếu source/hash đúng. Near-rim proximity không phải occlusion ground truth.
2. Chuẩn bị annotation/review UI có clip/frame context, bbox suggestions draft, visible/partial/fully-hidden/uncertain choices, ball/human/rim completeness, save/load/export và source offsets/hashes. Bóng hoàn toàn khuất không tự có bbox chính xác. Batch uncertain tách khỏi negative/train.
3. Tạo dataset proposal với original/checkpoint hashes, source family/exposure, quarantine/near-duplicate/split checks, augmentation/oversampling policy có thống kê thật. 30/30 REB/AST là collection target theo existing policy, không biến thành train gate cứng nếu không có frozen decision.
4. Prepare exact local recipe/resource/disk/VRAM/readiness, optimizer/loss smoke và paired evaluation plan. Quyền local CUDA/train đã có thì không hỏi lại, nhưng chưa review bbox không được auto-approve labels.
5. R01 trong Plan phải có UI/evidence/tested export/ingest commands và missing labels cụ thể; không chỉ bắt người dùng viết JSON. Synthetic UI/ingest tests tách dữ liệu thật.

### Phase D06-TRAIN — chỉ dùng labels/authorization thật sự đủ

1. Sau reviewed labels có evidence và dataset checks, chạy isolated local pilot rồi candidate theo recipe đã review/phạm vi được cho phép; không nhiều GPU jobs trùng nhau hoặc sửa source snapshots đang chạy.
2. Heartbeat/PID/epoch/batch/loss/VRAM/disk/artifacts thật, real detection loss với labels và finite gradients, checkpoint reloadability/class order. Không gọi target epochs đã xong khi chỉ có một epoch.
3. Paired native detector + continuous downstream trên same frame/source/config/evaluator version: ball recall/false observations, near-rim visibility groups, human/rim regressions, OCR/crops/identity/control/pass/PRA và latency. Eval trên train-exposed source phải ghi diagnostic; freeze/reserve không tự thay.
4. Không promote default từ mAP hoặc unit tests. Giữ baseline fallback, candidate hash/profile/rollback và R05 nếu cần quyết định mới. Không dùng train on reviewed evaluation labels rồi báo lại cùng test như unseen.

Tests: dataset/review approval isolation/binding/splits/offsets, loader/label completeness, readiness loss smoke, model adapter/class mapping và downstream regressions; full suite nếu code thay đổi. Tất cả job đã launch phải được monitor đến terminal/checkpoint hoặc state RUNNING trung thực, không báo completed từ launch.

**D06 gate:** PREPARE có thể PASS với TRAIN WAITING_REVIEW, R01/R05 rõ và reports đầy đủ; toàn task chưa được ghi training complete. Scheduler tiếp tục D07/D08/D09 bằng verified baseline. Sau user review, resume đúng phase, không làm lại preparation và không xin lại quyền đã cấp.
