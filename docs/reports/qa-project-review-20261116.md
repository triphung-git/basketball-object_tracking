# Review toàn dự án và sửa lỗi demo — 16/11/2026

## Kết luận hiện tại

**Demo có thể chạy và xem lại; mức hoàn thiện chức năng là `DEMO_PARTIAL`, chất lượng AI `NOT_ACCEPTED`.** Các nhãn PASS/READY trong báo cáo D11–D12 trước đây không chứng minh đã có đủ PTS/REB/AST tự động trên video thật. Báo cáo này cập nhật kết luận dựa trên mã, baseline test, chạy lại video và kiểm tra trình duyệt.

Không có Git repository trong workspace hiện tại. Các file có sẵn được sửa trực tiếp; bản sao nguồn trước sửa nằm tại `codebase/outputs/qa-review-20261116/source-backup`. Không thay approved GT, splits, calibration landmarks, baseline weights hay kết quả experiment lịch sử.

## Phạm vi rà soát

| Thành phần | Kết quả và giới hạn |
|---|---|
| Runtime/Python | Python 3.12.14 trong `.venv`; compile nguồn/scripts thành công; không cài lại môi trường |
| Entrypoints | Root Python launcher, batch launcher, view, video-analysis, diagnostic-cache được kiểm tra bằng suite/CLI |
| Detection/tracking/identity | Pipeline thật chạy trên Vietnam–Tonga, OCR local có evidence; chưa chứng minh accuracy tổng quát |
| Court/heatmap | Ràng buộc hash, kích thước và toàn bộ khoảng thời gian; heatmap có kiểm tra bảo toàn khối lượng |
| Shot/PTS/REB/AST | Sửa ghost rebound; giữ unknown/unresolved; test rule/ledger không được dùng thay accuracy video |
| Ledger/boxscore | Tính từ sự kiện đủ điều kiện; không tính proposal thành confirmed stat |
| Evaluator/data | Giữ nguyên scope/split/GT. Báo cáo D07 là diagnostic cùng nguồn đã exposed, không là blind acceptance |
| Dashboard/video | Kiểm tra browser desktop/mobile, playback/seek, heatmap thật, API exports và Range HTTP |
| Packaging/docs | Manifest kiểm SHA thật; summary từ run; bundle mới không ghi đè evidence cũ; cập nhật hướng dẫn |

## Lỗi đã xác minh và sửa

| ID | Mức | Lỗi trước sửa | Thay đổi |
|---|---|---|---|
| QA01 | P1 | ReboundEngine chấp nhận chuỗi control rows không có actor, kể cả `unknown/free`, tạo rebound giả từ video | Bắt buộc actor và state/certainty hợp lệ nếu có; break chuỗi khi không đủ bằng chứng |
| QA02 | P1 | Summary bundle cố định 150 frame, 46,18 FPS, 1 REB, 17,43 p-s, trong khi run thực có 151 frame, 2,1 FPS, 0 REB được tính, 17,4 p-s | Sinh summary từ stage_counts, timings, geometry và boxscore_totals; ưu tiên run.json chuẩn khi load |
| QA03 | P1 | Viewer ưu tiên video gốc thay overlay; timeline dùng 302s để tua clip 5s | Ưu tiên overlay; quy đổi source clock ↔ playback clock; marker nằm trong khoảng video |
| QA04 | P1 | MP4 overlay ghi PTS bắt đầu 300s; Chrome đổi duration thành ~301s sau seek | Xuất clip từ PTS=0, giữ source clock trong metadata/telemetry; kiểm tra browser sau tua |
| QA05 | P1 | Request video không có Range chỉ gửi 64MB dù Content-Length là cả file; Range cuối file/suffix không dùng được; video có thể chặn API trên server đơn luồng | Stream theo chunk đến hết, hỗ trợ suffix/clamp cuối file/416; dùng ThreadingHTTPServer |
| QA06 | P1 | Viewer nói “Verified manifest” nhưng không kiểm hash; load bỏ qua event/JSON lỗi | Kiểm path/size/SHA/count; báo lỗi cụ thể thay vì lặng lẽ làm mất event |
| QA07 | P1 | Geometry chấp nhận parent theo start 290–335s mà không kiểm end; upstream vẫn project dù orchestration ghi mismatch | Một bộ kiểm chung dựa trên manifest/segment; cả request phải thuộc scope; không cấp model vật lý khi mismatch |
| QA08 | P2 | Có heatmap PNG nhưng dashboard chỉ hiện banner; shot scalar distance bị dựng thành một vị trí giả | Cấp ảnh PNG thật; chỉ plot shot có đủ x/y, bỏ suy đoán tọa độ từ một khoảng cách |
| QA09 | P2 | Mobile tràn ngang 494px trên viewport 375px | Sửa min-width grid và vùng cuộn table; browser xác nhận scrollWidth=375 |
| QA10 | P1 | Python launcher lỗi Unicode tiếng Việt trên console Windows mặc định | UTF-8 cho stdout/stderr/child environment; bỏ import diagnostic không cần thiết ở view path |
| QA11 | P2 | 4 test fail khi chạy từ codebase; batch không truyền exit code rõ ràng; --serve bỏ qua host/open-browser và chưa đóng socket đúng khi Ctrl+C | Đường dẫn theo __file__; truyền exit code; dùng host/cổng thực và đóng server trong finally |
| QA12 | P2 | Video-analysis không tự sinh overlay; packaging có thể ghi đè bundle và gắn video không cùng run | Public CLI xuất overlay của run; builder nhận run-dir, từ chối output có sẵn, yêu cầu overlay cùng run; manifest ghi scope evidence lịch sử |

Ngoài ra: bỏ chuyển ảnh BGR cho các frame trước start-time, giữ frame index/PTS gốc; thêm validation time/frame/OCR interval; bổ sung `--check` và `--require-calibrated`. Không dùng seek xấp xỉ có thể làm sai frame index trên VFR.

## Bằng chứng kiểm thử

- Baseline **517 passed, 4 failed, 1 skipped, 61 subtests passed**, 284,31s. Bốn failure đều là đường dẫn trong D09/D11, không được bỏ test hoặc hạ tiêu chí để đạt.
- Nhóm API/rules/ledger/QA: **53 passed**.
- Nhóm video/overlay/QA: **41 passed**.
- Nhóm CLI/calibration/QA: **29 passed**.
- Full suite sau sửa: **539 passed, 1 skipped, 61 subtests passed**, 213,68s. Xem `codebase/outputs/qa-review-20261116/final-regression.log` và `final-junit.xml`.
- Nhóm regression chạy từ thư mục gốc: **25 passed**, 3,29s. Các cảnh báo còn lại là deprecation/pin_memory của EasyOCR/PyTorch; không có failure.
- Log baseline: `codebase/outputs/qa-review-20261116-baseline.log`; JUnit baseline: `codebase/outputs/qa-review-20261116/baseline-junit.xml`.

Test hồi quy mới bao gồm file >64MB; Range suffix/end clamp; bundle bị sửa; event JSON hỏng có dòng lỗi; geometry vượt thời gian; controller không có/không confirmed; clip PTS=0; bảo toàn frame index khi bỏ chuyển BGR prefix. Có một lượt kiểm tra từ thư mục gốc riêng để xác nhận sửa lỗi cwd.

## Chạy thật qua public entrypoint

Lệnh được chạy với output mới, không cache detector, OCR local bật:

```powershell
codebase/.venv/Scripts/python.exe run_demo.py --mode video-analysis --video codebase/assets_test/vietnam-tonga.mp4 --court codebase/configs/courts/vt_development_court.json --roster codebase/configs/rosters/vietnam_tonga.json --start-time-s 300 --end-time-s 305 --output codebase/outputs/qa-review-20261116/clean-run
```

Kết quả `completed`: 151 frame, 1 shot miss, **0 active ledger events**, 0 PTS/REB/AST được xác nhận. Rebound cũ đã biến mất sau guard fix. OCR có 2 evidence đọc số 18. Heatmap 17,40 p-s (team_a 5,633335; team_b 9,933333; unknown 1,833332), conservation=true.

Pipeline timing gồm khởi tạo/giải mã prefix: **242,7035s, 0,62 FPS** trong lần đo này; không gồm bước render overlay sau đó. Đây là lần chạy nguội với OCR, không so trực tiếp với 46,18 FPS cached benchmark lịch sử. Lượt replay dùng detections của chính clean-run, tắt OCR, chạy trên source sau sửa skip-BGR: 88,571s / 1,70 FPS; giữ 151 frame, 1 miss, 0 confirmed PRA. Các phép đo diễn ra khi có công việc QA khác trên máy, không là benchmark hiệu năng độc lập.

Artifacts tương ứng: `clean-run/`, `final-cache-replay/`, các file log cùng tên trong output QA. File JSONL rỗng là output hợp lệ khi không có event được chấp nhận.

## Browser QA

Chrome thật qua Playwright: desktop 1280×800 và mobile 375×812. Trước sửa: video duration đổi từ 5 thành 301,333s sau seek; mobile rộng 494px. Sau sửa: clip mới 5,033333s trước/sau seek, click miss tại 302,733s đưa video tới khoảng 1,733333s (pre-roll 1s), không JS error; mobile scrollWidth=375; heatmap tải được; 3 exports trả HTTP 200. Events export 0 bytes đúng với ledger rỗng.

Bằng chứng browser cuối và ảnh nằm trong `codebase/outputs/qa-review-20261116/browser-verified/`. `browser-final/` giữ lần kiểm tra trước tinh chỉnh bảng. Đã mở ảnh để kiểm tra trực quan.

## Chất lượng AI chưa được nghiệm thu

Báo cáo D07 được giữ nguyên: combined diagnostic TP=0, FP=8, FN=17; PTS 0 prediction/14 GT, REB 8 prediction/2 GT/0 TP, AST 0 prediction/1 GT. Đây là artifact lịch sử có sparse/exposed GT; không được dùng như precision/recall tổng quát hoặc đại diện cho bản QA mới. Chưa rerun toàn bộ đánh giá dài sau guard fix; không suy accuracy mới từ việc unit test pass.

D06 paired near-rim có 8 frame: baseline TP=0/FN=3/TN=5, candidate TP=0/FP=8/TN=0. Giữ baseline; không promote model dựa trên batch này. Quyền review nhãn R01 đã được ghi approved trong register, không cần hỏi lại.

Thứ tự công việc còn lại: (1) đo/cải thiện ball và control/identity trên development có GT; (2) chứng minh video thật có PTS/REB/AST được xác nhận và đúng attribution; (3) đo hiệu năng đúng profile và xử lý thời gian đọc prefix/OCR; (4) có coverage/nguồn independent phù hợp rồi chạy quality gate nguyên gốc. Không hạ ngưỡng nghiệm thu, không nhập tay stats để che thiếu recognition.

## Bàn giao

Mở `.\run_demo.bat`. Kiểm bundle bằng `codebase/.venv/Scripts/python.exe run_demo.py --check`. Bundle mặc định sau QA là `codebase/outputs/demo-completion-20261116/demo-bundle-qa-v2` và giữ bản cũ nguyên trạng.

[Hướng dẫn sử dụng](../USER_GUIDE.md). Kết quả kỹ thuật và giới hạn hiện tại nằm trong `qa-verdict.json`, không thay thế quyết định chất lượng của người dùng hoặc sửa approval lịch sử.
