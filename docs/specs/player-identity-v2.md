# Player/team/identity contracts — kiểm chứng 2026-11-03

G06 core tooling đã kiểm thử; **G06-D và OCR provider còn pending**. Đọc [report](../reports/task06-players-identity.md) và [handoff task07](../handoffs/task06-to-task07-08-12.md).

## Tracker

PlayerTracker dùng damped constant-velocity prediction và Hungarian matching trên IoU/center distance. Không phải Kalman filter hoặc ReID model. Association chưa có benchmark crossing/occlusion trên trận hai đội; synthetic tests không chứng minh ID accuracy thực.

Input dùng class_name từ runtime mapping, bbox/confidence ở ảnh gốc và PTS tăng. Không fallback class_id=1 nếu metadata nói là ball. Bbox gần trùng được dedup với IoU≥.95; đây là heuristic cần đo trên footage thật.

Stale tracks được retire **trước association** khi time_since_observed>max_age_s, không phục hồi ID cũ chỉ vì bbox giống. Timeout dùng giây, không thêm ngưỡng 30frames phụ thuộc FPS. min_hits vẫn là số observation confirmations, không phải thời lượng đã quan sát.

Namespace đầy đủ: (source_run_id,video_id,segment_id,track_id); string trk_<segment>_<number> không globally unique giữa nhiều run/video. Reset tạo ID mới; đổi segment làm invalid geometry cũ. Camera/segment observed và predicted phải thống nhất.

Role: ngoài ROI→non_player; trong ROI→unknown khi chưa có role evidence. ROI không chứng minh player (trọng tài/staff có thể ở trong sân). API nhận role evidence tường minh từ upstream; tests dùng synthetic_fixture_player. CLI chưa có role classifier học máy, không tự bịa mọi human thành player.

Observed bbox khác predicted bbox; predicted samples giữ predicted_occluded và không được project/heatmap nâng thành valid observed. original_wh lấy source metadata, tránh hardcode landscape cho video portrait.

## Color evidence và runtime CLI

--video dùng đúng media SHA-256 để decode theo G03 frame/PTS, lấy median RGB của torso crop quan sát và đưa vào TeamColorClassifier rồi resolver. Không có video/crops thì roster một mình không tạo được team evidence.

Color classifier so prototypes trước phiên, có ambiguity margin và absolute distance rejection. Score là heuristic, không phải calibrated probability. Team evidence window/TTL mặc định2s; unknown và evidence hết hạn không bị ép vào đội.

Roster config kiểm tra player/jersey/team/colors; lookup chỉ active player và theo (team_id,jersey_number). Hai đội cùng số áo không bị gộp. Roster synthetic/draft chỉ chạy diagnostic; không phải roster thật của clip02.

## Identity evidence, thời gian, OCR provider và conflicts

JerseyEvidenceRecord là cấu trúc chuẩn nhận evidence từ OCR hoặc fixtures. Đã xây dựng hoàn chỉnh provider layer:
- `evaluate_crop_quality(crop)`: Kiểm tra độ phân giải tối thiểu ($16\times 24\,\text{px}$) và độ biến thiên cường độ (std $\ge 8.0$) để loại trừ crop mờ, phẳng, rỗng.
- `LocalEasyOCRProvider`: Chạy offline với `download_enabled=False`, kiểm tra file weights trên đĩa và ném `ModelWeightsUnavailableError` nếu thiếu; lọc số áo bóng rổ 1–2 chữ số ($0$–$99$).
- `MockOCRProvider`: Phục vụ kiểm thử unit/chẩn đoán, bị từ chối nếu chạy production.
- CLI wiring: `track_players.py` tích hợp `--enable-ocr`, `--ocr-provider {easyocr,mock}`, `--ocr-weights-dir`, `--ocr-sampling-cadence`.
- Trạng thái hiện tại: **Chờ người dùng phê duyệt tải weights EasyOCR (130 MB)**. Không tự ý tải ngầm; trong production khi chưa có weights, OCR giữ trạng thái disabled hoặc báo lỗi tường minh nếu bật flag.

Resolver dedup evidence IDs, bỏ confidence không đủ, dùng weighted consensus và TTL. Một jersey reading không đủ để xác nhận với default threshold 3 (hoặc ngưỡng cấu hình). Future/expired evidence không được dùng tại timestamp hiện tại. Team known không đồng nghĩa player known. Khi thực thể nằm trong ROI sân và có evidence đội/cầu thủ được xác nhận, role được cập nhật từ `unknown` thành `player`.

update_track_mapping lưu revision khi assignment/conflict đổi. Mapping mới bắt đầu ở timestamp xác nhận, không backfill vào khoảng chưa có evidence; evidence expiry giới hạn khoảng tra cứu qua gap thưa. Các snapshot đã trả không bị mutate khi kéo dài view hiện tại. Ledger xuất theo run là versioned interval view, không phải append-only database WAL.

mapping_at(track_id,source_time_s) hoặc enrich_observations_with_identity là đường tra cứu event-time. Không dùng current_mappings cuối video để gán mọi pha trước đó. Predicted/non-player observations không nhận confirmed player assignment. Duplicate active-player conflict giữ tối đa một assignment phù hợp, có revision và conflict reason.

## Metrics và phần chưa đạt

Exports: tracked_observations.jsonl, identity_mappings.json, team_evidence.json, tracking_summary.json, run.json. Có source/config/code/package fingerprints, roles/sample counts, color evidence count và OCR status. Team/player accuracy hiện N/A vì không có GT độc lập; không gọi số color votes là accuracy.

Footage development hai đội, roster thật và reviewed track/team/identity GT còn thiếu. Trước benchmark chốt matching/mẫu số; unknown/miss trên GT hợp lệ phải vào lỗi/coverage. Mục tiêu team accuracy≥90% chưa đo. ID switches/fragmentation trên trận thật chưa đo.

Task07 có thể dùng contracts/fixtures cho ball tracking và control state machine. Real attribution cần role/identity/control evidence; unresolved không được biến thành nearest-player identity. Task08 cần geometry/release-foot evidence riêng; full dashboard task12 chưa được xây.

Xem [decision record](../decisions/20261103-ocr-model-evaluation.md).

