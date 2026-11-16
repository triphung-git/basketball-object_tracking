# Basketball Object Tracking — Phân tích video bóng rổ

Dự án phân tích video bóng rổ trên máy cục bộ, kết hợp phát hiện và theo dõi đối tượng,
nhận diện cầu thủ, bản đồ nhiệt di chuyển và xử lý sự kiện ghi điểm, bắt bóng sau cú ném trượt,
kiến tạo (PTS/REB/AST). Repository cung cấp mã nguồn, tài liệu kỹ thuật và một gói demo
có thể xem bằng giao diện web tương tác.

**Trạng thái hiện tại: `DEMO_PARTIAL` — demo hoàn thiện một phần; chất lượng AI:
`NOT_ACCEPTED` — chưa đạt nghiệm thu.** Demo có thể mở và phát lại kết quả đã xử lý.
Độ chính xác trên video thực tế và khả năng xử lý thời gian thực vẫn cần được cải thiện,
đánh giá thêm. Kết quả kiểm thử phần mềm không thay thế đánh giá độ chính xác nhận diện.

## Các thành phần chính

- Phát hiện và theo dõi bóng, người, vành rổ theo từng khung hình.
- Phân loại đội, tổng hợp bằng chứng đọc số áo và xác định danh tính cầu thủ.
- Hiệu chuẩn mặt sân, ánh xạ vị trí và tạo bản đồ nhiệt di chuyển.
- Xử lý các sự kiện ném rổ, ghi điểm, rebound và assist; tổng hợp bảng thống kê.
- Xem video có lớp chú thích, dòng thời gian sự kiện, bản đồ nhiệt và xuất dữ liệu.

Các thành phần trên đã có trong mã nguồn; mức độ chính xác và đầy đủ của kết quả
phụ thuộc vào video, cấu hình và chất lượng nhận diện. Xem
[báo cáo QA hiện hành](docs/reports/qa-project-review-20261116.md) để biết phạm vi đã kiểm chứng.

## Cài đặt và mở demo

Hướng dẫn dưới đây dùng **Windows, PowerShell và Python 3.12**. Thực hiện các lệnh
từ thư mục gốc của repository sau khi tải mã nguồn:

```powershell
git clone https://github.com/triphung-git/basketball-object_tracking.git
cd basketball-object_tracking
py -3.12 -m venv codebase/.venv
codebase/.venv/Scripts/python.exe -m pip install -r codebase/requirements-view.txt
codebase/.venv/Scripts/python.exe run_demo.py --check
.\run_demo.bat
```

Lệnh `--check` kiểm tra tính toàn vẹn của gói demo trước khi mở giao diện.
Bạn cũng có thể khởi chạy trực tiếp bằng Python:

```powershell
codebase/.venv/Scripts/python.exe run_demo.py --preset default --mode view --open-browser
```

**Chế độ xem demo sử dụng kết quả đã xử lý sẵn.** Bộ thư viện trong
`requirements-view.txt` đủ để mở giao diện này; không cần API key, tải trọng số
nhận diện hoặc có video trận đấu gốc. Video phát lại là file `annotated.mp4`
đi kèm gói demo.

Gói demo nằm tại `codebase/outputs/demo-completion-20261116/demo-bundle-qa-v2/`.
Giữ nguyên vị trí này để launcher mặc định tìm đúng dữ liệu. File manifest lưu
danh sách, kích thước và mã băm các file để kiểm tra tính toàn vẹn. Một số đường dẫn
tuyệt đối trong metadata ghi lại máy đã tạo kết quả; trình xem sử dụng video đi kèm
và danh sách cầu thủ trong repository khi chạy trên máy khác.

## Phân tích video riêng

Để chạy nhận diện trên video mới, cài bộ thư viện đầy đủ và tạo file cấu hình cục bộ:

```powershell
codebase/.venv/Scripts/python.exe -m pip install -r codebase/requirements.txt
Copy-Item codebase/.env.example codebase/.env
```

Lệnh sao chép dành cho lần thiết lập đầu tiên; giữ file `.env` hiện có nếu bạn đã
cấu hình. Điền Roboflow API key trong file này và không đưa key vào Git.

Chuẩn bị video đầu vào, danh sách cầu thủ và cấu hình hiệu chuẩn sân phù hợp.
Hiệu chuẩn bị ràng buộc với nguồn video và phạm vi thời gian đã kiểm chứng;
cần thiết lập lại khi dùng video không tương ứng. Video gốc, trọng số mô hình
và bộ dữ liệu huấn luyện được quản lý riêng.

Xem [hướng dẫn sử dụng](docs/USER_GUIDE.md) để chạy phân tích video, cấu hình
hiệu chuẩn, xuất dữ liệu và xử lý lỗi thường gặp.

## Cấu trúc repository

| Đường dẫn | Nội dung |
| --- | --- |
| `run_demo.py`, `run_demo.bat` | Khởi chạy demo từ thư mục gốc |
| `codebase/src/basketball_scoreboard/` | Mã nguồn nhận diện, tracking, danh tính, sự kiện, bản đồ nhiệt và giao diện |
| `codebase/scripts/` | Công cụ dòng lệnh, chuẩn bị dữ liệu, rà soát nhãn, đánh giá và huấn luyện |
| `codebase/configs/` | Cấu hình chạy, danh sách cầu thủ, hiệu chuẩn sân và đánh giá |
| `codebase/tests/` | Kiểm thử phần mềm và kiểm tra kết quả thí nghiệm đã lưu |
| `codebase/data/` | Danh mục dữ liệu, nhãn, lược đồ và thông tin phân chia tập dữ liệu |
| `codebase/outputs/demo-completion-20261116/demo-bundle-qa-v2/` | Gói demo mẫu đã kiểm tra tính toàn vẹn |
| `docs/` | Đặc tả, hướng dẫn, quyết định kỹ thuật, báo cáo và tài liệu bàn giao |

Git bỏ qua thông tin bí mật, môi trường Python, bộ nhớ đệm, video gốc, dữ liệu
huấn luyện, trọng số mô hình và các output thí nghiệm khác. Các file này vẫn được
giữ cục bộ trong môi trường phát triển khi cần sử dụng.

## Kiểm tra và kiểm thử

Kiểm tra gói demo bằng lệnh `run_demo.py --check` trong phần cài đặt. Để chạy bộ
kiểm thử phát triển, cài bộ thư viện đầy đủ và `pytest`, sau đó thực hiện:

```powershell
codebase/.venv/Scripts/python.exe -m pip install pytest
codebase/.venv/Scripts/python.exe -m pytest codebase/tests -q
```

Một số bài kiểm thử cần output thí nghiệm cũ, video gốc hoặc mô hình đã lưu cục bộ.
Bản clone mới chưa có đủ dữ liệu để chạy toàn bộ các bài kiểm thử đó. Kết quả
**539 bài kiểm thử đạt** trong báo cáo QA được đo tại môi trường phát triển.
Việc kiểm tra đóng gói và chạy demo trong môi trường Python mới được ghi riêng tại
[báo cáo đưa dự án lên GitHub](docs/reports/github-publication-20261116.md).

## Tài liệu tham khảo

- [Hướng dẫn sử dụng hiện hành](docs/USER_GUIDE.md).
- [Báo cáo QA và các giới hạn đã xác minh](docs/reports/qa-project-review-20261116.md).
- [Hướng dẫn phát triển](docs/DEVELOPMENT.md).
- [README kỹ thuật và các lệnh thí nghiệm trước đây](codebase/README.md).
- [Báo cáo đóng gói dự án](docs/reports/github-publication-20261116.md).

Các báo cáo theo ngày và hướng dẫn thí nghiệm cũ được giữ để tra cứu lịch sử.
Ưu tiên hướng dẫn sử dụng hiện hành và báo cáo QA khi xác định cách chạy demo
cũng như mức độ hoàn thiện của dự án.
