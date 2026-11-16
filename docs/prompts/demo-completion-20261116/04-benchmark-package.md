# D09–D10 — Đo hiệu năng thật và đóng gói demo thử nghiệm

Thực thi theo [prompt tổng](00-master-execution.md) và [Plan](../../../PLAN-DEMO-20261116.md). Đây là packaging bản dùng thử cho review, không mở lại 06B nghiệm thu chính thức khi 06A chưa đạt. Không đợi approval quality để hoàn thiện tooling/UI/bundle trong quyền hiện có.

## D09 — Benchmark production, job dài và phục hồi

1. Audit benchmark hiện tại: bỏ fallback times `[2570,2520,...]`, `stage_state.get(...,1.8/7.9/...)` hoặc số giả tương tự. Stage không đo được phải unavailable/N/A có reason, exception phải failed/partial; không output fabricated success.
2. Instrument actual production boundaries: decode→preprocess/detect→tracking→crop/OCR/identity→ball/control/pass→shot/PRA→ledger→heatmap/render/export. Record per-frame/stage times và warmup/cold-start/total wall scope, sample counts; không tự lấy inference reciprocal làm application FPS.
3. Full inference fresh vs validated cached-observation replay báo riêng; cached replay không phải model inference. Profiles CPU/GPU/config/model khác nhau phải versioned riêng. Mapping class từ runtime, adapters/input không rỗng giả hoặc sai contract.
4. Báo source FPS/processed/dropped/coverage, p50/p95, RAM/VRAM/queue/backlog, processing latency và occurrence→confirmation delay. Event chưa có thì delay N/A, không 0 giả. Không lấy synthetic event generator làm real confirmation measurement.
5. Kiểm metadata/hashes/counts/progress/terminal state của long run đang có; nếu reuse output thì source profile/coverage phải đúng. Heartbeat freshness và PID command identity, không chỉ process name. Job interruption có checkpoint/resume hoặc partial restart policy rõ, không duplicate physical events hoặc overwrite cũ.
6. Offline là target demo. Không tự thêm real-time requirement hoặc cam kết >30FPS. Nếu có optimization/candidate trong scope, paired quality regression cùng source/protocol trước chọn; đừng skip critical frames để che tốc độ.
7. Live claim chỉ khi separate gate thực đã đo theo existing Task14; không bật claim vì video playback mượt. Nếu source/góc camera ngoài hỗ trợ, đưa coverage/limitations đúng scope.

Tests: actual timing aggregation/N/A/error propagation, frame/coverage accounting, monotonic PTS/confirmation timestamps, cancellation/checkpoint/replay/no-overwrite. Loại sự phụ thuộc của tests vào FPS cũ hoặc fabricated artifact; thay bằng independent expected counts/measured-source validity, không đổi assertions chỉ để che lỗi thật. Full suite sau production changes.

Real benchmark bằng public production runner/selected profile trên declared continuous development scope đủ sample; lưu raw timing records và independent wall-time/frame-count cross-check. Nếu full-match job còn chạy, không restart chỉ để có benchmark nhanh; hoàn thành đoạn nhỏ đo được và report pending long-job phase trung thực.

**D09 PASS:** actual measurements có logs/profile/hash/coverage, N/A/failed paths đúng và tests/integration PASS. FPS thấp không phải lý do fail demo offline; thiếu số đo không được điền constants. Quality acceptance vẫn riêng; report/handoff đủ trước D10.

## D10 — Demo bundle và launcher một lệnh

1. Tạo entrypoint/script local đơn giản cho: chọn preset/input+roster/court/rules, preflight, phân tích video hoặc mở existing verified run với nhãn mode rõ, mở dashboard và tìm exports. Paths có spaces/OneDrive phải xử lý đúng; không cần người dùng sửa Python source.
2. Default preset dùng declared footage/config trong scope đã có quyền. Không tự chuyển sang replay selected windows khi fresh-analysis fail; không ghép calibration/roster/source khác để output có vẻ đủ.
3. Bundle đủ source/config/version snapshots, input references/media có quyền, annotated MP4, heatmap PNG+raw grid, trajectories/ball/control/pass logs, auto/raw events, audit/checkpoint/corrections riêng, auto boxscore, metrics/error/benchmark và evidence links. Tên file/counters/profiles phải nhất quán.
4. User guide tiếng Việt: requirements/setup/interpreter/weights/auth/offline caveats; exact launch commands/cwd/port, input constraints, cách cấu hình trước phiên, xem event/uncertainty/evidence, export, stop/cancel/resume và troubleshooting có thể kiểm. Không in key/signed URLs hoặc giả hỗ trợ fully-offline nếu vẫn cần metadata/auth download.
5. Release notes nêu experimental status, tested scenarios, feature/quality matrix, actual unknown/missed/false/coverage, hardware/runtime và known issues. Đừng gọi manual corrections là auto accuracy hoặc quality FAIL là full acceptance.
6. Artifact manifest ghi required/actual/hash/size/version và linkage. Paths/URLs/local links phải mở được trong workspace/reproduction context; không đóng gói cache secrets hay media không có quyền chia sẻ. Không publish/upload/commit/push tự động.
7. Nếu cần dependency/backend/paid resource mới, chuẩn bị concrete R06 proposal và continue fallback hiện có; không dừng toàn packaging vì một optional optimization pending. Không gọi optional dependency missing là tất cả runtime unusable nếu baseline còn chạy.

Tests: launcher success/invalid inputs/port conflict/path-with-spaces/output exists/missing model/readiness/failed stage và manifest completeness/schema/hash. Chạy launcher thật với video+configs, parse exports, mở dashboard/overlay; không chỉ `--help`.

**D10 PASS kỹ thuật:** bundle+launcher+guide thực có, chạy được và logs/checks pass. Nếu source artifacts đủ luồng nhưng chất lượng còn sai, label experimental và đưa D11 đo/đánh giá; không tự verdict READY trước QA. Nếu thiếu PRA/heatmap/overlay thật, bundle PARTIAL phải nêu missing và quay lại task upstream có thể sửa, không che thiếu bằng placeholder.
