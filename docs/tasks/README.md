# Task index — Automatic Stats v2

Cập nhật nghiệm thu 2026-11-10: [report](../reports/demo-completion-acceptance-20261110.md) — Task08–15 **IN_PROGRESS**, chưa được nghiệm thu. Code/test có sẵn không đồng nghĩa đạt requirement; xem ma trận implemented/executed/measured/accepted và các blockers mới. Các mô tả chưa triển khai dưới đây là lịch sử.

Cập nhật dataset-first07A: [QA/pilot359frame](../reports/task07a-dataset-first-20261105.md),257tests PASS; người dùng đã duyệt hướng, nhãn draft đang chờ review. Có bằng chứng shared-source train/test current project; chưa train/đổi weights, Task07 IN_PROGRESS, chưa mở07B/07Cnghiệm thu.

Thử nghiệm Task07 mới nhất: [spatial reliability v4](../reports/task07-spatial-reliability-20261104.md),240tests PASS, ball recall50% trên development đã tune; strict control/pass vẫn0%, Task07 IN_PROGRESS. Kết quả chưa chứng minh generalization hoặc OCR accuracy tăng.

Cập nhật full evaluation Task07: [development v2](../reports/task07-development-evaluation-v2-20261104.md) đã dùng GT người dùng review/xác nhận, đủ minimum samples nhưng `failed_criteria` (ball43.06%, control0%, pass recall0%). Task07 IN_PROGRESS do chất lượng recognition, validation GT còn pending. Không hỏi lại các xác nhận control đã chốt.

Cập nhật pilot mới nhất 2026-11-04: [Vietnam–Tonga](../reports/task07-vietnam-tonga-segments.md), **233 tests PASS**, hai đoạn 30s và [handoff](../handoffs/task07-vietnam-tonga.md). Roster/protocol đã duyệt, GT review pending; chưa có completed pass, real accuracy chưa đủ bằng chứng nghiệm thu. Không tự đóng Task04–07. Các counts 207/153 bên dưới là baseline lịch sử.

Nguồn: [MVP đã duyệt 2026-11-02](../MVP-v2-proposal.md), [PLAN v2](../../PLAN.md). Task01–02 là baseline v1; task03 đã nghiệm thu pipeline; task04 chờ dữ liệu/rules. Task05–06 đã có core tools và OCR local, real geometry/identity acceptance còn pending. Task07 có implementation/demo, task08–15 chưa triển khai. Không dùng lịch một tuần làm chuẩn nghiệm thu v2.

| Task | Nội dung | Trạng thái |
|---|---|---|
| [01](task01.md) | Runtime/model baseline | DONE v1 |
| [02](task02.md) | Shot dataset pilot | DONE v1 |
| [03](task03.md) | Video/PTS/detection nền | DONE v2 |
| [04](task04.md) | Dataset v2, rules, evaluation protocol | IN_PROGRESS (tooling pass; data/rules/protocol pending) |
| [05](task05.md) | Court geometry và heatmap | IN_PROGRESS (tooling pass; geometry/GT pending) |
| [06](task06.md) | Players/team/identity | IN_PROGRESS (core tools pass; OCR/footage/roster/GT pending) |
| [07](task07.md) | Ball/control/pass/possession | IN_PROGRESS (implementation/fixtures/clip04 demo PASS; real accuracy pending) |
| [08](task08.md) | Shots/value/points tự động | IN_PROGRESS |
| [09](task09.md) | Rebounds tự động | IN_PROGRESS |
| [10](task10.md) | Assists tự động | IN_PROGRESS |
| [11](task11.md) | Ledger và automatic box score | IN_PROGRESS |
| [12](task12.md) | Dashboard/evidence/exports | IN_PROGRESS |
| [13](task13.md) | End-to-end evaluation | IN_PROGRESS |
| [14](task14.md) | Performance/streaming readiness | IN_PROGRESS |
| [15](task15.md) | Đóng gói/nghiệm thu cuối | IN_PROGRESS |

Mỗi task có đầu vào người dùng, phần agent xây, artifacts, tests, acceptance, dependencies và điều kiện cần quyết định. TODO/IN_PROGRESS/DONE là trạng thái công việc; chưa đủ data/model thì ghi blocker, không đổi thành manual stats để pass.

Cập nhật 2026-11-04: [Task07 report](../reports/task07-ball-possession.md), 207 tests PASS và clip04 demo với roster giả lập/OCR local; [handoff task08–10](../handoffs/task07-to-task08-09-10.md). [Quyết định exposure](../decisions/20261104-clip04-development-exposure.md) cho phép đúng clip04 development và ghi nhận nhóm clip04–07 đã tiếp xúc. Real-data gates vẫn mở.

Task03 và công cụ/thu thập task04 có thể bắt đầu độc lập. Các task sau theo graph PLAN; không tự spawn agent chỉ vì có công việc độc lập.

Nghiệm thu mới nhất: [G03–G04](../reports/task03-task04-acceptance.md) · [data v2](../reports/data-v2.md) · [handoff 05–06](../handoffs/task04-to-task05-06.md). G04 chưa đóng; task05/06 chỉ có thể chuẩn bị phần kỹ thuật độc lập, chưa nghiệm thu phần phụ thuộc dữ liệu.

Tái nghiệm thu 2026-11-03: [task05–06](../reports/task05-task06-acceptance.md),153 tests PASS và independent artifact audit; [handoff task07/08/12](../handoffs/task06-to-task07-08-12.md). Có thể mở phần độc lập task07, chưa nghiệm thu real control/attribution khi role/identity/geometry còn thiếu evidence.

[Bàn giao task03](../handoffs/task03.md) · [Prompt task03](../prompts/task03-coding-agent.md) · [Snapshot cũ](../archive/2026-11-02-pre-auto-stats/README.md).

Để thực hiện xuyên suốt hai task với checkpoint kiểm thử/report/handoff ở giữa, dùng [prompt chung task03–04](../prompts/task03-task04-coding-agent.md). Sau G03 PASS tiếp tục task04 trong phạm vi đã giao; nếu thiếu dữ liệu/review, giữ readiness và status trung thực.

Các task tiếp theo: [prompt chung task05–06](../prompts/task05-coding-agent.md), giữ tên file cũ nhưng giao xuyên suốt court/heatmap → checkpoint/report/handoff G05 → tracking/team/identity → integration và nghiệm thu chung. Task07 trở đi chỉ là consumers để bàn giao. Thiếu geometry/roster/GT thì tiếp tục phần độc lập và giữ nghiệm thu dữ liệu pending; không tự đóng G04.
