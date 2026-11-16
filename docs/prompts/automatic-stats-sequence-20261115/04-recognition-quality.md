# Prompt 04 — Đo và cải thiện chất lượng nhận diện, paired evaluation

Thực thi **một task 04A** có phạm vi thí nghiệm hữu hạn; không gom thêm UI/benchmark/packaging. Đọc [execution-contract.md](execution-contract.md), kiểm đợt 03 data/evaluator checkpoints và handoff. Không tự triển khai đợt 05.

Đọc reports Task07 recovery 13/11, Task08 correctness 12/11 và comparison/raw artifacts, Task06/07 acceptance profiles, dataset exposure/decision docs. Source/config hiện tại có thể khác snapshot: xác minh lại trước kết luận.

## 04A — Baseline → Error analysis → Bounded candidate → Paired downstream decision

1. Freeze baseline source/model/preprocessing/config/roster/court/rules và calibration dataset version. Approved default giữ nguyên khi chưa có đủ evidence/authorization promote. Hai checkpoints pilot/candidate cũ chỉ là candidates, không coi recipe target 30 epochs đã hoàn tất khi chỉ có 1 epoch artifact.
2. Chạy continuous baseline trên calibration hợp lệ của đợt 03, dùng production runner/evaluator. Xuất raw predictions trước evaluation, đủ PTS/REB/AST/identity/control/heatmap metrics nếu GT cho phép; không tuning formal test/reserve.
3. Error analysis theo tầng: detector miss/false ball → ball continuity → player/team/crops/OCR → event-time identity → control/pass → release/crossing/value/FT → REB/AST rules → ledger. Phân biệt thiếu evidence, thiếu visibility và lỗi logic; không mặc định mọi lỗi đều do thiếu training.
4. Chọn tối đa 2 thay đổi candidate có giả thuyết, phạm vi và metric thành công cụ thể trước khi chạy; ưu tiên sửa lỗi có bằng chứng hoặc cải thiện OCR/crop/association/config trong quyền hiện có. Nếu không có thay đổi hợp lý, vẫn phải hoàn thành baseline/error analysis/decision có dữ liệu, không tạo model cho đủ số.
5. Không mở training dài, đổi backend/model family hoặc tải weights mới chỉ vì prompt có chữ “cải thiện”. Chỉ dùng authorization đã xác minh; nếu training mới là điều kiện bắt buộc, chuẩn bị recipe/checks/resource estimate cụ thể rồi giữ phần phụ thuộc pending. Không chạy job trùng; kiểm process identity và heartbeat freshness trước resume.
6. Với mỗi candidate thực sự được thử, chạy paired trên cùng source frames/PTS/config/rules/evaluation version. Đo ball recall/false observations, human/rim regression, OCR-readable exact match/coverage, team/player/unknown/ID switches, strict control/pass, event-only/strict PTS/REB/AST và latency. Native mAP hoặc unit tests không thay downstream evaluation.
7. Giữ source/config freeze của run; sửa code tạo experiment version mới. Tách approved/draft negative specificity; không gọi zero predictions là specificity 100% khi thiếu reviewed negative GT.
8. Chọn giữ baseline hoặc candidate bằng bảng metrics, regression và uncertainty/sample size. Không promote chỉ để báo tiến bộ; candidate thất bại vẫn lưu comparison/reasons. Formal product gate P≥95%, R≥90% mỗi stat giữ nguyên, không hạ để pass.

Tests bắt buộc khi thay production: ball/OCR/identity/control/shot + REB/AST/ledger regressions tương ứng; independent probes đợt 01 còn phải pass; full suite sau sửa cuối. Chạy ít nhất một continuous development integration bằng selected profile và kiểm raw replay/score conservation. Thiếu label cho metric bắt buộc thì bổ sung theo protocol hoặc giữ task pending; không ngầm bỏ metric khỏi paired comparison.

## Đầu ra và checkpoint

- Baseline run + error index/evidence links, experiment plan có hashes và planned metrics.
- Candidate runs/comparisons nếu có; `decision.json` ghi selected profile/hash, lý do, regression/rollback, `promotion_status` và `quality_gate` tách biệt.
- Metrics/matches/raw predictions/commands/tests/logs/resource timing, selected-profile integration bundle, report và handoff.
- Training status nếu liên quan phải dựa trên process + epoch/results/checkpoints thực, không PID cũ đơn lẻ.

**Gate 04A kỹ thuật:** baseline, mọi experiment đã khởi động trong phạm vi và paired comparisons đã hoàn tất/được đóng có lý do, required metrics có ground truth hợp lệ, tests PASS và bundle đủ để tái lập quyết định. Không để job đang chạy rồi gọi task hoàn tất. Hủy experiment phải có terminal status, partial artifacts và quyết định rõ; nếu chưa có phép đo bắt buộc thì task chưa PASS.

Gate kỹ thuật có thể PASS với quyết định giữ baseline và `quality_gate=FAIL`. Khi đó report phải ghi recognition/MVP vẫn IN_PROGRESS và đề xuất vòng cải thiện tiếp theo, không gọi candidate accepted. Đợt 05 có thể xây UI/benchmark bằng selected verified baseline; **nghiệm thu MVP/đóng gói release ở đợt 06 vẫn bị chặn bởi quality gate 06A**.

Chỉ kết thúc khi task có đầu ra đo lường hoàn chỉnh hoặc blocker cụ thể với `PENDING_INPUT`; không chỉ đưa ra đề xuất train thêm rồi báo đã xong.
