# Task12 — Dashboard local, heatmap và exports tự động

Kiểm thử lại 2026-11-10: [acceptance report](../reports/demo-completion-acceptance-20261110.md). **IN_PROGRESS; chưa nghiệm thu.** Browser thực: 10 pass/8 fail; thiếu actual heatmap, coverage/provenance/evidence/lifecycle workflow.

**Version: MVP v2 Automatic Stats, 2026-11-02. Trạng thái: IN_PROGRESS.**
Ước lượng: 2–3 ngày công (không bao gồm chờ đầu vào nếu có). Phụ thuộc: Task05, task11; nguồn players/identity/control từ task06–07.

## Mục tiêu

Trình diễn video/sân/heatmap/PRA tự cập nhật và truy vết từng event, không UI nhập tay làm nguồn stats chính.

Nguồn phạm vi: [MVP đã duyệt](../MVP-v2-proposal.md), [PLAN v2](../../PLAN.md), [chỉ mục](README.md). Đọc DEVELOPMENT và contracts/rules v2 khi được tạo. Task01–02 chỉ là baseline đã nghiệm thu.

## Bạn cần cung cấp / xác nhận

- Tên hiển thị roster/đội, khoảng coverage và format báo cáo mong muốn nếu khác CSV/JSON.
- Thử usability và xác nhận frame/time hiển thị dễ đối chiếu.

## Agent sẽ xây dựng

1. Giao diện local có video overlay, court map, team heatmaps, region stats, auto box score và timeline evidence.
2. Hiển thị tentative/auto-confirmed/unresolved/corrected rõ; chưa có số liệu là pending/unknown, không giả 0 đầy đủ.
3. Pause/seek trong đoạn đã xử lý, checkpoint/progress và phân biệt video time với processing time; không đọc lại frame làm nhân đôi heatmap/events.
4. Audit click mở bằng chứng, correction/undo tùy chọn; thao tác sửa không bắt buộc để stats tự cập nhật.
5. Export video, PNG, trajectories/control/events/boxscore và run metadata; snapshot config/roster/rules/model/hashes.
6. Recompute heatmap khi team/calibration correction theo version, giữ raw automatic outputs.

## Đầu ra bắt buộc

- ui/ và app integration; local run workflow, exports, docs/user-guide-v2.md.
- docs/reports/task12-dashboard.md, demo captures và export manifest.

Các đường dẫn code/config/output tương đối với codebase trừ docs/. Đây là thiết kế để triển khai, không phải file/tính năng đã hoàn thành. Mỗi run có versions/config/fingerprints và evidence, không có API key.

## Nghiệm thu

- [ ] Không thao tác nhập stats trong demo happy path, cả PRA/heatmap vẫn cập nhật.
- [ ] Video/JSON/heatmap/time labels đồng bộ; exports mở được, nguồn rõ.
- [ ] Corrections có provenance, raw auto unchanged; no secrets hay media upload mặc định.

## Kiểm thử cần thiết

- Pause/seek/reload, correction/undo và recompute không nhân đôi.
- Zero detections, pending events, gap/cut, lỗi export/write quyền.
- Một integration session hai đội từ video đến artifacts; không tuning bằng holdout.

Không dùng synthetic fixtures như dữ liệu thật, không dùng labels/manifest notes làm oracle recognition. Calibration/test v2 phải tách nhóm; labels/split v1 đã khóa được giữ nguyên. Chỉ test phù hợp thay đổi và integration evidence cần thiết, không benchmark lặp không có lý do.

## Rủi ro và điều kiện dừng phần phụ thuộc

Không thêm cloud/accounts/DB phức tạp trong MVP. Nếu UI chỉ có form points/rebounds/assists mà engines chưa chạy thì task chưa đạt.

Không cần hỏi lại có làm automatic PRA hay không: đã duyệt. Hỏi trước các thay đổi model/backend/dependency lớn, GPU stack, chi phí/cloud upload, dataset locked hoặc scope; tiếp tục phần độc lập trong khi chờ. Không xem im lặng là đồng ý. Không thay engine tự động bằng thao tác nhập/duyệt tay để đánh dấu DONE.

## Bàn giao

Demo product và output bundle cho task13 evaluation; UI phải đọc ledger chứ không tự tính logic event khác.

Khi kết thúc, cập nhật task này và report với file paths, lệnh đã chạy, số liệu thật, điều kiện chưa đạt và bước tiếp theo. Chỉ chuyển DONE khi checklist có bằng chứng; sửa tay không thay automatic metrics.
