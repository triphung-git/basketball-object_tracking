# Prompt 05 — Dashboard/evidence thật → Benchmark production E2E

Thực thi **05A → 05B**, đọc [execution-contract.md](execution-contract.md), kiểm selected-profile measurement/handoff đợt 04. Không tự triển khai đợt 06. Nếu quality chưa đạt, UI/report phải thể hiện diagnostic/IN_PROGRESS; không chỉnh dữ liệu hoặc bỏ unknown để làm demo đẹp.

## 05A — Dashboard, heatmap, evidence và trạng thái run

Điểm vào: `dashboard.py`, `scripts/run_dashboard.py`, runner/output schemas đợt 02, `court.py`, `heatmap.py`, Task05/12.

1. UI đọc đúng run bundle/source video/roster/versions; hiển thị auto_confirmed/provisional/unresolved/void và coverage/unknown đúng nghĩa. REB/AST chưa đo được không hiển thị như số 0 đã được xác minh.
2. Bỏ `frame_index % 7`, khoảng cách mặc định 5,5m và vị trí minh họa. Shot map dùng coordinates có evidence và source-matched geometry. Heatmap dùng observed occupancy + event-time identity; không có geometry thì báo unavailable, không vẽ dữ liệu giả.
3. Event list/timeline link đến occurrence/confirmation time và evidence thực; video seek/PTS offsets đúng. Parent pass/shot/control và provenance truy cập được; revisions/void không làm UI totals khác ledger.
4. Load/progress/cancel/failed/partial/completed lấy từ run state; không luôn báo thành công. HTTP video range hợp lệ và invalid ranges đúng; file thiếu không treo hoặc giả playable. Không cần cloud/backend/database mới.
5. Export đúng raw auto events/boxscore/metrics/heatmap hiện có; không trộn corrected output; nội dung user-provided hiển thị an toàn, không inject HTML từ tên đội/cầu thủ.

Tests: API/export/status/serialization, unknown/zero phân biệt, coordinates/geometry binding, missing media, range errors, rendering data input; full suite sau sửa production. Chạy dashboard với bundle video thật và bộ synthetic UI riêng cho states/edge cases.

Browser QA bắt buộc với công cụ automation hiện có: desktop/mobile, playback/seek, timeline→evidence, PTS alignment, exports mở/parse được, missing-video, failed/partial/unresolved states, long names và layout. Lưu screenshots và machine-readable results; đọc skill browser/UI áp dụng trước khi dùng. Nếu không có công cụ browser, báo limitation và task pending, không tự ghi browser PASS bằng unit tests.

**Gate 05A:** không còn tọa độ giả, totals/status đúng run/ledger, tests/browser checks PASS và đủ screenshots/exports/report/handoff. Geometry/visibility thật không đủ thì trạng thái unavailable phải có lý do; không đồng nghĩa chấp nhận heatmap accuracy của MVP. Chỉ sau đó mở 05B.

## 05B — Benchmark đúng production pipeline

Điểm vào: `scripts/benchmark_task14_performance.py`, production runner/config của đợt 02/04, Task14.

1. Sửa mapping từ model metadata; không dùng 0=player/1=rim/2=ball. Gọi cùng adapters/stream/APIs như production; có kiểm tra stage thực nhận data đúng, không benchmark empty tracker hoặc FSM contract sai.
2. Đo decode→detect→tracking→team/OCR/identity→control/pass→PTS/REB/AST→ledger→heatmap/render/export. Stage disabled/unavailable khai rõ; không coi tổng vài microbench là E2E.
3. Ghi source FPS, processed/dropped frames, coverage, warmup/cold-start, wall processing time, p50/p95 per-stage latency, event confirmation delay/source look-ahead, RAM/VRAM/backlog và run configuration. No-event case confirmation delay N/A, không gán 0 giả.
4. Đo trên đúng hardware/interpreter/selected profile. Nếu profile ONNX CPU và CUDA diagnostic khác nhau, báo riêng; không lấy tốc độ CUDA để đại diện default CPU.
5. Không tự tối ưu bằng skip-frame/thay input/model. Nếu thử optimization có quyền, freeze variant và chạy quality regression paired trước chọn. Không gọi live-ready nếu chưa có nguồn/run đáp ứng gate Task14; MVP offline được báo offline.
6. Kiểm cancel/interrupt/error giữ run status đúng và không tăng memory không giới hạn. Live claim chỉ khi có ít nhất 5 phút trên target source, throughput≥source FPS và backlog không tăng, cùng quality evidence; không bắt buộc live để hoàn tất benchmark offline.

Tests: timings/count aggregation và contracts có kiểm chứng; full suite nếu sửa production/shared code. Run benchmark thật bằng production entrypoint trên đoạn development đã khai báo, quan sát đủ để có sample p50/p95 đáng tin và báo sample size. Nếu long-run chưa có, ghi chưa kiểm chứng, không suy từ 100 frames.

Đầu ra: `benchmark.json`, per-stage timing records, hardware/config/model/code hashes, quality-regression comparison nếu có variant, plots/tables khi hữu ích, logs/report/handoff. Đối soát frame counts/wall time độc lập và parse output bundle.

**Gate 05B:** phép đo E2E đúng đường production, mapping/data không sai, tests PASS và artifacts/reproduction command đủ. Không cần realtime PASS để benchmark task PASS; giới hạn offline phải công bố. Chưa được nâng toàn bộ Task14/15 DONE nếu quality gate còn mở. Bàn giao cho đợt 06.
