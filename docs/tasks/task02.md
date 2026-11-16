# Task02 — Video, nhãn sự kiện và tập đánh giá

> Dataset shot pilot v1 đã nghiệm thu và giữ khóa. [Task04 v2](task04.md) sẽ bổ sung identity/control/pass/rebound/assist/rules riêng; không coi 10 nhãn cũ là đủ nghiệm thu PRA tự động. Xem [PLAN hiện hành](../../PLAN.md).

Trạng thái: **DONE — bộ dữ liệu pilot**, nghiệm thu 2026-11-01. Manifest có 7 video, 10 nhãn approved theo reviews.csv, 0 draft; split `1.0.0-locked`. Không thay đổi nhãn hoặc split trong đợt nghiệm thu. Xem [báo cáo nghiệm thu](../reports/task01-task02-acceptance.md). Dự kiến: ngày 1–2. Phụ thuộc: task01.

## Mục tiêu

Có dữ liệu đại diện và ground truth để đánh giá ghi điểm độc lập với cảm nhận demo.

## Bạn cần thực hiện

- Cung cấp MP4 thấy rõ bóng trước và sau khi qua vành; giữ camera cố định và không đổi zoom trong clip. -> [x] Đã bổ sung 4 video test độc lập (`clip04` đến `clip07`).
- Ưu tiên 50–100 lượt tổng cộng, gồm vào, trượt, bật vành, che khuất và người đi ngang. Hiện có 10 lượt (6 made, 4 miss); đây là pilot nhỏ, chưa đạt mục tiêu thu thập, không phải điều kiện chặn triển khai.
- Xem và gán nhãn thủ công: khoảng thời gian lượt ném, kết quả và thời điểm vào; đánh dấu `uncertain` khi hình ảnh không đủ kết luận. Xem [ANNOTATION_GUIDE.md](../data/ANNOTATION_GUIDE.md). -> [x] Cả 10 nhãn đã có review_status=approved trong ledger hiện tại.
- Nếu dùng A/B hoặc thay đổi giá trị điểm, ghi đội và giá trị của từng lượt. -> [x] Đã cấu hình A (Hà Nội, trắng) / B (TP.HCM, xanh) và điểm 1/2 theo vạch 3x3.

## Tôi sẽ thực hiện

1. Tạo manifest video: tên, FPS, độ phân giải, thời lượng, camera/session và điều kiện quay (`prepare_dataset.py`). -> [x] Đã hoàn thành (7 video).
2. Cung cấp mẫu annotation và hướng dẫn định nghĩa thời điểm vào: lúc bóng đi qua mặt phẳng vành theo bằng chứng thấy được; ghi sai số khi phải ước lượng. -> [x] Đã hoàn thành tại `docs/data/ANNOTATION_GUIDE.md`.
3. Chia calibration/test theo clip hoặc buổi quay, ưu tiên khoảng 70/30 khi đủ dữ liệu; không chia frame liền nhau ngẫu nhiên. Cân bằng tình huống nếu khả thi. -> [x] Đã phân chia trong `codebase/data/splits.json` (`clip02` calibration, `clip04`–`clip07` test độc lập).
4. Kiểm tra schema, timestamp ngoài thời lượng, ID trùng và video thiếu. Chốt test set trước chỉnh rule. -> [x] Validator kiểm tra media hashes, manifest/events/coverage lock, review ledger, coverage và leakage. Kết quả test hiện tại nằm trong báo cáo nghiệm thu.
5. Chọn ví dụ dễ/khó để regression và báo cáo; không đưa clip test vào vòng chỉnh ngưỡng. -> [x] Đã phân tích chi tiết trong `docs/reports/data.md`.

## Đầu ra

- `data/manifest.csv`, `data/splits.json`.
- `data/annotations/events.csv` (10 nhãn approved), `data/annotations/events.draft.csv` (header-only, 0 draft).
- `data/annotations/reviews.csv` (sổ theo dõi trạng thái rà soát).
- `data/annotations/coverage.csv` (định nghĩa khoảng thời gian đánh giá và loại trừ cho cả 7 clip).
- `docs/data/ANNOTATION_GUIDE.md`: Hướng dẫn gán nhãn, schema và timebase.
- `docs/reports/data.md`: số clip, số lượt từng loại, cách chia và thiếu hụt.

## Nghiệm thu

- [x] Đọc được video và nhãn; timestamp dùng giây theo nguồn video stream.
- [x] Toàn bộ dữ liệu có 6 made, 4 miss; riêng test có 4 made, 3 miss.
- [x] Test set tách khỏi calibration theo nhóm nguồn độc lập; ghi rõ cỡ mẫu và giới hạn trong `splits.json` và `docs/reports/data.md`.
- [x] Đối chiếu 10 review approved và split đã khóa với fingerprint hiện tại. Nghiệm thu theo ledger đã bàn giao; không tạo hoặc sửa xác nhận của người dùng.

## Bàn giao

Task03/05 dùng calibration (`clip02`); task07 dùng test set (`clip04`–`clip07`) đã khóa, cùng một session. Không dùng holdout để sửa rule. Clip04–07 có PTS biến thiên: đọc presentation timestamps thay vì frame_index / avg_fps. Xem [bàn giao task03](../handoffs/task03.md). Không tuyên bố đã đạt độ chính xác hoặc real-time từ dữ liệu pilot này.

