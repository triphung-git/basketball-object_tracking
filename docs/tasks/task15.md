# Task15 — Đóng gói, tái chạy và nghiệm thu MVP v2

Kiểm thử lại 2026-11-10: [acceptance report](../reports/demo-completion-acceptance-20261110.md). **IN_PROGRESS; chưa nghiệm thu.** Runner chỉ replay cache, xử lý 5/10 reviewed windows và thành công với missing video; bundle còn thiếu.

**Version: MVP v2 Automatic Stats, 2026-11-02. Trạng thái: IN_PROGRESS.**
Ước lượng: 1–2 ngày công (không bao gồm chờ đầu vào nếu có). Phụ thuộc: Task13 quality gate và task14 performance decision; tất cả engines/core artifacts hoàn thành.

## Mục tiêu

Bàn giao sản phẩm tự động PRA + heatmap có thể tái lập và đánh giá đúng phạm vi đã duyệt.

Nguồn phạm vi: [MVP đã duyệt](../MVP-v2-proposal.md), [PLAN v2](../../PLAN.md), [chỉ mục](README.md). Đọc DEVELOPMENT và contracts/rules v2 khi được tạo. Task01–02 chỉ là baseline đã nghiệm thu.

## Bạn cần cung cấp / xác nhận

- Chạy theo hướng dẫn trên máy mục tiêu, xác nhận quyền chia sẻ video demo và yêu cầu báo cáo học phần nếu có.
- Chỉ phê duyệt chất lượng dựa trên evidence; không cần nhập sự kiện để tạo demo tự động.

## Agent sẽ xây dựng

1. Hoàn thiện README/setup/config mẫu, dependency lock đã test, key cục bộ, roster/court/rules và input constraints.
2. Chạy acceptance từ môi trường sạch hoặc tái tạo tương đương; ghi nếu không có máy thứ hai, kiểm tra metadata/weights auth và offline caveat.
3. Demo không nhập/sửa stats: video→identity/control→tự points/rebounds/assists→heatmap/boxscore→exports. Audit/correction trình diễn riêng.
4. Đóng gói output bundle, raw metrics và report chỉ rõ dataset/version/test exposure, unknowns, lỗi và runtime limits.
5. Rà soát secrets/media/path cá nhân, scripts không upload/charge tự động; không tự commit/push/publish.
6. Cập nhật task status: không đánh dấu toàn bộ DONE nếu một stat chưa đạt hoặc thiếu chất lượng gate; acceptance checklist phân biệt implemented, measured và passed.

## Đầu ra bắt buộc

- README và docs/user-guide-v2.md; docs/reports/final-report-v2.md và acceptance-v2.md.
- Source/config/tests/dependency lock, demo video, heatmaps, auto box score/events/metrics và run snapshot mẫu.

Các đường dẫn code/config/output tương đối với codebase trừ docs/. Đây là thiết kế để triển khai, không phải file/tính năng đã hoàn thành. Mỗi run có versions/config/fingerprints và evidence, không có API key.

## Nghiệm thu

- [ ] Người khác theo README tái chạy được input phù hợp và tìm đủ artifacts.
- [ ] Cả ba stats tự nhận diện trên demo/evaluation trước correction; không chỉ là nút nhập tay hay candidate cần người duyệt.
- [ ] Có quality/performance evidence đúng protocol, giới hạn ngoài scope rõ; không tuyên bố gần100%/real-time nếu chưa đạt.

## Kiểm thử cần thiết

- Một end-to-end clean-run và artifact/schema/link checks cần thiết.
- Lệnh setup/CLI/documentation đúng, resume/reload mẫu không thay totals.
- Required suite/regression đã pass sau các thay đổi cuối; không chạy lặp vô hạn khi không có thay đổi mới.

Không dùng synthetic fixtures như dữ liệu thật, không dùng labels/manifest notes làm oracle recognition. Calibration/test v2 phải tách nhóm; labels/split v1 đã khóa được giữ nguyên. Chỉ test phù hợp thay đổi và integration evidence cần thiết, không benchmark lặp không có lý do.

## Rủi ro và điều kiện dừng phần phụ thuộc

Nếu thiếu model/data/runtime hoặc gate quality chưa pass, bàn giao partial kèm việc còn thiếu; không đổi định nghĩa MVP sau khi demo.

Không cần hỏi lại có làm automatic PRA hay không: đã duyệt. Hỏi trước các thay đổi model/backend/dependency lớn, GPU stack, chi phí/cloud upload, dataset locked hoặc scope; tiếp tục phần độc lập trong khi chờ. Không xem im lặng là đồng ý. Không thay engine tự động bằng thao tác nhập/duyệt tay để đánh dấu DONE.

## Bàn giao

MVP v2 nghiệm thu hoặc báo cáo chưa đạt có căn cứ; yêu cầu 5x5/camera động/live bất kỳ là roadmap riêng.

Khi kết thúc, cập nhật task này và report với file paths, lệnh đã chạy, số liệu thật, điều kiện chưa đạt và bước tiếp theo. Chỉ chuyển DONE khi checklist có bằng chứng; sửa tay không thay automatic metrics.
