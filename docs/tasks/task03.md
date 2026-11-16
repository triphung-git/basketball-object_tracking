# Task03 — Pipeline video, PTS và detection nền v2

**Version: MVP v2 Automatic Stats, 2026-11-02. Trạng thái: DONE.**
Ước lượng: 1–2 ngày công (không bao gồm chờ đầu vào nếu có). Phụ thuộc: Task01; clip02 phát triển. Task04 có thể tiến hành công cụ/thu thập độc lập.

## Mục tiêu

Đọc hết video và tạo detections/timebase đáng tin cậy làm nền cho automatic stats. Chưa thêm tracking/scoring vào reader.

Nguồn phạm vi: [MVP đã duyệt](../MVP-v2-proposal.md), [PLAN v2](../../PLAN.md), [chỉ mục](README.md). Đọc DEVELOPMENT và contracts/rules v2 khi được tạo. Task01–02 chỉ là baseline đã nghiệm thu.

## Bạn cần cung cấp / xác nhận

- Giữ key cục bộ và video phát triển có quyền dùng; không cần cung cấp lại key trong chat.
- Clip02 hiện có đủ để bắt đầu; không lấy clip04–07 holdout làm mẫu tuning.

## Agent sẽ xây dựng

1. Đọc lại DEVELOPMENT, MVP đã duyệt, plan, smoke loader và safeguards Windows; tái sử dụng loader, không tắt hash/TLS hoặc đổi detector.
2. Tạo video/config/contracts/detector/overlay/app dưới src/basketball_scoreboard. Frame record có video_id, index, normalized source_time_s, original_wh; detections có xyxy ở frame gốc, class_id/name/confidence.
3. Reader decode tuần tự qua decoder timestamp hiện có; xử lý CFR/VFR, missing/non-monotonic PTS, EOF và cleanup. Frame không detection vẫn có record.
4. Giữ tỷ lệ resize, kiểm tra class mapping runtime và bbox/schema; snapshot model/backend/config/versions. Không đọc notes/GT để recognition.
5. CLI tạo run directory mới, MP4 overlay + JSONL + metadata status; lỗi input/model/writer không tạo completed giả. Mặc định không dùng test split để development.
6. Giữ tất cả frame baseline offline. Export CFR giữ nhịp nội dung; hỗ trợ VFR phải preserve/resample có mapping rõ, không lấy avg_fps làm clock.

## Đầu ra bắt buộc

- src/basketball_scoreboard/{app,config,contracts,video,detector,overlay}.py; configs/default.yaml.
- outputs/acceptance-20261102/g03-clip02-verified/{annotated.mp4,detections.jsonl,run.json}; independent readback audit, docs/reports/task03-pipeline.md và CLI thực tế trong README. Giữ outputs/task03-clip02-full như run lịch sử, không trộn metrics giữa các run.

## Nghiệm thu

- [x] Chạy hết clip02 (1089/1089 frames), mở lại MP4 độc lập, đối chiếu frame count/shape/timestamp; JSON/overlay cùng hệ tọa độ [Báo cáo](../reports/task03-pipeline.md).
- [x] CFR/VFR fixture gồm export/readback, missing/frame-timebase PTS, empty detections, runtime mapping, init/writer failure và holdout hash; bộ kiểm thử chung 92 tests pass, xem report và logs.
- [x] Đo throughput toàn pipeline và model-call riêng cho từng run. 4.52 FPS là run lịch sử trước sửa lỗi, không đại diện code hiện tại; số đo mới tại report. Chưa đạt real-time.

## Kiểm thử cần thiết

- VFR fixture với PTS không đều, đảo/trùng/missing PTS có policy rõ.
- Ảnh ngang/dọc qua resize; empty detections; lỗi writer/EOF giải phóng handles.
- Một integration run thật trên clip02, không benchmark lặp vô ích.

Không dùng synthetic fixtures như dữ liệu thật, không dùng labels/manifest notes làm oracle recognition. Calibration/test v2 phải tách nhóm; labels/split v1 đã khóa được giữ nguyên. Chỉ test phù hợp thay đổi và integration evidence cần thiết, không benchmark lặp không có lý do.

## Rủi ro và điều kiện dừng phần phụ thuộc

Nếu đúng model không load được, xác minh lỗi/quyền rồi hỏi trước đổi runtime/model. Chưa cài GPU stack. Contract phải ổn trước task05–10.

Không cần hỏi lại có làm automatic PRA hay không: đã duyệt. Hỏi trước các thay đổi model/backend/dependency lớn, GPU stack, chi phí/cloud upload, dataset locked hoặc scope; tiếp tục phần độc lập trong khi chờ. Không xem im lặng là đồng ý. Không thay engine tự động bằng thao tác nhập/duyệt tay để đánh dấu DONE.

## Bàn giao

Frame/detection records và run config cho task05–07; sơ đồ artifact/timebase ghi trong docs/specs/contracts-v2.md.

Khi kết thúc, cập nhật task này và report với file paths, lệnh đã chạy, số liệu thật, điều kiện chưa đạt và bước tiếp theo. Chỉ chuyển DONE khi checklist có bằng chứng; sửa tay không thay automatic metrics.
