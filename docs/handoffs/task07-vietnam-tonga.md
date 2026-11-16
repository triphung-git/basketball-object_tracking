# Handoff Task07 — Vietnam–Tonga, 2026-11-04

Candidate development mới: [spatial reliability v4](../reports/task07-spatial-reliability-20261104.md),240tests PASS, ball recall50% và0observed ngoài vùng tìm kiếm khai báo; không đồng nghĩa0false positives. Strict control/pass vẫn0%; chưa chứng minh OCR accuracy tăng. Dùng `development-spatial-v4/` để xem thử bản sửa, giữ baseline/raw cache cũ. V4 chỉ tune development, chưa rollout validation và chưa nghiệm thu.

Cập nhật hiện hành: đã áp dụng xác nhận Việt Nam #6/Tonga #11, canonical GT là `codebase/data/matches/vietnam_tonga/reviewed-vt_development-v2.json`. [Full evaluation](../reports/task07-development-evaluation-v2-20261104.md) tại `reviewed-development-evaluation-v2/evaluation.json` trả `failed_criteria`: ball43.06%, strict control0%, pass recall0%, precision N/A. Có đủ sample tối thiểu; cần cải thiện recognition thực tế, không chỉ chờ review. File gốc và raw predictions giữ nguyên. Không hỏi lại hai xung đột đã chốt. Validation GT vẫn chờ; snapshot bên dưới tạo trước lần này.

Đã dùng roster và protocol được người dùng duyệt, chạy hai đoạn30s. Code/integration được kiểm thử; real-data acceptance còn chờ GT review và chưa được chứng minh đạt. Xem [report](../reports/task07-vietnam-tonga-segments.md) và [hướng dẫn review](../guides/task07-vietnam-tonga-review.md).

## Inputs và outputs hiện hành

- Video gốc: `codebase/assets_test/vietnam-tonga.mp4`, SHA-256 `1443c1d263c8037a5684f3dbc0ef9216beb5097d9a47c4c1c9b94d1363e26865`.
- Roster runtime được duyệt: `codebase/configs/rosters/vietnam_tonga.json`. CSV canonical và approval record: `codebase/data/matches/vietnam_tonga/`. CSV partial ban đầu giữ nguyên.
- Segment declaration: `codebase/configs/segments/vietnam_tonga_task07.json`.
- Acceptance profile: `codebase/configs/evaluation/task07_vietnam_tonga.json`.
- Config control: `codebase/configs/ball-possession-vietnam-tonga.json`.
- Artifact root: `codebase/outputs/task07-vietnam-tonga-segments-20261104/` (gọi là ROOT bên dưới).
- `media/segments.json`: parent/child hashes,30s duration,900frames/clip, mapping parent_time=child_time+300 hoặc+165s. Cùng trận/nguồn, không independent match holdout.
- `development-tiled/`, `validation-tiled/`: caches detector cùng approved model/ONNX CPU, không dùng GT.
- `development-tracking-v2/`, `validation-tracking/`: caches raw OCR thật. `development-tracking-masked/`, `validation-tracking-masked/`: bản replay cuối, lọc màu/ROI mới và kiểm tra source/tracker/observed bbox trước dùng lại raw jersey evidence. Counts không phải accuracy.
- `development-masked-delivery/`, `validation-masked-delivery/`: các run control cuối; dùng các directory này thay các lượt thử color-control/release/final trước đó.
- `review-development-final/`, `review-validation-final/`: gói source-only annotation review, chưa được duyệt.
- `tests-signoff.json/log`:233tests PASS. Các logs/revisions trước được giữ để đối chiếu.

User approvals đã có hiệu lực: roster đã xác nhận, được dùng từng đoạn30–60s, OCR weights local, protocol/ngưỡng pilot đã duyệt. Không hỏi lại. Không tự chuyển nhãn draft thành approved; không coi protocol approval là GT approval.

## Tái chạy

Lệnh tính từ workspace root; luôn dùng output directory mới. Không chạy lại detector/OCR khi chỉ cần sửa/replay control.

```powershell
codebase/.venv/Scripts/python.exe codebase/scripts/track_ball_possession.py --detections codebase/outputs/task07-vietnam-tonga-segments-20261104/development-tiled/detections.jsonl --run-json codebase/outputs/task07-vietnam-tonga-segments-20261104/development-tiled/run.json --tracks codebase/outputs/task07-vietnam-tonga-segments-20261104/development-tracking-masked/tracked_observations.jsonl --tracking-run codebase/outputs/task07-vietnam-tonga-segments-20261104/development-tracking-masked/run.json --identity-mappings codebase/outputs/task07-vietnam-tonga-segments-20261104/development-tracking-masked/identity_mappings.json --exclusions codebase/outputs/task07-vietnam-tonga-segments-20261104/vt_development-policy-masked.json --config codebase/configs/ball-possession-vietnam-tonga.json --video codebase/outputs/task07-vietnam-tonga-segments-20261104/media/vt_development.mp4 --output-dir codebase/outputs/vt-next-control
```

Khi cần OCR/tracking mới, thay source tương ứng. Giữ policy hash đúng clip; jersey TTL6s độc lập với team TTL2s, crop upscale3 và cadence5frames đã được ghi trong run. Cuts reset identity, không dùng mapping cuối video gán ngược:

```powershell
codebase/.venv/Scripts/python.exe codebase/scripts/track_players.py --detections codebase/outputs/task07-vietnam-tonga-segments-20261104/validation-tiled/detections.jsonl --run-json codebase/outputs/task07-vietnam-tonga-segments-20261104/validation-tiled/run.json --roster-config codebase/configs/rosters/vietnam_tonga.json --video codebase/outputs/task07-vietnam-tonga-segments-20261104/media/vt_validation.mp4 --tracking-policy codebase/outputs/task07-vietnam-tonga-segments-20261104/vt_validation-policy-masked.json --enable-ocr --ocr-provider easyocr --ocr-weights-dir codebase/.model-cache/easyocr --ocr-sampling-cadence 5 --ocr-upscale 3 --jersey-evidence-ttl-s 6 --color-method masked --output-dir codebase/outputs/vt-next-tracking
```

Nếu cần cache detector mới, dùng cùng approved model, local CPU.4ONNXthreads được khảo sát trên development, không phải đổi model/backend/GPU:

```powershell
codebase/.venv/Scripts/python.exe codebase/scripts/detect_ball_tiles.py --video codebase/outputs/task07-vietnam-tonga-segments-20261104/media/vt_validation.mp4 --confidence 0.15 --onnx-threads 4 --exclude-boxes '[[0.02,0.73,0.27,1.0]]' --output-dir codebase/outputs/vt-next-detection
```

Chuẩn bị lại segments/roster khi cần; không tạo lại mặc định nếu caches hiện có hợp lệ:

```powershell
codebase/.venv/Scripts/python.exe codebase/scripts/prepare_match_segments.py --source codebase/assets_test/vietnam-tonga.mp4 --roster-csv codebase/outputs/task07-vietnam-tonga-intake-20261104/roster-proposed.csv --segment-config codebase/configs/segments/vietnam_tonga_task07.json --output-dir codebase/outputs/vt-next-media
```

Child hash có thể thay đổi khi transcoding/runtime khác; tạo policies/profile revision đúng hash, giữ provenance và approval scope. Không bỏ qua source binding hoặc sửa locked v1/v2. Các helpers này chưa đăng ký toàn bộ dataset v2/G04 như đã hoàn tất.

## Đánh giá sau khi có nhãn thật

GT chưa được người dùng review nên lệnh sau là bước tiếp theo, không phải kết quả đã chạy:

```powershell
codebase/.venv/Scripts/python.exe codebase/scripts/evaluate_ball_possession.py --run-dir codebase/outputs/task07-vietnam-tonga-segments-20261104/validation-masked-delivery --ground-truth codebase/data/matches/vietnam_tonga/reviewed-vt_validation.json --acceptance-profile codebase/configs/evaluation/task07_vietnam_tonga.json --output-dir codebase/outputs/vt-reviewed-evaluation
```

Evaluator phải từ chối draft/synthetic/sai source, báo insufficient_samples khi chưa đủ cỡ mẫu; không dùng precision/recall N/A thành100%. Tách automatic và manual corrections. Nếu fail, phân tích trên development; validation đã xem phải ghi exposure/revision. Không gọi cùng trận là independent match test.

Task08–10 nhận nullable event-time actors, observed/predicted/missing, pass/shot/handoff uncertainty như [contracts](../specs/ball-possession-v2.md). Hiện chưa có completed pass đáng tin được chứng minh trên hai đoạn; chưa dùng pipeline để ghi PRA chính thức hoặc tự đóng Task07/G04/05/06.

## Snapshot nghiệm thu cuối

233 tests PASS; `delivery-audit.json` xác nhận 1800 frames, source PTS error≤0.333334µs, observed-source binding, draft GT rejection và 19 file dataset cũ không đổi. Hai đoạn đã xem để triage, ghi `validation-exposure.json`; không phải untouched validation. Development có 75 confirmed control frames nhưng 0 player_id; đoạn thứ hai 159/4. Cả hai chưa có completed pass; chưa đạt bằng chứng pass recall. GT review xong vẫn phải đo và sửa nếu fail, không tự DONE.

Có thể replay OCR từ raw cache bằng `--enable-ocr --jersey-evidence-cache ROOT/development-tracking-v2 --jersey-evidence-ttl-s 6 --color-method masked` cùng video/detections/policy đúng hash và output mới; không cần gọi lại OCR. Cache phải là lượt OCR thật completed, đúng source/tracker và observed bbox. Thay ROOT bằng artifact root khai báo ở trên.
