# Kiểm thử và nghiệm thu demo Automatic Stats — 2026-11-10

**Verdict: REQUEST CHANGES — CHƯA NGHIỆM THU DEMO/MVP. Confidence: HIGH.**

Đối tượng: các phần đã thực thi theo [prompt ưu tiên](../prompts/demo-completion-priority-execution.md), mã nguồn và artifacts hiện có ngày 2026-11-10, Asia/Bangkok. Báo cáo này thay kết luận nghiệm thu trong [báo cáo bàn giao 2026-11-09](demo-completion-priority-execution.md); giữ nguyên nội dung cũ để audit.

Có các thành phần chạy được và data QA đạt kiểm tra kỹ thuật, nhưng đường demo hiện tại chỉ replay cache chọn sẵn, còn lỗi làm phát sinh stats sai và chưa có bằng chứng chất lượng PRA đạt P≥95%, R≥90%. Không thể giữ trạng thái ACCEPTED cho ledger/box score, dashboard, benchmark, packaging hoặc toàn bộ P1 như báo cáo cũ.

## 1. Phạm vi, phương pháp và kết quả kiểm thử

Đã đối chiếu DEVELOPMENT, PLAN, MVP v2, task04–15, contracts/rules/evaluation protocol và các report/handoff liên quan; đọc source, tests, logs và raw artifacts. Workspace hiện không có `.git`, vì vậy dùng [snapshot SHA-256](../../codebase/outputs/acceptance-demo-20261110/source-snapshot.json) thay commit/diff. Không sửa mã ứng dụng, model, dataset gốc, nhãn review, split hoặc approval để làm pass. Chỉ thêm bộ kiểm tra/artifacts và cập nhật tài liệu nghiệm thu.

| Kiểm tra đã chạy | Kết quả | Bằng chứng |
|---|---|---|
| Toàn bộ tests hiện có | **367 passed; 61 subtests passed; 6 warnings; 72,14 s** | [log](../../codebase/outputs/acceptance-demo-20261110/pytest.log), [JUnit](../../codebase/outputs/acceptance-demo-20261110/pytest.xml) |
| Bộ kiểm tra độc lập theo yêu cầu | **39 failed, 1 passed; không có setup errors ở lần cuối** | [40 ca kiểm tra](../../codebase/outputs/acceptance-demo-20261110/test_acceptance_requirements.py), [log](../../codebase/outputs/acceptance-demo-20261110/requirements.log), [JUnit](../../codebase/outputs/acceptance-demo-20261110/requirements.xml) |
| Browser thực tế: Playwright + Chrome có sẵn | **10 pass, 8 fail / 18 checks** | [JSON](../../codebase/outputs/acceptance-demo-20261110/browser-results.json), [desktop](../../codebase/outputs/acceptance-demo-20261110/dashboard-desktop.png), [mobile](../../codebase/outputs/acceptance-demo-20261110/dashboard-mobile.png), [missing video](../../codebase/outputs/acceptance-demo-20261110/dashboard-missing-video.png) |
| ZIP/original/derived/mixed dataset | Đạt integrity và kiểm tra nhãn hình học, giới hạn tại mục 3 | [audit](../../codebase/outputs/acceptance-demo-20261110/dataset-audit.json) |
| CLI với video không tồn tại | **FAIL: exit 0, vẫn xuất 1 event** khi stdout UTF-8 | [log](../../codebase/outputs/acceptance-demo-20261110/missing-video.log), [summary](../../codebase/outputs/acceptance-demo-20261110/missing-video-utf8/summary.json) |
| CLI với video thật | Chạy được cache; 1 event unresolved, tỷ số 0–0; không phải video inference | [summary](../../codebase/outputs/acceptance-demo-20261110/actual-video/summary.json), [events](../../codebase/outputs/acceptance-demo-20261110/actual-video/events_auto.jsonl) |
| Candidate C replay cache, không truyền cờ theo nhãn/ID pha | 10 positive windows, 30 draft negative segments đã thực thi | [diagnostic](../../codebase/outputs/acceptance-demo-20261110/replay-diagnostic.json), [predictions](../../codebase/outputs/acceptance-demo-20261110/replayed-shots.jsonl) |
| GPU training loss probe được bàn giao | **FAIL: AttributeError, thiếu hyperparameter `box`** | [log](../../codebase/outputs/acceptance-demo-20261110/gpu-smoke.log) |
| Benchmark được bàn giao, chuyển output sang thư mục mới | Chạy được; báo 16,00 FPS, nhưng phép đo không đủ điều kiện E2E | [log](../../codebase/outputs/acceptance-demo-20261110/delivered-benchmark.log), [JSON](../../codebase/outputs/acceptance-demo-20261110/delivered-benchmark-results.json) |

Các test độc lập là synthetic để kiểm chứng logic, không phải số đo accuracy trên footage. 39 ca fail có nhiều biến thể chung một nguyên nhân, không phải 39 lỗi độc lập. Các lượt đầu có lỗi fixture `RosterPlayer.name` đã được sửa trong bộ kiểm tra; log lỗi fixture giữ riêng, không dùng làm bằng chứng lỗi sản phẩm. Lần browser cuối đã đợi seek hoàn tất và xác nhận playback thực sự tiến thời gian trước chụp ảnh.

## 2. Ma trận implemented / executed / measured / accepted

“Một phần” không có nghĩa là task hoàn thành. “Executed: tests” không phải đã chạy engine trên video thật. Không thay các tiêu chí nghiệm thu đã giao.

| Phần việc | Implemented | Executed | Measured | Accepted | Blocker hiện hành |
|---|---|---|---|---|---|
| P1: QA hình học và binding dataset | Có | Audit toàn bộ | 9.515 ảnh, 36.988 bbox; 24 box sửa | **Đạt phạm vi kiểm tra kỹ thuật này** | Không chứng nhận semantic completeness/near-duplicates toàn bộ dataset |
| P1 / Task07: CUDA readiness, fine-tune, candidate | Một phần | CUDA inference chạy; loss probe fail; không có train process | Có số đo inference; chưa có epoch/candidate evaluation | **Không** | Loss smoke không đạt, candidate stale, chưa có weights/results/paired comparison |
| Task04: data/rules/protocol/split | Tooling + một phần dữ liệu | Có artifact và review hiện có | Một phần | **Không** | Negative review, control/pass/REB/AST GT và các gate rules/geometry chưa đủ |
| Task05: court/heatmap | Core có sẵn | Tests/diagnostics có sẵn | Chưa có bằng chứng real geometry đạt gate trong đợt bàn giao này | **Không** | UI không dùng actual court coordinates; thiếu validation geometry phù hợp |
| Task06–07: identity/control/pass | Có implementation | Có raw cache và evaluation trước đó | Quality gate cũ thất bại; chưa có candidate mới | **Không** | Ball/control/pass/identity chưa đạt; không có cơ sở gọi upstream đã sửa xong |
| P2 / Task08: shot FSM, points/value/FT | Một phần | Real-observation cache replay | Diagnostic, chưa phải formal accuracy | **Không** | Crossing dùng predicted/gap dài; evaluator sai; value geometry/FT context thiếu |
| P4 / Task09: rebounds/OREB/DREB/team | Một phần | Unit tests + probes | Chưa có real-data P/R/F1 | **Không** | Không kiểm FT applicability/eligible miss/observed sustained control; chưa nối demo |
| P4 / Task10: assists | Một phần | Unit tests + probes | Chưa có real-data P/R/F1 | **Không** | Thiếu pass/action/cut guards; chưa nối demo; chưa có GT đủ dùng |
| P3 / Task11: ledger/box score | Một phần | Raw points ingestion và tests | Đã tái hiện invariant/lifecycle failures | **Không** | Status filtering, refinement duplicate, dependency revision, immutable log/checkpoint |
| P5 / Task12: dashboard | Một phần | Browser với video thật + missing input | 18 checks; 8 fail | **Không** | Heatmap minh họa, unknown hiển thị 0, thiếu evidence/provenance/progress/cancel/failed |
| P6 / Task13: evaluation E2E | Một phần diagnostics | Cached replay | Formal strict PTS/REB/AST **N/A** | **Không** | Production evaluator chưa đúng matching; thiếu GT/coverage/frozen full evaluation |
| P6 / Task14: benchmark | Một phần | 100 frames video thật + CUDA | Số đo microbenchmark; E2E chưa hợp lệ | **Không** | Class mapping sai, tracker input rỗng, FSM input sai, thiếu OCR/render/export/delay/p50/p95 |
| P6 / Task15: packaging | Runner cache có sẵn | CLI/UI cache chạy | 5/10 cửa sổ reviewed được chọn đúng; 1 unresolved event | **Không** | Không có continuous video pipeline; thiếu output bundle và tài liệu bắt buộc |

Task04–15 tiếp tục IN_PROGRESS theo phạm vi trên. Không nâng các task trước đây chưa đạt chỉ dựa trên audit lại lần này.

## 3. Dataset, GPU và trạng thái fine-tune thực tế

Dataset ZIP SHA-256: `009e9bb3ac5744a32fb4d398a7ce3ce709561276fa8af753dad4e82c3b981ea4`. CRC đạt; đối chiếu SHA-256 từng member với export không có mismatch. Ảnh original và derived giống nội dung; không thiếu label, không mất bbox hoặc biến ảnh thành negative giả trong bản dẫn xuất đã kiểm tra.

| Split gốc / derived | Ảnh | Bbox | Ball | Human | Rim |
|---|---:|---:|---:|---:|---:|
| Train | 6.662 | 25.882 | 6.708 | 14.448 | 4.726 |
| Valid | 1.893 | 7.490 | 1.918 | 4.227 | 1.345 |
| Test | 960 | 3.616 | 971 | 1.972 | 673 |
| Tổng | **9.515** | **36.988** | **9.597** | **20.647** | **6.744** |

19 label files thay đổi tương ứng 24 bbox vượt biên; mức vượt lớn nhất 0,5 pixel, normalized 0,0027322404. Tất cả nhãn derived đạt kiểm tra class, finite, positive area và bounds tolerance 1e-6. Mixed manifest binding/hash/split membership đạt hàm `verify_dataset`: train/valid/test = **6.711 / 515 / 219**, giữ **49 supplemental rows**, quarantine **2.119 holdout images**. Manifest vẫn `staged_for_QA_not_promoted`; giới hạn semantic completeness và near-duplicate audit giữ nguyên. Đây là acceptance kỹ thuật của dữ liệu dẫn xuất hiện có, không phải nghiệm thu chất lượng detector hay recipe trên mọi dữ liệu lỗi.

RTX 2050 và CUDA inference hoạt động trong benchmark. Tuy nhiên:

- `gpu_training_smoke_test.py:108` lấy trung bình output boxes/scores làm loss; `batch_dict` có labels được tạo nhưng không dùng vào loss. Artifact `gpu_training_smoke_passed` chứng minh backward trên một scalar thay thế, chưa chứng minh detection training loss đúng.
- Chạy script thực sự gọi loss `probe_task07a_gpu_training.py` thất bại tại `self.hyp.box` với runtime hiện tại. Không thay package/config cài đặt để che lỗi.
- Job cũ `job/status.json` còn `preparation_failed`. Candidate mới `task07a-candidate-20261109/run.json` ghi `training`, nhưng tại **16:34:24 ngày 10/11/2026 (Asia/Bangkok)** không có Python training process phù hợp, không có `results.csv`, không có best/last weights; stdout/stderr logs đều 0 byte. Có ba train batch preview, nên không suy “chưa hề bắt đầu”, nhưng **không chứng minh đã hoàn thành epoch**. [Process/artifact snapshot](../../codebase/outputs/acceptance-demo-20261110/training-process-snapshot.json).
- [So sánh snapshot candidate](../../codebase/outputs/acceptance-demo-20261110/training-runtime-drift.json) cho thấy `points.py` hiện khác hash đã freeze trong run. Không sửa expected hashes hoặc snapshot cũ. Cần experiment/run-code version riêng khi khôi phục.

Không có candidate checkpoint hoàn tất để chạy paired downstream evaluation hoặc promote; approved baseline được giữ nguyên. Đợt này không khởi động training job mới.

## 4. Những lỗi bắt buộc xử lý trước nghiệm thu

### [P1-A] Runner không phân tích video được chọn và có thể báo thành công giả

**Vị trí:** `codebase/scripts/run_demo.py:61`, `:84`, `:91`, `:113`.

`--video` chỉ được hash và dùng cho player; không có decode/detect/track trên video này. REB/AST engines chỉ khởi tạo, không được gọi. Runner chọn play_001…010, nhưng cache reviewed thực có 001/003/004/006/008/015/021/023/027/028: chỉ xử lý **5/10** cửa sổ đúng và bỏ mất play_021, nơi report cũ có basket thứ hai. Video nonexistent vẫn in “Verified Source”, exit 0 và xuất 1 event. Có cờ FT/camera-invalid suy trực tiếp từ window ID, không phải evidence runtime.

**Sửa cần thiết:** tạo entrypoint decode→inference→tracking→engines→ledger trên video/config thực; tách cache replay thành chế độ diagnostic với source/model/config bindings; validate input/cache trước chạy, báo failed/partial và coverage rõ. REB/AST phải nhận stream thật; không dùng tên pha để cung cấp FT/camera hints.

### [P1-B] Shot made có thể dựa vào entry/exit predicted hoặc gián đoạn quá dài

**Vị trí:** `codebase/src/basketball_scoreboard/shots.py:403`, `:478`.

Guard mất quan sát chỉ chạy khi không có center; predicted center đi qua nhánh này. `_check_rim_aperture_crossing` chỉ cần một observed sample gần rổ ở bất kỳ phần nào của trajectory, rồi xét top/bottom trên cả predicted samples. Hai probe qua public `step()` đều tạo `made`: observed không đi qua vành + predicted entry/exit; hoặc observed crossing có gap 0,8 s dù config max gap 0,35 s. Còn `net_cue_passed` luôn True; bật/tắt cue chưa tạo một phép ablation có ý nghĩa về điều kiện xác nhận.

**Sửa cần thiết:** yêu cầu observed crossing và temporal continuity của chính các mẫu crossing; kiểm max gap cả khi đang có predicted center; reset/abstain khi vượt điều kiện. Tính cue/reason từ feature thật và giữ aperture bbox-ratio là hypothesis chưa được calibration xác nhận.

### [P1-C] Evaluator production không phải evaluator được kiểm thử

**Vị trí:** `codebase/scripts/run_task08_temporal_shot_engine.py:158`, `:170`, `:390`; `codebase/tests/test_task08_evaluator.py:45`.

Production đánh dấu `basket_confirmed` khi có bất kỳ made nào trong window; không áp tolerance, không one-to-one matching và không tính duplicate FP. Một made tại 1–2 s vẫn được công nhận cho GT 10–11 s trong probe. Test evaluator định nghĩa class riêng ngay trong file test, không gọi production function nên các fixture FP/empty sets không chứng minh runner đúng. Team matches còn cộng cả window miss, khiến chúng không phải strict score TP.

**Sửa cần thiết:** một evaluator production dùng chung với test; maximum-cardinality one-to-one matching theo protocol frozen, có wrong actor/value/link, duplicates, uncertain/empty/background và N/A. Ghi predictions trước evaluation; không gọi tỷ lệ “có made trong window” là recall chính thức.

### [P1-D] Negative specificity 100% chưa có nhãn/provenance hợp lệ

**Vị trí:** `codebase/scripts/mine_negative_cohort.py`, `run_task08_temporal_shot_engine.py:276`, `:527`.

Đã có 30 cache thật, **4.050 frames**, và runner mới thực sự gọi FSM thay cho nhánh FP cố định cũ. Tuy nhiên manifest vẫn `draft_unreviewed`; metadata cache không bind đầy đủ source/model/preprocessing/frame hashes và không có negative review packet đủ evidence/sign-off. [Contact sheet nguồn](../../codebase/outputs/acceptance-demo-20261110/negative-source-contact-sheet.jpg) của neg_miss_001…004 cho thấy phần giới thiệu cầu thủ/chuẩn bị thi đấu tại các frame lấy mẫu, không hỗ trợ mô tả airball/fadeaway/corner miss ghi trong manifest. Các frame này không thay thế việc review toàn segment; không tự đổi nhãn hoặc ký duyệt chúng.

**Sửa cần thiết:** chuẩn bị clip/evidence và provenance cho các tình huống thực, review độc lập đầy đủ, bảo đảm nhóm replay/original, đủ category/unique segments trước khi freeze evaluation. Hiện chỉ báo “0 made predictions trên 30 draft cache segments”; **official specificity = N/A**.

### [P1-E] Box score cộng cả candidate/provisional/unresolved/VOID

**Vị trí:** `codebase/src/basketball_scoreboard/boxscore.py:116`.

`compile()` lấy mọi event `is_void=False`, không lọc `status`. 16 probes theo 4 loại event × 4 trạng thái không-confirmed đều tăng PTS/REB/AST/TO. Trường hợp `status=VOID` nhưng flag chưa đổi cũng bị cộng. Bảo toàn tổng số không phát hiện được việc tổng số được tạo từ event chưa đủ điều kiện.

**Sửa cần thiết:** chỉ aggregate `AUTO_CONFIRMED` và hợp lệ; báo các trạng thái còn lại qua coverage/unresolved riêng; đồng bộ lifecycle status/void flag. Kiểm soát status tại cả ingestion và compile.

### [P1-F] Ledger refinement, reordering và audit chưa bảo đảm invariants

**Vị trí:** `codebase/src/basketball_scoreboard/events.py:144`, `:175`, `:207`.

Sau unknown→known, fingerprint index không cập nhật: thông báo cùng score với actor mới và event ID mới được thêm tiếp, tổng điểm 2→4. Sửa team hoặc chuyển score sang unresolved không invalidate assist; assist đến sau khi parent đã void vẫn được cộng. Ledger giữ trực tiếp reference của object người gọi; sửa `original.point_value` bên ngoài làm đổi tổng mà không có audit mutation. `export_jsonl` chỉ xuất active state, không phải raw append-only log/checkpoint có thể tái lập correction history.

**Sửa cần thiết:** định danh theo source/physical event ổn định, giữ refinement cùng entity và quản lý index đúng; copy/immutable records; propagate eligibility changes và kiểm parent kể cả arrival đảo thứ tự; tách raw log/correction, triển khai checkpoint/resume và kiểm replay sau reload.

### [P1-G] Rebound còn thiếu điều kiện eligible miss, FT và control thật

**Vị trí:** `codebase/src/basketball_scoreboard/rebounds.py:85`, `:98`, `:137`.

Module chỉ chặn outcome `made`; `unknown`, `unresolved`, `not_a_shot` vẫn tạo rebound auto-confirmed. Bỏ qua `sample_type=predicted`; hai observations cách nhau 3,3 s cũng được xem là sustained control do điều kiện duration OR frames. `is_last_free_throw` không dùng và API không có shot-kind/FT-context để phân biệt field goal với FT không eligible. Team/unknown output chưa có rule matrix/real-data acceptance.

**Sửa cần thiết:** kiểm approved rule context/shot eligibility và final-FT applicability; chỉ xác nhận từ observed control sequence liên tục, có confidence/cut/dead-ball guards; ambiguous giữ unresolved. Nối module với shot/control stream thật và đo trên GT.

### [P1-H] Assist tự xác nhận khi pass/action evidence chưa đủ

**Vị trí:** `codebase/src/basketball_scoreboard/assists.py:61`, `:118`, `:136`, `:167`.

Unknown receiver vẫn được chấp nhận; candidate pass confidence 0,1 vẫn tạo auto-confirmed assist. `require_direct_shot`/`allow_dribbles` không được dùng; probe 12 dribbles + independent drive vẫn có assist. Deflection, loose_ball và camera_cut không break chain. Hiện module vẫn gần với “last pass trong 4 s” hơn yêu cầu action/rule evidence.

**Sửa cần thiết:** yêu cầu pass/control confirmed, receiver/scorer/possession links đúng và approved action rule profile; invalidate mọi chain break/cut cần thiết, xử lý FT theo applicability; chỉ chốt sau eligible score và nối dependency lifecycle vào ledger.

### [P1-I] Dashboard hiển thị geometry và chất lượng stats vượt bằng chứng

**Vị trí:** `codebase/src/basketball_scoreboard/dashboard.py:230`, `:485`, `:567`.

Marker sân dùng fallback distance 5,5 và `frame_index % 7` để tản vị trí; đó không phải court projection hoặc time-weighted heatmap. Event của run thật không có court coordinates nhưng vẫn xuất hiện trên “FIBA 3x3 Court Shot Heatmap”. REB/AST chưa chạy vẫn hiện 0 trong bảng “Official”. Missing video vẫn `status=ready`; thiếu chọn input/start/progress/cancel, run/model/config provenance và evidence panel. Click event hiện chỉ seek video. Không có overlay/trajectories/heatmap PNG/manifest exports theo yêu cầu.

**Sửa cần thiết:** chỉ vẽ actual validated geometry và heatmap có PTS/coverage; giữ unavailable/pending thay 0; dùng run lifecycle thật; hiện attribution/evidence/provenance, hoàn thiện workflow và exports bắt buộc. Không dùng marker minh họa để nghiệm thu heatmap.

### [P1-J] Benchmark hiện tại không đo pipeline E2E đúng

**Vị trí:** `codebase/scripts/benchmark_task14_performance.py:93`, `:99`, `:123`.

Checkpoint mapping đã xác minh là **0 ball / 1 human / 2 rim**, nhưng benchmark dùng **0 player / 1 rim / 2 ball**. Tracker còn nhận `class_name="player"`, trong khi `PlayerTracker` chỉ nhận `human`: phần tracking thực tế bị lọc rỗng. FSM ball sample không có `sample_type="observed"`; không đo đường shot thực. Không chạy team/OCR/control/REB/AST/render/export, không có p50/p95/event delay/RAM/dropped frames. GPU “peak VRAM” chỉ là PyTorch allocated, không phải toàn bộ bộ nhớ tiến trình hay bằng chứng đủ cho multi-stream.

**Sửa cần thiết:** dùng cùng adapter/class map/config/source PTS với application, kiểm tra non-empty expected inputs và execution coverage; benchmark continuous full pipeline có số frame thực, timers/latency distribution và memory phù hợp; regression chất lượng trước kết luận readiness.

### [P1-K] Training readiness và trạng thái job chưa thể nghiệm thu

**Vị trí:** `codebase/scripts/gpu_training_smoke_test.py:108`, `codebase/outputs/task07a-candidate-20261109/run.json`.

Loss surrogate, actual loss probe thất bại, candidate không còn process/epoch artifacts và snapshot source khác run freeze, như mục 3. Không được coi chỉ artifact “smoke_passed” hoặc `status=training` là readiness/training success.

**Sửa cần thiết:** khôi phục actual detection criterion/hyperparameters theo recipe versioned, chứng minh finite real loss/gradients/optimizer update với batch labels; kiểm process identity/heartbeat/epoch artifacts; resume một experiment có source snapshot phù hợp, không sửa hash cũ. Chỉ promote sau paired inference/downstream evaluation.

### Các điểm P2

| Vấn đề | Vị trí / bằng chứng | Sửa đề nghị |
|---|---|---|
| Range ngoài file trả 206; range ngược gây ValueError; GET không Range chỉ ghi 64 MiB dù Content-Length là toàn file | `dashboard.py:638`, `:647`; 2 probes fail | Validate/clamp byte ranges theo file size, trả 416 đúng; stream đủ body theo header |
| Mobile có document overflow 687 px trên viewport 390 px | browser-results + mobile screenshot | Responsive layout và scroll bảng cục bộ |
| CLI bị UnicodeEncodeError khi stdout pipe dùng cp1252 với roster tiếng Việt | missing-video-default-encoding.log | Entry point/launcher cấu hình stdout UTF-8 phù hợp; ghi môi trường trong hướng dẫn |
| Thiếu deliverables Task13–15 bắt buộc | [missing-deliverables.json](../../codebase/outputs/acceptance-demo-20261110/missing-deliverables.json) | Bổ sung evaluator, user guide, final/evaluation/performance reports và output bundle sau sửa pipeline |

## 5. Metrics được phép công bố sau tái kiểm tra

Đã replay Candidate C trên toàn bộ 10 positive cache windows và 30 draft negative cache segments, bỏ các cờ camera-invalid/FT dựa vào window ID, không đưa GT vào runtime.

- Có **2 made predictions / 10 positive windows**. Đây là số window có detection, không tự trở thành recall đúng protocol.
- Diagnostic matching yêu cầu release và basket đều trong ±0,5 s: **TP=1, FP=1, FN=9; P=50%, R=10%, F1=16,67%** trên 10 selected positive windows. Made play_021 lệch release 1,1 s nên không match trong phép kiểm này. Đây là tolerance chẩn đoán của audit, không phải phê duyệt protocol mới hoặc kết quả trên holdout.
- Trong 1 matched event: đúng team **0/1**, strict player **0/1**, point value được resolve **0/1**. Không có cơ sở gọi team attribution 100%.
- Negative caches có **0 made predictions / 30 segments**, nhưng labels chưa được review và category evidence không đủ; official specificity **N/A**, không phải 100% accepted.
- **Formal strict points/rebounds/assists TP/FP/FN/P/R/F1: N/A** cho full-demo acceptance do thiếu full GT/coverage/protocol và engine integration. Proposed scoreboard point values chưa là geometry GT độc lập. Không thay N/A bằng 0 hoặc 100%.
- Benchmark tái chạy báo **16,00 FPS**, detection 46,90 ms/frame, decode 13,86 ms/frame, PyTorch peak allocated 110,41 MiB. Vì đường dữ liệu mapping/coverage sai như P1-J, **không dùng làm application E2E FPS hoặc live-readiness**. Cache replay khoảng 1,5 s cũng không phải video-processing throughput.

Không có stat nào đủ bằng chứng đạt gate strict P≥95%, R≥90%. Không hạ gate, tự ký labels hoặc đổi scope thành points-only.

## 6. Lệnh tái lập và artifacts

Chạy từ workspace root trên PowerShell. Python inference và training là hai venv riêng; không cài lại dependencies để chạy audit này.

```powershell
$env:PYTHONPATH='codebase/src;codebase/scripts'
$env:PYTHONIOENCODING='utf-8'

# Bộ hiện có: kỳ vọng pass trên snapshot đã kiểm.
codebase/.venv/Scripts/python.exe -m pytest codebase/tests -q

# Contract probes: trên source hiện tại kỳ vọng 39 fail / 1 pass, exit code 1.
codebase/.venv/Scripts/python.exe -m pytest codebase/outputs/acceptance-demo-20261110/test_acceptance_requirements.py -q

# Audit read-only dữ liệu và replay diagnostic; ghi lại artifacts trong thư mục audit.
codebase/.venv/Scripts/python.exe codebase/outputs/acceptance-demo-20261110/audit_inventory.py
codebase/.venv/Scripts/python.exe codebase/outputs/acceptance-demo-20261110/replay_diagnostic.py

# Benchmark được bàn giao, chỉ đổi đường ghi output để bảo toàn artifact cũ.
codebase/.venv-train/Scripts/python.exe codebase/outputs/acceptance-demo-20261110/run_delivered_benchmark.py

# Thử CLI/UI hiện có: đây là cache demo, chưa phải full pipeline.
# Dùng output directory mới để không ghi đè bằng chứng.
codebase/.venv/Scripts/python.exe run_demo.py --video codebase/assets_test/vietnam-tonga.mp4 --output codebase/outputs/demo-audit-manual-new --serve --port 8765
```

Browser automation dùng skill `playwright`, script tại `%TEMP%/playwright-test-demo-acceptance.js`, Chromium API với Chrome có sẵn (`channel='chrome'`, `headless:false`); không tải browser mới. Các server audit đã được dừng sau khi lưu bằng chứng. Browser checks gồm playback sau seek, event seek, repeated seek/reload không đổi box score, CSV/JSONL downloads, provenance/evidence/unknowns, mobile và missing source.

Thư mục bằng chứng: [codebase/outputs/acceptance-demo-20261110](../../codebase/outputs/acceptance-demo-20261110). [Commands và exit codes](../../codebase/outputs/acceptance-demo-20261110/commands.json) và manifest SHA-256 phục vụ đối chiếu. Các file nhãn/GT/weights cũ được giữ nguyên; không có upload, cloud job hoặc thay model family.

## 7. Điều kiện tái nghiệm thu

1. Sửa P1-E/F và dùng các probes làm regression cho status/idempotency/dependency/audit.
2. Sửa shot observed continuity và production evaluator; review negative footage thực với provenance, không dùng nhãn vào recognition.
3. Khôi phục readiness/fine-tune theo snapshot versioned; đo paired quality/latency trước chọn candidate.
4. Hoàn thiện rule/control/action guards của REB/AST và nối toàn bộ engines vào continuous MP4 pipeline. Thu thập/duyệt đúng phần GT/rules/geometry còn thiếu, không hỏi lại roster đã có.
5. Hoàn thiện UI/exports thật, đo full E2E, freeze protocol/data/model/config rồi chạy raw automatic evaluation trên coverage phù hợp. Chỉ chuyển DONE khi từng stat và deliverable đạt bằng chứng nghiệm thu.

**Quyết định cuối: chấp nhận kết quả audit integrity/hình học dataset và các smoke checks được nêu rõ; từ chối nghiệm thu toàn bộ demo/MVP ở snapshot này.**
