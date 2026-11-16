# Prompt thực thi — Hoàn thiện demo Automatic Stats theo thứ tự ưu tiên

Ngày: 2026-11-09. Bạn là Senior AI/Python Engineer chịu trách nhiệm hoàn thiện demo của repository này. **Hãy thực thi trực tiếp: sửa code, xử lý dữ liệu dẫn xuất, chạy pipeline thật, kiểm thử, tích hợp giao diện và bàn giao. Không dừng ở kế hoạch, pseudocode hoặc tạo thêm prompt.**

Mục tiêu đã chốt: MP4 3x3 offline → detection/tracking → team/OCR/identity → shot/points/rebounds/assists tự động → heatmap/box score → dashboard/evidence/exports. Cấu hình roster, sân, ROI và rules trước phiên được phép; không nhập/xác nhận từng pha để tạo stats chính. Realtime không phải điều kiện bắt buộc của demo offline.

Thực hiện theo thứ tự bên dưới, tiếp tục phần độc lập khi một gate thiếu dữ liệu. Đừng kết thúc lượt sau checkpoint đầu tiên hoặc hỏi lại có tiếp tục phần đã giao hay không. Giữ riêng trạng thái **implemented, executed, measured, accepted**; không gọi toàn bộ demo hoàn thành khi còn thiếu một stat hoặc chưa có bằng chứng chất lượng.

## 0. Kiểm kê, xác minh và bảo vệ công việc hiện có

Đọc AGENTS.md áp dụng nếu có; `docs/DEVELOPMENT.md`, `PLAN.md`, `docs/MVP-v2-proposal.md`, tasks 04–15 và contracts/rules/evaluation protocol hiện hành. Đọc thêm:

- `docs/reports/task07a-local-finetune-20261108.md` và `codebase/outputs/task07a-finetune-20261108/job/status.json`.
- `docs/reports/task07c-acceptance-report-20261107.md`.
- `docs/reports/task08-critical-moments-baseline.md`, `docs/reports/task08-temporal-shot-engine.md` và handoffs liên quan.
- `docs/prompts/task08-temporal-shot-engine.md` để tái dùng yêu cầu chi tiết của shot engine, thay vì xây lại từ đầu.
- Source/tests/artifacts hiện có về dataset preparation, GPU readiness, shots/points, tracking/OCR, court/heatmap và evaluator.

Các phát hiện dưới đây là điểm vào cần xác minh lại, không phải trạng thái bất biến:

1. Dataset/CUDA wheels đã tải đủ; CUDA installation có log thành công. Readiness job dừng ở `preparing_mixed_dataset` vì một số bbox vượt biên. GPU training smoke/preflight chưa được xác nhận chỉ từ log cài package.
2. `shots.py`/`points.py` đã có. Report Task08 ghi 2/10 baskets và 0/10 strict-player matches trên positive windows; phải đối chiếu raw artifacts trước khi kết luận.
3. Negative manifest còn `draft_unreviewed`. Runner `run_task08_temporal_shot_engine.py` có nhánh gán `fp_detected=False` và các metric 0 FP/100% specificity bằng giá trị cố định; đây chưa phải đánh giá thật.
4. `points.py` có fallback 1 điểm khi không có court distance; cần thay bằng unresolved nếu không có bằng chứng khác đủ xác định value.

Freeze run/source/model/config/package hashes. Lưu output/report mới, giữ artifacts cũ để audit. Không sửa GT/split đã khóa, không overwrite original dataset/checkpoint, không in `.env`/signed URL. Kiểm tra PID, command identity, heartbeat và stage logs trước khi restart; không chạy job trùng hoặc dừng một job còn hoạt động chỉ vì status cũ.

Phạm vi đã cho phép gồm khôi phục local preparation/fine-tune theo recipe đang có, sửa các lỗi nêu trên và xây phần demo còn thiếu. Không tự tạo chi phí/cloud job, upload media, đổi model family hay publish bên ngoài. Làm lựa chọn kỹ thuật thường lệ trong phạm vi này mà không xin lại quyền đã có.

## Ưu tiên 1 — Khôi phục data QA và chốt đầu vào fine-tune Task07

### 1A. Audit toàn bộ nhãn lỗi, không sửa mù

- Đọc `job/restart-03/preparing_mixed_dataset.log` hoặc log mới hơn; tạo audit đầy đủ ảnh/nhãn lỗi, source split/group, class, tọa độ gốc và loại lỗi.
- Phân biệt sai số làm tròn epsilon, bbox bị cắt bởi biên ảnh, bbox thực sự sai, zero-area/nonfinite, class mapping và nhãn thiếu. Đo mức vượt biên theo pixel/normalized coordinates trước khi chọn xử lý.
- Chỉ sửa trên dataset dẫn xuất có manifest/version. Numerical clipping hoặc intersect bbox với ảnh chỉ được áp dụng theo policy hình học rõ ràng, giữ class/nguồn và ghi before/after. Box mơ hồ hoặc mất nội dung đáng kể cần quarantine/review; không tự vẽ lại đối tượng.
- Không xóa riêng bbox sai rồi biến vật thể thật thành background âm tính. Khi nhãn không đủ tin cậy, quarantine cả ảnh khỏi bản train dẫn xuất hoặc chuẩn bị review, giữ nguyên original.
- Báo counts theo split/class và ảnh hưởng phân bố. Không âm thầm bỏ nhiều dữ liệu rồi tuyên bố QA đạt; thiếu coverage/class/split phải trở thành blocker có tên.
- Giữ 49 supplemental rows đã duyệt nếu binding còn hợp lệ; không đưa 308 draft rows vào train chỉ để tăng số lượng. Không tự sửa approval fields trong packet nguồn.
- Chia/quarantine theo source family, near-duplicate/exact-pixel evidence và lịch sử exposure; không chuyển nhóm checkpoint đã train sang test rồi gọi unseen. Tập một trận chỉ là same-match diagnostic.

### 1B. Hoàn tất readiness và chạy candidate theo authorization hiện có

- Tái sử dụng ZIP/CUDA wheels đã xác minh; không tải/cài lại vô ích. Kiểm CRC/hash ZIP, original export và các stage outputs trước khi resume.
- Sửa orchestration để tiếp tục từ stage thất bại có kiểm chứng: reuse một export directory chỉ sau khi đối chiếu archive/provenance; không bỏ guard tồn tại thư mục một cách mù quáng.
- Xác minh `.venv-train`: torch/torchvision CUDA tương thích, GPU khả dụng và real forward/loss/backward/optimizer smoke với checkpoint gốc. Không coi `cuda_available=True` là toàn bộ training đã chạy được.
- Tạo mixed dataset, kiểm class order, hashes, split membership và dataloader. Lưu dependency lock, recipe, hardware/VRAM và readiness report.
- Khi đủ điều kiện, tiếp tục một fine-tune candidate theo recipe local đã được duyệt/ghi trong project, output mới; không sinh nhiều training jobs. Trạng thái job phải phản ánh epochs/artifacts thật, không chỉ một process còn sống.
- Giữ approved inference baseline; candidate model có profile/version riêng. Chỉ chọn candidate sau paired evaluation đúng preprocessing/tile/mapping, ball recall/false observations, human/rim regression, crop OCR/identity và latency. mAP native tăng không thay thế downstream acceptance.
- Nếu train đang chạy lâu, tiếp tục phần độc lập bên dưới. Không sửa source/config snapshot của experiment đang freeze hoặc ghi lại expected hashes để che thay đổi; tách run-code snapshot/version phù hợp.

**Đầu ra P1:** dataset QA/quarantine/repair manifest, mixed data có binding, GPU smoke/readiness, candidate training status/logs, paired comparison nếu đã đủ thời gian chạy. Nếu dữ liệu cản trở thật sự, báo đúng blocker và vẫn tiếp tục các phần độc lập.

## Ưu tiên 2 — Sửa đánh giá Task08 và hoàn thiện shot/points có bằng chứng

### 2A. Loại bỏ metric giả lập

- Loại các nhánh dùng category/expected outcome để quyết định false positive và các metric được hard-code. Nhãn negative không được làm recognition input.
- Thực sự decode/infer hoặc dùng cache hợp lệ cho từng negative segment; chạy cùng FSM/points engine như positive segments, ghi predictions/evidence trước evaluation.
- Metric tính từ one-to-one matching predicted events với GT đủ review, theo protocol/tolerances freeze trước validation. TP/FP/FN, unknown/unresolved, coverage và sample counts có denominator rõ; denominator 0 → N/A.
- Negative cohort >=30 tình huống duy nhất, đủ clean misses, rim/backboard misses, turnover/non-shot, replay. Xác minh source bounds, clip/frame hashes, visibility, original/replay grouping, source exposure và review status. Mô tả ghi trong manifest không chứng minh clip đã có nội dung đó.
- Phần nhãn còn draft chỉ cho exploratory diagnostic, không dùng để công bố specificity chính thức. Chuẩn bị review packet có video/evidence; không tự ký duyệt hoặc bịa/copy pha để đủ 30.
- Cho evaluator một fixture engine cố tình tạo false score để kiểm tra FP thật sự tăng; 0 predicted events không được biến thành kết luận chất lượng tốt nếu positive recall/coverage thấp.
- Giữ report cũ là historical/unverified khi cần, tạo corrected report chỉ rõ metric nào chưa đủ bằng chứng. Không xóa dấu vết claim cũ để làm như đã được đo đúng từ đầu.

### 2B. Sửa những điểm gây sai đầu ra

- Duy trì FSM nhiều frame, observed/predicted tách biệt, causal shooter history [release−2s, release], team fallback, camera-cut guards và idempotency theo prompt Task08 chi tiết.
- Rim presence 10/10 không là accuracy 100%. Aperture từ một tỷ lệ bbox cố định phải được xác minh như hypothesis/calibration; không gọi là physical ring geometry đã biết.
- Crossing phải có observed evidence và continuity hợp lệ. Giảm tốc/net cue là feature hỗ trợ được ablate, không là bằng chứng vật lý chắc chắn hoặc thay thế hoàn toàn đoạn bóng bị mất.
- Made chưa đủ để cộng điểm nếu value/FT context chưa rõ. Loại fallback mặc định 1 điểm khi thiếu geometry; giữ `point_value=null`, status/reason phù hợp. Không coi mọi vị trí gần rổ là FT hoặc dùng điểm trong review làm đầu vào.
- Event-only, team attribution, player strict attribution và value correctness báo riêng. Team fallback không thành strict-player TP; unknown vẫn được tính trong missing/coverage theo protocol.
- Replay suppression phải dựa trên evidence runtime hoặc chế độ operational exclusion đã khai báo riêng; không đưa replay GT flag vào engine rồi tính là tự nhận replay. Cooldown đơn thuần không chứng minh xử lý mọi replay.
- Chạy tối đa 3 vòng candidate calibration có giả thuyết; giữ failure/regression artifacts. Không tuning trên frozen validation hoặc chọn chỉ các pha đã thành công để chứng minh full-demo accuracy.

**Đầu ra P2:** runner/evaluator thật, corrected metrics/report, negative review/provenance packet, shots/points evidence và danh sách lỗi còn thiếu. Chưa đủ quality/data thì Task08 vẫn IN_PROGRESS.

## Ưu tiên 3 — Task11: unified event ledger và box score

Xây core tổng hợp trước để các engines có contract chung; adapter cho rebound/assist có thể hoàn thiện khi Task09/10 sẵn sàng. Không cần giả lập stats để nối UI.

- Schema versioned có event/shot/pass/control/source IDs, PTS, actor/team/value/subtype, status, evidence/dependencies và revision.
- Chỉ aggregate events đủ điều kiện auto-confirmed; candidate/provisional/unknown/unresolved không tự thành số liệu chắc chắn.
- Append-only raw log, correction/audit riêng; idempotency cho repeated notifications, duplicate frames, seek/reload/resume và reordering trong contract.
- Actor unknown→known không cộng lại team points; team-only points không tự thành player points. Team rebound không cộng vào personal rebound.
- Score void/value/team revision phải cập nhật totals và invalidation dependencies của assists; không để orphan events hoặc double-count khi replay.
- Initial-score offset khai báo riêng cho clip giữa trận, không OCR scoreboard làm oracle, không trộn offset với points quan sát được trong clip.
- Export `events_auto.jsonl`, `boxscore_auto.csv`, snapshot/checkpoint và coverage/unassigned/reconciliation summary. Unknown hoặc module chưa đo không hiển thị như 0 đã xác minh.

**Đầu ra P3:** `events.py`, `boxscore.py` hoặc module tương đương có integration thật với points, tests invariants/replay/revisions và report Task11. Phân biệt core implementation với full PRA acceptance còn phụ thuộc engines.

## Ưu tiên 4 — Task09/10 và dữ liệu Task04–06 còn thiếu

### Rebounds — Task09

- Mở cửa sổ từ eligible missed shot/FT context; made shot không tạo rebound. Không mở cho mọi missed FT khi chưa biết series applicability.
- Dùng multi-frame control recovery/controlled tip evidence. Không mặc định người gần bóng/rổ hoặc người chạm đầu tiên là rebounder.
- Offensive/defensive/team rebound theo ruleset có applicability/version; ambiguous/dead-ball/out-of-bounds context giữ unresolved. Timeout không tự là rebound.
- Đóng event một lần, liên kết shot/control, reset possession/pass chain đúng. Nếu upstream control/identity chưa tin cậy thì output candidate/unknown, không gọi personal stats đã đạt.

### Assists — Task10

- Dùng pass/control/possession history đã có evidence, liên kết passer/receiver/scorer/shot/score.
- Không coi mọi last pass hoặc pass trong N giây là assist. Time window là giới hạn kỹ thuật/matching, không thay luật; dùng rule profile và action context sau nhận bóng.
- Miss→rebound→score, turnover, deflection, cuts và possession reset phải vô hiệu chain không còn phù hợp. FT-related cases chỉ xử lý khi profile đã chốt.
- Assist xác nhận sau eligible score; score void/revision cập nhật dependency. Không tự dựng pass từ GT hoặc review notes khi pass recall upstream thấp.

### Data/court/identity nền

- Tận dụng roster/protocol/labels đã có, chỉ yêu cầu phần thực sự thiếu. Chuẩn bị packet review có nguồn cho actor/control/pass, eligible rebound, assist/no-assist và FT/rule-context cases.
- Xác minh court calibration/arc geometry trên source/camera hợp lệ, visible-foot location và team/identity accuracy; không coi synthetic geometry hoặc màu đúng trên vài snapshot là acceptance toàn trận.
- Split/exposure và các quyết định rule còn draft phải tiếp tục minh bạch; không tự đổi thành approved để mở gate.

**Đầu ra P4:** rebound/assist modules, automatic candidate/event traces, integration ledger, rule case matrix, tests và available real-data metrics. Hoàn tất tooling ngay cả khi chất lượng upstream còn chặn nghiệm thu; báo rõ accepted hay chưa.

## Ưu tiên 5 — Task12: dashboard local tích hợp

Khi ledger contract ổn định, có thể làm phần UI độc lập trong lúc training hoặc review dữ liệu còn diễn ra. Chọn stack nhẹ phù hợp project, ưu tiên tái sử dụng dependencies; không dựng backend/cloud nặng chỉ để demo.

- Một luồng sử dụng rõ: chọn MP4/config phiên → chạy phân tích → xem video overlay, timeline evidence, court/heatmap và team/player box score → export.
- Đồng bộ source PTS giữa video/trajectories/heatmap/events. Phân biệt video time, processing progress và event confirmation delay.
- Pause/seek/reload không làm tăng heatmap mass hoặc cộng lại stats. Có progress/cancel và completed/partial/failed đúng thực tế.
- Hiển thị nguồn run/model/config, attribution level và trạng thái chưa xác định. Khi PRA chưa đủ coverage, hiển thị pending/unknown; không dùng placeholder/mock totals để giả demo hoàn chỉnh.
- Click event mở evidence/timestamps; optional correction/undo có provenance riêng và không thay raw automatic metrics.
- Export video overlay, heatmap PNG, trajectories, events/boxscore, metadata và manifest. Không có key/signed URL hoặc tự upload video.

Kiểm tra UI bằng browser automation phù hợp, gồm happy path, seek/reload, incomplete run, event evidence và download exports. Lưu ảnh/demo capture thực tế; mockup không thay bằng chứng ứng dụng chạy được.

## Ưu tiên 6 — Task13–15: end-to-end, hiệu năng và đóng gói

### Đánh giá chất lượng

- Chọn clip demo continuous phù hợp và đủ context, khai báo selection/exposure; không nhận timestamp/actor/outcome GT làm runtime hints. Demo selection và frozen evaluation set là hai mục đích khác nhau.
- Freeze approved protocol/split/config/model trước evaluation. Báo event-only và strict points/rebounds/assists, TP/FP/FN/P/R/F1, actor/value/subtype/link errors, unknown/coverage và false scores trên no-event footage.
- Chạy raw auto trước correction; precision N/A khi không có predicted positives, không gán 100%. Không lấy tổng điểm trùng để chứng minh từng event đúng.
- Mục tiêu strict từng stat P>=95%, R>=90% theo protocol hiện hành. Không tự hạ để pass; sample size nhỏ, missing GT hoặc same-match exposure phải được công bố.
- Negative false-score control phải đi kèm positive recall; abstain mọi pha không phải nghiệm thu tốt. Không dùng cỡ mẫu 30 để hứa gần 100% mọi trận.

### Benchmark và tối ưu

- Đo decode→detect→track/OCR→events→render/export, throughput, latency p50/p95, event delay, memory và dropped/processed frames trên máy thực.
- Tách cached FSM replay timings với end-to-end inference; thời gian 0,x giây trên cached tracks không là tốc độ ứng dụng xử lý video.
- Chỉ tối ưu bottleneck có evidence. Resize/tile/sampling/batching/backend profile mới cần quality regression; không skip critical frames để làm FPS đẹp.
- Dùng quyền GPU/runtime đã có đúng phạm vi, không sửa global driver/backend hoặc đổi model family âm thầm. Kết luận offline rõ nếu chưa có benchmark live hợp lệ.

### Bản demo có thể tái chạy

- Tạo một entrypoint/lệnh demo rõ ràng, cấu hình mẫu và cơ chế source/run/output paths mới. Có thể bọc CLI + dashboard bằng launcher phù hợp; xác minh cú pháp thực, không chỉ ghi README tưởng tượng.
- Chạy một clean/reproducible run thực tế, kiểm tra artifacts mở được và links/metadata đúng. Không reset/delete môi trường của người dùng để giả clean install.
- Bàn giao README/setup/dependency lock, `docs/user-guide-v2.md`, demo captures/video, output bundle và `docs/reports/final-report-v2.md`/acceptance matrix.
- Phân biệt demo kỹ thuật chạy được với MVP chất lượng đạt nghiệm thu. Nếu một stat chưa đạt hoặc thiếu GT, ghi demo partial và blocker, không đổi scope thành chỉ points hoặc nhập tay mà vẫn đánh dấu cả MVP DONE.

## 7. Tests, checkpoints và cách tiếp tục tự động

Tests ưu tiên theo rủi ro:

- Data clipping/quarantine không tạo negative giả; source/class/split/hash/exposure guards và resume stage idempotency.
- Evaluator phải phản ứng với injected FP/FN/wrong actor/value/link, empty sets, uncertain intervals, tolerance boundaries; không nhận hard-coded metrics.
- Shot history causal, crossing observed, value unknown, camera/replay guards và no double score.
- Ledger duplicate/revision/void/actor refinement, rebound/team totals và assist dependency cascade.
- Rebound eligibility/control, pass→miss→rebound→score không kế thừa assist, unknown actors/FT context và cuts.
- UI synchronized playback, repeated seek/reload, exports và failed/partial run.

Chạy tests phù hợp từng thay đổi và required regression; không mở rộng/lặp lại khi không có lý do mới. Synthetic dùng kiểm logic, không gắn nhãn real-data accuracy.

Sau mỗi ưu tiên, lưu checkpoint report ngắn và **tự tiếp tục ưu tiên tiếp theo có thể làm**. Nếu thiếu input thật, liệt kê chính xác source/label/rule/geometry nào, các phần đã hoàn thành và phần nào vẫn làm độc lập. Chỉ hỏi phần cần quyết định ngoài authorization hoặc không thể tìm trong connected/local context; không hỏi lại roster/review đã cung cấp.

Job dài phải có trạng thái/heartbeat/PID/logs kiểm chứng được, stage resumable và output mới. Không kết thúc với lời “đang chạy” nếu process đã chết; không đánh dấu ready/completed chỉ vì đã tạo script. Khi còn tiến trình thật chạy nền, báo stage/artifact hiện hành và điều kiện tự chuyển tiếp, không tuyên bố kết quả tương lai đã đạt.

## 8. Bàn giao cuối

Tạo `docs/reports/demo-completion-priority-execution.md` kèm task statuses, commands và links artifacts. Mỗi task có bốn cột implemented/executed/measured/accepted, evidence và blocker nếu có. Cập nhật PLAN/task files nhất quán, giữ lịch sử report không đủ bằng chứng dưới nhãn phù hợp.

Phản hồi cuối phải nêu:

1. Code/data dẫn xuất đã thay đổi và vì sao.
2. Dataset/GPU/fine-tune/candidate inference đang ở trạng thái thực tế nào.
3. Kết quả evaluation đã sửa và metrics nào còn unavailable/unverified.
4. Cách chạy demo, vị trí UI/output bundle và phạm vi tự động thực sự.
5. Tests/benchmark và từng quality gate đạt/chưa đạt.
6. Nếu chưa có full MVP accepted, đúng đầu vào hoặc lỗi còn chặn; không dùng wording khiến người đọc hiểu đã nghiệm thu.

**Bắt đầu kiểm kê và thực thi từ Ưu tiên 1, tiếp tục xuyên suốt các phần còn lại đã được giao.**
