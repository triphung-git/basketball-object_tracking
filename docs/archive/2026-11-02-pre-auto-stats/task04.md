# Task04 — Tracking và vùng rổ

Trạng thái: TODO. Dự kiến: ngày 3. Phụ thuộc: task03.

## Mục tiêu

Tạo chuỗi chuyển động bóng đáng tin cậy và ID người tạm thời; cố định hình học vùng rổ cho scoring.

## Bạn cần thực hiện

Chọn/kiểm tra vùng vành rổ trên frame mẫu; xác nhận vùng phía trên/dưới không nhầm bảng rổ. Chỉ ra clip có che khuất hoặc bóng gây nhiễu.

## Tôi sẽ xây dựng

1. Tracking người bằng ByteTrack với dependency/API tương thích đã khóa; reset tracker khi đổi video.
2. Theo dõi bóng bằng khoảng cách tới vị trí dự báo, vận tốc và giới hạn tốc độ hợp lý theo thời gian; không dùng một ID bóng như danh tính vĩnh viễn.
3. Lưu quỹ đạo có timestamp, confidence, trạng thái observed/predicted. Chỉ thêm Kalman nếu baseline cần và có cải thiện đo được.
4. Giới hạn khoảng mất dấu; hết hạn thì reset, không nối hai đoạn xa tùy tiện. Khi nhiều ứng viên mơ hồ, ghi trạng thái không chắc chắn.
5. Công cụ chọn ROI rổ một lần, có detection `rim` gợi ý; lưu tọa độ chuẩn hóa và độ phân giải tham chiếu.
6. Tạo vùng trên/vành/dưới dựa vào kích thước ROI; hiển thị đường bóng, ID và các vùng để debug.

## Đầu ra

- `tracking.py`; cấu hình ROI trong `configs/`.
- Video debug và log quỹ đạo có phân biệt quan sát/dự báo.
- `docs/reports/tracking.md`: tham số, lỗi đổi ID/mất bóng, lý do dùng hoặc bỏ Kalman.

## Nghiệm thu

- [ ] ID người được duy trì trong đoạn quan sát liên tục; ghi nhận ID có thể đổi khi khuất lâu.
- [ ] Không nối quỹ đạo bóng qua khoảng mất dấu vượt giới hạn.
- [ ] Dự đoán không được ghi giả thành detection quan sát.
- [ ] ROI tải lại đúng và đổi về tọa độ frame chính xác; đổi camera phải cấu hình lại.
- [ ] Debug clip cho thấy trạng thái đủ rõ để rà soát scoring ở task05.

## Giới hạn và bàn giao

Tracking người phục vụ minh họa, không gán người ghi điểm. Task05 dùng quan sát bóng, timestamp và hình học ROI; không phụ thuộc ID người hay việc tracker bóng luôn giữ nguyên ID.
