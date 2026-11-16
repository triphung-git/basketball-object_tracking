# Task07A — Ball detection development ablation

Cập nhật2026-11-05: [root-cause audit và roadmap07A–07C](task07-improvement-roadmap-20261105.md) đã kiểm tra thêm21tổ hợp profile/ngưỡng từ artifacts resolution, giữ nguyên baseline vì chưa có candidate tốt hơn. Dataset train gốc chưa có cục bộ; source detector wrapper lịch sử khác current code và chưa đủ snapshot để tái lập. Không coi domain gap hoặc resolution là nguyên nhân gốc đã được chứng minh hoàn toàn.

**Ngày:** 2026-11-04  
**Trạng thái:** Đã hoàn tất ablation trên development; **chưa đạt nghiệm thu**. Cấu hình tốt nhất vẫn là `development-spatial-v4`, ball observed recall **36/72 = 50.00%**, thấp hơn ngưỡng đã duyệt **90%**.

## Phạm vi và tính toàn vẹn

- Chỉ dùng đoạn development Việt Nam–Tonga 30 giây, 900 frames, source SHA-256 `8fd370b0668860a5c70d56bf256c76e3783bc1fe6598b529944ad00ca0616b45`.
- Giữ nguyên approved model `phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1`, ONNX CPU, weights và dependency. Không dùng GPU, upload media, train hoặc thay backend.
- Ground truth SHA-256 `ee3f10d78164fe4d1b3301e80cb77896ddf3717fae87c45424721c068506b81d` chỉ được dùng sau inference bởi evaluator/diagnostic; không được truyền vào detector, player tracker hay ball tracker.
- Không sửa GT, manifest, split hoặc output baseline. Hai ablation và mọi output của chúng nằm dưới `codebase/outputs/task07a-ball-detection-20261104/`; run/settings/input hashes được giữ trong `run.json` và diagnostics.
- Giữ rõ semantics `observed` / `predicted` / `missing`; prediction không được tính là observed hit.

## Phân loại lỗi baseline v4

Đối chiếu 72 visible/certain GT samples với detections confidence 0.15 và ball output v4, IoU threshold 0.30:

| Nhóm | Bằng chứng trên 72 mẫu | Diễn giải |
|---|---:|---|
| Detector không có candidate khớp | 31/72 mẫu | 22 mẫu cho output missing/predicted; ở 9 mẫu còn lại tracker chọn observed candidate sai. Đây là detector miss dù output có observed box. |
| Candidate đúng có sẵn nhưng pipeline không chọn | 5/72 mẫu | Cache có candidate khớp GT nhưng tracker không phát ra observed hit tương ứng. |
| Wrong observed selection | 9/72 mẫu, là subset của 31 detector misses ở trên | Candidate được chọn không khớp GT; không cộng lần hai khi tính tổng lỗi. |
| Bóng rất nhỏ | 24/72 có cạnh ngắn nhất ≤20 px; 12/36 mẫu missed/wrong | Kích thước thấp là yếu tố thường gặp, nhưng không giải thích toàn bộ lỗi. |
| Gần/che bởi người | GT center nằm trong một human bbox ở 42/72 mẫu; 16/36 mẫu missed/wrong | Đây là proxy chồng lấp bbox, không khẳng định occlusion vật lý trong mọi trường hợp. |
| Chuyển động | Local optical-flow median >2 px/frame ở 19/72 mẫu và 10/36 mẫu missed/wrong; >4 px/frame ở 5/36 lỗi | Chỉ là proxy chuyển động tại crop GT; không phải nhãn motion blur. |
| Poster/khán đài/overlay | 80 candidate không khớp trong 102 candidate không khớp nằm ở nửa trên ảnh (y < 0.56H) | Contact sheet cho thấy nhiều candidate nằm trên poster, bảng quảng cáo/scoreboard và khu khán đài. Đây là phân loại vị trí có kiểm tra trực quan, không phải full-video false-positive precision. |
| Acquisition/reacquisition | 6/36 mẫu lỗi có ball output `missing` và không có track ID | Gợi ý tracker chưa có active track tại các thời điểm này; chỉ là phân loại theo state đầu ra. |

Baseline candidate recall là **41/72 = 56.94%**; observed recall là **36/72 = 50.00%**. Tổng lỗi quan sát là 36/72: 31 frame thiếu candidate khớp (gồm 9 false observed) và 5 frame có candidate khớp nhưng tracker không chọn đúng. Có **102** raw candidate không khớp trên các frame GT này. Không dùng số candidate bị ROI loại bỏ làm bằng chứng độ chính xác.

## Ablation có kiểm soát

Cùng video, grid 2×2, overlap 0.2, full-frame human detections, overlay exclusion và v4 ball search ROI. Ablation confidence hạ đồng thời detector và ball-tracker min confidence xuống0.10 để candidate mới được xét; ablation còn lại chỉ upscale crop. Các metric candidate dùng raw ball detections; observed recall lấy từ ball tracker và evaluator, không lấy predicted làm hit.

| Cấu hình | Candidate khớp GT | Candidate recall | Observed khớp GT | Observed recall | Observed không khớp trên mẫu GT | Candidate không khớp trên mẫu GT | Thời gian detection / toàn pipeline |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline `development-spatial-v4` — conf 0.15, scale 1.0 | 41/72 | 56.94% | 36/72 | **50.00%** | 9 | 102 | 421.7 s / 443.6 s |
| `confidence-010-native` — conf 0.10, scale 1.0; ball min confidence 0.10 | 42/72 | **58.33%** | 29/72 | 40.28% | 13 | 141 | 575.2 s / 626.8 s |
| `scale-150-confidence-015` — conf 0.15, scale 1.5; ball min confidence 0.15 | 38/72 | 52.78% | 31/72 | 43.06% | 10 | 102 | 1441.6 s / 1463.8 s |

Tổng ball detections trong 900 frames: baseline **1547**, conf 0.10 **2121**, scale 1.5 **1569**. Hạ confidence chỉ tăng candidate recall 1 mẫu (+1.39 điểm %) nhưng làm observed recall giảm 7 mẫu và tăng candidate không khớp 39. Upscale 1.5 không tăng candidate recall, giảm observed recall 5 mẫu và mất khoảng **3.3×** thời gian pipeline so với baseline. Thời gian ablation confidence có chạy đồng thời với phần diagnostic baseline nên chỉ là wall-time tham khảo; các số này không phải benchmark phần cứng ổn định. Scale trial chạy riêng.

Evaluator đầy đủ vẫn trả `failed_criteria`: strict control **0%**, pass recall **0%**, ball observed recall cao nhất trong thử nghiệm **50%**. Ngưỡng nghiệm thu không thay đổi; không có cấu hình mới nào đủ điều kiện thay baseline.

## Cấu hình được chọn và giới hạn

Giữ `development-spatial-v4` làm **cấu hình development tốt nhất hiện có**, không promote hai ablation. Không hạ confidence hoặc áp scale 1.5 vào mặc định. Tất cả vẫn là cùng một trận đã exposure, không chứng minh tổng quát hoặc realtime.

Candidate recall cao nhất 58.33% vẫn thấp xa observed recall gate 90%; nguyên nhân chính không thể giải quyết chỉ bằng nới threshold hoặc upscale crop: background candidate tăng, tracker có nhiều lựa chọn sai, và candidate recall không đủ. Bước tiếp theo nên tập trung tách candidate bóng khỏi poster/khán đài và xử lý bóng nhỏ/che khuất trước association. Thay model/weights/backend, train hoặc dependency mới vẫn cần user approval; chưa thực hiện. Không đánh dấu Task07 DONE.

## Artifacts

- Baseline failure cases, khung xanh là GT và cam là raw candidate: [failure-cases.jpg](../../codebase/outputs/task07a-ball-detection-20261104/baseline-diagnostics-v3/failure-cases.jpg).
- Baseline candidate trên toàn cảnh để rà poster/khán đài: [background-candidates.jpg](../../codebase/outputs/task07a-ball-detection-20261104/baseline-diagnostics-v3/background-candidates.jpg).
- Per-sample metrics, hash và taxonomy: [baseline diagnostics](../../codebase/outputs/task07a-ball-detection-20261104/baseline-diagnostics-v3/diagnostics.json), [confidence 0.10](../../codebase/outputs/task07a-ball-detection-20261104/confidence-010-native/diagnostics/diagnostics.json), [scale 1.5](../../codebase/outputs/task07a-ball-detection-20261104/scale-150-confidence-015/diagnostics/diagnostics.json).
- Settings: [confidence 0.10](../../codebase/configs/task07a/confidence-010-native.json), [scale 1.5](../../codebase/configs/task07a/scale-150-confidence-015.json), [ball tracker threshold 0.10](../../codebase/configs/task07a/ball-possession-confidence-010.json).
- Detections và `run.json`: [confidence 0.10](../../codebase/outputs/task07a-ball-detection-20261104/confidence-010-native), [scale 1.5](../../codebase/outputs/task07a-ball-detection-20261104/scale-150-confidence-015).
- Debug MP4: [confidence 0.10](../../codebase/outputs/task07a-ball-detection-20261104/confidence-010-native/ball/debug.mp4), [scale 1.5](../../codebase/outputs/task07a-ball-detection-20261104/scale-150-confidence-015/ball/debug.mp4). Baseline reference: [development-spatial-v4](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/development-spatial-v4/debug.mp4).

## Tái chạy

Từ workspace root; hai lệnh detector không nhận GT. Dùng backslash paths trong PowerShell:

```powershell
.\codebase\.venv\Scripts\python.exe codebase\scripts\detect_ball_tiles.py `
  --video codebase\outputs\task07-vietnam-tonga-segments-20261104\media\vt_development.mp4 `
  --output-dir codebase\outputs\task07a-ball-detection-20261104\confidence-010-native `
  --settings codebase\configs\task07a\confidence-010-native.json

.\codebase\.venv\Scripts\python.exe codebase\scripts\detect_ball_tiles.py `
  --video codebase\outputs\task07-vietnam-tonga-segments-20261104\media\vt_development.mp4 `
  --output-dir codebase\outputs\task07a-ball-detection-20261104\scale-150-confidence-015 `
  --settings codebase\configs\task07a\scale-150-confidence-015.json
```

Downstream commands cho từng trial; `$trial` lần lượt là một trong hai output ở trên, `$ballConfig` là config tracker phù hợp với confidence:

```powershell
$trial = 'codebase\outputs\task07a-ball-detection-20261104\confidence-010-native'
$ballConfig = 'codebase\configs\task07a\ball-possession-confidence-010.json'
$video = 'codebase\outputs\task07-vietnam-tonga-segments-20261104\media\vt_development.mp4'
$policy = 'codebase\outputs\task07-vietnam-tonga-segments-20261104\vt_development-policy-ball-roi-v4.json'
.\codebase\.venv\Scripts\python.exe codebase\scripts\track_players.py --detections "$trial\detections.jsonl" --output-dir "$trial\player-tracking" --run-json "$trial\run.json" --roster-config codebase\configs\rosters\vietnam_tonga.json --video $video --tracking-policy $policy --color-method masked
.\codebase\.venv\Scripts\python.exe codebase\scripts\track_ball_possession.py --detections "$trial\detections.jsonl" --run-json "$trial\run.json" --tracks "$trial\player-tracking\tracked_observations.jsonl" --tracking-run "$trial\player-tracking\run.json" --identity-mappings "$trial\player-tracking\identity_mappings.json" --exclusions $policy --config $ballConfig --video $video --output-dir "$trial\ball"
.\codebase\.venv\Scripts\python.exe codebase\scripts\evaluate_ball_possession.py --run-dir "$trial\ball" --ground-truth codebase\data\matches\vietnam_tonga\reviewed-vt_development-v2.json --output-dir "$trial\evaluation" --acceptance-profile codebase\configs\evaluation\task07_vietnam_tonga.json
.\codebase\.venv\Scripts\python.exe codebase\scripts\analyze_task07a_ball_detection.py --ground-truth codebase\data\matches\vietnam_tonga\reviewed-vt_development-v2.json --detection-run-dir $trial --ball-run-dir "$trial\ball" --video $video --output-dir "$trial\diagnostics"
```

Với trial scale, đặt `$trial` thành `...\scale-150-confidence-015` và `$ballConfig` thành `codebase\configs\ball-possession-vietnam-tonga-spatial.json`. Player tracking chạy không OCR. GT chỉ xuất hiện ở evaluator và diagnostic analyzer sau inference; output mới không ghi đè baseline.

## Kiểm thử

- `.\codebase\.venv\Scripts\python.exe -m pytest codebase\tests\test_task07_match_improvements.py codebase\tests\test_task07_pipeline.py -q`: **31 tests PASS** (18 detector/match regressions cùng pipeline tests).
- Pylance `problems`: không có lỗi ở detector, scripts và tests đã sửa.
- Cả hai detection runs xử lý đủ 900 frames với model ID/backend/device đúng approved config; ball pipeline/evaluator hoàn tất và debug video được xuất. PTS export checks PASS.
