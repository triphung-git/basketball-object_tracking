# Task05 — Court calibration, vùng sân và heatmap

**Version: MVP v2 Automatic Stats, 2026-11-03. Trạng thái: IN_PROGRESS — tooling implemented, geometry/data acceptance pending.**
Ước lượng: 2–3 ngày công (không bao gồm chờ đầu vào nếu có). Phụ thuộc: Task03; nhãn vị trí/geometry từ task04. Task06 dùng ROI này; task05 không chờ team classifier để tránh vòng phụ thuộc.

Prompt thực thi xuyên suốt **task05–06**: [task05-coding-agent.md](../prompts/task05-coding-agent.md). Tái nghiệm thu 2026-11-03: [report chung](../reports/task05-task06-acceptance.md), 159 tests PASS; G05-G còn pending, không gọi toàn task DONE.

## Mục tiêu

Tạo tọa độ sân và heatmap time-weighted đúng coverage; hoàn thiện tích hợp team sau ở task12.

Nguồn phạm vi: [MVP đã duyệt](../MVP-v2-proposal.md), [PLAN v2](../../PLAN.md), [chỉ mục](README.md). Đọc DEVELOPMENT và contracts/rules v2 khi được tạo. Task01–02 chỉ là baseline đã nghiệm thu.

## Bạn cần cung cấp / xác nhận

- Chọn ít nhất 4 cặp điểm cùng mặt sân, không suy biến; xác nhận nửa sân, orientation, rổ/cung/vùng phân tích.
- Vị trí chân nhìn rõ làm GT; chưa yêu cầu tự động đo mét nếu không có scale đáng tin.

## Agent sẽ xây dựng

1. Công cụ cấu hình court/ROI, giải homography và kiểm tra reprojection/điểm ngoài sân; lưu calibration theo góc quay/version.
2. Ước lượng điểm chân từ bbox hoặc keypoints được phép, đổi sang tọa độ sân; đánh dấu invalid/occluded, không lấy tâm người trên không làm điểm tiếp xúc chắc chắn.
3. Heatmap nhận position/time/team contract, dùng Δt và player-seconds; tổng thể/theo đội/unknown riêng.
4. Không cộng qua cut/excluded/mất dấu dài hoặc phần chỉ dự đoán. Pause/seek/reload dùng replay/checkpoint idempotent.
5. Lưu trajectory đủ để recompute khi đổi team/loại track/calibration, không chỉ vẽ màu cuối.

## Đầu ra bắt buộc

- court.py, heatmap.py; configs/courts/<camera>.json; trajectory schema và heatmap PNG/metadata.
- docs/reports/task05-court-heatmap.md, hướng dẫn chọn điểm và kiểm tra geometry.

Các đường dẫn code/config/output tương đối với codebase trừ docs/. Đây là thiết kế để triển khai, không phải file/tính năng đã hoàn thành. Mỗi run có versions/config/fingerprints và evidence, không có API key.

## Nghiệm thu

- [ ] Orientation/tọa độ ảnh–sân khớp labeled points; báo median error và coverage, mục tiêu ≤5% chiều rộng vùng sân trên visible-foot GT. (PENDING — chờ landmarks và visible-foot GT được review)
- [x] Công cụ có sampling-rate/VFR invariance, exclusions union, cut/invalid/predicted barriers và replay tests. PASS trong scope fixtures/diagnostic; chưa đo heatmap trận thật.
- [x] Test team input có thể dùng fixtures; sau task06 phải tích hợp nguồn team tự động ở task12, không gán GT vào live heatmap. (PASS — test_team_separation_and_mass_conservation)

## Kiểm thử cần thiết

- Homography suy biến/ít điểm, ảnh dọc, điểm ngoài ROI.
- Δt VFR, gap/cut, pause/seek/reload; 3 người ×2s =6 player-seconds.
- Recompute sau sửa team/calibration không nhân đôi counts.

Không dùng synthetic fixtures như dữ liệu thật, không dùng labels/manifest notes làm oracle recognition. Calibration/test v2 phải tách nhóm; labels/split v1 đã khóa được giữ nguyên. Chỉ test phù hợp thay đổi và integration evidence cần thiết, không benchmark lặp không có lý do.

## Rủi ro và điều kiện dừng phần phụ thuộc

Camera pan/zoom làm geometry không còn hợp lệ: reset/đánh dấu ngoài scope, không tiếp tục dùng ma trận cũ. Mở camera-motion compensation cần quyết định phạm vi.

Không cần hỏi lại có làm automatic PRA hay không: đã duyệt. Hỏi trước các thay đổi model/backend/dependency lớn, GPU stack, chi phí/cloud upload, dataset locked hoặc scope; tiếp tục phần độc lập trong khi chờ. Không xem im lặng là đồng ý. Không thay engine tự động bằng thao tác nhập/duyệt tay để đánh dấu DONE.

## Bàn giao

Court positions, ROI/rim/arc polygons và uncertainty cho task06/08; heatmap API cho task12.

[Report task05](../reports/task05-court-heatmap.md) · [Checkpoint task05→06](../handoffs/task05-to-task06-08-12.md) · [Handoff cuối](../handoffs/task06-to-task07-08-12.md). Synthetic geometry không phải arc/court calibration thật đã duyệt.

Khi kết thúc, cập nhật task này và report với file paths, lệnh đã chạy, số liệu thật, điều kiện chưa đạt và bước tiếp theo. Chỉ chuyển DONE khi checklist có bằng chứng; sửa tay không thay automatic metrics.
