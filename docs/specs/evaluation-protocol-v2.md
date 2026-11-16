# Evaluation protocol v2 — DRAFT

Ngày: 2026-11-03. Áp dụng cho:
1. Task05: Court calibration, footpoint projection, trajectory và time-weighted heatmap.
2. Task06: Player tracking, team classification, role/identity resolution và local OCR.
3. Task07–Task10: Automatic points, rebounds, assists, ball control (khi chuyển giao).

Chưa chốt rules giải, GT hoặc split; không chạy benchmark holdout theo protocol chưa duyệt. Task13 sẽ xây evaluator; task04 chỉ bàn giao thiết kế và validator dữ liệu.

## 1. Đơn vị, dữ liệu và freeze

Thời gian dùng normalized source PTS của G03, không dùng wall-clock hoặc frame_index/average_fps. Mỗi video có manifest hash và ánh xạ ID từ filename G03 sang manifest; v1 clip02 tương ứng filename 20521993-uhd_2160_3840_60fps, không thay hai ID bằng nhau tùy tiện.

Chỉ GT approved với reviewer/time hợp lệ và đủ evidence được đưa vào benchmark. Draft/rejected/uncertain tách riêng. Coverage phải được duyệt trước chạy predictions; khoảng fully_reviewed bao gồm cả background không có sự kiện. Excluded có lý do và fingerprint, báo thời lượng bị loại; không loại khoảng khó sau khi thấy lỗi.

Tách calibration/validation/test/reserve theo session/pha/nguồn, không chỉ theo tên file hoặc hash. Replay/crop/re-encode giữ cùng nhóm. Clip04–07 holdout v1 tiếp tục được bảo vệ; chưa có test v2 mới. Freeze rules/protocol/roster/annotations/reviews/coverage/splits trong external lock trước đọc output test.

## 2. Protocol đánh giá Task05 (Geometry & Court Position)

### Mẫu kiểm tra hợp lệ (Eligible Samples)
- Mẫu kiểm tra độc lập gồm các điểm chân nhìn rõ (visible-foot GT) được gán nhãn thủ công kèm thông tin reviewer trong `codebase/data/v2/annotations/player_positions.csv`.
- **Tuyệt đối không dùng chính các điểm correspondence (fit points) đã dùng để tính homography làm tập kiểm chứng.**
- Loại trừ các mẫu chân bị che khuất hoàn toàn (occluded) hoặc nằm ngoài khung hình/ROI; các mẫu này phải được ghi nhận rõ trong cột `visibility_status` và tính vào coverage thống kê, không tự động kẹp biên (clamp) về viền sân.
- Cỡ mẫu tối thiểu: 10–20 mẫu độc lập phân bố đều trên các khu vực sân (dưới rổ, vạch 1 điểm, vạch 2 điểm, hai góc baseline).

### Công thức tính sai số và chỉ số đánh giá
- Với mỗi mẫu kiểm tra thứ $i$ có tọa độ chân thực tế trên sân $p_{gt, i} = (x_{gt}, y_{gt})$ và tọa độ chiếu dự đoán $p_{pred, i} = (x_{court}, y_{court})$:
  $$e_i = \| p_{pred, i} - p_{gt, i} \|_2$$
- Sai số chuẩn hóa theo chiều rộng vùng phân tích sân ($W_{court} = 15.0\,\text{m}$ cho sân FIBA 3x3 nửa sân chuẩn, hoặc chiều rộng bounds theo hệ normalized):
  $$e_{norm, i} = \frac{e_i}{W_{court}} \times 100\%$$
- **Chỉ số nghiệm thu chính (Primary Metric):**
  $$\text{Median Normalized Position Error} \le 5.0\%$$
- Báo cáo phân bố sai số: Median error, Mean error, 90th percentile error, Min/Max error, và số lượng mẫu không thể chiếu hoặc bị loại do che khuất.

## 3. Protocol đánh giá Task06 (Tracking, Team & Identity)

### Mẫu kiểm tra hợp lệ (Eligible Samples)
- Dữ liệu video thi đấu hai đội thật (dual-team footage), phân biệt rõ màu áo, có các pha crossing, occlusion, lost/reacquire và thay người.
- Roster chính thức đã được phê duyệt trong `codebase/data/v2/roster.csv` (gồm team_id, jersey_number, player_id, is_active).
- Ground truth tracks và identities được đối soát độc lập trong `codebase/data/v2/annotations/identities.csv`.

### Phân loại Đội (Team Classification Evaluation)
- Khớp nối dự đoán với ground truth theo không gian (IoU $\ge 0.5$ tại cùng timestamp $t$).
- **Độ chính xác toàn diện (Overall Team Accuracy):**
  $$\text{Team Accuracy} = \frac{N_{\text{correct\_team}}}{N_{\text{total\_eligible\_gt}}} \times 100\%$$
  - Mẫu số ($N_{\text{total\_eligible\_gt}}$) bao gồm toàn bộ: Đúng đội, Sai đội, Chưa xác định đội (`unknown`), và Bỏ sót (`missed detections`).
  - **Mục tiêu nghiệm thu:** Team Accuracy $\ge 90.0\%$.
  - Độ chính xác có điều kiện trên các mẫu đã gán ($\frac{N_{correct}}{N_{correct} + N_{incorrect}}$) chỉ mang tính chất chẩn đoán thuật toán, không dùng để thay thế độ chính xác toàn diện.

### Định danh Cầu thủ (Player Identity Evaluation)
- Định danh cầu thủ phải được đánh giá tách bạch hoàn toàn với phân loại đội; không lấy Team Accuracy để gọi là Player Identity Accuracy.
- Chỉ các khoảng thời gian số áo nhìn rõ (visible jersey number) mới tính vào mẫu số đánh giá nhận dạng số áo/cầu thủ.
- Độ trễ xác nhận (Causal Confirmation Latency): thời gian từ lúc cầu thủ xuất hiện và số áo nhìn rõ đến khi resolver chốt identity phải $\le 2.0\,\text{s}$.
- Bảo đảm tính nhân quả (Causality): Ánh xạ tại thời điểm $t$ thông qua `mapping_at(track_id, t)` không được hồi tố gán ngược cho các frame trước thời điểm đủ evidence.
- Phát hiện xung đột (Conflict Handling): 0 trường hợp trùng lặp active player (cùng 1 player_id gắn đồng thời cho 2 tracks phân biệt đang hoạt động).
- Đánh giá Tracking: Báo cáo số lần đổi ID (ID Switches - IDS), độ phân mảnh track (Fragmentation), và MOTA/IDF1 khi có bộ nhãn tracklet hoàn chỉnh.

## 4. Matching đề xuất cho Events (Task07–Task10)

Các windows lưu trong ruleset: point 0.50s, rebound 0.75s, assist 0.75s. Đây là đề xuất cần duyệt trước test.

| Stat | Mốc GT | Điều kiện strict |
|---|---|---|
| Points | shots.score_time_s của made | cùng video, shooter/team, shot kind/value, trong window |
| Rebound | rebounds.rebound_time_s | cùng video, actor hoặc team rebound, team, subtype, liên kết shot đúng |
| Assist | assists.assist_time_s = passes.release_time_s | cùng video, passer/scorer/team, eligible, pass/shot links đúng |

Dự đoán và GT có ID độc lập. Match shots trước để tạo ánh xạ predicted_shot_id → gt_shot_id; rebound/assist phải dùng ánh xạ đó. Tương tự với pass nếu chấm liên kết pass. Không so hai chuỗi shot_id từ hai hệ thống như thể chúng cùng namespace.

Trong từng video/stat, tạo cạnh giữa các cặp thỏa điều kiện strict và time window. Chọn **matching một-một có số cặp lớn nhất**, sau đó tổng |delta_t| nhỏ nhất; tie còn lại theo thứ tự timestamp rồi ID ổn định. Không dùng greedy gần nhất gây mất một match hợp lệ khác. Mỗi prediction/GT dùng tối đa một lần. Duplicates không match là FP.

Sai actor/team/value/subtype/link làm cặp không đủ điều kiện strict: prediction thành FP, GT còn lại thành FN. Unknown/unresolved prediction trên GT hợp lệ vẫn làm giảm recall/attribution; không bỏ để nâng điểm. Có thể báo thêm event-only matching để chẩn đoán, luôn tách khỏi strict metrics.

## 5. Metrics và cỡ mẫu

- Precision = TP/(TP+FP); recall = TP/(TP+FN); F1 = 2TP/(2TP+FP+FN).
- Mẫu số bằng 0 → **N/A**, không ghi 1.0/100%. Ví dụ có GT nhưng không prediction: recall=0, precision=N/A, F1=0; cả hai rỗng: cả ba N/A.
- Báo TP/FP/FN, số positives/negatives, số video/session, reviewed/excluded seconds, unresolved rate, sai lệch số đếm points/REB/AST theo team/player và temporal error trên matches.
- Targets P≥95%, R≥90% cho từng stat là mục tiêu chưa đo. Báo cỡ mẫu/độ bất định; pilot nhỏ không chứng minh khả năng tổng quát.
- Kết quả tự động và sau manual correction là hai bộ riêng. Không lấy GT làm đầu vào recognition.

## 6. Gate hiện tại

Tooling validator phân biệt structural/tooling/data/locked. Gate data là kiểm tra tối thiểu bằng máy, không chứng nhận người review đúng chuyên môn hoặc đủ quy mô benchmark. Protocol/rule/schema cho FT series và quyết định giải vẫn cần duyệt; test fixtures là synthetic và không thuộc GT thật.

Xem [rules](rules-v2.md), [contracts](contracts-v2.md), [data report](../reports/data-v2.md). Khi freeze, ghi version/hash chính tài liệu protocol cùng bản data lock hoặc acceptance snapshot; không tự tạo lock trên dataset hiện đang trống.
