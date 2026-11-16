# Review trạng thái project — 2026-11-15

Phạm vi: workspace hiện tại, source/config/tests và artifacts local. Không có `.git` ở root hoặc `codebase`; không đánh giá được lịch sử commit/diff. Đây là review hiện trạng và backlog, chưa sửa ứng dụng hoặc khởi động training. Không chạy lại holdout inference, full detector evaluation hoặc browser acceptance trong đợt này.

**Kết luận: REQUEST CHANGES — MVP Automatic Points/Rebounds/Assists + Heatmap chưa đủ điều kiện nghiệm thu.** Đã có nhiều module và bằng chứng core correctness, nhưng entrypoint demo đang lỗi, chưa có continuous video pipeline và chất lượng nhận diện/GT chưa đạt.

## 1. Kiểm chứng trực tiếp trong đợt review

| Kiểm tra | Kết quả |
|---|---|
| `codebase/.venv/Scripts/python.exe -m pytest tests -q` từ `codebase` | 405 passed, 1 skipped, 61 subtests passed; 6 warnings; 73,71s |
| `scripts/run_demo.py --output <thư mục tạm mới>` bằng `.venv` và UTF-8 | Exit 1: `TypeError: run_engine_on_window() got an unexpected keyword argument 'is_play_006'` |
| Nhóm independent acceptance probes cho rebound/assist/FT | 12 failed, 4 passed, 24 deselected; không có setup error |
| `scripts/validate_dataset_v2.py --require-data-ready` | Exit 1; structural/tooling hợp lệ; data-ready và locked-ready đều false |
| Artifacts candidate training | `results.csv` chỉ có epoch 1; heartbeat cũ ở epoch 2, ngày 13/11; PID 9884 hiện là `Code.exe`, không phải job Python cũ |

Lệnh probes, chạy từ `codebase` với `PYTHONPATH=src;scripts`:

```powershell
.venv/Scripts/python.exe -m pytest outputs/acceptance-demo-20261110/test_acceptance_requirements.py -q -k 'rebound or isolated_controls or assist_requires or assist_chain or assist_checks or ft_series' --tb=line
```

Các probes là kiểm tra logic synthetic, không phải accuracy trên video. Bộ test chính không bao gồm probes đặt dưới `outputs`, do đó kết quả 405 pass không thay thế nghiệm thu contracts.

## 2. Trạng thái theo thành phần

| Task | Hiện trạng có bằng chứng | Còn thiếu |
|---|---|---|
| 01–03 | Baseline runtime/model, pilot v1 và nền video/PTS/detection đã nghiệm thu theo PLAN | Không cần làm lại toàn bộ |
| 04 | Schema/validators có sẵn; có review packets ở namespace khác | Dataset PRA canonical chưa có approved labels; roster rỗng, test split rỗng, rules/protocol/split chưa khóa |
| 05–06 | Court/heatmap/tracking/team/OCR providers có code và tests | Geometry thật, identity/team/position accuracy và coverage chưa đủ bằng chứng nghiệm thu |
| 07 | Ball/control/pass implementation; CUDA detection loss và training đã được chứng minh; có hai checkpoints được paired detector evaluation | Không checkpoint nào được promote; chưa có paired downstream control/pass/identity evaluation trên candidate |
| 08 | Core continuity/rim crossing và shared production evaluator đã sửa, tests pass | Diagnostic recognition còn yếu; PRA quality và negative review chưa đạt |
| 09–10 | Rebound/assist module và unit tests có sẵn | 12 probes contracts còn fail; chưa nối stream thật trong demo |
| 11 | Ledger/boxscore core đã sửa với audit/checkpoint/replay và eligibility tests | Integration PRA trên continuous video và real-data acceptance |
| 12 | Dashboard/video/events/exports có code | Tọa độ sân thật, heatmap thật, evidence/coverage/status và tái nghiệm thu browser |
| 13–15 | Có diagnostics, microbenchmark và runner cache | Full PRA evaluator, E2E benchmark hợp lệ, clean-run và bundle giao hàng |

Task04–15 tiếp tục IN_PROGRESS. Không lấy số lượng module hoặc tests làm tỷ lệ phần trăm hoàn thành MVP.

## 3. Findings hiện hành

### P1 — Demo entrypoint bị hỏng sau thay đổi API shot runner

[`run_demo.py:105`](../../codebase/scripts/run_demo.py#L105) vẫn truyền `is_play_006` và `is_free_throw`, trong khi [`run_engine_on_window:100`](../../codebase/scripts/run_task08_temporal_shot_engine.py#L100) đã bỏ hai tham số này. Chạy CLI mặc định tái hiện TypeError trước khi xuất kết quả.

Sửa: đồng bộ caller với API mới; không đưa lại hints theo tên pha. Bổ sung integration smoke qua entrypoint thật để phát hiện interface drift.

### P1 — Runner chưa xử lý video liên tục và chưa gọi rebound/assist

`run_demo.py` chỉ hash đường dẫn video rồi đọc cached windows `play_001` đến `play_010`. `ReboundEngine` và `AssistEngine` chỉ được khởi tạo. Không có decode→detect→tracking→PRA trên video được chọn. Missing input vẫn được biểu diễn bằng SHA `missing`; sửa TypeError đơn thuần chưa giải quyết pipeline hoặc validation.

Sửa: xây continuous runner nhận video/config và source PTS thật, gọi đủ engines; cache replay là chế độ diagnostic có source/model/config binding. Validate input trước chạy; xuất failed/partial/completed đúng thực tế, chống overwrite và báo coverage.

### P1 — Rebound có thể xác nhận khi chưa có eligible miss hoặc observed sustained control

[`rebounds.py:98`](../../codebase/src/basketball_scoreboard/rebounds.py#L98) chỉ loại `made`, vẫn chấp nhận `unknown`, `unresolved`, `not_a_shot`. Logic duration/frame ở dòng 137 không chặn predicted control hoặc hai quan sát cách xa nhau; FT applicability chưa có contract đủ dùng.

Sửa: whitelist eligible missed shot theo rules; thêm shot-kind/final-FT context; yêu cầu observed control liên tục, kiểm gaps/cuts/dead ball/confidence. Không đủ evidence thì unresolved. Sáu probes liên quan hiện fail.

### P1 — Assist có thể xác nhận từ pass/action evidence không hợp lệ

[`assists.py:127`](../../codebase/src/basketball_scoreboard/assists.py#L127) cho unknown receiver đi qua. Không yêu cầu confirmed pass với confidence đạt gate; chain-break set thiếu deflection/loose_ball/camera_cut; cấu hình direct-shot/dribble chưa thực thi đủ.

Sửa: yêu cầu receiver/scorer/possession links và pass evidence hợp lệ, áp dụng action/rule profile, invalidate khi chain break và parent score bị sửa. Sáu probes liên quan hiện fail.

### P1 — Chưa có dữ liệu/evaluation đủ để nghiệm thu PRA

Validator canonical `data/v2` báo 0 approved shots/rebounds/assists/control/pass/positions/identities, 0 roster players, test split rỗng và split draft. Điều này không phủ nhận reviewed packets Vietnam–Tonga hoặc 49 supplemental detector images ở namespace khác; cần tích hợp có provenance/review mapping, không tự tạo approval mới.

Artifact [`Task08 summary`](../../codebase/outputs/task08-shot-correctness-20261112/summary.json), Candidate C: 2 made predictions, TP=1, FP=1, FN=9, precision=50%, recall=10%, strict-all TP=0. Đây là diagnostic trên positive windows đã chọn, không phải formal blind E2E benchmark. Official negative specificity vẫn null do manifest draft.

### P2 — Dashboard và benchmark chưa thể dùng làm bằng chứng sản phẩm

[`dashboard.py:487`](../../codebase/src/basketball_scoreboard/dashboard.py#L487) tạo tọa độ X từ `frame_index % 7`, khoảng cách thiếu dùng mặc định 5,5m: shot map minh họa chưa phải geometry/heatmap thật.

[`benchmark_task14_performance.py:93`](../../codebase/scripts/benchmark_task14_performance.py#L93) coi class 0 là player, 1 là rim, 2 là ball, khác approved mapping 0=ball, 1=human, 2=rim. Benchmark thiếu các stages thực nên số FPS cũ chưa chứng minh throughput E2E.

### P2 — Tài liệu và training status có thông tin cũ/mâu thuẫn

README và task index vẫn chứa mô tả module chưa triển khai, OCR chưa có, và các đề nghị làm lại phần đã hoàn thành. Recovery report vừa ghi job dừng sau reboot, vừa ghi training đang chạy. Candidate target 30 epochs nhưng artifact chỉ có 1 epoch hoàn tất; không gọi đây là hoàn tất recipe 30 epochs. Hai checkpoints đã được đánh giá detector, nhưng `ocr_roi_identity_evaluated=false`, `control_pass_evaluated=false` trong comparison: regression tests không thay thế paired downstream evaluation.

## 4. Backlog đề xuất theo thứ tự

| Ưu tiên | Task cụ thể | Tiêu chí hoàn thành |
|---|---|---|
| P1 — làm ngay | A. Sửa demo API/CLI validation (Task15, integration Task08/11) | CLI thật chạy được; input sai fail rõ; không GT hints theo ID; integration smoke qua entrypoint thật |
| P1 — làm ngay | B. Sửa rebound và assist contracts (Task09–10) | 12 probes hiện fail chuyển pass; giữ tests chính pass; bổ sung eligibility/FT/control/action/cut và dependency lifecycle |
| P1 — nền dữ liệu | C. Hợp nhất reviewed GT, geometry, roster/rules/protocol (Task04–06) | Map packets đã review vào schema canonical; thiếu approval phải giữ pending; bổ sung positive/hard-negative PRA, footage nhóm độc lập; data-ready/locked-ready có evidence |
| P1 — tích hợp | D. Xây continuous MP4 runner (Task07–12/15) | Decode→detection→team/identity→control/pass→shots/PRA→ledger→heatmap/export trên input thật; PTS đúng, run hashes/coverage/errors rõ; gọi đủ REB/AST |
| P1 — chất lượng | E. Cải thiện ball + OCR/identity và paired downstream evaluation (Task06–08) | Error analysis có phân tầng, thử candidate riêng và giữ default; so sánh cùng clips/config, đo control/pass/identity/shot và precision/recall; không promote khi gate chưa đạt |
| P2 — giao diện | F. Dashboard dùng tọa độ/heatmap/evidence thật (Task05/12) | Không tạo vị trí minh họa khi thiếu geometry; unknown/unresolved và coverage rõ; seek/export/progress/cancel/failed được browser-test |
| P1 — gate nghiệm thu | G. Full PRA evaluator và frozen evaluation (Task13) | Có `scripts/evaluate_v2.py`; one-to-one strict PTS/REB/AST, actors/value/subtype/link/duplicates/unknown; trước correction; từng stat P≥95%, R≥90% hoặc báo chưa đạt |
| P2 — sau quality baseline | H. E2E benchmark và đóng gói (Task14–15) | Mapping đúng; đo toàn pipeline p50/p95/throughput/RAM/VRAM/confirmation delay; clean-run theo README, đủ bundle và acceptance matrix; offline/live kết luận theo số đo |
| P2 — duy trì cùng các task trên | I. Đồng bộ docs và trạng thái job | Một snapshot hiện hành trong PLAN/README/task index; lịch sử tách rõ; job status kiểm cả process identity và artifact freshness; recorded epochs đúng thực tế |

Có thể thực hiện A/B và chuẩn bị C độc lập. D cần contracts đủ rõ nhưng có thể xây bằng baseline hiện tại, không cần chờ model mới; đo quality sau khi tích hợp. G phụ thuộc GT frozen và predictions thật; H cần pipeline đo được. Việc chuẩn bị review packet được làm trước, approval human chỉ yêu cầu với phần thực sự mới/chưa được duyệt.

Không đề xuất chỉ tiếp tục train dài hơn như cách giải quyết duy nhất: hiện thiếu cả integration, identity/control, dataset acceptance và downstream evidence. Ưu tiên đợt tiếp theo: **A → B → D**, đồng thời hoàn thiện C và thiết kế paired evaluation cho E.
