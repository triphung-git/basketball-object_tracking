# Prompt 02 — Continuous upstream stream → PRA và output bundle

Thực thi **02A → 02B**. Đọc [execution-contract.md](execution-contract.md), kiểm checkpoint/handoff đợt 01 trước khi sửa. Không có predecessor PASS thì xác minh/khắc phục dependency, không tự ghi PASS. Không mở đợt 03 trong lượt này.

Đọc `app.py`, `video.py`, `detector.py`, `players.py`, `identity.py`, `ball.py`, `possession.py`, `ball_pipeline.py`, `spatial_io.py`, court/heatmap modules và CLI `track_players.py`, `track_ball_possession.py`, `generate_heatmap.py`. Tái dùng APIs/contracts hiện có thay vì nhân bản pipeline hoặc gọi unit-test fixtures làm production input.

## 02A — Luồng MP4 thật qua detection/tracking/identity/control

1. Xây entrypoint nhận MP4/config/roster/court/rules và xuất source-bound frame stream. Có thể incremental hoặc stage orchestration trên toàn stream; không giới hạn vào reviewed windows chọn trước. Mọi frame/cut/coverage/skip phải có policy rõ.
2. Decode bằng reader PTS hiện có, giữ normalized source_time_s/raw PTS/timebase và original dimensions. Không thay PTS bằng frame_index/30 hoặc wall clock, kể cả VFR.
3. Gọi approved detector thật; giữ bbox mapping/frame origin, human/ball/rim class mapping từ runtime. Event-free frames vẫn có record. Propagate lỗi model/decoder/writer, không sinh empty success giả.
4. Kết nối player tracking → team/OCR/identity theo event time → ball/control/pass/operational possession. OCR chỉ dùng provider/weights đã duyệt và crops có evidence. Unknown/predicted là trạng thái thực, roster không tự tạo identity evidence.
5. Bind video/model/preprocessing/config/roster/court/cuts và source hashes giữa stages; không trộn cache khác source. Cache là optimization có validation, không thay selected video ngầm.
6. Geometry reviewed và nguồn phù hợp mới được dùng production. Thiếu geometry thì mode diagnostic/uncalibrated tường minh, không tạo vị trí sân hoặc point value giả. Nếu thiếu calibration mới, hoàn thành nhánh diagnostic và report limitation của task kỹ thuật này; không tuyên bố geometry quality PASS.

Tests bắt buộc: adapter contracts/mapping, CFR/VFR PTS, cuts/gaps, empty detections, source/cache mismatch, unknown identity, failed stage. Chạy tests mục tiêu và full suite.

Real-run bắt buộc: một đoạn continuous development hai đội đã được phép, khai báo start/end trước khi xem kết quả, không cherry-pick theo GT. Export `run.json`, `detections.jsonl`, tracked observations, identity evidence/mappings, ball tracks/control/passes và stage counts. Input/clip chính xác lấy từ authorization/handoff, không inference holdout để chọn tham số. Khởi đầu bằng đoạn giới hạn có declared coverage; đây là technical partial-video smoke, chưa phải toàn trận hay quality test.

**Gate 02A:** input video thật đã decode/infer, downstream nhận stream có binding/PTS, counts/observed/unknown đúng, lỗi được phản ánh, tests pass và run bundle/report/handoff hoàn chỉnh. Chỉ sau đó mở 02B.

## 02B — Event orchestration → ledger/heatmap/export

1. Feed stream 02A vào shot/points, rebound và assist engines thực. Chứng minh REB/AST APIs được gọi và nhận đúng contract; không chỉ khởi tạo object. Eligibility/FT/action evidence thiếu thì unresolved, không dùng window names/GT làm hints.
2. Bảo toàn causal ordering: shot release/outcome → eligible miss/control hoặc eligible score/pass chain → event ledger. Phân biệt event occurrence và confirmation times; cuối stream flush không tự xác nhận evidence thiếu.
3. Ingest events bằng physical IDs, eligibility và lifecycle Task11. Kiểm raw log replay/checkpoint/duplicate/parent void và score conservation; corrected log tách raw auto.
4. Nối court/heatmap từ observed, identity-at-time và geometry hợp lệ. Giữ unknown occupancy/diagnostic riêng; không tạo nhiệt giả nếu chưa calibrated. Output unavailable có reason và không che gate geometry.
5. Output bundle tối thiểu: `run.json`, detections/tracks/control/passes, `shots_auto.jsonl`, `events_auto.jsonl`, `events_raw.jsonl`, audit/checkpoint, `boxscore_auto.csv`, coverage/timings và artifact manifest; heatmap/overlay theo config với status rõ. File rỗng hợp lệ phải có schema/count/reason.
6. CLI default video path phải đi qua pipeline mới; cache replay là mode riêng. Required stages fail → run failed; declared max-frames/range → partial theo policy; không overwrite artifacts cũ. Hủy/interruption phải giữ status/partial evidence đúng.

Tests bắt buộc: stream-to-PRA orchestration, positive PTS/REB/AST bằng synthetic diagnostic tách biệt, no-event/unknown, cuts, duplicate/replay, incomplete stream và writer failure; tests đợt 01 và full suite sau thay đổi cuối.

Real-run: chạy cùng đoạn video 02A bằng root entrypoint qua toàn pipeline, xuất thư mục mới. Đối soát source frame counts/PTS; event evidence refs thật; boxscore từ ledger; checkpoint/raw replay tái lập totals; giải thích zero/unresolved thay vì thêm events tay. Synthetic chứng minh plumbing không thay real-video outputs hoặc recognition metrics.

**Gate 02B:** production video path thực sự gọi đủ engines, đủ bundle, tests và đối soát outputs PASS; technical limitations được ghi rõ. Không cần giả đạt P/R để qua task integration; chưa được tuyên bố toàn MVP DONE. Bàn giao exact CLI/configs/schema/evidence cho evaluator đợt 03.
