# MVP v2 đề xuất — Basketball Heatmap & Assisted Stats

Ngày: 2026-11-01. Trạng thái: **DRAFT — CHỜ NGƯỜI DÙNG DUYỆT**.

Đây là đề xuất phạm vi sản phẩm, chưa thay thế PLAN.md hoặc cho phép triển khai các task tiếp theo. Sau khi người dùng duyệt, mới cập nhật kế hoạch, task, prompt và hợp đồng bàn giao tương ứng. Kết quả nghiệm thu task01–02 được giữ nguyên với đúng giới hạn đã công bố.

## 1. Mục tiêu sản phẩm

Xây dựng ứng dụng phân tích video bóng rổ: tự động phát hiện/theo dõi người chơi, hiển thị vị trí trên sơ đồ sân, tích lũy heatmap theo đội và thống kê vùng hoạt động. Đồng thời cung cấp bảng **points, rebounds, assists** được cập nhật từ các sự kiện do người dùng nhập và xác nhận khi xem video.

**Cam kết cốt lõi:** tự động hóa phần vị trí/heatmap; hỗ trợ ghi nhận và tổng hợp stats có lịch sử kiểm chứng. MVP chưa tự xác định đầy đủ points/rebounds/assists từ hình ảnh.

Người dùng mục tiêu: sinh viên, người phân tích hoặc huấn luyện viên muốn xem một đoạn thi đấu và tạo báo cáo trực quan có thể chỉnh sửa, xuất và giải thích nguồn số liệu.

## 2. Phạm vi đầu vào được hỗ trợ

Phiên bản đầu ưu tiên **video 3x3, một rổ/nửa sân, camera cố định**, hai đội có màu áo phân biệt. Có thể dùng video tập một người để kiểm thử kỹ thuật, nhưng đó chưa phải demo đầy đủ phân đội/thống kê trận.

| Đầu vào | Phạm vi MVP |
|---|---|
| MP4 cục bộ | Bắt buộc |
| Một đoạn quay liên tục, thấy rõ khu vực sân cần phân tích | Bắt buộc cho demo chính |
| Góc cao hoặc góc chéo, thấy được chân người chơi | Ưu tiên để ánh xạ vị trí |
| Camera ổn định, không đổi zoom trong đoạn phân tích | Điều kiện baseline |
| Nhiều đoạn/góc quay | Người dùng tách/chọn từng đoạn và hiệu chỉnh riêng; không tự gộp tọa độ giữa góc |
| Audio | Không dùng làm căn cứ tự động ghi stats |
| Replay/cận cảnh/đoạn ngoài sân | Người dùng đánh dấu bỏ qua; khoảng này không tích lũy heatmap hoặc sự kiện mới |
| Webcam/live stream | Phần mở rộng sau khi benchmark, không bắt buộc nghiệm thu MVP |

Ứng dụng không mặc định hỗ trợ mọi trận đấu hoặc mọi video highlights. Mọi kết quả đều gắn với **đoạn và vùng sân quan sát được**, không tự khôi phục phần thi đấu bị thiếu.

## 3. Chức năng bắt buộc và mức tự động hóa

| Chức năng | Máy thực hiện | Người dùng thực hiện |
|---|---|---|
| Phát hiện người/bóng/rổ | Chạy model hiện có, hiển thị bbox | Kiểm tra cấu hình đầu vào |
| Tracking người chơi | Nối vị trí thành track trong đoạn quay | Có thể sửa liên kết/gán lại khi ID bị đứt |
| Phân đội | Phân loại màu áo trong sân, giữ trạng thái unknown khi thiếu bằng chứng | Chọn màu mẫu đội A/B và sửa khi cần |
| Hiệu chỉnh sân | Biến đổi điểm ảnh sang sơ đồ sân sau cấu hình | Chọn tối thiểu 4 cặp điểm tương ứng trên cùng mặt sân, không suy biến |
| Heatmap tổng thể/theo đội | Tích lũy thời gian quan sát ở các vị trí hợp lệ | Xác nhận vùng sân và vùng loại trừ |
| Thống kê vùng | Tính thời gian hiện diện và số người quan sát được | Chọn vùng phân tích |
| Points | Tự tổng hợp từ sự kiện ghi điểm đã duyệt | Xác nhận có điểm, đội, người ghi và giá trị |
| Rebounds | Tự tổng hợp offensive/defensive rebound cá nhân đã duyệt | Xác định người rebound và loại; có tùy chọn team rebound không gán cầu thủ |
| Assists | Tự tổng hợp assist gắn với sự kiện ghi điểm | Xác nhận người chuyền và tình huống có được tính assist |
| Sửa sai/undo | Cập nhật lại các bảng và lưu lịch sử | Chỉnh hoặc hủy sự kiện |
| Xuất kết quả | Xuất ảnh, video/log và bảng stats | Chọn phiên/đoạn muốn xuất |

**Điểm cần duyệt rõ:** bảng points/rebounds/assists có đầy đủ chức năng nhập–duyệt–tổng hợp–sửa. MVP không hứa tự phát hiện đúng các sự kiện đó. Đề xuất sự kiện tự động là phần mở rộng, không âm thầm trở thành điều kiện bắt buộc của tuần đầu.

## 4. Heatmap và thống kê vị trí

### 4.1. Đầu ra tự động

- Bbox, track ID tạm thời và đội A/B/unknown trên video.
- Sơ đồ nửa sân, các vị trí hiện tại và đường di chuyển ngắn theo đội.
- Heatmap tổng thể và riêng từng đội trên sơ đồ sân, cập nhật theo thời gian video đã xử lý.
- Số cầu thủ đang quan sát được trong từng vùng đã cấu hình.
- Tổng thời gian hiện diện của người chơi thuộc từng đội trong vùng, đơn vị **player-seconds**.

Ví dụ: ba cầu thủ cùng đứng trong một vùng trong 2 giây tạo 6 player-seconds. Chỉ số này không phải 6 giây thi đấu hay thời gian kiểm soát bóng. Tỷ lệ phân bố theo vùng phải ghi rõ mẫu số là tổng thời gian quan sát người chơi được phân tích.

### 4.2. Nguyên tắc tính

- Ước lượng vị trí từ điểm gần chân của bbox; đây chưa phải phép đo chân chính xác bằng pose.
- Heatmap tính trọng số theo timestamp/Δt, không đếm frame đơn thuần. Video VFR phải dùng presentation timestamp.
- Điểm ngoài vùng sân/ánh xạ không hợp lệ không được cộng. Người ngoài sân không được mặc định coi là cầu thủ.
- Không tích lũy qua cut, khoảng mất dấu dài hoặc vùng chưa quan sát. Không coi khoảng ngoài khung hình là thời gian đứng yên ở vị trí cuối.
- Track nội suy ngắn phải được đánh dấu; thời gian/vị trí chỉ dự đoán không tự trở thành bằng chứng quan sát. Baseline heatmap dùng quan sát hợp lệ.
- Unknown team báo riêng và không được âm thầm chia sang A/B. Trọng tài/người ngoài sân có cách loại hoặc sửa nhãn.
- Đổi đội, loại một track hoặc sửa liên kết cần có khả năng tính lại phần heatmap bị ảnh hưởng từ trajectory log; không chỉ sửa nhãn hiển thị cuối.

### 4.3. Chưa bắt buộc

Heatmap xuyên toàn trận cho từng danh tính cầu thủ, quãng đường theo mét và tốc độ vận động chưa nằm trong đầu ra bắt buộc. Các chỉ số này cần kiểm soát identity, tỷ lệ sân và nhiễu tốt hơn. Có thể bổ sung sau khi baseline đạt.

## 5. Bảng points, rebounds, assists hoạt động thế nào?

### 5.1. Danh tính và cấu hình

Người dùng tạo roster tối thiểu: player_id, tên hoặc số áo, đội A/B. Có thể gán track đang thấy vào roster để hỗ trợ chọn người, nhưng không tự coi track ID là danh tính thật.

Thay góc quay hoặc mất dấu lâu có thể cần gán lại. Không tự nhận số áo/tên bằng OCR trong MVP. Không cộng stats cá nhân cho một track chưa được xác nhận danh tính; có thể để sự kiện pending hoặc team-only khi phù hợp.

### 5.2. Sự kiện thống kê

- **Points:** người dùng chọn timestamp, đội, cầu thủ nếu biết và giá trị điểm. Giá trị cho phép cấu hình theo thể thức; không tự suy ra luật 3x3/5x5 từ video. Khi thiếu người ghi, tổng điểm đội và phần chưa quy cho cá nhân phải được hiển thị rõ.
- **Rebound:** người dùng ghi timestamp, đội, cầu thủ hoặc team rebound, loại offensive/defensive. Team rebound không được cộng nhầm vào tổng rebound cá nhân.
- **Assist:** người dùng chọn người chuyền và liên kết tới một sự kiện ghi điểm được xác nhận. Không tự lấy mọi đường chuyền cuối làm assist; quy tắc ghi thống kê áp dụng được ghi trong cấu hình/hướng dẫn phiên.

AI không thay người dùng diễn giải các tình huống tranh chấp, điểm bị hủy hoặc trường hợp đặc biệt. Trường hợp chưa rõ giữ pending, chưa cộng vào bảng confirmed.

### 5.3. Toàn vẹn và lịch sử

- Mỗi sự kiện có ID, timestamp nguồn, người tham gia, trạng thái pending/confirmed/void và lịch sử sửa.
- Điểm/stats được tính từ log confirmed, không tăng bộ đếm không truy vết.
- Không áp dụng trùng cùng event ID. Có thể sửa, hủy, undo và tải lại phiên mà không đổi tổng ngoài ý muốn.
- Khi hủy sự kiện ghi điểm, assist liên kết phải được hủy hoặc chuyển chờ review nhất quán; không để assist mồ côi trong tổng confirmed.
- Tách stats đề xuất và stats đã xác nhận nếu sau này thêm AI gợi ý. Không dùng kết quả sửa tay để báo độ chính xác tự động.

## 6. Trải nghiệm sử dụng dự kiến

1. Chọn video và đoạn thời gian phân tích.
2. Chọn sơ đồ sân/phạm vi nửa sân, đánh dấu vùng sân và điểm hiệu chỉnh.
3. Chọn màu mẫu hai đội, nhập roster nếu cần stats cá nhân, chọn quy ước điểm của phiên.
4. Chạy phân tích. Giao diện thể hiện video, sơ đồ sân, heatmap và bảng stats.
5. Pause/seek đoạn đã xử lý; nhập hoặc duyệt points/rebounds/assists, sửa đội/track khi cần.
6. Tiếp tục phân tích hoặc xuất báo cáo. Seek lại không làm nhân đôi heatmap hoặc sự kiện; thay cấu hình cần tạo revision hoặc tính lại phần liên quan.

Một giao diện local tối thiểu, dễ thao tác là đủ. Không bắt buộc website triển khai cloud, tài khoản, database server hoặc nhiều người dùng đồng thời.

## 7. “Cập nhật theo thời gian” trong MVP

**Bắt buộc:** heatmap/stats cập nhật tăng dần theo timestamp video đã phân tích; stats confirmed cập nhật sau khi người dùng xác nhận. Hiển thị tiến độ và phân biệt thời gian nội dung video với thời gian xử lý trên máy.

**Chưa cam kết:** xử lý live ở FPS nguồn hoặc thống kê chính thức không cần con người. Baseline ONNX CPU gần nhất khoảng 724 ms/model-call; cần benchmark/tối ưu riêng để biết tốc độ toàn pipeline.

Nếu tối ưu giúp chạy live, phải đo throughput và độ trễ bền vững, báo frame bị bỏ và tác động chất lượng. Không gọi việc phát lại một video đã xử lý là inference real-time. Không tự cài GPU stack hoặc đổi model để đạt mốc tốc độ khi chưa có quyết định phù hợp.

## 8. Bạn cần cung cấp, tôi sẽ xây dựng

| Bạn cung cấp hoặc xác nhận | Tôi xây dựng |
|---|---|
| Một đoạn 3x3 camera ổn định, thấy hai đội và chân người chơi | Pipeline detection/tracking và trajectory log |
| Quyền sử dụng video; đánh dấu replay/cut hoặc đoạn ngoài phạm vi | Hiệu chỉnh sân, ROI, timebase và cơ chế bỏ đoạn |
| Các điểm/vạch sân tham chiếu nhìn rõ, sơ đồ nửa sân phù hợp | Công cụ chọn điểm và kiểm tra phép ánh xạ |
| Màu áo mẫu, roster nếu muốn stats theo người | Phân đội, gán track thủ công, trạng thái unknown |
| Quy ước điểm và bộ quy tắc thống kê của phiên | Màn hình nhập/duyệt stats, bộ tổng hợp và undo |
| Rà soát nhãn vị trí/đội và các sự kiện làm chuẩn đánh giá | Công cụ kiểm tra, xuất dữ liệu, benchmark và báo cáo |

Task01 tái sử dụng model/runtime/code smoke. Task02 giữ nguyên nhãn shot và split đã khóa; cần bổ sung nhãn vị trí/đội cho mục tiêu mới. Clip02 một người chưa đủ làm demo phân hai đội. Không chuyển clip04–07 từ holdout sang calibration âm thầm: cần video phát triển mới phù hợp hoặc người dùng duyệt revision split trước khi dùng để chỉnh hệ thống.

## 9. Đầu ra bàn giao

- Ứng dụng local chạy MP4, có hướng dẫn cài/chạy và cấu hình mẫu.
- Video overlay detection/tracking và thông tin đội; sơ đồ sân/heatmap cập nhật trong giao diện.
- Ảnh heatmap tổng thể/theo đội, có chú giải và khoảng thời gian phân tích.
- CSV trajectory: timestamp, track, đội, vị trí ảnh/sân, trạng thái quan sát/dự đoán.
- CSV thống kê vùng và thống kê theo đội/cầu thủ đã xác nhận, định nghĩa rõ đơn vị/mẫu số.
- Log sự kiện points/rebounds/assists, lịch sử sửa và trạng thái xác nhận; cấu hình roster/hiệu chỉnh để tải lại phiên.
- Run metadata: video fingerprint, model/runtime, cấu hình, coverage, timings và giới hạn.
- Báo cáo đánh giá, video demo và tài liệu thao tác.

Mọi media/keys giữ local theo quy tắc hiện có. Không đưa secrets vào log hoặc tự upload video.

## 10. Tiêu chí nghiệm thu đề xuất

### Luồng sử dụng và tính đúng của dữ liệu

- Chạy hết ít nhất một đoạn phù hợp có hai đội, lưu/tải lại phiên và xuất đầy đủ artifacts.
- Ánh xạ điểm sân đúng orientation/tỷ lệ theo cấu hình; ROI loại được người ngoài sân trong bộ kiểm tra.
- Heatmap phản ánh thời gian quan sát; pause/seek/tải lại không cộng lặp. Đoạn excluded và khoảng mất dấu không bị cộng như thời gian quan sát.
- Bảng points/rebounds/assists khớp log confirmed; pending/void, undo, team-only và quan hệ assist–score được kiểm thử bằng các ca có expected result.
- Không dùng ground truth hoặc manifest notes để suy kết quả tự động. Đánh giá nhãn/đội/heatmap trước chỉnh tay và thống kê sau xác nhận là hai nhóm kết quả riêng.

### Chất lượng CV và khả năng giải thích

- Chuẩn bị tối thiểu 30 frame tham chiếu có người dùng rà soát, có đủ hai đội và trường hợp che khuất/unknown; không chọn chỉ các frame dễ. Chia dữ liệu phát triển và kiểm tra theo đoạn/nguồn, ghi rõ cỡ mẫu.
- **Mục tiêu đề xuất để duyệt:** độ chính xác gán đội trên các trường hợp đủ điều kiện đạt ít nhất 90%; bắt buộc báo thêm tỷ lệ unknown và số người bị bỏ sót để không nâng điểm bằng cách từ chối hầu hết trường hợp.
- **Mục tiêu vị trí đề xuất:** trung vị sai số vị trí trên sơ đồ sân không vượt 5% chiều rộng vùng sân hiệu chỉnh, đo trên các điểm chân nhìn rõ được gán nhãn độc lập. Báo số điểm bị loại/không định vị được; không đánh đồng lỗi hiệu chỉnh landmark với lỗi định vị cầu thủ.
- Báo ID switches/đứt track trên đoạn kiểm tra, ví dụ lỗi và phạm vi thời gian/diện tích quan sát. Không công bố heatmap cá nhân xuyên trận khi chưa giữ được identity.
- Ghi FPS xử lý và latency thực tế trên máy cụ thể. Real-time không phải điều kiện pass của bản MVP offline.

Các mốc chất lượng trên là mục tiêu nghiệm thu được đề xuất, chưa phải kết quả đo. Nếu không đạt, phải báo phần chưa đạt và phương án sửa/giảm phạm vi để người dùng quyết định; không tự đổi ngưỡng hoặc dùng test để tối ưu rồi báo pass.

## 11. Những gì không nằm trong MVP bắt buộc

- Tự động points/rebounds/assists chính xác gần 100% từ trận bất kỳ.
- Nhận danh tính bằng số áo/khuôn mặt và giữ ID qua mọi góc quay.
- Heatmap toàn sân từ video chỉ nhìn một phần sân, tự khôi phục vị trí ngoài hình.
- Xử lý camera động/cắt cảnh/replay hoàn toàn tự động.
- Possession, steals, blocks, fouls, đồng hồ trận/shot clock và quyết định trọng tài tự động.
- Khoảng cách/tốc độ chính xác theo mét, nhiều camera, dashboard cloud hoặc live nhiều người dùng.

Phần mở rộng ưu tiên sau baseline: gợi ý bóng vào rổ để duyệt points; tiếp theo là ứng viên rebound, sau đó assist. Mỗi phần cần nhãn và đánh giá riêng; không đưa tất cả vào cam kết một tuần.

## 12. Thời hạn và quyết định duyệt

Mục tiêu khoảng **một tuần làm việc tập trung kể từ khi duyệt phạm vi và có video/nhãn đầu vào phù hợp**. Đây chưa phải lịch cam kết: sau khi duyệt sẽ lập plan để kiểm tra khối lượng giao diện review, hiệu chỉnh/tracking và dữ liệu. Nếu cần tự động cả ba stats hoặc live ở FPS nguồn, phải mở lại ước lượng.

### Phương án tôi đề xuất chốt

**Heatmap theo đội + thống kê vùng tự động; points/rebounds/assists có nhập–duyệt–tổng hợp; MP4 camera ổn định; offline trước.**

Bạn có thể duyệt bằng câu:

> Duyệt MVP v2 theo phương án đề xuất. Proceed lập plan cho các task tiếp theo.

Nếu muốn chỉnh trước khi duyệt, chỉ cần nêu các tính năng bắt buộc thay đổi, đặc biệt: mức tự động hóa stats, yêu cầu live, thể thức 3x3/5x5 và phạm vi camera. Chưa tiến hành lập lại tasks hoặc triển khai MVP v2 cho đến khi có phản hồi duyệt.
