# Rule profile v2 — DRAFT, chờ chốt áp dụng cho giải

Ngày rà soát: 2026-11-02. Người dùng đồng ý sửa diễn giải sai và bàn giao công cụ trong khi chờ dữ liệu/rules. Việc này chưa phải duyệt toàn bộ rule profile.

## Nguồn và phạm vi

- [FIBA Statisticians’ Manual 2024, v1.0](https://assets.fiba.basketball/image/upload/documents-corporate-fiba-statisticians-manual-2024.pdf), mục 4 (rebounds), 6.1 (assists); truy cập 2026-11-02. Đây là phiên bản tham chiếu cụ thể, chưa khẳng định là tài liệu mới nhất hoặc tự động áp dụng toàn bộ cho giải 3x3.
- [FIBA — 3x3 Basketball](https://about.fiba.basketball/en/our-sport/3x3-basketball), truy cập 2026-11-02: giá trị ném trong cung/ngoài cung/FT là 1/2/1.

**Sửa lỗi:** Manual 2024 cho phép tính assist khi người nhận chuyền bị phạm lỗi trong động tác ném và thực hiện thành công ít nhất một FT, nếu thỏa điều kiện assist tương ứng. Câu “FIBA không tính assist dẫn đến FT” đã bị loại bỏ. Số lần dẫn bóng hay một lần bóng bị chạm không đủ để quyết định mọi trường hợp; phải xét toàn diễn biến theo mục 6.1. [Nguồn trực tiếp](https://assets.fiba.basketball/image/upload/documents-corporate-fiba-statisticians-manual-2024.pdf).

## Profile đề xuất cho MVP

Bảng dưới là **case matrix cần review theo giải**, chưa phải rule engine đã triển khai hoặc labels đã được duyệt.

| Nhóm | Positive candidate | Negative control | Chờ bằng chứng/quyết định |
|---|---|---|---|
| Points | Bóng vào rổ hợp lệ, shooter và vị trí release xác định | Miss, replay cùng pha | Góc quay mất release, chân sát cung, quyết định trọng tài |
| Rebound | Sau miss, có kiểm soát bóng hoặc controlled tip được xác minh | Chạm bóng đơn thuần, nhặt bóng sau made | Team rebound, bóng chết, FT cuối/không cuối, retained possession |
| Assist | Pass trực tiếp tạo cơ hội ghi điểm, liên kết scorer/shot rõ | Pass trước pha tự tạo cơ hội hoặc không dẫn đến điểm | Paint/dribble/deflection; shooting foul và FT; giới hạn mỗi pha |
| Identity | Cầu thủ và team có evidence roster/áo/track | Nearest player khi bị che khuất | Track đứt, số áo không thấy, người ngoài sân |

Không dùng khoảng N giây làm định nghĩa assist. Thời gian matching của evaluator là tolerance đo lường, không phải luật thống kê. Không dùng “gần bóng nhất” thay bằng chứng control.

## Quyết định cần chốt trước freeze

1. Giải/trận nào, tài liệu thống kê và phiên bản áp dụng, người duyệt.
2. Case matrix rebound/assist gồm FT, controlled tip, dead ball, deflection và các ca không quan sát đủ.
3. Cách mã hóa FT series, foul→pass→FT và control/possession refs. Schema hiện có notes để lưu evidence draft; cần extension có kiểu trước khi đưa các ca này vào benchmark chính thức.
4. Chính sách uncertain: giữ riêng để audit; không biến thành negative hoặc xóa lỗi nhận diện tự động.

`codebase/data/v2/ruleset.json` đang `review_status=draft`, `applicability_status=pending`, `protocol_status=draft`, `roster_status=pending`. Chưa có quyền đổi thành approved/confirmed chỉ vì tools chạy pass.
