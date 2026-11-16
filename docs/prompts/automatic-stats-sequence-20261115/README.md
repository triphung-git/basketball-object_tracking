# Chuỗi prompt hoàn thiện Automatic Stats

Cách giao việc mới theo yêu cầu 2026-11-16: [bộ prompt demo D01–D12](../demo-completion-20261116/README.md), [prompt tổng mới](../demo-completion-20261116/00-master-execution.md) và [Plan review tập trung](../../../PLAN-DEMO-20261116.md). Dùng bộ mới khi muốn agent tự làm toàn bộ phần còn lại, gom approvals để review sau và tiếp tục công việc độc lập; phần dưới giữ làm lịch sử/tham chiếu.

Ngày lập: 2026-11-15. Nguồn: [review project](../../reports/project-status-review-20261115.md), [PLAN](../../../PLAN.md), [MVP v2](../../MVP-v2-proposal.md).

Đây là prompt để giao thực thi, chưa phải bằng chứng các task đã hoàn thành. Chia thành 6 đợt, 12 task nhỏ, mỗi đợt 1–3 task. Dùng lần lượt theo bảng; mỗi file đã yêu cầu đọc [quy trình checkpoint chung](execution-contract.md), không cần dán lại file chung vào chat.

## Thực thi toàn bộ phần còn lại sau đợt 01

Đợt 01 đã hoàn tất: dùng [prompt tổng 02A → 06B](00-execute-all-remaining.md) để giao cả **9 task còn lại trong một lần**. Agent tự chuyển task/đợt khi checkpoint PASS, ghi state để resume và chỉ dừng ở blocker hoặc gate chưa thể đáp ứng; không cần gửi lại từng prompt riêng.

```text
Đọc và thực thi toàn bộ:
docs/prompts/automatic-stats-sequence-20261115/00-execute-all-remaining.md

Đợt 01 đã hoàn tất. Xác minh handoff/checkpoints rồi thực thi liên tục:
02A → 02B → 03A → 03B → 04A → 05A → 05B → 06A → 06B.
Tuân thủ execution-contract.md và các prompt chi tiết được dẫn chiếu.
Mỗi task phải đủ tests đã chạy, real-run outputs, report/handoff và checkpoint PASS trước khi chuyển tiếp.
Không dừng sau mỗi đợt để hỏi lại. Không chỉ lập kế hoạch hoặc tạo thêm prompt.
Nếu thiếu input bắt buộc hoặc quality gate không đạt, ghi blocker/evidence và giữ đúng gate; không bỏ qua để báo hoàn tất.
```

Phần bên dưới vẫn dùng được khi muốn giao riêng từng đợt; giới hạn không chuyển đợt ở cách giao riêng không áp dụng cho prompt tổng đã giao toàn chuỗi.

## Danh mục prompt chi tiết

Khi 03B bị chặn bởi dữ liệu/review: dùng [bổ sung 03B — chuẩn bị review packets](03B-prepare-review-packets.md) để agent làm rõ blockers, validate proposal và chuẩn bị clips/rules/split/calibration cho người dùng review. Đây là công việc trong 03B, không mở task tiếp theo hoặc bỏ gate.

| Đợt | Prompt | Task nối tiếp | Phụ thuộc |
|---|---|---|---|
| 01 | [CLI → Rebound → Assist](01-cli-rebound-assist.md) | 01A: sửa entrypoint; 01B: rebound correctness; 01C: assist correctness | Bắt đầu được ngay |
| 02 | [Continuous MP4 → PRA và exports](02-continuous-video-pipeline.md) | 02A: frame/upstream stream; 02B: event orchestration và output bundle | Đợt 01 đạt checkpoint kỹ thuật |
| 03 | [PRA evaluator → Dataset chuẩn và freeze](03-evaluator-dataset-freeze.md) | 03A: evaluator dùng chung; 03B: hợp nhất reviewed GT, xác minh data/lock readiness | Đợt 02 đạt checkpoint kỹ thuật |
| 04 | [Chất lượng nhận diện và paired evaluation](04-recognition-quality.md) | 04A: baseline, error analysis, cải thiện trong phạm vi đã cho phép và paired evaluation | Đợt 03 hoàn tất, calibration đủ dữ liệu |
| 05 | [Dashboard thật → Benchmark E2E](05-dashboard-benchmark.md) | 05A: UI/evidence/heatmap thật; 05B: benchmark production | Đợt 04 có measurement bundle đầy đủ; không đòi promote model để xây UI |
| 06 | [Frozen evaluation → Đóng gói và nghiệm thu](06-final-evaluation-delivery.md) | 06A: nghiệm thu chất lượng trước correction; 06B: đóng gói và clean-run | Đợt 01–05 đủ bằng chứng; 06B chỉ bắt đầu sau quality gate 06A PASS |

Đợt 03 xây evaluator trước khi freeze dữ liệu để kiểm thử tooling trong lúc chưa có đủ nhãn; khi bắt đầu 03B, thiếu đầu vào thì giữ 03B pending và không mở đợt 04. Đợt 04 là một task lớn riêng, không gom thêm UI hoặc training dài chưa rõ phạm vi.

Mỗi task phải có code/config cần thiết, tests thực sự đã chạy, run artifacts, report và handoff trước khi mở task kế tiếp. Tests fail, smoke fail hoặc artifact thiếu thì tiếp tục sửa task hiện tại. Thiếu review/approval thực sự cần thiết thì bàn giao blocker cụ thể và giữ task chưa hoàn tất. Không coi thời gian chờ, file tồn tại hoặc lời hứa test sau là PASS.

Task 04A hoàn tất khi thí nghiệm có phạm vi hữu hạn đã được thực hiện/đánh giá đầy đủ và có quyết định dùng baseline/candidate có bằng chứng. Kết quả không đạt mục tiêu vẫn phải ghi `quality_gate=FAIL`; không gọi recognition/MVP DONE. Điều đó cho phép xây UI và đo hiệu năng bằng baseline đã xác minh ở đợt 05, nhưng không cho phép vượt quality gate nghiệm thu 06A.

Giao agent đợt đầu bằng nội dung sau:

```text
Đọc và thực thi docs/prompts/automatic-stats-sequence-20261115/01-cli-rebound-assist.md.
Thực hiện lần lượt 01A → 01B → 01C, tuân thủ execution-contract.md cùng thư mục.
Mỗi task phải có tests đã chạy, run artifacts, report và handoff trước khi mở task sau.
Không chỉ lập kế hoạch hoặc tạo thêm prompt. Không tự chuyển sang đợt 02.
```

Các đợt sau thay tên file và danh sách task tương ứng. Không cần hỏi lại người dùng giữa hai task đã được giao và đã PASS checkpoint. Không tự chạy đợt tiếp theo chỉ vì có link trong README.
