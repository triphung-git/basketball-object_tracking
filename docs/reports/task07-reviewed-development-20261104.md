# Task07 — tiếp nhận nhãn development đã review, 2026-11-04

**Đã xử lý tiếp bằng xác nhận người dùng:** Việt Nam #6 và Tonga #11 tại hai khoảng hỏi lại. Canonical GT v2 đã hợp lệ về cấu trúc; full evaluator đã chạy và trả `failed_criteria` (ball43.06%, control0%, pass recall0%). Đọc [kết quả v2 hiện hành](task07-development-evaluation-v2-20261104.md). Nội dung dưới giữ nguyên như lịch sử intake trước khi giải quyết overlap, không còn là yêu cầu chờ trả lời.

Đã nhận `codebase/outputs/task07-vietnam-tonga-segments-20261104/reviewed-vt_development.json`, reviewer `triphung`, review_status `approved`. **File chưa hợp lệ cho nghiệm thu đầy đủ vì control intervals trùng/chồng thời gian.** Giữ nguyên file người dùng; không suy diễn lại actor hoặc sửa thời gian từ prediction.

Nguồn nhãn SHA-256: `1d8b3cdd7a8496d946ab2b18d798e634ecf57feb3f7e634a5f8332a9c3da1ebb`. Source video hash, video_id, protocol version, IoU0.30 và pass tolerance0.25s khớp pilot đã duyệt. Cả108ball samples được đánh dấu reviewed;72mẫu visible/certain đủ điều kiện tính recall. Có5pass labels đã review. Đây là đoạn development đã tiếp xúc, không phải independent validation.

## Kết quả thành phần

Đối chiếu raw outputs `development-masked-delivery/`, kiểm tra hashes khớp `signoff-freeze.json`. Không chạy lại hoặc điều chỉnh recognition bằng nhãn này.

| Chỉ số chẩn đoán | Kết quả | Ngưỡng đã duyệt |
|---|---:|---:|
| Observed ball recall, IoU≥0.30 | 31/72 = 43.06% | ≥90% |
| Strict completed-pass recall | 0/5 = 0% | ≥90% |
| Strict completed-pass precision | N/A:0predicted passes | ≥95% |
| Strict control accuracy | Chưa đánh giá:control GT không hợp lệ | ≥90% |

Ball miss41/72; pass TP0/FP0/FN5. Precision N/A không được thay bằng100%.36ball samples còn lại bị loại theo nhãn uncertain hoặc không visible. Có đủ mẫu ball/pass tối thiểu riêng cho đoạn này, nhưng control cần sửa trước full acceptance. Dù sửa control, các ball/pass outputs hiện tại vẫn chưa đạt.

Evaluator đầy đủ đã thực sự chạy và từ chối packet với `Invalid or overlapping control GT` (exit1, không tạo evaluation directory). Phép đo phía trên dùng bản sao trong bộ nhớ chỉ giữ nguyên ball/pass, bỏ control khỏi phép đo thành phần. Không tạo GT approved mới, không áp acceptance profile để công bố overall PASS/FAIL. `acceptance_pass=null`, scope `partial_reviewed_development_ball_pass_only`.

Artifacts tại `codebase/outputs/task07-vietnam-tonga-segments-20261104/reviewed-development-intake-01/`:

- [Intake và danh sách xung đột](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/reviewed-development-intake-01/intake.json).
- [Metrics thành phần](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/reviewed-development-intake-01/partial-evaluation.json).
- [Log evaluator đầy đủ](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/reviewed-development-intake-01/full-evaluation-attempt.log).
- [Repair draft](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/reviewed-development-intake-01/repair-draft.json): chỉ bỏ6bản ghi trùng hoàn toàn, giữ ball/pass và các control khác; review_status trở lại draft để chờ sửa/xác nhận xung đột. Bản gốc vẫn nguyên vẹn.

## Control cần làm rõ

Số thứ tự dưới đây tính từ1 trong `control_intervals` của file người dùng:

| Records | Vấn đề | Cần xử lý |
|---|---|---|
| 1–7 | Cùng Việt Nam #1, start1.833315/end7.999920 lặp7lần | Giữ1bản; repair draft đã bỏ6bản trùng |
| 8 và9 | Cùng khoảng8.633247–9.566571s nhưng gán cả Việt Nam #1 và #6 | Xác nhận người kiểm soát hoặc tách tại thời điểm đổi người thật |
| 10 và11 | Tonga #11:10.433229–10.999890s; Tonga #18:10.566561–12.266544s | Sửa khoảng chồng10.566561–10.999890s theo video nguồn |

Trong repair draft, hai cặp xung đột tương ứng records2/3 và4/5. Không cho hai controller chắc chắn cùng lúc trong GT một quả bóng. Nếu không thể kết luận, annotator cần biểu diễn uncertain interval không chồng theo protocol, không ép chọn actor.

Review UI hiện chỉ kiểm tra trạng thái reviewed khi xuất approved và chưa chặn mọi overlap/duplicate; vì vậy việc xuất được approved không chứng minh packet hợp lệ. Intake phát hiện các lỗi này trước chấm; không bỏ qua validation để có metrics.

Không cần review lại108ball samples hoặc nhập lại5passes chỉ vì sửa control. Có thể nạp repair draft qua nút “Nạp draft/packet” trong trang review, sửa `control_intervals` bằng JSON, “Áp dụng JSON sửa”, rồi xuất lại sau khi xác nhận reviewer/coverage. Có thể chỉnh file JSON bằng IDE và lưu thành bản mới; báo đường dẫn để kiểm tra lại. Không ghi đè bản nguồn làm mất lịch sử review.

## Trạng thái tiếp theo

**Task07 vẫn IN_PROGRESS.** Cần giải quyết hai xung đột control, chạy full evaluator, phân tích41ball misses và5pass misses trên development, rồi cải thiện/freeze recognition và kiểm chứng bằng đoạn chưa dùng để chỉnh. Nhãn development đã xem không còn là test độc lập. Chưa nhận reviewed validation packet.

Lần tiếp nhận này không sửa runtime/model hoặc raw prediction files; không chạy lại bộ233tests đã PASS chỉ để kiểm tra tài liệu/nhãn. Kiểm tra đã thực hiện gồm JSON parse, schema/source/protocol, overlap/duplicate audit, immutable prediction hashes, full CLI rejection, partial component evaluation và hash file nguồn trước/sau.
