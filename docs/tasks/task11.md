# Task11 — Automatic event ledger, box score và reconciliation

Cập nhật thực thi 2026-11-11: Đã triển khai và kiểm chứng toàn diện bản sửa Core Ledger / BoxScore Correctness theo [prompt thực thi Task 11](../prompts/task11-ledger-boxscore-correctness.md). Xem [Báo cáo kỹ thuật sửa đổi và bằng chứng](../reports/task11-ledger-correctness-20261111.md). Toàn bộ 21/21 independent acceptance probes (P1-E/P1-F) PASS, 33/33 comprehensive Task 11 tests PASS, 393/393 full codebase tests PASS (0 regressions). Trạng thái Task 11 tiếp tục giữ **IN_PROGRESS** để chờ hoàn thiện tích hợp upstream/downstream (Task 08–10, Task 13–15).

Kiểm thử lại 2026-11-10: [acceptance report](../reports/demo-completion-acceptance-20261110.md). Tái hiện cộng event chưa confirmed, duplicate sau refinement và dependency/audit failures.

**Version: MVP v2 Automatic Stats, 2026-11-02. Trạng thái: IN_PROGRESS.**
Ước lượng: 2–3 ngày công (không bao gồm chờ đầu vào nếu có). Phụ thuộc: Task06, task08–10.

## Mục tiêu

Tổng hợp tự động PRA theo đội/cầu thủ, nhất quán qua update/void/replay mà không phụ thuộc nhập tay.

Nguồn phạm vi: [MVP đã duyệt](../MVP-v2-proposal.md), [PLAN v2](../../PLAN.md), [chỉ mục](README.md). Đọc DEVELOPMENT và contracts/rules v2 khi được tạo. Task01–02 chỉ là baseline đã nghiệm thu.

## Bạn cần cung cấp / xác nhận

- Initial score/box-score offset nếu clip bắt đầu giữa trận, được ghi config rõ.
- Roster phiên và trường hợp correction muốn thao tác sau phân tích.

## Agent sẽ xây dựng

1. Event schema versioned với stable IDs, actor/team/timestamp/type/subtype/value, evidence/dependencies, auto status và reasons.
2. Aggregate raw auto_confirmed events; candidate/provisional/unresolved báo riêng. Unresolved attribution không gán cầu thủ tùy tiện; tổng team/unassigned phải đối chiếu được.
3. Idempotent event application, checkpoint/resume/seek replay và ordering theo source PTS; tránh race/double-add.
4. Score void/reclassify phải propagate assist dependencies; rebound/team rebound rules giữ conservation và separate personal/team totals.
5. Automatic logs append-only theo run; correction separate không sửa raw evidence hoặc làm đẹp evaluation.
6. Export boxscore_auto.csv, events_auto.jsonl và trạng thái reconciliation.

## Đầu ra bắt buộc

- events.py, boxscore.py; event schema/ledger snapshots và exports.
- docs/reports/task11-ledger.md, invariant tests và README contracts.

Các đường dẫn code/config/output tương đối với codebase trừ docs/. Đây là thiết kế để triển khai, không phải file/tính năng đã hoàn thành. Mỗi run có versions/config/fingerprints và evidence, không có API key.

## Nghiệm thu

- [ ] PRA cập nhật tự động khi module phát event, không yêu cầu user approve.
- [ ] Chạy lại/reload/reorder inputs theo contract không đổi totals; point/assist void không để số liệu mồ côi.
- [ ] Bảng raw auto và corrected tách riêng; offset không bị lẫn điểm do video quan sát.

## Kiểm thử cần thiết

- Duplicate event, provisional→confirmed→void/revision, score value change cascade.
- Unknown-to-known actor update không cộng hai lần; team rebound không vào player rebound.
- Checkpoint replay, initial offsets và failed/incomplete run integrity.

Không dùng synthetic fixtures như dữ liệu thật, không dùng labels/manifest notes làm oracle recognition. Calibration/test v2 phải tách nhóm; labels/split v1 đã khóa được giữ nguyên. Chỉ test phù hợp thay đổi và integration evidence cần thiết, không benchmark lặp không có lý do.

## Rủi ro và điều kiện dừng phần phụ thuộc

Log không nhất quán là blocker nghiệm thu dù bảng cuối nhìn đúng. Không dùng tổng số khớp để bỏ qua actor/link errors.

Không cần hỏi lại có làm automatic PRA hay không: đã duyệt. Hỏi trước các thay đổi model/backend/dependency lớn, GPU stack, chi phí/cloud upload, dataset locked hoặc scope; tiếp tục phần độc lập trong khi chờ. Không xem im lặng là đồng ý. Không thay engine tự động bằng thao tác nhập/duyệt tay để đánh dấu DONE.

## Bàn giao

Read-only aggregate/events/evidence API cho dashboard và evaluator; corrections layer riêng.

Khi kết thúc, cập nhật task này và report với file paths, lệnh đã chạy, số liệu thật, điều kiện chưa đạt và bước tiếp theo. Chỉ chuyển DONE khi checklist có bằng chứng; sửa tay không thay automatic metrics.
