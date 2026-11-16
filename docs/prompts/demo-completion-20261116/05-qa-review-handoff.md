# D11–D12 — Kiểm thử cuối, Plan duyệt tập trung và bàn giao

Đọc [prompt tổng](00-master-execution.md), [Plan mới](../../../PLAN-DEMO-20261116.md), brief và requirements nghiệm thu gốc. Không tự hạ quality gate; không đòi 100% mọi output để xây bản dùng thử. Hai việc này phải được phân biệt rõ trong verdict.

## D11 — Full regression, clean-run, browser và demo acceptance

1. Freeze selected demo profile/code/config/model/roster/court/rules/data/source/coverage và hashes. Checkpoint cũ chỉ reuse khi evidence vẫn áp dụng; không lấy benchmark/review kết quả của version khác làm chứng nhận version mới.
2. Chạy tests mục tiêu cần thiết + independent regressions/probes liên quan + full suite sau production changes cuối, lưu JUnit/log/exit codes. Không báo PASS từ tổng test count; phân loại baseline failures và sửa lỗi trong scope ảnh hưởng demo.
3. Clean-run theo đúng launcher/user guide từ output/workdir mới, environment đã khai báo. Có thể controlled reproduction nếu không có máy thứ hai, nhưng phải nói rõ; không bịa clean install hoặc cài lại GPU/dependencies lớn ngoài quyền đã có.
4. Test real-video path tự động end-to-end: decode/infer→team/player/control/pass→PRA→heatmap/ledger→overlay/dashboard→exports→reload/replay. Có declared demo set chứa bằng chứng PTS/REB/AST genuine auto positives và heatmap/attribution có evidence; GT chỉ dùng để chấm sau predictions.
5. Check đúng parent/event-time identity/value/subtype/assist link, score/team/player conservation và revisions/void/late arrival/duplicate/cancel/seek/reload. Unknown/unresolved phải giữ và đi vào metrics/coverage; không gán tay để đủ ba stats.
6. Browser thật: playback/seek/source offsets, event→evidence, timeline/boxscore/court/heatmap, progress/cancel/fail/partial, safe long text và download exports parse được, desktop/mobile layout; screenshots + machine-readable QA results. Check overlay frames và VFR/CFR readback theo actual scope.
7. Chạy evaluator shared trên compatible reviewed scope, có original vs basket-primary nếu dùng revision, event-only và strict per-stat. Hand-check TP/FP/FN/unknown samples, report size/session dependence/coverage/exposure. Không tuning independent test đã xem rồi gọi lại frozen pass.
8. Đối chiếu từng requirement của brief bằng crosswalk requirement→actual production code→test→real artifact→verdict. Không còn required item chỉ có mock/scaffold/constant “generated”.

### Verdict bắt buộc

- `technical_gate`: runtime/test/contract/integrity/output/QA đúng.
- `demo_gate`: chỉ READY khi đủ luồng và real-data proof bắt buộc của Plan, launcher/overlay/heatmap/UI/exports/clean-run đạt. Lỗi recognition còn lại có error report và uncertainty rõ; không yêu cầu 100% mọi pha.
- `quality_gate_06A`: PASS/FAIL/INSUFFICIENT_DATA theo targets gốc và valid protocol/source/split. P≥95%, R≥90% per stat không bị hạ tự động, same-match sparse metrics không tự thành quality acceptance.
- `approval_gate`: items Rxx chưa được xác nhận giữ WAITING_REVIEW; không ghi người dùng đã duyệt hoặc auto-promote model.

Nếu quality chưa đạt nhưng demo functionality thật đủ và không có integrity/runtime P1, được bàn giao `DEMO_READY_FOR_REVIEW`, giữ MVP/06A/06B chưa accepted. Nếu REB/AST luôn không tạo được real events, identity evidence không chạy, heatmap/overlay giả hoặc clean-run/browser fail thì chưa đủ demo; sửa phần thực thi được và bàn giao partial/blocker khi hết lựa chọn trong scope, không phát hành claim hoàn thiện.

**D11 checkpoint:** đầy đủ tests/clean-run/browser/evaluation/crosswalk logs và report; verdict tách biệt, không gộp thành một PASS. Nếu sửa code do QA, re-run checks bị ảnh hưởng + full suite và invalidate/recompute measurements liên quan trước chốt.

## D12 — Report sau từng task, Plan review duy nhất và resume sau duyệt

Task này cập nhật liên tục, không đợi D11 PASS mới bắt đầu tổng hợp.

1. Sau MỖI task/phase tạo report và handoff riêng: scope/version, yêu cầu→implementation→commands/cwd/exit→tests→real-run/evidence→verdict, files/reason, actual measurements, limitations/open issues và exact input/config/command cho phần tiếp theo.
2. Update `PLAN-DEMO-20261116.md` bảng D01–D12, dependencies/phases/status/hashes và evidence links. Đồng bộ `approval-register.json`; parse/schema/link checks phải PASS. Không chỉnh PLAN nghiệm thu gốc thành accepted nếu gate chưa đạt.
3. Gom mọi phần thật sự cần duyệt vào Rxx của Plan. Một item chỉ REVIEW_READY khi có artifacts cụ thể có thể xem: bbox UI/export/clips, calibration overlay+points/checks, coverage/GT packet, split/source exposure proposal, candidate paired table+rollback hoặc final demo/metrics. Nếu chưa chuẩn bị được thì ghi thiếu gì, không yêu cầu approve empty packet.
4. Ghi rõ quyết định nào đã được duyệt ở lịch sử và scope/hash, không hỏi lại. Không coi approval label batch đồng nghĩa training/default-model promotion; không coi model approval thay chất lượng thực.
5. Final review packet có README duy nhất dẫn tới launcher/user guide/demo bundle/screenshots/evaluation/benchmark/errors và các Rxx. Người dùng không cần đọc nhiều logs để biết mình phải quyết định gì; raw logs vẫn link cho audit.
6. Không kết thúc ở danh sách blockers nếu còn code/tooling/proposal/test/demo work độc lập có quyền làm. Khi tất cả phần độc lập đã hoàn tất và chỉ còn review/input, giữ state resumable, reports/bundle có thật và gửi Plan review một lần, không hỏi lặp tiếp tục từng task.
7. Sau người dùng review, chỉ apply các quyết định thực sự được xác nhận với exact Rxx/artifact/version, record decision nguồn/thời điểm. Resume D03/D06/data/model/quality phases bị chặn, không reset tất cả. Rerun validations/tests/evaluation/clean-run phù hợp thay đổi; corrected outputs không thay raw auto.
8. Nếu người dùng chưa review thì không tự approve, không chạy action phụ thuộc và không coi toàn task hoàn tất. Preparation/checkpoint có thể REVIEW_READY; execution phases/quality vẫn pending đúng thực tế.

### Đầu ra cuối

- Plan mới với bảng task/phase và Rxx đã được chuẩn bị có bằng chứng.
- Run root/state/checkpoints/commands/artifact manifest/approval register hợp lệ và resume command cụ thể.
- Demo bundle/launcher/user guide, reports từng task, report tổng cuối/crosswalk brief, test/browser/clean-run/evaluation/benchmark evidence.
- Verdict technical/demo/quality/approval riêng và known limitations: offline/input scope/unknowns/sample sizes/exposure; chưa có gì không được viết thành completed.
- Hướng dẫn một lần để người dùng chạy demo và review Plan; không yêu cầu trả lời một chuỗi câu hỏi phân tán.

**Chỉ kết thúc khi demo và review packet đủ điều kiện tương ứng hoặc đã hoàn thành mọi phần có thể thực thi và nêu đúng dependency ngoài quyền/đầu vào. Không tạo một bộ prompt mới thay cho công việc đã được giao.**
