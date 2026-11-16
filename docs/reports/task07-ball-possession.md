# Task07 — triển khai, kiểm thử và demo 3x3

2026-11-04. **Implementation/fixtures PASS; clip04 diagnostic integration PASS; Task07 IN_PROGRESS vì chưa đủ điều kiện nghiệm thu hành vi trên trận thật.**

Đã triển khai ball tracking, temporal control/pass/operational possession, CLI, evaluator riêng và debug exports. Đã chạy clip giải 3x3 thật với roster giả lập theo yêu cầu. Không biến fixture metrics hoặc số lượng output thành accuracy thực.

## Phạm vi code

- [ball.py](../../codebase/src/basketball_scoreboard/ball.py): confidence/kinematics association, ambiguity, bounded prediction, stale/reset.
- [possession.py](../../codebase/src/basketball_scoreboard/possession.py): multiframe control, dribble provisional, contested/free/loose, flight/pass, shot/handoff candidates, causal actor snapshots.
- [ball_pipeline.py](../../codebase/src/basketball_scoreboard/ball_pipeline.py): validation, replay, JSONL/timeline/debug MP4.
- [track_ball_possession.py](../../codebase/scripts/track_ball_possession.py), [config](../../codebase/configs/ball-possession.json).
- [possession_evaluation.py](../../codebase/src/basketball_scoreboard/possession_evaluation.py), [evaluator CLI](../../codebase/scripts/evaluate_ball_possession.py): GT riêng, matching một-một, unknown trong mẫu số.
- Tests: [logic/evaluator](../../codebase/tests/test_task07_ball_possession.py), [CLI/authorization](../../codebase/tests/test_task07_pipeline.py).

Thay đổi nhỏ upstream: app, spatial_io và track_players nhận authorization path tường minh để cho phép đúng source SHA clip04 theo [quyết định người dùng](../decisions/20261104-clip04-development-exposure.md). Mặc định vẫn chặn holdout; clip05–07 không được mở bởi authorization này. Dataset/nhãn/splits v1/v2 không bị sửa.

## Input thật và setup demo

Clip04: `assets_test/2aOboR9Z2NjQ1XP8HgYdKMG7VVzS44zOdTVVjB5s.mp4`, SHA-256 `ae789418b89cfcf868a546eb0a5ce502497bb6d2b61af252978038d7cf8af3c4`, 1038×480, 447 frames, khoảng17.65s.

Detector giữ đúng `phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1`, ONNX CPU, confidence0.25/max_edge1280. Model metadata được truy cập theo quyền đã có, inference chạy local. Lần sandbox đầu lỗi RetryError; lần được phép truy cập metadata hoàn thành. Không upload media hoặc inference cloud.

Roster [demo_clip04_3x3.json](../../codebase/configs/rosters/demo_clip04_3x3.json) có hai đội DEMO Blue/White, 6 placeholder players, màu áo gần đúng. Names/IDs/jersey membership chưa được xác minh; không phải official roster hay GT. Không dùng các notes chứa kết quả pha bóng để recognition. Nhóm clip04–07 đã exposure cho development, không còn là holdout độc lập chưa tiếp xúc trong đánh giá mới.

Không dùng synthetic court geometry. Vì chưa có ROI/role benchmark thật, tracking có cả người ngoài trận ở nền; team/role output là heuristic diagnostic. Camera trong clip có chuyển động; chưa có automatic camera-motion handling. Không xuất heatmap metric hoặc giá trị cú ném từ geometry giả.

## Kết quả chạy cuối

Root artifacts: `codebase/outputs/acceptance-20261104-task07/`.

| Stage / chỉ số | Kết quả |
|---|---:|
| Detection input/output frames | 447 |
| Frames có ít nhất một ball detection | 124 /447 |
| Detector pipeline FPS | 9.46, CPU, không export video ở stage này |
| Player tracking observations | 5823: 3978 observed, 1845 predicted |
| Local EasyOCR evidence records | 11 |
| Task07 ball samples | 112 observed, 92 predicted, 243 missing |
| Control states | 347 unknown, 14 contested, 38 control_candidate, 19 controlled, 29 loose |
| Confirmed control frames có player_id | 0 |
| Operational possession segments | 6, bị phân mảnh; không phải 6 lượt possession chính thức |
| Completed passes trên clip thật | 0; không kết luận video không có đường chuyền |
| Debug MP4 | 447 frames, 960×442, PTS error tối đa0s |
| Replay | PASS, cùng input bundle cho cùng IDs/JSONL |

OCR đọc các candidates số19 (7 lần),12 (2),4 và1 (mỗi số1 lần); một số mappings đạt consensus với roster demo. Những con số này không phải OCR accuracy và không cung cấp actor hợp lệ ở các frame control được xác nhận. Không gọi trạng thái `resolved_with_consensus` của tracking là danh tính thật đã được nghiệm thu.

Output cuối: [summary](../../codebase/outputs/acceptance-20261104-task07/clip04-ball-possession-final/summary.json), [video debug](../../codebase/outputs/acceptance-20261104-task07/clip04-ball-possession-final/debug.mp4), [timeline](../../codebase/outputs/acceptance-20261104-task07/clip04-ball-possession-final/timeline.png). Contact sheet đã kiểm tra trực quan tại `debug-contact-sheet.jpg`.

Core logic trên cache mất ~0.0091s; toàn Task07 CLI có replay/export mất ~4.52s. Hai số này không gồm detector và OCR, không chứng minh end-to-end real-time.

## Kiểm thử và audit

- Baseline trước thay đổi: 160 tests PASS,13.602s. Chạy trong sandbox ban đầu lỗi quyền Windows ở tempfile; chạy được phép ngoài sandbox pass. PowerShell redirect stderr của unittest tạo exit status không phản ánh kết quả, nên lần cuối dùng Python runner lưu UTF-8 log và exit theo TestResult.
- Cuối: **207 tests PASS,0 fail/error/skip**,16.846s; gồm160 baseline và47 tests mới. [Kết quả](../../codebase/outputs/acceptance-20261104-task07/tests-final.json), `tests-final.log` và `run_tests.py` cùng directory.
- Các ca: ambiguity, dribble, bounce, handoff candidate, opponent/contested transfer, shot suspicion, same-player track switch, predicted/missing, VFR/cut/gap, role/team expiry, causal identity, replay, no-overwrite, missing humans, invalid provenance, failed writer, authorization scope và evaluator denominators/matching.
- [Independent artifact audit](../../codebase/outputs/acceptance-20261104-task07/independent-audit.json) đối chiếu observed ball với detection gốc, actors với observation cùng thời điểm, clock/frame count, code hashes và decode MP4. Không gọi lại engine để suy kết quả kiểm chứng. 19 dataset files trong snapshot giữ nguyên hash.

Fixture evaluator riêng:1 completed pass, strict/event-only TP1/FP0/FN0; observed ball10/10; control accuracy1/3 do confirmation latency và unknown được tính vào mẫu số. Đây là **synthetic fixture**, không phải metrics clip04. [Fixture evaluation](../../codebase/outputs/acceptance-20261104-task07/synthetic-evaluation/evaluation.json).

## Lỗi còn thấy và điều kiện DONE

Detector chỉ có ball candidate trên khoảng27.7% frames; tracker giữ observed trên khoảng25.1%. Đây là coverage quan sát, không phải recall vì chưa có GT bóng. Có các quãng dài missing, detection nhầm đồ họa truyền hình và bóng bị che khuất. Bbox interaction còn mơ hồ khi người gần nhau; ROI/role/team/identity chưa được benchmark. Bộ quy tắc bảo thủ ngắt control ở gaps, nên không có chuỗi flight/control đủ dài để xác nhận pass trong lần chạy này.

Handoff/deflection/shot mới là candidates khi thiếu hand/intent/context evidence. Công cụ đã hoạt động nhưng chưa chứng minh đủ chất lượng actor/control để nhận PRA trên trận này. Không hạ các điều kiện chỉ để tạo pass giả.

Để đóng Task07: cần reviewed ball/control/pass GT trên footage đã chọn hoặc footage phù hợp hơn, protocol/ngưỡng task07 được chốt trước đo, và cải thiện quan sát bóng/identity đủ để pass các trường hợp thật. Có thể nghiên cứu crop/resolution/ROI và dữ liệu bổ sung theo lỗi đã thấy; đổi model/stack lớn cần quyết định riêng. Các file GT v2 hiện vẫn trống. Roster giả lập không thay GT.

Task08 có thể tiếp nhận contracts và fixtures để phát triển phần độc lập. Nghiệm thu scorer/rebound/assist trên trận thật còn phụ thuộc chất lượng và dữ liệu chưa đạt ở trên. Task05/06/G04 không được tự chuyển DONE.

Lệnh tái chạy và semantics nằm ở [handoff](../handoffs/task07-to-task08-09-10.md) và [spec](../specs/ball-possession-v2.md). Các output lần chạy trước được giữ nguyên; `clip04-ball-possession-final` là run cần dùng, không phải directory trung gian.
