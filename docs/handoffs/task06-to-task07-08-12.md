# Handoff Task05–06 → Task07 /08 /12

**Cập nhật 2026-11-04:** OCR weights đã được duyệt và chạy local; Task07 đã có implementation/fixtures/demo clip04, xem [report](../reports/task07-ball-possession.md) và [handoff mới](task07-to-task08-09-10.md). Clip04 development được [duyệt riêng](../decisions/20261104-clip04-development-exposure.md); nhóm clip04–07 đã exposure. Nội dung 2026-11-03 bên dưới giữ làm lịch sử, không dùng dòng TODO/OCR-pending/holdout chưa tiếp xúc để ghi đè trạng thái mới. G05/G06 real-data acceptance vẫn pending.

2026-11-03. **Core tools được kiểm chứng; Task05 và Task06 vẫn IN_PROGRESS.** G05-G/G06-D pending; OCR provider code đã hoàn thiện nhưng weights download pending user authorization. Task07 giữ TODO; chỉ phần độc lập được chuẩn bị từ nền bàn giao này.

Đọc [nghiệm thu chung](../reports/task05-task06-acceptance.md), [code review](../reports/task05-task06-code-review.md), [G05 report](../reports/task05-court-heatmap.md), [G06 report](../reports/task06-players-identity.md), [contracts](../specs/contracts-v2.md), [court](../specs/court-heatmap-v2.md), [identity](../specs/player-identity-v2.md).

## 1. Input đã kiểm chứng

Directory mới: codebase/outputs/acceptance-20261103-task05-06-review/.
- tracking-handoff/: tracked_observations.jsonl, identity_mappings.json, team_evidence.json, jersey_evidence.json, tracking_summary.json, run.json.
- heatmap-handoff/: trajectories.jsonl, heatmap_raw_grid.json, PNG, summary/run.json.
- raw-trackless-verified/: diagnostic mass0, không ghép bbox order thành identity.
- audit.json, tests-verified.log, v2-validation.json, handoff-snapshot.json: evidence kiểm thử/hash/readiness.

Source là G03 verified 1089 frames. Run mới có 1416 observations (1100 observed, 316 predicted); 900 torso-color evidence records; 0 verified players, tất cả player_id unresolved. Synthetic homography/roster chỉ dùng diagnostic, không phải phép đo/đội thật của clip02.

159 tests pass (~23s). Independent interval/grid audit tính 727 intervals và 12.116667s diagnostic human occupancy. Không gọi số này là team/player accuracy; geometry/team/player metrics đều N/A.

## 2. Task07 có thể triển khai ngay phần nào

Có thể xây ball candidate tracking, nullable actor contracts, control/pass/possession state machine và fixtures cho observed/predicted/missing/gap/cut. Có thể nối adapter với human track outputs ở mức diagnostic. Chưa triển khai các engine này trong lượt nghiệm thu.

Các điều kiện bắt buộc:
- Dùng class_name/runtime mapping, không hardcode ball=0/human=1 khi metadata khác.
- Namespace run/video/segment/track và source timestamps đúng. Track ID khác player ID; predicted khác observed.
- ROI không chứng minh player. Current real-input diagnostic có role unknown/non_player, không tự đổi hết thành player để control engine có actor. Khi có bằng chứng đội/cầu thủ được resolver xác nhận trong ROI, role mới được nâng thành player.
- Candidate tương tác với unknown track phải giữ unknown/provisional; confirmed player/control attribution cần evidence phù hợp. Không dùng nearest distance một frame thay bằng chứng control.
- Không xác nhận possession/stat từ predicted-only positions, không nối qua cut/stale gaps.
- Identity tra theo mapping_at(track_id,event_time) hoặc observation được enrich theo thời điểm, không dùng current_mappings cuối video gán ngược lịch sử.
- Chưa có OCR provider hoặc jersey evidence thì player_id unresolved, không tự lấy tên roster/annotation IDs làm identity.
- Không dùng clip04–07 holdout để debug; task04 data/rules/protocol còn mở.

## 3. Gate để nghiệm thu phần task07 phụ thuộc dữ liệu

Cần footage development hai đội rõ bóng/jersey, roster/role evidence, reviewed ball/control/pass và track/team/identity GT. G05 landmarks/geometry cần được chốt nếu dùng court geometry. Quyết định OCR/model phải được thẩm định/phê duyệt đúng scope; không tự tải model lớn hoặc cloud upload.

Thiếu dữ liệu không chặn logic/contracts/fixtures độc lập, nhưng không được gọi real possession/actor attribution PASS. Unknown/missing trên GT hợp lệ phải vào coverage/error metrics.

## 4. Task08 và Task12 tiếp nhận

Task08 nhận coordinate/ROI/nullable actor interfaces; **chưa có arc/rim-floor geometry thật được duyệt**. Không dùng tọa độ giả trong fixture hoặc bbox bottom khi airborne làm shot-value ground truth. Quy tắc/phiên bản giải và release-foot evidence vẫn cần xác minh.

Task12 nhận raw logs/grid/metadata để hiển thị/recompute. API hiện là batch; seek/reload dùng raw-log replay/recompute, không có persisted streaming checkpoint engine hoặc full web dashboard. Offline whole-track mapping corrections phải ghi revision/run mới; causal mapping dùng interval ledger.

PNG diagnostic đã kiểm tra mở lại; màu sắc/scale synthetic không chứng minh accuracy thật. Heatmap cá nhân không được xuất tên khi identity chưa đủ evidence.

## 5. Lệnh tái chạy từ workspace root

Chọn output directory mới, tracking và heatmap tách nhau:

```powershell
codebase/.venv/Scripts/python.exe -m unittest discover -s codebase/tests -v
codebase/.venv/Scripts/python.exe codebase/scripts/track_players.py --detections codebase/outputs/acceptance-20261102/g03-clip02-verified/detections.jsonl --run-json codebase/outputs/acceptance-20261102/g03-clip02-verified/run.json --court-config codebase/configs/courts/synthetic_half_court.json --roster-config codebase/configs/rosters/synthetic_dual_team_roster.json --video codebase/assets_test/20521993-uhd_2160_3840_60fps.mp4 --allow-uncalibrated --output-dir codebase/outputs/new-task56-tracking
codebase/.venv/Scripts/python.exe codebase/scripts/generate_heatmap.py --court-config codebase/configs/courts/synthetic_half_court.json --detections codebase/outputs/new-task56-tracking/tracked_observations.jsonl --run-json codebase/outputs/acceptance-20261102/g03-clip02-verified/run.json --allow-uncalibrated --verify-replay --output-dir codebase/outputs/new-task56-heatmap
```

Không cần chạy lại detection model chỉ để tracking/projection. Không có --video thì không có color evidence mới từ video; roster một mình không phân đội. --allow-uncalibrated là diagnostic flag, không tự phê duyệt geometry hoặc roster. Exclusion JSON operational có thể cấp bằng --exclusions, không đọc coverage GT âm thầm trong production.

## 6. Trạng thái và dữ liệu cần bổ sung

Task05: core tooling PASS, geometry acceptance pending. Task06: tracker/color/resolver core PASS, OCR provider code PASS, OCR model weights download PENDING USER AUTHORIZATION, real team/identity acceptance pending. G56: computational/synthetic PASS, real match accuracy chưa đo. Task04 vẫn mở, task07–15 chưa nghiệm thu.

Người tiếp nhận cần landmarks/GT vị trí, footage development/test mới/roster/identity evidence, role/control/pass GT và model decision theo [OCR record](../decisions/20261103-ocr-model-evaluation.md). Không sửa locked v1 hoặc dùng labels làm oracle để vượt gate.

