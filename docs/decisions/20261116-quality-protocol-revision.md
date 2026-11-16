# Revision đánh giá và run mở rộng — 2026-11-16

Nguồn quyết định: người dùng yêu cầu cho đợt phát triển tiếp theo (1) dung sai release ±0,75s cho pha cận rổ **hoặc** ưu tiên basket time khi matching, (2) bổ sung training bóng bị che một phần bởi lưới/vành, (3) mở rộng nhận diện đến khoảng 995 giây để phủ các nhãn made đã có.

## Phương án triển khai

- Chọn phương án **basket-primary**: basket tolerance giữ ±0,50s, release delta vẫn được ghi để audit nhưng không làm hard gate trong profile mới. Matching vẫn one-to-one; strict team/player/value không đổi. Đây là revision có thay đổi định nghĩa metric, không thay âm thầm profile cũ và không chứng minh recognition tốt hơn chỉ vì có thêm matches.
- Profile default `pra-production-evaluator-v2` tiếp tục yêu cầu release và basket trong ±0,50s. Profile mới tại `codebase/configs/evaluation/pra-basket-primary-20261116.json`, dùng explicit protocol version và so sánh song song trên cùng predictions. Không mở rộng ±0,75s cho tất cả shot types hoặc suy 1PT đồng nghĩa pha cận rổ.
- Video nguồn đo lại dài 1381,0667s. Label made cuối có outcome 995,3s, nên run mới xử lý **0–1000s** để có context xác nhận. Đây là prefix mở rộng của broadcast, không phải toàn bộ video 1381s.
- Labels clip `vt_development` chuyển sang timeline parent bằng offset +300s và kiểm source hashes; các files GT gốc không đổi. Run mới ghi coverage đã xử lý. Evaluator scoped từ chối run 30s dùng cho scope 1000s và không ghép event có explicit video IDs khác nhau.
- Source đã exposed và GT chủ yếu là sự kiện rời rạc; chưa có exhaustive review coverage 0–1000s. Vì vậy measurements mới là same-match **diagnostic**, không phải independent frozen acceptance. 06A/06B cũ không được tự động nâng PASS.

## Training

Người dùng đã yêu cầu local fine-tune bổ sung. GPU RTX 2050/CUDA của `.venv-train` đã kiểm tra còn hoạt động. Chưa khởi động job mới vì chưa có một batch bbox mới được review cho visibility/partial occlusion quanh lưới/vành.

49 supplemental images hiện có có 5 spatial near-rim candidates. Đã xem 5 ảnh để triage: không thể từ việc nằm gần rổ suy ra có đủ lớp che khuất bởi lưới/vành để giải quyết lỗi. Tạo 8 source frames draft quanh hai miss trong development để bổ sung review; không tự tạo bbox cho bóng hoàn toàn khuất, không promote draft thành approved hoặc thay approved default model.

Run inference CPU có thể tiến hành độc lập trong lúc chuẩn bị nhãn; chưa gọi phần train hoàn thành. Giữ max observation gap 0,35s và observed-crossing guards. Không tăng timeout hoặc dùng predicted centers để thay cải thiện detector.
