# Task14 — Hiệu năng, causal streaming và tối ưu có đo lường

Kiểm thử lại 2026-11-10: [acceptance report](../reports/demo-completion-acceptance-20261110.md). **IN_PROGRESS; chưa nghiệm thu.** Microbenchmark chạy được nhưng mapping/input sai và thiếu các stage E2E; không chấp nhận application FPS.

**Version: MVP v2 Automatic Stats, 2026-11-02. Trạng thái: IN_PROGRESS.**
Ước lượng: 2–4 ngày công (không bao gồm chờ đầu vào nếu có). Phụ thuộc: Task13 baseline; không dùng tối ưu tốc độ để né lỗi chất lượng.

## Mục tiêu

Đo throughput/latency thật và cải thiện có kiểm tra chất lượng; kết luận offline/live-readiness đúng bằng chứng.

Nguồn phạm vi: [MVP đã duyệt](../MVP-v2-proposal.md), [PLAN v2](../../PLAN.md), [chỉ mục](README.md). Đọc DEVELOPMENT và contracts/rules v2 khi được tạo. Task01–02 chỉ là baseline đã nghiệm thu.

## Bạn cần cung cấp / xác nhận

- Máy mục tiêu, quyền cân nhắc runtime/GPU/model bổ sung nếu benchmark chứng minh cần.
- Live source chỉ khi muốn kiểm tra live; MVP mặc định vẫn MP4 offline.

## Agent sẽ xây dựng

1. Đo decode→detect→tracking→events→render/export và confirmation latency, p50/p95, source FPS, processed/dropped frames, backlog và bộ nhớ.
2. Tách processing latency, causal look-ahead video time và event confirmation delay; không dùng frame tương lai vô hạn rồi gọi live.
3. Profile bottleneck; thử resize/crop/batching/caching hay schedule inference có config, giữ observed/predicted evidence rõ.
4. Không skip-frame gần tương tác quan trọng tùy tiện; mọi thay đổi ảnh đầu vào/logic phải re-evaluate ball/event recall và attribution.
5. Nếu chọn GPU/ONNX backend mới, trình phương án driver/VRAM/package/chi phí và xin quyền trước; giữ baseline có thể khôi phục.
6. Nếu tuyên bố live, chạy ít nhất5 phút liên tục ở nguồn mục tiêu, throughput≥FPS nguồn, backlog không tăng; báo latency và chất lượng dropped-frame cùng phiên.

## Đầu ra bắt buộc

- docs/reports/performance-v2.md; benchmark.json/config và quyết định runtime.
- Optimized profile nếu có, quality-regression report so với baseline; không sửa GT/split.

Các đường dẫn code/config/output tương đối với codebase trừ docs/. Đây là thiết kế để triển khai, không phải file/tính năng đã hoàn thành. Mỗi run có versions/config/fingerprints và evidence, không có API key.

## Nghiệm thu

- [ ] Có end-to-end benchmark thực tế, không lấy 1/model_latency làm application FPS.
- [ ] Không giảm chất lượng PRA/heatmap mà không báo; target quality task13 vẫn áp dụng.
- [ ] Nếu chưa đạt live, ghi offline rõ; task benchmark có thể hoàn tất nhưng live gate là chưa đạt, không đổi yêu cầu tự động PRA.

## Kiểm thử cần thiết

- Causal look-ahead bounds, queue/backpressure, cancellation và long-run memory.
- Quality regression cho input/schedule/backend mới trên protocol frozen; nếu tuning đã dùng test, dùng reserve phù hợp.
- Run interrupted/failed không sinh artifacts completed giả.

Không dùng synthetic fixtures như dữ liệu thật, không dùng labels/manifest notes làm oracle recognition. Calibration/test v2 phải tách nhóm; labels/split v1 đã khóa được giữ nguyên. Chỉ test phù hợp thay đổi và integration evidence cần thiết, không benchmark lặp không có lý do.

## Rủi ro và điều kiện dừng phần phụ thuộc

Tối ưu GPU không bảo đảm sửa được identity/control/assist reasoning. Nếu phải đổi phạm vi/live requirement, hỏi người dùng cụ thể, không tự cam kết.

Không cần hỏi lại có làm automatic PRA hay không: đã duyệt. Hỏi trước các thay đổi model/backend/dependency lớn, GPU stack, chi phí/cloud upload, dataset locked hoặc scope; tiếp tục phần độc lập trong khi chờ. Không xem im lặng là đồng ý. Không thay engine tự động bằng thao tác nhập/duyệt tay để đánh dấu DONE.

## Bàn giao

Runtime/profile và measured limits, quality snapshots cho task15.

Khi kết thúc, cập nhật task này và report với file paths, lệnh đã chạy, số liệu thật, điều kiện chưa đạt và bước tiếp theo. Chỉ chuyển DONE khi checklist có bằng chứng; sửa tay không thay automatic metrics.
