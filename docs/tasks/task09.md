# Task09 — Rebounds tự động, loại và người ghi nhận

Kiểm thử lại 2026-11-10: [acceptance report](../reports/demo-completion-acceptance-20261110.md). **IN_PROGRESS; chưa nghiệm thu.** Module có tests nhưng thiếu eligible-miss/FT/observed-control guards, chưa nối demo thực.

**Version: MVP v2 Automatic Stats, 2026-11-02. Trạng thái: IN_PROGRESS.**
Ước lượng: 2–4 ngày công (không bao gồm chờ đầu vào nếu có). Phụ thuộc: Task04, task06–08.

## Mục tiêu

Tự ghi rebound đúng actor/team sau missed shot/last FT phù hợp, phân offensive/defensive và team rebound.

Nguồn phạm vi: [MVP đã duyệt](../MVP-v2-proposal.md), [PLAN v2](../../PLAN.md), [chỉ mục](README.md). Đọc DEVELOPMENT và contracts/rules v2 khi được tạo. Task01–02 chỉ là baseline đã nghiệm thu.

## Bạn cần cung cấp / xác nhận

- GT rebound có control/controlled tip, tranh chấp, airball/block, dead-ball, bóng ngoài sân và hard negatives.
- Review rule matrix và những tình huống không quan sát được quyền bóng/trọng tài.

## Agent sẽ xây dựng

1. Mở rebound window theo eligible missed shot; dùng FT sequence/context để không ghi rebound cho mọi missed FT.
2. Nhận control recovery/controlled tip qua multi-frame ball/player evidence; không lấy người chạm/gần bóng đầu tiên như rebounder mặc định.
3. Loại offensive/defensive theo đội ném; team rebound tách khỏi player stats, chỉ nhận khi đủ evidence rule profile.
4. Đóng window một lần khi rebound/terminal outcome; liên kết shot_id/control event; reset pass-chain cần thiết để assists không đi xuyên shot miss.
5. Handle blocked FGA, loose ball, multi-touch, out-of-bounds/foul/context unresolved; lưu reason codes thay vì tự đoán tình huống trọng tài.
6. Đo event detection và strict actor/subtype/link separately.

## Đầu ra bắt buộc

- rebounds.py; automatic rebound events với shot/control refs và subtype.
- docs/reports/task09-rebounds.md, case matrix/debug timelines và tests.

Các đường dẫn code/config/output tương đối với codebase trừ docs/. Đây là thiết kế để triển khai, không phải file/tính năng đã hoàn thành. Mỗi run có versions/config/fingerprints và evidence, không có API key.

## Nghiệm thu

- [ ] Tự tạo event, không người dùng chọn rebounder; không double-count sau nhiều lần chạm.
- [ ] Player/team rebound và offensive/defensive đúng theo profile fixtures; missing context thành unresolved có tính vào coverage.
- [ ] Strict P/R từng loại và chính xác actor/shot link được task13 đo trước correction.

## Kiểm thử cần thiết

- Miss→loose→control, controlled tip, contested catch rồi mất bóng.
- Missed FT không cuối, team rebound/dead ball, block có/không FGA hợp lệ.
- Made shot không mở rebound event; window timeout/cut không nối lượt khác.

Không dùng synthetic fixtures như dữ liệu thật, không dùng labels/manifest notes làm oracle recognition. Calibration/test v2 phải tách nhóm; labels/split v1 đã khóa được giữ nguyên. Chỉ test phù hợp thay đổi và integration evidence cần thiết, không benchmark lặp không có lý do.

## Rủi ro và điều kiện dừng phần phụ thuộc

Không có control hoặc FT/dead-ball context thì gate chưa đạt, không thay bằng nearest-player heuristic rồi gọi rebound hoàn chỉnh.

Không cần hỏi lại có làm automatic PRA hay không: đã duyệt. Hỏi trước các thay đổi model/backend/dependency lớn, GPU stack, chi phí/cloud upload, dataset locked hoặc scope; tiếp tục phần độc lập trong khi chờ. Không xem im lặng là đồng ý. Không thay engine tự động bằng thao tác nhập/duyệt tay để đánh dấu DONE.

## Bàn giao

Rebound/shot/possession reset events cho task10/11; team rebounds không cộng vào rebound cá nhân.

Khi kết thúc, cập nhật task này và report với file paths, lệnh đã chạy, số liệu thật, điều kiện chưa đạt và bước tiếp theo. Chỉ chuyển DONE khi checklist có bằng chứng; sửa tay không thay automatic metrics.
