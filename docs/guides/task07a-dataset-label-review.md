# Review pilot nhãn detection — Task07A dataset-first

Cập nhật sau review 40 frame: [đối soát và thử nghiệm](../reports/task07a-reviewed-feedback-20261105.md). Người dùng đã xác nhận bbox đầu gối ở `pilot_0017` là nhầm; tiếp tục bằng cách **Nạp file** [draft v2 giữ nguyên tiến độ 40 ảnh](../../codebase/outputs/task07a-reviewed-feedback-20261105/draft-task07a-pilot-corrected-v2.json) vào trang sửa bbox phía dưới. File gốc được bảo toàn. Còn319ảnh unreviewed, không cần review lại40ảnh đã làm.

[Preview đối chiếu 40 ảnh](../../codebase/outputs/task07a-reviewed-feedback-20261105/final-preview/review.html) là trang xem thử nghiệm, không phải trang sửa nhãn. Đỏ=raw candidates, xanh lá=nhãn đã duyệt, cyan=tối đa một bóng được chọn. Raw có thể có nhiều candidate; đầu ra **bóng thi đấu** chỉ được tối đa1hoặc missing. Không ép bbox theo người hoặc bỏ bóng bay chỉ vì nằm ngoài footprint mặt sân trong ảnh. Bộ lọc mới vẫn bỏ sót/chọn sai, chưa promote; full regression269tests PASS không thay nghiệm thu accuracy.

Ngày2026-11-05. Người dùng đã duyệt QA/dataset preparation, **chưa duyệt train, đổi weights hoặc chi phí**. Đây là nhãn huấn luyện detection, khác với control intervals/pass GT củaTask07. Không cần nhập roster hoặc control/pass vào gói này.

## Mở đúng trang

- [Pilot359frames — trang sửa bbox](../../codebase/outputs/task07a-dataset-first-20261105/pilot-candidate/model-review/review.html).
- [Ảnh/nhãn dataset gốc — QA27samples](../../codebase/outputs/task07a-dataset-first-20261105/original-image-qa/review.html).

Mở HTML tại máy, giữ nguyên cây thư mục. Không upload hoặc chạy server. Pilot cùng nguồn Việt Nam–Tonga, lấy từ6đoạn60s; tất cả split vẫn unassigned, không phải test độc lập. Các bbox gợi ý có nhiều false positives; số lượng bbox không phải accuracy.

Nên review10–20ảnh đầu cùng một số ảnh cận cảnh/background trước để phát hiện bất đồng tiêu chuẩn, rồi tiếp tục theo batch. Không cần làm359ảnh trong một lần. Bấm “Xuất draft” để lưu tiến độ, dùng “Nạp file” để mở lại packet ở lần sau.

## Tiêu chuẩn nhãn làm việc v1

Áp dụng nhất quán và ghi nhận chỗ chưa chắc trước khi xuất packet approved:

- **ball:** bóng rổ thật nhìn thấy trong ảnh, kể cả bóng trên tay trọng tài hoặc bóng thật ngoài phần sân thi đấu. Không gán cho hình bóng trên poster, logo hay scoreboard. Chọn active match ball là nhiệm vụ tracking, không tạo nhãn mâu thuẫn bằng cách bỏ một quả bóng thật chỉ vì nằm ngoài sân. Khi bóng hoàn toàn bị che/ngoài ảnh, không vẽ bbox suy đoán.
- **human:** người thật có thể phân biệt được, gồm cầu thủ, trọng tài/staff và người khác nhìn rõ; không gán hình người in trên poster. Không suy đoán từng người trong cụm khán giả quá nhỏ/không rõ. Ghi lại các trường hợp crowd/policy chưa thống nhất để QA, không ép model guesses thành nhãn.
- **rim:** bbox phần vành rổ/lưới nhìn thấy, không gộp toàn bộ bảng rổ hoặc cột. Nếu gặp nhãn cũ dùng phạm vi khác, ghi policy discrepancy để đối soát, không trộn hai cách vào dataset mới một cách im lặng.
- Bbox bám vật thể ở mức nguồn cho phép; không vẽ thêm phần bị che không nhìn được. Chỗ không thể kết luận thì bỏ qua ảnh với lý do, tránh tạo nhãn sai. Không bỏ ảnh chỉ vì model miss hoặc vì đó là tình huống khó cần học.

Đây là policy đề xuất cho vòng pilot, cần được reviewer xác nhận; dataset cũ vẫn phải QA trước khi trộn/train theo policy này. Nhãn human/crowd và extent củarim cần kiểm tra consistency khi mix dữ liệu cũ/mới. Đánh dấu đã đọc policy không tự chứng minh mọi bbox đúng.

## Thao tác trên từng ảnh

1. Bấm **“Nạp gợi ý cho ảnh này”** nếu muốn dùng model làm điểm bắt đầu. Gợi ý không tự được duyệt; có thể vẽ từ đầu.
2. Chọn class rồi kéo bbox trên canvas. Bấm dòng bbox trong danh sách để chọn, dùng “Xóa bbox đang chọn”, rồi vẽ lại nếu cần sửa. Xóa các detection trên poster/khán đài không phải vật thể mục tiêu; bổ sung bóng thật model bỏ sót.
3. Review cả3classes, không chỉ ball. Ảnh không có bóng vẫn có thể có human/rim cần gán; “Không nhìn thấy bóng” không có nghĩa toàn ảnh là empty negative.
4. Chọn loại cảnh và visibility. “Bóng nhìn thấy” phải có bboxball; “Không nhìn thấy bóng” không được có bboxball. Nếu còn uncertain, dùng “Bỏ qua ảnh” và ghi lý do thay vì xuất nhãn chắc chắn.
5. Tick đã kiểm tra đủ nguồn rồi **“Duyệt ảnh”**. Thao tác sửa/nạp/xóa bbox đưa ảnh về unreviewed. Có thể dùng browser zoom hoặc mở ảnh gốc để kiểm tra bóng nhỏ; tọa độ được lưu theo1920×1080.

Canvas không có chức năng kéo resize box có sẵn: chọn/xóa/vẽ lại. JSON editor cho phép sửa nâng cao; importer kiểm tra các trường source/ảnh/PTS cố định. Không sửa source metadata để đổi ảnh hoặc chia split.

## Lưu và xuất

- Xuất draft khi chưa hoàn tất. Giữ filename/version rõ ràng để không mất tiến độ.
- Để xuất reviewed packet: mọi ảnh phải approved hoặc skipped có lý do, có ít nhất một ảnh giữ lại, reviewer không rỗng và xác nhận policy. Cần QA việc bỏ qua nhiều case khó, không coi packet approved là đạt đủ coverage tự động.
- Có thể lưu file đã xuất vào:

```text
codebase/outputs/task07a-dataset-first-20261105/reviewed-task07a-pilot.json
```

Trang chưa xuất YOLO labels và luôn để training_ready=false. Agent sẽ kiểm tra source/hash/bbox/visibility, thống kê nhóm ảnh được giữ/bỏ và split trước khi tạo training dataset. Approval nhãn không phải quyền khởi chạy training.

Lệnh kiểm tra packet sau khi review:

```powershell
codebase/.venv/Scripts/python.exe codebase/scripts/validate_task07a_pilot_review.py --reviewed codebase/outputs/task07a-dataset-first-20261105/reviewed-task07a-pilot.json --source-packet codebase/outputs/task07a-dataset-first-20261105/pilot-candidate/annotations-draft.json
```

## Điều kiện còn thiếu trước train

359frames đều cùng trận. Nếu đưa vào training, toàn nhóm nguồn phải được coi đã exposure; không dùng các đoạn cùng trận làm bằng chứng test độc lập theo trận. Cần nguồn khác để đánh giá tổng quát. Ngoài reviewed labels còn phải chốt cleanup dataset/splits cũ, policy consistency, checkpoint compatibility, recipe và tài nguyên/chi phí.

Trang review đã qua JavaScript syntax và bbox/visibility guard checks; chưa kiểm thử thao tác end-to-end bằng trình duyệt. Nếu có lỗi UI, giữ packet đã tải trước khi đóng trang để bảo toàn tiến độ.
