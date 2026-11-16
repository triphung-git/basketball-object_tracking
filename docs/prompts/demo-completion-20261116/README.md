# Bộ prompt hoàn thiện demo và gom review vào một Plan

Điểm vào duy nhất: [00-master-execution.md](00-master-execution.md). Plan mới: [PLAN-DEMO-20261116.md](../../../PLAN-DEMO-20261116.md).

| Nhóm | Task | Prompt |
|---|---|---|
| Nền chạy, OCR/identity, geometry/heatmap | D01–D03 | [01-core-identity-spatial.md](01-core-identity-spatial.md) |
| Shot/control/PRA và fine-tune có dữ liệu duyệt | D04–D06 | [02-pra-training.md](02-pra-training.md) |
| Evaluator scope/run dài và UI/overlay | D07–D08 | [03-evaluation-dashboard.md](03-evaluation-dashboard.md) |
| Benchmark thật và bundle demo | D09–D10 | [04-benchmark-package.md](04-benchmark-package.md) |
| QA/clean-run và Plan/report/approval tổng hợp | D11–D12 | [05-qa-review-handoff.md](05-qa-review-handoff.md) |

Giao agent bằng một câu:

```text
Đọc và thực thi docs/prompts/demo-completion-20261116/00-master-execution.md.
Thực hiện toàn bộ D01–D12 theo dependency gates, tự chuyển task sau kiểm thử/report/checkpoint.
Gom mọi mục thật sự cần tôi duyệt vào PLAN-DEMO-20261116.md để tôi review một lần sau.
Khi chờ duyệt, giữ phase phụ thuộc pending và tiếp tục phần độc lập; không tự phê duyệt hoặc bỏ gate.
Đầu ra là demo tự động đủ PTS/REB/AST/heatmap/video/dashboard/exports, QA/clean-run và báo cáo trung thực.
Không chỉ lập kế hoạch hoặc tạo thêm prompt thay cho thực thi.
```

Bộ này thay cách điều phối trong bộ 20261115 khi được giao cho agent. Reuse requirements và artifacts cũ, không làm lại toàn bộ các module đã đạt. Không cần người dùng gửi từng nhóm riêng hoặc hỏi lại quyền chuyển task/đợt.

Không đòi 100% mọi output, cũng không tự hạ standards gốc. Demo readiness khác quality acceptance; đóng gói demo thử nghiệm không được đổi historical 06A/06B thành PASS.
