# Packet review pha ghi điểm Việt Nam – Tonga — 2026-11-06

Cập nhật 2026-11-07: [đã nhận review 34 clip và chốt toàn bộ target conflicts](task08-scoring-review-intake-20261107.md), không còn case chờ đội/người ném đối lập. Nội dung pending/0 nhãn bên dưới là snapshot lịch sử lúc chuẩn bị packet; không ghi đè manifest hoặc raw export. Latest intake nằm trong `outputs/task08-scoring-intake-20261107/adjudicated-v3/`.

**Sửa phát video cùng ngày:** người dùng xác nhận đang mở trong preview VS Code/Codex. Đã thêm `Mo-review-bang-trinh-duyet.cmd` để mở đúng HTML bằng Chrome/Edge cài sẵn, không qua shell interpolation hay đổi default browser. Không encode lại media hoặc thay manifest; SHA manifest vẫn `153eb12d779add28dff51d38c873107913d2eb1955bd36d63cfff2da9a5ce665`, nên binding JSON/localStorage trong cùng browser được giữ. Nếu chuyển từ preview sang browser, cần export/import JSON để chuyển nhãn giữa hai storage context. Đã kiểm tra lại 27 thao tác UI và phát/seek cả 34 clip trên Chrome; thêm kiểm tra lỗi media, hướng dẫn và retry tại `ui-qa/playback-fix-results.json`. Chưa xác minh cấu hình codec của preview, không kết luận clip bị mất hoặc hỏng chỉ từ thông báo cũ.

Đã chuẩn bị công cụ quét scoreboard, cắt clip có provenance và trang review để kiểm tra khả năng quan sát ở những pha tăng điểm. [Trang review](../../codebase/outputs/task08-scoreboard-review-20261106/review.html), [hướng dẫn](../guides/vietnam-tonga-scoring-review.md), [manifest](../../codebase/outputs/task08-scoreboard-review-20261106/review-manifest.json).

**34 candidate tăng điểm, 8 clip ưu tiên; tất cả pending user review.** Chuỗi điểm dự kiến đi từ Tonga–Việt Nam 0–0 đến 19–21, tổng mức tăng 40 điểm qua 28 mốc +1 và 6 mốc +2. Đây là thống kê của chuỗi scoreboard đã chuẩn bị cho review, không phải kết quả engine tự nhận made shots hoặc bằng chứng không bỏ sót sự kiện.

## Nguồn và phương pháp

- Nguồn local: `codebase/assets_test/vietnam-tonga.mp4`, 41432 frame, 1920×1080, 30 FPS, SHA-256 `1443c1d263c8037a5684f3dbc0ef9216beb5097d9a47c4c1c9b94d1363e26865`.
- Quét toàn bộ timeline ở 1 Hz, 1382 mẫu. Vùng scoreboard truyền hình tại góc trái dưới có thứ tự Tonga rồi Việt Nam; ô điểm được tách khỏi ô fouls và đồng hồ. ROI chỉ áp dụng cho đúng nguồn này.
- EasyOCR CPU dùng weights đã có, `download_enabled=False`; không tải thêm weights, không gọi cloud/upload, không training hoặc thay detector.
- Scoreboard font có trường hợp 7 đọc thành 11, 8 thành 6, cạnh panel thành tiền tố. Font calibration được agent đối chiếu ảnh nguồn và ghi tường minh trong metadata. Các mẫu này là annotation assistance, không phải kết quả inference độc lập.
- Khi cộng điểm, ô Việt Nam chuyển đỏ và có thời gian chỉ hiện một phần số. Phải bỏ các mẫu nền không ổn định thay vì gán thành 0. Cache hình số ban đầu quá rộng cũng gây lẫn 6/8; đã thu hẹp và giữ các run cũ để audit.
- `scan-v4` là lượt OCR đầy đủ cuối: 253 fresh OCR calls. `scan-final` là dẫn xuất từ v4: thêm đối chiếu font Việt Nam 15 ở frame nguồn 995s để khôi phục 5 reading unresolved, không ghi đè kết quả quét trước. Xem `scan-final/repairs.json`. Không suy số theo quy tắc tăng đơn điệu để lấp khoảng trống.
- Yêu cầu ít nhất 2 mẫu liên tiếp cùng cặp điểm trước khi tạo trạng thái; tăng đúng một đội +1/+2 tạo candidate. Các khoảng mờ/OCR/gap phải xử lý trước export; không chia tùy ý một mức tăng gộp thành nhiều cú ném.

Artifacts tại `codebase/outputs/task08-scoreboard-review-20261106/`: các run quét ban đầu, `scan-v2`, `scan-v3`, `scan-v4`, `scan-final`; ảnh `states-contact-*`, `gap-contact.jpg`, `plays-survey-*` phục vụ agent đối chiếu. Chỉ `review.html` và manifest hiện hành là packet bàn giao, không nhầm các scan trung gian thành nhãn đã duyệt.

## Media và review

Mỗi clip bắt đầu 12 giây trước mẫu điểm cũ cuối cùng, kết thúc 5 giây sau mẫu điểm mới đầu tiên, có thể chồng lấn với clip liền kề. Cắt tại frame thực, giữ kích thước gốc 1080p và 30 FPS, encode H.264 CRF21; không phóng to giả chi tiết và không giữ audio. Mỗi clip có 6 ảnh từ nguồn để điều hướng, scoreboard trước/sau, hash video và mapping PTS về nguồn. Tất cả clip được decode lại ngay khi xuất để kiểm số frame và PTS.

Nhóm ưu tiên: `play_001`, `play_008`, `play_015`, `play_021`, `play_023`, `play_027`, `play_028`, `play_034`. Chọn từ ảnh khảo sát để có hai đội, mức tăng 1/2, tình huống gần rổ, ném phạt và pha cuối trận; không khẳng định toàn bộ chuỗi bóng rõ trước người dùng review. `play_015` có hình ảnh ném phạt trong survey; nhãn shot kind vẫn chưa tự điền để reviewer xác nhận.

Trang review có lọc 8 ưu tiên / tất cả / chưa review, video giảm tốc và ±1 frame, đánh dấu release/outcome tùy chọn, chọn người ném từ roster đã duyệt, autosave và import/export JSON ràng buộc source/manifest SHA. Không yêu cầu vẽ bbox hoặc review lại batch trước. Các trạng thái không đủ bằng chứng được giữ riêng; không tự điền người ném, release, outcome hoặc auto-confirmed event.

## Hướng tiếp theo sau review

1. Chọn các pha live có bóng nhìn rõ, tách field goal/FT và camera. Đánh dấu cửa sổ quan trọng quanh release và rim/outcome; giữ các pha bị che/cut thành nhóm khó riêng, không loại khỏi báo cáo coverage một cách im lặng.
2. Freeze mẫu và nhãn được người dùng duyệt; chạy detector hiện tại trên các cửa sổ này, recognition không đọc scoreboard hoặc GT. Đo riêng candidate recall và bóng được chọn đúng tại release/rim; lỗi actor/value cũng tách riêng.
3. Nếu raw detector thấy đúng nhưng association bỏ/chọn sai: sửa motion/actor context, tách role cầu thủ khỏi uncertainty OCR, kiểm lại một bóng observed hoặc không có, phân biệt predicted. Không buộc bóng luôn đi theo tay sau khi đã chuyền/ném.
4. Nếu thiếu raw candidate ở vùng rổ: thử xử lý ROI nguyên độ phân giải, kiểm camera/rim geometry và thời gian lấy mẫu. Chỉ đề xuất fine-tune khi có ảnh lỗi, nhãn sạch, split theo nhóm và recipe; chưa có quyền training từ packet này.
5. Với identity: lấy số áo khi rõ ở trước cú ném, duy trì mapping nhân quả đến release; không dùng scoreboard hay kết quả cuối video để suy ngược người ném. Không đủ bằng chứng thì unknown.
6. Bổ sung một nhóm nhỏ hard negatives như miss/rim bounce/replay trước đo precision made/miss. Mẫu tăng điểm đơn thuần không đủ để nghiệm thu points, rebounds hoặc assists.

Không đổi các gate đã duyệt hoặc tuyên bố Task07/08 DONE. Chưa có inference detector mới, benchmark realtime hoặc số liệu chất lượng ở cửa sổ ghi điểm trong đợt chuẩn bị này. Chờ bản review để xác định ưu tiên sửa bằng dữ liệu thực tế.

## Tái lập

Từ workspace root, dùng outputdir mới:

```powershell
codebase/.venv/Scripts/python.exe codebase/scripts/prepare_scoreboard_review.py scan --output-dir codebase/outputs/scoring-review-new/scan
codebase/.venv/Scripts/python.exe codebase/scripts/prepare_scoreboard_review.py repair-font --input-scan codebase/outputs/scoring-review-new/scan --output-dir codebase/outputs/scoring-review-new/scan-final --font-seed 995:VIE:15
codebase/.venv/Scripts/python.exe codebase/scripts/prepare_scoreboard_review.py candidates --output-dir codebase/outputs/scoring-review-new/scan-final
codebase/.venv/Scripts/python.exe codebase/scripts/build_scoreboard_review.py --scan-dir codebase/outputs/scoring-review-new/scan-final --output-dir codebase/outputs/scoring-review-new --priority-ids play_001,play_008,play_015,play_021,play_023,play_027,play_028,play_034
```

Kết quả kiểm tra media/browser cuối lưu tại `packet-integrity.json` và `ui-qa/browser-results.json` trong packet; xem các file này trước khi coi thao tác chuẩn bị/bàn giao đã hoàn tất. Không dùng fixtures UI như nhãn thật.

## Kiểm tra bàn giao đã chạy

- 34/34 clip được export và decode đầy đủ: **21540 frame**, tổng thời lượng 718 giây; mỗi clip 19–30 giây, tổng file video 337944825 byte. Tám clip ưu tiên dài tổng cộng **165 giây (2 phút 45 giây)**.
- 34 clip giữ 1920×1080/30 FPS, PTS bắt đầu 0, mapping khớp frame nguồn; sai số PTS lớn nhất đo được 0 giây. Có 68 ảnh scoreboard và 204 ảnh nguồn điều hướng, đủ file và đúng kích thước.
- **27 browser checks PASS** trên Chrome cài sẵn qua Playwright, mở trực tiếp bằng `file:`: phát H.264 thật, ±1 frame, giảm tốc, lọc, đánh dấu thời gian, autosave/reload, export/import đúng packet, từ chối sai source/mốc ngoài clip và mobile không tràn ngang. Không có JavaScript error. Đã xem screenshot desktop; screenshot mobile lưu cùng QA.
- Browser bundle của Playwright hiện tại không có executable tương ứng; đã dùng Chrome cài sẵn để hoàn thành kiểm tra, không tải/cài browser hoặc dependency. Bản JSON synthetic kiểm thử chỉ nằm trong `ui-qa/synthetic-browser-export.json`, được đánh dấu rõ và đã xóa khỏi localStorage của context QA; không nạp thành nhãn thật.
- 19 file dataset/labels đã khóa, canonical control GT, 11 source/config/test file theo snapshot Task07B và weights EasyOCR giữ nguyên hash. Các script mới đã kiểm tra cú pháp; không chạy lại toàn bộ suite core vì không sửa engine, thay vào đó kiểm tra trực tiếp toàn bộ media và UI mới.
- **0 nhãn người dùng mới được duyệt trong lượt này**, 34 candidate pending; không có detector inference mới hoặc metrics made/miss. Trạng thái kiểm tra chỉ nghiệm thu công cụ/packet review.
