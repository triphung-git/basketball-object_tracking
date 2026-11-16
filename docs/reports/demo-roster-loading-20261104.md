# Demo nạp roster/thông tin đội theo video — 2026-11-04

Đã thực thi yêu cầu giả lập roster trên video có sẵn. Phạm vi là **demo cấu hình**, không phải nghiệm thu nhận diện trận hai đội hoặc automatic PRA. Không đổi trạng thái Task05/06 từ bằng chứng này.

## Input và cách giả lập

- Video clip02: `codebase/assets_test/20521993-uhd_2160_3840_60fps.mp4`.
- SHA-256: `3ed25e1b246ccebbe7904d76a22fbea65ebfcb86701499417cd52962f1fc4c26`.
- Cache detector: `codebase/outputs/acceptance-20261102/g03-clip02-verified/`.
- Script: [demo_roster_loading.py](../../codebase/scripts/demo_roster_loading.py).
- Artifacts: [summary.json](../../codebase/outputs/demo-roster-loading-20261104/summary.json), [independent audit](../../codebase/outputs/demo-roster-loading-20261104/independent-audit.json).

Video có một người tập ném, không phải trận hai đội và không có số áo sử dụng được trong demo. Tên đội, player IDs và các số áo 7/23 đều là placeholders, không được suy ra từ video. Hai profile ALPHA/BETA mỗi profile có 2 đội và 4 cầu thủ giả lập, được lưu bằng đúng schema roster mà pipeline hiện tại đọc.

Một lượt sampling lấy torso RGB thật từ video; median toàn bộ mẫu là `[48, 83, 134]`, được dùng làm prototype diagnostic cho đội A. Màu đỏ của đội B là placeholder, không khẳng định đội B xuất hiện. Sampling toàn clip dùng để chuẩn bị cấu hình demo, không phải bằng chứng nhận diện causal hoặc phép đo team accuracy.

Sau đó cùng pipeline tracking chạy hai lần với hai file roster khác nhau, không sửa engine giữa hai lần. Không dùng court config giả, không tạo tọa độ sân hoặc heatmap vật lý. Cache detection được dùng lại; không chạy detector, không đọc GT, không thay dataset/splits.

## Kết quả thực thi

| Chỉ số | ALPHA | BETA |
|---|---:|---:|
| Frames | 1089 | 1089 |
| Tracking observations | 1416 | 1416 |
| Observed / predicted | 1100 / 316 | 1100 / 316 |
| Observations gán nhãn đội A demo | 1100 | 1100 |
| Unknown team | 316 | 316 |
| Video player identities resolved | 0 | 0 |

Thay roster làm các output dùng team IDs của profile tương ứng. Independent audit đối chiếu bbox, track IDs, sample types và source timestamps giữa hai lần: không đổi; không có team ID từ profile kia rò sang output. Đây là kiểm tra thay cấu hình, không phải xác nhận màu áo đã phân đúng đội thật.

OCR không chạy trong demo nạp cấu hình này; `jersey_evidence.json` của cả hai lần đều rỗng và mọi video `player_id` vẫn null. Giá trị legacy `ocr_status=not_enabled_pending_model_decision` trong tracking summary chỉ phản ánh nhánh OCR tắt của CLI; không có nghĩa quyền tải OCR hiện vẫn chưa được cấp. Người dùng đã phê duyệt tải weights OCR; demo này không tải thêm hoặc kiểm thử lại engine OCR.

## Fixture danh tính tách riêng

`fixture-alpha.json` và `fixture-beta.json` dùng các jersey evidence **tạo bằng code**, không phải kết quả OCR từ video. Mỗi fixture đưa cùng số 7 cho hai tracks của hai đội, qua 4 thời điểm. Resolver ghép đúng player IDs theo `(team_id, jersey_number)` tại 0.3s và không hồi tố danh tính về 0s. Hai player IDs không bị gộp.

Fixtures có `is_synthetic=true`, `source_video=null` và `evidence_kind=fabricated_fixture_not_ocr`. Không trộn các mapping này vào tracking/video outputs. Không sử dụng fixtures để báo real identity accuracy.

## Tái chạy và kiểm chứng

Từ workspace root, chọn output directory chưa tồn tại:

```powershell
codebase/.venv/Scripts/python.exe codebase/scripts/demo_roster_loading.py --output-dir codebase/outputs/demo-roster-loading-next
```

Script chuẩn bị cấu hình, lấy màu từ video, chạy hai profile, kiểm tra không có video identity tự phát sinh và kiểm tra fixture team-qualified lookup. `summary.json`/`run.json` ghi scope diagnostic, fingerprints, runtime và limitations; lỗi sau khi tạo output ghi status failed. Ba lượt decode video 4K có thể mất vài phút trên CPU. Clock repair ở các frame1086–1088 giữ chính sách G03, không coi đó là PTS quan sát nguyên vẹn.

Kiểm chứng lần này: compile và CLI help PASS; ba lượt tracking completed; hai fixtures PASS; independent output audit PASS. Thử lại output directory đã tồn tại bị từ chối và hashes của tất cả output cũ giữ nguyên. Không chạy lại toàn bộ suite vì chỉ thêm script demo, không sửa engine; không tuyên bố suite hiện tại được nghiệm thu lại.

## Bước tiếp theo

Có thể dùng roster demo để phát triển luồng cấu hình và consumers. Khi có video trận thật, thay bằng roster/thông tin đội của trận đó. Tên thật không thể khôi phục từ video không có nguồn đối chiếu; jersey không đọc được vẫn unresolved. Task05 cần geometry/GT vị trí độc lập; Task06 cần footage hai đội và reviewed GT để đo chất lượng thật. Demo này không tự đóng các gates đó hoặc tạo points/rebounds/assists.
