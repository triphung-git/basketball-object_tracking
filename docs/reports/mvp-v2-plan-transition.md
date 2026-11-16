# Chuyển phạm vi sang Automatic Stats v2 — 2026-11-02

## Quyết định đã nhận

Người dùng yêu cầu phiên bản tự nhận diện đầy đủ points/rebounds/assists và duyệt MVP v2 để lập plan tiếp theo. Manual-entry/duyệt từng pha không còn là điều kiện để sinh stats; corrections chỉ audit riêng. Giữ các điều kiện MP4 3x3 một rổ, camera ổn định và offline-first của MVP được duyệt. Chưa có cam kết độ chính xác gần100% mọi video hoặc throughput live.

## Các tài liệu đã cập nhật

- [MVP đã duyệt](../MVP-v2-proposal.md): thay Assisted Stats bằng automatic engines bắt buộc và strict evaluation.
- [PLAN v2](../../PLAN.md): architecture, task03–15, dependencies, inputs, gates, quality protocol và ước lượng 32–52 ngày công (7–11 tuần nếu làm 5 ngày/tuần, chưa tính chờ data/train thêm).
- [Task index](../tasks/README.md): task01–02 DONE baseline; 13 task tiếp theo TODO, mỗi task có user inputs, implementation, artifacts, tests, acceptance và blockers.
- [Handoff task03](../handoffs/task03.md), [prompt task03](../prompts/task03-coding-agent.md): điểm vào triển khai mới.
- DEVELOPMENT, README và các prompt baseline có thông báo scope/version, tránh agent dùng kế hoạch cũ.
- [Archive](../archive/2026-11-02-pre-auto-stats/README.md): giữ nguyên snapshots plan cũ, đề xuất assisted, task03–08 cũ và handoff cũ.

## Các thứ không bị thay đổi

Source Python, runtime/packages, model weights, .env, video gốc, dataset v1/labels/reviews/coverage/splits, outputs và bằng chứng nghiệm thu task01–02. Các đường dẫn module v2 trong plan là thiết kế, chưa phải implementation.

Approval sản phẩm không tự cho phép chuyển holdout v1 sang calibration, thêm chi phí/cloud upload hoặc cài GPU stack. Các quyết định đó vẫn cần chốt cụ thể khi có bằng chứng.

## Việc còn thiếu trước các gate chất lượng

Footage phát triển hai đội mới; roster/jersey đủ nhìn; GT control/pass/shooter/rebound/assist và hard negatives; rule profile có nguồn/phiên bản; split v2 và protocol đánh giá khóa trước holdout. Clip02 và 10 shot labels cũ đủ bắt đầu reader/detection nhưng chưa đủ nghiệm thu automatic PRA.

Task03 có thể bắt đầu ngay với đầu vào hiện có; công cụ/thu thập task04 không cần chờ pipeline xong. Chỉ lập plan trong lượt này, chưa bắt đầu triển khai task03.

## Kiểm tra tài liệu sau cập nhật

- Kiểm tra 32 tài liệu hiện hành và archive index: không có local link hỏng.
- Task03–15: đủ 13 file, mỗi file có mục tiêu, user inputs, implementation, outputs, acceptance, tests, rủi ro và handoff.
- Đối chiếu 6 fingerprint dataset v1 trong snapshot nghiệm thu: không đổi.
- Không chạy lại tests Python/model vì lượt này chỉ đổi Markdown; không dùng kết quả 31 tests lịch sử để tuyên bố code v2 đã được kiểm thử.
