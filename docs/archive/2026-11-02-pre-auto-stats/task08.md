# Task08 — Đóng gói, demo và báo cáo

Trạng thái: TODO. Dự kiến: ngày 7. Phụ thuộc: task07.

## Mục tiêu

Bàn giao dự án sinh viên có thể chạy lại, trình diễn và giải thích bằng số liệu.

## Bạn cần thực hiện

- Cung cấp yêu cầu định dạng báo cáo của môn học nếu có; mặc định bàn giao Markdown.
- Chạy theo README trên máy mục tiêu, kiểm tra demo và xác nhận ground truth.
- Chọn clip có quyền chia sẻ; tự thực hiện việc nộp hoặc công khai dự án.

## Tôi sẽ thực hiện

1. Hoàn thiện README: mục tiêu, phạm vi, cấu trúc, dependency, cài đặt, cấu hình key cục bộ, chọn ROI, chạy MP4/webcam, phím, đầu ra và troubleshooting.
2. Cung cấp config mẫu không bí mật; khóa phiên bản đã kiểm thử, quy định bỏ qua video lớn, outputs, environment và key trong Git.
3. Smoke test từ môi trường sạch hoặc môi trường tái tạo tương đương; ghi rõ nếu không thể kiểm tra máy thứ hai. Không chỉ dựa vào môi trường phát triển đang có.
4. Chuẩn bị demo ngắn: chọn ROI → detection/tracking → lượt vào/trượt → scoreboard → undo → log. Kèm ít nhất một lỗi/giới hạn điển hình và cách nhận biết.
5. Viết báo cáo: bài toán, dataset/model, kiến trúc, state machine, kết quả detection được cung cấp so với metrics sự kiện tự đo, benchmark, hạn chế và hướng phát triển.
6. Rà soát không có API key/đường dẫn riêng bắt buộc; không tự publish, tạo workflow hay đưa video lên dịch vụ khác.
7. Cập nhật trạng thái từng task và bảng yêu cầu đạt/chưa đạt, nêu điều kiện để hoàn thiện phần còn thiếu.

## Đầu ra cuối

- Source code, dependency, config và README có lệnh chạy thực tế.
- `docs/reports/final-report.md`, evaluation/performance report và sơ đồ luồng.
- Video demo/annotated, events, adjustments, scoreboard và run metadata mẫu.
- `docs/reports/acceptance.md`: checklist, bằng chứng, hạn chế và việc còn lại.

## Nghiệm thu

- [ ] Người dùng làm theo README có thể tái chạy clip mẫu và tìm được đầu ra.
- [ ] Demo thể hiện detection, tracking, scoring và thao tác sửa; không che giấu mức tự động hóa.
- [ ] Số liệu báo cáo khớp file metrics; live/offline được mô tả đúng bằng chứng.
- [ ] Không chứa secrets; video chia sẻ phù hợp quyền sử dụng.
- [ ] Tất cả yêu cầu bắt buộc được kiểm tra; phần không đạt có ghi chú rõ thay vì đánh dấu hoàn tất.

## Sau MVP

Chỉ xem xét tự phân loại 1/2/3 điểm, nhận đội, attribution người ném, camera di chuyển hoặc web dashboard sau khi có baseline và thời gian bổ sung. Các hạng mục này không được làm trễ bàn giao cốt lõi.
