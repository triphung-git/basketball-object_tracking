# Kế hoạch dự án Basketball Scoreboard

Tiến độ nghiệm thu 2026-11-01: task01 PASS, task02 PASS cho bộ dữ liệu pilot (7 video, 10 nhãn approved; test có 7 lượt trong một session). Task03 sẵn sàng bắt đầu, chưa được triển khai. Đọc [báo cáo nghiệm thu](docs/reports/task01-task02-acceptance.md) và [bàn giao task03](docs/handoffs/task03.md) để biết evidence, giới hạn CPU/offline, split locked và yêu cầu timestamp VFR.

## 1. Mục tiêu và phạm vi

Xây dựng ứng dụng Python phát hiện bóng, vành rổ, người; tracking người và quỹ đạo bóng; nhận diện bóng vào rổ; cập nhật scoreboard và xuất kết quả. Thời gian dự kiến: 7 ngày làm việc tập trung. Đây là kế hoạch triển khai, chưa phải các tính năng đã hoàn thành.

MVP: một camera cố định, một rổ nhìn rõ, mỗi lượt một bóng; chạy MP4 trước, webcam sau nếu phần cứng đáp ứng. Người dùng chọn giá trị lượt ném 1/2/3 điểm và đội A/B trước lượt. Máy tự phát hiện bóng vào rổ. ID tracking chỉ là ID tạm thời, không phải danh tính cầu thủ.

Không thuộc MVP: tự phân biệt 1/2/3 điểm, tự nhận đội/người ghi điểm, luật trận đấu, camera di chuyển, video truyền hình cắt cảnh, nhiều bóng, nhiều camera, cloud deployment. Không suy ra thời gian thi đấu chính thức từ thời lượng video.

## 2. Cơ sở đã kiểm tra

Roboflow đã trả về model `phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1`: YOLO26s, object detection, train finished; mAP50 96,39%, precision 93,4%, recall 94,3%. Project có 9.515 ảnh và classes `ball`, `rim`, `human`. Đây là metrics detection được dịch vụ trả về, chưa xác nhận tập đánh giá hay hiệu quả trên video mục tiêu. Chưa kiểm chứng runtime, quyền tải weights, tốc độ máy và chất lượng đếm điểm.

## 3. Phân công

| Bạn cung cấp/thực hiện | Tôi xây dựng/thực hiện |
|---|---|
| Cấu hình CPU, GPU/VRAM, RAM, hệ điều hành | Khảo sát môi trường, chọn runtime và khóa dependency |
| Video MP4 gốc có quyền sử dụng, đặc điểm camera | Pipeline đọc nguồn, detection và xuất video |
| Quyền truy cập model qua cấu hình cục bộ | Adapter model, kiểm tra class mapping và lỗi truy cập |
| Gán nhãn thủ công lượt vào/trượt và thời điểm | Tracking, máy trạng thái, chống đếm lặp |
| Chọn vùng rổ, đội và điểm mỗi lượt | Công cụ cấu hình, scoreboard, undo/reset |
| Thử nghiệm tại sân nếu muốn webcam | Benchmark, báo cáo lỗi, tài liệu, đóng gói demo |
| Xác nhận tính đúng của video kết quả | Hướng dẫn và phân tích kết quả; không tự tạo ground truth thay bạn |

Không gửi API key vào chat, ảnh chụp hay commit. Bạn cấu hình biến môi trường trên máy chạy; tôi cung cấp mẫu cấu hình không chứa bí mật. Không mặc định model có thể export hoặc chạy bằng mọi YOLO runtime.

## 4. Checklist đầu vào

- [ ] Thông tin CPU/GPU/VRAM/RAM và Python hiện có.
- [ ] 2–3 clip ngắn để thử triển khai, thấy rõ bóng trên và dưới vành rổ.
- [ ] Khoảng 50–100 lượt ném tổng cộng cho hiệu chỉnh và đánh giá; có vào, trượt, bật vành, che khuất. Đây là quy mô mục tiêu, không phải điều kiện phải đủ mới bắt đầu.
- [ ] Video gốc kèm FPS/độ phân giải nếu biết; không chỉ gửi video overlay bbox.
- [ ] Ground truth theo mẫu ở task02; ghi rõ trường hợp không thể kết luận bằng hình ảnh.
- [ ] Chọn chế độ cá nhân hoặc A/B thủ công; mặc định cá nhân, mỗi lượt 2 điểm.
- [ ] Nếu dùng webcam: camera, khoảng cách/góc quay và quyền truy cập thiết bị trên máy.

## 5. Kiến trúc và nguyên tắc

`MP4/Webcam → frame + timestamp → model adapter → detections → person tracker + ball trajectory → shot state machine → event store → scoreboard/overlay/export`

Python, OpenCV; runtime inference được chốt sau smoke test đúng model; tracking người bằng ByteTrack qua API tương thích phiên bản đã khóa. Bóng dùng ghép vị trí/vận tốc theo thời gian, chỉ thêm Kalman khi cần. Rổ cố định theo ROI người dùng xác nhận. CSV/JSON đủ cho MVP; không cần database/backend/frontend riêng.

Tách thời gian video khỏi thời gian chạy máy. Rule dùng giây và tọa độ chuẩn hóa/đơn vị kích thước rổ. Detection thiếu không được biến thành bằng chứng bóng vào. Score xuất phát từ sự kiện có ID; chỉnh sửa lưu lịch sử.

## 6. Task và lịch

| ID | Task | Ngày | Phụ thuộc | Tài liệu |
|---|---|---|---|---|
| 01 | Chốt đầu vào, môi trường, runtime model | 1 | Không | [task01](docs/tasks/task01.md) |
| 02 | Chuẩn bị video và ground truth | 1–2 | Bắt đầu độc lập; chốt scope ở 01 | [task02](docs/tasks/task02.md) |
| 03 | Pipeline detection và xuất kết quả | 2 | 01 + clip từ 02 | [task03](docs/tasks/task03.md) |
| 04 | Tracking và cấu hình vùng rổ | 3 | 03 | [task04](docs/tasks/task04.md) |
| 05 | Nhận diện ghi điểm, chống đếm lặp | 4 | 04 + nhãn từ 02 | [task05](docs/tasks/task05.md) |
| 06 | Scoreboard và điều khiển | 5 | 05 | [task06](docs/tasks/task06.md) |
| 07 | Đánh giá và tối ưu real-time | 6 | 02–06 | [task07](docs/tasks/task07.md) |
| 08 | Đóng gói, demo và báo cáo | 7 | 07 | [task08](docs/tasks/task08.md) |

Task02 có thể tiến hành cùng task01. Mỗi task cập nhật trạng thái `TODO / IN_PROGRESS / BLOCKED / DONE`, bằng chứng nghiệm thu và vấn đề còn mở trong chính tài liệu task. Lịch là ước lượng, phụ thuộc đầu vào và runtime.

## 7. Cấu trúc đầu ra dự kiến

Cập nhật 2026-10-31: toàn bộ source, scripts, dependency, config, dữ liệu cục bộ và outputs đặt dưới `codebase/`. Các đường dẫn kỹ thuật bên dưới là tương đối với `codebase/`, ngoại trừ `docs/` nằm tại gốc dự án. Tài liệu cần đọc trước sửa code: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md), task liên quan và báo cáo môi trường.

```text
src/basketball_scoreboard/
  app.py, config.py, video.py, detector.py, tracking.py
  scoring.py, scoreboard.py, events.py, overlay.py
configs/default.yaml
data/raw/                 # không commit video lớn
data/annotations/events.csv
data/splits.json
outputs/<run_id>/         # video, log, metrics, config snapshot
tests/                   # tập trung logic sự kiện và điểm
scripts/evaluate.py
requirements.txt
.env.example, .gitignore, README.md
docs/tasks/task01.md ... task08.md
docs/reports/
```

Các đường dẫn mã nguồn là thiết kế dự kiến; chỉ bộ kế hoạch được tạo ở giai đoạn hiện tại.

## 8. Nghiệm thu toàn dự án

1. Từ môi trường sạch, làm theo README chạy được MP4 và xuất video + events + metadata.
2. Hiển thị detection, ID người, đường bóng, vùng rổ, trạng thái và điểm; pause/undo/reset hoạt động.
3. Một lượt vào không sinh nhiều sự kiện; có kiểm tra vào, trượt, bật vành, mất bóng và timeout.
4. Có ground truth độc lập, định nghĩa matching, TP/FP/FN, precision/recall, đếm trùng, sai lệch điểm và bảng lỗi. Đánh giá log tự động trước chỉnh sửa.
5. Mục tiêu ban đầu: precision sự kiện ≥95%, recall ≥90% trên tập góc quay đã chọn; không bảo đảm trước khi đo. Nếu không đạt, báo trung thực và ghi giới hạn, không chỉnh ngưỡng bằng test set.
6. Real-time chỉ được công bố khi tốc độ xử lý bền vững đạt FPS nguồn trong điều kiện benchmark đã ghi và độ trễ không tăng dần. Nếu không đạt, bàn giao bản xử lý video offline kèm số đo; đánh dấu yêu cầu live chưa đạt.
7. Không chứa API key, đường dẫn cá nhân bắt buộc hoặc tuyên bố hiệu năng chưa đo.

## 9. Rủi ro và quyết định giảm phạm vi

| Rủi ro | Hành động |
|---|---|
| Model không chạy được ở runtime chọn ban đầu | Xác minh deployment chính thức/quyền truy cập ngay ngày 1; thử endpoint được hỗ trợ; không tự giả định weights export |
| CPU chậm hoặc inference mạng trễ | Đo baseline; thử crop/resize có đánh giá lại bóng nhỏ; ưu tiên MP4; ghi live chưa đạt nếu cần |
| Bóng khuất hoặc xuyên rổ giữa các frame | Cải thiện góc quay/FPS, giữ quan sát gần rổ; bỏ qua trường hợp không đủ bằng chứng thay vì tự cộng |
| Bóng trượt có hình chiếu giống bóng vào | Thu video phản ví dụ, tối ưu ROI/rule; thừa nhận giới hạn 2D |
| Thiếu thời gian | Giữ app OpenCV, bỏ dashboard/webcam trước; giữ đánh giá và log |
| Thiếu video đánh giá | Bàn giao demo và kết quả trên mẫu nhỏ, ghi cỡ mẫu; không gọi là đã đạt độ chính xác tổng quát |

## 10. Cách bắt đầu

Bạn chuẩn bị checklist đầu vào, ưu tiên cấu hình máy và 2–3 clip mẫu. Bước triển khai đầu tiên là task01: chứng minh đúng model chạy được trên máy với clip thật, rồi mới xây các module còn lại. Kế hoạch này chưa tạo workflow, chưa chạy inference trả phí và chưa thay đổi model trên Roboflow.
