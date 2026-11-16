# D01–D03 — Nền chạy, nhận dạng cầu thủ và heatmap thật

Thực thi trong phạm vi [prompt tổng](00-master-execution.md) và [Plan mới](../../../PLAN-DEMO-20261116.md). Không dừng sau nhóm nếu còn task sẵn sàng. Gate sau từng task/phase có tests/run/report/handoff; thiếu approval chỉ chặn phase phụ thuộc.

## D01 — Runtime, state, public entrypoints và job inventory

1. Đọc handoffs/source thay vì xây lại baseline. Inventory interpreter/packages/weights/data/config/CLI hiện có; không đọc `.env` ra tool outputs.
2. Xác minh worker/PID/heartbeat/log/source-snapshot của run 0–1000s đang có. Nếu khỏe, reuse terminal outputs sau khi hoàn tất và tiếp tục việc độc lập; không launch duplicate. Thay source trong khi job chạy phải cô lập snapshot/copy hoặc xác minh files đã load, không âm thầm đổi experiment giữa chừng.
3. Backup legacy state malformed và tái dựng status từ checkpoints + artifacts thật, validate JSON/schema/hash refs. Tạo state run mới, không sửa historical checkpoints để làm đẹp status.
4. Root `run_demo.py` và scripts CLI phải thống nhất video-analysis/diagnostic-cache. Kiểm `--serve` dùng đúng dashboard API, video/roster/run bindings, source timestamps, safe output paths/no-overwrite và failure/cancel/partial states. Không vẫn ghi “unsupported” khi video path đã chạy được.
5. Một run output không completed nếu writer/inference/required stage failed. Existing cache chỉ reuse nếu source/model/config/frame clock hợp lệ; không fallback sang selected windows khi người dùng chọn video khác.
6. Preflight đủ inputs/configs thì mới chạy model; giữ CPU approved default và record profile nếu chạy experimental runtime trong quyền hiện có.

Tests: CLI subprocess valid/invalid source/roster/config/cache/output, JSON state recovery/no status fabrication, serve API compatibility, cancel/partial/fail và no-events. Tests mục tiêu + full suite sau code cuối. Real-run đoạn development đã được phép, một smoke public entrypoint→artifacts→dashboard API; không cần chạy lại toàn 1000s để test CLI.

**D01 PASS:** state parse/recover/reuse được, entrypoints hoạt động, job inventory/commands/hashes/logs và report/handoff đủ; không còn startup/integrity P1 chặn demo. Tiếp tục D02 hoặc phase độc lập khác theo DAG.

## D02 — OCR/team/identity thực trong continuous production path

Điểm vào: `continuous_stream.py`, `continuous_orchestration.py`, `identity.py`, `identity_crops.py`, `ball_actor_context.py`, `track_players.py`, các OCR/crop guards/tests hiện có.

1. Nối local OCR provider + weights được duyệt, sampling/crop quality/ROI/torso-jersey region đúng nguồn. Không chỉ khởi tạo resolver rồi xuất `jersey_evidence=[]`; không dùng GT roster mapping như một OCR reading.
2. Tái dùng cache OCR thật khi source/tracker/observed-bbox/preprocessing binding đúng. Không coi mock/cache khác config là evidence production; fresh/memoized calls phải có status/hash.
3. Team evidence theo crops thật, role player/non-player/unknown đúng contracts; ROI không tự chứng minh player/team. Giữ ball actor-context decoupling để tránh guard OCR làm giảm ball recall.
4. Event-time player identity phải dùng evidence đã tồn tại ở thời điểm event, có TTL/conflict/reset/hysteresis và cuts/gaps; không lấy final whole-track mapping gán ngược về đầu video.
5. Nối jersey/team/identity evidence sang shooter/control/pass consumers và export IDs/mappings/evidence refs. Track ID khác player ID. Team-only events hợp lệ giữ unassigned credits, không pick nearest player hoặc roster member để có số.
6. Expose configs/readiness/errors/unknown rate trong run metadata. Tái dùng quyền local OCR đã có, không hỏi lại tải weights nếu files hợp lệ.

Tests: crop binding/cross-source/mock rejection, TTL/time ordering, duplicate/conflicting jersey, non-player/occlusion/cut resets, actor-context ball regression, mapping-at-time qua seek/reload; full suite.

Real-run cùng development scope với approved roster/weights, export raw OCR/crop evidence và event-time mappings. Hand-check mẫu readable/unknown/conflict; báo exact-match/coverage nếu có reviewed GT, không dùng “readable count” như OCR accuracy. So baseline cùng frames để phát hiện regression.

**D02 PASS:** production stream thực sự gọi provider hoặc validated real cache, evidence thật tới consumers, tests/API/outputs PASS; unresolved vẫn đúng. Nếu OCR hoàn toàn không đọc được vì footage, ghi limitation và xử lý bằng configs/data trong scope; không gọi identity demo hoàn thiện chỉ vì exports không lỗi. Candidate/new weights ngoài scope → R05/R06 với evidence; tiếp tục các phase không phụ thuộc candidate mới.

## D03 — Calibration, source/camera policy và heatmap accumulation thật

Điểm vào: court configs dưới cả `configs/court` và `configs/courts`, `court.py`, `heatmap.py`, `spatial_io.py`, `generate_heatmap.py`, `continuous_orchestration.py` và court guide/specs.

1. Audit đúng schema/origin/axes/units của calibration đã được duyệt; đừng coi hai JSON cùng tên gần giống là interchangeable. Bind source hash, original dimensions, segment/camera/time validity. Không lấy calibration clip 300–330s áp ngầm cho full broadcast có pan/zoom/cuts.
2. Reuse approved geometry đúng scope, tính projection từ observed feet/footpoint và event-time team/identity. Thiếu geometry mới: phase proposal có frame/landmarks/check points/overlay/residual/foot GT → R02; chưa duyệt thì phần mới diagnostic/unavailable, không giả verified-meters.
3. Nối real time-weighted accumulator vào continuous output. Bỏ đường “generated” nhưng `total_player_seconds=0.0` cố định; grid/intervals/team/unknown/region stats phải từ observations thật. Không chỉ đếm `recent_player_obs` hoặc vẽ shot markers rồi gọi heatmap.
4. Observed valid endpoints, role/gap/cut rules, source PTS và identity namespace theo existing contracts; predicted/invalid không filter mất rồi nối qua. Không extrapolate cuối run hoặc clamp mọi projected point vào sân để tăng mass.
5. Export trajectories, raw grid, heatmap summary/PNG, region stats và evidence/config hashes. Recompute/reload cùng raw inputs phải giữ mass/identity policy; unavailable có reason/coverage và không xuất PNG giả.

Tests: homography/source/units mismatch, collinear/degenerate landmarks, independent check error, interval union/cuts/gaps, observed-vs-predicted, unknown/player-role mass, region/team/grid conservation, replay/recompute; full suite sau shared-code changes.

Real-run trên đoạn có geometry đã approved; kiểm independent integration player-seconds so grid/team totals và ảnh PNG/overlay. Fit residual nhỏ không thay external position accuracy. Phase geometry mới chưa approved giữ WAITING_REVIEW nhưng verified heatmap trên scope cũ phải chạy được nếu đủ evidence.

**D03 PASS:** đủ calibrated run + real grid/PNG/trajectories và tests/mass/source checks; không còn fabricated occupancy. Nếu chỉ xong proposal thì phase preparation PASS, toàn task pending và demo heatmap gate chưa PASS. Update R02 cụ thể rồi tự tiếp tục các task độc lập.
