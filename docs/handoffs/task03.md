# Bàn giao task03 — Pipeline nền cho Automatic Stats v2

Cập nhật: 2026-11-02. **ACTIVE**. Bản handoff scoreboard cũ ở archive. [MVP đã duyệt](../MVP-v2-proposal.md), [PLAN](../../PLAN.md), [task03](../tasks/task03.md) và [task04](../tasks/task04.md) là nguồn hiện hành.

## Trạng thái

Task01/model runtime và task02/dataset shot pilot đã nghiệm thu. Chưa có automatic PRA hoặc pipeline app hoàn chỉnh. Lượt lập plan không thay code, dữ liệu/nhãn/split đã khóa hoặc package/runtime.

Python codebase/.venv/Scripts/python.exe (3.12.14), inference-models 0.39.7, ONNX CPU; detector phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1. Mapping phải lấy từ runtime, baseline là 0 ball/1 human/2 rim. Cache cần compatibility Windows và có thể cần auth metadata qua mạng; hoàn toàn offline chưa được nghiệm thu.

## Điểm vào triển khai

1. Đọc DEVELOPMENT, MVP và PLAN, task03, reports/task01-task02-acceptance.md; đọc code reader/smoke/validator, không đọc .env vào chat.
2. Xây src/basketball_scoreboard/{contracts,config,video,detector,overlay,app}.py và CLI chạy MP4.
3. Clip02 20521993-uhd_2160_3840_60fps.mp4 là baseline reader/detection: 2160×3840, 60 FPS, 1089 frames, 18,15s. Chạy đủ frame; CPU chậm được chấp nhận cho baseline offline.
4. VFR hỗ trợ bằng PTS thật, không frame_index/avg_fps. Clip04–07 đã kiểm tra packet PTS biến thiên nhưng vẫn giữ holdout; phát triển reader VFR bằng fixture tổng hợp, không inference holdout để debug.
5. Tạo run mới: annotated.mp4, detections.jsonl, run.json. Không overwrite artifacts cũ, không completed khi writer/model thất bại.
6. Task03 chỉ định nghĩa frame/detection contracts; task04 chốt schema identity/possession/events/rules/evaluation. Không có vòng phụ thuộc yêu cầu mọi event engine đã tồn tại để reader hoàn thành.

## Contract tối thiểu

Frame: video_id, frame_index zero-based, normalized source_time_s, original_wh, source PTS/time_base khi có. Detection: xyxy ở frame gốc, class_id/name/confidence. Empty detections vẫn có frame record.

Run metadata: input fingerprint, source/export timebase, model/runtime/config/versions, counts, timings và trạng thái. Input inference chỉ path/metadata kỹ thuật; không dùng event labels hoặc manifest notes chứa kết quả.

Đo model-call và full pipeline riêng. Event engines phía sau cần causal timestamps và observed/predicted distinction; không tự thêm skip-frame hoặc đọc tương lai vô hạn để giả real-time.

## Dữ liệu và scope v2

Task04 cần footage calibration hai đội và GT control/pass/shot/rebound/assist/identity mới. Dataset cũ 10 shot labels chưa đủ cho automatic stats. Giữ data/ và split v1; version v2 ở data/v2/, chỉ thay locked data khi có revision người dùng duyệt.

Thiết kế mọi module mới hướng tới tự nhận diện đủ PRA. Không xây scoreboard nhập tay làm sản phẩm thay thế. Nhưng task03 chưa phải nơi implement points/rebounds/assists; chúng ở task08–10 và là điều kiện nghiệm thu cuối.

## Xác minh và bàn giao

- Run đủ clip02, đọc lại video, đối chiếu frame counts/shape/PTS.
- Tests cần thiết cho CFR/VFR, coordinate resize, empty/model/writer errors và cleanup.
- Cập nhật docs/specs/contracts-v2.md, README và reports/task03-pipeline.md.
- Không claim FPS nguồn hoặc accuracy scoring từ detection smoke.
- Sau task03, triển khai geometry task05 và tiếp tục dataset/rules task04; chỉ tiến các gate còn lại khi đủ đầu vào.

[Prompt thực hiện task03](../prompts/task03-coding-agent.md).

Nếu nhận phạm vi cả task03–04: [prompt thực hiện xuyên suốt](../prompts/task03-task04-coding-agent.md), yêu cầu tạo report/handoff G03 trước khi kết luận G04.
