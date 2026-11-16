# Prompt chung — Thực hiện task03 và task04, kiểm thử và bàn giao theo từng mốc

Bạn là Senior AI/Python Engineer phụ trách triển khai liên tục **task03 và task04** theo MVP v2 Automatic Stats đã được duyệt. Làm việc trực tiếp trên workspace hiện có, kiểm chứng bằng code/dữ liệu thật, cập nhật reports và bàn giao contracts để các task sau sử dụng.

**Không dừng sau khi chỉ hoàn thành task03.** Sau mốc kiểm thử/report/bàn giao task03, tự tiếp tục task04 trong phạm vi đã được giao; không hỏi lại “có tiếp tục task04 không?”. Nếu thiếu đầu vào hoặc cần một quyết định thật sự, hỏi cụ thể và tiếp tục phần độc lập còn thực hiện được. Không xem im lặng là phê duyệt.

## 1. Mục tiêu và giới hạn

- **Task03:** pipeline MP4 → frame/PTS → detection → overlay/exports/metadata, chạy được hết video và có contract tọa độ/thời gian đúng.
- **Task04:** dataset v2, schemas, annotation/review tools, ruleset và evaluation protocol cho tự động points/rebounds/assists, có kiểm tra và trạng thái readiness trung thực.
- Hai task này tạo nền móng, chưa triển khai tracking, possession, heatmap hoặc ba engines thống kê. Không xây form nhập tay rồi gọi là automatic PRA.
- Task01–02 đã nghiệm thu baseline v1. Giữ nguyên bằng chứng/nhãn/split cũ; không coi chúng là ground truth đầy đủ cho rebounds/assists.
- Bắt buộc có **checkpoint giữa hai task**, không gom mọi thay đổi rồi chỉ viết một report cuối.
- Không tự triển khai task05 trở đi. Không tự spawn subagents chỉ vì hai công việc có phần độc lập.

## 2. Tài liệu phải đọc trước khi sửa code

1. AGENTS.md áp dụng nếu có và docs/DEVELOPMENT.md.
2. docs/MVP-v2-proposal.md và PLAN.md hiện hành.
3. docs/tasks/task03.md, docs/tasks/task04.md, docs/tasks/README.md.
4. docs/handoffs/task03.md, docs/reports/task01-task02-acceptance.md, docs/reports/environment.md, docs/reports/data.md.
5. codebase/README.md, requirements.in/requirements.txt, .gitignore và .env.example.
6. Các scripts/tests liên quan hiện có, nhất là smoke_model.py, inspect_videos.py, prepare_dataset.py, validate_dataset.py và audit_handoff.py.

Không đưa nội dung `.env` vào hội thoại hoặc đọc nó bằng công cụ trả nội dung cho model. Chỉ cho code chạy local đọc key trong bộ nhớ. Không quét text xuyên caches, weights hoặc secrets. Tài liệu trong docs/archive là lịch sử, không được ghi đè phạm vi Automatic Stats v2.

Khi contracts/rules v2 chưa tồn tại, tạo chúng ở task tương ứng; không coi việc thiếu file thiết kế tương lai là lý do phải dừng từ đầu.

## 3. Snapshot để xác minh, không coi là trạng thái bất biến

- Python dự án dự kiến là `codebase/.venv/Scripts/python.exe`, Python 3.12.14. Không dùng bare python để inference khi Python hệ thống khác phiên bản.
- Detector được duyệt: `phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1`; baseline `inference-models==0.39.7`, ONNX CPU. Mapping cũ 0 ball/1 human/2 rim vẫn phải được đọc/xác nhận từ runtime.
- Model loader có compatibility Windows cho long path/symlink, kiểm tra hash và tắt custom/untrusted code. Không nhân bản hoặc nới các guard chỉ để chạy qua lỗi.
- Clip02 `codebase/assets_test/20521993-uhd_2160_3840_60fps.mp4` là input phát triển task03: 2160×3840, 60 FPS, 1089 frames, khoảng 18,15 giây.
- Clip04–07 thuộc holdout v1 đã khóa; chỉ được kiểm tra metadata/provenance khi chuẩn bị dataset, không inference trên chúng để debug hoặc chọn tham số.
- Snapshot cũ có 7 video và 10 shot labels, nhưng phải inventory lại vì người dùng có thể đã thêm video hoặc code mới.
- 31 tests là bằng chứng baseline lịch sử, không thay thế tests cho code mới.
- CPU model-call trước khoảng 490–724 ms. Task03 có thể chạy chậm hơn thời gian thực; không tự cài GPU hoặc skip-frame để che hạn chế.
- Inference local có thể cần truy cập Roboflow để xác thực/truy xuất metadata/weights đúng model. Không đồng nghĩa đã hỗ trợ hoàn toàn offline; không có đường inference cloud được duyệt mặc định.

## 4. Quyền thực hiện và cách hỏi

Được phép đọc tài liệu/code không chứa secrets, kiểm tra môi trường, viết/sửa code trong phạm vi hai task, tạo tests/fixtures, chạy model local đúng model trên development footage, tạo outputs mới và cập nhật docs. Tái sử dụng môi trường hiện có; không cài lại mọi thứ từ đầu nếu không cần.

Hỏi người dùng trước phần phụ thuộc khi cần:

- Model/backend mới, dependency lớn/GPU stack, thay Python hệ thống/driver.
- Upload media, cloud inference, dịch vụ trả phí hoặc tài nguyên phát sinh chi phí.
- Đổi labels/splits đã khóa, chuyển holdout sang calibration, thay ruleset/phạm vi đã thống nhất.
- Tắt checksum/TLS, bật untrusted/custom code hoặc dùng nguồn weights chưa xác minh.

Tuân thủ sandbox/network approval của công cụ. Quyền đã được cấp cho cùng hành động còn áp dụng thì không hỏi lại; không tìm đường né chặn. Không yêu cầu gửi key trong chat.

Hỏi dữ liệu task04 sớm nếu inventory cho thấy thiếu footage hai đội, roster, source/session, rule profile hoặc review ground truth. Một câu hỏi cần nêu rõ thiếu gì, ảnh hưởng gate nào và phần nào vẫn đang thực hiện. Không yêu cầu bổ sung lại thứ đã có.

## 5. Giai đoạn A — Khảo sát và lập execution checklist

1. Kiểm tra cây thư mục, code/test/doc thay đổi hiện có và interpreter/packages thực tế. Nếu có Git, xem trạng thái; nếu không có, không tự git init/commit/push.
2. Ghi danh sách phần đã có, phần phải sửa, phần thiếu dữ liệu. Không ghi completed chỉ vì có tên file.
3. Đọc fingerprint snapshot hoặc tính baseline hash các file dữ liệu v1 sẽ bảo vệ. Không sửa `.env`, video, labels, reviews, coverage hoặc splits v1.
4. Gửi yêu cầu đầu vào task04 còn thiếu trong khi bắt đầu task03. Có thể tạo templates/tooling task04 độc lập trước checkpoint, nhưng chưa chốt schema phụ thuộc frame contract chưa được nghiệm thu.
5. Tạo checklist thực thi cho G03 và G04; cập nhật task03/task04 thành IN_PROGRESS khi bắt đầu phần tương ứng, không đánh dấu DONE trước evidence.

## 6. Giai đoạn B — Triển khai và kiểm thử task03

### B1. Code và contracts

- Source dưới `codebase/src/basketball_scoreboard/`: contracts.py, config.py, video.py, detector.py, overlay.py, app.py và package initialization cần thiết.
- Config dưới codebase/configs/default.yaml hoặc cấu trúc tương đương có lý do; README phải ghi CLI thực tế.
- Frame contract: video_id, zero-based frame_index, normalized source_time_s, original_wh, raw PTS/time_base khi có và timestamp status/policy.
- Detections contract: xyxy ở frame gốc, class_id, class_name, confidence; không bịa detections khi lỗi model. Frame không có detections vẫn phải có record.
- Reader tuần tự, CFR/VFR, PTS chuẩn hóa theo video stream. Không dùng wall clock hoặc frame_index/avg_fps làm timestamp cho VFR.
- Missing/trùng/đảo PTS phải có policy rõ: từ chối, đánh dấu hoặc repair có audit; không âm thầm tạo đồng hồ giả.
- Loader đúng model/runtime, input BGR theo SDK đã kiểm tra, giữ tỷ lệ resize và chuyển tọa độ chính xác. Kiểm tra schema và NaN/Inf/class IDs/confidence/bbox geometry.
- Data/GT/manifest notes không là input recognition. Tách metadata kỹ thuật khỏi mô tả kết quả pha.
- Video export giữ tỷ lệ và thời lượng nguồn baseline; VFR phải preserve/resample có mapping được ghi. MVP không bắt buộc giữ audio.
- Output run directory mới có annotated.mp4, detections.jsonl và run.json. Metadata gồm fingerprint nguồn, config/runtime/model/versions, timebase, frame counts, timing scope và trạng thái completed/failed/incomplete.
- Cleanup handles khi EOF/lỗi/hủy; writer thất bại không tạo success report. Không ghi đè video gốc hoặc output cũ.

Ghi frame/detection contract vào `docs/specs/contracts-v2.md`. Task03 chỉ chốt phần nền; event/identity/rules schemas được task04 bổ sung sau, không tạo vòng phụ thuộc.

### B2. Kiểm thử bắt buộc

1. Unit/contract tests cho tọa độ ngang/dọc, empty detections, invalid bbox/class/confidence, input/config sai.
2. Fixture CFR/VFR với PTS không đều, missing/non-monotonic PTS và EOF; kiểm tra timestamp theo nội dung nguồn.
3. Lỗi decoder/model/writer và cancellation phải đóng tài nguyên, trả exit code/status có nghĩa, không lộ authenticated URL/key.
4. Smoke ngắn nếu cần trước integration; sau khi logic ổn, **chạy hết clip02 bằng đúng model**, giữ đủ frame.
5. Đọc lại MP4 đầu ra bằng công cụ độc lập hoặc reader phù hợp: frame count, shape, FPS/PTS/export mapping, thời lượng và khả năng mở.
6. Mở ảnh/frame thực tế đối chiếu overlay với JSON, gồm bóng/người/rổ và frame không detection nếu có.
7. Đo model-call và toàn pipeline riêng, nêu warm-up, resize và có/không tính vẽ/ghi. Không báo 1/model_latency là FPS ứng dụng.

Dùng venv hiện có để chạy tests. CLI mới phải do implementation thực tế quyết định, không chép lệnh giả vào report. Chỉ broaden/repeat khi có thay đổi, lỗi hoặc nghi vấn mới; không chạy inference toàn bộ holdout hoặc benchmark lặp không cần thiết.

### B3. Checkpoint G03 — Report và bàn giao giữa hai task

Trước khi tuyên bố task03 hoàn tất, tạo:

- `docs/reports/task03-pipeline.md`.
- `docs/handoffs/task03-to-task04.md`.
- Frame/detection section trong `docs/specs/contracts-v2.md`.
- README lệnh chạy thực tế và task03 checklist có evidence.

Report phải có: scope, file changes, interpreter/model/backend, commands/exit codes, tests và số ca pass/fail, integration input/output paths, frame counts/shape/timebase, ảnh review, model/full-pipeline timings, lỗi đã sửa, hạn chế còn lại và kết luận PASS/FAIL/IN_PROGRESS.

Handoff phải có: contract version/fields/units, PTS normalization và export policy, artifact schema, đường dẫn run tham chiếu, lỗi cần lưu ý, metadata task04 có thể dùng và danh sách không được dùng như GT. Đánh dấu trường nào đã verified và trường nào còn là thiết kế.

**G03 PASS** khi toàn bộ tiêu chí task03 có evidence, không có lỗi nghiêm trọng về secrets, timestamp, tọa độ hoặc output integrity. Nếu có lỗi cần sửa, sửa và chạy lại đúng kiểm thử bị ảnh hưởng trước đánh dấu DONE.

Sau checkpoint, cập nhật ngắn cho người dùng rồi **tiếp tục task04 ngay**, không kết thúc lượt chỉ để xin phép chuyển task. Nếu task03 thật sự bị chặn bởi quyền/model, giữ IN_PROGRESS, báo rõ và vẫn hoàn thiện tooling task04 không phụ thuộc integration.

## 7. Giai đoạn C — Triển khai task04 trên nền đã bàn giao

### C1. Inventory và versioning dataset v2

- Namespace `codebase/data/v2/`; không rename hoặc ghi đè data/manifest.csv, data/annotations hoặc data/splits.json của v1.
- Manifest v2 có source path/fingerprint, stream metadata, timebase, camera/session/source_group, eligibility và exposure notes; IDs ổn định theo nguồn, không theo thứ tự liệt kê.
- Media vẫn ở nơi ignored phù hợp, manifest chỉ tham chiếu; không tự copy hàng loạt video lớn vào thư mục được commit.
- Dẫn xuất/crop/replay/re-encode/cùng pha/cùng session phải có provenance và giữ cùng nhóm chống leakage. Hash khác không chứng minh độc lập ngữ nghĩa.
- Không tự coi mỗi file là session mới. Unknown provenance phải được báo trước khi khóa split.

### C2. Schemas và annotation workflow

Định nghĩa/tạo các bảng theo task04, ít nhất biểu đạt được:

- Roster: team/player/jersey, aliases và tính duy nhất trong phạm vi giải/phiên.
- Player positions/identity: timestamp, điểm ảnh/sân, track hoặc observation ref, player/team, visibility/uncertainty.
- Ball control: khoảng thời gian, controller/team hoặc free/unknown, evidence; tách quan sát khỏi dự đoán.
- Pass: passer/receiver, release/receive times, possession ref, deflection/handoff khi phù hợp.
- Shot: shooter/team, release/outcome time, kind, value, made/miss/uncertain và FT series context.
- Rebound: actor/team hoặc team rebound, offensive/defensive, time, shot/control refs.
- Assist: passer/scorer, pass/shot/score refs, time và eligibility theo ruleset.
- Coverage: fully reviewed/background/excluded/unreviewed/uncertain policy; không chỉ annotate lúc có pha ném rồi bỏ toàn bộ background.
- Review ledger: draft/approved/rejected/needs_review, reviewer/time/reason và history/provenance.

Draft và approved tách biệt; agent có thể đề xuất từ video gốc nhưng không tự ghi người dùng đã duyệt. Headers/templates/synthetic fixtures chưa phải dataset sẵn sàng. Không lấy detections hoặc GT v1 để suy labels rebound/assist mà không xem và review độc lập.

Mọi bảng dùng source PTS normalization theo handoff G03. Nếu chuyển frame index ↔ timestamp, dùng đúng decoder timebase, không avg_fps cho VFR. Ghi tolerance và độ chính xác annotation.

### C3. Rule profile và evaluation protocol

- Tìm/đọc nguồn chính thức hiện hành, ghi URL/tên/version/ngày truy cập và applicability đối với giải 3x3. Không coi toàn bộ manual 5x5 tự động là profile 3x3.
- Ruleset gồm point values/shot kinds/FT, control/controlled tip, eligible rebounds/team rebound/dead ball và assist/no-assist cases; quy định rõ tình huống không quan sát đủ bằng chứng.
- Case matrix có positive/negative/uncertain và ví dụ căn cứ, không dùng một ngưỡng N giây thay định nghĩa assist hoặc nearest-player thay rebound.
- Chia calibration/validation/test, reserve nếu đủ nguồn, theo nhóm session/pha. Clip04–07 v1 không tự biến thành calibration v2; ghi exposure/revision nếu người dùng duyệt thay đổi.
- Chốt protocol trước output holdout: one-to-one matching, time windows, tie/duplicates, strict actor/team/value/subtype/link correctness, coverage/ignored intervals, zero-denominator policy và uncertainty.
- Mục tiêu làm việc theo PLAN: P≥95%, R≥90% cho từng stat; ghi đây là target chưa đo. Unknown/unresolved trên GT hợp lệ phải làm giảm recall/attribution, không bị loại để nâng điểm.
- Task04 chỉ xây dữ liệu/protocol/validator; chưa triển khai evaluator task13 hoặc tuyên bố engines PRA đã đạt target.

### C4. Validator v2 và tests

Tạo công cụ rõ tên/version/CLI riêng cho v2 hoặc extension có backward compatibility được kiểm thử; `validate_dataset.py --require-ready` v1 không chứng minh readiness v2.

Validator phải kiểm tra:

1. Schema/types/finite times, source existence/hash, time bounds và coverage gaps/overlaps.
2. Referential integrity giữa roster/identity/control/pass/shot/rebound/assist, actor/team consistency, chronological constraints và giá trị phù hợp rule profile.
3. Draft/approved isolation, thiếu reviewer/time/evidence; không promote draft bằng một lần validator pass.
4. Split disjointness/group membership/session/duplicate footage và exposure/provenance.
5. Fingerprints của labels/reviews/coverage/roster/rules và split specification khi khóa. Không dùng self-hash bất khả thi: nếu cần hash toàn split, lưu ở external lock manifest/snapshot, không tự nhúng hash của chính file vào nó.
6. Cỡ mẫu, thiếu event types/negative controls, unknown provenance và loại video không đủ scope, tách khỏi lỗi schema.

Có trạng thái tách biệt: structurally valid, tooling-ready, data-ready và locked-ready. Header-only có thể valid nhưng không data-ready. Một CLI exit 0 do schema hợp lệ không được diễn giải là task04 DONE.

Tests có fixtures độc lập cho dangling refs, nonfinite/out-of-range PTS, approved thiếu review, duplicate actors/IDs, impossible event links, replay/session leakage, locked-file tamper và coverage readiness. Không trộn synthetic fixtures vào dữ liệu thật.

Mục tiêu thu thập ≥50 shots, ≥30 rebound positives và ≥30 assist positives kèm hard negatives theo task04 là mục tiêu lập dataset; không được bịa hoặc nhân bản pha để đủ số. Pilot nhỏ báo đúng giới hạn; thiếu nhãn đã duyệt của một stat thì chưa đạt task04 đầy đủ.

### C5. Checkpoint G04 — Report và handoff cuối

Tạo/cập nhật:

- `docs/data/ANNOTATION_GUIDE-v2.md`.
- `docs/specs/contracts-v2.md`, `rules-v2.md`, `evaluation-protocol-v2.md`.
- `docs/reports/data-v2.md`: inventory, labels/review counts theo stat/split/session, coverage, source/rules versions, quality warnings và readiness.
- `docs/reports/task03-task04-acceptance.md`: nghiệm thu hai mốc, test/evidence matrix, issues resolved/open và kết luận riêng từng task.
- `docs/handoffs/task04-to-task05-06.md`: input/config/contracts/tool commands/fingerprints cho court và player/identity tasks.
- README thực tế, task03/task04 status và links trong task index nếu cần.

**G04 PASS** khi có GT đủ loại đã được người dùng review, rules/protocol/splits chốt đúng policy, integrity/tests pass và các module sau có contracts usable. Không thay đổi status locked chỉ vì người dùng đã duyệt mục tiêu sản phẩm; phê duyệt labels/split là quyết định dữ liệu riêng.

Nếu dữ liệu/review chưa đủ: hoàn thành tooling/templates/guide/tests/report, giữ task04 IN_PROGRESS, ghi danh sách cần bổ sung cụ thể theo video/event/actor/timestamp hoặc rule case. Không đánh dấu DONE cho toàn task04 chỉ vì scripts chạy và CSV tồn tại.

## 8. Kiểm tra bàn giao chung sau G03 và G04

- So contracts task03→task04: IDs, tọa độ, PTS/units, source hash và visibility/uncertainty không mâu thuẫn.
- Thử dùng output metadata/detection từ task03 với tooling task04 ở mức kỹ thuật; không chuyển predictions thành ground truth tự động.
- Chạy các tests v1 liên quan để bảo đảm thay đổi shared code không phá baseline; chạy tests mới task03/04 và integrity validator đúng namespace. Sau khi pass, không lặp lại toàn bộ chỉ vì viết thêm prose.
- Đối chiếu fingerprint dữ liệu v1 trước/sau; mọi thay đổi không được duyệt là lỗi nghiệm thu cần xử lý, không cập nhật hash để che.
- Kiểm tra local links, CLI từ đúng working directory, output paths mở được, package/dependency versions và logs không chứa secrets.
- Ghi artifacts đã có thật khác với artifacts còn dự kiến. Không tạo report hoàn thành bằng placeholder số liệu.

## 9. Mẫu report/handoff bắt buộc

Mỗi report có tối thiểu:

```text
Task / scope version / thời điểm / trạng thái
Yêu cầu → implementation → bằng chứng → PASS/FAIL/PENDING
File changes và lý do
Input/config/model/dataset/rules/contract versions + fingerprints
Commands, working directory, exit codes
Tests: ca nào, kết quả, log/report paths
Integration output và kiểm tra độc lập
Metrics/timing scope hoặc counts/readiness (không tự điền N/A thành 100%)
Issues đã sửa, issues còn mở, giới hạn
Điều kiện tiếp tục và dữ liệu/quyết định người dùng còn thiếu
Handoff cho task tiếp theo
```

Handoff không chỉ là “đã xong”: phải chỉ được người nhận mở file nào, dùng contract/CLI nào, điểm gì đã verified và điểm gì còn blocked. Không nhét secrets hoặc video/base64 vào Markdown.

## 10. Giao tiếp và tiêu chí kết thúc lượt

Cập nhật ngắn khi có phát hiện, lỗi, mốc test hoặc quyết định; không để một lệnh inference dài làm người dùng mất thông tin tiến độ. Có thể dùng process session/poll để giữ phản hồi; không mở cửa sổ GUI/bật trình duyệt trừ khi cần và có quyền phù hợp.

Sau G03 PASS, thông báo checkpoint rồi tiếp tục G04. Khi gặp yêu cầu dữ liệu/approval, giữ câu hỏi pending và làm phần độc lập; thời gian trôi qua không thay thế câu trả lời. Không dừng cả hai task chỉ vì một phần labeling đang chờ.

Kết thúc bằng tiếng Việt, có:

1. Task03 và task04 **mỗi task một trạng thái**, cùng bằng chứng tương ứng.
2. Links tới report G03, handoff giữa hai task, report dữ liệu v2, report nghiệm thu chung và handoff task05–06.
3. Tests thực tế và integration outputs; cỡ mẫu/schema readiness/data readiness tách biệt.
4. Các file quan trọng, contracts/versions và dữ liệu v1 được bảo toàn.
5. Nếu còn thiếu đầu vào: yêu cầu cụ thể, phần đã hoàn tất và phần chưa thể nghiệm thu; không xin key trong chat.

Chỉ báo “cả hai task DONE” khi G03 và G04 đều pass. Trường hợp G03 PASS/G04 IN_PROGRESS là bàn giao một phần hợp lệ và phải nói rõ; không tiến task05+ như cách bỏ qua một gate chưa đạt.
