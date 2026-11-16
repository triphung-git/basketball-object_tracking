# Handoff Task07 → Task08 /09 /10

2026-11-04. **Code/fixtures và diagnostic integration đã bàn giao; Task07 IN_PROGRESS, chưa nghiệm thu độ chính xác thật.** Đọc [report](../reports/task07-ball-possession.md), [contracts](../specs/ball-possession-v2.md) và [quyết định exposure](../decisions/20261104-clip04-development-exposure.md).

## Artifacts để sử dụng

Trong `codebase/outputs/acceptance-20261104-task07/`:
- `clip04-detection-verified/`: source detections + run,447frames.
- `clip04-tracking/`: observations, event-time identity mappings, team/jersey evidence, metadata. Roster demo; không phải danh tính thật đã kiểm chứng.
- `clip04-ball-possession-final/`: ball_tracks.jsonl, ball_control.jsonl, passes.jsonl, possessions.jsonl, transitions.jsonl, debug.mp4, timeline.png, summary/run.json.
- `synthetic-fixture/`, `synthetic-evaluation/`: fixture có completed pass và evaluator evidence, phải giữ nhãn synthetic.
- `tests-final.json/log`, `independent-audit.json`, `before.json`: nghiệm thu kỹ thuật và hashes.

## Cách consumer dùng dữ liệu

1. Dùng source timestamps/camera/segment và namespace đầy đủ. Track ID không phải player ID. Predicted ball không đủ để xác nhận event.
2. Controller đã confirmed ở mức track vẫn có thể thiếu player_id. Consumer phải giữ nullable attribution và unresolved reason.
3. Actor snapshot của pass/transition là event-time evidence. Không lấy roster hoặc mapping cuối video để gán ngược người chuyền/người ném.
4. Completed pass cần observed flight và stable same-team receiver. Handoff, bounce, deflection và shot có mức candidate riêng; không coi tất cả candidates là sự kiện đã xác nhận hoặc assist.
5. Pass có shot_suspected/contested/gap không được tự thăng thành completed. Task08/09 sau này phải cung cấp shot/outcome/reset context qua adapter có version; chưa có dependency vòng hoặc mutation ngược vào raw logs.
6. Possession output là operational observed control segments. Không dùng số đoạn làm số possession/turnover chính thức; 6 segments trong clip04 chủ yếu phản ánh fragmentation.
7. Input/config đổi tạo revision/run mới. Replay full logs có idempotent IDs theo cùng input bundle; chưa có persisted incremental checkpoint. Không append rerun vào output cũ.

Task08 có thể xây release/shot fixtures từ controller history + ball observations. Task09 cần shot/miss/last-FT context trước khi ghi rebound. Task10 cần pass→shot→score links và rules; không suy assist từ last passer/time window đơn thuần. Các module này chưa được triển khai trong Task07.

## Lệnh từ workspace root

Chọn directory output mới mỗi lần. Cache detection/tracking có thể dùng lại:

```powershell
codebase/.venv/Scripts/python.exe codebase/scripts/track_ball_possession.py --detections codebase/outputs/acceptance-20261104-task07/clip04-detection-verified/detections.jsonl --run-json codebase/outputs/acceptance-20261104-task07/clip04-detection-verified/run.json --tracks codebase/outputs/acceptance-20261104-task07/clip04-tracking/tracked_observations.jsonl --tracking-run codebase/outputs/acceptance-20261104-task07/clip04-tracking/run.json --identity-mappings codebase/outputs/acceptance-20261104-task07/clip04-tracking/identity_mappings.json --config codebase/configs/ball-possession.json --development-authorization codebase/configs/development_authorizations/task07-clip04.json --video codebase/assets_test/2aOboR9Z2NjQ1XP8HgYdKMG7VVzS44zOdTVVjB5s.mp4 --diagnostic --output-dir codebase/outputs/task07-next-run
```

Omit `--video` khi chỉ cần logs/timeline; core dùng cache và không load detector/OCR. Optional video là một input fingerprint nên namespace có thể khác bundle có video. Input diagnostic không được gọi là production benchmark.

Tái tạo tracking/OCR khi có thay đổi liên quan:

```powershell
codebase/.venv/Scripts/python.exe codebase/scripts/track_players.py --detections codebase/outputs/acceptance-20261104-task07/clip04-detection-verified/detections.jsonl --run-json codebase/outputs/acceptance-20261104-task07/clip04-detection-verified/run.json --roster-config codebase/configs/rosters/demo_clip04_3x3.json --video codebase/assets_test/2aOboR9Z2NjQ1XP8HgYdKMG7VVzS44zOdTVVjB5s.mp4 --allow-uncalibrated --enable-ocr --ocr-provider easyocr --ocr-weights-dir codebase/.model-cache/easyocr --ocr-sampling-cadence 15 --development-authorization codebase/configs/development_authorizations/task07-clip04.json --output-dir codebase/outputs/task07-next-tracking
```

Chỉ chạy lại detector khi cần cache mới:

```powershell
codebase/.venv/Scripts/python.exe codebase/src/basketball_scoreboard/app.py --video codebase/assets_test/2aOboR9Z2NjQ1XP8HgYdKMG7VVzS44zOdTVVjB5s.mp4 --development-authorization codebase/configs/development_authorizations/task07-clip04.json --no-video-export --output-dir codebase/outputs/task07-next-detection
```

Kiểm thử:

```powershell
codebase/.venv/Scripts/python.exe -m unittest discover -s codebase/tests -v
```

Windows sandbox có thể chặn temporary cleanup; không sửa tests để bỏ assertions. Runner lưu log của lần đã nghiệm thu là `outputs/acceptance-20261104-task07/run_tests.py`; tránh chạy đè evidence lịch sử khi tái nghiệm thu, dùng log/output mới.

Evaluator độc lập trên fixture (không phải clip04 GT):

```powershell
codebase/.venv/Scripts/python.exe codebase/scripts/evaluate_ball_possession.py --run-dir codebase/outputs/acceptance-20261104-task07/synthetic-fixture --ground-truth codebase/outputs/acceptance-20261104-task07/synthetic-fixture/ground-truth-synthetic.json --diagnostic --output-dir codebase/outputs/task07-next-fixture-evaluation
```

## Điều kiện còn thiếu

207 tests PASS; clip04 debug447frames, PTS sai số0;112observed ball frames;19confirmed-control frames nhưng0 có player identity;0completed pass. Đây không phải khả năng control/PRA đủ dùng trong trận thật. Cần reviewed GT/protocol và cải thiện ball/identity coverage trước data acceptance. Nhóm clip04–07 đã exposure; chọn nhóm mới cho đánh giá độc lập sau này. Giữ trạng thái G04/05/06 và Task07 data acceptance đúng thực tế.
