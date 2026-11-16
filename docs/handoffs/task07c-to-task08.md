# Bàn Giao Kỹ Thuật: Từ Task07C Sang Task08 (Scoring, Points, Rebounds, Assists)

Ngày bàn giao: 2026-11-08.  
Trạng thái upstream (Task07): **FAILED CRITERIA — Task07 TIẾP TỤC IN_PROGRESS.**  
Tham chiếu nghiệm thu: [Báo cáo nghiệm thu Task07C](../reports/task07c-acceptance-report-20261107.md), [Acceptance Manifest](../../codebase/outputs/task07c-acceptance-20261107/manifest.json).

---

## 1. Bối Cảnh Nghiệm Thu Upstream

Quy trình nghiệm thu Task07C đã được kích hoạt và thực thi đầy đủ trên cả hai phân đoạn phát triển (`vt_development.mp4`) và validation (`vt_validation.mp4`).  
Kết quả đánh giá cho thấy:
- **Observed Ball Recall:** Đạt **50.00%** (36/72 mẫu) $\rightarrow$ Chưa đạt ngưỡng yêu cầu $\ge 90\%$.
- **Strict Controller Accuracy:** Đạt **0.00%** (0.0s / 14.30s) $\rightarrow$ Chưa đạt ngưỡng yêu cầu $\ge 90\%$.
- **Strict Pass Recall:** Đạt **0.00%** (0 TP, 5 FN) $\rightarrow$ Chưa đạt ngưỡng yêu cầu $\ge 90\%$.
- **Validation Ground Truth:** Tệp `annotations-draft.json` trong kho mã nguồn hiện ở trạng thái `draft`, chưa có reviewer ký duyệt và trống hoàn toàn các mốc kiểm soát bóng và đường chuyền.
- **Integrity Guards:** Đạt **100% PASS** (0 prediction-only control, 0 pass crossing cut, sai số PTS $\approx 0.33\mu\text{s} \le 2\mu\text{s}$).

Do đó, **Task07 chưa được đóng (chưa đạt DONE)**. Để đảm bảo Task08 không bị đình trệ nhưng đồng thời không phát sinh lỗi domino do dữ liệu upstream chưa đạt chuẩn, tài liệu này quy định rạch ròi phạm vi dữ liệu được phép và không được phép sử dụng.

---

## 2. Phần Dữ Liệu Được Phép Sử Dụng Trong Task08 (Approved For Consumption)

1. **Player Tracking Bounding Boxes & Tọa Độ Sân (Từ Task05 & Task06):**
   - Dữ liệu `tracked_observations.jsonl` (14,007 observations trên development, 12,403 trên validation) đã được kiểm chứng tính toàn vẹn: không có tọa độ vô hạn, bbox nằm trong khung hình, ID track ổn định.
   - Ma trận hình học sân đấu và hình chiếu mặt sân từ Task05 được phép sử dụng để tính toán khoảng cách ném bóng, xác định vị trí trong/ngoài vòng 2 điểm (1 điểm vs 2 điểm theo luật 3x3).
2. **Gán Nhãn Màu Đội (Team Assignment):**
   - Thuật toán candidate `--team-crop-region jersey --reset-on-team-conflict` đã sửa hiện tượng trôi màu (giảm 89.5% thời gian gán sai đội, đạt 7/7 snapshot đúng đội trên tập review).
   - Task08 được phép dùng nhãn đội của các track cầu thủ để gán điểm cho đội (team score: Việt Nam vs Tonga).
3. **Mốc Thời Gian Chuẩn PTS & Cắt Cảnh (Exclusions & Cuts):**
   - Thời gian PTS giải mã chính xác tuyệt đối (sai số $\le 2\mu\text{s}$ so với video nguồn).
   - Các khoảng loại trừ vận hành (như đoạn cận cảnh khán giả $t = 21.567\text{s} - 26.433\text{s}$) và cờ ranh giới cắt cảnh giúp Task08 tránh kích hoạt phát hiện ghi điểm giả trong các pha chuyển cảnh truyền hình.
4. **Bộ Dữ Liệu 34 Pha Ghi Điểm Đã Review Của Task08:**
   - 34 pha ghi điểm đã được tiếp nhận và xử lý nhất quán ([`docs/reports/task08-scoring-review-intake-20261107.md`](../reports/task08-scoring-review-intake-20261107.md)), gồm 13 pha có cặp timestamp release/basket chính xác. Đây là ground truth độc lập để kiểm thử scoring.

---

## 3. Phần Dữ Liệu TUYỆT ĐỐI KHÔNG ĐƯỢC DÙNG TỰ ĐỘNG Trong Task08 (Restricted / Blocked)

1. **Tự Động Ghi Nhận Kiến Tạo (Assists Attribution) — NGHIÊM CẤM:**
   - **Lý do:** Strict pass recall của Task07 hiện là **0.0%** (hệ thống chưa nhận diện được đường chuyền hoàn thành nào do detector miss bóng và thiếu OCR identity).
   - **Hệ quả:** Nếu Task08 cố gắng tự động suy ra cầu thủ kiến tạo (Assist) từ output của Task07, tỷ lệ lỗi sẽ là 100%. Mọi chỉ số assist phải tạm thời để trống (`null`) hoặc chỉ ghi nhận dựa trên nhãn review thủ công của con người.
2. **Tự Động Ghi Nhận Bắt Bóng Bật Bảng (Rebounds Attribution) — NGHIÊM CẤM:**
   - **Lý do:** Strict controller accuracy của Task07 đạt **0.0%** (do các track khống chế bóng sau cú ném trượt thiếu đọc số áo OCR hợp lệ nên `player_id` là `None`).
   - **Hệ quả:** Task08 không được tự động gán rebound cho cá nhân cầu thủ dựa trên `ball_control.jsonl`. Chỉ được ghi nhận rebound cấp độ đội (Team Rebound) dựa trên nhãn đội của cầu thủ gần rổ nhất sau cú ném trượt.
3. **Quỹ Đạo Bóng Bay Liên Tục Để Suy Ra Made/Miss — HẠN CHẾ:**
   - **Lý do:** Raw ball detector hiện bỏ sót bóng ở 40.3% thời lượng và 31/72 mẫu kiểm tra. Các cú ném bóng bổng bay nhanh thường bị mất dấu từ 3–5 frames liên tiếp.
   - **Khuyến nghị cho Task08:** Thuật toán xác định cú ném thành công (Made) hay trượt (Miss) trong Task08 **không được phụ thuộc hoàn toàn vào quỹ đạo liên tục của quả bóng qua tâm rổ**. Thay vào đó, Task08 phải kết hợp:
     - Tương tác tại vùng vành rổ/lưới (Rim ROI / net animation).
     - Bảng điểm truyền hình hoặc nhãn review outcome.
     - Vị trí của người ném tại thời điểm release.
4. **Định Danh Cầu Thủ Cá Nhân (Continuous Player Identity):**
   - Chưa có Ground Truth quỹ đạo cầu thủ liên tục. Danh tính cá nhân chỉ nên ghi nhận khi track có bằng chứng OCR tin cậy tại thời điểm ném rổ; nếu không có, giữ `player_id: null` và gán điểm cho đội (`team_id`).

---

## 4. Hướng Đi Độc Lập Cho Task08

Để tiếp tục phát triển Task08 mà không bị chặn bởi Task07:
1. Tập trung xây dựng bộ nhận diện cú ném (Shot Release & Basket Entry) trên 10 cửa sổ quan trọng đã chốt nhãn (`critical-windows-draft.json` trong `task08-scoring-intake-20261107`), sử dụng đặc trưng hình ảnh quanh vành rổ và tọa độ người ném.
2. Tách module tính điểm (Points) độc lập với module thống kê phụ (Assists/Rebounds).
3. Đợi phê duyệt kế hoạch fine-tune ball detector từ Task07B để cải thiện chất lượng nhận diện bóng trước khi tích hợp end-to-end PRA (Points - Rebounds - Assists).

