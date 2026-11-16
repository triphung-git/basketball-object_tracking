# Task10 — Assists tự động theo rule profile

Kiểm thử lại 2026-11-10: [acceptance report](../reports/demo-completion-acceptance-20261110.md). **IN_PROGRESS; chưa nghiệm thu.** Module có tests nhưng thiếu receiver/pass/action/cut guards, chưa nối demo thực.

**Version: MVP v2 Automatic Stats, 2026-11-02. Trạng thái: IN_PROGRESS.**
Ước lượng: 3–5 ngày công (không bao gồm chờ đầu vào nếu có). Phụ thuộc: Task04, task06–09.

## Mục tiêu

Tự xác định người chuyền được assist và liên kết score hợp lệ, có phân biệt pass cuối không đủ điều kiện.

Nguồn phạm vi: [MVP đã duyệt](../MVP-v2-proposal.md), [PLAN v2](../../PLAN.md), [chỉ mục](README.md). Đọc DEVELOPMENT và contracts/rules v2 khi được tạo. Task01–02 chỉ là baseline đã nghiệm thu.

## Bạn cần cung cấp / xác nhận

- GT assist/no-assist theo cùng profile, có chuỗi trước/sau nhận bóng, dribbles/deflections/rebounds và FT-related cases.
- Review những case rule có diễn giải; đây là GT development/evaluation, không phải bấm duyệt để production sinh stats.

## Agent sẽ xây dựng

1. Giữ lịch sử pass/control/possession với passer/receiver, court position và các hành động scorer sau nhận bóng.
2. Dựng eligibility theo bảng rule source/version: last eligible pass, actor/team, continuity, action after catch; dùng temporal classifier/context model nếu rule-only không phân biệt được.
3. Không coi mọi last pass là assist, không dùng một ngưỡng N giây thay định nghĩa rule; phân biệt dribble/beat-defender/context theo profile đã chốt.
4. Invalidation qua missed FGA/rebound, turnover, deflection đáng kể, cuts và possession reset; FT assist chỉ theo applicability profile.
5. Chờ outcome/score phù hợp rồi tự xác nhận assist; event có pass_id/shot_id/score_id/passer/scorer và evidence. Nếu score void thì dependency cập nhật.
6. Đo strict linked-event/actor correctness và abstention, không dùng labels để dựng pass chain.

## Đầu ra bắt buộc

- assists.py; eligibility decisions + automatic assists, reason/evidence refs.
- docs/reports/task10-assists.md, source-backed rule matrix, tests positive/negative.

Các đường dẫn code/config/output tương đối với codebase trừ docs/. Đây là thiết kế để triển khai, không phải file/tính năng đã hoàn thành. Mỗi run có versions/config/fingerprints và evidence, không có API key.

## Nghiệm thu

- [ ] Có assist events tự phát sinh sau score không cần người dùng nhập; no-assist controls được xử lý.
- [ ] Một score không nhận nhiều assist sai profile; đúng passer/receiver/linked score.
- [ ] Module chưa DONE chỉ nhờ xuất candidate chờ người duyệt; strict P/R và coverage được task13 kiểm tra.

## Kiểm thử cần thiết

- Catch-and-shoot/handoff/bounce pass, dribble/context phù hợp và không phù hợp.
- Pass→miss→offensive rebound→score không kế thừa assist cũ; deflection/turnover.
- FT-series profile, void score, unknown actor, scene gap và duplicate score notifications.

Không dùng synthetic fixtures như dữ liệu thật, không dùng labels/manifest notes làm oracle recognition. Calibration/test v2 phải tách nhóm; labels/split v1 đã khóa được giữ nguyên. Chỉ test phù hợp thay đổi và integration evidence cần thiết, không benchmark lặp không có lý do.

## Rủi ro và điều kiện dừng phần phụ thuộc

Assists là task reasoning khó nhất; nếu cần model hoặc rule interpretation, báo cụ thể. Không đổi output thành manual-confirmed mà giữ nhãn auto.

Không cần hỏi lại có làm automatic PRA hay không: đã duyệt. Hỏi trước các thay đổi model/backend/dependency lớn, GPU stack, chi phí/cloud upload, dataset locked hoặc scope; tiếp tục phần độc lập trong khi chờ. Không xem im lặng là đồng ý. Không thay engine tự động bằng thao tác nhập/duyệt tay để đánh dấu DONE.

## Bàn giao

Linked assist events và eligibility state cho task11; invalidation/revision contract rõ.

Khi kết thúc, cập nhật task này và report với file paths, lệnh đã chạy, số liệu thật, điều kiện chưa đạt và bước tiếp theo. Chỉ chuyển DONE khi checklist có bằng chứng; sửa tay không thay automatic metrics.
