# Task07A — phương án dữ liệu trước fine-tune

**Đã duyệt hướng dataset-first ngày2026-11-05**, phạm vi QA ảnh/split và chuẩn bị pilot cục bộ, chưa train/đổi weights/chi phí. [Report thực thi](task07a-dataset-first-20261105.md) và [review guide](../guides/task07a-dataset-label-review.md) bàn giao359frame draft. Không hỏi lại phê duyệt hướng; chỉ trình training cụ thể sau labels/QA/split/recipe/cost.

Ngày2026-11-05. **Đề xuất để duyệt hướng tiếp theo; chưa phải lệnh train hoặc phê duyệt chi phí.** [Checkpoint đã thực hiện](task07a-improvement-checkpoint.md) xác nhận preprocessing tái lập và các cấu hình mới không vượt baseline.

## Phương án đề xuất

Giữ kiến trúcYOLO26s và baseline hiện tại. Chuẩn bị dataset bổ sung có chủ đích cho bóng rất nhỏ, bóng trên tay/trên không, che khuất còn nhìn được và background poster/khán đài. Chỉ fine-tune sau label QA và split audit; chưa tăng epochs trên toàn bộ dataset hiện tại một cách mù quáng.

### D1 — Chốt dữ liệu và kiểm tra nguồn

- Lấy frozen dataset version/annotations tương ứng training gốc để đối chiếu với current project geometry. Đây là phần chưa có local export; metadata hiện đọc được chưa thay thế kiểm tra ảnh.
- Kiểm tra ảnh thật cho các mẫu tiny-ball, close-up và hard negatives; rà missing labels, bbox tightness và chính sách visible/occluded. Giữ3classes ball/human/rim thì phải gán nhãn đủ các class được train, không chỉ thêm ball rồi bỏ human/rim.
- Kiểm tra hash/perceptual/source-group cho nguy cơ cùng filename family ở train/test. Split theo nguồn/trận, không phân ngẫu nhiên frames gần nhau. Không sửa locked v1/v2 hoặc dùng lại nhóm đã exposure làm independent holdout.
- Lập distribution kích thước bóng sau đúng pipeline full/tile và preprocessing, không chỉ kích thước ảnh. Đối chiếu với footage thực tế.

**Đầu ra review:** dataset manifest, label-policy notes, size/domain distribution, source grouping và leakage warnings đã đối soát. Báo riêng phần chưa thể kết luận.

### D2 — Chuẩn bị pilot bổ sung, chưa train

Ước lượng vòng đầu300–500frame chọn lọc, là ngân sách annotation đề xuất chứ không phải số lượng bảo đảm đạt90%. Chọn theo độ đa dạng/chuyển trạng thái thay vì trích liên tiếp: bóng nhỏ, trên tay, flight/rim, dribble, occlusion/deflection và background dễ nhầm. Negative frame vẫn cần nhãn human/rim đúng nếu giữ3classes.

Chỉ sử dụng nguồn có quyền dùng đã xác nhận. Nếu dùng clip development Việt Nam–Tonga vào training, công bố exposure và không dùng nó làm test độc lập. Giữ nhóm validation/test chưa train/tune; nếu chỉ có một trận thì kết luận giới hạn same-match pilot, không tổng quát.

Có thể dùng current detector làm gợi ý annotation nhưng người review phải sửa miss/false positives từ nguồn; không tự chuyển predictions thành approved GT. Không upload dữ liệu/ghi annotation cloud ngoài phạm vi người dùng duyệt. Roster, protocol và quyền OCR local đã có không cần xin lại.

**Đầu ra review:** ảnh/nhãn cục bộ, thống kê chất lượng và manifest splits, danh sách case khó, dữ liệu regression human/rim. Chưa đổi weights/runtime đang dùng.

### D3 — Chốt training recipe trước xin chạy

- Xác minh raw checkpoint đúng model: API có cấp URL nhưng file/format/resume compatibility chưa được kiểm tra. Không thay bằng random initialization rồi gọi là tiếp tục train model cũ.
- GiữYOLO26s; thiết kế preprocessing/crop phù hợp inference và mix dữ liệu cũ/mới có validation để theo dõi regression. Recipe cụ thể cần xác minh khả năng backend; chưa ấn định epochs/LR mà không có lý do.
- Chọn môi trường training tách khỏi runtime ONNX CPU hiện hành. Xác minh tài nguyên, chi phí/credits, giới hạn và tiêu chí dừng trước khi trình người dùng. Chưa cài GPU stack, không khởi tạo job training hoặc generate phiên bản cloud.
- Lưu model candidate thành version mới, không ghi đè approved model. Sau export kiểm tra lại ONNX/runtime/class mapping và latency.

**Đề nghị phê duyệt training sau khi D1–D3 đủ:** dataset/version/hash, checkpoint, recipe, tài nguyên/chi phí, phạm vi media upload nếu có, điều kiện chọn/rollback. Không coi phê duyệt hướng dữ liệu là quyền chi tiền/chạy training không giới hạn.

## Tiêu chí chọn model candidate

So baseline với candidate bằng cùng nguồn/GT và protocol, báo ball recall/false observations, strict control/pass và latency; thêm regression human/rim. mAP/recall headline trên Roboflow không thay thế phép đo trên video mục tiêu. Candidate mới không được dùng GT làm recognition input hoặc manual corrections để tăng automatic metrics.

Giữ ngưỡng dự án: observed ball≥90%, strict control≥90%, pass precision≥95%/recall≥90% và integrity guards. Candidate detector tốt hơn vẫn cần07Btemporal attribution và07Cvalidation. Nếu chưa đạt thì không promote/không gọiTask07DONE; ghi thất bại và chi phí đã dùng.

**Checkpoint hiện tại:** duyệt hướng dataset-first để hoàn thiện07A thay vì tiếp tục tăng input size/letterbox không có bằng chứng. Chưa đủ điều kiện phê duyệt một training job cụ thể; mọi chi phí và thay weights phải được duyệt sau khi proposal đầy đủ.
