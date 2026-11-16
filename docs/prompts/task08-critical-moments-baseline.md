# Prompt — Task08: baseline chẩn đoán cú ném tại các thời điểm quan trọng

**Cập nhật 2026-11-09:** baseline đã có report/artifacts và Task08 chuyển sang triển khai temporal shot engine. Dùng [prompt thực thi pha tiếp theo](task08-temporal-shot-engine.md) cho FSM bốn pha, rim crossing, history OCR 2 giây/team fallback và negative cohort >=30. Prompt dưới giữ để tái lập baseline; không khởi động lại toàn bộ diagnostic nếu cache hợp lệ đã có.

Bạn là Senior AI/Python Engineer, làm việc trực tiếp trong repository này. Hãy thực thi baseline chẩn đoán Task08 trên dữ liệu Việt Nam–Tonga đã được review: khảo sát code, viết phần công cụ còn thiếu, chạy trên video thật, kiểm thử và bàn giao artifacts/report. Không dừng ở việc đề xuất kế hoạch.

Mục tiêu đợt này là xác định pipeline có quan sát đúng bóng, rổ và người ném từ trước release đến sau basket hay không, và lỗi nằm ở detector, ROI, association, camera hay identity. Kết quả là cơ sở xây shot/made–miss engine cho demo Automatic Stats. Đây chưa phải nhiệm vụ hoàn tất toàn bộ Task08 hoặc nghiệm thu PRA.

## 1. Đọc và đối chiếu hiện trạng

Các đường dẫn tính từ workspace root; đọc AGENTS.md áp dụng nếu có và:

- `docs/DEVELOPMENT.md`, `PLAN.md`, `docs/tasks/task08.md`.
- `docs/handoffs/task08-scoring-review-to-critical-diagnostics-20261107.md`.
- `docs/reports/task08-scoring-review-intake-20261107.md`.
- `docs/handoffs/task07c-to-task08.md`, `docs/reports/task07c-acceptance-report-20261107.md`.
- `docs/reports/task07b-decoupling-20261107.md`.
- `docs/reports/task07a-local-finetune-20261108.md` và `codebase/outputs/task07a-finetune-20261108/job/status.json` nếu tồn tại.
- Code detector, video/PTS, tiled inference, player/ball tracking, identity/OCR, ROI và CLI/tests hiện có.

Ưu tiên artifacts/code hiện tại hơn ghi chú lịch sử. Xác minh CLI bằng source hoặc `--help`, không đoán flags. Không sửa đè công việc của người dùng.

Task07 chưa đạt quality gate. Dữ liệu gần nhất ghi ball recall development 50%, strict control/pass 0%; đây là lịch sử phải đối chiếu, không mặc định là kết quả của run mới. Job fine-tune là công việc riêng: không khởi chạy job thứ hai, dừng job đang chạy hoặc đổi dependencies của nó. Không chờ fine-tune để làm phần baseline độc lập này.

## 2. Đầu vào đã có

Nguồn hiện hành:

- `codebase/outputs/task08-scoring-intake-20261107/adjudicated-v3/events-reviewed.json`.
- `codebase/outputs/task08-scoring-intake-20261107/adjudicated-v3/critical-windows-draft.json`.
- `codebase/outputs/task08-scoring-intake-20261107/adjudicated-v3/evidence-reuse.json`.
- Packet/manifest tại `codebase/outputs/task08-scoreboard-review-20261106/` và resolutions đã dẫn trong report intake.
- Video gốc theo đường dẫn trong packet/manifest, SHA-256 `1443c1d263c8037a5684f3dbc0ef9216beb5097d9a47c4c1c9b94d1363e26865`.

Đã có 34 metadata nhất quán, không còn xung đột target chờ xác nhận. Không yêu cầu review lại 34 clip hay hỏi lại các quyết định 009/024/027/028/034. Shooter null và timestamp null hợp lệ phải tiếp tục giữ null.

Chạy đúng 10 cửa sổ đã có mốc rõ: `play_001`, `play_003`, `play_004`, `play_006`, `play_008`, `play_015`, `play_021`, `play_023`, `play_027`, `play_028`. Đọc source bounds, frame indices và PTS từ manifest, không nhập lại bằng tay. 40 ảnh critical moments đã có là ảnh nguồn; không coi đó là predictions hay bbox GT.

## 3. Baseline và ranh giới recognition

1. Freeze fingerprint code/config/runtime/model/source trước khi chạy. Dùng approved model `phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1`, ONNX CPU và pipeline đã có. Class mapping lấy từ runtime.
2. Không thay detector weights, OCR engine, ROI hoặc thuật toán production trong lượt baseline. Viết diagnostic scripts/adapters riêng; không train, upload media hoặc phát sinh cloud inference trong task này.
3. Tạo manifest input recognition chỉ gồm source/window bounds và cấu hình vận hành cần thiết. Các trường `reviewed_shooter_id`, `shot_kind`, score, outcome, notes và `evaluation_times` không được truyền vào detector/tracker/identity hay dùng để điều khiển trạng thái shot.
4. Review times chỉ được dùng để chọn cửa sổ chẩn đoán và đối chiếu sau khi predictions đã được ghi, đóng băng/hash. Mọi kết quả phải ghi `conditional diagnostic`, `independent_holdout=false`; không gọi là blind test hoặc tự tìm shot toàn video.
5. Roster/camera calibration đã có được dùng như cấu hình trước phiên. Không dùng expected shooter để gán identity, không lấy identity cuối clip gán ngược về release.
6. Chỉ reuse cache nếu khớp source, timestamps/frame coverage, model, preprocessing, config và class mapping; ghi rõ phần reused so với inference mới.

## 4. Công việc cần thực hiện

### A. Chạy đủ 10 cửa sổ

- Decode theo source PTS, giữ mapping local ↔ source và kiểm tra boundaries/cuts. Không thay PTS bằng chỉ số frame giả định khi stream không bảo đảm CFR.
- Ghi raw candidates ball/human/rim trước selection, kết quả sau ROI/gates, ball tracker chọn và trạng thái observed/predicted/missing.
- Ghi rejection reason, actor/body evidence, player track, team và identity/OCR evidence sẵn có theo thời điểm.
- Tái dùng logic actor context đã decouple: thiếu số áo không tự loại human khỏi ball association.
- Bóng trong flight có thể xa người. Với FT `play_006`, cần ghi nhận thay đổi bố cục camera và đánh dấu vùng không thể dùng calibration/ROI cũ; không sửa ROI theo vị trí bóng GT để làm baseline đẹp hơn.

### B. Tạo bằng chứng review

- Xuất video overlay cho từng cửa sổ, phân biệt raw candidate, selected observed, predicted, ROI và track/identity rõ ràng.
- Xuất contact sheets quanh release và vùng rổ cùng timeline bóng–actor–camera. Review markers chỉ là lớp hiển thị sau inference.
- Chuẩn bị packet review nhỏ, ưu tiên các frame release/rim và frame thể hiện lỗi; không yêu cầu người dùng annotate lại toàn bộ footage.
- Packet bbox mới giữ draft/unreviewed, có image/source/PTS hashes, visibility và cơ chế skip/uncertain. Không tự duyệt bbox từ predictions hoặc coi không có detection là negative.
- Nếu kết luận lỗi bằng kiểm tra trực quan, lưu frame/evidence và ghi rõ visual diagnostic; không biến nó thành approved GT hoặc IoU metric.

### C. Phân loại lỗi và đo đúng phạm vi

Phân biệt: không có raw candidate đúng; candidate đúng bị ROI/gate loại; tracker chọn sai; thiếu/sai actor identity; camera/cut/calibration không hợp lệ; nguồn không đủ nhìn rõ bóng. Trường hợp thiếu bằng chứng phải giữ uncertain.

Đo được ngay: số frame/window đã xử lý, observed/predicted/missing coverage, candidate counts, các rejection reasons, identity coverage và latency thực đo. Coverage không phải accuracy. Báo ảnh hưởng cạnh tranh tài nguyên nếu job khác đang chạy.

Ball bbox GT hiện chưa có: không công bố IoU recall/precision mới cho đến khi có nhãn được duyệt. Tập scoring hiện chủ yếu là positives: không công bố made/miss precision hoặc khả năng chống false scoring khi chưa có negative cohort. Chỉ thống kê shooter agreement trên nhãn đủ điều kiện, với unknown/missing được báo riêng và denominator rõ.

Lập danh sách dữ liệu bổ sung cụ thể cho miss, rim-bounce, replay và tình huống dễ nhận nhầm. Có thể chuẩn bị draft packet từ nguồn đã được phép sử dụng; không tự gán nhãn outcome chắc chắn.

## 5. Artifacts và kiểm thử

Tạo output directory mới, ví dụ `codebase/outputs/task08-critical-baseline-<run-id>/`, có:

- `run.json`: hashes/versions/config, nguồn, selection exposure, completed/partial/failed và các giới hạn.
- Manifest recognition đã loại các trường GT, predictions/raw candidates và selection/rejection traces theo từng window.
- Overlay videos, contact sheets, timeline và packet review draft.
- `summary.json` cùng bảng lỗi theo 10 pha, liên kết evidence và phần còn uncertain.
- Commands tái chạy; không ghi API key hoặc signed URLs vào artifacts/logs.

Ưu tiên tái dùng contracts/schema đang có. Kiểm thử có ý nghĩa cho phần mới: GT không lọt vào input recognition; mapping PTS/source-window đúng; predicted không thành observed; cut không nối trajectory; null/uncertain không thành nhãn chắc chắn; output không ghi completed khi chỉ chạy một phần. Chạy tests phù hợp và regression cần thiết; không viết tests chỉ để đếm số lượng.

Viết `docs/reports/task08-critical-moments-baseline.md` và handoff cho bước shot engine tiếp theo. Báo đủ: đã chạy gì, kết quả nào đo được, giới hạn, lỗi ưu tiên và điều kiện còn thiếu. Cập nhật PLAN/task status ở mức phù hợp với evidence, giữ nguyên lịch sử.

## 6. Điều kiện hoàn thành đợt này

- Đủ 10 cửa sổ có artifacts liên kết nguồn, hoặc ghi rõ từng cửa sổ bị chặn và lý do kiểm chứng được.
- Có raw predictions tách khỏi selection, evidence review và bảng phân loại lỗi; không bịa metric khi thiếu GT.
- Tests phần mới và regression liên quan pass; baseline inference/OCR/ROI không bị đổi âm thầm.
- Có đề xuất can thiệp tiếp theo dựa trên lỗi thực tế và danh sách nhãn/negative cohort tối thiểu còn thiếu.
- Không đánh dấu Task07 hoặc toàn bộ Task08 DONE chỉ vì hoàn tất diagnostic này.

Tiếp tục làm hết phần đã được giao mà không hỏi lại các lựa chọn triển khai thường lệ. Nếu thiếu GT, vẫn hoàn thành chạy baseline, exports, draft review và report; nêu chính xác dữ liệu còn thiếu để mở bước tiếp theo. Phản hồi cuối dẫn tới report, artifacts, tests và kết luận ưu tiên.
