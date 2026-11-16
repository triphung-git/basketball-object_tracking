# Hướng dẫn phát triển

Cập nhật nghiệm thu 2026-11-10: [report](reports/demo-completion-acceptance-20261110.md) — **REQUEST CHANGES**. 367 tests + 61 subtests hiện có PASS, nhưng 39/40 contract probes fail; browser 10 pass/8 fail. Data integrity/hình học đạt phạm vi audit; full PRA/demo, GPU training readiness, ledger/dashboard/E2E benchmark chưa đạt. Không coi cache replay là continuous video pipeline.

Review scoring 2026-11-07 đã chốt: [report](reports/task08-scoring-review-intake-20261107.md), [handoff](handoffs/task08-scoring-review-to-critical-diagnostics-20261107.md). 34 clip user-reviewed, 34 metadata nhất quán sau toàn bộ xác nhận: 009 Tonga#11, 024 Tonga#9, 034 Việt Nam#6 field goal; 027/028 liên kết lại theo user. Latest intake `outputs/task08-scoring-intake-20261107/adjudicated-v3/`; các snapshot trước giữ nguyên. Mốc FT Tonga trong 034 được bỏ ở bản dẫn xuất, không đoán mốc target. 10 cửa sổ critical rõ/timed không đổi, không phải ball bbox GT hoặc điểm tự nhận diện. 15 tests +10 subtests PASS; không sửa engine/train/weights. Task07 IN_PROGRESS, Task08 TODO.

Chuẩn bị review scoring 2026-11-06: [report](reports/vietnam-tonga-scoring-review-20261106.md), [guide](guides/vietnam-tonga-scoring-review.md), packet `outputs/task08-scoreboard-review-20261106/review.html`. 34 candidate tăng điểm từ scoreboard, 8 clip ưu tiên; tất cả pending user review. Scoreboard/OCR font calibration chỉ để chuẩn bị annotation, không phải recognition input hoặc benchmark made shots. Không train/đổi weights. Task07 IN_PROGRESS, Task08 TODO; chờ review để chọn cửa sổ release/rim cho diagnostic tiếp theo.

Task07B2026-11-06 đã triển khai/test: [report](reports/task07b-crop-ownership-20261106.md), [handoff](handoffs/task07b-crop-ownership-20261106.md),290tests PASS. Candidatehẹp `--team-crop-region jersey --reset-on-team-conflict` sửa team snapshots5/7→7/7 và giữ ball50%, nhưng control/pass vẫn0%, IDcoverage giảm; defaultslegacy/off. Fullguard crop tuy giữ7/7good crops và chặn4/7bad crops nhưng regressionball45,83%, khôngpromote. Không train/đổiweights, không cầnreviewlạibatch; Task07IN_PROGRESS.

Đã nhận review thật Checkpoint A: [report](reports/task07-checkpoint-a-reviewed-20261105.md),278tests PASS. Snapshot mới `outputs/task07-checkpoint-a-return-20261105/accepted-v2/merged-progress-v3.json` giữ40nhãn cũ và thêm9approved/2skipped; frame542s uncertain được giữ riêng, không làm negative. Có14crop identity reviewed,7crop sai vùng/đối tượng trong batch; freshOCR upscale3 tái lập4/5readable crops. Giữ cấu hình hiện hành, chưa train/promote. Không dùng fixture synthetic. Task07 IN_PROGRESS.

UI review Checkpoint A đã đơn giản hóa tại run-08: [hướng dẫn](guides/task07-checkpoint-a-simple-review.md), [QA34browser checks +6subset tests](reports/task07-checkpoint-a-review-ui-20261105.md). Dùng template `task07a_checkpoint_a_review_simple.html` và renderer riêng khi chỉ sửa UI, không chuẩn bị/inference lại media. Source/manifest/nhãn thật giữ nguyên; các file `ui-qa/synthetic-*.json` chỉ phục vụ test.

Checkpoint A 2026-11-05: [audit và packet review nhỏ](reports/task07-checkpoint-a-audit-20261105.md). Tái sử dụng 40 nhãn được duyệt; packet mới yêu cầu review 12 frame/14 crop. Giữ nguyên labels, weights, GT và split; chưa có labels mới hoặc benchmark identity, Task07 vẫn IN_PROGRESS.

Sau người dùng review40frame: đọc [report feedback](reports/task07a-reviewed-feedback-20261105.md),269tests PASS. Dùng draft v2 trong report để giữ tiến độ và sửa bbox đầu gối theo xác nhận người dùng; packet toàn bộ vẫn draft. Single-active-ball preview có giảm FP so với top1 nhưng không tăng recall; actor continuity optional mặc định0,900frame replay giữ36/72. Không promote geometry/cue, không đổi weights/train; Task07 IN_PROGRESS. Không nhầm1Hz annotation candidates với output tracking30FPS.

Dataset-first đã được người dùng duyệt và chuẩn bị: [report](reports/task07a-dataset-first-20261105.md),257tests PASS,27ảnh QA và359frame model-assisted draft. Current project có same-photo derivatives ở train/test đã xác minh pixel/registration; chưa sửa cloud/split. Dùng [review guide](guides/task07a-dataset-label-review.md); null/unreviewed không phải negative, không export/train trước human label QA và approval riêng về job/cost. Không hỏi lại hướng dataset-first.

Checkpoint07A đã thực thi: [report](reports/task07a-improvement-checkpoint.md),251tests PASS. `ObjectDetector.detect` có optional network WH với default giữ nguyên; actual ONNX-feed trace chỉ dùng diagnostic CPU. Baseline113/113tương đương;960square/letterbox640 đều regression, không promote. Current model/project metadata đã đọc qua Roboflow, chưa train hoặc đổi weights. Xem [proposal dữ liệu](reports/task07a-data-finetune-proposal.md) trước chuyển giai đoạn.

Cập nhật chẩn đoán2026-11-05: đọc [roadmap nguyên nhân và checkpoint07A–07C](reports/task07-improvement-roadmap-20261105.md). Audit21tổ hợp resolution/confidence giữ baseline; không kết luận dataset thiếu domain hay resize là nguyên nhân gốc khi chưa đủ bằng chứng. Artifacts resolution dùng wrapper khác current source, cần chốt tái lập trước promote.45/126OCR readings không exact-match roster chỉ là diagnostics, không phải OCR error rate. Không train/thay model bằng suy đoán.

Task07A đã thử confidence0.10 và tile upscale1.5 trên development với cùng approved model; không config nào cải thiện observed recall v4, upscale tốn khoảng3.3x. Baseline v4 vẫn tốt nhất ở36/72=50%, dưới gate90%; xem [report Task07A](reports/task07a-ball-detection.md). Candidate recall chỉ là diagnostics; Task07 vẫn IN_PROGRESS.

Code Task07 mới nhất hỗ trợ optional source-bound ball search ROI tách footpoint ROI và conservative roster OCR consensus. Đọc [spatial reliability v4](reports/task07-spatial-reliability-20261104.md):240tests PASS, development ball recall50%, strict control/pass0%. Giữ v3 regression và v2 baseline, không gọi0observed ngoài ROI là0false detections. ROI theo camera còn thủ công; OCR fresh accuracy chưa cải thiện bằng chứng.

Kết quả real-data hiện hành: [Task07 development evaluation v2](reports/task07-development-evaluation-v2-20261104.md), `failed_criteria` dù đủ minimum samples. Dùng canonical GT `codebase/data/matches/vietnam_tonga/reviewed-vt_development-v2.json` trong evaluator, không trong recognition. Hai xung đột control đã được người dùng xác nhận; không hỏi lại. Recognition chưa đạt, validation GT còn pending; các snapshot trước không thay kết quả này.

Cập nhật pilot mới nhất 2026-11-04: đọc [report Vietnam–Tonga](reports/task07-vietnam-tonga-segments.md), [handoff](handoffs/task07-vietnam-tonga.md), [review guide](guides/task07-vietnam-tonga-review.md). Roster/protocol đã duyệt; GT review pending. **233 tests PASS**, integrity audit PASS, nhưng chưa có completed pass và player-controller coverage thấp: Task07 vẫn IN_PROGRESS. Giữ đúng approved model/local CPU, không dùng GT làm recognition input, không gọi cache replay FPS là realtime, không xin lại approval đã có. Cả hai đoạn đã triage cùng trận, không phải independent test. Các cập nhật 207 tests bên dưới là lịch sử.

Cập nhật 2026-11-04: [Task07 implementation/report](reports/task07-ball-possession.md) và [handoff task08–10](handoffs/task07-to-task08-09-10.md) đã có, 207 tests PASS. Task07 vẫn IN_PROGRESS do chưa đạt real-data acceptance. OCR đã được người dùng phê duyệt, weights local/CLI đã chạy; không coi đây là blocker xin quyền còn mở. Người dùng đã [cho phép dùng đúng clip04 development và ghi exposure nhóm clip04–07](decisions/20261104-clip04-development-exposure.md). Giữ dataset/lock v1; truyền scoped authorization tường minh, không dùng nhóm đã exposure làm untouched holdout. Các chỉ dẫn lịch sử bên dưới cần đọc cùng cập nhật này.

## Phạm vi hiện hành — 2026-11-02

Người dùng đã duyệt **MVP v2 tự động nhận diện points/rebounds/assists**. Đọc [MVP](MVP-v2-proposal.md), [PLAN v2](../PLAN.md), [task index](tasks/README.md), task liên quan và handoff hiện hành trước triển khai. Không thay bằng form nhập/duyệt từng pha; manual correction chỉ phục vụ audit và tách khỏi metrics tự động.

Task01–02 giữ nghiệm thu baseline v1. Task03–08 đã được viết lại; task09–15 bổ sung. Snapshot plan/task cũ ở archive/2026-11-02-pre-auto-stats/, không còn là hướng dẫn triển khai. Các đoạn hướng dẫn MVP scoreboard cũ bên dưới là lịch sử, không được dùng để ghi đè phạm vi v2.

Nghiệm thu hiện hành: [task03–04](reports/task03-task04-acceptance.md), [dataset v2](reports/data-v2.md), [handoff task05–06](handoffs/task04-to-task05-06.md). Task04 chỉ bàn giao công cụ, còn chờ footage/roster/labels/rules/protocol và split freeze; task05–06 chưa được nghiệm thu. Đọc contracts v2.0.1 và các readiness notes trước phát triển phần phụ thuộc.

Cập nhật 2026-11-03: [tái nghiệm thu task05–06](reports/task05-task06-acceptance.md) xác nhận core tooling/diagnostic integration; cả hai vẫn IN_PROGRESS vì geometry/GT và OCR/identity data pending. Dùng [handoff task07](handoffs/task06-to-task07-08-12.md), giữ predicted/unknown đúng nghĩa, không dùng mapping cuối video làm event-time identity hoặc ROI làm bằng chứng player.

Source/config/tests ở codebase, docs ở docs; dữ liệu v2 version riêng trong codebase/data/v2/. Giữ nguyên data/annotations và split pilot đã khóa. Tự động hóa không cho phép đọc GT/notes để suy kết quả. Input baseline vẫn MP4 3x3 camera ổn định; real-time và gần100% chưa được chứng minh. Roster/calibration trước phiên được phép, actor/event recognition phải tự động.

## Hướng dẫn baseline v1 và bảo mật còn áp dụng

Đọc tài liệu này, `../PLAN.md` và task liên quan trong `tasks/` trước khi sửa code. Đọc `reports/environment.md` trước khi thay runtime. Mã nguồn, dependency, config và scripts nằm trong `../codebase/`; tài liệu thiết kế, yêu cầu và báo cáo nằm trong `docs/`.

Không đánh dấu task01 hoàn tất trước khi chạy đúng model trên clip thật, xác nhận schema/class mapping và đo latency. Không đổi model âm thầm; không commit key hoặc video lớn. Dùng timestamp video cho logic sự kiện. Những phần chưa chạy phải được ghi là chưa kiểm chứng.

## Tiêu chuẩn clip đầu vào

- Đợt đầu: 2–3 MP4 khoảng 10–30 giây/clip; ưu tiên 720p/1080p, ít nhất 25–30 FPS nếu có. Đây là tiêu chuẩn thu thập đề xuất, không bảo đảm độ chính xác.
- Camera cố định hoặc đoạn quay gần như cố định, một rổ rõ và một bóng. Thấy bóng từ trước khi đến vành đến sau khi xuống dưới rổ; giữ thêm khoảng 1–2 giây trước/sau pha.
- Có cả vào và trượt, bật vành. Tránh chỉ lấy khoảnh khắc bóng đã nằm dưới rổ, zoom quá xa, bảng chữ che rổ, slow motion và frame nội suy.
- File gốc có quyền sử dụng; có âm thanh/bình luận/nhạc đều được. Pipeline bỏ qua audio, video kết quả có thể không giữ audio.
- Highlights nhiều góc: dùng để smoke test detection được; để đếm điểm hãy chọn/tách đoạn góc ổn định và cấu hình lại ROI mỗi đoạn. Pan/zoom đáng kể vẫn ngoài MVP dù không có hard cut.
- Replay không phải một lượt ném mới. Bỏ replay khỏi tập đếm hoặc gán dấu rõ và loại khỏi scoring; MVP chưa tự nhận replay/cắt cảnh. Không chạy toàn bộ montage rồi kỳ vọng tổng điểm trận đúng.

Đặt clip trong `codebase/data/raw/` hoặc `codebase/assets_test/` (ba clip hiện tại ở assets_test; cả hai được bỏ qua trong Git). Nếu chỉ có highlights, cung cấp file và thời gian bắt đầu/kết thúc 2–3 đoạn phù hợp; không cần tự quay mới ngay. Ground truth chi tiết thuộc task02.

## Quy tắc tính điểm MVP

Không cần gửi toàn bộ luật bóng rổ. Chọn đội (hoặc solo) và giá trị 1/2/3 trước lượt; máy chỉ nhận diện bóng vào và cộng giá trị đã chọn. Mặc định solo, 2 điểm/lượt. Đây là cấu hình sản phẩm, không phải thuật toán xác định cú ném 2/3 điểm.

Chưa xử lý tự động vị trí chân, vạch ba điểm, ném phạt, buzzer, lỗi, goaltending, điểm bị hủy hoặc đổi sân. Nếu muốn mở rộng theo luật giải cụ thể, cung cấp tên/bản luật và tình huống cần hỗ trợ; phải đổi phạm vi và đánh giá lại lịch.
