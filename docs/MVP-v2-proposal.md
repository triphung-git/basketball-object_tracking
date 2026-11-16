# MVP v2 đã duyệt — Basketball Heatmap & Automatic Stats

Cập nhật: 2026-11-02. **APPROVED theo yêu cầu người dùng: phiên bản phải tự nhận diện đầy đủ points/rebounds/assists, sau đó proceed lập plan.** Đề xuất Assisted Stats ngày 2026-11-01 được thay thế; bản gốc ở [archive](archive/2026-11-02-pre-auto-stats/README.md).

## 1. Kết quả bắt buộc

Từ video hợp lệ, hệ thống tự phát hiện/tracking người và bóng, phân đội/định danh cầu thủ, tạo heatmap và tự phát sinh points, rebounds, assists theo đội và cầu thủ. Box score cập nhật tự động khi có đủ bằng chứng theo thời gian nội dung video, không cần người dùng nhập hoặc xác nhận từng pha.

Người dùng vẫn có thể audit/sửa sau chạy. Kết quả sau sửa không được dùng thay kết quả tự động để nghiệm thu. Chỉ có form nhập stats hoặc AI gợi ý chờ người duyệt là **chưa đạt MVP này**.

## 2. Phạm vi đầu vào giữ từ đề xuất trước

- MP4 cục bộ, 3x3 một rổ/nửa sân, camera ổn định; hai đội có áo phân biệt, thấy được bóng, chân và các thời điểm tương tác cần thống kê.
- Chọn vùng sân/rổ, hiệu chỉnh hình học và nhập roster trước phiên được phép. Roster là nguồn định danh, không phải nhãn sự kiện.
- Cần thấy diễn biến trước chuyền/giữ bóng, cú ném và kết quả sau pha. Không mặc định hỗ trợ montage, replay, cắt cảnh, camera di động hoặc footage thiếu diễn biến.
- Cut/replay/vùng loại trừ được khai báo trước phiên; hệ thống reset/không tích lũy qua khoảng đó. Không tự gộp identity hoặc tọa độ qua nhiều góc.
- Quy ước 3x3: điểm trong cung/ném phạt là 1, ngoài cung là 2 theo [FIBA](https://about.fiba.basketball/en/our-sport/3x3-basketball). Rule profile versioned phải được xác minh cho giải đấu; không dùng profile 5x5 thay thế ngầm.
- Chưa bao gồm việc tái tạo quyết định trọng tài không thể quan sát, điểm bị hủy chỉ biết từ bàn thư ký, hoặc vị trí ngoài khung hình. Các trường hợp thiếu bằng chứng phải lộ rõ trong output và đánh giá, không được đoán thành thống kê chính thức.

Đây là tự động hóa trong phạm vi đầu vào nêu trên. Chưa có cơ sở cam kết gần 100% cho mọi video/trận đấu.

## 3. Các chức năng bắt buộc

| Thành phần | Đầu ra tự động |
|---|---|
| Detection | ball/human/rim từ model đã train, bbox/confidence, giữ source timestamps |
| Người chơi | Track, team A/B/unknown, identity gắn roster bằng bằng chứng số áo/ngoại hình theo thời gian |
| Hiệu chỉnh sân | Tọa độ ảnh/sân, vị trí hợp lệ trong ROI |
| Heatmap | Tổng thể/theo đội và vùng hoạt động, tích lũy theo thời gian quan sát |
| Ball control | Trạng thái bóng được kiểm soát/đang chuyền/đang ném/bóng tự do/không đủ bằng chứng |
| Points | Người ném, đội, release time, made/miss, loại cú ném và giá trị, sự kiện score duy nhất |
| Rebounds | Sau cú ném trượt hợp lệ, nhận người/đội giành kiểm soát hoặc controlled tip; offensive/defensive và team rebound khi đủ bằng chứng |
| Assists | Xác định pass chain, người chuyền và liên kết đến pha ghi điểm; áp dụng rule profile, không mặc định mọi đường chuyền cuối là assist |
| Event ledger | Tự chuyển candidate → provisional → auto_confirmed/void/unresolved, replay idempotent và revision |
| Dashboard/export | Video overlay, sơ đồ sân, heatmap, box score, evidence timeline, CSV/JSON |

Points/rebounds/assists là **bắt buộc**, không phải stretch features. Sửa tay là khả năng audit, không phải đường đi chính để sinh stats.

## 4. Quy tắc nhận diện cần xây

### Points

Phải nối người ném → cú ném → kết quả → giá trị/đội/cầu thủ. Vị trí phân loại cú ném xét tại release và vị trí chân hợp lệ, không lấy vị trí tiếp đất. Tách ném phạt khỏi field goal. Không cộng lại cùng pha khi bóng nảy gần rổ hoặc tracker đổi ID. Tổng điểm đội chưa gán được người phải báo unresolved attribution; không ghi công ngẫu nhiên cho người gần rổ.

### Rebounds

Nhận biết missed shot hoặc last free throw phù hợp, rồi phân biệt chạm bóng với giành kiểm soát/controlled tip. Xác định offensive/defensive theo đội ném. Xử lý loose ball, airball, block, out-of-bounds/dead ball theo rule profile và bằng chứng. Không coi người gần bóng nhất sau trượt luôn là rebounder. Team rebound phải tách khỏi tổng rebound cá nhân.

### Assists

Nhận người chuyền/người nhận, lịch sử giữ bóng, hành động sau nhận bóng và score liên quan. Shot miss, offensive rebound, turnover, deflection hoặc ngắt phiên có thể làm pass chain không còn hợp lệ. Rule profile có nguồn và bảng tình huống, bao gồm trường hợp không assist và trường hợp liên quan ném phạt nếu luật thống kê áp dụng quy định như vậy. Không thay định nghĩa assist bằng quy tắc “chuyền trong N giây trước score”.

Căn cứ khởi đầu: [FIBA Statisticians](https://about.fiba.basketball/en/fiba-game-officials/statisticians). Task dữ liệu/rules phải chốt tài liệu, phiên bản và phạm vi áp dụng trước khi gán nhãn/evaluate; chưa tuyên bố profile triển khai đã tương đương toàn bộ thống kê chính thức.

## 5. Danh tính, bất định và tính toàn vẹn

- Track ID không phải player ID. Roster có team_id/player_id/jersey_number; tự hợp nhất bằng chứng nhận dạng, có xử lý duplicate/conflict và substitution trong đoạn hỗ trợ.
- Cho phép cấu hình ban đầu, không yêu cầu người dùng click ai ném/ai rebound/ai assist cho từng pha.
- Khi thiếu bằng chứng, xuất unresolved cùng lý do/timestamp; không bịa danh tính/sự kiện. Chỉ hiện phần tự xác nhận trong bảng auto, kèm số pha chưa giải quyết.
- Unknown/unresolved phải được tính vào coverage và missed events/attribution metrics; không đạt precision cao bằng cách từ chối hầu hết pha khó.
- Event có evidence refs, source timestamp, dependencies, ruleset/model/config versions. Hủy score phải cập nhật assist liên quan; replay/restart/seek không cộng lặp.
- Log tự động bất biến theo run; chỉnh tay thành correction log riêng. Nghiệm thu tự động dùng log trước correction.
- Không đọc events.csv, review notes, tỷ số ground truth hoặc mô tả kết quả trong manifest để quyết định stats. OCR tỷ số truyền hình chỉ có thể là kênh đối chiếu riêng được thiết kế/đánh giá rõ; không thay thế attribution/PRA bằng ground truth.
- Bóng dự đoán và vị trí người nội suy phải phân biệt quan sát. Không tự xác nhận basket/control chỉ từ Kalman prediction.

## 6. Heatmap

Giữ các yêu cầu đã đề xuất: ánh xạ mặt sân từ các cặp điểm, dùng vị trí chân/ước lượng chân hợp lệ; time-weighted heatmap theo đội; số người trong vùng và player-seconds. Không tích lũy qua cuts/mất dấu dài; unknown team và phần không quan sát được báo riêng. Roster identity đủ tốt mới xuất heatmap cá nhân; không gộp track mơ hồ thành một người.

## 7. Thời gian và hiệu năng

Bắt buộc cập nhật tự động theo video đã xử lý, có độ trễ causal để xác nhận kết quả/control. Không dùng frame tương lai ngoài cửa sổ look-ahead đã khai báo khi tuyên bố streaming. Phân biệt tentative score và auto-confirmed score; báo confirmation latency.

MVP v2 vẫn là **MP4 offline trước**, live ở FPS nguồn là gate hiệu năng riêng, chưa được chứng minh. Run CPU hiện khoảng 724 ms/model-call. Không gọi video phát lại mượt là inference real-time. Nếu muốn đổi backend/model hoặc cài GPU stack, chốt phương án và quyền trước; không bắt đầu bằng việc nâng mọi dependency.

## 8. Người dùng cung cấp / agent thực hiện

| Người dùng cung cấp/xác nhận | Agent thực hiện |
|---|---|
| Video phát triển mới phù hợp, gồm đủ positive/negative cho PRA | Pipeline tự động, các module recognition và rule engine |
| Roster/số áo/đội, góc nhìn đủ để nhận dạng; quyền dùng video | Tracking/team/identity resolution và kiểm tra attribution |
| Điểm/vạch sân tham chiếu, rule profile giải đấu | Công cụ hiệu chỉnh, profile và tests tình huống |
| Nhãn độc lập: người ném/pass/control/rebound/assist, giá trị và timestamp | Schema, validator, annotation guide, evaluator |
| Review ground truth và các thay đổi dữ liệu đã khóa | Báo coverage/uncertainty, lỗi và kết quả không sửa tay |
| Quyết định khi cần thêm model/dữ liệu/tài nguyên | Thử nghiệm có kiểm soát và đề xuất dựa trên benchmark |

Task01–02 vẫn PASS trong phạm vi cũ. 10 nhãn shot hiện có **chưa đủ** cho dataset v2. Giữ nguyên codebase/data/ và split cũ; annotations/split v2 dùng namespace/version riêng. Không âm thầm đưa clip04–07 vào calibration.

## 9. Đầu ra bàn giao

Ứng dụng local/CLI, video overlay, heatmap PNG, trajectories/ball-control logs, automatic events + box score theo đội/cầu thủ, evidence timeline, correction log riêng, config/roster/ruleset snapshot, benchmark/evaluation report và README tái chạy. Metadata không có API key; media không tự upload.

## 10. Nghiệm thu và kế hoạch

Xem [PLAN.md](../PLAN.md) và [chỉ mục task](tasks/README.md). Nghiệm thu bắt buộc cả 3 module tự phát sinh sự kiện trên dữ liệu chưa dùng tuning. Tổng đúng nhờ sửa tay không thay tiêu chí tự động; bỏ một stat để kịp tiến độ không phải hoàn thành MVP.

Ngưỡng chất lượng làm việc ban đầu: event precision ≥95%, recall ≥90% cho **từng** points/rebounds/assists; chốt matching, attribution và cỡ mẫu trước test ở task04. Đây là mục tiêu lập kế hoạch, chưa phải kết quả hoặc cam kết gần 100%. Báo riêng điểm đội, điểm cá nhân, value/subtype/identity correctness và unknown rate; confidence interval/cỡ mẫu đi kèm.

Nếu không đạt, task tương ứng chưa DONE: phân tích lỗi, bổ sung calibration/huấn luyện được phép hoặc báo blocking decision. Không tự hạ ngưỡng sau khi xem test.

## 11. Ước lượng được điều chỉnh

Phạm vi tự động PRA cần data/identity/control/temporal reasoning mới. Không còn dùng mốc một tuần của Assisted Stats. Tổng ước lượng task hiện tại **32–52 ngày công, khoảng 7–11 tuần ở mức 5 ngày/tuần** nếu dữ liệu/nhãn sẵn sàng; có thể dài hơn khi cần train thêm model hoặc footage không đủ nhìn rõ. Đây là ước lượng kỹ thuật, không phải cam kết ngày bàn giao.

Không hỏi lại người dùng có muốn tự động PRA hay không: yêu cầu này đã được duyệt. Chỉ hỏi các thông tin còn thiếu hoặc quyết định cụ thể về dữ liệu, tài nguyên, luật và thay đổi phạm vi.
