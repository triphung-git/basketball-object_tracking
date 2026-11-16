# Bàn giao Task07B — 2026-11-06

[Report và lệnh tái chạy](../reports/task07b-crop-ownership-20261106.md).290tests PASS; Task07 IN_PROGRESS. Không training/weights/backend mới, không yêu cầu review thêm.

## Artifacts

ROOT: `codebase/outputs/task07b-ownership-20261106/`.

- `baseline-source-snapshot/`, `before-source-hashes.json`: source trước thay đổi; `baseline-replay/`: pairedbaseline900frame/14007observations.
- `baseline-source-geometry.json`, `identity-source-contact.jpg`, `source-hud-reference.jpg`: audit source, bbox/crop vàHUD.
- `guard-only/`, `guard-jersey/`: coldguard trials; `cold-policy-source/` giữ code tương ứng.
- `recovery-jersey/`, `recovery-crop-probe/`, `recovery-policy-source/`: recovery bằng absolute color coverage còn regression, giữ để audit.
- `recovery-final/`, `final-crop-probe/`: relative color dominance giữ7/7good crops, chặn4/7bad crops; fullintegration vẫn regression, khôngpromote.
- `team-region-only/`: A/B chỉ đổi vùng màu; chưa sửa lỗi consensus.
- `team-conflict-reset/`: candidate hẹp, sửa team snapshots5/7→7/7; player snapshots4/7không tăng, player_id count859→695 nên không tuyên bố overallidentity tốt hơn.
- `ball-team-conflict-reset/debug.mp4` và `ball-team-conflict-reset-evaluation/evaluation.json`:900frames, ball36/72=50%, strictcontrol0%, passrecall0%, precisionN/A, integrityguardsPASS.
- `trace-team-conflict-reset/trace.json`: control duration decomposition và5GT pass endpoints.
- `evaluation-final/evaluation.json`, `evaluation-final/comparison.html`: mọi trial, labels chỉ đọc sau predictionfreeze.
- `disabled-final-equivalence.json`:14007/14007observations tương đương khi options tắt.
- `tests-final.log/json`:290tests PASS. `tests.log`287tests là checkpoint trung gian.

## Code và lựa chọn cấu hình

- `identity_crops.py`: source-only ownership/mask guard, source-boundpolicyloader.
- `identity.py`: optionalvalid-mask cho màu vàcausal invalidation; default color behavior giữ nguyên.
- `track_players.py`: optionalfullguard, isolatedteam crop vàteam-conflict reset. Defaultslegacy/off.
- `probe_task07b_identity_ownership.py`, `evaluate_task07b_identity_ownership.py`, `trace_task07b_control_failures.py`: chẩn đoán/tái lập; GT không vào recognition.
- `configs/task07b/`: camera-boundguard configs. Không dùngHUD coordinates của đoạndevelopment cho clip khác.

Đề xuất candidate để tiếp tụcdevelopment: `--team-crop-region jersey --reset-on-team-conflict`, giữOCRupscale3 và cùngcache đã xác minh. Chưa bật mặc định hoặc freeze07C. Fullguard tuy chặn crop lỗi nhưng kéo roleunknown vào ballcontext làm recall giảm45,83%, nên giữ experimental.

## Blockers và bước tiếp theo

1. Role dùng choball association hiện phụ thuộc identity/team enrichment. Cần tách evidence về actor/body khỏi uncertainty củajersey, cósource provenance vàtests; không dùngGT role để runtimevượtgate.
2. Các side-view/wrong-region0178/0192 vẫn có OCR ngoài số áo; shape/color chưa đủ semanticownership. Không ép đọc theo roster.
3. Ball detector vẫn thiếu candidates đúng; candidatehẹp không cải thiện ballrecall. Cần clean data/source-group split/checkpoint/recipe cụ thể trước trìnhtrainapproval. Không có quyềntrain mặc nhiên từ checkpoint này.
4. Chưa có đủtrajectoryGT để đánhgiátemporalidentity hoặcID switches;7snapshot không thay thếcontrol/passgate90/95/90 đã duyệt.
5. Giữ `pilot_0062` uncertain, không hỏi lại xác nhận đã có. Mergedprogress49approved/2skipped/308unreviewed và14crop đãreview vẫnlànguồnnhãn, không dùngsyntheticUIfixtures.

Không yêu cầu người dùng review lại12frame/14crop. Nếu cần bổ sung, chỉ hỏi tối đa4case có mâu thuẫn thực sự, tiếp tục việc độc lập trong lúc chờ.
