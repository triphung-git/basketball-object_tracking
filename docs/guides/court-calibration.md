# Chọn điểm và kiểm chứng calibration mặt sân

Cập nhật sau nghiệm thu 2026-11-03. Workspace hiện chưa có landmarks/visible-foot GT được duyệt, nên chưa có geometry clip02 được nghiệm thu. File synthetic là fixture, không phải bản đo sân.

## Đầu vào cần chuẩn bị

1. Chọn đúng source video hash, camera/segment và frame/PTS, kích thước ảnh gốc.
2. Định nghĩa duy nhất origin, hướng trục, units và bounds. Nếu chưa đo được scale, dùng normalized coordinates và ghi giới hạn; không ghi verified_meters chỉ vì biết kích thước sân tiêu chuẩn.
3. Chọn ít nhất4 cặp điểm cùng mặt sân, phân bố tốt, không suy biến; có thêm points check độc lập và visible-foot GT để đánh giá ngoài fit.
4. Ranh giới ROI phải có evidence. Pan/zoom/cut vô hiệu geometry; tách segment/config, không reuse ma trận cũ.
5. Có reviewer/provenance rõ trước validated. Agent có thể tạo proposal, không tự ghi người dùng đã duyệt.

Không dùng rim/backboard ở trên cao để fit floor homography. Điểm chiếu rim xuống sàn chỉ dùng nếu thực sự xác định được. Không lấy tâm bbox người đang nhảy làm chân chạm đất chắc chắn.

## Tránh nhầm hệ tọa độ

Bản guide trước trộn origin ở tâm hình chiếu rổ với tọa độ lấy từ baseline, tạo bảng landmarks không nhất quán. Bảng đó đã được bỏ. Không sao chép các con số6.75/1.575/5.8 hoặc bounds của fixture để hiệu chuẩn clip bất kỳ.

Ghi origin/axes/units nhất quán trong config và mọi correspondence. Muốn dùng mét hoặc arc/shot-value geometry, xác minh bản vẽ/kích thước/luật của sân và giải cụ thể trước. Task05 chưa chứng minh arc/court dimensions của clip02.

## Công cụ headless

Từ thư mục codebase, output preview phải là đường dẫn mới:

```powershell
.venv/Scripts/python.exe scripts/court_tool.py --config configs/courts/template_court.json
.venv/Scripts/python.exe scripts/court_tool.py --config configs/courts/synthetic_half_court.json --allow-uncalibrated --preview outputs/new-court-preview.png
```

Lệnh đầu kỳ vọng exit2 (chưa validated). Synthetic cũng bị từ chối nếu thiếu --allow-uncalibrated. Preview có numbered points/ROI/projected grid và nhãn diagnostic. Đây là công cụ nhập JSON/preview, chưa có click-to-label UI; tạo correspondences draft theo [schema](../specs/court-heatmap-v2.md), không điền điểm ảnh giả vào production config.

## Kiểm tra trước nghiệm thu

Residual trên4 fit points có thể gần0 dù geometry sai. Báo fit residual, independent check residual, cỡ mẫu/coverage và median visible-foot error normalized theo chiều rộng vùng phân tích. Mục tiêu task05≤5% chưa được đo trên GT thật.

Fixture hiện có check residual190px, vượt threshold10px; không được phê duyệt geometry thật từ fixture này. Orientation và points phải đối chiếu ảnh gốc, không chỉ thấy PNG heatmap đẹp. Không clip projected points ngoài sân vào biên để làm số liệu có vẻ hợp lệ.

Khi đổi calibration, giữ raw bbox/image footpoints để recompute ra run/version mới. Xem [G05 report](../reports/task05-court-heatmap.md) và [court/heatmap contract](../specs/court-heatmap-v2.md).

