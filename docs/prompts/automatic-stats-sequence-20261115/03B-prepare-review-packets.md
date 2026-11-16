# Bổ sung 03B — Làm rõ blockers và chuẩn bị dữ liệu để người dùng review

Tiếp tục trong task 03B đang PENDING_INPUT của `remaining-tasks-20261115`. Đọc [prompt tổng](00-execute-all-remaining.md), [quy trình chung](execution-contract.md), [prompt đợt 03](03-evaluator-dataset-freeze.md), missing packet/report/validator JSON hiện có. **Không mở task 04A hoặc thay dữ liệu/quality gates.** Thực thi các phần chuẩn bị thuộc 03B, không chỉ trả lại danh sách việc người dùng phải làm.

## 1. Sửa phân loại blocker bằng evidence

Giữ packet/report cũ để audit; tạo revision mới trong thư mục output mới và link từ state/report sau khi kiểm tra.

- Validator `scripts/validate_dataset_v2.py` hiện ghi 50 shots/30 rebounds/30 assists dưới dạng collection-target warnings. Đừng ghi `required_minimum=30` như hard acceptance threshold nếu chưa có policy/ngưỡng đã được phê duyệt riêng. Báo riêng target, actual counts, machine data-readiness và statistical adequacy. Không tự hạ frozen protocol hoặc dùng ít mẫu để tuyên bố generalization.
- Rebound individual có actor và subtype; `team_rebound` trong schema validator yêu cầu `actor_id` rỗng. Gói review phải hỗ trợ đúng cả hai, không bắt người dùng gán cầu thủ cho mọi team rebound.
- Spec court hiện dùng floor homography 2D, không yêu cầu reconstruct sân 3D. ROI ảnh chưa phải metric calibration; thiếu dimensions/landmarks/validation không được ghi geometry approved.
- Rules/roster/pilot protocol đã được duyệt ở namespace nào thì bảo toàn đúng scope. Roster review và pilot protocol Task07 không tự phê duyệt toàn bộ PRA/rules cho giải; không hỏi lại roster chỉ vì ruleset canonical vẫn pending.
- Raw validator đang chạy active `data/v2` còn rỗng, proposal là namespace khác. Không quy mọi missing active rows thành nhãn người dùng chưa cung cấp; tách migration/validation/activation work của agent khỏi thiếu GT thật.
- Ghi đủ mọi readiness note có thật: negative assist, identity/position GT, reviewed coverage, source provenance, made/miss, parent pass/shot reviews, split/lock và geometry. Không rút còn đúng 5 nếu còn thiếu mục khác.

## 2. Audit migration/proposal trước xin review mới

1. Đọc `consolidate_dataset_v2.py`, schema/review sources và proposal output hiện có. Đối chiếu counts, IDs, source hash, offsets local/global và status/evidence từng hàng.
2. Không coi 34 scoring confirmations đương nhiên thành 34 fully-timed/approved shot rows. Báo hàng nào đủ schema, hàng nào thiếu release/outcome/player/type/evidence; không tự điền timestamps hoặc reviewer/time.
3. Validate đúng namespace proposal bằng option hiện có hoặc một isolated revision có đủ manifest/rules/split/roster/annotations. Không chạy validator active rồi mô tả kết quả như đã kiểm proposal. Nếu sửa tooling namespace, thêm tests binding/refs/offsets/approval và chạy full suite sau production change.
4. Tạo migration map và dry-run diff cụ thể cho việc activate dữ liệu đã approved trong quyền hiện có. Giữ source packets, labels/splits/locks gốc. Chưa activate phần cần approval mới; không coi script chạy thành công là review dữ liệu hoàn tất.

## 3. Chuẩn bị review packet REB/AST trên footage development hiện có

1. Dùng nguồn/đoạn development đã được phép và các candidate observations/review windows hiện có. Không chạy holdout để tìm mẫu. Nếu cần khảo sát thêm phạm vi ngoài authorization, inventory/đề xuất phạm vi cụ thể trước phần phụ thuộc.
2. Cắt clips có đủ context trước/sau shot, miss/recovery hoặc pass→score. Mỗi item có source/clip hash, source-global và clip-local time/offset, teams/roster reference, candidate ID, evidence và câu hỏi cần review.
3. REB: parent missed-shot evidence, recovery time, team, actor nếu individual, offensive/defensive/team subtype, FT/eligibility/dead-ball context và lựa chọn uncertain/not-a-rebound.
4. AST: pass/scorer/shot links, passer/receiver/team, pass/release/catch/score times phù hợp schema, direct-action/chain-break/FT evidence, eligible/ineligible/uncertain. Bao gồm hard negatives có context, không chỉ positive suggestions.
5. Model/candidate suggestions luôn draft. Người dùng không cần điền CSV/JSON thủ công nếu có thể tạo review page/form đơn giản tái dùng tooling hiện có. Nếu xây UI, đọc skill áp dụng, test save/load/export và browser interactions; nếu browser không khả dụng phải ghi chưa verified.
6. Chia batch review đầu khoảng 6–10 tình huống hỗn hợp dễ kiểm trước, đồng thời inventory backlog tiến tới collection target 30 REB/30 AST. Không khẳng định footage hiện có chắc đủ 60 positives; báo actual candidates, unique sources và mẫu còn thiếu. Batch nhỏ không thay quality/minimum-sample policy đã chốt.
7. Test ingestion: giữ candidate IDs/hashes/source offsets; approved/uncertain/rejected tách đúng; round-trip không mất review; synthetic test files nằm riêng, không ghi vào real GT.

## 4. Rule applicability, split và calibration: agent chuẩn bị, người dùng review

- **Rules:** đọc nguồn official đang được dẫn, xác minh version/applicability và so case matrix với engines hiện tại. Chuẩn bị bảng ngắn các lựa chọn cần chốt cho chính giải/trận: FT/assist-to-FT, rebound/team/dead-ball, controlled tip/deflection, uncertain policy và evaluation tolerances. Không chỉ yêu cầu “duyệt FIBA 2024” khi còn khác biệt chưa được trình bày. Đánh dấu rõ rule nào đã có approval và scope nào còn mới; không suy từ một tham số dribble thành quy tắc chính thức.
- **Split:** inventory video/source-family/exposure hiện có; đề xuất calibration/test/reserve cụ thể nếu có nguồn phù hợp, kèm lý do độc lập. Đoạn khác cùng trận không tự thành independent match test. Nếu không có nguồn độc lập, ghi cần footage mới hoặc chỉ có same-match diagnostic; không tạo unseen giả. Người dùng cần cung cấp/chọn nguồn hoặc duyệt revision; agent lập partitions/hashes/lock sau khi đủ dữ liệu và authorization, không yêu cầu người dùng tự tạo `lock.json`.
- **Calibration:** trích frame gốc ổn định có source PTS/hash/segment, lập draft landmarks mặt sân và preview overlay để review. Chọn ít nhất 4 cặp điểm không suy biến, thêm independent check points và visible-foot GT theo guide. Xác định origin/axes/units/dimensions có nguồn; không dùng rim/backboard trên cao làm floor correspondence, không dùng kích thước fixture như sân thật. Nếu video không thấy đủ landmarks hoặc thiếu kích thước thật, đánh dấu chính xác phần cần người dùng xác nhận/cung cấp; không yêu cầu họ tự tính ma trận homography.

## 5. Đầu ra bắt buộc trước xin người dùng xử lý

- Revised missing-input packet có evidence/scope/owner, actual counts, target vs hard-policy distinction và các mục migration vs missing GT thật.
- Proposal validation results, migration/provenance map, source/approval discrepancy list.
- REB/AST review packet có clips/evidence, hướng dẫn thao tác, batch đầu và unique candidate inventory; test/QA logs và export/ingestion example.
- Rule applicability/case-matrix proposal có nguồn/version và câu hỏi cụ thể.
- Source/exposure split proposal hoặc evidence vì sao cần nguồn độc lập mới.
- Calibration frame/landmark proposal/preview và thiếu thông tin nào để validate.
- `commands.json`, artifacts/hashes, report/handoff cập nhật và state vẫn 03B PENDING_INPUT khi chưa đủ review/data/lock.

Nếu một gói không thể chuẩn bị với nguồn/quyền hiện có, bàn giao đầy đủ phần đã làm và blocker nhỏ nhất cho chính gói đó; không bịa output hoặc tự mở scope.

Sau khi người dùng review: ingest đúng records/decisions thực được xác nhận, validate đúng active revision, freeze khi đủ điều kiện và chạy lại gates 03B. Chỉ khi checkpoint 03B PASS mới resume 04A trong prompt tổng. Không đánh dấu 03B PASS vì đã hoàn thành gói review.
