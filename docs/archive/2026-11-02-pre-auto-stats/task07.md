# Task07 — Đánh giá sự kiện và hiệu năng

Trạng thái: TODO. Dự kiến: ngày 6. Phụ thuộc: task02–06.

## Mục tiêu

Đo độ chính xác ghi điểm và tốc độ thực tế; kết luận rõ phần đạt và chưa đạt, không chỉ chọn clip đẹp.

## Bạn cần cung cấp/thực hiện

Ground truth test đã rà soát; máy chạy mục tiêu. Nếu cần live, cung cấp camera thực tế và thử một phiên liên tục có nhãn đối chiếu.

## Tôi sẽ thực hiện

1. Khóa cấu hình sau calibration, lưu snapshot/model/runtime version trước chạy test.
2. `scripts/evaluate.py`: ghép sự kiện dự đoán và `made` ground truth một-một trong cùng video, theo sai lệch thời gian nhỏ nhất trong cửa sổ ±0,5 giây mặc định. Chốt cửa sổ trước đánh giá; báo nếu độ chính xác nhãn buộc thay đổi.
3. Dự đoán đã ghép là TP; chưa ghép là FP; ground truth chưa ghép là FN. Nhiều dự đoán quanh cùng lượt vào chỉ ghép một, phần dư là FP/đếm trùng. Lượt miss dùng để phân tích FP; uncertain báo riêng.
4. Tính precision = TP/(TP+FP), recall = TP/(TP+FN), F1; nếu mẫu số 0 ghi N/A và số lượng, không báo 100% tùy tiện.
5. Báo sai lệch điểm cuối và sai số theo lượt. Tính điểm dự đoán dùng cùng metadata đội/giá trị thủ công đã chốt, không quy lỗi nhận đội cho detection.
6. Benchmark warm-up riêng; đo toàn pipeline gồm đọc/inference/tracking/scoring/vẽ/ghi khi bật. Ghi FPS nguồn, FPS xử lý, độ trễ p50/p95 và frame bỏ qua; phân biệt latency xử lý với capture-to-display khi không đo được timestamp capture.
7. Tối ưu có mục tiêu: crop/resize, giảm overhead. Nếu thay đổi ảnh đầu vào/rule sau xem test, đánh dấu vòng đó là phát triển và dùng tập giữ lại mới để kết luận cuối.
8. Chỉ thử webcam sau MP4 ổn; kiểm tra backlog và bỏ frame gần rổ. Không đạt live thì giữ bản offline và báo giới hạn.

## Đầu ra

- `metrics.json`, bảng matching TP/FP/FN, clip/frame lỗi và config snapshot.
- `docs/reports/evaluation.md`: dataset/split, cỡ mẫu, phương pháp, kết quả và lỗi theo nhóm.
- `docs/reports/performance.md`: máy, nguồn, độ phân giải, runtime, chế độ local/remote, FPS/latency và quyết định live.

## Nghiệm thu

- [ ] Metrics được tính từ events tự động trước undo/sửa tay; ghép một-một tái lập được.
- [ ] Báo đủ mẫu số, TP/FP/FN, đếm trùng; có vào, trượt và tình huống khó.
- [ ] So mục tiêu precision ≥95%, recall ≥90%; nếu không đạt ghi rõ, không sửa kết quả.
- [ ] Live chỉ đánh dấu đạt khi chạy liên tục ít nhất 5 phút với throughput ≥FPS nguồn, không tăng backlog; báo mọi frame bị bỏ và chất lượng sự kiện trong phiên.
- [ ] Nếu chưa có camera hoặc không đạt tốc độ, kết luận live chưa kiểm chứng/chưa đạt, bản offline vẫn có thể nghiệm thu riêng.

## Bàn giao

Task08 nhận số liệu thật và danh sách hạn chế. Không train lại model trong task này trừ khi được mở phạm vi sau dự án một tuần.
