# Handoff task04 → task05/06

2026-11-02 — bàn giao **công cụ và contracts**, task04 IN_PROGRESS. Người dùng đã đồng ý hình thức bàn giao này và chờ dữ liệu/rules. Task05/06 vẫn TODO; không tự coi G04 đã đóng.

## Tài liệu và artifacts

Đọc [G03 report](../reports/task03-pipeline.md), [biên bản nghiệm thu](../reports/task03-task04-acceptance.md), [data report](../reports/data-v2.md), [contracts](../specs/contracts-v2.md), [annotation guide](../data/ANNOTATION_GUIDE-v2.md), [rules draft](../specs/rules-v2.md), [protocol draft](../specs/evaluation-protocol-v2.md).

Technical predictions tại codebase/outputs/acceptance-20261102/g03-clip02-verified; dataset scaffold tại codebase/data/v2; evidence gates/hashes tại codebase/outputs/acceptance-20261102. Dùng source hash và config của đúng run.

## Readiness cho người tiếp nhận

| Hạng mục | Có thể dùng | Chưa thể kết luận |
|---|---|---|
| Frame/detection/PTS | Reader, JSONL, bbox gốc, explicit export timestamps | Model chính xác bao nhiêu trên mọi footage |
| Court/heatmap | Thiết kế API, ROI, tổng hợp theo delta source time, kiểm thử homography synthetic | Geometry clip02/court dimensions đúng hoặc heatmap metric chính xác |
| Tracking | Prototype từ detections human, track lifecycle, unknown handling | Team/player identity đúng trên trận hai đội |
| Roster/GT | Schema, templates, validator | Roster thật, identity/control/PRA approved |
| Rules/evaluation | Draft case matrix và matching design | Applicability giải 3x3, protocol/split frozen hoặc metrics PRA |

Clip02 phù hợp kiểm thử kỹ thuật reader/detector. Chưa có bằng chứng đủ landmarks để khẳng định lý tưởng cho calibration hoặc có rõ cung chuẩn 6.75m.

## Task05 — ràng buộc hình học

Dùng ít nhất 4 cặp điểm tương ứng trên **cùng mặt phẳng sân**, phân bố tốt, không suy biến; xác minh kích thước/định nghĩa sân và reprojection error. **Vành rổ ở trên cao không phải điểm của homography mặt sân.** Chỉ dùng điểm chiếu xuống mặt sân nếu đã biết tọa độ và xác định được bằng chứng ảnh.

Bbox footpoint ((x1+x2)/2,y2) là ước lượng, chịu ảnh hưởng che khuất/crop; cần ROI/visibility và GT vị trí để đánh giá. Không tự tạo ma trận từ các điểm sân không nhìn rõ. Heatmap cần trọng số thời gian PTS và giới hạn gap, tránh cộng mỗi frame như cùng delta_t trên VFR.

Được chuẩn bị API/fixtures/prototype độc lập; nghiệm thu court/heatmap cần position GT và landmarks được review.

## Task06 — team và identity

Track ID khác player ID. Không gán player vào roster giả hoặc dựa trên nearest detection. Lưu unresolved/evidence khi mất dấu, giao cắt, không thấy số áo; đo ID switches/identity attribution khi có GT. Chưa có footage hai đội/roster để nghiệm thu phân team và player.

Các schema hiện có: player_positions, identities, ball_control, passes, shots, rebounds, assists, coverage, reviews. Nguồn header là dataset_schema.py v2.0.1. Không thêm reads GT/manifest result notes vào recognition runtime.

## Lệnh từ codebase

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe scripts/validate_dataset_v2.py --require-tooling-ready
.venv/Scripts/python.exe scripts/validate_dataset_v2.py --require-data-ready
.venv/Scripts/python.exe scripts/validate_dataset_v2.py --require-locked
```

Kết quả bàn giao: tests pass; các gate lần lượt exit0, exit2, exit3. Data/locked fail đúng kỳ vọng vì thiếu dữ liệu, không sửa flags để pass. Không chạy prepare ghi đè manifest. Không chạm v1 holdout hoặc thay detector/GPU stack.

## Điều kiện mở phần nghiệm thu phụ thuộc

Cần footage development/test mới đủ hai đội, roster, provenance/session/source_group được xác nhận, landmarks mặt sân, labels vị trí/identity/control/PRA và coverage đã review; chốt rule profile/protocol, extension FT-series và lock. Mục tiêu ≥50 shots/≥30 REB/≥30 AST positives kèm negatives vẫn chưa đạt.

Khi có dữ liệu, đề xuất update v2 và review split/labels trước freeze. Dataset/data-ready gate chỉ kiểm tra tối thiểu tự động, không thay review chuyên môn. Các engines PRA, evaluator và dashboard tiếp tục theo task07–15; chưa được triển khai trong lần bàn giao này.
