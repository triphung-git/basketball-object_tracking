# D07–D08 — Đánh giá đúng scope và giao diện demo đầy đủ

Tuân thủ [prompt tổng](00-master-execution.md), [Plan](../../../PLAN-DEMO-20261116.md) và actual protocol decisions. Tự tiếp tục task dependency-ready; không gate toàn chuỗi vào independent test/approval còn thiếu.

## D07 — Evaluator, source timeline/coverage và run mở rộng

1. Dùng shared production evaluator và CLI có tests, không evaluator định nghĩa riêng trong test. Đối chiếu scope/version/requirements của các profiles cũ và basket-primary mới đã được cho phép; không áp ±0,75s toàn bộ shots hoặc hạ attribution thresholds ngầm.
2. Kiểm source SHA, video IDs, clip→parent offsets, occurrence vs confirmation time và processed coverage. Normalization bất biến, không double-count cùng event nếu có cả parent/child annotation. Phân biệt records/made events/unique events. Không so prediction 30s với GT toàn trận hoặc chỉ đổi video_id mà không đổi timeline.
3. Chỉ lấy labels reviewed đúng approval scope. Schema/value/subtype/parent/pass links từ canonical rules/types phải được đọc đúng. Unknown/sparse/uncertain/excluded/background policy rõ; GT thiếu actor không được giả strict TP. Negative review packet chưa duyệt không có official specificity.
4. One-to-one max-cardinality matching/ties/duplicates và strict all-correct cho từng PTS/REB/AST; wrong actor/value/subtype/link là strict FP/FN. Denominator zero N/A có reason. Không đơn thuần “window có made” hoặc ignore missing events để pass.
5. Với long run hiện có: kiểm terminal status và source-snapshot trước reuse; không gọi output cũ của source profile khác là kết quả candidate mới. Gộp original/basket-primary comparisons đúng predictions, store immutable raw outputs + metrics/matches/errors.
6. Khoảng 0–1000s trên video dài 1381s chỉ là expanded prefix. Calibration clip/camera không tự valid cho full broadcast. GT ngoài reviewed coverage là sparse/exposed diagnostic; không suy formal precision hoặc independent 06A từ 14 event labels.
7. Inventory data/provenance/split/exposure/coverage còn thiếu; tạo R03/R04 proposal có cụ thể clips/labels/controls/reserve và giữ historical locks. Không sửa expected hashes để vượt validator; không tự allocation independent holdout từ nguồn đã tune.

Tests: source mismatch, missing/short coverage, zero timestamps/NaN, parent offset, duplicate parent/child events, cross-video matching, basket-primary vs original boundaries, greedy trap, wrong attribution/link, review/uncertain/background/empty cases; CLI exit/output/schema checks + full suite sau code cuối.

Real verification: hand-calculate một subset TP/FP/FN độc lập với matching implementation; run CLI trên current real outputs + compatible reviewed GT; parse exported CSV/JSON và đối soát totals/GT counts/times. Nếu long job đang chạy, hoàn thiện tooling và report phase RUNNING rồi tiếp tục việc độc lập; không bịa terminal metrics.

**D07 PASS kỹ thuật:** evaluator/scope/review safeguards/tests và measurement bundle thật đủ; formal quality/split pending ghi riêng. Quality gate giữ ≥95%/≥90% per stat và requirements gốc, không tự PASS vì protocol revision làm một event khớp. D07 có phase long-run result pending khi job chưa terminal, không giả task toàn bộ done.

## D08 — Dashboard, annotated MP4, evidence, heatmap và exports

Điểm vào: dashboard/runner modules, overlay/video writer APIs, existing browser scripts/tests và complete bundle contracts.

1. UI nhận selected source/run/profile và consistent IDs/version/coverage. Không ngầm mở video gốc khi run là clip mà seek time vẫn clip-local. Source-global/clip-local mapping hiển thị/seek đúng.
2. Annotated video thật: bbox/tracks/observed-vs-predicted/ball/control, event-time identity/team, provisional/auto-confirmed score và status/evidence theo scope. Export MP4 giữ source PTS policy/CFR/VFR và writer failures thật; không chỉ contact sheet/synthetic video hoặc unannotated source được đổi tên.
3. Timeline/list/boxscore/court/heatmap/region stats cùng raw auto ledger. Render uncertainty/team-only/unknown và coverage, không biến unavailable thành 0 verified. Real grid/trajectories vào heatmap; bỏ tọa độ từ frame_index/modulo/distance default và không chỉ vẽ marker theo khoảng cách một chiều rồi claim measured xy.
4. Evidence: event→shot/pass/control/actor/rule/model/source refs, occurrence/confirmation times, dependency revisions/void. Click seek đúng pha, linked events có thể kiểm, corrections tách raw.
5. Progress/cancel/resume/failed/partial/completed phản ánh run state. CPU inference chậm không khiến UI freeze/báo success giả; existing-run playback và fresh-analysis modes có nhãn rõ. No automatic unsupported live claims.
6. Export events/raw audit/boxscore/summary/metrics/heatmaps/overlay đủ; validate names/content/source/profile. XSS/text escaping, HTTP ranges 206/416, missing media/links/errors đúng và không expose credentials/path traversal.
7. Giữ UI local và dễ dùng: chọn input/config hoặc preset, chạy/xem kết quả, click evidence/export. Không đưa chi tiết implementation vào flow nếu không giúp người dùng quyết định. Không đòi dịch vụ cloud/backend nặng để hoàn thành demo.

Tests: public API/run bundle loading/eligibility totals/geometry binding/seek offsets/status/exports, source hash/file errors, video range, text safety; full suite. Dùng skill frontend/browser phù hợp khi sửa UI/test browser.

Browser QA thực bắt buộc: desktop/mobile, play/pause/seek/evidence→frame, progress/cancel/fail/partial/unresolved states, court/heatmap, long names và downloads parse được. Lưu screenshots + machine-readable checks; unit tests/mock không thay browser. Inspect overlay frames/video readback để kiểm layout/PTS/counter.

**D08 PASS:** đủ UI/overlay/exports thật và tests/browser/output checks PASS, không còn placeholders được trình bày như measurements. Thiếu calibration ở scope khác báo unavailable; demo heatmap requirement phải có bằng chứng trên ít nhất scope hợp lệ, không chỉ banner unavailable cho tất cả runs. Ghi report/handoff rồi tự tiếp tục D09/D10 khi dependencies đủ.
