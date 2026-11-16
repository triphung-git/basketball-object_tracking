# Task07B — crop ownership, team evidence và continuous replay

Ngày 2026-11-06. Đã triển khai và kiểm thử bước tiếp theo bằng nhãn đã có, không cần người dùng review thêm. **290 tests PASS. Task07 vẫn IN_PROGRESS.** Candidate hẹp sửa hai team errors trên mẫu review và giữ ball recall50%; guard đầy đủ bị regression nên không bật mặc định. Không train, đổi weights hoặc thêm dependency.

## Kết quả và quyết định

| Phương án | Team đúng tại7mốc crop đúng | Snapshot player đúng* | Ball observed recall /72 | Quan sát có player_id |
|---|---:|---:|---:|---:|
| Baseline phiên này |5/7|4/7|36/72=50%|859|
| Chỉ đổi vùng màu sang jersey |5/7|4/7|36/72=50%|859|
| Jersey + reset khi team xung đột mạnh |7/7|4/7|36/72=50%|695|
| Guard đầy đủ, hold ban đầu |5/7|1/7|35/72=48,61%|276|
| Guard có phục hồi từ frame hiện tại |7/7|2/7|33/72=45,83%|294|

*Team cohort là7crop được reviewer xác nhận đúng người/vùng và có team. Player cohort là7snapshot có team+số áo đủ tra roster, gồm một crop sai vùng nhưng người/số vẫn được reviewer xác định từ context. Hai cohort không hoàn toàn trùng nhau. Đây là điểm quan sát trong batch chọn lọc, không phải temporal identity accuracy hoặc kết quả trận độc lập.

**Đề xuất giữ candidate development:** `--team-crop-region jersey --reset-on-team-conflict`. Các flag mặc định tắt/legacy; chưa promote toàn pipeline. Tổng quan sát gánplayer_id giảm859→695; chưa có GT đủ để biết phần giảm gồm bao nhiêu false IDs được loại hay correct IDs bị mất. Không gọi7/7team là100%accuracy toàn video. Strict controller accuracy vẫn0%, pass recall0%, precisionN/A; chưa qua07B/07C.

Xem [video candidate900frame](../../codebase/outputs/task07b-ownership-20261106/ball-team-conflict-reset/debug.mp4), [full evaluation](../../codebase/outputs/task07b-ownership-20261106/ball-team-conflict-reset-evaluation/evaluation.json), [so sánh crop](../../codebase/outputs/task07b-ownership-20261106/evaluation-final/comparison.html), [evaluation chi tiết mọi trial](../../codebase/outputs/task07b-ownership-20261106/evaluation-final/evaluation.json).

## B1 — truy nguyên nguồn lỗi

Đã kiểm14mẫu theo source frame → human detection → track bbox → jersey crop → OCR/team proposal → causal mapping. Cả14bbox nguồn khớp rawhuman detection ở frame tương ứng; lỗi không chỉ do cropper tự chọn sai detection index.

- **Bảng điểm truyền hình nằm trong crop áo.** `crop_0033` chứa số09 của overlay, `crop_0136` chứa một phần graphics cạnh số6. Đây là lỗi vùng ảnh, không phải bằng chứng cầu thủ mặc09/7. Đã xác định mask từ bố cục ảnh nguồn, không dùng GT số áo/bóng: rectangle normalized `[.045,.78,.315,.965]`, gắn đúng SHA của đoạn development. Không áp mask này cho video/camera khác.
- **Human false positive trên bảng rổ.** `crop_0038` có bbox dạng người hợp lệ và khớp source detection, nhưng vùng pixel không đủ jersey-color support. Chỉ kiểm bbox hợp lệ/kích thước/contrast không phát hiện được lỗi ngữ nghĩa này.
- **Bbox gộp/che người.** `crop_0145` có haihuman detections khác chồng lên crop với tỷ lệ khoảng91,6%/79%; `crop_0151` còn khoảng38,8%. Không thể chọn số18/6 chỉ từ maxconfidence hoặc từ việc cùngtrack_id.
- **Người bị cắt ngang mép ảnh.** `crop_0055` có bbox chạm mép phải, crop chứa nền/banner và một phần trọng tài. Side-clipped gate chỉ làm identity uncertain, không tuyên bố mọi người chạm biên là non-player; không loại trường hợp chỉ chân bị cắt.
- **Team evidence cũ giữ mapping sai.** Với cùng decoded frame, cả vùng màulegacy vàjersey đều cho team đúng7/7crop tốt. Chỉ đổi vùng màu chưa sửa hai mapping sai. Tại265/630frames, instant color đúngTonga/Việt Nam nhưng consensus của track giữ đội cũ. Cần xử lý sự mâu thuẫn theo thời gian, không lấy crop-level7/7 làm bằng chứng resolver đã đúng.

[Geometry audit](../../codebase/outputs/task07b-ownership-20261106/baseline-source-geometry.json), [contact sheet source](../../codebase/outputs/task07b-ownership-20261106/identity-source-contact.jpg), [mask/crop before-after](../../codebase/outputs/task07b-ownership-20261106/crop-comparison-contact.jpg).

## B2 — thay đổi code đã thực hiện

`identity_crops.py` cung cấp policy source-bound và guard tùy chọn:

- Chỉ nhận observedhuman khớp source detection; predicted/untrusted clock/non_player không sinh confirmed evidence.
- Kiểm ownership bằng overlap với human khác, tách near-duplicate detection khỏi đối tượng khác.
- Mask HUD trên bản sao crop, giữ nguyên pixel ảnh nguồn và tọa độ. Color voting chỉ dùng pixel còn nhìn thấy, không tính vùngfillgray vào mẫu số.
- Giữ pending khi crop quá thiếu pixel hoặc không có jersey support. Đây là geometric/color cues, chưa phải một person/pose verifier.
- Hold ambiguity ban đầu0,75s gây chặn cả hai crop đúng sau occlusion. Giữ trial regression. Thử phục hồi bằng bằng chứng frame hiện tại: overlap nhỏ hơn ngưỡng, màu đội trội tương đối, ít màu đội cạnh tranh. Đây là tuning development, chưa xác minh tổng quát.

Kết quả probe trên cùng decoded pixels, cùngOCR upscale3:

| Probe | Crop đúng được giữ | Crop lỗi bị chặn | Exact OCR trên5readable crops | Team proposal trên7crop đúng |
|---|---:|---:|---:|---:|
| Legacy |7/7|0/7|4/5|7/7|
| Guard hold ban đầu |5/7|5/7|3/5|5/7|
| Guard phục hồi cuối |7/7|4/7|4/5|7/7|

Guard cuối chặn0038/0055/0145/0151.0033 được mask để bỏ reading09 của HUD, nhưng không khôi phục được số2 từ phần còn lại.0136 vẫn missingOCR; không suy đoán6 theo GT.0178/0192 vẫn có thể tạo reading sai vùng, nên không kết luận đã giải quyết đủ7crop lỗi. Missing/blocked vẫn nằm trong mẫu số5readable; không tăngaccuracy bằng cách bỏ mẫu.

39freshOCR calls tổng cộng qua3probe,0runtime error. Legacy predictions được reuse giữa các probe khi source/hash/crop scope/scale/weights khớp; không đọc nhãn trong recognition. Các replay900frame dùng cacheOCR đã xác minh. Khi mask thay pixel, cached reading cũ không được reuse; replay ghi rõ cần freshOCR cho crop đã đổi. Vì vậy fullguard replay chưa phải full freshOCR pipeline hoặc benchmark realtime.

## B3 — xử lý team conflict có causal ledger

`IdentityResolver.invalidate_track_evidence` đóng mapping tại thời điểm hiện tại, bỏ cả team và jersey evidence cũ, giữ lịch sử trước đó. Điều này ngăn số1 của độiA được thừa kế thành độiB chỉ vì hai đội có cùng số. Có test riêng cho case này và backward clock.

Trial hẹp giữ nguyên tracking boxes, raw detections, cachedOCR, roster và ball/control config. Chỉ đổi vùng màu, rồi thử thêm flag reset khi observed color có team đối lập mạnh với mapping cũ. Thresholdscore0,75 là heuristic, không phải probability đã calibrate. Có107reset events trên các track của đoạn30s; không diễn giải thành107lần cầu thủ thật đổi đội. Đây cũng là lý do chưa promote khi thiếu trajectory GT rộng hơn.

Tại14snapshot:

-265frame: mappingteamA→teamB khớp nhãnTonga#18; player_id vẫnunknown do chưa có đủOCR18.
-630frame: mappingteamB→teamA khớp nhãnViệt Nam#6; player_id vẫnunknown, không dùng đáp án6 để điền.
- Số snapshotplayer đúng không tăng:4/7. Nhiều crop sai vùng/không đọc được vẫn là blocker.

## Tác động downstream và fail trace

Ball association hiện dùng các observed tracks mang roleplayer làm context. Fullguard làm nhiều role thànhunknown, nên cùngball config và cùngrawdetections vẫn đổi trajectory được chọn. Đây là coupling giữa identity/role vàball association, không phải detector weights bị đổi. Fullguard vì vậy không được bật chỉ vì crop precision tốt hơn. Có [trace các GT matches bị mất và context actor counts](../../codebase/outputs/task07b-ownership-20261106/ball-context-regression.json).

Trial hẹp giữ observed recall36/72,0prediction-only confirmed control,0completed pass qua cut vàPTS export trong2µs. Đã xuất/đọc lại video900frames cho5paired ball runs. Điều này xác nhận integrity của các exports, không thay thế accuracy gate.

Phân rã14,299857giây eligible control:

| Trạng thái bằng chứng | Baseline(s) | Candidate hẹp(s) |
|---|---:|---:|
| Ball chưa observed |5,767|5,767|
| Có observedball nhưng control chưa confirmed |6,100|5,800|
| Controller confirmed nhưng team sai/unknown |0,633|0,067|
| Team đúng nhưng player sai/unknown |1,800|2,667|

Strict correct vẫn0s. Các nhóm mô tả bằng chứng runtime đối chiếu controlGT; observedball không bảo đảm ball đúng vị trí trên mọiframe. Có [trace từng interval và endpoint5GT passes](../../codebase/outputs/task07b-ownership-20261106/trace-team-conflict-reset/trace.json). Không gán tất cả5pass misses choOCR khi ball/control chưa đủ evidence.

## Baseline, kiểm thử và giới hạn

- Baseline phiên này đãfreeze trước sửa. So với artifactv3 lịch sử: bbox/IDs cùng nguồn nhưng129/14007observation khác ở role/team fields; source snapshot trước bước này đã có color quality gate. Dùng pairedbaseline hiện tại để đánh giá, không giả vờ historical output tái lập bit-for-bit.
- Tắt tất cả options mới trên code cuối tái lập **14007/14007observations** ở frame/time/track/bbox/sample_type/role/team/player: [equivalence](../../codebase/outputs/task07b-ownership-20261106/disabled-final-equivalence.json).
- **290tests PASS**: [log](../../codebase/outputs/task07b-ownership-20261106/tests-final.log).12tests mới bao gồm ownership/duplicates, crossing, hold/reset/recovery, predicted/no-source/color rejection, HUD valid-mask, side clipping, causal invalidation và opposing-team same-number. Không đổi Hungarian tracker, không thêm model/pose/ReID weights.
- Dataset/GT/roster và reviewJSON giữ nguyên; không dùng whitelist sampleIDs hoặc nhãn người dùng trong runtime. Tất cả trials là cùng trận, đãexposure; N/A cho temporal identity accuracy và ID-switch count vì chưa có đủ trajectoryGT.

## Tái chạy và bàn giao

Template commands từ workspace root, dùng outputdir mới:

```powershell
codebase/.venv/Scripts/python.exe codebase/scripts/track_players.py --detections codebase/outputs/task07-vietnam-tonga-segments-20261104/development-tiled/detections.jsonl --run-json codebase/outputs/task07-vietnam-tonga-segments-20261104/development-tiled/run.json --roster-config codebase/configs/rosters/vietnam_tonga.json --video codebase/outputs/task07-vietnam-tonga-segments-20261104/media/vt_development.mp4 --enable-ocr --ocr-upscale 3 --jersey-evidence-ttl-s 6 --color-method masked --jersey-evidence-cache codebase/outputs/task07-vietnam-tonga-segments-20261104/development-tracking-v2 --tracking-policy codebase/outputs/task07-vietnam-tonga-segments-20261104/vt_development-policy-ball-roi-v4.json --team-crop-region jersey --reset-on-team-conflict --output-dir codebase/outputs/task07b-new-candidate
```

Rollback: bỏ `--team-crop-region jersey --reset-on-team-conflict`; defaultlegacy giữ nguyên. Fullguard chỉ dùng opt-in `--identity-crop-policy`, không kết hợp với flagteam-region riêng.

[Handoff](../handoffs/task07b-crop-ownership-20261106.md) ghi artifacts, candidate và blocker. Bước triển khai/test/report này đã hoàn tất; quality gates07B/07C vàTask07 chưa DONE. Không cần người dùng review lại batch để tiếp tục. Việc tiếp theo là tách role dùng choball khỏi uncertainty củajersey/identity, cải thiện human/ball detector và chuẩn bị phương án dữ liệu/checkpoint trước một phép thửfine-tune được duyệt riêng.
