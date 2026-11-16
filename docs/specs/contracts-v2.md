# Data contracts v2.0.1

Rà soát 2026-11-02. Phạm vi đã có code: frame/detection/export G03 và schema/validator dataset G04. Rule profile và evaluation protocol còn draft. Các engines PRA chưa được xây.

## Frame và thời gian

`FrameRecord`: video_id, frame_index (zero-based), source_time_s (giây hữu hạn ≥0), original_wh=[width,height], raw_pts, time_base, timestamp_status, timestamp_policy.

Tính raw_time_s = frame.pts × frame.time_base (fallback stream.time_base khi frame thiếu time_base); source_time_s = raw_time_s − origin_s. Không trừ hai raw_pts thuộc timebase khác nhau. Origin là thời gian raw của frame đầu có PTS; nếu trước đó thiếu PTS thì căn theo bước ước lượng và đánh dấu estimated.

- strict_reject: thiếu PTS hoặc không tăng → lỗi.
- repair_with_audit: thiếu PTS → previous + 1/fps và estimated; PTS không tăng → previous + 1/fps và repaired, có warning. Reader làm tròn microsecond trước khi so sánh, để chuỗi JSONL không bị trùng do epsilon số thực.
- flag_only: giữ quan sát không tăng, đánh irregular; writer yêu cầu thời gian tăng nên export MP4 sẽ fail nếu gặp trường hợp này. Có thể dùng --no-video-export để audit JSONL.
- FPS chỉ dùng khi phải ước lượng timestamp mất; giá trị đó không phải PTS quan sát thật.

`VideoMetadata.is_vfr` là heuristic từ stream rates, không chứng minh từng bước PTS. Việc bảo toàn thời gian được kiểm tra bằng timestamp đọc lại, không dựa vào cờ này.

## Detection và JSONL

`DetectionRecord`: xyxy=[x1,y1,x2,y2] ở frame gốc, class_id, class_name, confidence. Tất cả hữu hạn; 0≤x1<x2≤width, 0≤y1<y2≤height; confidence∈[0,1].

Runtime phải có đúng ba lớp ball/human/rim. Mapping lấy từ metadata model khi load, ghi trong run.json; baseline hiện 0/1/2 nhưng downstream dùng class_name hoặc mapping của run. Mapping runtime không bị hardcode khi tạo record.

Resize giữ tỷ lệ cạnh dài max_edge, quy đổi x/y theo kích thước input thực đã làm tròn. Không thay detector/backend hoặc dùng nhãn làm đầu vào.

`FrameDetectionsRecord` ghi một dòng JSONL cho mỗi frame, kể cả detections=[]. Gồm toàn bộ trường FrameRecord, detections và model_call_ms. Detections là predictions, không phải GT. ID của run mặc định là filename stem; ánh xạ sang manifest v1/v2 phải qua source hash.

## Export và trạng thái run

App tạo output directory mới, không ghi đè; filenames cấu hình là basename nội bộ khác nhau. Từ chối footage reserved theo SHA-256 kể cả khi đổi tên file. .env chỉ đọc tại máy, không lưu key vào config/log.

Writer nhận source_time_s, gán PTS với timebase 1/1,000,000; từ chối hai giá trị trùng tick kể cả khi float tăng rất nhỏ. CFR và VFR đều dùng timestamp tường minh, không dàn đều theo average FPS. MP4 phải được đọc lại để đối chiếu sai số lượng tử khoảng microsecond với timeline JSONL. Timestamp repaired/estimated được đối chiếu riêng với PTS quan sát và không nhận cờ preserved_vfr_mapping=true. Không export audio. Kích thước frame giữ nguyên, H264/yuv420p có nén; không cam kết pixel-identical.

run.json gồm run_id/status, source hash, metadata, config, runtime/versions/mapping, counts (read/written/detections/timestamp_status), timings và export policy. Trạng thái:
- completed: đọc tới EOF thành công;
- partial: prefix giới hạn ngắn hơn số frame metadata;
- failed/cancelled: lỗi hoặc hủy, không phải output hoàn chỉnh.

Metadata frame count có thể là ước lượng khi container thiếu thông tin; cần audit decode để nghiệm thu. Model-call gồm preprocessing/inference/postprocessing runtime, không phải pure kernel latency. Pipeline timing bao gồm probe/load/warmup/decode/resize/overlay/JSON/encode/flush. Stage totals không nhất thiết cộng bằng total do overhead và flush.

Lỗi Python bắt được sau khi tạo run directory được ghi bằng tên stage và exception class; không lưu message/traceback SDK có thể chứa URL credentials. Lỗi input/config trước khi tạo directory không tạo completed metadata giả. Kill process/native crash có thể không chạy cleanup hoặc ghi run.json; artifact thiếu metadata/không completed không phải bằng chứng nghiệm thu.

## Dataset schema

Nguồn header máy đọc: [dataset_schema.py](../../codebase/src/basketball_scoreboard/dataset_schema.py), SCHEMA_VERSION=2.0.1. Mỗi bảng annotations là CSV UTF-8:

| Bảng | Khóa và quan hệ |
|---|---|
| shots | shot_id; video/shooter/team, release/outcome/score_time_s, shot_type, result, notes |
| rebounds | rebound_id; video/shot/actor/team, rebound_time_s, rebound_type, notes |
| passes | pass_id; video/passer/receiver/team, release/receive_time_s, outcome |
| assists | assist_id; video/pass/shot/passer/scorer/team, assist_time_s, eligibility, notes |
| player_positions | position_id; video/player/team, time_s, x_image/y_image, x_court/y_court, visibility, notes |
| identities | identity_id; video/track/player/team, start/end_time_s, evidence, notes |
| ball_control | control_id; video/player/team, start/end_time_s, state, evidence_status, notes |
| coverage | interval_id; video, start/end_time_s, status, notes |
| reviews | (table_name,record_id); review_status, reviewer, reviewed_utc, review_notes |

Roster: team_id,player_id,jersey_number,name,is_active. Player ID khác track ID; số áo duy nhất trong team theo phạm vi roster phiên. Cross-video links không hợp lệ; ID sự kiện duy nhất trong bảng. Assist time tham chiếu pass release, không phải lúc ghi điểm. Team rebound để actor_id rỗng. Court coordinates có thể trống theo cặp nếu chưa calibration.

Manifest có media relative_path nằm trong codebase, SHA-256 và stream metadata/session/camera/source_group/provenance_status. Data gate cần provenance_status=confirmed và source_group đã xác định; session/camera khác nhau chưa chứng minh khác pha. Cần review provenance thủ công, không tự gán session mới chỉ vì khác filename.

## Review, gates và lock

Không có review → draft theo nghĩa đánh giá; approved cần reviewer và timestamp timezone-aware. Validator không xác thực danh tính thật của người ký hoặc thay review chuyên môn. reviews.csv hiện là snapshot một dòng/key; lịch sử phải giữ bằng phiên bản dữ liệu, không thêm hai review trùng key.

Structural/tooling gate kiểm tra schema/hash/refs/finite/timing/splits/lock hiện có. Data gate thêm roster/rules/protocol được duyệt, approved các loại nhãn, positives/assist negatives, coverage và calibration/test. Đây là mức tối thiểu cho pilot, chưa chứng nhận đủ quy mô ≥50 shots/≥30 REB/≥30 AST hoặc đủ mọi hard case. Locked gate thêm split locked và lock.json hợp lệ.

`data/v2/lock.json` lưu object `files` ánh xạ đường dẫn tương đối từ data/v2 sang SHA-256 của manifest.csv, roster.csv, ruleset.json, splits.json và cả 9 annotations. Không hash chính lock.json. Hiện **chưa có lock**, không tạo khi data trống. Khi freeze, kèm snapshot/version các docs rules/protocol và provenance review.

Schema hiện chưa có typed FT-series/foul/possession references. Dùng notes cho đề xuất draft, không coi đó là đầy đủ chuỗi FT cho benchmark; chốt extension tương thích trước freeze. Unknown identity/evidence phải được giữ, không suy người chơi từ nearest box để tạo GT.

Xem [annotation guide](../data/ANNOTATION_GUIDE-v2.md), [rules](rules-v2.md), [protocol](evaluation-protocol-v2.md).

## Spatial/tracking extensions — nghiệm thu công cụ 2026-11-03

Court/trajectory/heatmap contracts: [court-heatmap-v2.md](court-heatmap-v2.md). Track/team/identity contracts: [player-identity-v2.md](player-identity-v2.md). Đây là extensions cho task05–06, không đổi header GT v2.0.1 và không biến predictions thành ground truth.

Calibration version gồm digest nội dung config. ROI không tự chứng minh player role; predicted/invalid observations là ranh giới ngắt heatmap. Event-time identity dùng mapping_at, không dùng mapping cuối video gán ngược lịch sử. Geometry và nhận diện hai đội thật vẫn pending; xem [nghiệm thu](../reports/task05-task06-acceptance.md).
