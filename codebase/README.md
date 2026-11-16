# Basketball Scoreboard — codebase

> **Hiện trạng sau QA 16/11/2026: DEMO_PARTIAL, quality NOT_ACCEPTED.** Mở `run_demo.bat` từ thư mục gốc. [Hướng dẫn hiện hành](../docs/USER_GUIDE.md) · [Review và sửa lỗi](../docs/reports/qa-project-review-20261116.md). Full regression: **539 passed, 1 skipped**. Các báo cáo/baseline bên dưới là lịch sử; test pass chưa chứng minh đủ PRA trên video thật.

Dataset-first07A: [report](../docs/reports/task07a-dataset-first-20261105.md),257tests PASS,27QA samples và359frame pilot với model suggestions chờ review. [Hướng dẫn review](../docs/guides/task07a-dataset-label-review.md). Không có YOLO labels/training mới; Task07 vẫn IN_PROGRESS. Dataset prep không thay thế accuracy acceptance.

Candidate development mới: [spatial reliability v4](../docs/reports/task07-spatial-reliability-20261104.md),240tests PASS; ball recall50% sau sửa ball ROI/acquisition, strict control/pass0%. Consensus OCR chặt hơn nhưng chưa chứng minh OCR accuracy tăng. Đây là pilot tune theo camera, chưa đạt nghiệm thu hoặc video bất kỳ.

Cập nhật real-data Task07: [full development evaluation v2](../docs/reports/task07-development-evaluation-v2-20261104.md) đã chạy với GT người dùng review/xác nhận; ball recall43.06%, strict control0%, pass recall0%, precision N/A, **`failed_criteria`**. Task07 vẫn IN_PROGRESS vì recognition chưa đạt; không còn đơn thuần chờ nhãn development. Validation GT chưa nhận.

Cập nhật pilot mới nhất 2026-11-04: [Task07 Vietnam–Tonga](../docs/reports/task07-vietnam-tonga-segments.md), **233 tests PASS**, hai đoạn 30s dùng roster thật/protocol đã duyệt; [handoff](../docs/handoffs/task07-vietnam-tonga.md), [review nhãn](../docs/guides/task07-vietnam-tonga-review.md). GT vẫn pending, chưa có completed pass và identity-control coverage thấp; **Task07 chưa DONE**, chưa chứng minh realtime hoặc accuracy thresholds. Các counts/baseline clip04 bên dưới giữ làm lịch sử.

**Cập nhật 2026-11-04:** [Task07](../docs/reports/task07-ball-possession.md) đã có ball tracking/control/pass/operational possession, evaluator và debug exports; 207 tests PASS. [Hướng dẫn tái chạy và handoff](../docs/handoffs/task07-to-task08-09-10.md) dùng clip04 3x3 + roster giả lập theo authorization riêng. Task07 chưa DONE về real accuracy: thiếu GT và ball/identity coverage còn thấp. OCR local đã được phê duyệt và chạy; các dòng pending OCR/Task07 chưa triển khai bên dưới thuộc baseline lịch sử.

Phạm vi sản phẩm hiện hành từ 2026-11-03: [Heatmap & Automatic PRA v2](../docs/MVP-v2-proposal.md), [PLAN](../PLAN.md), [task index](../docs/tasks/README.md). Task01–02 là baseline v1; task03 đã có pipeline video/detection, task04 bàn giao công cụ và còn chờ dữ liệu/rules. Task05–06 có core tools/diagnostic integration đã kiểm chứng (153 tests PASS); cả hai vẫn IN_PROGRESS vì thiếu real geometry/GT, footage hai đội/roster và OCR provider. Xem [nghiệm thu 05–06](../docs/reports/task05-task06-acceptance.md) và [handoff](../docs/handoffs/task06-to-task07-08-12.md).

Tài liệu cần đọc: [hướng dẫn phát triển](../docs/DEVELOPMENT.md), [kế hoạch](../PLAN.md), [task01](../docs/tasks/task01.md).

## Hiện trạng

Công cụ kiểm tra môi trường chạy bằng thư viện chuẩn Python. Có thêm công cụ kiểm tra video và smoke test detection local; chưa có pipeline tracking/scoring. Python 3.12.14 đã được cài riêng dưới `.tools/python`, môi trường `.venv` đã tạo. Trạng thái cài/kiểm thử runtime xem báo cáo môi trường; không coi việc có script là model đã chạy thành công.

Từ thư mục `codebase`:

```powershell
python scripts/check_environment.py --output outputs/environment.json
```

## Kiểm tra clip

Bảy clip hiện có trong `assets_test/`, đã được thêm vào gitignore. Cần FFmpeg/FFprobe trong PATH:

```powershell
.venv/Scripts/python.exe scripts/inspect_videos.py --source assets_test --output outputs/video-inspection-new
```

File gốc giữ nguyên; tool chỉ giải mã và ghi metadata/contact sheet. Không suy ra vào/trượt từ ảnh lấy mẫu.

## Quản lý dữ liệu và kiểm tra nhãn (Task 02)

Các lệnh prepare_dataset.py/validate_dataset.py ở mục này kiểm tra **pilot v1**. `--require-ready` pass không chứng minh dataset PRA v2 hoặc automatic stats đã sẵn sàng; schema/validator v2 ở phần task04 bên dưới. Không chạy prepare ghi đè dữ liệu đã khóa.

Dữ liệu và nhãn sự kiện được chuẩn hóa theo các công cụ:

### 1. Tạo danh mục video (`manifest.csv`)
Tự động quét các thư mục video (`assets_test/`, `data/raw/`), trích xuất thông số stream (FPS, kích thước, thời lượng, số frame) và mã băm SHA-256:
```powershell
.venv/Scripts/python.exe scripts/prepare_dataset.py
```

Manifest hiện đã khóa. Script từ chối ghi đè file có sẵn; để khảo sát video mới hãy dùng `--output outputs/manifest-proposal.csv` (đường dẫn mới), rồi review thay đổi trước khi cập nhật dataset. IDs mới dựa trên hash; metadata đã được biên tập được giữ khi tạo proposal.

### 2. Kiểm tra tính toàn vẹn và mức độ sẵn sàng (`validate_dataset.py`)
Kiểm tra cấu trúc CSV, tính hợp lệ của timestamp, kiểm tra rò rỉ split giữa các nhóm nguồn và phân định rõ trạng thái sẵn sàng đánh giá:
```powershell
# Kiểm tra cấu trúc schema và toàn vẹn dữ liệu (trả về 0 nếu hợp lệ):
.venv/Scripts/python.exe scripts/validate_dataset.py

# Kiểm tra nghiêm ngặt mức độ sẵn sàng cho benchmark đánh giá:
.venv/Scripts/python.exe scripts/validate_dataset.py --require-ready
```

`--require-ready` kiểm tra điều kiện cho **pilot evaluation**: nhãn approved, test có made/miss, coverage, split locked, media và hash manifest/events/coverage đúng. Quy mô dưới 50 lượt là cảnh báo, không phải điều kiện bắt buộc. Hiện có 10 nhãn (6 made, 4 miss), test có 7 (4 made, 3 miss). Đây chưa phải benchmark đủ lớn để kết luận độ chính xác tổng quát.

### 3. Quy trình rà soát nhãn
- Các pha ném ứng viên khảo sát từ video nằm tại `data/annotations/events.draft.csv`.
- Sau khi người dùng mở video kiểm tra mốc thời gian (theo hướng dẫn tại `../docs/data/ANNOTATION_GUIDE.md`), chuyển các pha ném đã duyệt vào `data/annotations/events.csv` và cập nhật người duyệt vào `data/annotations/reviews.csv`.


## Smoke test đúng model

Tạo `.env` từ `.env.example` và điền key trên máy; không gửi key vào chat. `smoke_model.py` chỉ đọc hai assignment literal `ROBOFLOW_API_KEY` và `ROBOFLOW_MODEL_ID`, hỗ trợ dấu nháy bao quanh; không hỗ trợ inline comment, shell expansion hoặc `export`. Biến môi trường có giá trị được ưu tiên. Chỉ chấp nhận đúng model ID đã duyệt (`phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1`).

```powershell
.venv/Scripts/python.exe scripts/smoke_model.py --source assets_test --samples 6
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Smoke script tự loại video thuộc test split đã khóa. Để chạy một clip phát triển: thêm `--video-name 20521993-uhd_2160_3840_60fps.mp4`. Không inference holdout trong lúc debug/calibration. Offline mode và lần tái chạy mới được ghi tại [báo cáo nghiệm thu](../docs/reports/task01-task02-acceptance.md); output cũ vẫn giữ nguyên.

Smoke test dùng ONNX CPU, tải metadata/weights từ Roboflow một lần vào `.model-cache/` và inference trên máy, không upload frame. Mỗi clip lấy 6 frame độc lập, ảnh dài tối đa 1280 px, tọa độ JSON quy về frame gốc. Hai lần warm-up được đo riêng, median/mean model-call latency tách khỏi decode/vẽ/ghi; đây không phải FPS toàn pipeline. Model vẫn có preprocessing kích thước mạng riêng.

Kiểm tra riêng cấu hình mà không tải model: `.venv/Scripts/python.exe scripts/smoke_model.py --check-credentials`. Lệnh chỉ báo key đã được cấu hình hay chưa, không in giá trị.

Cài đặt lại môi trường khi cần:
```powershell
uv pip install --python .venv/Scripts/python.exe --cache-dir "$env:TEMP/bb-uv" -r requirements.txt
```

### Kết quả mẫu & Báo cáo nghiệm thu

- Output mẫu đã nghiệm thu hoàn tất: `outputs/smoke-20261031-215143/` gồm `smoke.json` và 18 ảnh overlay JPG.
- Báo cáo chi tiết: [docs/reports/task01-smoke.md](../docs/reports/task01-smoke.md).
- Class mapping xác nhận: `0: ball`, `1: human`, `2: rim`.
- Độ trễ đo được trên CPU: Median 490.4 ms, Mean 527.1 ms (Intel 16 logical cores).

### Xử lý lỗi thường gặp (Troubleshooting)

1. **`WinError 1314: A required privilege is not held by the client`**:
   - *Nguyên nhân*: Thư viện `inference-models` cố gắng tạo symbolic link giữa thư mục cache và `shared-blobs`, đòi hỏi quyền Administrator hoặc Developer Mode trên Windows.
   - *Giải pháp*: Script `smoke_model.py` đã tự động tích hợp fallback `shutil.copyfile` kèm kiểm tra toàn vẹn mã băm MD5.
2. **`FileNotFoundError: [Errno 2] No such file or directory` khi tạo file `.tmp`**:
   - *Nguyên nhân*: Giới hạn độ dài đường dẫn 260 ký tự (`MAX_PATH`) của Windows API khi thư mục dự án nằm sâu trong cây thư mục (ví dụ OneDrive).
   - *Giải pháp*: Script `smoke_model.py` tự động kích hoạt tiền tố đường dẫn mở rộng `\\?\` trên Windows cho cache path.
3. **`Missing key: set ROBOFLOW_API_KEY...`**:
   - *Nguyên nhân*: Chưa tạo file `codebase/.env` hoặc giá trị key còn giữ nguyên chuỗi giữ chỗ mẫu `your_api_key_here`.
   - *Giải pháp*: Điền API key thực tế vào `codebase/.env` theo mẫu tại `.env.example`. Không chia sẻ key vào logs/chat.
4. **`Model ID differs from the approved model`**:
   - *Nguyên nhân*: Cấu hình sai model ID khác với mô hình dự án đã duyệt (`phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1`).
   - *Giải pháp*: Giữ đúng model ID được chỉ định, không tự ý đổi model ID.


## Pipeline video/PTS/detection v2 — Task03

`src/basketball_scoreboard` đọc tuần tự MP4, chuẩn hóa PTS, inference đúng model ONNX CPU, xuất overlay/JSONL/run metadata. Chạy từ thư mục **codebase**, chọn output directory mới:

```powershell
.venv/Scripts/python.exe src/basketball_scoreboard/app.py --video assets_test/20521993-uhd_2160_3840_60fps.mp4 --output-dir outputs/new-clip02-run
.venv/Scripts/python.exe src/basketball_scoreboard/app.py --video assets_test/20521993-uhd_2160_3840_60fps.mp4 --output-dir outputs/new-prefix --max-frames 100 --confidence 0.30
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Config mặc định: configs/default.yaml; có --config, --max-edge, --pts-policy, --no-video-export. CLI revalidate overrides; không ghi đè artifacts. Prefix ngắn được ghi partial, lỗi probe/model/writer ghi failed nếu directory đã tạo. Config credentials.env_file được đọc cục bộ; không ghi API key/SDK traceback vào logs.

Một record JSONL/frame kể cả empty detections; bbox theo frame gốc, mapping lớp từ runtime. Time dùng frame PTS và frame timebase; MP4 xuất explicit source timestamps (microsecond), đã có regression VFR readback. --pts-policy flag_only có thể ghi irregular JSONL nhưng writer từ chối non-monotonic timestamps. Không export audio.

model.cpu_threads giới hạn PyTorch CPU postprocessing, không khẳng định giới hạn toàn bộ ONNX runtime. export.encoder_preset=veryfast. Không đổi detector/backend/dependencies hoặc cài CUDA. Thư mục run mới có config/versions/hash/timings thực tế; tốc độ CPU chưa đạt 60FPS nguồn.

Bằng chứng: run lịch sử outputs/task03-clip02-full được giữ; run sau sửa lỗi outputs/acceptance-20261102/g03-clip02-verified. [Report G03](../docs/reports/task03-pipeline.md) ghi rõ hai run, kiểm tra độc lập và giới hạn. Bộ tests chung: 92 PASS ở lần nghiệm thu, log outputs/acceptance-20261102/unittest-verified.log. Không coi detection correctness là đã đo PRA accuracy.

## Dataset v2 — Task04 IN_PROGRESS

Namespace data/v2 gồm manifest, splits, roster, ruleset và 9 annotations: positions, identities, control, passes, shots, rebounds, assists, coverage, reviews. Header nguồn: dataset_schema.py. Hiện roster/annotations trống; rules/protocol draft, split draft/test rỗng, provenance pending, không có lock. Công cụ pass không có nghĩa dữ liệu PRA đủ.

```powershell
.venv/Scripts/python.exe scripts/validate_dataset_v2.py --require-tooling-ready
.venv/Scripts/python.exe scripts/validate_dataset_v2.py --require-data-ready
.venv/Scripts/python.exe scripts/validate_dataset_v2.py --require-locked
```

Lần bàn giao kỳ vọng exits 0/2/3. Mặc định validator in JSON, exit0 chỉ structural validity; lỗi cấu trúc exit1, thiếu tooling exit4. --output-json ghi file mới, không overwrite. Có positive/negative synthetic fixtures kiểm tra gates và external-lock tamper; synthetic không phải ground truth thật.

Manifest đang tồn tại, prepare_dataset_v2.py mặc định sẽ từ chối ghi đè kể cả --force. Nếu cần inventory proposal mới:

```powershell
.venv/Scripts/python.exe scripts/prepare_dataset_v2.py --help
.venv/Scripts/python.exe scripts/prepare_dataset_v2.py --output outputs/new-manifest-v2-proposal.csv
```

Không dùng initializer để cập nhật dataset locked. Source/session/camera/source_group cần review; filename không chứng minh khác trận hay đủ điều kiện. Approved review không được tự tạo bởi validator. Freeze cần rules/protocol, roster, labels/coverage và split được duyệt, rồi external lock.json hash đủ 13 file cốt lõi; không hash chính lock.

Đọc [annotation guide](../docs/data/ANNOTATION_GUIDE-v2.md), [contracts](../docs/specs/contracts-v2.md), [rules draft](../docs/specs/rules-v2.md), [protocol draft](../docs/specs/evaluation-protocol-v2.md), [data report](../docs/reports/data-v2.md). Trước benchmark cần chốt extension FT-series/foul/possession và đủ footage/GT hai đội.

## Task05–06 — core tools & OCR provider đã kiểm chứng, data/model acceptance pending

Source: court.py, heatmap.py, players.py, identity.py và spatial_io.py. Đây là batch local pipeline trên cached detections, chưa phải full identity/PRA hoặc streaming real-time.

- Production court cần validated/reviewed/source-matched geometry; synthetic/draft cần --allow-uncalibrated và output diagnostic.
- Main heatmap cần stable track, observed/valid endpoints và role player có evidence; ROI một mình là unknown, predicted/cut/gap không được nối. Khi thực thể trong ROI có bằng chứng đội/cầu thủ được resolver xác nhận, role được cập nhật thành player.
- --video cấp torso RGB evidence cho team resolver. Không video/crops thì roster không tự sinh team evidence.
- OCR provider layer đã nối CLI (`LocalEasyOCRProvider`, `MockOCRProvider`, `evaluate_crop_quality`, flags `--enable-ocr`, `--ocr-provider`, `--ocr-sampling-cadence`). Không auto-download ngầm; quyền tải weights (~130 MB) chờ user phê duyệt.
- Event-time identity dùng mapping_at hoặc interval-enriched observations, không lấy mapping cuối video gán ngược.

Từ codebase, output paths phải mới và hai stage tách directory:

```powershell
.venv/Scripts/python.exe scripts/court_tool.py --config configs/courts/synthetic_half_court.json --allow-uncalibrated --preview outputs/new-court-preview.png
.venv/Scripts/python.exe scripts/track_players.py --detections outputs/acceptance-20261102/g03-clip02-verified/detections.jsonl --run-json outputs/acceptance-20261102/g03-clip02-verified/run.json --court-config configs/courts/synthetic_half_court.json --roster-config configs/rosters/synthetic_dual_team_roster.json --video assets_test/20521993-uhd_2160_3840_60fps.mp4 --allow-uncalibrated --output-dir outputs/new-task56-tracking
.venv/Scripts/python.exe scripts/generate_heatmap.py --court-config configs/courts/synthetic_half_court.json --detections outputs/new-task56-tracking/tracked_observations.jsonl --run-json outputs/acceptance-20261102/g03-clip02-verified/run.json --allow-uncalibrated --verify-replay --output-dir outputs/new-task56-heatmap
```

Run thật ở mức diagnostic: outputs/acceptance-20261103-task05-06-review/tracking-handoff và heatmap-handoff. 1089 source frames→1416 observations (1100 observed/316 predicted), 900 color evidence records; mọi player_id unresolved khi chưa bật OCR, 0 verified player roles từ video clip02 đơn người. Independent mass 12.116667s là human occupancy trên synthetic geometry, không phải accuracy trận hai đội. Raw trackless detections có mass 0, không invent trajectories.

159 tests PASS (~23s); kiểm tra toàn diện core contracts, homography, mass conservation, lifecycle, identity hysteresis, conflict detection, crop quality, offline OCR provider security và CLI flags. Audit độc lập kiểm dataset/G03 hashes, source bbox provenance, predicted status, namespace, interval/grid mass, replay, PNG và code fingerprints. Full unittest cần quyền ngoài sandbox nếu Windows Temp cleanup bị chặn; không sửa permissions/driver hoặc cài lại environment để che lỗi.

Recompute/seek/reload hiện bằng replay raw log theo batch, chưa có persisted incremental checkpoint engine. Mapping override dict là explicit offline whole-track correction; lưu run/revision mới. CLI --exclusions nhận operational intervals start_s/end_s/reason; overlap dùng union, cut/camera_change/segment_change ngắt interval băng qua scene boundary.

Outputs task05-court-heatmap/task06-players-identity/task05-06-integrated cũ giữ làm lịch sử; các mass12.1500/20.1667 trước review không được dùng nghiệm thu hiện tại.

[Biên bản nghiệm thu](../docs/reports/task05-task06-acceptance.md) · [Code review](../docs/reports/task05-task06-code-review.md) · [G05 report](../docs/reports/task05-court-heatmap.md) · [G06 report](../docs/reports/task06-players-identity.md) · [Handoff task07/08/12](../docs/handoffs/task06-to-task07-08-12.md).


