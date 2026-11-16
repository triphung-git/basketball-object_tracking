# Dataset v2 — bàn giao công cụ, chưa data-ready

Ngày 2026-11-02. Scope: MVP automatic PRA. **Task04 IN_PROGRESS** theo quyết định người dùng: bàn giao công cụ, ghi rõ footage/roster/labels/rules đang chờ.

## Inventory thực tế

| Thành phần | Số lượng/trạng thái |
|---|---|
| Video manifest v2 | 7 file gốc hiện có; không có footage hai đội mới được duyệt |
| Roster | 0 player, 0 team; chỉ header |
| shots / rebounds / passes / assists | 0 row từng bảng, 0 approved |
| player_positions / identities / ball_control | 0 row từng bảng, 0 approved |
| coverage / reviews | 0 row từng bảng |
| Rule applicability / protocol | pending / draft |
| Split | draft; calibration=clip02 theo filename; test v2 rỗng |
| Holdout v1 | 4 video được bảo vệ nguyên trạng; không dùng tuning |
| External lock | Chưa tạo |

Không còn sáu player mẫu bị hiểu nhầm thành roster thật. Không sao chép 10 shot v1 thành labels PRA v2. Đã bổ sung ba template positions/identities/control còn thiếu. Cả 9 bảng annotations có header chuẩn schema 2.0.1.

Manifest giữ hash media và ID theo nguồn hiện có. Metadata session/camera cũ là grouping đề xuất, **provenance_status=pending**, source_group=unknown; chưa xác minh khác phiên/khác pha. Clip03 không còn bị tự khẳng định “streetball dusk / ánh sáng không đủ” từ filename. Video mới giữ unknown provenance cho đến khi review; filename không chứng minh eligibility. Không sửa manifest/splits/labels v1.

## Kết quả gate

Bằng chứng máy đọc: [v2-handoff-validation.json](../../codebase/outputs/acceptance-20261102/v2-handoff-validation.json), [gate-checks.json](../../codebase/outputs/acceptance-20261102/gate-checks.json).

| Gate | Kết quả | Ý nghĩa |
|---|---|---|
| Structural | PASS | Header/media/hash/refs của scaffold hợp lệ |
| Tooling-ready | true, CLI exit0 | Công cụ dùng được với scaffold hiện tại |
| Data-ready | false, CLI exit2 | Chưa có GT/roster/rules/protocol/coverage/test đủ điều kiện |
| Locked-ready | false, CLI exit3 | Split draft, không có data lock |

Validator không tạo approval và không chứng nhận chuyên môn của reviewer. Cỡ mẫu ≥50 shots/≥30 REB positives/≥30 AST positives là mục tiêu thu thập, chưa đạt; các gate pilot tối thiểu không thay nghiệm thu dataset đầy đủ.

## Công cụ và kiểm thử

prepare_dataset_v2.py giữ metadata đã biên tập theo hash, tạo IDs mới theo hash, không ghi đè manifest ngay cả khi --force. Output proposal phải nằm trong data/v2 hoặc outputs; initializer không được thay nhãn đã tồn tại hoặc dataset locked.

validate_dataset_v2.py kiểm tra header kể cả bảng trống, finite/in-bounds time, roster/team, event refs/chronology, source hash/path, review ledger, coverage, split leakage theo session/camera/source_group/hash và bảo vệ holdout v1. Approved rebound/assist không được phụ thuộc shot/pass chưa duyệt để đạt data gate. Protocol và provenance chưa duyệt giữ data-ready=false.

Khi split locked, lock.json phải hash đủ manifest/roster/rules/splits và cả 9 annotations. Thiếu hoặc sửa file sau lock bị lỗi. Không nhúng self-hash trong splits.

Bộ test tổng hợp bao gồm v1, pipeline và dataset; xem [biên bản nghiệm thu](task03-task04-acceptance.md). Fixtures synthetic độc lập kiểm tra cả trường hợp hợp lệ đạt locked gate lẫn negative cases; không đưa vào dataset thật. Validator chưa phải evaluator task13.

## Phần còn chờ và việc tiếp theo

1. Footage hai đội đủ chuỗi pass→shot→control; made/miss, rebound tranh chấp, assist positives và hard negatives. Footage development/test khác session, có nguồn/provenance và quyền sử dụng.
2. Roster thật, team/số áo và evidence identity; các điểm **trên mặt sân** để kiểm chứng mapping.
3. Người review labels/coverage từng pha theo PTS; không tự ghi approval thay người dùng.
4. Chốt rules áp dụng giải 3x3 và protocol. Diễn giải FT assist sai đã sửa theo nguồn trong [rule profile](../specs/rules-v2.md); chưa duyệt cả manual cho giải.
5. Chốt schema extension cho FT-series/foul/possession, provenance grouping, split và external lock trước benchmark.

Chỉ phần kỹ thuật độc lập của task05/06 có thể đề xuất tiếp; chưa nghiệm thu geometry/team/identity/PRA trên dataset hiện tại. Xem [handoff task05–06](../handoffs/task04-to-task05-06.md).
