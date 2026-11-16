# Tiếp nhận Vietnam–Tonga cho Task07 — 2026-11-04

Đã kiểm tra file thật `codebase/assets_test/vietnam-tonga.mp4` và `codebase/data/vietnam_tonga_roster_partial.csv`. Đường dẫn CSV trong câu nhắn có lỗi gõ; file đúng là tên đang mở trong IDE. Không sửa CSV gốc, không inference hoặc upload media trong lần kiểm tra này.

## Kiểm tra sơ bộ

- H264,1920×1080,30 FPS; stream metadata cho 41432 frames,1381.067s (23phút01giây).
- SHA-256 video: `1443c1d263c8037a5684f3dbc0ef9216beb5097d9a47c4c1c9b94d1363e26865`.
- Ảnh mẫu cho thấy intro, góc rộng thi đấu, cận cảnh và đổi góc. Chưa rà full video hoặc kiểm chứng toàn bộ cuts/replays/timestamps/decode.
- CSV có 8 cầu thủ,2 đội; Việt Nam thiếu cả4 số áo. Tonga có1,9,11,18. Notes tự ghi màu áo/số áo còn cần đối chiếu.
- Việt Nam mặc đỏ, Tonga trắng trong các ảnh được kiểm tra.
- Nguồn URL của Việt Nam ghi Asia Cup2026; biển hiệu video thể hiện Singapore2025. Đây là sự khác biệt provenance quan sát được, chưa truy cập/xác minh các trang nguồn trong lần intake.

## Bản đối chiếu từ video, chờ xác nhận

Bảng TEAM ROSTER khoảng49s cho Việt Nam:

| Tên trong CSV | Số áo đề xuất theo bảng video |
|---|---:|
| Nguyễn Huỳnh Phú Vinh | 1 |
| Nguyễn Phúc Vinh | 6 |
| Nguyễn Anh Kiệt | 13 |
| Huỳnh Thanh Tâm | 2 |

Tonga: đã thấy các số1,9,11,18 ở khoảng84–92s. Tên giữ theo CSV người dùng cung cấp; không khẳng định các ảnh mẫu tự xác minh được toàn bộ tên–số áo của Tonga. Đối chiếu bằng chữ/bảng roster và số áo, không nhận diện danh tính từ khuôn mặt.

[Roster đề xuất](../../codebase/outputs/task07-vietnam-tonga-intake-20261104/roster-proposed.csv) giữ các fields/source URLs gốc, bổ sung số áo Việt Nam và review/evidence notes. Tất cả rows vẫn draft_pending_user_review; nguồn2026 chưa được coi là xác minh cho trận2025.

Bằng chứng: [intro sheet](../../codebase/outputs/task07-vietnam-tonga-intake-20261104/intro-contact-sheet.jpg), [Tonga intro](../../codebase/outputs/task07-vietnam-tonga-intake-20261104/tonga-intro-contact-sheet.jpg), [video samples](../../codebase/outputs/task07-vietnam-tonga-intake-20261104/contact-sheet.jpg), [metadata](../../codebase/outputs/task07-vietnam-tonga-intake-20261104/intake.json). Sampling script hoàn thành lưu artifacts, nhưng print JSON ra console sau đó gặp UnicodeEncodeError do terminal cp1252; metadata/ảnh đã lưu UTF-8 thành công. Không có kết luận full decode PASS.

## Cần người dùng xác nhận

1. Dùng roster đối chiếu video làm cấu hình trận: Việt Nam1/6/13/2; xác nhận tên–số áo Tonga theo CSV; màu đỏ/trắng. Có thể giữ tên ẩn danh theo đội/số áo nếu chưa chắc tên thật.
2. Sau khi agent chuẩn bị nhãn control/pass/ball draft: review các chuỗi và uncertain cases. Không yêu cầu người dùng gán nhãn toàn bộ41432frames.
3. Sau khi agent soạn protocol/ngưỡng và các đoạn development/acceptance: duyệt trước đánh giá. Chia đoạn cùng trận chỉ chứng minh pilot, không chứng minh độc lập theo trận.

## Agent tiếp tục thực hiện trong lượt triển khai

Rà footage và ranh giới cảnh, chọn các đoạn góc rộng liên tục; chuyển roster đã chốt sang runtime config; giữ nguyên nguồn. Chuẩn bị nhãn và gói review; khảo sát detector/OCR/control trên đoạn ngắn trước khi chạy toàn video; cải thiện theo error analysis; chạy regressions/evaluator và bàn giao metrics/video evidence. Intro/đồ họa/roster chỉ dùng setup identity, không dùng scoreboard hoặc kết quả GT làm recognition oracle.

Chưa cần thêm video hoặc hiệu chỉnh sân để bắt đầu Task07 theo hệ ảnh. DONE cần kết quả thật đạt tiêu chí đã chốt; việc có video/roster mới chưa tự đóng gate hoặc biến các số đo clip04 cũ thành metrics của Vietnam–Tonga.
