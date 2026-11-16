# Review các pha tăng điểm Việt Nam – Tonga

Packet ngày 2026-11-06: [mở trang review](../../codebase/outputs/task08-scoreboard-review-20261106/review.html).

## Bạn cần làm

1. Trong **File Explorer**, mở thư mục packet rồi nhấp đúp **`Mo-review-bang-trinh-duyet.cmd`** để mở trang bằng Chrome/Edge bên ngoài IDE. Không dùng preview trong VS Code/Codex để phát video. Hoặc mở Chrome/Edge và kéo `review.html` vào cửa sổ trình duyệt. Giữ nguyên các thư mục `clips`, `frames`, `score-evidence` bên cạnh trang; không cần server hay API key.
2. Bắt đầu với bộ lọc **Ưu tiên review trước**: 8 clip `play_001`, `play_008`, `play_015`, `play_021`, `play_023`, `play_027`, `play_028`, `play_034`. Đây là mẫu để quyết định hướng phát triển trước, chưa phải toàn bộ dữ liệu nghiệm thu.
3. Xem clip, đối chiếu ảnh scoreboard trước/sau. Điểm hiển thị theo thứ tự **Tonga – Việt Nam**. Nhãn đội và số điểm trên tiêu đề là đề xuất từ scoreboard, chưa phải kết luận đã duyệt.
4. Chọn **Kết luận** và **Bóng ở các thời điểm quan trọng**. Nếu thấy rõ, chọn thêm loại tình huống và người ném. Không cần đoán số áo khi bị che hoặc vẽ bbox.
5. Có thể giảm tốc độ xuống 0,5×/0,25×, bấm ảnh để nhảy thời gian, hoặc dùng nút ±1 frame. Trong phần đánh dấu thời điểm, dừng ở frame bóng rời tay hoặc bóng qua rổ rồi bấm **Lấy frame hiện tại**. Mốc nhập là giây trong clip; manifest lưu offset để đổi về video gốc.
6. Bấm **Lưu và xem clip tiếp**. Khi xong, bấm **Tải bản review JSON** và gửi lại đường dẫn file `vietnam-tonga-scoring-review.json`. Có thể gửi sau 8 clip đầu, các clip còn lại giữ `pending`.

Không cần review lại batch bbox cũ. Nếu muốn xem thêm, chọn **Tất cả pha tăng điểm** để có 34 clip hoặc **Chưa review** để tiếp tục phần chưa làm. Bản tự lưu chỉ nằm trong trình duyệt hiện tại; file JSON tải xuống là bản bàn giao. **Nạp bản review** chỉ nhận đúng video và đúng manifest của packet, không nhập JSON từ batch frame cũ.

Nếu đã nhập nhãn trong preview IDE, hãy tải JSON ở preview rồi nạp file đó trong Chrome/Edge. Việc chuyển sang trình duyệt khác không tự chuyển localStorage. Nếu còn lỗi phát, mở mục **Không phát video / đang mở trong preview…?** ở đầu trang; thông báo mới có mã lỗi media để phân biệt truy cập file với giải mã. Launcher chỉ mở trình duyệt đã có, không cài phần mềm hoặc thay browser mặc định.

## Chọn kết luận thế nào

| Lựa chọn | Khi dùng |
|---|---|
| Có pha ghi điểm, hành động rõ | Thấy được pha tương ứng và có đủ hình ảnh để đối chiếu kết quả; vẫn đánh giá riêng độ rõ bóng |
| Có tăng điểm, hành động bị che/mất | Scoreboard tăng nhưng lúc ném hoặc bóng tới rổ bị cắt cảnh, che, mờ hay ngoài hình |
| Không phải pha ghi điểm / scoreboard sai | OCR/đối chiếu điểm sai, điều chỉnh điểm hoặc không có pha tương ứng; ghi chú lý do |
| Chỉ thấy replay, không tính lượt mới | Clip chỉ cho thấy phát lại của pha đã diễn ra, không có bằng chứng lượt live mới |
| Chưa chắc / cần thêm ngữ cảnh | Clip thiếu thời gian trước/sau hoặc bạn chưa xác định được |

Một clip có thể chứa thêm pha liền trước/sau vì thời gian cắt có chồng lấn. Chỉ review pha gắn với **cặp điểm trước → sau** của clip; không tính lại mọi lần bóng vào trong clip đó. Replay/cận cảnh có thể xuất hiện bên trong clip; đừng xác nhận lượt mới chỉ vì nhìn thấy replay bóng vào rổ.

Với ném phạt, chọn `Ném phạt`; không suy loại tình huống chỉ từ mức tăng 1 điểm. Với người ném không rõ, giữ `Không xác định`. Nếu không thấy frame bóng qua rổ, để trống mốc outcome, không lấy thời điểm scoreboard thay thế.

## Packet này dùng để làm gì

Video gốc là `codebase/assets_test/vietnam-tonga.mp4`, SHA-256 `1443c1d263c8037a5684f3dbc0ef9216beb5097d9a47c4c1c9b94d1363e26865`. Mọi clip giữ kích thước 1920×1080, 30 FPS, được encode lại nên không pixel-identical với nguồn, bỏ âm thanh. Sáu ảnh mỗi clip là ảnh JPEG từ nguồn dùng để điều hướng, không phải các frame được agent gán sẵn là release/basket.

Scoreboard truyền hình được dùng để **tìm mẫu cần review**. Thời điểm cập nhật điểm có thể trễ và không phải lúc bóng rời tay/qua rổ. OCR có kiểm tra nền nhấp nháy và mẫu font được agent đối chiếu thủ công; đây không phải benchmark OCR tự động hoặc nhãn người dùng đã duyệt.

Sau khi nhận review, agent sẽ chọn các đoạn có bằng chứng rõ, đối chiếu detector/association/identity tại những thời điểm quan trọng và phân loại nguyên nhân lỗi. Những pha không nhìn đủ vẫn giữ uncertain/partial, không biến thành nhãn chắc chắn. Tập chỉ gồm các pha tăng điểm chưa đủ để đo false positive/precision: cần bổ sung một số cú ném trượt, bật vành và replay trước khi nghiệm thu engine ghi điểm.

Không dùng scoreboard, các mốc review hoặc đáp án người ném làm đầu vào của engine nhận diện tự động. Cùng trận đã được xem và dùng development; packet không phải holdout độc lập. Task07 chưa DONE và Task08 chưa được nghiệm thu.
