# Checkpoint07A — preprocessing, detection và dữ liệu

Cập nhật sau phê duyệt: người dùng đã duyệt dataset-first; [QA ảnh thật và pilot359frame](task07a-dataset-first-20261105.md) đã chuẩn bị,257tests PASS. Đã xác minh shared source photo train/test ở current project, chưa sửa cloud; pilot có gợi ý nhãn chờ review, chưa train-ready. Không hỏi lại hướng dataset-first; các đoạn đề xuất chờ duyệt phía dưới là snapshot trước quyết định này.

2026-11-05. **A1 tái lập PASS; A2 đã đo và giữ baseline; accuracy Task07A chưa đạt.** Không train/thay weights/backend, không upload video. Task07 IN_PROGRESS. [Roadmap](task07-improvement-roadmap-20261105.md) là phạm vi thực thi; chưa chuyển sang07B implementation hoặc07C.

ROOT dưới đây là `codebase/outputs/task07a-improvement-checkpoint-20261105/`.

## 1. Thay đổi đã thực hiện

- `ObjectDetector.detect` hỗ trợ optional network input WH, kiểm tra integer/divisible32/range320–2048. Mặc định không đổi SDK arguments hoặc bbox mapping. Không chỉ upscale ảnh rồi để SDK resize về cùng size.
- Diagnostic observer chỉ dùng cho SDK CPU session, ghi shape array thực sự truyền vào ONNX và khôi phục original session cả khi có lỗi. Không sửa source của SDK, không lưu pixel tensor/API keys.
- Runner GT-free lấy frame0,8,16,…,896 theo lịch cố định trên video30s. Mỗi profile113frames, full-frame+4tiles, cùng confidence0.15, overlap0.2, exclusions và NMS. Chỉ xuất ball candidates; không dùng thử nghiệm này để đo OCR/control.
- Probe đối chiếu metadata SDK preprocessing với tensor ONNX thật. Inference outputs và source snapshot lưu tách khỏi evaluator; GT chỉ được đọc sau inference.
- Chuẩn bị204jersey crops/context từ raw local OCR frames cộng fixed schedule, không đọc GT hoặc gọi lại OCR. Tất cả label vẫn draft/unreviewed, chưa có OCR accuracy mới.

Source mới: `codebase/src/basketball_scoreboard/preprocessing_diagnostics.py`, `codebase/scripts/run_task07a_preprocessing_checkpoint.py`, `codebase/scripts/evaluate_task07a_preprocessing_checkpoint.py`. Settings tại `codebase/configs/task07a/preprocessing-checkpoint.json` và `preprocessing-letterbox-checkpoint.json`.

## 2. A1 — bằng chứng tái lập

[Probe](../../codebase/outputs/task07a-improvement-checkpoint-20261105/probe-authorized/probe.json) xác nhận:

| Tùy chọn | ONNX input thật | Preprocessing |
|---|---|---|
| SDK mặc định |1×3×640×640|Stretch, không padding|
| Explicit640×640 |1×3×640×640|Giống mặc định; predictions tương đương ở probe|
| Explicit960×960 |1×3×960×960|Stretch, không padding|

Video gốc1920×1080 được SDK stretch với scale_x=1/3,scale_y≈0.59259 ở640. Wrapper trả bbox theo source đúng qua SDK, không unscale input mạng lần thứ hai.

[Controlled evaluation](../../codebase/outputs/task07a-improvement-checkpoint-20261105/evaluation/evaluation.json) so baseline replay với raw tiled cache cũ: **113/113frames tương đương**, tolerance bbox1e-6px/confidence1e-4; không có frame khác. Candidate hits41/72 và unmatched102 được tái lập. Các source/hash và ONNX weights fingerprint có trong runtime/run files, kèm source snapshot đủ cho lượt mới. Không suy đoán rằng đã khôi phục exact wrapper lịch sử ngày05/11; đã tạo revision mới có kiểm chứng.

Probe sandbox ban đầu bị RetryError khi lấy metadata; artifact failed được giữ tại `probe/`. Sau khi chạy ngoài sandbox theo quyền xác thực đúng model đã có, probe và inference local hoàn tất. Không cloud inference hoặc upload media.

## 3. A2 — so sánh tách biến

Giữ cùng video, sampling, weights, CPU/ONNX, tiling và confidence. Trial960 chỉ đổi network size640square→960square, giữ stretch/aspect policy. Trialletterbox giữ network640square nhưng resize giữ tỷ lệ và pad đen trước SDK; inverse mapping clip bỏ bbox chỉ nằm trong padding đã qua tests.

| Profile | GT candidate hits /72 | Candidate recall | Unmatched candidates tại mẫu GT | SDK detection-call time,113frames/565calls |
|---|---:|---:|---:|---:|
| Baseline mặc định |41|56.94%|102|98.45s|
| Square960 |39|54.17%|104|234.26s|
| Letterbox640 |18|25%|52|56.12s|

960 tốn khoảng2.38× SDK-call time, không tăng recall. Letterbox giảm unmatched nhưng bỏ sót nhiều hơn; không promote. SDK-call time không phải end-to-end latency: letterbox resize nằm ngoài model-call timer, metadata inspection và decode cũng không nằm đầy đủ trong cột đó. Run wall times lưu riêng. Không kết luận letterbox nhanh hơn cho sản phẩm chỉ từ cột này.

[Evaluation letterbox](../../codebase/outputs/task07a-improvement-checkpoint-20261105/letterbox-evaluation/evaluation.json). Đây là **candidate diagnostics trên72visible/certain GT samples**, không phải observed tracking recall, full-video precision hoặc independent validation. Không chạy thêm900frame temporal pipeline cho cấu hình đã regression ở candidate stage. Continuous baseline vẫn là v4: observed recall36/72=50%, strict control0%, pass recall0%, precision N/A.

Đã đo kích thước bóng ở các vùng thực sự infer: full-frame640 có median min-side≈8.3px theo projection trước; xét vùng full/tile chứa đủ bbox, best projected median baseline≈15px,960≈22.5px. Độ phân giải tăng tạo thêm pixels nhưng candidate recall vẫn giảm trong phép thử này. [Effective input-size diagnostics](../../codebase/outputs/task07a-improvement-checkpoint-20261105/effective-ball-input-size.json). Vì baseline có tiling, không lấy8.3px full-frame để mô tả mọi lần gọi model.

## 4. A3 — audit Roboflow read-only

Đã dùng connector Roboflow đọc đúng project/version/model, tìm ảnh và đọc annotation geometry; không ghi annotation, tạo version, export dataset hoặc training job.

- Project có9515ảnh, platform báo unannotated0; split6662train/1893valid/960test; counts ball9597/human20647/rim6744.
- Version1 có training finished cho đúng modelYOLO26s. Model metadata báo mAP50=96.39%,precision93.4%,recall94.3%,F1=93.9%. Chưa xác minh split/protocol và per-class breakdown của các headline metrics; không gọi đây là ball accuracy trên video mới.
- API listing không trả existing model-evaluation records cho project/version này; không tạo eval mới tốn inference. Các headline legacy metrics vẫn có, không suy ra model chưa từng được đánh giá.
- API cấp được URL tạm cho raw checkpoint của đúng model. **Chưa tải file, chưa xác minh format/resume compatibility; URL riêng không lưu hoặc công bố.** Không có native `.pt` hoặc original dataset YOLO export được tìm thấy cục bộ trong phạm vi đã kiểm tra.

[Project/version/6semantic samples](../../codebase/outputs/task07a-improvement-checkpoint-20261105/roboflow-dataset-readonly-audit.json), [24stratified annotation samples và checkpoint availability](../../codebase/outputs/task07a-improvement-checkpoint-20261105/roboflow-stratified-annotation-audit.json).

### Những dấu hiệu có ích, chưa phải kết luận toàn dataset

1. Sáu semantic search hits có ball min-side quy về stretch640≈220–299px. Đây là mẫu thiên lệch theo truy vấn, không đại diện dataset.
2. Đọc thêm8image IDs đầu trả về cho mỗi split có classball:24ảnh/32ball boxes. Min-side quy về640 có min9,median24.5,max640px;7/32≤12px,0/32≤8px. Mẫu video full-frame nhỏ hơn đáng kể; xét tile, median≈15px vẫn nhỏ hơn median24.5 của mẫu dataset. Đây là dấu hiệu cần audit scale/domain, không chứng minh toàn9515ảnh thiếu bóng nhỏ. [Stratified size summary](../../codebase/outputs/task07a-improvement-checkpoint-20261105/stratified-size-summary.json).
3. Trong6semantic hits có filename family `89CW1YC6FXUH` xuất hiện ở train và test với suffix `.rf` khác nhau. Cần so ảnh/hash/source trước xác nhận leakage; chưa gọi là duplicate đã chứng minh. Mẫu24ảnh không có cảnh báo filename family kiểu đó.
4. Các geometry là annotations hiện tại của project, chưa đối chiếu pixel và frozen version export. Bbox phủ gần cả ảnh có thể là ảnh close-up hoặc nhãn cần sửa; không tự kết luận nhãn sai chỉ từ geometry.

**Kết luận A3:** chưa có cơ sở nói thiếu tổng số ảnh. Ưu tiên kiểm tra ảnh/nhãn, source splits và mức phù hợp của dữ liệu bóng rất nhỏ/background trận đấu, thay vì thêm ảnh ngẫu nhiên hoặc chỉ tăng epochs. Chưa chứng minh nguyên nhân gốc duy nhất là domain gap; crop preprocessing, annotation policy và model capability vẫn cần đối soát.

## 5. Chuẩn bị độc lập cho07B

[Source crop gallery](../../codebase/outputs/task07a-improvement-checkpoint-20261105/identity-review-preparation/review.html) và `annotations-draft.json`:204crops, gồm actual OCR-reading frames và frames định kỳ mỗi90frames có observed player role. Trang gallery không hiển thị số model đọc làm đáp án; raw readings lưu riêng để đối chiếu sau review.

Chưa có labels được review, không tính exact jersey accuracy và không đổi identity engine. Sampling dựa raw tracking/cached reads, có bias và không đại diện OCR recall toàn trận. Crop preparation không có nghĩa checkpoint07B đã đạt; chưa triển khai Kalman/control/pass mới.

## 6. Kiểm thử, integrity và checkpoint tiếp theo

Regression cuối: **251tests PASS**,0failures/errors/skipped,17.55s. [Summary](../../codebase/outputs/task07a-improvement-checkpoint-20261105/tests-checkpoint-final.json), [log](../../codebase/outputs/task07a-improvement-checkpoint-20261105/tests-checkpoint-final.log). Các tests mới kiểm tra default kwargs, explicit network WH, invalid sizes, bbox unscale, actual ONNX-feed trace, restore session khi lỗi, round-trip letterbox với rounding và padding-only boxes. Source inputs, approved GT, baseline outputs và locked datasets được kiểm tra lại trước bàn giao. Artifact audit không thay thế accuracy.

**Quyết định đề xuất:** giữ v4 làm baseline development; không promote square960 hoặc letterbox640. A1 đã hoàn tất phần tái lập, A2 đã kiểm tra hai giả thuyết có kiểm soát nhưng không đạt90%; A3 mới audit metadata/geometry samples, chưa đủ label QA/training readiness.

Theo [phương án dữ liệu tiếp theo](task07a-data-finetune-proposal.md), checkpoint cần duyệt **hướng dataset-first cho07A**. Trước training phải có tập nhãn/splits được review, checkpoint tương thích, recipe/runtime và chi phí được xác minh; không xin một phê duyệt train chung chung. Chưa đủ điều kiện chuyển07B implementation hoặc07C acceptance. Các ngưỡng ball/control/pass đã duyệt giữ nguyên.

## Tái chạy

Lệnh từ workspace root, dùng output directory mới. `--stage compare` không nhận GT:

```powershell
codebase/.venv/Scripts/python.exe codebase/scripts/run_task07a_preprocessing_checkpoint.py --video codebase/outputs/task07-vietnam-tonga-segments-20261104/media/vt_development.mp4 --settings codebase/configs/task07a/preprocessing-checkpoint.json --stage probe --output-dir codebase/outputs/task07a-next-probe
codebase/.venv/Scripts/python.exe codebase/scripts/run_task07a_preprocessing_checkpoint.py --video codebase/outputs/task07-vietnam-tonga-segments-20261104/media/vt_development.mp4 --settings codebase/configs/task07a/preprocessing-checkpoint.json --stage compare --output-dir codebase/outputs/task07a-next-comparison
codebase/.venv/Scripts/python.exe codebase/scripts/evaluate_task07a_preprocessing_checkpoint.py --experiment-dir codebase/outputs/task07a-next-comparison --ground-truth codebase/data/matches/vietnam_tonga/reviewed-vt_development-v2.json --baseline-detections codebase/outputs/task07-vietnam-tonga-segments-20261104/development-tiled/detections.jsonl --output-dir codebase/outputs/task07a-next-evaluation
```

Đổi settings sang `preprocessing-letterbox-checkpoint.json` để tái chạy trialletterbox. SDK session initialization có thể cần kết nối metadata dù inference local. Không tái dùng các output directories đã có hoặc coi cache cũ là một lần thử mới.
