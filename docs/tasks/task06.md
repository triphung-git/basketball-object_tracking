# Task06 — Player tracking, team classification và định danh

**Version: MVP v2 Automatic Stats, 2026-11-03. Trạng thái: IN_PROGRESS — tooling implemented, data/model acceptance pending.**
Ước lượng: 4–6 ngày công (không bao gồm chờ đầu vào nếu có). Phụ thuộc: Task03, task04; court ROI từ task05.

Prompt chung task05–06: [task05-coding-agent.md](../prompts/task05-coding-agent.md). Tái nghiệm thu 2026-11-03: [report chung](../reports/task05-task06-acceptance.md), 159 tests PASS; core tracker/color/resolver và OCR provider layer (`LocalEasyOCRProvider`, `MockOCRProvider`, CLI wiring) đã kiểm chứng, OCR model weights download (~130 MB) chờ user phê duyệt và G06-D còn pending.

## Mục tiêu

Gán đúng team và player_id ổn định đủ cho attribution PRA; không coi track ID tạm là danh tính.

Nguồn phạm vi: [MVP đã duyệt](../MVP-v2-proposal.md), [PLAN v2](../../PLAN.md), [chỉ mục](README.md). Đọc DEVELOPMENT và contracts/rules v2 khi được tạo. Task01–02 chỉ là baseline đã nghiệm thu.

## Bạn cần cung cấp / xác nhận

- Roster team/player/jersey và footage có số áo nhìn được ở một số thời điểm.
- Màu đội mẫu và nhãn identity qua che khuất/thay người; không phải click gán actor từng sự kiện.

## Agent sẽ xây dựng

1. Tracking người trong sân với dependency tương thích phiên bản hiện có; loại staff/spectators/referees bằng ROI/classification/unknown policy.
2. Phân đội từ màu áo và evidence theo thời gian, cấu hình A/B; unknown riêng, không ép mọi human vào đội.
3. Tạo identity resolver: OCR/số áo kết hợp roster và track/appearance evidence; kiểm tra jersey trùng giữa hai đội, confidence/conflict và cập nhật identity theo thời gian.
4. Giữ mapping track→player có version/evidence; merge/split khi reacquire có ngưỡng, reset khi scene đổi; substitution không tự nhân bản một người thành hai.
5. Khảo sát bằng calibration xem cần OCR/pose/ReID model bổ sung. Chốt model/nguồn/license/runtime và xin quyết định trước thêm tải lớn/chi phí; không thay detector đã duyệt.
6. Báo team accuracy/unknown/miss, ID switches/fragmentation và event-time identity coverage; không chỉ báo frame accuracy trên mặt người dễ.

## Đầu ra bắt buộc

- players.py, identity.py; roster/config/schema mappings và identity evidence logs.
- docs/reports/task06-players-identity.md, model decision record nếu cần bổ sung.

Các đường dẫn code/config/output tương đối với codebase trừ docs/. Đây là thiết kế để triển khai, không phải file/tính năng đã hoàn thành. Mỗi run có versions/config/fingerprints và evidence, không có API key.

## Nghiệm thu

- [ ] Theo dõi và nhận team/player tự động trên đoạn hai đội, có handling mất dấu/conflict, không cần gán lại từng pha. (PENDING — chờ footage hai đội và roster chính thức)
- [ ] Metrics attribution thật có unknown/miss/error trên GT độc lập. Unit logic TTL/dedup/conflict/no-backfill đã PASS; real accuracy vẫn N/A, không dùng fixtures hoặc team-color votes thay GT.
- [ ] Team accuracy mục tiêu ≥90% với unknown/miss counts; đủ actor evidence cho task07–10 trên calibration, final quality vẫn do task13. (PENDING — chờ benchmark footage hai đội)

## Kiểm thử cần thiết

- Hai đội cùng số áo, OCR đổi số sai một frame, duplicate player active, giao nhau/occlusion.
- Track mất dấu/reacquire/substitution/cut, mapping revision replay.
- Không có jersey evidence phải unknown; đường production không đọc annotation IDs.

Không dùng synthetic fixtures như dữ liệu thật, không dùng labels/manifest notes làm oracle recognition. Calibration/test v2 phải tách nhóm; labels/split v1 đã khóa được giữ nguyên. Chỉ test phù hợp thay đổi và integration evidence cần thiết, không benchmark lặp không có lý do.

## Rủi ro và điều kiện dừng phần phụ thuộc

Footage không đủ đọc jersey hoặc identity coverage thấp là gate G2 chưa đạt. Cần video tốt hơn/model/data, không hạ yêu cầu thành danh tính nhập tay theo từng pha.

Không cần hỏi lại có làm automatic PRA hay không: đã duyệt. Hỏi trước các thay đổi model/backend/dependency lớn, GPU stack, chi phí/cloud upload, dataset locked hoặc scope; tiếp tục phần độc lập trong khi chờ. Không xem im lặng là đồng ý. Không thay engine tự động bằng thao tác nhập/duyệt tay để đánh dấu DONE.

## Bàn giao

Player observations/team/identity probabilities hoặc evidence scores có nguồn cho possession và event attribution; không gọi score chưa calibrate là xác suất chắc chắn.

[Report task06](../reports/task06-players-identity.md) · [Handoff task07/08/12](../handoffs/task06-to-task07-08-12.md). ROI không tự chứng minh player; event-time mapping dùng mapping_at, OCR chưa nối CLI.

Khi kết thúc, cập nhật task này và report với file paths, lệnh đã chạy, số liệu thật, điều kiện chưa đạt và bước tiếp theo. Chỉ chuyển DONE khi checklist có bằng chứng; sửa tay không thay automatic metrics.
