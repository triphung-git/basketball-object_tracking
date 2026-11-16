# Prompt thực thi — Task08: temporal shot engine, basket confirmation và shooter history

Để thực thi toàn bộ lộ trình demo theo thứ tự QA Task07 → đánh giá thật Task08 → ledger → rebound/assist và dashboard → nghiệm thu/đóng gói, dùng [prompt điều phối hoàn thiện demo](demo-completion-priority-execution.md). File này là yêu cầu chi tiết cho riêng shot engine; trạng thái implementation/metrics phải đối chiếu artifacts hiện tại trước khi chạy lại.

Bạn là Senior AI/Python Engineer trực tiếp làm việc trong repository này. Hãy **thực thi phần tiếp theo của Task08**, từ khảo sát code/artifacts hiện hành đến triển khai, chạy dữ liệu thật, kiểm thử, đánh giá và bàn giao. Không kết thúc ở kế hoạch hoặc pseudocode. Tự giải quyết các lựa chọn kỹ thuật thông thường trong phạm vi này.

Mục tiêu là xây shot/points engine theo chuỗi thời gian, kết hợp bốn cải tiến: FSM bốn pha; xác nhận bóng xuyên vành từ trên xuống; truy lịch sử OCR trong 2 giây trước release với fallback cấp đội; và negative cohort tối thiểu 30 tình huống thật trước nghiệm thu. Giữ nguyên công việc fine-tune đang chạy và kết quả baseline đã có.

## 1. Đọc hiện trạng và tiếp tục từ checkpoint đã hoàn thành

Đường dẫn tính từ workspace root. Đọc AGENTS.md áp dụng nếu có, sau đó:

1. `docs/DEVELOPMENT.md`, `PLAN.md`, `docs/tasks/task08.md` và contracts/rules/evaluation protocol hiện hành.
2. `docs/reports/task08-critical-moments-baseline.md`.
3. `docs/handoffs/task08-critical-baseline-to-shot-engine-20261108.md`.
4. `docs/reports/task08-scoring-review-intake-20261107.md` và handoff review → diagnostic.
5. `docs/reports/task07b-decoupling-20261107.md`, `docs/reports/task07c-acceptance-report-20261107.md`.
6. `docs/reports/task07a-local-finetune-20261108.md` và `codebase/outputs/task07a-finetune-20261108/job/status.json`.
7. Source/contracts/tests về detector, tiled inference, ball/player tracking, identity/OCR history, court geometry, PTS/cuts và baseline runner.

Pha baseline đã có runner `codebase/scripts/run_task08_critical_baseline.py`, tests và artifacts tại `codebase/outputs/task08-critical-baseline-20261108/`. Không làm lại toàn bộ baseline nếu cache/source/model/config/frame coverage vẫn khớp. Đối chiếu số liệu từ raw artifacts; report không phải oracle.

Các điểm cần sửa cách diễn giải trước khi dùng làm giả thuyết:

- **10/10 cửa sổ có rim detection tại basket chỉ là coverage trên mẫu được chọn.** Chưa có GT hình học đầy đủ thì không gọi là detector chính xác/đáng tin cậy 100%, không gán probability=1 hoặc bỏ kiểm tra false rim.
- Observed ball coverage 62,05% của baseline khác định nghĩa/tập mẫu với ball recall 50% Task07. Không kết luận accuracy đã tăng từ phép so trực tiếp đó.
- Tốc độ ảnh giảm gần lưới là một feature cần kiểm chứng. Không tự khẳng định nguyên nhân vật lý là ma sát lưới từ video 2D, không lấy nó làm điều kiện bắt buộc hoặc bằng chứng đủ duy nhất.
- Các gợi ý lịch sử dùng scoreboard/review outcome để xác nhận điểm hoặc lấy người gần rổ nhất làm rebound không áp dụng cho engine tự động này. GT/scoreboard dùng riêng cho audit/evaluation; attribution cần bằng chứng đúng thời điểm.

Task07 chưa đạt quality gate. Task08 được xây candidate từ observations thực tế nhưng không tự nâng trạng thái Task07, không coi predicted là observed và không triển khai assists/rebound attribution cá nhân trong lượt này.

## 2. Đầu vào, exposure và giới hạn nhận diện

Tái dùng:

- Baseline recognition manifest, raw detections, ball/player tracks, OCR evidence, run/config hashes và video overlay tại `codebase/outputs/task08-critical-baseline-20261108/`.
- `codebase/outputs/task08-scoring-intake-20261107/adjudicated-v3/critical-windows-draft.json` và `events-reviewed.json`.
- Video nguồn, roster và court/ROI config có source binding đã kiểm trong baseline.
- Draft bbox packet 20 keyframes tại baseline để chuẩn bị review; không tự chuyển thành approved GT.

10 cửa sổ hiện hành: `play_001/003/004/006/008/015/021/023/027/028`. Đã có 34 review nhất quán; không hỏi lại các xác nhận đã chốt. Giữ null/uncertain tại các trường còn thiếu.

Tách recognition và evaluation bằng manifest/API riêng. Recognition chỉ nhận media/PTS/operational camera context, roster/rule profile hợp lệ và cấu hình thuật toán. Không đưa `reviewed_shooter_id`, review release/basket times, outcome/value/score, negative labels hoặc notes vào engine. Review times chỉ dùng chọn cửa sổ diagnostic và matching hậu nghiệm sau khi predictions được freeze/hash.

Các cửa sổ chọn theo review là **conditional diagnostic, same-match exposed**, không phải blind shot discovery hoặc independent-match test. Nếu chạy thêm continuous segments, dùng source bounds độc lập với event GT và báo rõ cách chọn. Giữ đủ pre-roll/warm-up để history 2 giây có cơ hội hình thành; thiếu lịch sử ở biên clip phải được đánh dấu.

Không train/đổi detector hoặc OCR weights trong task này. Không stop/restart fine-tune job, đổi `.venv-train` hay sửa expected hashes để che thay đổi. Candidate shot config/module có version riêng; lưu provenance nếu việc thêm source mới ảnh hưởng snapshot của job khác. Không upload media hoặc tạo job cloud ngoài phạm vi đã được giao.

## 3. FSM bốn pha thời gian

Triển khai `Ready -> Release -> FlightArc -> Outcome`, trong đó pha Outcome phân nhánh `Basket` hoặc `Rebound/Miss`. Có đường `Unresolved/Aborted/Reset` khi thiếu bằng chứng; đây là trạng thái phụ điều khiển an toàn, không phải ép mọi chuỗi đi đến Basket/Rebound.

| Pha | Bằng chứng và hành vi cần có |
|---|---|
| Ready | Theo dõi tương tác bóng–actor qua nhiều frame; duy trì actor candidates và history. Chưa có player_id vẫn được giữ actor track/body evidence. Không mặc định strict controller upstream đã đúng. |
| Release | Phát hiện tự động bóng rời vùng tay/thân với thay đổi khoảng cách/hướng chuyển động qua thời gian; đánh giá motion continuity, candidates cạnh tranh và uncertainty. Không kích hoạt chỉ vì một frame upward motion hoặc review marker. |
| FlightArc | Theo dõi diễn biến hướng vùng rổ; có thể dùng fit/smoothing làm feature và prediction bridge có hạn. Không yêu cầu parabol hoàn hảo trên ảnh 2D; pan/zoom/perspective phải được xét. Phân biệt shot với pass, dribble, lob và turnover. |
| Outcome | Xác nhận Basket bằng chuỗi observed evidence tại rổ; Miss bằng bằng chứng bóng bật/đi khỏi sau tương tác và outcome đủ rõ. Rebound ở đây chỉ là pha bóng sống sau miss/candidate handoff cho Task09, không tự ghi stat rebound cho người/đội. |

Yêu cầu triển khai:

- Mỗi shot có `shot_id`, source/segment/camera IDs, release candidate time, timestamps chuyển trạng thái, reason codes và evidence refs. Dùng PTS thực và thresholds theo giây, không hard-code số frame theo giả định 30 FPS.
- Không chọn shooter theo người gần rổ khi bóng tới rổ. Actor gần bóng tại release chỉ là candidate, phải so với tương tác trong history và các actor cạnh tranh.
- Timeouts, max unobserved gap, hysteresis và cooldown có cấu hình/version. Ghi rõ lý do gap được bridge hoặc vì sao shot bị ngắt; không dùng prediction-only để confirm Basket.
- Reset/abort phù hợp ở cut, replay boundary, layout không hợp lệ, source discontinuity hoặc ambiguous association. Không nối đường bóng qua cut để hoàn thành shot giả.
- Trường hợp bắt gặp bóng gần rổ mà thiếu release được giữ outcome-only/unresolved shooter evidence riêng; không bịa Ready/Release hoặc coi chuỗi đủ bốn pha đã được quan sát.
- Miss chưa đồng nghĩa chắc chắn có rebound; timeout/mất bóng không tự là miss. Rim-bounce rồi vào vẫn có thể là made sau khi evidence window đủ.
- One physical shot → tối đa một score event. Có chống lặp do frame lặp, seek/replay pipeline, reload và nhiều lần bóng vào ROI; không chỉ cooldown cố định vì có thể làm mất hai cú ném thật gần nhau.

## 4. Basket confirmation: vành rổ, hướng xuyên vành, net cue

Xây một `rim evidence / rim-local geometry` layer trước khi dùng bbox làm cổng xác nhận:

1. Kiểm tra rim detections nhất quán qua thời gian, association đúng rổ, confidence/size/jitter và camera validity. Không lấy một bbox rim ngẫu nhiên trên poster làm anchor.
2. Đối chiếu annotation semantics: bbox rim có thể chứa bảng/lưới/cả cụm rổ. Không mặc định tâm/biên bbox là khẩu độ vành rổ. Có aperture/entry band đáng tin cậy mới dùng crossing gate; nếu cần calibration mới, tạo dữ liệu draft có nguồn và giữ geometry validity rõ.
3. Biểu diễn ball positions/velocities tương đối theo rim, normalize theo kích thước rim phù hợp và tính vận tốc bằng delta PTS. Giảm tác động rim/camera motion trước khi so tốc độ; không gọi pixel/s là vận tốc 3D.
4. Xác nhận made bằng chuỗi quan sát trước–tại/gần–sau vành: bóng đi từ vùng trên, qua khẩu độ hợp lý, tới vùng dưới theo hướng xuống, với continuity/uncertainty và bằng chứng observed đủ. Một lần bbox overlap, bóng từ dưới lên, bóng đi sau/trước rổ hoặc chỉ có predicted crossing đều chưa đủ.
5. Smoothing hoặc nội suy chỉ hỗ trợ association trong gap đã giới hạn, không tạo thêm frame observed và không lấp toàn bộ đoạn rổ bị che rồi xác nhận made.

Net/deceleration cue:

- Tính feature giảm tốc tương đối trước/sau tương tác vành cùng độ tin cậy đo, số samples và camera stability. Có thể ghi net-local motion nếu nguồn hỗ trợ, tách chuyển động lưới khỏi camera/background.
- Dùng như evidence hỗ trợ có weight/availability flag. Thiếu net cue không tự loại một made có crossing rõ; giảm tốc do bounce/camera/occlusion không tự xác nhận made.
- So candidate crossing-only với crossing + optional net/deceleration cue trên cùng cohort; chỉ giữ cue nếu có lợi ích đo được mà false positives/recall không bị che.
- Đặt camera pan/layout-invalid thành lý do abstain hoặc local rim-relative fallback được kiểm chứng. `play_006` là case bắt buộc; không sửa ROI bằng vị trí bóng GT.

Không dùng scoreboard OCR hoặc review outcome để tự cộng điểm. Rim/shot/made evidence và việc xác định point value phải tách riêng.

## 5. Shooter history trong [release − 2,0s; release]

Tại release do engine tìm được, truy lịch sử **actor track đã được liên kết với bóng** trong khoảng thời gian này:

- Thu thập OCR candidates, capture PTS, crop quality, visibility, team evidence và track association confidence. OCR có thể nằm trên mặt áo trước/sau hoặc góc khác nếu crop đủ rõ; không giả định cứ đối diện camera là đọc được.
- Resolver dùng weighted temporal consensus và các mẫu hỗ trợ, không đơn giản chọn reading có confidence cao nhất. Kiểm tra roster theo cặp team + jersey, xung đột số, stale readings, track fragmentation/ID switches.
- Không merge hai người chỉ vì cùng số áo. Chỉ nối tracklets nếu có association evidence độc lập; không truy qua camera cut hoặc track switch chưa giải quyết.
- Chỉ lấy evidence có capture PTS <= release. Không dùng OCR sau release/basket, nhãn shooter hoặc final whole-track mapping để gán ngược. Ghi riêng event_time, observation_time và decision/emission_time; mọi publication phải causal theo evidence sẵn có.
- Giữ player_id null khi thiếu/xung đột OCR, và ghi reason/coverage. Không ép chọn số áo gần roster nhất để tăng số event attributed.

Fallback cấp đội:

- Khi actor track tại release có team evidence màu áo/jersey đã qua quality/conflict checks và đủ consensus, có thể đặt team_id dù player_id chưa biết. Nếu team cũng chưa chắc thì giữ null.
- Chỉ cộng team points khi made và point value được xác nhận hợp lệ. Output có `attribution_level=player/team/unknown`, evidence refs và `unresolved_identity` khi cần.
- Một basket không được cộng lại vào tổng đội khi sau này chỉ bổ sung danh tính. Player attribution refinement phải tham chiếu cùng score event/shot và có idempotency/revision rõ.
- Báo event detection, team attribution và strict player attribution riêng. Team fallback không được tính thành strict-player TP hoặc dùng để hạ tiêu chuẩn nghiệm thu hiện hành.

## 6. Point value và event contract

Triển khai/tái dùng `shots.py`, `points.py` và adapter/CLI phù hợp kiến trúc hiện có. Cấu hình candidate riêng; không đổi approved inference pipeline âm thầm.

- Value theo rule profile có applicability/version hợp lệ và geometry đáng tin tại release/last floor contact. Không dùng vị trí tiếp đất, không suy FT chỉ từ vị trí đứng, không dùng shot_kind/value trong review làm recognition input.
- Nếu made rõ nhưng value/FT context chưa đủ, giữ made evidence và unresolved point_value; không tự mặc định 1 hoặc 2 để hoàn thiện demo.
- Event tối thiểu có shot/source refs, release/outcome/confirmation times, trạng thái candidate/provisional/auto_confirmed/void/unresolved, team/player/value, attribution level, observed evidence và reason codes.
- Cộng points theo event có đủ điều kiện; aggregate raw auto và corrected/audit outputs riêng. Không đọc GT hoặc point selector mỗi pha làm đường đi chính.
- Không mở rộng sang full rebound/assist engine. Chỉ handoff miss/rebound-phase candidates cho Task09, giữ attribution chưa kiểm chứng null.

## 7. Negative cohort: tối thiểu 30 tình huống thật, duy nhất

Tự khảo sát footage cục bộ được phép sử dụng, trích clip/context và chuẩn bị review packet. Không chờ người dùng tự tìm toàn bộ các pha. Không dùng holdout đã khóa để mining/tuning, không tải hoặc upload footage ngoài phạm vi đã được phép.

Mục tiêu phân bố ban đầu: 10 clean misses, 8 rim/backboard misses, 6 turnover/non-shot situations, 6 replay segments. Có thể điều chỉnh theo footage thực tế nhưng phải đủ >=30 events/segments duy nhất, có đủ bốn nhóm, nêu phân bố và case còn thiếu. Primary category không cộng trùng; giữ secondary tags.

- Bóng chạm bảng/vành rồi vào là positive counterexample cần bổ sung, không gán negative chỉ vì có va chạm. Thu thêm các ca này khi nguồn có.
- Replay của một pha made là negative đối với việc **cộng thêm điểm**, dù bóng thật sự xuyên vành trong replay. Liên kết replay với original physical play; không đếm hai clip trùng hoặc nhiều frame cùng pha thành nhiều negatives độc lập.
- Dùng event/source groups để dedup và chia calibration/validation; original và replay của cùng pha phải cùng nhóm. Với một trận đã exposure chỉ gọi same-match diagnostic validation; independent-match test cần nguồn khác phù hợp.
- Packet có source/clip hashes, source PTS bounds, primary/secondary categories, action/outcome visibility, review status, duplicate/original-play refs và uncertainty. Labels agent đề xuất giữ draft; predictions và notes không tự thành approved GT. Chỉ dùng nhãn đủ review cho metrics chính thức, báo số draft/approved riêng.
- Candidate mining có thể dùng model để tìm vùng nghi vấn nhưng phải có sampling/source-coverage audit, tránh chỉ giữ các ca engine đã xử lý tốt. Không gọi frame không có detection là negative event.
- Đánh giá replay suppression tự động phải dùng image/temporal duplication hoặc broadcast cues được engine tìm từ media. Không cấp replay GT flags/exclusion intervals của evaluator vào runtime rồi tính đó là khả năng tự nhận replay. Operational exclusions đã cấu hình trước phiên phải báo thành một chế độ riêng.
- Nếu nguồn thực sự không đủ 30 ca hoặc review chưa xong, hoàn tất code, collection packet, available evaluation và báo thiếu cụ thể. Không bịa/copy/augment cùng pha để đủ quota; chưa nghiệm thu engine khi gate này chưa đạt.

## 8. Thực thi và vòng cải tiến tự động có kiểm soát

1. Audit baseline artifacts/config/hashes, tạo sanitized input và candidate config/version.
2. Triển khai FSM, rim confirmation, bounded shooter history, team fallback và idempotent points.
3. Viết tests trọng yếu; chạy trên cached raw observations nếu đủ contract/coverage, chỉ infer/OCR bổ sung phần thiếu. Mọi run ghi rõ cache reuse và inference mới.
4. Chạy đủ 10 positive windows và negative cohort có sẵn; chuẩn bị phần review còn thiếu. GT chỉ nạp trong evaluator sau prediction freeze.
5. Phân tích FP/FN/unresolved theo các tầng: release → flight association → rim crossing → optional net cue → history identity → team/value → dedup/replay.
6. Thực hiện tối đa 3 candidate iterations có giả thuyết rõ trên calibration, mỗi lần thay một nhóm yếu tố. Giữ cả regression/failure artifacts. Không tuning trên tập validation đã freeze rồi gọi là đánh giá độc lập; không lặp vô hạn cho tới khi đạt số đẹp.
7. So sánh ít nhất single-frame diagnostic reference (nếu có), temporal crossing candidate, temporal + history/team fallback; ablate net/deceleration cue riêng khi evidence đo được. Tách detection gain với attribution gain, không coi fallback là cải thiện strict OCR.
8. Chọn candidate theo evidence và false-score tradeoff, chạy frozen evaluation theo protocol đã chốt. Nếu dữ liệu chưa đủ, kết luận conditional/partial và tiếp tục bàn giao phần độc lập; không tự hạ ngưỡng.

Freeze matching/tolerances và split trước validation. Kế thừa protocol hợp lệ hiện có; thông số còn thiếu được đề xuất rõ và giữ metric exploratory cho đến khi chốt. Ngưỡng strict points hiện hành P>=95%, R>=90% là mục tiêu nghiệm thu, không phải kết quả hứa trước. Tập 30 negatives là mức tối thiểu kiểm thử, không bảo đảm tổng quát hay độ tin cậy gần 100%.

## 9. Tests và báo cáo bắt buộc

Tests phải kiểm hành vi thực tế, gồm:

- Full ordered shot sequence; frame đơn lẻ/overlap-only không confirm; below-to-above, near miss, ball behind rim, wrong rim và prediction-only không tạo score.
- Rim bounce rồi miss; rim/bank bounce rồi made; missing net cue không làm mất made có crossing đủ; deceleration đơn lẻ không tạo made.
- Camera pan/cut/layout invalid; PTS/VFR/gaps; history ngắn ở biên clip; pass/dribble/turnover không bị ép thành shot made.
- OCR trước release được dùng đúng actor, OCR sau release bị loại; conflict cùng số áo khác đội, ID switch và stale history không gán nhầm shooter.
- Team fallback khi team đủ evidence, unknown khi không đủ; không tính team-only thành strict-player TP; identity refinement không cộng điểm đội lần hai.
- Replay/original grouping, repeated frames, seek/reload và hai shot thật gần nhau: idempotency đúng mà không blanket-suppress event thứ hai.
- GT isolation, không truyền replay/outcome labels vào runtime, không auto-approve draft negatives; partial run không ghi completed/accepted giả.

Chạy regression phù hợp các thay đổi và integration run thật. Tests/synthetic không thay evidence accuracy. Giới hạn CPU threads phù hợp, không tranh GPU với fine-tune job; báo timing/resource contention thực đo.

Artifacts tại output directory mới, ví dụ `codebase/outputs/task08-temporal-engine-<run-id>/`:

- Run/config/source/code/package hashes, sanitized input và split/exposure manifest.
- `shot_state_transitions.jsonl`, `shots_auto.jsonl`, `points_auto.jsonl` hoặc contracts tương đương đã tích hợp.
- History/rim/crossing/net/dedup evidence, overlay video, timeline và event evidence clips.
- Negative cohort manifest, dedup/source audit, clip index và draft/approved review packet tách biệt.
- Paired comparison/ablations, TP/FP/FN, unresolved/coverage, team vs player strict metrics, per-negative-category false-score counts, latency và giới hạn cỡ mẫu. Thiếu nhãn/tolerance thì đánh dấu unavailable/exploratory thay vì bịa điểm số.

Viết `docs/reports/task08-temporal-shot-engine.md`, handoff cho Task09/11 và cập nhật Task08/PLAN theo evidence thực tế. Preserve baseline lịch sử và artifacts người dùng. Không commit/push/publish hoặc thay approved production weights trong lượt này.

## 10. Kết thúc với kết quả review được

Hoàn thành phần implementation, actual runs, tests, negative collection và available evaluation trong phạm vi đã giao. Không hỏi lại các quyết định người dùng đã chốt hoặc quyền làm các bước routine này. Nếu thiếu footage/GT/rule applicability, chỉ nêu đúng đầu vào còn thiếu sau khi đã hoàn tất phần độc lập; không tự gán approval.

Chỉ gọi engine accepted khi đủ positive/negative đã review, causal/GT-isolation/idempotency guards đạt và quality gates theo protocol có bằng chứng. Nếu chưa đạt, giữ Task08 IN_PROGRESS, báo failed criteria/partial scope; không đánh dấu full demo hoàn chỉnh từ 10 positive windows hoặc team-only results.

Phản hồi cuối gồm: code đã thay đổi, lệnh/run/artifacts, tests, metrics thực đo, candidate được giữ và lý do, các gate còn thiếu cùng task tiếp theo cụ thể. Không tuyên bố cải thiện từ số tests, prediction coverage hay rim presence 10/10.
