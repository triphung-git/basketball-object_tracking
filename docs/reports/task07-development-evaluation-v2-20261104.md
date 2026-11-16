# Task07 — full development evaluation sau xác nhận control

Cập nhật thử nghiệm sau baseline này: [spatial reliability v4](task07-spatial-reliability-20261104.md), ball recall50% trên cùng development, strict control/pass vẫn0%,240tests PASS. Kết quả v2 dưới đây giữ nguyên, không ghi đè; v4 chưa là independent validation hoặc nghiệm thu.

2026-11-04. **Đánh giá đã chạy thành công; kết quả `failed_criteria`, Task07 IN_PROGRESS.** Người dùng đã xác nhận Việt Nam #6 trong khoảng8.633247–9.566571s và Tonga #11 trong khoảng chồng10.566561–10.999890s. Không cần hỏi lại hai quyết định này.

## Nhãn đã áp dụng

Canonical packet mới: [reviewed-vt_development-v2.json](../../codebase/data/matches/vietnam_tonga/reviewed-vt_development-v2.json), SHA-256 `ee3f10d78164fe4d1b3301e80cb77896ddf3717fae87c45424721c068506b81d`.

- Bỏ6bản control trùng hoàn toàn, giữ1bản gốc.
- Bỏ bản gán Việt Nam #1 trong8.633247–9.566571s, giữ Việt Nam #6 theo xác nhận.
- Giữ Tonga #11 trong10.566561–10.999890s; chỉ cắt phần chồng khỏi interval #18. #18 còn10.999890–12.266544s. Đây là phép trừ phần chồng theo xác nhận, không suy ra mốc nhận bóng mới từ model.
- Còn8control intervals không overlap, tổng eligible14.299857s.108ball samples và5pass labels giữ nguyên. Reviewer/protocol/source bindings được giữ và xác nhận hội thoại được ghi vào provenance.
- File reviewed ban đầu, repair draft và raw prediction files không đổi. [Resolution record](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/reviewed-development-resolution-v2.json) lưu before/after và fingerprints.

Packet hiện qua schema/source/protocol/roster và overlap validation. Còn cảnh báo chất lượng nhãn liên trường: #18 control bắt đầu10.999890s trong khi pass2 ghi receive11.566551s, sớm khoảng0.567s. Không tự sửa thêm vùng ngoài hai xác nhận; cần đối soát cảnh báo này trong lần review nhãn tiếp theo. Việc qua validation cấu trúc không chứng minh mọi timestamp/actor đã đúng chuyên môn. Cảnh báo này không làm các chỉ số đang thất bại trở thành đạt.

## Kết quả full evaluator

Raw predictions vẫn là `development-masked-delivery/`, đối chiếu hashes với freeze trước khi nhận GT. Không rerun detector hoặc dùng GT làm recognition input.

| Chỉ số | Kết quả | Ngưỡng | Kết luận |
|---|---:|---:|---|
| Observed ball recall, IoU≥0.30 |31/72 =43.06%|≥90%|Chưa đạt|
| Strict team/player control accuracy |0/14.299857s =0%|≥90%|Chưa đạt|
| Strict completed-pass recall |0/5 =0%|≥90%|Chưa đạt|
| Strict completed-pass precision |N/A,0predictions|≥95%|Không đủ giá trị để đạt|
| Prediction-only confirmed control |0frames|0|Đạt integrity guard|
| Completed pass crossing cut |0|0|Đạt integrity guard|
| Video export PTS |Trong2µs theo run và audit decode|≤2µs|Đạt integrity guard|

Minimum sample check đạt:72visible/certain ball samples,5GT passes,control seconds>0. Evaluator exit0 nghĩa hoàn thành phép đo; **không có nghĩa nghiệm thu PASS**. `acceptance_pass=false`, `acceptance_status=failed_criteria`. Precision N/A không được đổi thành100%.

[Evaluation JSON đầy đủ](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/reviewed-development-evaluation-v2/evaluation.json). Đây là development evaluation cùng trận đã exposure, không phải independent match test, chưa chứng minh tổng quát hoặc realtime.

## Phân tích lỗi để phát triển tiếp

Ball:31mẫu được chọn đúng,31mẫu không có bất kỳ candidate ball khớp IoU0.30 trong cache tiled ở confidence0.15,10mẫu có candidate khớp nhưng tracker chọn sai hoặc loại bỏ. Nếu chỉ sửa association trên cache hiện tại, upper bound là41/72≈56.94%, chưa đủ90%. Đây là upper bound chẩn đoán dùng GT trong evaluator, không phải chiến lược chọn candidate cho engine và không phải giới hạn của mọi cấu hình/model.

[Ball failure analysis](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/reviewed-development-evaluation-v2/ball-failure-analysis.json) lưu từng frame, matching candidates, confidence, selected sample type/reason. [Ảnh6mẫu miss](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/reviewed-development-evaluation-v2/missed-ball-samples.jpg): bbox GT màu xanh lá, cached ball candidates màu vàng cam; đây là ảnh chẩn đoán, không dùng làm nguồn annotation mới.

Control: trong14.299857s GT, khoảng4.966483s ball không observed;7.300162s có observed ball nhưng không confirmed controller;2.033212s có confirmed controller nhưng không có player_id. Do đó strict accuracy0% không đồng nghĩa mọi bbox người đều sai; pipeline thiếu đủ observed ball, confirmation và identity để đáp ứng attribution theo cầu thủ. [Control duration breakdown](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/reviewed-development-evaluation-v2/control-failure-analysis.json).

Pass: không có completed pass predictions nên5GT passes đều FN. Chỉnh nhãn control không tạo thêm automatic passes. Cần sửa các tầng trước để có observed continuity, đúng actor tại thời điểm release/receive và stable control; không hạ ngưỡng để ép pass hoặc dùng GT chọn người/bóng khi inference.

## Bước tiếp theo và giới hạn bàn giao

1. Đối soát ball misses trên development, đo candidate recall của các thử nghiệm confidence/crop cùng approved model trước khi chỉnh temporal thresholds. Chỉ test trên development; không chọn crop theo GT ở inference.
2. Phân tích OCR/track identity quanh5pass events, cải thiện causal team/jersey consensus và track continuity; giữ observed/predicted/missing rõ ràng.
3. Đối soát cảnh báo control/receive timestamp trong GT, lưu revision/provenance nếu có sửa. Freeze revision recognition, đo lại development rồi dùng đoạn30–60s chưa dùng để chỉnh và reviewed GT tương ứng. Không gọi hai đoạn đã triage là untouched validation.
4. Nếu cần đổi model/weights/backend hoặc dependency lớn, trình bằng chứng và phương án cụ thể trước thực hiện; hiện chưa có thay đổi các phần này.

Nguồn mới đã cung cấp nhãn thật; blocker hiện không còn đơn thuần là chờ GT development. **Recognition thực tế chưa đạt**, validation GT vẫn chưa nhận. Task08–10 chỉ tiếp tục phần contract/fixtures độc lập, chưa coi real attribution từ Task07 đã được nghiệm thu.

Lần này không sửa runtime source code nên không lặp bộ233tests. Đã kiểm tra schema/protocol/roster, non-overlap, bảo toàn ball/pass và file gốc, full CLI, immutable prediction hashes cùng phân tích lỗi thành phần. Các tests233PASS và integrity audit trước đó không thay thế kết quả real-data evaluation này.
