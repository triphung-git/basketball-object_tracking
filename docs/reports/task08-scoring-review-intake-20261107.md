# Tiếp nhận review ghi điểm Việt Nam – Tonga — 2026-11-07

**Đã nhận đủ 34 review và đã chốt toàn bộ 5 xung đột liên kết target bằng xác nhận người dùng. Có 34 bản ghi nhất quán, không còn case chờ đội/người ném đối lập.** Xác nhận cuối: play_009 Tonga #11; play_024 Tonga #9; play_034 Việt Nam #6, ném trong trận. Không sửa file người dùng, packet/manifest hoặc nhãn đã khóa. Chưa chạy detector mới hoặc nghiệm thu Task07/08.

Nguồn trả về: `codebase/outputs/task08-scoreboard-review-20261106/vietnam-tonga-scoring-review.json`, SHA-256 `1ca130edea0c9b6862fd210476256dba8dfda05dbf80baa3dda095313918a696`. Manifest khớp SHA `153eb12d779add28dff51d38c873107913d2eb1955bd36d63cfff2da9a5ce665`; source khớp SHA `1443c1d263c8037a5684f3dbc0ef9216beb5097d9a47c4c1c9b94d1363e26865`. Ngày export trong file được giữ nguyên; ngày tiếp nhận là 2026-11-07.

Artifacts đầu tiên tại `codebase/outputs/task08-scoring-intake-20261107/` giữ nguyên 5 xung đột; adjudicated-v2 giữ checkpoint 31/3 để audit. **Dẫn xuất hiện hành:** [adjudicated-v3/summary.json](../../codebase/outputs/task08-scoring-intake-20261107/adjudicated-v3/summary.json), [events-reviewed.json](../../codebase/outputs/task08-scoring-intake-20261107/adjudicated-v3/events-reviewed.json), [subset nhất quán](../../codebase/outputs/task08-scoring-intake-20261107/adjudicated-v3/events-consistent-subset.json).

## Kết quả tiếp nhận

| Hạng mục | Kết quả |
|---|---:|
| Người dùng đã review | 34/34 |
| Kết luận action rõ / thiếu một phần | 33 / 1 |
| Ball visibility clear / partial / unknown | 28 / 4 / 2 |
| Loại cú ném trong file gốc, chưa giải quyết target | 25 field goal / 9 FT |
| Loại cú ném sau xác nhận, bản dẫn xuất | 26 field goal / 8 FT |
| Xung đột target ban đầu / còn chờ | 5 / 0 |
| Metadata nhất quán sau xác nhận | 34 |
| Shooter đã khai và nhất quán với target | 32 |
| Chưa khai shooter | 2, play_002 và play_005 |
| Có cả release và basket timestamp ở bản dẫn xuất | 13; file gốc có 14, bỏ một cặp của pha Tonga bị gán sang pha Việt Nam |
| Cặp timestamp thuộc target không còn xung đột | 13 |
| Pha action rõ + bóng clear + có cả hai mốc + target nhất quán | 10 |
| Chưa có cặp timestamp | 21, hợp lệ vì các ô này là tùy chọn |
| Bbox bóng kiểm chứng / negative events | 0 / 0 |

Các con số này là thống kê nhãn và tính nhất quán dữ liệu, **không phải accuracy/recall của model**. `confirmed_clear` không tự chuyển ball visibility partial/unknown thành clear. `play_014` giữ confirmed_partial và ghi chú thiếu lúc bóng vào rổ; không tự điền mốc outcome. Hai shooter null được giữ null.

## Các clip có nhiều pha và quyết định của người dùng

| Clip mục tiêu | Vấn đề | Trạng thái |
|---|---|---|
| play_009: Tonga 4–6→5–6 | File ghi Việt Nam #1, có thể đang chọn pha liền trước | **Đã xác nhận Tonga #11** |
| play_024: Tonga 12–15→13–15 | File ghi Việt Nam #13, có thể đang chọn pha liền trước | **Đã xác nhận Tonga #9** |
| play_027: 15–15→17–15 | File ghi Việt Nam #1 và mốc pha kế tiếp | **Đã xác nhận** dùng Tonga #18, release 985,866667s, basket 987,233333s nguồn |
| play_028: 17–15→17–17 | File ghi Tonga #18 và mốc pha trước | **Đã xác nhận** dùng Việt Nam #1, release 994,033333s, basket 995,300000s nguồn |
| play_034: 19–20→19–21 | File ghi Tonga #18/FT và mốc 0,566667–2,700000s thuộc pha đầu clip | **Đã xác nhận Việt Nam #6, field goal**; xóa cặp mốc pha Tonga trong bản dẫn xuất, không đoán mốc chính xác pha Việt Nam |

Việc cắt clip có chồng lấn làm một clip chứa nhiều pha. Đây là vấn đề liên kết nhãn với target, không phải bằng chứng model nhận sai cầu thủ. Không tính một pha xuất hiện ở hai clip thành hai lượt ghi điểm.

Toàn bộ xác nhận hiện hành được lưu riêng tại [resolutions-confirmed-v3-20261107.json](../../codebase/outputs/task08-scoring-intake-20261107/resolutions-confirmed-v3-20261107.json); file xác nhận cũ 027/028 giữ nguyên. Script lấy cả hai phép chuyển từ file gốc bất biến và giữ thời gian nguồn, sau đó đổi về giây local của clip đích. Không swap trực tiếp timestamp local vì hai clip có offset khác nhau. Ghi chú gốc của mỗi clip vẫn giữ tại clip đó. Với play_034, chỉ sửa shooter/shot kind theo người dùng và vô hiệu cặp mốc thuộc đối thủ; không tự gán 9,547s trong ghi chú thành timestamp đã duyệt chính xác.

Ảnh audit ba case vừa chốt: [play_009](../../codebase/outputs/task08-scoring-intake-20261107/play009-contact.jpg), [play_024](../../codebase/outputs/task08-scoring-intake-20261107/play024-contact.jpg), [play_034](../../codebase/outputs/task08-scoring-intake-20261107/play034-contact.jpg). Không cần hỏi lại các xác nhận này hoặc review lại toàn bộ 34 clip.

## Nhóm có thể chẩn đoán tiếp ngay

10 pha: `play_001`, `play_003`, `play_004`, `play_006`, `play_008`, `play_015`, `play_021`, `play_023`, `play_027`, `play_028`. Có 8 field goal và 2 FT theo nhãn người dùng; cùng trận đã exposure, không phải holdout.

[critical-windows-draft.json](../../codebase/outputs/task08-scoring-intake-20261107/adjudicated-v3/critical-windows-draft.json) lưu mốc và cửa sổ nguồn. Danh sách 10 cửa sổ giống v2 nên tái sử dụng 40 ảnh nguồn đã kiểm, ghi hash tại `adjudicated-v3/evidence-reuse.json`. Có 40 ảnh 1080p tại release−0,2s, release, basket, basket+0,2s; mapping PTS được kiểm tới 2µs. Đây là ảnh nguồn, không phải detector predictions hoặc bbox GT. Không tự biến mốc basket thành bằng chứng mọi frame trong cửa sổ đều thấy bóng.

Các ảnh tổng hợp hiện hành: [nhóm 1](../../codebase/outputs/task08-scoring-intake-20261107/adjudicated-v2/critical-moments-1.jpg), [nhóm 2](../../codebase/outputs/task08-scoring-intake-20261107/adjudicated-v2/critical-moments-2.jpg), [nhóm 3](../../codebase/outputs/task08-scoring-intake-20261107/adjudicated-v2/critical-moments-3.jpg).

## Quan sát nguồn và hướng ưu tiên

1. **Tách giai đoạn giữ bóng và bóng bay.** FT play_006 đổi bố cục camera từ người ném lên vùng rổ; cầu thủ không còn ở gần bóng khi bóng tới rổ. Không áp điều kiện bóng luôn sát bbox human trong flight. Cần giữ một bóng được chọn hoặc missing, với predicted có giới hạn và không dùng prediction-only để xác nhận điểm.
2. **Tách chế độ camera.** Play_015 là FT góc rộng, còn play_006 là góc gần/follow-shot. ROI theo một camera của đoạn development không đủ cho toàn trận. Cần nhận boundary/bố cục và xác minh rổ trước khi áp ROI; camera thay đổi không tự là lượt ném mới.
3. **Ưu tiên release/rim của các pha rõ.** Play_001/004/021/023/027/028 có góc rộng; play_003/008 có vùng tay và nhiều người sát rổ. Chạy cùng approved detector, tách raw candidate khỏi bóng tracker chọn để biết lỗi nằm ở detector, association hay context. Ảnh nguồn hiện tại chưa chứng minh tỷ lệ lỗi từng loại.
4. **Identity phải theo thời điểm release.** Dùng OCR/màu/track evidence trước hoặc tại release; không đọc nhãn người ném này vào runtime. Giữ actor/body evidence cho ball association ngay cả khi số áo chưa chắc, tránh regression của full crop guard đã đo ở Task07B.
5. **Sau baseline mới chọn can thiệp.** Candidate đúng bị bỏ → sửa association/gate. Thiếu candidate đúng → kiểm ROI/full-resolution crop và ảnh lỗi, rồi mới đề xuất dữ liệu/fine-tune riêng. Không đổi weights/train trong lượt tiếp nhận nhãn này.

Đây là chẩn đoán quan sát ảnh nguồn và kế hoạch đo, không phải kết luận đã sửa detector. Cửa sổ được chọn từ mốc người dùng nên phép đo tới đây là **conditional diagnostic**, không phải khả năng tự tìm shot trên video bất kỳ. Muốn đo ball IoU recall cần bbox thật ở một nhóm frame trọng yếu; muốn đo made/miss precision cần thêm miss/rim-bounce/replay negatives. Chưa đề nghị người dùng vẽ lại cả 34 clip.

## Kiểm thử và bàn giao

`15 tests PASS, 10 subtests PASS` cho importer: source/manifest binding, timestamp/frame mapping, thiếu mốc/shooter vẫn null, unknown/partial không lên clear, target conflict giữ riêng, duplicate JSON/nonfinite bị từ chối, explicit approval, swap hai chiều giữ nguyên source clock và không kế thừa timestamp đối thủ khi sửa target. Kiểm tra thực tế toàn bộ 34 hash clip và source trước tiếp nhận.

Lệnh từ workspace root:

```powershell
codebase/.venv/Scripts/python.exe codebase/scripts/ingest_scoring_review.py --review codebase/outputs/task08-scoreboard-review-20261106/vietnam-tonga-scoring-review.json --packet-dir codebase/outputs/task08-scoreboard-review-20261106 --output-dir codebase/outputs/scoring-intake-new --resolutions codebase/outputs/task08-scoring-intake-20261107/resolutions-confirmed-v3-20261107.json
codebase/.venv/Scripts/python.exe -m pytest codebase/tests/test_scoring_review_intake.py -q
```

Không ghi đè intake đã tồn tại, file gốc, manifest, canonical control GT hoặc split. Toàn bộ case chờ xác nhận đã được giải quyết; thiếu các mốc tùy chọn không bị lấp bằng suy đoán. [Handoff cho diagnostic tiếp theo](../handoffs/task08-scoring-review-to-critical-diagnostics-20261107.md). **Task07 IN_PROGRESS; Task08 TODO.**
