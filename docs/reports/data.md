# Dữ liệu nghiệm thu task02 — 2026-11-01

Trạng thái: **DONE cho bộ dữ liệu pilot**. Báo cáo này thay thế các thống kê draft/proposed trước đây. Các file manifest, labels, reviews, coverage và split đã khóa được giữ nguyên trong đợt nghiệm thu.

## Số liệu từ file hiện tại

| Thành phần | Kết quả |
|---|---|
| Video | 7, tổng 5177 frames, khoảng 180,897 giây video stream |
| Approved theo events.csv và reviews.csv | 10 lượt: 6 made, 4 miss, 0 uncertain |
| Draft | 0; events.draft.csv chỉ có header |
| Calibration | clip02: 1 made, 0 miss |
| Test | clip04–07: 4 made, 3 miss, cùng một session broadcast |
| Detection-only / loại khỏi scoring | clip01: 1 miss; clip03: 1 made, camera chuyển động |
| Split | 1.0.0-locked; nhóm calibration và test tách theo nguồn/camera/session |
| Coverage | fully_reviewed có background; clip03 sau 4,8s và clip07 sau 10s bị excluded |

Điểm/đội là metadata thủ công. Dữ liệu hiện chứa solo/2 cho ba clip đầu, A/B và 1/2 cho broadcast. Pipeline chưa tự xác định đội, cầu thủ hoặc luật ghi điểm. Không cần thay đổi schema để tiếp tục task03.

## Nhãn đã bàn giao

| Video | Shot | Khoảng giây | Result | Score time | Team / điểm |
|---|---|---|---|---|---|
| clip01 | s001 | 3,80–7,70 | miss | — | solo / 2 |
| clip02 | s001 | 3,80–7,30 | made | 6,38 | solo / 2 |
| clip03 | s001 | 1,50–4,80 | made | 4,04 | solo / 2 |
| clip04 | s001 | 7,20–10,80 | miss | — | B / 2 |
| clip05 | s001 | 7,20–10,50 | miss | — | A / 2 |
| clip06 | s001 | 4,20–6,40 | made | 5,72 | A / 1 |
| clip06 | s002 | 24,50–26,60 | made | 25,74 | B / 1 |
| clip06 | s003 | 30,80–33,10 | made | 32,26 | A / 1 |
| clip06 | s004 | 40,50–42,70 | made | 41,87 | B / 1 |
| clip07 | s001 | 5,50–8,50 | miss | — | A / 1 |

Xác nhận phê duyệt dựa trên ledger đã có (reviewer user, timestamp và reason); đợt nghiệm thu không tạo xác nhận mới và không tự gán lại nhãn. Nội dung notes chi tiết nằm trong events.csv.

## Kiểm định đã thực hiện

- Validator đọc và đối chiếu SHA-256 của 7 file media với manifest.
- Kiểm tra các fingerprint manifest/events/coverage trong split locked: khớp.
- Kiểm tra review approved, timestamp, schema, key trùng, coverage overlap, group/session/camera/hash leakage và draft isolation.
- Đối chiếu test classes trên đúng test IDs, không mượn made/miss từ calibration hoặc detection-only.
- `validate_dataset.py --require-ready` pass, với cảnh báo cỡ mẫu nhỏ. Mục tiêu 50–100 lượt là mục tiêu thu thập trong kế hoạch, không phải điều kiện cứng để bắt đầu pilot.
- Snapshot fingerprint bổ sung cho reviews, draft và splits tại `codebase/outputs/acceptance-20261101/audit.json`; công cụ audit không đổi dữ liệu đã khóa.
- Kết quả tests và review code cuối cùng: [task01-task02-acceptance.md](task01-task02-acceptance.md).

## Timebase bắt buộc cho pipeline sau

Audit FFprobe packet PTS xác nhận clip01–03 có khoảng timestamp đều; clip04–07 có khoảng PTS biến thiên khoảng 0,0333–0,0700 giây. FPS trong manifest broadcast là trung bình, không phải đồng hồ cố định.

Task03/07 phải dùng presentation timestamp chuẩn hóa về đầu video. Không suy timestamp bằng frame_index / avg_fps cho VFR. Các số frame trong ghi chú broadcast là tham chiếu gần đúng: phép đối chiếu chỉ số suy từ FPS với PTS của clip06 lệch đến khoảng 65 ms. Score_time_s đã duyệt vẫn giữ nguyên; muốn sửa nhãn cần revision và người dùng duyệt.

Coverage endpoints được ghi tròn đến 0,01 giây; validator cho dung sai biên 0,05 giây. Không dùng dung sai này để kéo dài một pha hoặc coi vùng chưa xem là background đã duyệt.

## Giới hạn và bảo vệ holdout

- 7 lượt test cùng một session, không phải 7 mẫu độc lập về cảnh quay. Chưa đủ để kết luận độ chính xác tổng quát hoặc mốc precision/recall mục tiêu.
- Calibration chỉ có một made, thiếu miss: hạn chế khả năng chỉnh rule chống false positive. Có thể thu thêm dữ liệu calibration ngoài session test; không lấy clip04–07 để chỉnh rule.
- Test đã được xem khi gán nhãn/kiểm định dữ liệu, chưa phải blind holdout chưa ai từng thấy. Giữ độc lập với vòng chỉnh detector/scoring; không tuyên bố Zero Leakage vượt quá bằng chứng nhóm/manifest hiện có.
- Manifest notes có chứa mô tả kết quả nhãn; input inference chỉ được lấy path/metadata kỹ thuật. Không dùng notes hoặc events.csv để quyết định detection/scoring, chỉ dùng labels khi đánh giá.
- Camera broadcast có replay/cut; dùng coverage để loại đúng đoạn, không đếm replay như lượt mới.
- Không suy ra chất lượng scoring từ metrics detection task01.

## Bàn giao

Task03 có thể bắt đầu với clip02 và runtime ONNX CPU đã chốt. Giữ toàn bộ frame cho baseline offline, chưa tự áp dụng skip-frame. Task05 chỉ chỉnh trên calibration; task07 đọc test cùng coverage đã khóa. Xem [hợp đồng bàn giao task03](../handoffs/task03.md).
