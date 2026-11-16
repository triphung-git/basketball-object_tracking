# Kiểm tra ba video mẫu — task01

Nguồn: `codebase/assets_test/`. Chỉ đọc file gốc, không sửa hoặc upload. FFprobe lấy metadata, FFmpeg giải mã toàn bộ video bằng `-xerror`, xuất ảnh lấy mẫu riêng. Audio không dùng cho detection.

| Video | Độ phân giải | FPS | Thời lượng video | Frames | Giải mã |
|---|---|---|---|---|---|
| 19570048-uhd_3840_2160_24fps.mp4 | 3840×2160 | 24 | 18,083 s | 434 | Pass |
| 20521993-uhd_2160_3840_60fps.mp4 | 2160×3840 | 60 | 18,150 s | 1089 | Pass |
| 5275554-uhd_2160_4096_25fps.mp4 | 2160×4096 | 25 | 28,320 s | 708 | Pass |

Hai file đầu có AAC audio. Thời lượng container dài hơn video một chút do audio; bảng trên dùng thời lượng video stream.

## Quan sát từ 12 ảnh lấy mẫu mỗi video

- Clip01: sân ban đêm, nhiều người, bóng tương đối nhỏ. Vành nhìn thấy nhưng ánh sáng yếu và thay đổi vị trí người dễ gây che khuất. Dùng kiểm tra detection trong điều kiện khó; cần xem chuyển động đầy đủ và kiểm chứng ROI trước scoring.
- Clip02: một người áo xanh, một rổ nhìn rõ và góc nhìn ổn định hơn trong ảnh mẫu. Đề xuất làm mẫu chính cho MVP. Dạng dọc khiến letterbox vào model vuông có thể giảm kích thước bóng hiệu dụng; 60 FPS nguồn chưa đồng nghĩa inference đạt 60 FPS. Chưa gán nhãn vào/trượt.
- Clip03: nhiều người, camera thay đổi vị trí/góc rõ; có đoạn vành ra sát/ngoài khung. Dùng smoke test detection; chưa phù hợp scoring bằng ROI cố định xuyên toàn clip. Không tự bổ sung camera-motion compensation trong task01.

Ảnh lấy mẫu chỉ hỗ trợ đánh giá sơ bộ, không xác nhận không có cuts/replay, không xác nhận nhãn lượt ném và không chứng minh độ chính xác model.

## Bằng chứng tái lập

`codebase/scripts/inspect_videos.py` chạy thành công trên cả ba file. JSON metadata và contact sheets nằm trong `codebase/outputs/video-inspection-01/` (không commit). Muốn chạy lại phải dùng tên output mới; công cụ từ chối ghi đè thư mục có sẵn.

## Quyết định trong phạm vi task01

Giữ cả ba clip để kiểm tra output detection. Đề xuất clip02 làm baseline cho các task scoring sau, nhưng chưa mở rộng phạm vi để theo camera di chuyển. Không cần cung cấp video mới để bắt đầu smoke test. Vẫn cần quyền tải đúng model riêng và kiểm chứng runtime local.
