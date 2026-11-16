# Hướng dẫn gán nhãn và rà soát sự kiện ném bóng rổ (Task 02)

Tài liệu này quy định chuẩn gán nhãn sự kiện ném bóng rổ (`shot event`), quy tắc xác định mốc thời gian, tiêu chí phân loại kết quả, quy trình kiểm soát chất lượng từ bản nháp (`draft`) đến tập dữ liệu chuẩn đã duyệt (`ground truth`), và hướng dẫn người dùng rà soát các pha ném hiện có.

---

## 1. Mục tiêu và phạm vi

1. **Mục tiêu**: Chuẩn bị tập dữ liệu sự kiện có nguồn gốc rõ ràng, không rò rỉ thông tin giữa tập hiệu chỉnh (`calibration`) và tập kiểm thử độc lập (`test`).
2. **Phạm vi Task 02**:
   - Quản lý metadata video, thời lượng, FPS, mã hash định danh.
   - Gán nhãn sự kiện cấp lượt ném (thời điểm bắt đầu, kết thúc, thời điểm ghi điểm, kết quả).
   - Thiết lập vùng thời gian đánh giá (`coverage`) và loại trừ các đoạn camera di chuyển mạnh/ngoài khung hình.
   - **Không bao gồm**: Huấn luyện lại model, gán nhãn bounding box từng frame, chạy bộ tracking/shot detector tự động (thuộc các task 03–07).

---

## 2. Cấu trúc thư mục dữ liệu

Tất cả các file dữ liệu được lưu trữ tại `codebase/data/`:

| Đường dẫn | Vai trò | Trách nhiệm chỉnh sửa |
|---|---|---|
| `codebase/data/manifest.csv` | Danh mục toàn bộ video, FPS, kích thước, thời lượng stream, camera_id, session_id, hash SHA-256. | Script `prepare_dataset.py` sinh tự động. |
| `codebase/data/annotations/events.draft.csv` | Chứa các pha ném ứng viên do AI Agent hoặc người dùng soạn thảo sơ bộ (chưa phê duyệt). | AI Agent / Người dùng soạn thảo. |
| `codebase/data/annotations/events.csv` | **Ground truth chính thức**: Chỉ chứa các sự kiện đã được con người rà soát và phê duyệt. Task 05/07 đọc file này. | Người dùng phê duyệt (Agent không tự ý copy). |
| `codebase/data/annotations/reviews.csv` | Sổ theo dõi trạng thái rà soát (`review ledger`), người duyệt, thời gian duyệt và lý do. | Cập nhật cùng lúc khi duyệt nhãn vào `events.csv`. |
| `codebase/data/annotations/coverage.csv` | Định nghĩa các khoảng video đã rà soát đầy đủ (`fully_reviewed`), đang chờ (`needs_review`) hoặc loại trừ (`excluded`). | Xác định vùng thời gian hợp lệ cho Task 07. |
| `codebase/data/splits.json` | Phân chia calibration / test theo nhóm nguồn độc lập, ghi nhận mức tiếp xúc (`exposure`). | Khóa (`locked`) sau khi chốt với người dùng. |

---

## 3. Schema sự kiện chuẩn (`events.csv` & `events.draft.csv`)

Mỗi dòng đại diện cho một lượt ném bóng rổ (`shot event`):

```csv
video_id,shot_id,start_s,end_s,result,score_time_s,team,point_value,notes
```

### Chi tiết các trường:

1. **`video_id`** *(chuỗi, bắt buộc)*:
   - Phải khớp chính xác với `video_id` đã khai báo trong `manifest.csv` (ví dụ: `clip01`, `clip02`).
2. **`shot_id`** *(chuỗi, bắt buộc)*:
   - Định danh duy nhất cho từng pha ném trong cùng một video (ví dụ: `s001`, `s002`).
   - Cặp `(video_id, shot_id)` là khóa chính không được trùng lặp.
3. **`start_s`** *(số thực, giây, bắt buộc)*:
   - Thời điểm người ném bắt đầu động tác ném (nhấc bóng lên, chuẩn bị bật nhảy hoặc vào tư thế phát lực).
   - Đơn vị tính: giây kể từ đầu video stream (`0.0 <= start_s < end_s`).
4. **`end_s`** *(số thực, giây, bắt buộc)*:
   - Thời điểm kết thúc lượt ném: bóng rơi xuống chạm đất, hoặc chạm tay cầu thủ bắt bóng bật bảng/rebound, hoặc bóng bay ra ngoài khung hình.
   - Bắt buộc: `start_s < end_s <= duration_s` (trong đó `duration_s` là thời lượng video stream).
5. **`result`** *(chuỗi, bắt buộc)*:
   - Chỉ được nhận 1 trong 3 giá trị sau:
     - **`made`**: Có bằng chứng trực quan rõ ràng bóng đi qua rổ từ trên xuống.
     - **`miss`**: Quan sát đầy đủ thấy bóng bật vành/bảng hoặc bay trượt ra ngoài mà không vào rổ.
     - **`uncertain`**: Có động tác ném nhưng hình ảnh bị che khuất hoặc camera không thấy rõ kết quả bóng vào hay trượt. Không dùng `uncertain` để biểu thị "chưa xem".
6. **`score_time_s`** *(số thực, giây)*:
   - **Bắt buộc đối với `made`**: Thời điểm tâm (xích đạo) của quả bóng đi qua mặt phẳng vành rổ từ trên xuống dưới.
   - Bắt buộc phải nằm trong khoảng: `start_s <= score_time_s <= end_s`.
   - **Bắt buộc để trống (ô rỗng) đối với `miss` và `uncertain`**.
7. **`team`** *(chuỗi, bắt buộc)*:
   - `solo` (chế độ tập một mình/mặc định MVP), `A` hoặc `B`.
8. **`point_value`** *(số nguyên, bắt buộc)*:
   - Giá trị điểm của lượt ném (`1`, `2`, hoặc `3`). Mặc định MVP là `2`.
9. **`notes`** *(chuỗi, tùy chọn)*:
   - Mô tả đặc điểm pha ném (ví dụ: ném trực tiếp, đập bảng `bank shot`, ném chạm vành `rim bounce`, góc khuất, sai số ước tính timestamp).

---

## 4. Quy tắc xác định thời điểm và xử lý tình huống đặc biệt

### 4.1. Quy đổi thời gian và FPS
- Kiểm tra nghiệm thu 2026-11-01 xác nhận clip04–07 có khoảng PTS biến thiên khoảng 0,0333–0,0700 giây. FPS trong manifest là trung bình; không dùng `frame_idx / avg_fps` làm đồng hồ cho các clip này. Task03/07 cần dùng presentation timestamp trừ mốc PTS đầu video (đọc qua PyAV/FFmpeg hoặc decoder có timestamp đã kiểm chứng).
- Các số frame trong phần mô tả nhãn broadcast chỉ là tham chiếu gần đúng, không thay thế score_time_s đã duyệt. Audit so sánh chỉ số suy từ FPS với PTS cho clip06 có sai lệch đến khoảng 65 ms; chưa thay đổi nhãn đã khóa. Nếu cần sửa ground truth, mở revision và yêu cầu người dùng duyệt.
- Thời gian tính theo **video stream** (không dùng audio container duration).
- Với video 60 FPS (như `clip02`): Mỗi frame cách nhau `1/60 ≈ 0.0167` giây. Thời điểm `score_time_s = frame_idx / fps`.
- Với video 24 FPS (như `clip01`): Mỗi frame cách nhau `1/24 ≈ 0.0417` giây.
- Sai số ước tính cho phép: Ghi chú trong `notes` nếu frame bị mờ chuyển động (`motion blur`).

### 4.2. Phân biệt các tình huống bóng chạm vành
- **Bóng bật vành rồi vào**: Gán `made`. `score_time_s` là thời điểm bóng đi qua mặt phẳng vành sau các cú nảy.
- **Bóng bật vành rồi ra ngoài**: Gán `miss`. Bắt buộc `score_time_s` để trống.
- **Bóng đi từ dưới rổ lên**: Không tính là lượt ném vào. Không được gán `made`.
- **Cầu thủ chuyền bóng hoặc dẫn bóng**: Không gán nhãn shot event.
- **Pha quay chậm / Replay**: Không được gán thành lượt ném mới. Nếu có đoạn replay, đánh dấu vùng đó trong `coverage.csv` là `excluded`.

---

## 5. Quy trình rà soát và chuyển từ Draft sang Ground Truth

```
[Khảo sát video gốc] 
        │
        ▼
[events.draft.csv] (Trạng thái: needs_review)
        │
        ▼ (Người dùng mở video, kiểm tra timestamp & kết quả)
[reviews.csv] ──► Cập nhật reviewer, timestamp, lý do
        │
        ▼ (Chỉ sau khi được duyệt)
[events.csv] (Ground Truth chính thức dùng cho Task 05 & Task 07)
```

1. **Bước 1**: Xem xét các pha ném ứng viên trong `codebase/data/annotations/events.draft.csv`.
2. **Bước 2**: Mở video gốc tại mốc thời gian chỉ định (xem Bảng kiểm tra dưới đây).
3. **Bước 3**: Nếu đồng ý với kết quả:
   - Thêm dòng vào `codebase/data/annotations/events.csv`.
   - Cập nhật dòng tương ứng trong `codebase/data/annotations/reviews.csv`:
     - `review_status`: `approved`
     - `reviewer`: Tên/ID người duyệt (ví dụ: `user`)
     - `reviewed_at_utc`: Thời gian ISO (ví dụ: `2026-10-31T17:00:00Z`)
     - `rejection_or_approval_reason`: Ghi chú xác nhận.
4. **Bước 4**: Chạy công cụ kiểm tra tính toàn vẹn:
   ```powershell
   & "codebase\.venv\Scripts\python.exe" codebase/scripts/validate_dataset.py --codebase-root codebase
   ```

---

## 6. Bảng theo dõi và rà soát các pha ném

### 6.1. Các pha ném đã được người dùng phê duyệt chính thức (`events.csv`)

| Video ID | Shot ID | Mốc thời gian | Kết quả | `score_time_s` | Đội / Điểm | Chi tiết quan sát & Đối chiếu Bảng điểm | Trạng thái |
|---|---|---|---|---|---|---|---|
| **`clip01`** | `s001` | **3.80s – 7.70s** | **`miss`** | *(trống)* | solo / 2đ | Sân đêm. Cầu thủ bên trái ném bóng. Bóng chạm vành trước lúc t = 6.0–6.2s, nảy văng sang phải lúc t = 7.08s. Không vào rổ. | **`approved`** (User đã duyệt) |
| **`clip02`** | `s001` | **3.80s – 7.30s** | **`made`** | **6.38s** | solo / 2đ | Cầu thủ áo xanh ném đập bảng (`bank shot`). Bóng cắt mặt phẳng vành rổ lúc **t = 6.38s** (frame 383), rơi khỏi lưới ~6.8s. | **`approved`** (User đã duyệt) |
| **`clip03`** | `s001` | **1.50s – 4.80s** | **`made`** *(camera động)* | **4.04s** | solo / 2đ | Cầu thủ áo trắng bật ném. Bóng chạm bảng và lọt lưới tại t = 4.04s (frame 101). Sau 4.80s camera di chuyển/xoay vòng -> loại trừ. | **`approved`** (User đã duyệt) |
| **`clip04`** | `s001` | **7.20s – 10.80s** | **`miss`** | *(trống)* | Blue #14 (TP.HCM) / 2đ | Áo xanh #14 ném 2 điểm từ cánh phải ngoài vạch bán nguyệt; bóng bay chệch hoàn toàn khỏi rổ (airball); không vào rổ; bảng điểm giữ nguyên **TP.HCM 3 - Hà Nội 4** suốt clip. | **`approved`** (User đã duyệt) |
| **`clip05`** | `s001` | **7.20s – 10.50s** | **`miss`** | *(trống)* | White #11 (Hà Nội) / 2đ | Áo trắng #11 ném 2 điểm từ ngoài vạch bán nguyệt (đỉnh trái); bóng đập vành/bảng lúc 9,45s nảy ra ngoài; áo xanh rebound lúc 9,92s; không vào rổ; bảng điểm giữ nguyên **TP.HCM 0 - Hà Nội 1** suốt clip. | **`approved`** (User đã duyệt) |
| **`clip06`** | `s001` | **4.20s – 6.40s** | **`made`** | **5.72s** | White #3 (Hà Nội) / 1đ | Áo trắng #3 đột phá lên rổ cận thành trong vòng bán nguyệt; bóng đập bảng rơi qua vành rổ lúc 5,72s (frame 144); tính 1 điểm theo luật 3x3; bảng điểm cập nhật Hà Nội lên 2, sau đó cập nhật TP.HCM lên 1 (tỉ số thành **1 - 2**). | **`approved`** (User đã duyệt) |
| **`clip06`** | `s002` | **24.50s – 26.60s** | **`made`** | **25.74s** | Blue #12 (TP.HCM) / 1đ | Áo xanh #12 nhận bóng cận rổ rồi bật nhảy lên rổ ghi 1 điểm lúc 25,74s (frame 648); bảng điểm hiển thị cập nhật tỉ số thành **1 - 3**. | **`approved`** (User đã duyệt) |
| **`clip06`** | `s003` | **30.80s – 33.10s** | **`made`** | **32.26s** | White #3 (Hà Nội) / 1đ | Áo trắng #3 đột phá trung lộ rồi lên rổ ghi 1 điểm lúc 32,26s (frame 812); bảng điểm hiển thị cập nhật tỉ số thành **2 - 3**. | **`approved`** (User đã duyệt) |
| **`clip06`** | `s004` | **40.50s – 42.70s** | **`made`** | **41.87s** | Blue #19 (TP.HCM) / 1đ | Áo xanh #19 tiếp tục đột phá trung lộ rồi lên rổ ghi 1 điểm lúc 41,87s (frame 1054); bảng điểm hiển thị cập nhật tỉ số thành **2 - 4**. | **`approved`** (User đã duyệt) |
| **`clip07`** | `s001` | **5.50s – 8.50s** | **`miss`** | *(trống)* | White (Hà Nội) / 1đ | Áo trắng đột phá cận rổ, bị 2 cầu thủ áo xanh cản phá (block) lúc 7,28s; bóng không vào rổ; trọng tài thổi còi hết shot clock; bảng điểm giữ nguyên **TP.HCM 4 - Hà Nội 4**. | **`approved`** (User đã duyệt) |

### 6.2. Các pha ném ứng viên đang chờ rà soát (`events.draft.csv`)

*Hiện tại không có pha ném nào ở trạng thái draft (0 pending draft). Toàn bộ 10 pha ném đã được người dùng phê duyệt chính thức vào `events.csv`.*

---

## 7. Quy tắc phân chia Calibration và Test Set (`splits.json`)

1. **Phân tách theo nhóm nguồn**: Không bao giờ đưa các clip thuộc cùng một buổi quay (`session_id`) hoặc cùng một góc máy (`camera_id`) vào cả hai tập calibration và test.
2. **Nguyên tắc chống rò rỉ**:
   - Mọi biến thể cắt ghép hoặc replay của cùng một pha phải ở cùng một tập.
   - Không chia frame ngẫu nhiên hay chia các pha liền kề trong cùng một video vào 2 tập.
3. **Độ phủ dữ liệu**:
   - Tập `calibration` (`group_day_solo_01`): Dùng để điều chỉnh quy tắc chuyển trạng thái và các ngưỡng khoảng cách/thời gian trong Task 05. Gồm `clip02` (1 pha `made`).
   - Tập `test` (`group_u18_3x3_test`): Là tập giữ lại hoàn toàn độc lập (`holdout test set`) để Task 07 đánh giá khách quan. Gồm 4 clip mới (`clip04`, `clip05`, `clip06`, `clip07`), chứa **4 pha `made`** và **3 pha `miss`**.
4. **Trạng thái khóa split (`locked`)**:
   - Toàn bộ 10 nhãn đã được người dùng duyệt vào `events.csv`.
   - `splits.json` đã được khóa chính thức ở phiên bản `1.0.0-locked` với đầy đủ mã băm SHA-256 fingerprint của `manifest.csv`, `events.csv`, và `coverage.csv`.
