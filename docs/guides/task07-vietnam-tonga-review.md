# Review nhãn Vietnam–Tonga để nghiệm thu Task07

Cập nhật development:108ball samples và5passes đã review; người dùng đã xác nhận Việt Nam #6 và Tonga #11 ở hai khoảng xung đột. Canonical packet hiện hành là `codebase/data/matches/vietnam_tonga/reviewed-vt_development-v2.json`. **Không cần làm lại hai xác nhận hoặc nhập lại ball/pass.** [Full evaluation](../reports/task07-development-evaluation-v2-20261104.md) đã chạy và thất bại về ball/control/pass; report ghi một cảnh báo timestamp control/receive còn cần đối soát khi review tiếp. Validation packet vẫn chưa nhận. Hướng dẫn chung dưới đây dùng cho sửa nhãn có revision hoặc review đoạn tiếp theo; các phát biểu chưa có GT là snapshot lịch sử.

Roster và protocol đã được người dùng duyệt ngày2026-11-04. Không cần xác nhận lại hai phần này. Nhãn ball/control/pass chưa được review, nên chưa có real accuracy hoặc Task07 DONE.

## Mở đúng gói review

- [Development — parent05:00–05:30](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/review-development-final/review.html).
- [Validation cùng trận — parent02:45–03:15](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/review-validation-final/review.html).

Mở HTML bằng trình duyệt tại máy, giữ nguyên cây thư mục để video và ảnh tương đối tải đúng. Không cần upload. Các bản review72/62ảnh trước đó giữ làm lịch sử; bản cuối có108/94mẫu để có cơ hội đủ ít nhất60ball samples nhìn thấy. Nếu đã review bản cũ, giữ JSON đã xuất; có thể gộp theo source hash/frame_index để không mất nhãn đã làm.

Ảnh mẫu và video trong gói review lấy từ nguồn, không có overlay prediction. Các bbox gợi ý màu vàng chỉ từ HSV, có thể sai và đều được đánh dấu uncertain. Chúng không phải GT hoặc detector predictions. Không dùng video output của pipeline làm đáp án nhãn.

## Ball samples

1. Dùng “Mẫu trước/sau” để xem từng ảnh. Bấm “Video tới mẫu” và ±1frame nếu cần xem chuyển động quanh đó.
2. Chọn gợi ý đúng hoặc kéo bbox sát bóng trên ảnh. Coordinates tự quy về frame gốc1920×1080.
3. Bấm “Bóng nhìn thấy — duyệt bbox”, hoặc “Bóng bị che/ngoài khung”. Nếu không thể kết luận, giữ uncertain; không đánh visible chỉ để đủ mẫu.
4. Reviewer phải kiểm tra thực tế, không chỉ bấm duyệt tất cả gợi ý. Unknown/miss của model không phải lý do tự loại GT khó.

## Control và passes

Phần này chưa có nhãn được xác nhận. Công cụ cho nhập intervals và events sau khi xem30giây nguồn:

- Control: chọn start/end ở thời điểm thật sự kiểm soát, chọn đúng đội/cầu thủ từ roster. Có thể dùng nút lấy thời gian từ video và ±1frame; không lấy game clock trên scoreboard làm source time.
- Pass: nhập release/receive, chọn passer/receiver. Ghi toàn bộ completed passes đủ nhìn rõ trong coverage, không chỉ các pha model tìm thấy. Phân biệt dribble, shot→recovery, loose/contested và deflection. Các tình huống không đủ evidence phải giữ uncertain, không ép nearest-player thành GT.
- Có thể sửa JSON trong trang rồi bấm “Áp dụng JSON sửa” để bổ sung notes/uncertain hoặc điều chỉnh records. Không để overlapping control intervals hoặc IDs trùng. Với các trường hợp không có pass, coverage vẫn phải được xem để chấm false positives.

Với30giây footage, không cần gán danh tính cho từng frame của cả trận. Tuy nhiên, cần review đủ control/pass trong vùng được chấm; một vài pha được chọn riêng không chứng minh recall toàn coverage.

## Xuất nhãn

Nhập reviewer và xác nhận đã xem toàn bộ coverage, rồi bấm “Xuất packet đã review”. Trang chỉ cho xuất approved khi mọi ball sample đã được xem. Control/pass vẫn cần người review bổ sung đầy đủ; UI không tự biết có bỏ sót pha hay không. Xuất draft nếu chưa làm xong.

Lưu hai file đã review vào workspace, ví dụ:

```text
codebase/data/matches/vietnam_tonga/reviewed-vt_development.json
codebase/data/matches/vietnam_tonga/reviewed-vt_validation.json
```

Báo đường dẫn file đã lưu để agent tiếp tục đánh giá. Không cần gửi lại video/roster. Nếu chưa đủ60visible ball samples hoặc5GT completed passes trong đoạn validation, không bịa nhãn hoặc đổi ngưỡng; sẽ bổ sung mẫu/đoạn30–60s phù hợp từ nguồn đã cho phép và ghi revision/exposure.

## Sau khi có GT đã review

Agent chạy evaluator trên raw automatic outputs trước sửa tay, dùng profile [đã duyệt](../../codebase/configs/evaluation/task07_vietnam_tonga.json): ball recall≥90%, strict control≥90%, strict pass precision≥95% và recall≥90%, PTS≤2µs và integrity guards. N/A/thiếu mẫu không được PASS. Profile kiểm tra đúng source và từ chối synthetic/draft GT.

Nếu chưa đạt, report phải ghi đúng failure và tiếp tục cải thiện trên development; không tự hạ ngưỡng, không lấy nhãn làm recognition input hoặc đổi corrections thành auto results. Hai đoạn cùng trận chỉ phục vụ pilot, không phải đánh giá tổng quát theo trận độc lập.
