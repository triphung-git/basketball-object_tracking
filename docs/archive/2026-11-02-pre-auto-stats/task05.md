# Task05 — Nhận diện bóng vào rổ và chống đếm lặp

Trạng thái: TODO. Dự kiến: ngày 4. Phụ thuộc: task04, calibration labels task02.

## Mục tiêu

Chuyển chuỗi quan sát thành sự kiện `basket_made`; ưu tiên tránh cộng nhầm và cộng lặp, có thể giải thích bằng trạng thái.

## Bạn cần cung cấp

Ground truth calibration đã rà soát; xác nhận các clip bật vành, bóng trượt phía trước/sau rổ và tình huống khuất khó kết luận.

## Tôi sẽ xây dựng

1. `scoring.py`: trạng thái `IDLE → ABOVE_RIM → CROSSING_RIM → BELOW_RIM → SCORED`; timeout/reset cho chuỗi không hoàn chỉnh.
2. Định nghĩa rõ điều kiện chuyển: vị trí tương đối với ROI, xu hướng đi xuống, giao vùng vành và quan sát phía dưới trong cửa sổ thời gian. Việc chạm bbox không đủ.
3. Dùng tọa độ chuẩn hóa/kích thước vành và thời gian giây. Các ngưỡng phải cấu hình được, chốt bằng calibration.
4. Phân biệt chuỗi có bằng chứng với chuỗi thiếu; không tự xác nhận điểm chỉ từ nội suy/Kalman. Mất bóng quá lâu hoặc ứng viên mơ hồ thì hủy/đánh dấu chưa xác nhận.
5. Chống lặp theo chu kỳ lượt ném: latch sự kiện đến khi bóng rời vùng/reset, thêm cooldown có cấu hình; không chỉ dựa vào tracker ID.
6. `events.py`: tạo ID duy nhất, timestamp theo nguồn, `shot_id` nội bộ, lý do và tham chiếu frame; giữ ID lượt nội bộ tách khỏi nhãn thủ công.
7. Xuất trace chuyển trạng thái để giải thích vì sao cộng/bỏ qua.

## Đầu ra

- Module scoring, event schema và cấu hình ngưỡng.
- `events_auto.csv`, state trace và video debug trên calibration.
- Test logic bằng chuỗi quan sát ngắn: vào, đi lên, trượt cạnh, bật vành rồi ra, bóng đứng gần rổ, mất dấu, timeout, ID đổi và hai lượt liên tiếp.

## Nghiệm thu

- [ ] Một chuỗi vào hợp lệ phát một sự kiện; đứng dưới rổ nhiều frame không tạo thêm.
- [ ] Bóng chỉ chạm vùng vành, đi ngược hướng hoặc chỉ có dự báo không được tự cộng.
- [ ] Timeout khôi phục khả năng xử lý lượt kế tiếp.
- [ ] Hai lượt hợp lệ liên tiếp được ghi riêng khi đáp ứng điều kiện reset.
- [ ] Các test logic trọng yếu pass và có video thực tế minh họa; pass test không thay thế đánh giá video.

## Giới hạn

Hình chiếu 2D không bảo đảm phân biệt mọi bóng vào/trượt. Log phải cho phép tìm FP/FN; không chỉnh ngưỡng trên test set task07. Chưa tự suy ra đội hay giá trị 1/2/3 điểm.
