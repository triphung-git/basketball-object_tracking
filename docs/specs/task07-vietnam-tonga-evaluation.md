# Task07 Vietnam–Tonga — protocol pilot đã duyệt

2026-11-04. **PROTOCOL/NGƯỠNG ĐÃ ĐƯỢC NGƯỜI DÙNG DUYỆT; GT còn chờ review.** Người dùng xác nhận trong hội thoại: “Duyệt protocol/ngưỡng đề xuất; nhãn thực tế sẽ review sau”. Roster đã được xác nhận; không hỏi lại roster, protocol hoặc quyền dùng các đoạn30–60s.

Nguồn video SHA-256 `1443c1d263c8037a5684f3dbc0ef9216beb5097d9a47c4c1c9b94d1363e26865`. Development: parent300–330s. Validation đề xuất: parent165–195s. Cả hai cùng trận, chỉ chứng minh pilot theo pha; không phải test độc lập theo trận. Cận cảnh/cuts được review và ghi operational exclusions trước recognition, không loại đoạn sau khi thấy lỗi để nâng metrics. Thay segment vì footage không đủ tình huống phải ghi revision và lý do, giữ kết quả cũ.

## Metrics và ngưỡng đã duyệt

| Chỉ số | Ngưỡng đã duyệt |
|---|---:|
| Observed ball recall trên visible GT samples, IoU≥0.30 | ≥90% |
| Strict controller accuracy theo eligible GT seconds, đúng team/player; unknown/missed vẫn trong mẫu số | ≥90% |
| Strict completed-pass precision | ≥95% |
| Strict completed-pass recall | ≥90% |
| PTS export error | ≤2 microseconds |
| Gap/cut tạo phantom completed pass; predicted-only xác nhận control/pass | 0 |

Đây là tiêu chí riêng cho pilot Task07, không phải áp tự động ngưỡng PRA hoặc kết quả đã đạt. Báo actor-only/event-only metrics để chẩn đoán; không thay strict metrics. Ngưỡng không thay đổi sau khi xem validation để tự PASS.

GT pilot: nhãn ball visible/occluded và bbox ở mẫu đều theo thời gian cùng các mốc release/receive; control intervals/player/team, passes và negatives được review từ video gốc, không sao chép prediction. Mục tiêu tối thiểu60visible ball samples và5completed passes kèm negative/uncertain cases trước khi gọi là pilot acceptance; nếu footage thiếu, mở rộng bằng đoạn30–60s mới và báo cỡ mẫu. Dataset nhỏ không chứng minh gần100% hoặc khả năng tổng quát.

Pass matching một-một, tối đa cardinality rồi tối thiểu timestamp error; release/receive tolerance0.25s. Actor snapshots theo event time; sai actor thành strictFP/FN. Control duration dùng PTS, không kéo sample cuối hoặc nối gaps lớn. GT uncertain được tách theo policy công bố; số mẫu/thời lượng bị loại và predictions trong vùng uncertain phải được báo.

Cập nhật exposure: cả hai outputs đã được xem để triage màu/ROI; revision masked được báo như diagnostic pilot cùng trận, không phải untouched validation. Giữ tên thư mục, snapshots và kết quả cũ để truy vết. Xem [report](../reports/task07-vietnam-tonga-segments.md). Thresholds không đổi; nhãn vẫn draft chờ review.

Agent chuẩn bị nhãn draft/evidence pack, người dùng review trước đổi approved. Roster approval không phải GT approval. Recognition không đọc nhãn hay scoreboard để suy events. Freeze code/config/protocol/labels trước chạy validation; lưu fingerprints và số lần validation được xem. Nếu chưa đạt, ghi failure và phát triển tiếp trên development; validation đã xem không tiếp tục được gọi untouched.
