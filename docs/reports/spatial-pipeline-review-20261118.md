# Review và sửa pipeline spatial-only — 18/11/2026

Phạm vi: detection/PTS, tracking/bbox, crop identity, court calibration,
projection, heatmap CLI/web, upload worker và dashboard. Review trực tiếp trạng
thái working tree sau chuyển đổi spatial-only; giữ nguyên các thay đổi và phần
xóa module thống kê trận đấu của người dùng.

## Các lỗi đã sửa

| Mức | Lỗi và tác động trước bản sửa | Xử lý |
| --- | --- | --- |
| P1 | `identity_crops.py` và `tiled_detection.py` import `ball.py` đã xóa; CLI/web worker không import được. | Dùng IoU từ tracker còn hoạt động; tính tâm bbox trực tiếp. |
| P1 | Detection trả `partial` khi dùng `--max-frames`, nhưng downstream chỉ chấp nhận `completed`. | Tracking/projection nhận prefix đã xử lý; kết quả tổng vẫn giữ trạng thái `partial`. |
| P1 | Không có human detection làm file tracking rỗng và heatmap crash ở bước lấy dòng đầu. | Chấp nhận trajectory rỗng; xuất grid zero và metadata thay vì crash. |
| P1 | Mất thông tin chân bị cắt khi trạng thái bị ghi đè bởi `outside_roi`; reprojection có thể nâng thành `valid`. | Giữ validity của visibility; quan sát bị cắt không sinh court coordinates, kể cả khi reproject. |
| P1 | Web heatmap bỏ qua predicted/estimated nhưng giữ điểm cũ, nối xuyên qua khoảng mất dấu. | Các mẫu này xóa trạng thái liên tục của track. |
| P1 | Heatmap CLI có thể dùng timestamp `repaired` ở cuối để che timestamp `estimated` ở đầu. | Kiểm tra cả hai endpoint, lấy trạng thái hạn chế hơn. |
| P1 | Bộ lọc thời gian UI dựng lại heatmap từ frame playback 5 Hz, làm thay đổi thời lượng và nối sai khoảng trống. | Backend xuất các khoảng đã được chấp nhận; UI cắt trực tiếp theo cửa sổ thời gian. Gộp các khoảng liên tiếp cùng ô để giảm kích thước. |
| P1 | UI tự xóa exclusions khi mở/lưu cấu hình. | Bảo toàn exclusions được cấu hình. |
| P1 | Gán đội mới ở cuối interval có thể ghi thời lượng vào đội sai; màu tự động ghi đè manual unknown hoặc bỏ toàn bộ phần tự động của track có assignment. | Ngắt continuity khi đội/role thay đổi; chỉ thêm màu cho các khoảng chưa được gán thủ công. |
| P2 | Track lỗi hình học có thể chiếm khóa chống trùng của một player, khiến track hợp lệ khác mất occupancy. | Chỉ cập nhật khóa sau khi interval vượt kiểm tra hình học/tốc độ. |
| P2 | Màu áo được lấy theo raw PTS, lệch với clock đã chuẩn hóa/sửa của tracking. | Dùng frame index gốc để chọn crop; giữ fallback cho bundle cũ thiếu frame index. |
| P2 | Cache màu chỉ xét số lượng/thời gian track, bỏ qua thay đổi tập crop sau lọc. | Thêm signature theo thời gian, frame index, track và bbox thực tế. |
| P2 | Homography loại bộ mốc đủ tốt vì ba trong bốn mốc đầu thẳng hàng dù còn các mốc khác. | Với hơn bốn mốc, dùng toàn bộ tập điểm và các kiểm tra suy biến của nghiệm. |
| P2 | Track tentative mất dấu rồi trở lại được active sớm dù chưa đủ `min_hits`. | Khi khôi phục, vẫn kiểm tra tổng số hits. |
| P2 | `SceneFilter` so frame mới với cảnh cũ sau cut, có thể bỏ liên tiếp cảnh mới ổn định. | Cập nhật ảnh tham chiếu sau phép so sánh frame kề nhau. |
| P2 | Tiến độ web nhảy về 0 khi tracking bắt đầu; FPS tổng chỉ đo detection. | Chia progress theo stage; timing/FPS tổng bao gồm downstream. |
| P2 | `--roster` ở launcher chỉ dùng cho viewer. | Truyền roster xuống tracking; chỉ decode lại nguồn khi cần crop. |
| P2 | Input roster sai kiểu gây lỗi ngoài validation; `max_frames` nhận bool/float/NaN. | Chuẩn hóa lỗi cấu hình và yêu cầu số frame nguyên dương. |
| P2 | Đóng socket khi body của upload bị từ chối chưa được đọc có thể gây reset trên Windows. | Đọc bỏ body nhỏ với deadline ngắn trước khi trả 403; không đợi upload lớn. |

## Tối ưu thực hiện

- Đọc JSONL theo dòng, không giữ toàn bộ detection records trong RAM.
- Ghi observation theo từng frame, đồng thời cập nhật counters thay vì giữ toàn
  bộ trajectory trong list để xuất cuối run.
- Bỏ hash/decode video lần hai trong tracking spatial không cần crop.
- Reader của detection dùng lại metadata đã probe, tránh hash lại toàn bộ video.
- Overlay 5 Hz chọn frame từ clock detection, kể cả frame không có người;
  không để observation muộn hoặc predicted quyết định frame hiển thị.
- Spatial revision bao gồm phiên bản thuật toán. Spatial map cũ sẽ thành
  `stale`, cần dựng lại để áp dụng quy tắc heatmap mới.

## Kiểm chứng

Kết quả cuối: **150 passed, 9 subtests passed** trong 38,05 s; 6 warnings từ
EasyOCR/PyTorch về API deprecated và pin-memory trên CPU. Kiểm tra cú pháp
JavaScript và CLI `--help` đều thành công.

Verdict: **APPROVE** cho các bản sửa đã kiểm chứng. Confidence: **HIGH** cho
các lỗi có hồi quy tái hiện; chất lượng nhận diện trên footage thực chưa được
đánh giá bằng ground truth.

Lệnh regression toàn bộ:

```powershell
codebase\.venv\Scripts\python.exe -m pytest codebase/tests -q -p no:cacheprovider --tb=short --disable-warnings
node --check codebase/src/basketball_scoreboard/match_dashboard.js
```

Các hồi quy mới nằm trong
`codebase/tests/test_spatial_pipeline_regressions.py`, bao gồm import tất cả
module còn giữ, video/PyAV thật với detector giả lập, prefix, no-human,
clipped-foot, clock barriers, timestamp endpoint, manual/color assignment,
occupancy windows, tracker lifecycle và progress worker. Kiểm tra HTTP dùng
server local thật; chưa thực hiện kiểm tra tương tác trình duyệt.

Smoke test detector thật dùng 8 frame đầu clip development 4K:

```powershell
codebase\.venv\Scripts\python.exe codebase/scripts/run_demo.py --mode video-analysis --video codebase/assets_test/19570048-uhd_3840_2160_24fps.mp4 --output codebase/outputs/spatial-review-20261118-smoke-retry --max-frames 8
```

Kết quả: `partial` đúng theo giới hạn 8 frame; 58 detections (50 human,
8 rim), 7 tracks, 55 observations, 8 timestamps valid. Heatmap `unavailable`
do không cung cấp calibration cho clip này. Tổng thời gian run khoảng 11,09 s,
gồm khởi tạo model khoảng 5,47 s; model-call median khoảng 101,48 ms.
Đây là smoke test ngắn có chi phí khởi tạo, không phải benchmark FPS ổn định.
Run đầu trong sandbox thất bại ở kết nối SDK (`RetryError`); chạy lại ngoài
sandbox thành công. Không dùng footage holdout để kiểm tra development.

## Giới hạn cần giữ rõ

- Chưa có đánh giá GT mới cho detection recall/precision, ID switches,
  fragmentation, projection error hoặc heatmap agreement. Không kết luận
  tăng accuracy từ kết quả unit tests.
- Chưa benchmark RAM/FPS trước và sau trên video dài. Streaming giảm dữ liệu
  giữ trong RAM ở tracking; bước dựng map và heatmap vẫn cần dữ liệu tổng hợp,
  grids theo track và artifacts phục vụ playback.
- Calibration vẫn phụ thuộc đúng camera và khoảng thời gian. Chưa có hệ thống
  tự hiệu chuẩn theo pan/zoom. `SceneFilter` là heuristic độc lập; bản sửa
  không tự bật nó để loại frame trong pipeline.
- Các run/map đã sinh trước bản sửa cần chạy hoặc dựng lại để có kết quả mới.
