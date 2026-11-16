# Task07A — kết quả dataset-first QA và pilot cục bộ

Ngày2026-11-05. Thực hiện theo phê duyệt người dùng “Duyệt hướng dataset-first”. **Đã có QA mẫu ảnh thật và pilot359frame với model-assisted draft labels; chưa train-ready.** Không train, thay inference weights/backend, upload media, ghi annotation/split cloud hoặc phát sinh training job. Task07 IN_PROGRESS; accuracy baseline không đổi.

## D1 — QA dataset gốc bằng ảnh thật

Đã tải27ảnh:24mẫu cóball (8ảnh đầu từ mỗi train/valid/test query) và3ảnh cùng filename family để kiểm tra cảnh báo. Đây là mẫu có chủ đích/ordered, không phải random sample đại diện9515ảnh. Tải từ URL riêng Roboflow qua HTTPS, không lưu/công bố signed URLs. Pixel dimensions của27ảnh khớp annotation dimensions; overlay dùng đúng geometry hiện tại.

[Gallery ảnh gốc và stored labels](../../codebase/outputs/task07a-dataset-first-20261105/original-image-qa/review.html), [contact sheet](../../codebase/outputs/task07a-dataset-first-20261105/original-image-qa/contact-sheet.jpg), [QA findings](../../codebase/outputs/task07a-dataset-first-20261105/original-dataset-qa-findings.json).

### Đã xác minh shared source giữa train/test hiện tại

Family `89CW1YC6FXUH.jpg` có2ảnh train và1ảnh test: indices24/25/26trong gallery. Cùng ảnh bóng và bàn tay, có khác resize/rotation. Đối chiếu SIFT/RANSAC sau kiểm tra trực quan:

| Cặp | Good matches | Inliers | Inlier ratio | Overlap sau đăng ký | Gray MAE trên overlap, thang0–255 |
|---|---:|---:|---:|---:|---:|
| Train24 → Test26 |50|47|94%|93.59%|0.874|
| Train25 → Test26 |60|57|95%|93.81%|0.937|

Đây là bằng chứng cùng ảnh nguồn qua augmentation ở **current project splits**, không chỉ đoán từ filename. Chưa kiểm tra frozen version export để khẳng định membership tại đúng thời điểm training version1; chưa định lượng tác động lên headline metrics. Không tuyên bố toàn bộ dataset bị leak hoặc metrics96.39%mAP50 là giả.

Cặp12valid/17test cópHash distance0và cùng bối cảnh sân/camera; registration1345/1376inliers, grayMAE8.61. Đây là cảnh báo frames/source group tương quan, không tự gọi là exact duplicate. Train2/valid9cũng có source filename/court tương tự. Cần source-group audit toàn tập trước chia split mới.

[Registration evidence](../../codebase/outputs/task07a-dataset-first-20261105/original-image-qa/source-family-registration.json). Hash/phash, original byte hashes và current annotations nằm trong manifest. Không sửa project cloud hoặc original locked local datasets.

### Vấn đề dữ liệu cần ưu tiên

- Có cả ảnh sản phẩm/portrait/close-up bóng lớn và footage sân. Kết quả27mẫu không đủ tính tỷ lệ domain toàn tập; cần chốt phân bố target footage thay vì thêm ảnh ngẫu nhiên.
-32ball boxes trong24mẫu split có median projected min-side24.5px ở640; video development full-frame≈8.3px, best-containing tile≈15px. Đây là dấu hiệu mismatch về scale trong mẫu, không chứng minh thiếu mọi bóng nhỏ trong9515ảnh.
- Một số ảnh có nhiều bboxball partial/adjacent, crowd và rim extent cần đối soát bằng policy trước relabel. Không tự kết luận tất cả annotation đó sai từ contact sheet.
- Khi fine-tune từ checkpoint cũ, không được chuyển nhóm từng nằm trong old training sang test rồi gọi là unseen: checkpoint đã có exposure. Split cleanup cần giữ lịch sử nguồn và model exposure.

**Quyết định D1:** ưu tiên source-family cleanup, consistency label và bổ sung tiny-ball/hard-background data. Một lỗi split được xác minh không tự giải thích mọi31detector misses; cần test sau cải thiện dữ liệu.

## D2 — pilot359frame đã chuẩn bị

Nguồn duy nhất: Việt Nam–Tonga SHA-256 `1443c1d263c8037a5684f3dbc0ef9216beb5097d9a47c4c1c9b94d1363e26865`.

6windows60s: parent360–420,540–600,720–780,900–960,1080–1140,1200–1260s. Seek/decode từng đoạn, lấy1frame/s từPTS thật, không đọc GT hay dùng vị trí bóng để chọn crop. Yêu cầu360frame, loại1frame trùng pixel tại743s với frame đã giữ742s, còn359ảnh1920×1080. JPEG95là derived frame, không pixel-identical với video decode; lưu cả source pixel hash và saved-image hash.

Mẫu gồm wide play, shot/dribble, closeup, replay/transition/timeout và background. Scene/visibility chưa gán chắc chắn; không tự gọi ảnh không có model detection là negative. Tất cả split **unassigned**, cùng source group `vietnam_tonga_same_match_2025`; không independent match validation/test.

Artifacts tại `codebase/outputs/task07a-dataset-first-20261105/pilot-candidate/`:

- [Source sampling audit](../../codebase/outputs/task07a-dataset-first-20261105/pilot-candidate/sampling-audit.json), [source contact sheet](../../codebase/outputs/task07a-dataset-first-20261105/pilot-candidate/contact-sheet.jpg).
- `annotations-draft.json`:359source-bound samples, boxes=null/unreviewed, training_ready=false. Null không phải empty negative; không có YOLO training labels.
- [Model review UI](../../codebase/outputs/task07a-dataset-first-20261105/pilot-candidate/model-review/review.html), [gợi ý và runtime](../../codebase/outputs/task07a-dataset-first-20261105/pilot-candidate/model-review/run.json).

Đã dùng đúng approved localYOLO26s/ONNX CPU để gợi ý cả3classes:2758human/263rim/704ball boxes. **Các số này là predictions, không phải nhãn đúng hoặc accuracy.** Gợi ý tách riêng khỏi packet nguồn, cần reviewer sửa miss/false positives và kiểm tra đủ vật thể thật. Không có training hoặc cloud inference.

UI cho nạp gợi ý, chọn class, vẽ/xóa bbox, xác nhận scene/ball visibility, bỏ ảnh có lý do, lưu draft và nạp tiếp. Guard kiểm tra source/frame/PTS và policy; ảnh sửa trở lại unreviewed, reviewed export không tự cho phép training. Validator Python độc lập từ chối draft/null labels, source tampering, class/bounds sai, visibility mâu thuẫn và không có ảnh được duyệt.

## Kiểm tra và giới hạn

- Regression: **257tests PASS**,0failures/errors/skipped; [summary](../../codebase/outputs/task07a-dataset-first-20261105/tests-dataset-first.json), [log](../../codebase/outputs/task07a-dataset-first-20261105/tests-dataset-first.log).
- Pilot nguồn đủ359samples sau dedup; image hashes/sourcePTS và prediction/image binding được kiểm tra. Metadata không dùng làm oracle labels.
- Review JavaScript qua `node --check`, bbox/visibility guards chạy trênfixtures; draft packet thật bị CLI từ chối. Chưa browser end-to-end acceptance.
-27download images đều decode thành ảnh và không có mismatch kích thước so annotation. SIFT evidence được lưu; no full-dataset or frozen-version pixel QA claim.
- Chưa có human-reviewed pilot labels, chưa xuất YOLO, chưa download/load native train checkpoint, chưa tạo dataset version cloud hoặc train job. Các inference model weights đã dùng vẫn là model approved cũ.

## Bước người dùng review và công việc tiếp theo

Đọc [hướng dẫn review](../guides/task07a-dataset-label-review.md). Nên review10–20ảnh đầu và một số closeup/background để chốt policy, rồi lưu draft theo batch. Sau khi review, lưu packet vào `codebase/outputs/task07a-dataset-first-20261105/reviewed-task07a-pilot.json` và báo đường dẫn. Không cần cấp lại roster/protocol/API key hoặc sửa control/pass.

Agent sẽ validate packet, thống kê labels/skip reasons và case khó, chốt source-family cleanup và chuẩn bị dataset version cục bộ. Trước train còn cần frozen dataset audit, consistent label policy, checkpoint/recipe compatibility và tài nguyên/chi phí để duyệt riêng. Không dùng một trận đã train/tune để chứng minh khả năng mọi video; cần nguồn khác cho independent-match test, hoặc giới hạn rõ same-match pilot.

**Trạng thái:** hướng dataset-first đã được duyệt và thực hiện phần prep. D1QA mẫu hoàn tất với phát hiện cụ thể; D2draft pilot sẵn review; D3training chưa mở. Gate07Aaccuracy chưa đạt,07Bimplementation/07Cacceptance chưa được coi đã qua. Chưa cần xin phê duyệt training khi labels/splits/recipe/cost chưa đủ để review.
