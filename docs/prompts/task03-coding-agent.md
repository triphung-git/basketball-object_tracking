# Prompt coding agent — Task03, Automatic Stats v2

Nếu được giao thực hiện liên tục task03 và task04, dùng [prompt chung có checkpoint/report/handoff](task03-task04-coding-agent.md). Prompt hiện tại vẫn dùng khi chỉ triển khai task03.

Bạn là Senior AI/Python Engineer. Thực hiện task03 theo MVP v2 tự động points/rebounds/assists đã được người dùng duyệt ngày 2026-11-02. Task03 là pipeline nền, không phải toàn bộ sản phẩm và không phải scoreboard nhập tay.

## Đọc trước

Đọc AGENTS.md áp dụng nếu có, docs/DEVELOPMENT.md, docs/MVP-v2-proposal.md, PLAN.md, docs/tasks/task03.md, docs/tasks/task04.md, docs/handoffs/task03.md, docs/reports/task01-task02-acceptance.md và code/scripts/tests hiện có. Nguồn hiện hành là v2; tài liệu trong archive chỉ phục vụ truy vết. Không in/đọc .env vào hội thoại.

## Thực hiện

1. Xác minh code/môi trường hiện tại thay vì cài lại từ đầu. Giữ công việc người dùng, dataset và split v1 đã khóa, outputs nghiệm thu.
2. Tạo src/basketball_scoreboard với contracts/config/video/detector/overlay/app; source/scripts/config/tests dưới codebase, docs dưới docs.
3. Tái sử dụng đúng detector đã train, mapping runtime, safeguards checksum/custom-code và compatibility cache Windows. Không thay model hoặc thêm GPU stack tự động.
4. Reader tuần tự với source PTS chuẩn hóa, CFR/VFR, EOF/cleanup/error handling. Clip02 làm integration baseline, không dùng clip04–07 holdout để debug. Với VFR dùng fixture tổng hợp và metadata kỹ thuật, không suy clock từ avg_fps.
5. Detection coords quy về frame gốc; overlay giữ tỷ lệ ngang/dọc, class/confidence/timestamp rõ. Frame không detections vẫn có record.
6. Run directory mới chứa annotated.mp4/detections.jsonl/run.json; không overwrite video gốc/run cũ, không success giả khi lỗi. Manifest notes/labels không là input inference.
7. Baseline offline giữ mọi frame. Ghi full-pipeline time riêng model-call; không dùng skip-frame để che tốc độ CPU và không gọi playback là real-time.
8. Tests đúng rủi ro tọa độ/PTS/empty/errors/cleanup và một integration run thật. Chỉ broaden/repeat khi thay đổi hoặc lỗi mới cần; không benchmark mọi clip nhiều lần.
9. Cập nhật contracts-v2 cho frame/detections, README và báo cáo task03. Event/rule schema ở task04 và event engines ở task08–10; không đòi có sẵn chúng mới hoàn thành reader.

## Quyền và câu hỏi

Tự động PRA đã duyệt, không hỏi lại có muốn tự động hay không. Được kiểm tra/sửa bug thông thường trong task. Nếu cần model/backend/dependency lớn mới, GPU stack, cloud/chi phí/upload, thay locked data hoặc đổi scope, giải thích vấn đề và hỏi trước phần phụ thuộc. Secrets chỉ đọc cục bộ bởi code; dùng cơ chế xin quyền của công cụ khi sandbox/network bị chặn, không tìm cách né quyền.

## Nghiệm thu và trả kết quả

Làm đầy đủ checklist task03: chạy hết clip02, đọc lại video, timestamps/coords đúng, errors/cleanup rõ, output metadata và measured throughput. Không thêm form nhập stats rồi tuyên bố automatic PRA đã hoàn thành.

Cuối lượt báo tiếng Việt: DONE/IN_PROGRESS dựa evidence; file/output paths; commands/tests; runtime và tốc độ thực; lỗi/giới hạn; contract bàn giao task04–07. Không coi 31 tests baseline cũ là tests cho code mới nếu chưa chạy kiểm tra liên quan.
