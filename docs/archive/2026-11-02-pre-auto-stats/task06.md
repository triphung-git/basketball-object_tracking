# Task06 — Scoreboard, điều khiển và lịch sử sửa

Trạng thái: TODO. Dự kiến: ngày 5. Phụ thuộc: task05.

## Mục tiêu

Biến sự kiện nhận diện thành ứng dụng demo dễ sử dụng; điểm và chỉnh sửa phải truy vết được.

## Bạn cần quyết định/thực hiện

Chọn cá nhân hoặc A/B thủ công; chọn giá trị lượt ném trước khi ném. Mặc định cá nhân, 2 điểm. Thử thao tác trong một phiên demo và phản hồi tính dễ dùng.

## Tôi sẽ xây dựng

1. `scoreboard.py`: tính tổng từ sự kiện, chống áp dụng hai lần cùng `event_id`.
2. Chốt đội/giá trị vào ngữ cảnh lượt khi tạo ứng viên; đổi lựa chọn trong lúc bóng đang gần rổ chỉ áp dụng lượt sau và hiển thị rõ.
3. Overlay: tổng điểm, số lần vào tự động còn hiệu lực, đội/giá trị đang chọn, trạng thái lượt, nguồn và tốc độ xử lý. Thời gian hiển thị là thời gian video/phiên.
4. Điều khiển pause/resume, chọn đội, chọn 1/2/3, undo sự kiện điểm gần nhất, reset phiên và quit; hiển thị bảng phím thực tế.
5. Undo/reset lưu bản ghi chỉnh sửa, không xóa log gốc; reset tạo mốc phiên mới để không nhập nhằng điểm.
6. Khi pause MP4 không tiến timestamp/trạng thái; với live chốt chính sách bỏ frame lúc pause và reset ứng viên khi resume, không tính điểm trong thời gian bị bỏ qua.
7. Tách log tự động, log điều chỉnh và scoreboard cuối để đánh giá không bị ảnh hưởng bởi sửa tay.

## Đầu ra

- Module scoreboard và tích hợp app/overlay.
- `events_auto.csv`, `adjustments.csv`, `scoreboard.json` theo run.
- Hướng dẫn phím, ví dụ phiên và ảnh/video giao diện.

## Nghiệm thu

- [ ] Sự kiện 2 điểm tăng đúng 2; đội/giá trị lấy đúng ngữ cảnh đã chốt.
- [ ] Áp dụng lại cùng sự kiện không tăng thêm; undo không làm mất bản ghi gốc.
- [ ] Reset bắt đầu phiên mới và có lịch sử; xử lý rõ trường hợp chưa có điểm để undo.
- [ ] Pause/resume không tạo một lượt vào giả; quit giải phóng camera/video.
- [ ] Có test cập nhật điểm, idempotency, undo/reset và đổi ngữ cảnh giữa lượt.

## Giới hạn

Không phải scoreboard điều hành trận chính thức. Không có đồng hồ luật, tự nhận đội, tự phân loại vị trí ném hoặc chỉnh sửa không dấu vết. Dashboard web không cần cho MVP.
