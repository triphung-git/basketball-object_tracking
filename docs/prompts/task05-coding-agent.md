# Prompt chung — Thực hiện xuyên suốt Task05–06, kiểm thử và bàn giao từng mốc

Đã có [tái nghiệm thu core task05–06 ngày2026-11-03](../reports/task05-task06-acceptance.md). Nếu dùng lại prompt, kiểm tra code/artifacts hiện tại và tiếp tục phần còn thiếu; không xây lại từ đầu hoặc lấy baseline trước triển khai bên dưới như trạng thái hiện tại. Geometry/GT và OCR provider vẫn pending.

Ngày cập nhật: 2026-11-03. Phạm vi: MVP v2 Automatic Stats đã duyệt. Giữ tên file `task05-coding-agent.md` làm điểm vào, nhưng prompt này giao **thực thi liên tục task05 và task06**, gồm code, kiểm thử, report ở giữa, tích hợp và bàn giao cuối; không chỉ phân tích hoặc viết kế hoạch.

Bạn là Senior AI/Python Engineer. Xây court calibration/heatmap, sau đó player tracking/team classification/identity; giữ nguyên nền video/detection đã nghiệm thu. Hoàn thành phần độc lập dù dữ liệu nghiệm thu còn thiếu. Không tạo calibration/ground truth/identity giả để đạt checklist.

Chọn hai task vì ROI, projection và trajectory contract của task05 được task06 dùng trực tiếp; đầu ra task06 lại giúp kiểm thử heatmap bằng track/team thật. Như vậy có một vòng tích hợp cụ thể mà không mở rộng sang ball control hoặc event engines khi identity chưa được kiểm chứng. Task07–15 chỉ là consumers để bàn giao, **không nằm trong phạm vi triển khai lần này**.

**Không kết thúc lượt sau checkpoint task05.** Ghi tests/report/handoff cho task05 rồi tự tiếp tục task06 trong phạm vi đã giao, không hỏi lại có tiếp tục hay không. Nếu thiếu geometry/data hoặc quyết định model, giữ đúng trạng thái pending và tiếp tục phần task06 độc lập; không giả tạo G05 PASS để vượt dependency.

Trình tự bắt buộc: khảo sát/readiness → task05 (mục 4–8) → checkpoint/report/handoff G05 → task06 (mục 9) → kiểm thử tích hợp G56 (mục 10) → nghiệm thu và bàn giao chung (mục 11).

## 1. Đọc và đối chiếu trước khi sửa code

Các đường dẫn dưới đây tính từ workspace root; source/config/scripts/tests dưới `codebase/`, tài liệu dưới `docs/`.

Đọc theo thứ tự:

1. `AGENTS.md` áp dụng nếu có; `docs/DEVELOPMENT.md`.
2. `docs/MVP-v2-proposal.md`, `PLAN.md`, `docs/tasks/README.md`.
3. `docs/tasks/task05.md`, `docs/tasks/task06.md`, `docs/tasks/task07.md`, `docs/tasks/task08.md`, `docs/tasks/task12.md` để hiểu consumers và ranh giới công việc.
4. `docs/handoffs/task04-to-task05-06.md`, `docs/handoffs/task03-to-task04.md`.
5. `docs/reports/task03-task04-acceptance.md`, `docs/reports/task03-pipeline.md`, `docs/reports/data-v2.md`, `docs/reports/environment.md`.
6. `docs/specs/contracts-v2.md`, `docs/specs/rules-v2.md`, `docs/specs/evaluation-protocol-v2.md`, `docs/data/ANNOTATION_GUIDE-v2.md`.
7. `codebase/README.md`, requirements/config hiện tại, source video/contracts/app/detector và tests liên quan.
8. Metadata và audit của run G03 verified; kiểm tra dataset hiện tại bằng công cụ riêng v1/v2 khi cần. Không in `.env` hay credential ra terminal/hội thoại.

Ưu tiên tài liệu v2 hiện hành. Phần scoreboard nhập tay trong tài liệu baseline và `docs/archive/` là lịch sử. Nếu thực tế khác thông tin dưới đây, ghi nhận khác biệt trước khi dùng; không khôi phục hoặc ghi đè công việc mới của người dùng.

## 2. Baseline bàn giao và giới hạn đã biết

- Task01–02: DONE trong phạm vi pilot v1; không làm lại hoặc sửa nhãn/split để phục vụ task05–06.
- Task03: DONE, G03 PASS. Input phát triển là `codebase/assets_test/20521993-uhd_2160_3840_60fps.mp4` (clip02).
- SHA-256 clip02: `3ed25e1b246ccebbe7904d76a22fbea65ebfcb86701499417cd52962f1fc4c26`.
- Run được nghiệm thu: `codebase/outputs/acceptance-20261102/g03-clip02-verified/`, gồm `run.json`, `detections.jsonl`, `annotated.mp4`.
- Audit: `codebase/outputs/acceptance-20261102/g03-independent-audit.json`; snapshot lịch sử: `handoff-snapshot.json` cùng thư mục.
- Run này có 1089 frames, 3045 detections; frame1086–1088 có timestamp repaired, không được coi là PTS quan sát nguyên vẹn. Nền clock đã sửa lỗi float/sub-tick collision; giữ các regressions đó.
- `g03-clip02-final` từng chạy đủ frame nhưng FAIL independent timestamp audit; `task03-clip02-full` là run code cũ. Không lấy nhầm hai run này làm input chuẩn mới.
- Model giữ nguyên `phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1`, ONNX CPU. Mapping đọc từ runtime metadata/class_name, không suy class ID từ trí nhớ.
- Lần nghiệm thu trước có 92 tests PASS. Đây là baseline lịch sử, không chứng minh code task05–06 đã được test.
- Task04 vẫn IN_PROGRESS: công cụ pass, roster/annotations/coverage v2 thật chưa được duyệt, rules/protocol draft và split chưa khóa. Phải kiểm tra lại trạng thái lúc thực thi.
- Tại baseline bàn giao, task06 chưa có tracking/team/identity production. Detection G03 không chứa track_id hoặc team_id ổn định; xây tracker thật ở giai đoạn task06, không lấy thứ tự bbox làm identity.
- Clip04–07 tiếp tục là holdout v1. Không dùng footage này cho chọn điểm, demo, debug hoặc tuning task05–06, kể cả khi đổi filename.

Source timestamp là `source_time_s` của G03; bbox nằm trên frame gốc `original_wh`. Dùng run/source hash để liên kết filename ID với manifest ID, không mặc định tên v1/v2 giống nhau.

## 3. Đầu vào người dùng và phần được làm độc lập

Ngay đầu lượt, kiểm tra đã có calibration/landmarks hoặc dữ liệu mới hay chưa. Chỉ hỏi phần thật sự thiếu, nêu cụ thể:

- Video/camera/segment phát triển có quyền sử dụng; source/session và ranh giới cut, pan/zoom hoặc excluded.
- Ít nhất 4 cặp điểm tương ứng **cùng mặt phẳng sân**, có phân bố tốt, không suy biến; điểm ảnh theo frame gốc và tọa độ sân có định nghĩa.
- Orientation/origin/axes, nửa sân/vùng phân tích, ROI và scale/đơn vị. Nếu dùng mét cần kích thước/nguồn xác minh; chưa đủ scale thì chọn tọa độ normalized và ghi rõ giới hạn.
- Các mẫu chân nhìn rõ cùng tọa độ tham chiếu độc lập, reviewer và nguồn bằng chứng để đánh giá vị trí; không lấy điểm dùng fit làm bộ kiểm chứng độc lập.
- Footage development hai đội phân biệt được màu áo, có đủ crossing/occlusion/reacquire và một số thời điểm nhìn được số áo; roster team/player/jersey có phạm vi phiên rõ, mẫu màu đội được cung cấp trước phiên nếu có.
- GT track/team/identity qua che khuất/thay người và các mốc hành động cần attribution để đánh giá; review/provenance rõ. Không yêu cầu người dùng gán actor từng pha khi chạy production.

Không yêu cầu đầy đủ nhãn rebounds/assists mới bắt đầu xây `court.py`/`heatmap.py`. Task05 cần phần geometry/position liên quan của task04; roster/team thật và PRA evaluation có gate riêng. Không chờ team classifier task06 để tạo API/fixtures task05.

Nếu thiếu đầu vào, tiếp tục công cụ cấu hình, contracts, solver, accumulator, tracker/resolver scaffolds, CLI, fixtures, tests và report theo đúng giai đoạn. Tạo checklist yêu cầu dữ liệu cho từng gate. Không chạy production calibration giả hoặc đánh task05/task06 DONE. Khi hỏi, tiếp tục việc không phụ thuộc câu trả lời; im lặng không phải phê duyệt.

Trước chỉnh sửa, ghi execution checklist và fingerprint baseline dữ liệu cần bảo vệ; xem code/test/doc đang thay đổi nếu có Git, không tự git init/commit/push nếu workspace chưa có repository. Chỉ chuyển task tương ứng sang IN_PROGRESS khi thực sự bắt đầu triển khai, không đổi status chỉ vì prompt được tạo.

## 4. Giai đoạn B — Thiết kế và triển khai task05

### A. Court configuration và homography

1. Tạo `court.py` và cấu hình versioned dưới `codebase/configs/courts/`. Có schema/template dùng được, phân biệt rõ template/draft/validated; template chưa có điểm thật phải bị từ chối khi chạy calibrated mode. Fixture synthetic để trong tests, không đóng giả camera thật.
2. Config lưu ít nhất: schema/calibration version, camera/segment ID, source hash/ref, original image dimensions, reference frame/PTS, point correspondences, origin/axes/orientation, units/scale status, court bounds/ROI, thresholds và provenance/review status.
3. Tạo công cụ chọn/nhập cặp điểm và preview đánh số điểm, ROI, lưới sân chiếu lên ảnh. Ưu tiên CLI/file JSON và xuất ảnh headless; không cần dựng web app hoặc mở GUI chỉ để hoàn thành task. Nếu cần nhập điểm bằng tay, cung cấp định dạng và validate rõ, không tự chọn điểm mơ hồ trên clip02.
4. Giải homography bằng thư viện hiện có, giữ hướng image→court và court→image tường minh. Kiểm tra số điểm, finite values, duplicate/collinear/near-degenerate points, matrix rank/conditioning/invertibility và mẫu số projective gần 0. Nếu dùng RANSAC, báo inlier mask, ngưỡng và mọi điểm bị loại.
5. Báo residual fit theo pixel và/hoặc court units đúng ngữ cảnh. Với đúng 4 cặp điểm, residual gần 0 chưa chứng minh geometry thật chính xác. Dùng independent check points/visible-foot GT để đánh giá ngoài fit khi có.
6. Kiểm tra ROI/polygon hợp lệ, điểm ngoài sân và orientation; không clip mọi điểm vào biên rồi gọi hợp lệ. Không tự coi toàn ảnh là sân thi đấu, cũng không tự gán mọi human là player.
7. **Vành rổ/bảng rổ không nằm trên mặt sân**, không dùng làm correspondence cho homography mặt sân. Vị trí rổ chiếu xuống sân chỉ được dùng nếu có evidence và định nghĩa tọa độ phù hợp. ROI rổ trong ảnh và tọa độ chiếu trên sân phải tách riêng.
8. Pan/zoom/cut hoặc thay kích thước ảnh/góc quay làm calibration cũ mất hiệu lực: invalidate/reset theo segment. Hỗ trợ ranh giới khai báo trước; chưa được tuyên bố đã có automatic cut/camera-motion detection. Không thêm camera-motion compensation trong task này.
9. ROI/rim/arc/zone definitions phục vụ task06/08 phải có nguồn, status và units. Không tự vẽ cung theo giả định sân chuẩn; nếu chưa đủ geometry/rules thì để pending, không dùng để tự xác nhận shot value.

### B. Footpoint, projection và trajectory contract

1. Baseline footpoint từ bbox có thể dùng `((x1+x2)/2, y2)`, nhưng phải ghi `position_method=bbox_bottom_center` và thể hiện đây là ước lượng. Không gọi bbox bottom là chân chạm đất chắc chắn; không mặc định phát hiện được occlusion từ detector hiện có.
2. Bbox crop/touch boundary, outside ROI, invalid projection, unknown visibility hoặc occluded phải có status/reason. Không thêm pose/keypoint model âm thầm để giải quyết.
3. Contract trajectory/observation nên có: schema version, observation ID, source run/video/hash, frame_index, source_time_s, timestamp_status, segment/camera, bbox/image point, projected court point và units, position method/evidence, validity/reason, calibration version, optional track/player/team cùng nguồn/version mapping.
4. Phân biệt observed/estimated/predicted. Bbox-derived footpoint vẫn là vị trí ước lượng từ detection quan sát; không biến nó thành labeled ground truth. Missing/occluded/predicted-only samples phải tách khỏi heatmap chính theo policy khai báo.
5. Ở checkpoint task05, thiết kế API nhận observations từ tracker task06 và test bằng fixtures. Chưa có tracker thì track_id/player_id để unknown/null; **không** dùng bbox index hoặc tạo ID bền vững giả để nối người qua frame. Triển khai tracker/team/OCR ở giai đoạn task06 sau checkpoint, không trộn vào evidence G05 ban đầu.
6. Lưu đủ raw observations và refs để chiếu lại khi đổi calibration, đổi team hoặc loại track. Chỉ lưu tọa độ court/PNG là chưa đủ để recompute geometry. Raw logs bất biến theo run; revisions tạo output mới.
7. Nếu team/identity chưa có, chỉ xuất unknown/unattributed hợp lệ, không dùng roster/annotations/GT làm runtime classifier. Heatmap cá nhân chỉ được xuất khi upstream identity đủ evidence.

### C. Heatmap theo thời gian, coverage và replay

1. Tạo `heatmap.py` nhận position/time/team contract, không phụ thuộc trực tiếp Roboflow hoặc bộ GT. Đơn vị tích lũy là **player-seconds**; tổng thể, theo team và unknown là các nhóm tách bạch. Không cộng một đơn vị mỗi frame.
2. Khai báo một integration convention nhất quán, ví dụ left-hold trên `[t_i,t_(i+1))` trong cùng segment/track đã xác định, và ghi rõ causal/look-ahead/finalization behavior. Với observation batch không có track IDs, chỉ cho phép diagnostic aggregate occupancy được ghi nhãn rõ; không suy trajectories hay metrics theo cầu thủ từ đó.
3. Chọn và snapshot `max_gap_s`/staleness policy. Gap vượt ngưỡng phải ngắt, không dùng `min(delta_t,max_gap_s)` để âm thầm cộng một phần mất quan sát. Không cộng qua cut/calibration change/mất dấu dài hoặc predicted-only spans; không gán trọng số âm cho duplicate/out-of-order timestamps.
4. Cắt interval theo đúng giao với valid coverage và declared exclusions. Nếu interval băng qua vùng excluded/cut/gap, không nối vị trí xuyên qua ranh giới bằng một phép trừ timestamps đơn giản. Semantics và tests phải thống nhất.
   Operational coverage/exclusions lấy từ config trước phiên và evidence upstream, không tự đọc annotation/review ledger làm runtime oracle. Coverage ground truth chỉ dùng ở đường evaluation riêng; nếu dùng cho một diagnostic, ghi rõ đây là chế độ đánh giá, không phải production heatmap tự động.
5. Mẫu cuối chưa có timestamp kế tiếp không tự nhận `1/fps`. Chỉ đóng interval khi có end boundary/duration được xác minh và thỏa staleness policy; nếu không, bỏ phần chưa biết và báo coverage thiếu. Pause là wall-clock event, không được làm tăng video-time occupancy.
6. Repaired/estimated/irregular PTS phải có policy rõ: loại, ngắt hoặc cho phép repaired timeline với cảnh báo và tổng thời lượng bị ảnh hưởng; không đổi chúng thành valid. Frame cuối clip02 là regression thực tế cần đối chiếu G03.
7. Deduplicate bằng source observation/interval key ổn định; pause/resume/reload/seek/replay cùng input không cộng lặp. Out-of-order có policy reject/rebuild/checkpoint rõ. Không trộn nhiều revision/calibration bằng cách append các counts vào heatmap cũ.
8. Recompute từ raw trajectories sau sửa team/calibration/track exclusions phải thay thế view cũ hoặc tạo revision mới, không cộng chồng. Không cần xây full dashboard/seek UI, nhưng API và tests phải chứng minh replay idempotent.
9. Grid có bounds/cell size/units rõ; xử lý biên đúng một cell, outside/invalid không được clamp thành mass hợp lệ. Density/probability/colormap chỉ là visualization view, không thay raw accumulation.
10. Bảo toàn mass: tổng grid raw bằng tổng valid integrated player-seconds trong tolerance; total bằng known-team + unknown. Team unknown không phải đội thứ ba chính thức. Báo valid, excluded, stale/missing, invalid/outside và predicted-only coverage riêng; không gọi thời lượng không thấy người là 0 player-seconds chắc chắn.

### D. Integration và CLI

1. Ưu tiên tái dùng `run.json`/`detections.jsonl` G03 verified; không chạy lại model đầy clip chỉ để vẽ heatmap. Kiểm tra source hash, dimensions, index/PTS/schema và metadata đầu vào trước dùng. Không làm sai contracts G03 hoặc nới holdout guard để chạy.
2. Thiết kế CLI/script dưới `codebase/scripts/` cho config validation, preview calibration, projection/heatmap và replay/recompute. Tên option là lựa chọn implementation, nhưng README/report phải ghi lệnh thực đã chạy; không chỉ ghi ví dụ không tồn tại.
3. Artifacts gồm config snapshot, raw/projected trajectories, raw grid có thể đọc lại, PNG có legend/units, metadata counts/coverage/errors, versions/hashes, input/ref và status. Empty/unknown/no-calibration là trạng thái rõ ràng, không sinh success metrics giả.
4. Config thật chưa validated thì calibrated run phải từ chối rõ hoặc tạo output draft/pending tách biệt. Có thể demo API/PNG bằng synthetic fixtures được đánh nhãn `synthetic`; không đặt tên hoặc mô tả như heatmap sân clip02 đã được nghiệm thu.
5. Diagnostic heatmap theo ảnh, nếu có, phải ghi image-space, units và giới hạn; không dùng nó thay đầu ra court-space trong checklist task05.
6. Tạo output directory mới, không overwrite video/run/config đã duyệt; lỗi đọc/config/writer không ghi completed giả. Chỉ phần CLI shared cần thiết mới sửa app/config; giữ pipeline detection chạy độc lập như trước.
7. Dùng NumPy/OpenCV/Matplotlib và các dependency đã có sau khi xác minh import/version. Không cài lại môi trường, không thêm framework/web/backend/pose/OCR/model hoặc GPU stack ngoài nhu cầu task05.

## 5. Outputs task05 bắt buộc

| Nhóm | Artifacts |
|---|---|
| Core | `codebase/src/basketball_scoreboard/court.py`, `heatmap.py`; contracts/config mở rộng tương thích khi cần |
| Tooling | CLI/scripts chọn/validate/preview calibration và chạy/recompute heatmap |
| Config | `codebase/configs/courts/<camera>.json` nếu có dữ liệu thật; nếu chưa có thì schema/template được nhận diện rõ, không kích hoạt calibrated production mode |
| Tests | Homography, projections, time/coverage, mass conservation, idempotence/revisions và failure cases |
| Run mới | `codebase/outputs/<new-task05-run>/`: trajectories, raw grids, PNG, metadata/config/hash snapshots, tests/audit evidence |
| Spec/guide | `docs/specs/court-heatmap-v2.md`; `docs/guides/court-calibration.md`; cập nhật `contracts-v2.md` tương thích nếu mở rộng |
| Report | `docs/reports/task05-court-heatmap.md` |
| Handoff | `docs/handoffs/task05-to-task06-08-12.md` |
| Usage/status | `codebase/README.md`, task05 và task index; PLAN chỉ chỉnh trạng thái khi có evidence |

Các đường dẫn mới trong bảng là đầu ra cần tạo, không khẳng định đã có sẵn. Tạo thư mục docs/guides nếu cần. Không chỉnh report/snapshot nghiệm thu lịch sử để che thay đổi; ghi snapshot mới cho task05.

## 6. Kiểm thử và checkpoint task05

### G05-T — Công cụ và contracts

Viết tests gắn với rủi ro thực tế, dùng fixtures độc lập; ít nhất chứng minh:

- Homography identity/known transform, round-trip trong tolerance, orientation/ảnh dọc, points ngoài ROI và denominator gần 0.
- Reject <4 correspondences, duplicate/collinear/near-degenerate hoặc NaN/Inf; image dimensions/config/camera/version không khớp không được dùng âm thầm.
- Independent check points không trộn với fit residual; thiếu scale không báo centimet/mét.
- Cùng quỹ đạo/thời lượng ở sampling rates khác nhau và VFR cho cùng mass trong tolerance. **3 người quan sát hợp lệ ×2s =6 player-seconds**, không phụ thuộc số frames.
- Excluded/cut/long gap/predicted-only spans không tích lũy; boundary/last-sample/zero or negative delta_t/duplicate timestamps được xử lý rõ.
- Team inputs A/B/unknown từ fixtures bảo toàn mass; unknown không bị ép vào A/B. Không dùng detection index thành track ID.
- Replay input hai lần, pause/resume, checkpoint/reload, seek hoặc out-of-order theo policy không nhân đôi counts; đổi team/calibration/track filtering recompute không cộng chồng.
- Repaired end-of-clip timestamps của G03 theo policy đã chọn không tạo zero/negative weight hoặc khẳng định PTS nguyên vẹn.
- Metadata/error/output-overwrite guards hoạt động; PNG/raw grid/trajectory có thể mở lại, schema/units/counts khớp và mass được kiểm tra độc lập.

Baseline command từ workspace root:

```powershell
codebase/.venv/Scripts/python.exe -m unittest discover -s codebase/tests -v
codebase/.venv/Scripts/python.exe codebase/scripts/validate_dataset.py --require-ready
codebase/.venv/Scripts/python.exe codebase/scripts/validate_dataset_v2.py --require-tooling-ready
```

Dùng interpreter hiện có, không lệnh `python` hệ thống tùy ý. Chạy tests task05 và regression chung phù hợp thay đổi; ghi actual count, exits và log. Chỉ chạy lại/broaden khi có thay đổi hoặc lỗi cần xác minh. Không lấy 92 baseline PASS cũ thay kết quả mới. Nếu môi trường/dependency không đủ, ghi lỗi thực và xin quyết định đúng phần phụ thuộc; không tự cài runtime mới.

`--require-data-ready`/`--require-locked` v2 có thể vẫn fail đúng kỳ vọng do task04 mở; báo readiness và exit riêng, không sửa dataset/flags để pass task05.

Sau G05-T, ghi checkpoint vào report và tiếp tục integration có dữ liệu hợp lệ. Không dừng chỉ để xin phép chuyển checkpoint nếu đã có đủ đầu vào được giao.

### G05-G — Geometry trên dữ liệu thật

Chỉ PASS khi có correspondences/ROI/orientation/scale phù hợp và visible-foot GT độc lập đã review. Ghi sample count, visibility/uncertainty, vùng sân bao phủ, median position error và normalized error theo chiều rộng vùng phân tích; mục tiêu median ≤5% như task05.

Nếu court units normalized, công thức và orientation phải rõ; không giả vờ đây là error theo mét. Báo cả coverage và số mẫu bị bỏ; không chỉ chấm các điểm dễ để đạt ngưỡng. Residual 4 fit points hoặc synthetic transform không thay GT video thật.

Thiếu landmarks/GT → **PENDING**, metrics N/A; vẫn bàn giao G05-T và file yêu cầu dữ liệu cụ thể. Không đổi ngưỡng sau khi xem test.

### G05-I — Integration và handoff

Tích hợp trên technical input thật chỉ trong mức evidence cho phép. Với calibration thật hợp lệ, đọc lại trajectories/grid/PNG/metadata, kiểm tra coords/mass/coverage/config refs độc lập. Chưa có calibration thì demo synthetic và diagnostic adapter G03 phải được gắn nhãn riêng; không tuyên bố heatmap court thật đã xác minh.

Tại checkpoint G05, team/identity thật còn phụ thuộc task06; task05 không cần tự xây classifier để chốt API. Handoff ghi rõ acceptance hình học task05 và acceptance team/personal heatmaps là hai phần khác nhau. Sau task06, kiểm tra adapter track/team→heatmap trong mục 10; full dashboard vẫn thuộc task12.

## 7. Bảo toàn codebase, dữ liệu và quyền

- Giữ đúng detector/backend/cache safeguards; không tắt hash/TLS hoặc nới bảo vệ custom code. Task này mặc định không cần API key hay tải model vì tái dùng predictions verified.
- Không dump `.env`, key, SDK URLs có credentials; không upload media hoặc cloud inference. Nếu phải tải metadata/weights lại, kiểm tra authorization đang có và cơ chế xin quyền thực tế; không đổi detector hoặc né network/sandbox.
- Không sửa dữ liệu/nhãn/splits v1, holdout v1, approved/locked labels v2 hoặc evidence cũ. Chỉ tạo proposal/revision mới khi cần; không tự phê duyệt landmarks/roster/labels thay người dùng.
- Kiểm tra fingerprint nguồn/dataset quan trọng trước/sau; phân biệt hash dữ liệu bất biến với hash docs/code thay đổi hợp lệ ở phiên bản mới. Không ghi đè snapshot ngày 2026-11-02 để làm như tài liệu lịch sử chưa từng đổi.
- Hỏi trước phần phụ thuộc cần đổi scope/model/backend/dependency lớn/GPU/cloud/chi phí hoặc thay locked data. Tiếp tục phần độc lập trong lúc chờ. Không hỏi lại automatic PRA đã duyệt, có tiếp tục task06 hay có được sửa bug thường lệ trong phạm vi task05–06.
- Không tự spawn/delegate sub-agents chỉ vì có nhiều phần độc lập; tuân theo authorization và hướng dẫn áp dụng của phiên làm việc.

## 8. Checkpoint giữa hai task — report và handoff G05

`docs/reports/task05-court-heatmap.md` cần có:

1. Scope/version/ngày, trạng thái riêng G05-T/G05-G/G05-I, và task05 DONE hay IN_PROGRESS.
2. Yêu cầu → implementation → test/artifact → PASS/FAIL/PENDING; issues đã sửa và còn mở.
3. Input/source run/hash, calibration/segment/version/units/scale status, config và temporal/exclusion policy; actual commands, working directory, exits và log paths.
4. Geometry metrics với cỡ mẫu/coverage hoặc N/A có lý do; tách fit residual, synthetic evidence và independent GT evaluation.
5. Raw player-seconds/mass accounting, unknown/excluded/stale/invalid/predicted coverage, replay/recompute evidence; không lấy PNG đẹp thay kiểm tra số.
6. Danh sách file đã thay đổi, compatibility/regression results, bảo toàn baseline và limitations.
7. Đầu vào người dùng còn thiếu được chỉ rõ theo camera/video/point/GT/review; không chỉ ghi chung chung “cần thêm dữ liệu”.

`docs/handoffs/task05-to-task06-08-12.md` cần có:

- Task06: ROI/geometry validity, source coordinate system, footpoint/observation API, track/team nullable contracts và version/reset policy.
- Task08: court units/orientation và arc/rim ROI sources/status/uncertainty; giới hạn homography/pose khi phân loại vị trí chân tại release. Không coi player bbox bottom là shot-value ground truth.
- Task12: grid/raw trajectories/metadata schema, units/colormap/coverage, replay/recompute entrypoints và phần cần tích hợp team từ task06.
- Lệnh chạy thật, input/output mới, verified vs synthetic vs pending, dependencies chưa có và acceptance chưa đạt.

Chỉ đánh **Task05 DONE** khi checklist task05 có evidence thật trong phạm vi của nó, không vì fixtures/tooling pass. Thiếu geometry/visible-foot GT thì giữ **IN_PROGRESS — tooling implemented, geometry/data acceptance pending**. Không đóng task04 thay người dùng và không gọi toàn bộ MVP hoàn tất. Không giữ task05 mở chỉ vì chưa có nhãn assist không liên quan đến geometry; team integration task12 vẫn có thể là việc bàn giao tương lai được ghi rõ.

Trước chuyển task06, hoàn tất report/handoff task05 với evidence thực tế và một cập nhật tiến độ ngắn. Phân biệt `G05-T PASS / G05-G PENDING` với toàn G05 PASS. Không gom mọi report tới cuối hai task mới viết. Sau đó **tiếp tục ngay mục 9**; đây là checkpoint, không phải điểm kết thúc lượt.

Nếu lỗi còn mở ở API/ROI/PTS, khoanh vùng và sửa trước khi cho task06 dùng phần bị lỗi. Nếu chỉ thiếu landmarks/GT thật, vẫn có thể triển khai tracker, team/identity contracts và tests bằng image-space/synthetic fixtures; chưa nghiệm thu geometry hoặc heatmap court thật. Không tạo ROI hay calibration giả để tuyên bố dependency đã đủ.

## 9. Giai đoạn C — Task06: player tracking, team và identity

### C1. Tracking người và vai trò trong sân

1. Tạo `players.py`, `identity.py`, config tracker/team/identity và CLI/adapter cần thiết. Tái dùng detector predictions G03, ROI/coordinate contracts từ checkpoint G05. Tận dụng dependency hiện có sau khi xác minh API/version; không cài tracker/ReID stack mới chỉ vì thuận tiện.
2. Tracker nhận bbox/confidence, source timestamps và segment context. Association/lifecycle phải xử lý duplicate detections, crossing, occlusion, lost/reacquire, stale timeout và các sampling rates khác nhau. Không lấy số frame làm số giây trên VFR; nếu thư viện tracker dùng frame counters, adapter phải ghi rõ giới hạn và policy thời gian đã kiểm thử.
3. Track ID duy nhất trong namespace run/video/segment, khác player ID roster. Có lifecycle/evidence cho tentative/active/lost/retired hoặc trạng thái tương đương, reset khi cut/đổi camera; không nối track xuyên cut chỉ vì bbox gần nhau.
4. Dùng valid ROI và evidence để phân player/non-player/unknown. Staff/referee/spectator vẫn có thể nằm trong ROI; chỉ ở trong ROI chưa chứng minh player. Nếu chưa có ROI đúng, chỉ xuất diagnostic human tracks với role unknown, không gọi là player tracking trong sân đã nghiệm thu.
5. Detections observed khác tracker predictions/interpolations. Mất detection phải phản ánh missing/predicted status, không phát sinh observation giả để tăng coverage hoặc tích lũy heatmap chính.
6. Merge/split/reacquire phải có evidence và revision; không tái sử dụng ID cho người khác trong cùng namespace. Không tự gộp identity sau thay người; phát hiện conflict khi một player bị gán đồng thời cho hai active tracks không phù hợp.

### C2. Phân đội theo evidence thời gian

1. Tạo classifier baseline phù hợp bằng appearance/màu áo theo thời gian, chọn vùng áo và lọc background/da/số áo khi có thể. Team A/B là configuration trước phiên, không phải màu cluster ngẫu nhiên tự gọi thành tên đội thật.
2. Lưu evidence, sample count, mapping version và unknown reason. Xử lý màu áo gần nhau, ánh sáng/che khuất, crop nhỏ và thay đổi một frame; không ép mọi human/track vào A hoặc B. Stabilization không được giữ team cũ vô hạn khi evidence đã hết hoặc có conflict.
3. Mẫu màu/team prototypes do cấu hình trước phiên là đầu vào được phép. Label team/identity theo từng frame hoặc annotation IDs không được đi vào recognition runtime. GT chỉ được evaluator đọc trên đường riêng.
4. Không gọi heuristic score là calibrated probability. Nếu không đủ evidence thì team unknown; tiếp tục giữ và báo unknown/missed coverage, không bỏ các đoạn khó khỏi mẫu số.

### C3. Identity resolver và quyết định OCR/model

1. Roster được đọc như config hợp lệ gồm team/player/jersey, phạm vi phiên, active status và aliases cần thiết. Kiểm tra player ID duy nhất, team-jersey consistency, duplicate/conflict; hai đội có thể có cùng số áo nên không map jersey→player toàn cục.
2. Xây resolver kết hợp evidence số áo/OCR, team và lịch sử track/appearance với thresholds/hysteresis/expiry rõ. Một frame OCR đọc sai không được đổi player ngay. Appearance chỉ hỗ trợ duy trì liên kết đã có evidence; không tự tạo ánh xạ tên roster từ màu áo/thứ tự người.
3. Không có jersey/identity evidence hợp lệ trong lịch sử liên quan → player_id unresolved. Team có thể known trong khi player unknown; track vẫn có giá trị mà không phải identity đã nhận đúng. Không tự ép đủ 6 player hoặc bịa số áo cho clip02.
4. Kiểm tra OCR/runtime/weights thật sự đã có trên máy. Package OCR đã cài không chứng minh weights có sẵn hoặc đã được duyệt. Adapter mock/fixtures đủ test resolver nhưng không chứng minh production OCR đã hoạt động.
5. Nếu cần model/weights OCR/pose/ReID bổ sung, lập decision record với nhu cầu, nguồn chính thức, model/version/license, runtime/dependencies, kích thước tải, CPU latency dự kiến/cần đo, local-vs-cloud và phương án đánh giá. Tuân theo authorization hiện có, hỏi trước phần chưa được duyệt theo mục 7; không tự tải model lớn, cloud upload hoặc đổi detector. Dùng tài liệu chính thức theo đúng phiên bản khi cần xác minh API.
6. Trong lúc chờ quyết định/footage/roster, hoàn thiện interfaces, validation, evidence aggregator, unknown/conflict handling và tests; báo model/data acceptance pending. Không thay OCR bằng bảng GT track→player để tuyên bố tự nhận dạng.
7. Lưu mapping track→team/player theo interval/revision với evidence refs, first/last evidence time và conflict status. Khai báo causal confirmation delay; nếu offline smoothing dùng tương lai hoặc sửa các interval cũ, xuất revision/replay view riêng, không âm thầm gọi đó là streaming causal.

### C4. Contracts, exports và adapter tới heatmap

1. Player observation gồm ít nhất: observation/track/run/video/source refs, frame/PTS/timestamp status, segment, bbox/footpoint, observed/predicted/role, team_id/player_id nullable, evidence scores/status/reasons và tracker/team/identity/config versions. Court position/calibration ref chỉ có khi geometry hợp lệ.
2. Xuất trajectories/player observations và identity/team evidence logs có schema version, raw evidence refs và mapping intervals; không chỉ video overlay. IDs/revisions phải replay được, parse lại được và không trùng.
3. Adapter đưa observed valid player positions và team/unknown vào heatmap task05. Unknown player nhưng known team có thể đóng góp heatmap đội theo policy; heatmap cá nhân phải có identity đủ evidence. Không đưa non-player/predicted-only hoặc vị trí court invalid vào mass hợp lệ.
4. Không cần xây dashboard task12. Cần chứng minh pipeline dữ liệu tự động từ detections→tracks→team/identity→projection/heatmap, và recompute khi mapping đổi mà không nhân đôi player-seconds.
5. Khi thiếu input thật, tạo demo synthetic được gắn nhãn riêng và diagnostic human tracking trên clip02 nếu phù hợp. Không dùng một người không có jersey làm benchmark hai đội hoặc bằng chứng player recognition đúng.

### C5. Kiểm thử và gate task06

Viết tests có assertions về hành vi và evidence, ít nhất:

- Crossing/occlusion/lost/reacquire/cut/reset, bbox order thay đổi, duplicate detection, missing frames và VFR timeouts; bbox index không phải identity.
- Player/non-player/unknown ROI handling; spectator trong ROI không tự thành player, thiếu ROI không tự thành court-valid.
- Hai đội cùng jersey number, duplicate active player/conflict, jersey đổi sai một frame, evidence expiry, substitution và cùng player trên hai active tracks.
- Team ambiguous/unknown, one-frame color noise, team mapping/revision; thiếu identity evidence không sinh player_id.
- Replay/restart cho IDs/mapping/intervals ổn định hoặc có revision semantics xác định; pending/failed OCR không bịa evidence.
- GT files không nằm trên production path; mocks/synthetic và real OCR outputs được phân biệt trong artifacts.

`G06-T` PASS khi code/contracts/tooling/tests có evidence. `G06-D` chỉ PASS khi video hai đội, roster và reviewed track/team/identity GT phù hợp cho thấy hệ thống chạy tự động, xử lý unknown/conflict và đạt điều kiện task06. Chưa có footage/model/GT → PENDING, không lấy fixture PASS thay data acceptance.

Trước nhìn kết quả đánh giá thật, ghi rõ matching GT↔pred observations/tracks, eligible time spans, windows/thresholds và mẫu số. GT ID chỉ dùng matching/evaluation, không đưa vào tracker/resolver. Báo:

- Team correctness trên tập GT eligible, unknown/missed/wrong counts và coverage. Mục tiêu ≥90%; báo riêng accuracy có điều kiện trên assigned samples nếu cần chẩn đoán, không dùng nó thay kết quả bao gồm unknown/misses.
- ID switches/fragmentation, false/missed human/player detections, team/identity conflicts và identity attribution coverage theo thời gian; interval hoặc event-time metrics chỉ khi có GT mốc tương ứng.
- Player identity correctness và unresolved riêng với team correctness; không gọi team accuracy là player identity accuracy.
- Cỡ mẫu/video/session/visibility, confirmation latency, runtime cost và giới hạn. Mẫu số 0 → N/A, không 100%. Unknown trên GT hợp lệ không bị bỏ để nâng số.

Outputs task06: `players.py`, `identity.py`, configs/schema, player observations/trajectories, evidence logs, `docs/specs/player-identity-v2.md`, `docs/reports/task06-players-identity.md`, và decision record trong `docs/decisions/` nếu cần model bổ sung. Chưa có roster thật thì chỉ tạo template/proposal nhận diện rõ, không ghi đè data/v2/roster.csv hoặc tạo approval.

## 10. Giai đoạn D — Kiểm thử tích hợp hai task (G56)

Sau tests/report riêng task06, chạy adapter tích hợp với task05. Không dừng khi chỉ có các modules test riêng lẻ.

1. Nối đúng namespaces, source hash/video/frame/PTS, image dimensions, ROI/camera/segment và calibration version. Track ID, player ID, team ID không hoán đổi; predicted positions không biến thành observed khi project.
2. Với fixture độc lập có known geometry/tracks/team, kiểm tra detections→tracking→projection→heatmap, tổng mass bằng valid player-seconds và bằng known-team + unknown. Có cả missing/occluded/non-player/cut để phát hiện sai lệch coverage.
3. Replay toàn chuỗi hai lần, checkpoint/reload/seek theo policy; thay team hoặc hợp nhất/tách mapping rồi recompute. Kết quả không nhân đôi observation IDs, mapping intervals hoặc heatmap mass.
4. Mapping theo thời gian phải được áp cho đúng interval. Sau team revision, rebuild từ raw observations đúng version; không sửa mutable team field của track rồi retroactively gán cả lịch sử mà không ghi revision.
5. Nếu có development footage hai đội/geometry thật hợp lệ: chạy integration local, đọc lại artifacts và đối chiếu GT độc lập. Không inference holdout để debug. Tái dùng detections verified; chỉ re-inference khi cần footage mới hoặc thay đổi adapter/detector input có lý do và trong authorization.
6. Nếu geometry hoặc identity GT còn thiếu: tách `synthetic integration PASS`, `technical real-input diagnostic`, `real-data acceptance PENDING`. Không đặt clip02 thành demo trận hai đội, không xuất heatmap cá nhân có tên giả.
7. Chạy regression phù hợp cho shared contracts/G03 và dataset validators. Lần kiểm thử cuối phải phản ánh code cuối; không lặp benchmark toàn bộ nhiều lần nếu không có lỗi/thay đổi mới. Đọc lại PNG/grid/log/metadata và kiểm tra local docs links/fingerprints; không chỉ xác nhận file tồn tại.

G56 không tự đóng G04, không chứng minh points/rebounds/assists đã hoạt động hoặc đạt gần100%. Thời gian thực cần benchmark riêng; phân biệt tốc độ xử lý offline với playback video.

## 11. Nghiệm thu và bàn giao cuối hai task

Tạo `docs/reports/task05-task06-acceptance.md` với kết quả riêng từng gate:

| Gate | Bằng chứng tối thiểu | Nếu thiếu |
|---|---|---|
| G05-T | Court/heatmap tools, contracts, meaningful tests | Sửa code; chưa dùng API lỗi cho task06 |
| G05-G | Landmarks/independent visible-foot GT, geometry error và coverage | Geometry PENDING; không bịa calibration |
| G05-I | Projection/heatmap integration đúng theo mức input có thật | Phân loại synthetic/diagnostic/real rõ |
| G06-T | Tracker/team/identity tooling, evidence/replay tests | Sửa code hoặc nêu dependency/model cần quyết định |
| G06-D | Tự động trên footage hai đội, roster/GT và metrics task06 | Data/model acceptance PENDING, task06 chưa DONE |
| G56 | Adapter hai task, mass/coverage/revisions, replay và readback | Báo integration issue; không gọi cả hai DONE |

Report chung có actual commands/working directory/exits/test counts/logs, requirement→evidence matrix, inputs/config/model/calibration/contracts versions/hashes, geometry/team/identity metrics hoặc N/A, issues resolved/open, bảo toàn v1/holdout và phần cần người dùng cung cấp/quyết định. Số tests baseline cũ không thay log mới. Không chỉnh ngưỡng hoặc readiness flags để đạt PASS.

Handoff cuối: `docs/handoffs/task06-to-task07-08-12.md`, bao gồm:

- Task07: observed/predicted player tracks, team/player nullable, evidence/uncertainty, coordinate/time/segment và identity revision/reset API; chưa có ball/control/pass engine.
- Task08: court/ROI/arc/rim sources/status, track→actor mappings, release-time footpoint limitations; chưa có scorer/value engine.
- Task12: trajectories/grid/metadata, team/personal eligibility, replay/recompute API và những gì đã/chưa được kiểm chứng; chưa dựng full dashboard.
- Lệnh chạy thật, artifacts mở được, tests/fingerprints, input requirement và acceptance còn pending; không chỉ ghi “đã xong”.

Cập nhật `codebase/README.md`, specs/contracts liên quan, task05/task06/task index và trạng thái PLAN theo evidence. Giữ report/handoff checkpoint task05, report task06 và report chung thành ba bằng chứng riêng. Snapshot task05–06 mới không ghi đè snapshot G03/G04.

Chỉ gọi task05 hoặc task06 DONE khi tiêu chí tương ứng có bằng chứng; hai task có thể có trạng thái khác nhau. Thiếu data/model thì hoàn tất tooling và bàn giao có giới hạn, giữ IN_PROGRESS đúng phần. Không chặn nghiệm thu geometry chỉ vì chưa có nhãn assist, cũng không nghiệm thu team/identity khi chỉ có synthetic fixtures. Cần làm hết phần độc lập đã được giao, không dừng ở một bản đề xuất hoặc xin phép chuyển task thường lệ.

Kết thúc bằng tiếng Việt, tự đầy đủ: trạng thái riêng task05/task06/G56; phần đã xây; số liệu/tests thực; links report G05, handoff ở giữa, report G06, acceptance chung và handoff cuối; giới hạn, phần chờ và điều kiện tiếp tục task07. Trong lúc làm, cập nhật tiến độ ngắn ở các phát hiện/checkpoint; không để một inference dài làm người dùng mất thông tin.
