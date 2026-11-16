# Annotation guide v2.0.1

2026-11-02 — hướng dẫn công cụ, dataset PRA thật chưa sẵn sàng. Không dùng ví dụ hoặc tests synthetic làm nhãn thật. Roster hiện chỉ có header.

## Trình tự tạo ground truth

1. Xác minh quyền dùng video, source/session/camera, replay/crop/derived footage và source hash. Không dùng clip04–07 holdout v1 để tuning. Footage cần đủ hai đội, bóng, số áo và chuỗi trước/sau pha; highlights nhiều cut có thể dùng khảo sát nhưng không mặc định đủ control/assist/identity continuity.
2. Dùng video gốc với normalized PTS G03. Xem đủ diễn biến trước pass/release và sau outcome/control; khoảng ±2s là điểm bắt đầu, kéo dài khi chuỗi hành động chưa kết thúc. Không dùng average FPS cho VFR.
3. Lập roster thật: team_id,player_id,jersey_number,name,is_active. Chưa thấy số áo/identity thì ghi uncertainty trong draft, không tự điền tên giả để đủ hai đội.
4. Gán cả positions/identities/ball_control/passes/shots/rebounds/assists, đối chiếu links cùng video và actor/team. Header chuẩn ở [dataset_schema.py](../../codebase/src/basketball_scoreboard/dataset_schema.py); dùng đúng tên trường và dấu phẩy CSV.
5. Phân coverage toàn video: fully_reviewed (gồm cả background), excluded (lý do cụ thể), unreviewed, needs_review hoặc uncertain. Không có status background riêng. Không đánh fully_reviewed chỉ vì xem đoạn bóng vào rổ.
6. Review độc lập trên video gốc. Mỗi approved row, kể cả coverage/excluded, có entry reviews.csv: table_name,record_id,review_status,reviewer,reviewed_utc,review_notes. ISO8601 có timezone; không tự ghi người dùng đã duyệt. Không review nghĩa là chưa approved.
7. Chạy validator; xử lý errors/readiness notes, chưa promote draft chỉ vì exit0. Chốt rules và protocol trước dùng test; sau đó mới đề xuất split/lock để người có trách nhiệm duyệt.

## Quy ước từng nhóm

| Nhóm | Quy ước |
|---|---|
| Positions | x_image/y_image theo frame gốc, không theo ảnh resize; x_court/y_court để trống cả hai nếu chưa có mapping sân được xác minh |
| Identities | track_id tạm thời khác player_id roster; start/end khoảng có evidence, notes ghi đứt track/che khuất |
| Control | state thuộc controlled/free/pass/shot/loose/unknown; evidence_status phân quan sát với dự đoán/uncertain; khoảng tăng theo PTS |
| Passes | release_time_s ≤ receive_time_s; outcome completed/deflected/turnover/uncertain; completed cần receiver roster cùng team |
| Shots | 1pt/2pt/free_throw, made/miss/uncertain; made có release ≤ score_time_s ≤ outcome; chưa xác minh loại ném thì giữ draft |
| Rebounds | nối missed shot cùng video; time không trước outcome; offensive/defensive đúng team; team_rebound không có actor cá nhân |
| Assists | nối pass và shot/scorer cùng video; eligible/ineligible/uncertain; assist_time_s bằng pass release; giữ cả hard negatives |
| Coverage | interval_id duy nhất, không overlap, đủ từ 0 tới cuối video; lý do excluded phải được review |

Các ca rebound vs touch, controlled tip, FT và assist sau dribble/deflection xem [rule profile đang draft](../specs/rules-v2.md). Không áp “pass dẫn đến FT luôn không assist”; không suy quyết định chỉ bằng một ngưỡng số giây. Những ca cần FT-series/foul/possession refs phải giữ draft và chốt schema extension trước freeze.

## Review ledger và tránh thất thoát

reviews.csv là trạng thái hiện tại với một row cho mỗi (table_name,record_id), không phải append nhiều phiên bản cùng key. Lưu lịch sử qua snapshot/version có provenance. Thay nhãn đã lock phải có revision được phép và test exposure record; không sửa hash để hợp thức hóa.

Không chuyển predictions G03 thành approved GT tự động. Synthetic fixtures trong tests nằm ngoài data/v2. Không nhập số liệu thủ công vào production để thay automatic recognition.

## CLI từ thư mục codebase

```powershell
.venv/Scripts/python.exe scripts/validate_dataset_v2.py --require-tooling-ready
.venv/Scripts/python.exe scripts/validate_dataset_v2.py --require-data-ready
.venv/Scripts/python.exe scripts/validate_dataset_v2.py --require-locked
```

Hiện lệnh thứ nhất kỳ vọng exit0; data gate exit2, locked gate exit3. Exit1 là lỗi cấu trúc, exit4 là chưa tooling-ready. Validator in JSON đầy đủ; output-json chỉ ghi vào đường dẫn mới.

Prepare v2 chỉ khởi tạo templates còn thiếu và tạo proposal manifest mới, không ghi đè manifest hiện có kể cả --force. Đọc --help trước dùng --output trong outputs/. Không chạy initializer để “cập nhật” dataset đã freeze.

## Cần bổ sung để đóng G04

Footage phát triển và test mới độc lập theo session; roster thật hai đội; landmarks mặt sân đã xác minh; labels đã review cho từng stat và hard negatives; rule applicability/protocol được duyệt; split/provenance/lock. Mục tiêu thu thập ≥50 shots, ≥30 rebound positives, ≥30 assist positives, không nhân bản pha cho đủ số.
