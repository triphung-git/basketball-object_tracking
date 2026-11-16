# Task07 — Ball tracking, control, passes và possession

Prompt thực thi ưu tiên ngày 13/11/2026: [Training readiness, fine-tune và paired evaluation](../prompts/task07-finetune-readiness-paired-evaluation.md). Bao gồm loss thật, training có checkpoint và regression OCR/ROI/identity; việc tạo prompt chưa thay đổi trạng thái nghiệm thu bên dưới.

Cập nhật 2026-11-08: [Nghiệm thu Task07C](../reports/task07c-acceptance-report-20261107.md), **FAILED CRITERIA — Task07 TIẾP TỤC IN_PROGRESS**. Đã thực thi pipeline candidate freeze trên cả hai đoạn validation và development theo protocol đã chốt. Integrity guards đạt 100% PASS (0 prediction-only control, 0 cut crossing pass, PTS error $\le 2\mu\text{s}$). Tuy nhiên, các tiêu chí cốt lõi thất bại: Ball recall 50.00% (ngưỡng $\ge 90\%$), Strict control accuracy 0.00% (ngưỡng $\ge 90\%$), Strict pass recall 0.00% (ngưỡng $\ge 90\%$). Tập validation thiếu nhãn đã duyệt (`review_status: draft`, 0 control intervals, 0 passes). Đã lập [acceptance manifest](../../codebase/outputs/task07c-acceptance-20261107/manifest.json) (35 files) và [handoff sang Task08](../handoffs/task07c-to-task08.md) xác định rõ: Task08 được dùng player tracks, team assignments, court projection và cut exclusions; TUYỆT ĐỐI KHÔNG dùng automated assists/rebounds/ball flight cho đến khi Task07 đạt chuẩn. Các Task04–06 giữ nguyên trạng thái.

Cập nhật 2026-11-07: [Task07B decoupling & paired evaluation](../reports/task07b-decoupling-20261107.md), **309 tests PASS**. Đã tách biệt thành công ngữ nghĩa actor/body context (`sample_type == 'observed' and role != 'non_player'`) khỏi jersey/identity uncertainty, loại bỏ 100% hiện tượng regression của Full Guard (ball recall phục hồi từ 45.83% về 50.00%). Candidate `jersey + conflict-reset` giảm 89.5% thời gian gán sai team (0.633s -> 0.067s). Truy nguyên 7 tầng xác định detector miss (40.3% thời lượng) và thiếu số áo OCR là nguyên nhân chính khiến strict control/pass đạt 0%. Đã lập phương án huấn luyện fine-tune detector (40 GT reviewed v2 + 319 draft frames, split chống rò rỉ, YOLOv8 CPU ONNX, chi phí 0 USD) chờ phê duyệt. Task07 tiếp tục **IN_PROGRESS**, candidate chưa đủ điều kiện freeze cho 07C. Xem [handoff](../handoffs/task07b-decoupling-20261107.md).

Cập nhật 2026-11-06: [Task07B crop/ownership/team](../reports/task07b-crop-ownership-20261106.md), 290 tests PASS. Có candidate team-conflict reset 5/7→7/7 team snapshots, ball 50% giữ nguyên, strict control/pass 0%. Fullguard làm ball 45.83% nên không bật. Identity temporal chưa đo; defaults legacy/off, chưa freeze 07C hoặc DONE. Xem [handoff](../handoffs/task07b-crop-ownership-20261106.md).

Đã tiếp nhận nhãn Checkpoint A: [report](../reports/task07-checkpoint-a-reviewed-20261105.md),278tests PASS. Merged corpus49approved/2skipped/308unreviewed,40row cũ giữ nguyên;14crop identity reviewed. Người dùng đã xác nhận đổi bboxball lớn541s thànhhuman và quarantine542s uncertain. Raw proposal batch mới6/8visible matches; không so thành improvement với batch cũ hoặc continuous50%. Ưu tiên sửa crop/track ownership và team evidence; chưa train/promote, Task07 IN_PROGRESS.

Cập nhật Checkpoint A ngày 2026-11-05: [audit và packet review nhỏ](../reports/task07-checkpoint-a-audit-20261105.md). Đã tái sử dụng 40 nhãn cũ, chuẩn bị 12 frame và 14 crop identity có source/PTS binding; labels mới vẫn chờ người dùng review. Chưa đổi thuật toán/model; Task07 tiếp tục IN_PROGRESS.

Cập nhật review40frame: [report2026-11-05](../reports/task07a-reviewed-feedback-20261105.md),269tests PASS. Nhãn v2 sửa đúng1bbox đầu gối theo xác nhận người dùng;319ảnh còn draft. Single-ball context giảm false selections27→16so với top1 nhưng recall giữ39,39% trên40ảnh; temporal actor cue trên900frame không tăng recall50%, giữ tắt mặc định. Không train/đổi weights, Task07 IN_PROGRESS.

Cập nhật dataset-first đã duyệt: [QA/pilot359frame](../reports/task07a-dataset-first-20261105.md),257tests PASS. Đã có ảnh/nhãn gốc QA và gợi ý bbox để người dùng review; chưa human-approved pilot labels, chưa train/đổi weights hoặc đạt accuracy. Không hỏi lại hướng dataset-first; Task07 IN_PROGRESS.

Checkpoint thực thi07A ngày2026-11-05: [report](../reports/task07a-improvement-checkpoint.md),251tests PASS, baseline tái lập113/113sampled frames. Candidate baseline41/72, square96039/72, letterbox64018/72; giữ continuous v4 observed50%, control/pass0%. Dataset-first proposal đã sẵn để review; chưa train/thay model, chưa qua gate07A, Task07 IN_PROGRESS.

Cập nhật2026-11-05: dùng [roadmap nguyên nhân/phép thử07A–07C](../reports/task07-improvement-roadmap-20261105.md). Audit21tổ hợp resolution/confidence không đổi baseline; ưu tiên tái lập preprocessing, audit dataset/crop/track và đo từng tầng trước quyết định fine-tune/Kalman. Chưa train, chưa có accuracy acceptance mới; Task07 IN_PROGRESS.

Cập nhật sửa spatial/OCR consensus: [report](../reports/task07-spatial-reliability-20261104.md),240tests PASS. Development v4 có ball recall50% (baseline43.06%), strict control/pass vẫn0%; Task07 IN_PROGRESS. Ball search ROI là cấu hình theo camera, đã tune trên development, chưa kiểm chứng tổng quát. Các kết quả trước giữ làm baseline.

Cập nhật Task07A: [controlled ball-detection ablation](../reports/task07a-ball-detection.md). Cùng approved model, confidence0.10 cho candidate recall42/72 nhưng observed29/72; upscale crop1.5 cho observed31/72 và latency3.3x. Không ablation nào vượt v4; giữ v4 36/72=50% làm best development, ngưỡng90% chưa đạt. Task07 IN_PROGRESS.

Cập nhật full evaluation development 2026-11-04: canonical GT đã review và sửa theo xác nhận người dùng, phép đo trả **`failed_criteria`**: ball recall43.06%, strict control accuracy0%, pass recall0%, precision N/A. [Report và failure analysis](../reports/task07-development-evaluation-v2-20261104.md). Task07 tiếp tục **IN_PROGRESS do recognition chưa đạt**, không còn chỉ chờ GT development. Validation GT vẫn pending; các snapshot trước ở dưới giữ để truy vết.

Cập nhật pilot Vietnam–Tonga 2026-11-04: roster thật và protocol/ngưỡng đã được người dùng duyệt; hai đoạn 30s đã chạy, **233 tests PASS** và integrity audit PASS. [Report mới nhất](../reports/task07-vietnam-tonga-segments.md), [review GT](../guides/task07-vietnam-tonga-review.md), [handoff](../handoffs/task07-vietnam-tonga.md). Ball observed 514/530 trên 900 frames mỗi đoạn, confirmed control có player_id 0/4, completed passes 0/0; đây là counts chưa đối soát, không phải accuracy. GT vẫn chờ review; real ball/control/pass criteria chưa được chứng minh đạt, Task07 tiếp tục IN_PROGRESS. Hai outputs đã triage cùng trận, không phải independent/untouched test. Phần dưới mô tả baseline clip04 trước pilot này.

**Version: MVP v2 Automatic Stats, 2026-11-04. Trạng thái: IN_PROGRESS — implementation/fixtures và demo 3x3 PASS; real-data acceptance chưa đạt.**
Ước lượng: 3–5 ngày công (không bao gồm chờ đầu vào nếu có). Phụ thuộc: Task03, task04, task06.

Đã triển khai ball/control/pass/operational possession, CLI, evaluator và debug exports. Đọc [report task07](../reports/task07-ball-possession.md), [contracts](../specs/ball-possession-v2.md) và [handoff task08–10](../handoffs/task07-to-task08-09-10.md) trước tiếp tục. 207 tests PASS; clip04 chạy 447 frames với roster giả lập/OCR local. Ball coverage còn thấp, chưa xác nhận được pass và chưa có reviewed GT; không tự coi real attribution đã PASS.

Người dùng đã cho phép dùng clip04 và ghi exposure nhóm clip04–07 theo [quyết định](../decisions/20261104-clip04-development-exposure.md). Authorization theo SHA được truyền tường minh; giữ nguyên các file dataset/split v1. Không hỏi lại quyền đã cấp hoặc coi nhóm này là holdout chưa tiếp xúc.

## Mục tiêu

Xây lịch sử ai kiểm soát/chuyền bóng để phân biệt cú ném, rebound và assist.

Nguồn phạm vi: [MVP đã duyệt](../MVP-v2-proposal.md), [PLAN v2](../../PLAN.md), [chỉ mục](README.md). Đọc DEVELOPMENT và contracts/rules v2 khi được tạo. Task01–02 chỉ là baseline đã nghiệm thu.

## Bạn cần cung cấp / xác nhận

- Nhãn bóng/control/pass trên calibration, gồm che khuất, handoff/bounce pass, loose ball, deflection và turnover.
- Các khoảng control thật sự không thể nhìn phải ghi uncertain trong GT, không ép nearest-player label.

## Agent sẽ xây dựng

1. Theo dõi ball candidates bằng vị trí/vận tốc/thời gian/confidence, phân observed/predicted và giới hạn mất dấu; không nối bóng qua cut.
2. Control assignment dựa nhiều frame, tương tác tay/thân/quỹ đạo và relative motion; không chỉ argmin khoảng cách bóng–người ở một frame.
3. Temporal state machine free/controlled/pass/shot_candidate/loose/unknown; possession_id và pass_id ổn định.
4. Phân biệt dribble, pass/handoff, steal/deflection và tranh chấp; control chỉ đổi sau evidence đủ, không do bbox overlap đơn lẻ.
5. Output causal: transition times, actors/evidence/certainty; reset qua coverage gaps/scene cuts. Nếu cần pose/temporal model, lập quyết định cụ thể trước thêm stack.
6. Đo ball recall gần các hành động trọng yếu, control attribution accuracy/unknown coverage và pass actor correctness trên calibration.

## Đầu ra bắt buộc

- ball.py, possession.py; ball_control.jsonl/pass observations, contracts và configs.
- docs/reports/task07-ball-possession.md kèm video timeline debug.

Các đường dẫn code/config/output tương đối với codebase trừ docs/. Đây là thiết kế để triển khai, không phải file/tính năng đã hoàn thành. Mỗi run có versions/config/fingerprints và evidence, không có API key.

## Nghiệm thu

- [ ] Các chuỗi chuyền/dribble/loose/shot candidates có timestamp/actor đúng trên fixtures và calibration có GT.
- [x] Prediction-only không xác nhận possession hay stat; gap không tạo đường chuyền ảo. Tests và independent artifact audit PASS ngày 2026-11-04.
- [ ] Đủ output cho scorer/rebound/assist để hoạt động mà không xem GT; failed/missing observations lộ rõ.

## Kiểm thử cần thiết

- Hai người gần bóng, dribble sát đối thủ, bounce pass, handoff và deflected pass.
- Control contested/occluded, ball out of view, reacquire, cut/coverage reset.
- CFR/VFR causal transition và replay chạy lại cho cùng IDs/events.

Không dùng synthetic fixtures/roster như dữ liệu thật, không dùng labels/manifest notes làm oracle recognition. Calibration/test v2 phải tách nhóm; labels/split v1 đã khóa được giữ nguyên. Clip04 đã được dùng development theo quyết định exposure riêng, nhóm clip04–07 không còn independent holdout cho đánh giá mới. Chỉ test phù hợp thay đổi và integration evidence cần thiết, không benchmark lặp không có lý do.

## Rủi ro và điều kiện dừng phần phụ thuộc

Ball mất thường xuyên ở vùng rổ/pass là blocker, cần cải thiện crop/data/model được phép trước. Không bù bằng assignment từ annotations hoặc đoán mọi gap là pass.

Không cần hỏi lại có làm automatic PRA hay không: đã duyệt. Hỏi trước các thay đổi model/backend/dependency lớn, GPU stack, chi phí/cloud upload, dataset locked hoặc scope; tiếp tục phần độc lập trong khi chờ. Không xem im lặng là đồng ý. Không thay engine tự động bằng thao tác nhập/duyệt tay để đánh dấu DONE.

## Bàn giao

Ball/control/pass/possession timeline và actors cho task08–10; schema giữ evidence phân biệt detection và inference.

Khi kết thúc, cập nhật task này và report với file paths, lệnh đã chạy, số liệu thật, điều kiện chưa đạt và bước tiếp theo. Chỉ chuyển DONE khi checklist có bằng chứng; sửa tay không thay automatic metrics.

---

### Nhật ký cập nhật ngày 2026-11-13: Phục hồi Training Readiness, Fine-tune & Paired Evaluation
- **Báo cáo chi tiết:** [docs/reports/task07-finetune-recovery-20261113.md](file:///c:/Users/Admin/OneDrive - National Economics University/Documents/object tracking/docs/reports/task07-finetune-recovery-20261113.md)
- **Training Readiness:** Đã sửa triệt để thiếu `hyp.box` trong Ultralytics bằng `get_cfg(DEFAULT_CFG_DICT, overrides=model.args)`. Chứng minh detection loss thật trên CUDA: batch loss 6.0142, finite gradients 366 tensors, label sensitivity passed ($\Delta \text{loss} = 14.20$).
- **Pilot Checkpoint:** Hoàn thành 1 epoch pilot trên 6.711 train + 515 val images (`codebase/outputs/task07-finetune-recovery-20261113/pilot/pilot/weights/best.pt`).
- **Paired Evaluation:** Đánh giá native detector trên 2 splits:
  - `val` (515 ảnh): Ball recall tăng $+2.59\%$ ($82.28\% \to 84.87\%$), Ball mAP50 tăng nhẹ $+0.0013$, mAP50-95 tăng $+0.0162$. Quyết định: `inconclusive`.
  - `test` (219 ảnh): Ball mAP50 tăng $+0.0120$, tổng mAP50 tăng $+0.0110$, mAP50-95 tăng $+0.0289$.
- **Downstream Protection & Tests:** 100% tests Task08 và Task11 PASS; toàn bộ 405 tests codebase PASS.
- **Candidate Job & Checkpoint:** Hoàn thành Epoch 1 (`candidate-training/candidate/weights/best.pt`, SHA-256 `a6c0c6ea...`). Paired evaluation ghi nhận val Ball recall $83.03\%$ ($+0.75\%$), mAP50 dao động $-0.0063$, quyết định `inconclusive`.
- **Quyết định Promotion:** **REJECTED cho cả 2 candidates.** Giữ nguyên model mặc định `phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1` (ONNX CPU). Task07 tiếp tục `IN_PROGRESS` cho đến khi OCR và strict control/pass đạt ngưỡng nghiệm thu $\ge 90\%$.
