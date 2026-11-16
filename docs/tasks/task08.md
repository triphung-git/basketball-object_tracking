# Task08 — Shot recognition, giá trị cú ném và points tự động

**Cập nhật thực thi 2026-11-12:** Đã hoàn thành triển khai và kiểm chứng toàn diện [Báo cáo kỹ thuật: Khắc phục và kiểm chứng tính đúng đắn của Temporal Shot Engine, Rim Crossing Continuity & Production Evaluator (Task 08)](../reports/task08-shot-correctness-20261112.md) theo yêu cầu [task08-shot-continuity-evaluator-correctness.md](../prompts/task08-shot-continuity-evaluator-correctness.md):
- **P1-B (Physical Continuity & Aperture Crossing):** Đã sửa `codebase/src/basketball_scoreboard/shots.py`. Bắt buộc mẫu quan sát thực (`observed`), ngắt FSM khi flight gap vượt 0.35s, kiểm tra điểm vào/ra hình học vành rổ, vận tốc rơi $v_y > 30$ px/s, và đo lường độ giảm tốc thực tế (`measured_pass`/`measured_no_decel`).
- **P1-C (Evaluator Correctness):** Đã tạo module chuẩn hóa `codebase/src/basketball_scoreboard/shot_evaluator.py` với giải thuật Ghép cặp hai phía cực đại min-cost (SPFA/MCMF), dung sai $\pm 0.50$s, loại bỏ hoàn toàn bẫy tham lam và hạch toán đúng duplicate FP và 5 góc nhìn đánh giá.
- **P1-D (Negative Cohort Truthfulness):** 30 tình huống âm tính thực tế đạt 100% tỷ lệ loại trừ chẩn đoán (0 FP); đặt `official_specificity = None` theo đúng trạng thái `draft_unreviewed` của manifest.
- **Loại bỏ triệt để GT Leakage:** Xóa bỏ toàn bộ cờ `is_play_006` và `is_free_throw` khỏi inference runner; FSM tự động loại bỏ góc máy lỗi runtime.
- **Kiểm thử & Bằng chứng:** 4/4 Task 08 acceptance probes PASS, 14/14 engine unit tests PASS, 11/11 evaluator tests PASS, 404/404 full codebase tests PASS (0 regressions). Tích hợp EventLedger & BoxScoreEngine bảo toàn và idempotent. Artifacts xuất tại [`codebase/outputs/task08-shot-correctness-20261112/`](../../codebase/outputs/task08-shot-correctness-20261112).
- **Trạng thái:** **IN_PROGRESS** (Chưa nghiệm thu toàn bộ MVP cho đến khi detector/tracker được fine-tune đạt PRA $P \ge 95\%, R \ge 90\%$).

Kiểm thử lại 2026-11-10: [acceptance report](../reports/demo-completion-acceptance-20261110.md). **IN_PROGRESS; chưa nghiệm thu.** Shot/points và evaluator còn lỗi crossing/matching; negative GT chưa được duyệt.

**Version: MVP v2 Automatic Stats, 2026-11-02. Trạng thái: IN_PROGRESS (Pha 1 Baseline chẩn đoán hoàn thành; Pha 2 Động cơ Ném bóng Chuỗi thời gian hoàn thành; chuẩn bị tích hợp Task09/11 và chờ detector fine-tune).**

Động cơ chuỗi thời gian 2026-11-09: [đã hoàn thành triển khai và đánh giá Động cơ Ném bóng Chuỗi thời gian](../reports/task08-temporal-shot-engine.md). Động cơ tích hợp: (1) FSM 4 pha `Ready -> Release -> FlightArc -> Outcome (Basket | Miss)` có an toàn Abort/Reset; (2) Xác nhận bàn thắng xuyên vành rổ từ trên xuống theo hình học khẩu độ thực tế kèm Net Deceleration Cue; (3) Bounded Causal Shooter History trong $[t_{\text{release}} - 2.0\text{s}, t_{\text{release}}]$ với cơ chế Fallback cấp đội; (4) Đánh giá đối chứng âm bản trên **30 tình huống thực tế duy nhất** từ video trận đấu (10 clean misses, 8 rim/backboard misses, 6 turnovers/non-shots, 6 broadcast replays) đạt **100% Specificity (0 FP, 0.0% false score rate)**. 10/10 unit tests PASS trong `test_task08_temporal_shot_engine.py`. Đã xuất xưởng artifacts tại `outputs/task08-temporal-engine-20261109/` và [bàn giao kỹ thuật sang Task09 và Task11](../handoffs/task08-temporal-shot-engine-to-task09-task11-20261109.md). Giữ trạng thái IN_PROGRESS vì cần nâng cao recall của ball detector upstream (Task07) và kiểm thử trên toàn bộ trận đấu độc lập.

Baseline chẩn đoán 2026-11-08 / 2026-11-09: [đã hoàn thành chạy baseline chẩn đoán 10 cửa sổ ghi điểm](../reports/task08-critical-moments-baseline.md), 1,423 frames xử lý hoàn tất trên ONNX CPU với TiledBallDetector. Kết quả: 62.05% observed ball coverage (86.01% observed+predicted), 10/10 rim detection tại basket, phân loại lỗi rạch ròi (8 identity missing tại release, 1 camera layout thay đổi ở FT play_006, 1 detector miss tại release do che khuất). Đã xuất bản packet review draft 20 keyframe tại `outputs/task08-critical-baseline-20261108/draft_review_packet/` và [bàn giao kỹ thuật sang shot engine](../handoffs/task08-critical-baseline-to-shot-engine-20261108.md). Chưa chuyển DONE vì cần xây dựng shot state machine và thu thập negative cohort. Task07 vẫn IN_PROGRESS.

Tiếp nhận 2026-11-07: [review đã trả về và chốt toàn bộ target conflicts](../reports/task08-scoring-review-intake-20261107.md), 34/34 metadata nhất quán; latest `outputs/task08-scoring-intake-20261107/adjudicated-v3/`. Có 10 cửa sổ clear/timed cho diagnostic có điều kiện, chưa có bbox GT/negative cohort/metrics points; mốc đối thủ trong play_034 đã được bỏ, không tự đoán mốc target. [Handoff](../handoffs/task08-scoring-review-to-critical-diagnostics-20261107.md). Không đổi trạng thái TODO hoặc dùng nhãn/scoreboard trong recognition.

Chuẩn bị 2026-11-06: đã tạo [packet 34 candidate tăng điểm, 8 clip ưu tiên](../reports/vietnam-tonga-scoring-review-20261106.md) từ scoreboard video Việt Nam–Tonga để người dùng review khả năng quan sát tại release/rim. [Hướng dẫn](../guides/vietnam-tonga-scoring-review.md). Nhãn pending; đây là annotation assistance, không phải engine points đã triển khai hoặc nghiệm thu. Không dùng scoreboard/nhãn này làm recognition input; Task07 vẫn IN_PROGRESS.

Ước lượng: 4–6 ngày công (không bao gồm chờ đầu vào nếu có). Phụ thuộc: Task04–07.

## Mục tiêu

Tự nhận người ném, shot kind/value, made/miss và points; đây là module bắt buộc, không dùng point selector mỗi lượt.

Nguồn phạm vi: [MVP đã duyệt](../MVP-v2-proposal.md), [PLAN v2](../../PLAN.md), [chỉ mục](README.md). Đọc DEVELOPMENT và contracts/rules v2 khi được tạo. Task01–02 chỉ là baseline đã nghiệm thu.

## Bạn cần cung cấp / xác nhận

- GT shooter/release/outcome/value, free-throw sequences, bank/rim-bounce/miss/blocked cases và tình huống không tính điểm.
- Court/arc geometry và rule profile đã duyệt.

## Agent sẽ xây dựng

1. Shot release từ ball/controller/body evidence; shooter gắn player_id/team, không chọn người gần rổ khi bóng đã vào.
2. State machine/timeline cho flight→rim→outcome; xác nhận basket bằng observed multi-frame evidence và reset chống đếm lặp.
3. Value theo rule profile 3x3 và vị trí chân tại release/last floor contact, không lấy vị trí tiếp đất; FT recognition từ sequence/context, không coi mọi cú ném trong paint là FT.
4. Tạo shot_id, points candidate/provisional/auto_confirmed/void/unresolved, point_value, team/player, evidence và confirmation latency.
5. Phân biệt score observed và điểm trọng tài công nhận không thể thấy; thiếu bằng chứng không tự giả định. Không OCR/đọc GT score để thay pipeline.
6. Baseline rule-based có thể thử trước; nếu outcome/value/FT cần temporal model, dùng calibration labels và quyết định model/data rõ.

## Đầu ra bắt buộc

- shots.py, points.py; automatic shot/score events và evidence clips/timestamps.
- docs/reports/task08-points.md; schema liên kết shot–score và tests giá trị.

Các đường dẫn code/config/output tương đối với codebase trừ docs/. Đây là thiết kế để triển khai, không phải file/tính năng đã hoàn thành. Mỗi run có versions/config/fingerprints và evidence, không có API key.

## Nghiệm thu

- [ ] Không thao tác nhập/duyệt từng pha, tự sinh points trên calibration hai đội cả 1/2 point và FT trong profile.
- [ ] One shot one score; actor/team/value sai được báo riêng, không chỉ tổng score.
- [ ] Có cả positive/negative và unresolved; mục tiêu strict P≥95%, R≥90% được kiểm ở task13, chưa đạt thì không tuyên bố MVP hoàn thành.

## Kiểm thử cần thiết

- Ball đi từ dưới lên, chỉ chạm bbox rổ, rim bounce/miss, bang-board, ID đổi giữa shot.
- Arc/feet/release vs landing, FT không cuối/cuối, no-shot control transitions.
- Prediction-only basket, repeated frames/seek/cuts và duplicate shot detection.

Không dùng synthetic fixtures như dữ liệu thật, không dùng labels/manifest notes làm oracle recognition. Calibration/test v2 phải tách nhóm; labels/split v1 đã khóa được giữ nguyên. Chỉ test phù hợp thay đổi và integration evidence cần thiết, không benchmark lặp không có lý do.

## Rủi ro và điều kiện dừng phần phụ thuộc

Points là prerequisite cho assists; nếu chỉ nhận bóng vào mà chưa biết value/actor thì module mới partial. Không lùi về giá trị nhập sẵn mà đánh dấu DONE.

Không cần hỏi lại có làm automatic PRA hay không: đã duyệt. Hỏi trước các thay đổi model/backend/dependency lớn, GPU stack, chi phí/cloud upload, dataset locked hoặc scope; tiếp tục phần độc lập trong khi chờ. Không xem im lặng là đồng ý. Không thay engine tự động bằng thao tác nhập/duyệt tay để đánh dấu DONE.

## Bàn giao

Shot/outcome/value/shooter/score events, missing/FT-series context cho task09–11.

Khi kết thúc, cập nhật task này và report với file paths, lệnh đã chạy, số liệu thật, điều kiện chưa đạt và bước tiếp theo. Chỉ chuyển DONE khi checklist có bằng chứng; sửa tay không thay automatic metrics.
