# Task13 — Đánh giá end-to-end và nghiệm thu tự động PRA

Kiểm thử lại 2026-11-10: [acceptance report](../reports/demo-completion-acceptance-20261110.md). **IN_PROGRESS; chưa nghiệm thu.** Chỉ có diagnostics; production matching chưa đạt và strict PRA evaluation chưa khả dụng.

**Version: MVP v2 Automatic Stats, 2026-11-02. Trạng thái: IN_PROGRESS.**
Ước lượng: 3–4 ngày công (không bao gồm chờ đầu vào nếu có). Phụ thuộc: Task04–12; frozen labels/split/protocol và config/model versions.

## Mục tiêu

Đo đúng khả năng tự động của từng stat trước sửa tay, không chỉ chứng minh app chạy hoặc tổng points trùng.

Nguồn phạm vi: [MVP đã duyệt](../MVP-v2-proposal.md), [PLAN v2](../../PLAN.md), [chỉ mục](README.md). Đọc DEVELOPMENT và contracts/rules v2 khi được tạo. Task01–02 chỉ là baseline đã nghiệm thu.

## Bạn cần cung cấp / xác nhận

- GT holdout đã duyệt, metadata source/session, quyền đánh giá; người rà soát độc lập các case mơ hồ theo protocol.
- Nếu test trước đã ảnh hưởng thiết kế, cung cấp/duyệt reserve mới thay vì gọi lại là blind holdout.

## Agent sẽ xây dựng

1. evaluate_v2.py matching một-một theo protocol task04; explicit actor/value/subtype/link matching, tie và duplicate handling.
2. Báo per-stat event-only và strict TP/FP/FN/P/R/F1; N/A khi denominator0, không báo100% giả.
3. Sai actor/value/subtype là attribution failure và strict FP/FN; unknown/unresolved trên GT hợp lệ đi vào missed/coverage.
4. Báo score/team/player totals, initial offset, ID switches/fragmentation, ball/control, heatmap/location và no-event false positives.
5. Giữ automatic logs immutable; corrected results riêng. Ghi sample size, session dependence, uncertainty và lý do excluded trước test.
6. Error analysis trên holdout không được biến thành tuning rồi báo pass cùng test; lập calibration fixes/reserve evaluation version mới nếu cần.

## Đầu ra bắt buộc

- scripts/evaluate_v2.py; metrics.json, matched_events.csv, error index và config/dataset fingerprint snapshots.
- docs/reports/evaluation-v2.md và acceptance matrix mỗi component/PRA.

Các đường dẫn code/config/output tương đối với codebase trừ docs/. Đây là thiết kế để triển khai, không phải file/tính năng đã hoàn thành. Mỗi run có versions/config/fingerprints và evidence, không có API key.

## Nghiệm thu

- [ ] Cả points/rebounds/assists có labels và predicted events thật; target mỗi stat P≥95%, R≥90% theo protocol trước test.
- [ ] Metrics reproduce được, không dùng corrected totals thay auto. Báo chưa đạt nếu một stat thất bại hoặc thiếu GT.
- [ ] Heatmap/team/identity metrics và footage limitations minh bạch; không suy cỡ mẫu nhỏ thành gần100% mọi trận.

## Kiểm thử cần thiết

- Matching one-to-one, duplicate predictions, wrong actor/value/link, unknown và empty sets.
- Ignored/uncertain intervals, background FP, PTS tolerance edges và session-level summaries.
- Tái tính metrics từ raw outputs và independent hand-check sample; data/model/config hash consistency.

Không dùng synthetic fixtures như dữ liệu thật, không dùng labels/manifest notes làm oracle recognition. Calibration/test v2 phải tách nhóm; labels/split v1 đã khóa được giữ nguyên. Chỉ test phù hợp thay đổi và integration evidence cần thiết, không benchmark lặp không có lý do.

## Rủi ro và điều kiện dừng phần phụ thuộc

Nếu không đạt, gate G4 chưa pass; báo loại lỗi và plan calibration mới, không tự hạ mục tiêu hoặc sửa nhãn test.

Không cần hỏi lại có làm automatic PRA hay không: đã duyệt. Hỏi trước các thay đổi model/backend/dependency lớn, GPU stack, chi phí/cloud upload, dataset locked hoặc scope; tiếp tục phần độc lập trong khi chờ. Không xem im lặng là đồng ý. Không thay engine tự động bằng thao tác nhập/duyệt tay để đánh dấu DONE.

## Bàn giao

Baseline quality + immutable outputs cho task14; reserve policy và final acceptance inputs cho task15.

Khi kết thúc, cập nhật task này và report với file paths, lệnh đã chạy, số liệu thật, điều kiện chưa đạt và bước tiếp theo. Chỉ chuyển DONE khi checklist có bằng chứng; sửa tay không thay automatic metrics.
