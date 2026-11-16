# Prompt 03 — PRA evaluator → Canonical dataset và freeze

Thực thi **03A → 03B**, đọc [execution-contract.md](execution-contract.md) và kiểm checkpoints/handoff đợt 02. Xây evaluator trước để phần tooling không bị chờ nhãn; khi vào 03B, thiếu data/approval bắt buộc phải giữ 03B pending, không mở đợt 04. Không tự triển khai đợt 04.

Đọc `shot_evaluator.py`, `possession_evaluation.py`, `dataset_schema.py`, `dataset_review_validation.py`, `scripts/validate_dataset_v2.py`, specs contracts/rules/evaluation và Task04/13. Inventory lại reviewed GT/roster/geometry/rules trong `data/matches`, review packets và decision/handoff docs; không chỉ nhìn CSV rỗng rồi xin lại toàn bộ nhãn.

## 03A — Shared production evaluator đủ PTS/REB/AST

1. Tạo `codebase/scripts/evaluate_v2.py` và module dùng chung dưới `src/basketball_scoreboard` cho CLI và tests. Tái dùng/factor shared shot matching nếu phù hợp; không tạo evaluator riêng ngay trong test.
2. Nhận predictions immutable, dataset/version/protocol/coverage và model/config fingerprints. Recognition phải xuất predictions trước rồi evaluator mới đọc GT; không inject GT vào engine.
3. One-to-one matching theo frozen protocol: event type/video/time, actor/team/value/subtype/assist parent/pass links, collisions/ties/duplicates. Sai actor/value/link phải tạo strict attribution failure và strict FP/FN tương ứng; không chỉ báo accuracy trên những event dễ match.
4. Unknown/unresolved trên GT hợp lệ được tính missed/coverage theo protocol; uncertain/excluded chỉ loại theo policy có trước. Không bỏ background/no-event intervals để giấu FP. Denominator 0 trả null/N/A + reason.
5. Export per-stat event-only và strict TP/FP/FN/P/R/F1, matched/unmatched rows, per-video/session totals/offsets/coverage, identity/control/heatmap diagnostics nếu có GT. Không gọi shot-only metrics là full PRA.
6. Validate schema/hash/source/split/lock compatibility và malformed/nonfinite input; draft data cho diagnostic riêng, không trả formal accepted.

Tests độc lập: positive/negative PTS/REB/AST, wrong actor/value/subtype/link, duplicate, empty sets, unknown, time tolerance edges, matching collision/greedy trap, background FP, uncertain coverage, wrong binding và tampered lock. Hand-calculate ít nhất một bộ expected TP/FP/FN không dùng cùng algorithm để dựng expected.

Run bắt buộc: CLI với frozen synthetic fixture để đối soát metrics và CLI diagnostic với auto output thật của đợt 02 + reviewed packet tương thích hiện có. Nếu chưa có GT compatible cho một stat, export N/A có reason, không tạo review; formal evaluation còn ở 03B/06A. Chạy full suite sau code cuối.

**Gate 03A:** evaluator production có đủ ba stats, tests và hand-check pass, CLI xuất metrics/match tables/error index/version snapshots, report/handoff hoàn chỉnh. Technical evaluator PASS không đồng nghĩa data/quality PASS. Chỉ sau đó mở 03B.

## 03B — Hợp nhất reviewed GT, roster/rules/geometry và khóa dataset

1. Inventory approved/draft/uncertain records theo source/session/exposure, reviewed evidence và scope approval. Dùng lại các xác nhận đã có, không tự nâng packet draft thành approved hoặc hỏi lại control/roster đã được chốt.
2. Lập mapping sang canonical schema: source/clip offsets, PTS, player/team/possession/shot/pass IDs và review provenance. Tạo proposal/version dẫn xuất trước khi cập nhật namespace active; không ghi đè labels/locks nguồn. Chỉ merge phần đã có authorization, giữ provenance/reviewer nguồn chính xác.
3. Validate cross-references, shot/REB/AST eligibility và positive/negative coverage; geometry/source match; rules profile và evaluation applicability đã được duyệt. Không tự chốt các case FT/action còn chưa xác định.
4. Đưa missing labels thành review packet nhỏ theo video/timestamp/actor/case kèm evidence. Thiếu ảnh/frame không suy thành negative; không nhân bản samples để đạt collection targets. Mục tiêu ban đầu 50 shots/30 REB positives/30 AST positives cùng hard negatives là collection targets, không thay frozen acceptance policy.
5. Tách calibration/validation/test theo source family và exposure, giữ v1 lock và quyết định clip04. Same-match và source đã tune phải ghi diagnostic/exposed; muốn reserve mới cần nguồn/approval phù hợp. Không tự đổi split đã khóa.
6. Sau khi đủ review/data/rules/protocol, freeze bằng external manifest/hash theo tooling hiện có; không tự hash chính lock vào lock. Không sửa expected hashes để che mutation.

Chạy từ `codebase` và lưu JSON/exit codes:

```powershell
.venv/Scripts/python.exe scripts/validate_dataset_v2.py --require-tooling-ready
.venv/Scripts/python.exe scripts/validate_dataset_v2.py --require-data-ready
.venv/Scripts/python.exe scripts/validate_dataset_v2.py --require-locked
```

Kiểm tra `--help`/namespace flags trước khi chạy với dataset version khác; dùng validator đúng revision. Tests: mapping/time offsets, review provenance, dangling refs, split/exposure leakage, uncertain/draft isolation và lock tamper; full suite nếu sửa production code.

Đầu ra: inventory/provenance map, canonical proposal/active version đã duyệt, missing-input packet nếu có, validator results, lock/fingerprints và report/handoff cho calibration vs formal evaluation. Kiểm đối chiếu thủ công một số record với reviewed nguồn, không chỉ round-trip serializer.

**Gate 03B:** structural/tooling/data/locked readiness thật đều đạt và có bằng chứng approval phù hợp. Nếu chưa đủ, ghi `PENDING_INPUT` cùng missing list chính xác, task chưa hoàn tất và không mở đợt 04. Không dùng diagnostics 03A thay formal data readiness. Bàn giao formal test policy nhưng không chạy holdout để debug ở đợt này.
