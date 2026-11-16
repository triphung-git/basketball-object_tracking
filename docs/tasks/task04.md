# Task04 — Dataset v2, rule profile và protocol đánh giá

**Version: MVP v2 Automatic Stats, 2026-11-02. Trạng thái: IN_PROGRESS (bàn giao công cụ; chờ footage/roster/labels và chốt rules/protocol).**
Ước lượng: 3–5 ngày công cho công cụ/kiểm tra; thời gian quay/gán nhãn/chờ review phụ thuộc người dùng. Phụ thuộc: Task02 pilot v1; Task03 pipeline contracts.

## Mục tiêu

Có ground truth đủ chuỗi hành động và profile thống kê để nghiệm thu từng points/rebounds/assists tự động, không chỉ nhãn shot.

Nguồn phạm vi: [MVP đã duyệt](../MVP-v2-proposal.md), [PLAN v2](../../PLAN.md), [chỉ mục](README.md). Đọc DEVELOPMENT và contracts/rules v2 khi được tạo. Task01–02 chỉ là baseline đã nghiệm thu.

## Bạn cần cung cấp / xác nhận

- Video phát triển mới hai đội, roster/số áo, session/camera và các điểm sân; có cả made/miss, free throws, rebound, pass dẫn đến assist và các trường hợp không assist.
- Review actors/timestamps và rules áp dụng cho giải 3x3. Không cần nhập stats vào app production, nhưng ground truth đánh giá vẫn do người kiểm tra độc lập.

## Agent sẽ xây dựng

1. Giữ nguyên dataset/split v1; namespace data/v2, IDs/provenance/hashes và aliases nguồn, chống duplicate/replay cùng pha xuyên split.
2. Định nghĩa schemas player positions/identity/ball control/pass/shot/rebound/assist, coverage và reviews; quan hệ shot/possession/event, uncertainty và labels draft/approved.
3. Chốt ruleset versioned và source citations cho giải: point values, shot/FT kinds, control/controlled tip, team rebound, dead ball, assist exclusions và ngoại lệ. Kiểm tra tính áp dụng manual thay vì coi luật 5x5 là profile 3x3 mặc định.
4. Tạo annotation guide với positive/negative/uncertain examples; xem đủ chuỗi trước/sau pha. Point time lấy PTS; frame notes VFR chỉ tham chiếu gần đúng.
5. Tạo validator v2 kiểm tra refs, reviewed coverage kể cả background, lock fingerprints cho labels/reviews/roster/rules/splits và metadata; không promote draft tự động.
6. Chốt calibration/validation/test và một reserve cho final retest nếu có thể, theo session/source; protocol strict actor/value/subtype/link và matching windows trước test.
7. Mục tiêu thu thập ≥50 shots, ≥30 rebounds và ≥30 assists positives kèm hard negatives, đủ hình thức 1/2 điểm và FT; báo số thật, không dùng ngưỡng số lượng để bịa nhãn. Thiếu loại sự kiện thì chưa nghiệm thu stat đó.

## Đầu ra bắt buộc

- data/v2/{manifest.csv,splits.json,roster.csv,ruleset.json,annotations/...}; không sửa data/v1 artifacts hiện có.
- docs/data/ANNOTATION_GUIDE-v2.md, docs/specs/{contracts-v2,rules-v2,evaluation-protocol-v2}.md, docs/reports/data-v2.md.
- Công cụ prepare/validate v2, tests và template reviewer.

Các đường dẫn code/config/output tương đối với codebase trừ docs/. Đây là thiết kế để triển khai, không phải file/tính năng đã hoàn thành. Mỗi run có versions/config/fingerprints và evidence, không có API key.

## Nghiệm thu

- [ ] Mỗi stat có GT đã duyệt, controls/no-event/uncertain policy; source/identity/timebase có evidence (Đang chờ footage trận đấu 2 đội và dual-team review từ người dùng).
- [x] Bàn giao 9 schema templates, annotation guide, prepare/validator và tests (92 tests chung pass). [Báo cáo dữ liệu v2](../reports/data-v2.md) · [Nghiệm thu G03–G04](../reports/task03-task04-acceptance.md).
- [ ] Rules/protocol được chốt theo giải 3x3; hiện draft/pending. Diễn giải FT-assist sai đã sửa theo xác nhận người dùng; còn cần extension FT-series/foul/possession trước freeze.
- [x] Namespace `codebase/data/v2/` độc lập, sáu fingerprint v1 baseline không đổi; validator có tests chống leakage/tamper.
- [ ] Split v2 và provenance session/pha được review rồi khóa. Hiện draft, test rỗng; không kết luận split benchmark đã sẵn sàng.
- [x] Handoff kỹ thuật cho Task 05 & Task 06: [Bàn giao task04→05–06](../handoffs/task04-to-task05-06.md). Các module sau có thể đọc data kỹ thuật mà không cần load GT.

## Kiểm thử cần thiết

- Dangling actor/shot/pass/assist links, nonfinite/out-of-range PTS, review missing và lock tamper phải fail.
- Replay/derived clip grouping, same-session leakage và uncertain/coverage gaps.
- Case matrix gồm assist/no-assist sau dribble/deflection/miss/rebound; rebound vs mere touch và FT cuối/không cuối theo profile.

Không dùng synthetic fixtures như dữ liệu thật, không dùng labels/manifest notes làm oracle recognition. Calibration/test v2 phải tách nhóm; labels/split v1 đã khóa được giữ nguyên. Chỉ test phù hợp thay đổi và integration evidence cần thiết, không benchmark lặp không có lý do.

## Rủi ro và điều kiện dừng phần phụ thuộc

Thiếu video/nhãn là blocker chất lượng thật. Tiếp tục công cụ/scaffold độc lập, hỏi dữ liệu cụ thể; không tự đổi holdout v1 thành calibration hoặc dùng manual entry để thay automatic recognition.

Không cần hỏi lại có làm automatic PRA hay không: đã duyệt. Hỏi trước các thay đổi model/backend/dependency lớn, GPU stack, chi phí/cloud upload, dataset locked hoặc scope; tiếp tục phần độc lập trong khi chờ. Không xem im lặng là đồng ý. Không thay engine tự động bằng thao tác nhập/duyệt tay để đánh dấu DONE.

## Bàn giao

Contracts/rules/protocol cho task05–15. Ngưỡng làm việc P≥95%, R≥90% từng stat được ghi trước test; chưa phải kết quả đạt.

Khi kết thúc, cập nhật task này và report với file paths, lệnh đã chạy, số liệu thật, điều kiện chưa đạt và bước tiếp theo. Chỉ chuyển DONE khi checklist có bằng chứng; sửa tay không thay automatic metrics.
