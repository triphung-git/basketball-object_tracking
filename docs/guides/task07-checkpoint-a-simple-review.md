# Hướng dẫn review Checkpoint A

Đã nhận JSON batch này và [đối soát nhãn](../reports/task07-checkpoint-a-reviewed-20261105.md). Nếu tiếp tục UI, nạp [corrected subsetv2](../../codebase/outputs/task07-checkpoint-a-return-20261105/reviewed-subset-corrected-v2.json) để giữ hai xác nhận mới: bboxcầu thủ541s làhuman,542s uncertain. Không cần duyệt lại12frame/14crop; có thể để frame542s chờ đủ bằng chứng. Filemerged359samples dành cho agent xử lý dữ liệu, không nạp vào UI subset12frame.

Ngày 2026-11-05. Dùng [trang review run-08](../../codebase/outputs/task07-checkpoint-a-review-20261105-run-08/review.html). Batch này chỉ có **12 ảnh mới và14 crop số áo**; không yêu cầu duyệt lại40ảnh cũ hoặc toàn bộ359ảnh.

## Bắt đầu

1. Nếu đang mở bản giao diện cũ và có nhãn chưa tải xuống, **tải JSON ở bản cũ trước**. Sau đó refresh để mở giao diện mới và bấm **Nạp JSON** để tiếp tục. Chỉ refresh sau khi giữ được nhãn đang làm.
2. Mở `review.html` bằng Chrome hoặc Edge, giữ nguyên các thư mục `frames/`, `identity/`, `clips/` bên cạnh. Không cần chạy server.
3. Nhập tên hoặc tên viết tắt tại **Người duyệt**, tick xác nhận chính sách ở đầu trang.
4. Làm lượt **1. Ảnh thi đấu** trước, sau đó **2. Số áo và đội**. Có thể dừng giữa chừng và tải JSON bất cứ khi nào dữ liệu nháp hợp lệ.

Các ô số giúp chuyển thẳng đến mẫu: **trắng** chưa duyệt, **cam** cần xem lại, **xanh** đã duyệt hoặc đã xác nhận loại. Trạng thái chi tiết nằm bên phải. Tiến độ không tính “Cần xem lại” là hoàn tất.

## Lượt1 —12ảnh thi đấu

### Chọn cảnh

- **Thi đấu / ném phạt / check-ball:** giữ ảnh để gán nhãn. Cầu thủ đứng yên không tự có nghĩa ngoài phạm vi.
- **Cận cảnh / khán đài / graphics / chuyển camera:** chọn khi đã xác minh không đủ ngữ cảnh phục vụ subset thi đấu. Nhập lý do và bấm **Loại ảnh và tiếp**. Nhãn bbox của ảnh loại không được xuất thành dữ liệu huấn luyện.
- **Replay:** mở **Xem clip trước / sau frame này** và kiểm tra trước khi chọn; không kết luận replay chỉ từ ảnh đứng.
- Chưa rõ cảnh hoặc thiếu bằng chứng: dùng **Chưa chắc / để sau**. Mẫu vẫn được giữ, chưa coi là negative hoặc đã loại.

### Sửa bbox

Gợi ý mặc định được ẩn để dễ xem ảnh thật. Có hai cách:

**Cách nhanh:** bấm **Lấy gợi ý để sửa**. Toàn bộ gợi ý ball/human/rim trở thành bản nháp có thể chỉnh. Thao tác này không tự duyệt nhãn. Xóa đầu gối, vai, logo, người trên poster hoặc các bbox sai; bổ sung đối tượng bị thiếu.

**Vẽ từ đầu:** chọn **Bóng / Người / Rổ**, để chế độ **Vẽ bbox**, kéo từ góc này sang góc kia của vật thể.

Các thao tác sửa:

| Thao tác | Cách làm |
|---|---|
| Chọn bbox | Bấm dòng bbox trong danh sách hoặc chọn **Chọn / sửa** rồi bấm bbox trên ảnh |
| Di chuyển | Kéo bên trong bbox đã chọn |
| Đổi kích thước | Kéo một trong bốn góc của bbox đã chọn |
| Đổi class | Chọn bbox, dùng dropdown **Bóng / Người / Rổ** trong chế độ sửa |
| Xóa | Bấm **Xóa** cạnh dòng bbox, **Xóa đã chọn**, hoặc phímDelete khi không nhập liệu |
| Khôi phục thao tác | Bấm **Hoàn tác**; lịch sử hoàn tác chỉ tồn tại trong phiên đang mở |
| Xem chi tiết bóng nhỏ | Bấm **Phóng ảnh**, cuộn trong khung; bấm **Vừa khung** để trở lại |
| Đối chiếu detector | Chọn **Gợi ý: Chỉ bóng / Bóng + người + rổ**; bbox cam là prediction chưa duyệt |

Xanh lá là nhãn của bạn; xanh dương là bbox đang chọn. Tọa độ được lưu theo ảnh nguồn1920×1080, kể cả khi ảnh đang thu nhỏ/phóng.

### Chính sách cần kiểm tra

- **Bóng:** vẽ vừa phần nhìn thấy của bóng thật; không gán cho đầu gối, vai, logo hoặc hình bóng in trên poster. Không vẽ bbox suy đoán khi bóng bị che hoàn toàn. Bóng bay có thể nằm ngoài đường sân khi chiếu lên ảnh.
- **Người:** người thật phân biệt được, gồm cầu thủ, trọng tài/staff; không phải người trên poster. Không suy đoán từng người trong đám đông quá nhỏ/không rõ; ghi chú khi chưa chắc chính sách.
- **Rổ:** vùng vành rổ/lưới nhìn thấy, không gộp cả bảng hoặc cột rổ.
- Nếu nguồn có thêm bóng thật ngoài trận, ghi chú để phân biệt nhãn detection với active match ball; đừng âm thầm xóa vật thể thật chỉ để ảnh còn đúng một bbox.

Chọn **Có nhìn thấy / Không nhìn thấy** bóng. “Không nhìn thấy” yêu cầu không còn bbox ball, nhưng vẫn phải kiểm tra người/rổ. Ảnh không có bóng chưa có nghĩa toàn ảnh là empty negative.

Sau khi kiểm tra cả3classes, tick **Tôi đã kiểm tra đủ bbox bóng, người thật và rổ**, bấm **Duyệt và tiếp**. Bất kỳ thao tác sửa nhãn nào đều đưa ảnh về bản nháp và bỏ tick kiểm tra, cần xác nhận lại trước khi duyệt.

## Lượt2 —14crop số áo

Ảnh trái cho ngữ cảnh người, ảnh phải là vùng áo. Bấm ảnh để phóng. Mở clip khi cần kiểm tra người/track qua thời gian. Gợi ý OCR/đội nằm trong phần thu gọn, không được điền sẵn vào nhãn.

Điền theo thứ tự:

| Trường | Cách chọn |
|---|---|
| Ảnh cắt đúng người/vùng áo? | Chọn đúng, sai người, sai vùng, hoặc chưa chắc theo ảnh thực tế |
| Số áo có đọc được? | Phân biệt đọc rõ, chỉ thấy một phần, không đọc được, bị che, chưa chắc |
| Số áo thực tế | Nhập1–2chữ số khi đủ bằng chứng; giữ nguyên số0đầu nếu thấy rõ, để trống khi không rõ |
| Đội thực tế | Việt Nam hoặc Tonga theo bằng chứng; **Không rõ / mâu thuẫn** khi chưa xác định được |
| Vai trò | Cầu thủ, người ngoài như trọng tài/staff, hoặc chưa chắc |
| Track giữ cùng một người? | Chỉ chọn **Đúng** sau khi đối soát chuỗi/clip; nếu chưa đủ bằng chứng chọn đúng lựa chọn đó |

Roster hiện hành: Việt Nam=`team_a` (áo đỏ), Tonga=`team_b` (áo trắng). Màu/đội model đoán không phải nhãn. Không ép số đọc sai thành số gần nhất trong roster. Không điền số của người khác khi crop sai người/vùng.

Ví dụ quan sát đủ rõ: `Đúng crop → Đọc rõ → số2 → Việt Nam → Cầu thủ → track đã đối soát`. Đây chỉ là ví dụ thao tác, không phải nhãn được phê duyệt sẵn cho bất kỳ mẫu nào.

Nếu không thấy số: chọn visibility thích hợp và để số trống. Các trường chưa chắc có lựa chọn riêng. **Duyệt và tiếp** xác nhận bạn đã xem các trường đó; nhãn “Không rõ” không tự trở thành identity đã nhận đúng. Nếu chưa xem đủ nguồn, dùng **Chưa chắc / để sau**.

## Lưu, nạp lại và bàn giao

1. Trang tự lưu vào trình duyệt khi được cho phép; thông báo ở cuối trang cho biết trạng thái. Cùng trình duyệt và cùng đường dẫn có thể khôi phục sau refresh.
2. **Tải tiến độ JSON** để giữ bản trên máy, nhất là trước khi đóng trình duyệt, chuyển máy hoặc đổi vị trí thư mục. Tự lưu không thay thế file bàn giao.
3. File tải xuống có tên `task07-checkpoint-a-review.json`. Windows có thể thêm `(1)`, `(2)`; dùng đúng bản mới nhất.
4. Bấm **Nạp JSON** để tiếp tục. File phải thuộc đúng run-08; trang từ chối file sai manifest hoặc bị thay nguồn/prediction. Nạp file thay tiến độ đang mở, nên tải bản hiện tại trước nếu cần giữ cả hai.
5. Có thể bàn giao khi còn mẫu cần xem lại: giữ nguyên trạng thái đó và thông báo. Không đánh dấu tất cả đã duyệt chỉ để đủ số lượng.
6. Lưu JSON tại nơi dễ tìm, có thể ngay trong thư mục run-08. Giữ nguyên `review-manifest.json`. Gửi agent đường dẫn chính xác của **JSON đã tải**, không chỉ đường dẫn HTML hoặc manifest.

Trang sẽ báo lỗi nếu số áo sai định dạng, bbox trùng, visibility và bbox mâu thuẫn, hoặc thiếu người duyệt/chính sách đối với nhãn hoàn tất. Sửa trường báo lỗi rồi tải lại. Bản tự lưu giữ những thao tác đang sửa dở để tiếp tục, chưa biến chúng thành nhãn hợp lệ.

Phím←/→ chuyển mẫu theo lượt đang mở; khi con trỏ trong ô nhập/select, phím giữ chức năng nhập liệu. Có thể dùng nútTrước/Tiếp trên mọi thiết bị.

## Kiểm tra khi nhận lại JSON — dành cho agent

Từ workspace root, thay đường dẫn JSON bằng file người dùng trả lại:

```powershell
codebase/.venv/Scripts/python.exe codebase/scripts/validate_task07a_checkpoint_a_subset.py --reviewed codebase/outputs/task07-checkpoint-a-review-20261105-run-08/task07-checkpoint-a-review.json --manifest codebase/outputs/task07-checkpoint-a-review-20261105-run-08/review-manifest.json
```

Validator kiểm source/hash/scope/labels; việc pass không chứng minh mọi nhãn đúng, không tự duyệt train hoặc đóng Task07. Không dùng các file `ui-qa/synthetic-*.json` làm nhãn thật: đó là dữ liệu giả lập phục vụ kiểm thử giao diện.
