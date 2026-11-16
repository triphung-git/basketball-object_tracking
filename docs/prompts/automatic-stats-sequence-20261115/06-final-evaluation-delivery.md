# Prompt 06 — Frozen quality evaluation → Đóng gói và clean-run

Thực thi **06A → 06B**, đọc [execution-contract.md](execution-contract.md), Task13–15 và checkpoints/handoffs đợt 01–05. **06B chỉ bắt đầu sau khi quality gate 06A PASS.** Không lấy implementation/tests/benchmark thay recognition acceptance.

## 06A — Nghiệm thu chất lượng PRA/heatmap trước correction

1. Kiểm selected code/model/config/data/roster/court/rules/protocol hashes, test authorization/exposure và frozen lock. Calibration đã dùng để chọn candidate không phải independent test. Nếu nguồn formal test đã dùng debug/tune, cần reserve/protocol revision phù hợp trước chạy.
2. Chạy production continuous pipeline trên frozen evaluation source đúng phạm vi; export raw auto predictions immutable và run bundle trước khi evaluator đọc GT. Không sửa tay hoặc dùng labels/window IDs/OCR scoreboard truth làm runtime hints.
3. Chạy shared `evaluate_v2.py` từ đợt 03 và ghi full matching tables cho PTS/REB/AST: event-only và strict actors/team/value/subtype/pass-score links, TP/FP/FN/P/R/F1, duplicates/background/unknown/unresolved và coverage. Per-video/session, sample sizes/uncertainty và initial score offsets rõ.
4. Đánh giá team/player/control/ID switches và heatmap/location theo frozen protocol; official negative specificity chỉ khi reviewed negatives/provenance đủ. N/A không phải PASS.
5. Hand-check mẫu cả TP/FP/FN/unknown từ source/evidence, đối soát boxscore vs auto ledger và raw replay/checkpoint. So fingerprints trước/sau để phát hiện mutation/leakage.
6. Full suite cuối, independent regression/probes liên quan, CLI/API/browser smoke với selected release profile và final bundle. Có thể reuse evidence còn cùng hash cho kiểm tra đã chạy; thay production code thì rerun checks bị ảnh hưởng và full suite.

**Quality gate 06A:** từng PTS/REB/AST đạt precision ≥95%, recall ≥90% theo frozen strict acceptance protocol và các điều kiện geometry/team/heatmap hiện hành (PLAN: team accuracy ≥90%, median position error ≤5% chiều rộng vùng sân, cùng coverage); đủ GT/cỡ mẫu/approval theo protocol, không còn P1 correctness/integration defect, tests/real-run/binding checks PASS.

Nếu thất bại hoặc thiếu dữ liệu: xuất đầy đủ failure/partial metrics, error index, commands, artifacts và report `FAIL` hoặc `PENDING_INPUT`; giữ MVP IN_PROGRESS. **Không mở 06B.** Đề xuất sửa trên calibration và reserve/version phù hợp, không sửa model rồi rerun cùng holdout để gọi independent PASS. Không hạ thresholds hoặc thay automatic results bằng corrected totals.

## 06B — Đóng gói, tái lập và bàn giao cuối

Chỉ thực hiện khi checkpoint 06A chất lượng PASS và evidence paths/hashes còn hợp lệ.

1. Hoàn thiện README/setup/user guide, sample config, dependency lock theo runtime đã test, local credentials hướng dẫn không lộ key, required model access/cache và offline caveats. Không ghi fully offline nếu còn cần authentication/metadata download.
2. Bundle source/config/tests và authorized demo artifacts: video hoặc source reference/quyền truy cập phù hợp, auto tracks/control/events/boxscore/heatmap/evidence/metrics, raw audit/checkpoint/corrections tách biệt, hashes/versions và benchmark report. Không nhúng media không có quyền chia sẻ.
3. Clean-run bằng đúng hướng dẫn từ working directory/user environment đã khai báo, dùng output mới. Nếu không tạo được environment/máy thứ hai, dùng controlled reproduction tương đương và nói rõ giới hạn; không bịa clean install. Không cài dependency/driver lớn chỉ để đóng gói khi chưa có quyền.
4. Từ clean-run, kiểm CLI actual video path → đủ auto PRA/heatmap/exports → dashboard playback/seek → download/parse → checkpoint/raw replay giữ totals. Không nhập hoặc xác nhận từng pha để tạo stats chính.
5. Lập acceptance matrix từng task/module: implemented/executed/measured/accepted, bằng chứng links và actual quality/performance. Chỉ cập nhật DONE khi requirement tương ứng đã đạt; giữ lịch sử reports và exposure/authorization cũ.
6. Tạo `docs/user-guide-v2.md`, `docs/reports/final-report-v2.md`, `docs/reports/acceptance-v2.md`; cập nhật PLAN/task index/README theo snapshot hiện hành. Không để các claim TODO/chưa có model/đang training lỗi thời nằm ở mục hiện trạng.
7. Kiểm bundle không lộ `.env`, token/signed URLs, cache secrets; không publish/upload/commit/push. Rà links, referenced files, CLI working directories, manifests/hashes và required artifact completeness.

Tests/run bắt buộc: clean-run integration + artifact schema/link/hash checks, CLI failure/no-overwrite và reload/replay. Nếu chỉ sửa docs sau tests cuối và code hashes không đổi, không chạy lại toàn inference/full suite vô ích. Nếu clean-run phát hiện lỗi cần sửa code, sửa rồi chạy lại required tests và quality checks phù hợp trước bàn giao; quality evidence bị thay đổi không được dùng nguyên.

**Gate 06B:** người nhận theo guide tái chạy được, đủ artifacts và acceptance matrix, chất lượng 06A và benchmark còn khớp selected profile, tests/clean-run PASS. Chỉ lúc đó báo MVP hoàn tất trong phạm vi đã đo; nêu rõ offline/footage constraints. Nếu gate fail, giữ 06B chưa hoàn tất và báo blocker cụ thể.
