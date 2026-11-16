# Checkpoint A — giao diện review đơn giản

Ngày2026-11-05. Đã sửa trực tiếp [review.html run-08](../../codebase/outputs/task07-checkpoint-a-review-20261105-run-08/review.html), giữ12ảnh/14crop,40nhãn đã review và manifest/source inputs. Chỉ thay UI; chưa có nhãn người dùng mới hoặc thay đổi detection/identity accuracy.

## Thay đổi

- Tiếng Việt, hai lượt ảnh thi đấu và số áo; bỏ phần giới thiệu lớn, thu gọn predictions và metadata.
- Một lựa chọn loại cảnh quyết định giữ/loại, yêu cầu lý do cho loại cảnh ngoài phạm vi; “Chưa chắc / để sau” giữ unresolved.
- Sửa lỗi canvas cũ không gọi `drawImage` trước overlay. Mặc định xem ảnh nguồn rõ, có lựa chọn bật gợi ý bóng hoặc đủ3classes.
- Vẽ/chọn/di chuyển/resize/xóa bbox, hoàn tác, phóng ảnh; có thể lấy predictions làm nháp nhưng phải xác nhận đủ bbox trước duyệt.
- “Duyệt và tiếp”, danh sách số có trạng thái, điều hướng đúng tab đang mở. Trường identity không được tự điền từ OCR/team predictions.
- LocalStorage theo manifest để tự lưu/khôi phục, import/export JSON cùng schema. Khôi phục giữ bản đang sửa dở; export và approve vẫn chặn nhãn không hợp lệ. Nhãn/dự đoán/source immutable vẫn kiểm tra khi import.
- Video WebM local có controls, seek tới mốc frame khi load, thay GIF tự chạy mặc định. Crop có phóng ảnh.

Template mới: `codebase/scripts/task07a_checkpoint_a_review_simple.html`. Generator tương lai đã dùng template này. Có script render lại UI mà không chuẩn bị lại media hoặc chạy model:

```powershell
codebase/.venv/Scripts/python.exe codebase/scripts/render_task07a_checkpoint_review.py --review-dir codebase/outputs/task07-checkpoint-a-review-20261105-run-08 --roster-config codebase/configs/rosters/vietnam_tonga.json
```

Renderer đọc initial packet, giữ source/manifest, tạo backup `review-before-simplify.html` một lần. Nhãn chưa tải ở trang cũ chỉ nằm trong bộ nhớ trình duyệt; người dùng cần tải JSON trước refresh và nạp lại ở giao diện mới. Script render không đọc được phần chưa export trong tab browser cũ.

## Kiểm chứng

**34 browser checks PASS** với Playwright/Chromium local, không JavaScript error hoặc remote HTTP request. Có kiểm vẽ đúng source coordinates, kéo/resize, undo/delete, guard duyệt/loại, draft predictions, unknown, identity, phím theo tab, autosave/reload, export/import, source tamper rejection, dialog zoom, video decode/play, và mobile390px/tablet768px không tràn ngang trang. Đã xem screenshots desktop/identity; checkbox text được sửa để không chia câu thành nhiều cột.

Test dùng context riêng và nhãn giả lập, không ghi đè review-packet/nhãn người dùng. Chỉ các fixture trong `ui-qa/` chứa trạng thái được test bấm duyệt; chúng không phải GT hoặc nhãn huấn luyện.

- [Browser results](../../codebase/outputs/task07-checkpoint-a-review-20261105-run-08/ui-qa/browser-results.json).
- [Desktop screenshot](../../codebase/outputs/task07-checkpoint-a-review-20261105-run-08/ui-qa/desktop-clean.png).
- [Identity screenshot](../../codebase/outputs/task07-checkpoint-a-review-20261105-run-08/ui-qa/identity-clean.png).
- [Mobile screenshot](../../codebase/outputs/task07-checkpoint-a-review-20261105-run-08/ui-qa/mobile-clean.png).

6tests `test_task07a_checkpoint_subset.py` PASS. File synthetic export từ thao tác browser qua CLI validator hiện có, vẫn `training_authorized=false`, scope12ảnh/14crop, tái sử dụng40approval. Không chạy lại inference/OCR hoặc full ML suite vì không đổi model/recognition/validator contracts.

Browser đầu tiên không đọc được `canvas.getImageData` do canvas tainted khi mởfile://; kiểm source-image rendering bằng screenshot thay vì đổi browser security. Bản giao hiện tại đã qua toàn bộ kiểm tra cuối.

## Bàn giao

[Hướng dẫn thao tác chi tiết](../guides/task07-checkpoint-a-simple-review.md). Người dùng tiếp tục với trang run-08 và nạp JSON nếu có tiến độ cũ. File đầu ra là `task07-checkpoint-a-review.json`; giữ manifest đúng phiên bản và trả lại đường dẫn JSON. Task07 vẫn IN_PROGRESS, chờ nhãn thật để tiếp tục các phép đo cải thiện.
