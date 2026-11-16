# Handoff07A → 07B — checkpoint2026-11-05

Đã thực hiện bước07B ngày2026-11-06: [report](../reports/task07b-crop-ownership-20261106.md), [handoffmới](task07b-crop-ownership-20261106.md),290tests PASS. Có sửa crop guard/mask/teamconflict; candidatehẹp giữball50%vàsửa2teamerrors trênsample, fullguardregressionkhôngpromote. Chưaquaaccuracygate; khôngcầnreviewlạibatch.

Đã có nhãn thật từ batch12frame/14crop: [report tiếp nhận](../reports/task07-checkpoint-a-reviewed-20261105.md),278tests PASS. Dùng merged-progress-v3 trong `task07-checkpoint-a-return-20261105/accepted-v2/`; giữ frame542s uncertain.7/14crop trong batch được xác nhận sai vùng/đối tượng, cần sửa upstream; freshOCR upscale3 vẫn4/5trên5crop readable. Team masked extraction trêncorrect crop có tín hiệu7/7nhưng chưa là temporal identity accuracy. Không cần duyệt lại batch để tiếp tục chẩn đoán; chưa promote/train hoặc mở nghiệm thu07C.

Cập nhật sau feedback người dùng về nhiều bóng/background/temporal: [40frame audit và thử nghiệm](../reports/task07a-reviewed-feedback-20261105.md),269tests PASS.40ảnh đã review,319ảnh còn unreviewed; draft v2 giữ tiến độ và sửa đúng bbox đầu gối người dùng xác nhận. Spatial/context chưa tăng recall; optional actor cue đã thử theo yêu cầu mới nhưng900frame vẫn50%, không promote. Chưa qua gate07A/07Baccuracy; các đoạn nói chưa mở implementation bên dưới là checkpoint trước yêu cầu thử nghiệm này. Không mở07Choặc đánh dấuDONE.

Cập nhật sau duyệt dataset-first: [QA/pilot359frame](../reports/task07a-dataset-first-20261105.md) đã sẵn review,257tests PASS. Đã xác minh shared-photo current train/test, không sửa cloud. Hướng dataset-first đã được duyệt; chưa duyệt training/weights/cost và chưa có pilot labels approved. [Guide](../guides/task07a-dataset-label-review.md) là bước tiếp theo. Các đoạn chờ duyệt hướng phía dưới giữ như snapshot trước quyết định.

**Chưa đủ điều kiện mở07B implementation/accuracy acceptance.** [Report07A](../reports/task07a-improvement-checkpoint.md) đã tái lập baseline113/113frame và thử square960/letterbox640, không cấu hình nào vượt candidate baseline41/72. Continuous v4 giữ observed50%, strict control/pass0%; Task07 IN_PROGRESS.

## Artifacts hiện hành

ROOT: `codebase/outputs/task07a-improvement-checkpoint-20261105/`.

- `probe-authorized/`: actual ONNX shapes, preprocessing metadata, default/explicit640 equivalence, source snapshot.
- `controlled-comparison/` + `evaluation/`: baseline và square960,113frames theo lịch cố định, GT chỉ đọc sau inference.
- `letterbox-comparison/` + `letterbox-evaluation/`: cùng640tensor, đổi resize giữ tỷ lệ, inverse coordinate mapping; kết quả regression.
- `roboflow-*-audit.json`, `stratified-size-summary.json`: read-only metadata và geometry samples; không label QA toàn dataset, không xác nhận leakage từ tên file.
- `identity-review-preparation/`:204source crops/context + draft labels;0OCRcalls, chưa reviewed, không OCR accuracy.
- `tests-checkpoint-final.json/log`: regression cuối; xem report/manifest khi nghiệm thu.

## Quyết định tiếp theo

Giữ v4, không promote hai input variants. [Đề xuất dữ liệu/fine-tune](../reports/task07a-data-finetune-proposal.md) cần duyệt hướng dataset-first. Khi đủ dataset QA/split/checkpoint/recipe/cost mới xin chạy training cụ thể. Không hỏi lại roster/ngưỡng/OCR local hoặc hai control confirmations đã chốt.

07B có thể tiếp tục phần source crop review độc lập, nhưng không dùng điều đó để báo end-to-end control/pass đã sẵn sàng. Chưa triển khai Kalman mới, chưa đổi OCR model, chưa khởi động07C. Khi chuyển tiếp, giữ event-time mapping, observed/predicted/missing và zero prediction-only/cut phantom events như contracts.
