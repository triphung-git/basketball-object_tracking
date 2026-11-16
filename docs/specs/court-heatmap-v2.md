# Court/heatmap contracts — kiểm chứng 2026-11-03

Phạm vi: công cụ task05 và adapter task06. G05-G còn PENDING; cấu hình synthetic không phải calibration thật. Xem [nghiệm thu](../reports/task05-task06-acceptance.md).

## Geometry và validity

CourtConfig giữ schema version, camera/segment, source hash, original_image_wh, status, is_synthetic, correspondences fit/check, ROI, coordinate units/bounds và provenance. Source code là [court.py](../../codebase/src/basketball_scoreboard/court.py). calibration_version trên observation gồm schema version và digest nội dung config; hai ma trận khác nhau không dùng chung version chỉ vì cùng schema.

Homography chỉ dùng điểm trên mặt phẳng sân, ít nhất 4 cặp không suy biến. Rim/backboard trên cao không phải floor correspondence. Solver kiểm tra finite/duplicate/collinear, determinant/conditioning, inverse và projective denominator; đây là least-squares solver hiện có, không có automatic camera-motion compensation hoặc bảo đảm tracking qua cut.

Production calibration cần validated, không synthetic, provenance approved có reviewer, source hash và ROI. Reprojection/check errors vượt threshold bị từ chối. Config/source hash hoặc dimensions không khớp run bị từ chối ở CLI. Empty ROI không mặc định thành toàn ảnh.

Synthetic/draft/template cần --allow-uncalibrated và output diagnostic. Fixture synthetic hiện có residual check 190px, lớn hơn threshold10px; chỉ dùng kiểm thử thuật toán, không chứng minh geometry clip02 đúng hoặc scale theo mét đã được đo.

Footpoint = bbox bottom-center là ước lượng. Crop/touch boundary/outside ROI/invalid projection/predicted occlusion giữ validity_reason; phép project không tự nâng predicted/occluded thành quan sát valid. Geometry-only status có thể được tính lại khi đổi calibration; sample_type và visibility uncertainty vẫn giữ nguyên.

## Observation contract

TrajectoryObservation gồm source run/video/hash, observation ID, frame/index/PTS/status, segment/camera, bbox/footpoint, position_method, projected_court_xy/court_units, validity/reason, calibration_version, track/player/team nullable, role, sample_type và confidence.

Tọa độ ảnh theo frame gốc. Timestamp theo G03 microsecond-normalized timeline; frame1086–1088 clip02 được repaired, không nhận là PTS nguyên vẹn. Player ID khác track ID; trackless human detections không tự tạo trajectories.

## Tích lũy thời gian

- Left-hold trên hai endpoints kề nhau của cùng namespace run/video/hash/track/segment/camera/calibration.
- Cả hai endpoints phải observed, valid và có court point; invalid/predicted được giữ trong stream để ngắt liên tục, không filter mất rồi nối hai đầu còn lại.
- Main mode chỉ tích lũy role=player. Diagnostic mode có thể gồm unknown humans và phải ghi scope; non_player luôn bị loại.
- Gap>max_gap_s ngắt toàn interval. Generic operational exclusions dùng union, không trừ overlap hai lần. reason cut/camera_change/segment_change loại cả interval băng qua ranh giới, không giữ pose cũ sang cảnh mới.
- Default clock policy chỉ valid/repaired; estimated không tự được nhận, irregular cần policy tường minh. Metadata ghi repaired mass/counters riêng.
- Last sample không tự được cộng 1/FPS. CLI không extrapolate tới cuối video. API final_time_s chỉ dùng khi có boundary thật và trong max_gap_s.
- Total grid = team A + team B + unknown, đơn vị occupancy seconds/player-seconds theo scope. Tổng đúng về số học không chứng minh positions hoặc role/team đúng.

Input trackless cho CLI có thể xuất observations/preview diagnostic, **mass=0**, không nối bbox order thành một người. Các metrics raw 12.1500 và integrated20.1667 trong output cũ trước review không được dùng nghiệm thu hiện tại.

## Replay, revision và exports

Replay cùng complete batch có interval/observation dedup; ID thay nội dung phải tạo revision và recompute. reset/recompute từ raw log tạo view mới, không append mass. Đây là API batch; chưa có persisted incremental checkpoint engine. Seek/reload thực hiện bằng đọc lại raw log và recompute; caller không được giả định các batch rời không có overlap tự nối được endpoints.

updated_team_mappings/updated_player_mappings là override **toàn track cho offline view** được yêu cầu tường minh, không phải causal identity inference. Muốn event-time mapping dùng ledger/mapping_at ở identity resolver. Ghi override/version trong run mới, giữ raw log.

CLI output directory mới có trajectories.jsonl, heatmap_raw_grid.json, heatmap_total.png, heatmap_summary.json và run.json. Metadata có acceptance_scope, input/config/code fingerprints, units, temporal/role/exclusion policies, counts, mass and replay result. Không ghi đè source/run cũ. PNG là view; raw grid và independent integration mới là evidence số học.

Xem [guide](../guides/court-calibration.md), [player/identity](player-identity-v2.md), [G05 report](../reports/task05-court-heatmap.md).

