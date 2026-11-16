# Checkpoint A — nhận nhãn đã review và đối soát detection/identity

Ngày 2026-11-05. Đã nhận JSON của reviewer `triphung`, kiểm tra source/manifest và hợp nhất phần hoàn tất vào snapshot mới. **278 tests PASS; Task07 IN_PROGRESS.** Có thêm nhãn thật để chẩn đoán, chưa nghiệm thu accuracy hoặc phê duyệt training.

## Nhãn được nhận và hai xác nhận bổ sung

[JSON gốc người dùng trả lại](../../codebase/outputs/task07-checkpoint-a-review-20261105-run-08/task07-checkpoint-a-review.json) có10ảnh approved,2ảnh skipped và14crop identity reviewed. SHA gốc: `bf033587bbd308520f3173d48cd1b0407ce5f07df2033454bf0e69fa9f18bed3`. File này được giữ nguyên.

Đã đối soát2trường hợp bằng câu hỏi cụ thể và nhận xác nhận của người dùng:

1. `pilot_0061`,541s: bbox `[880.8486,446.6732,967.8688,648.4860]` bao quanh cầu thủ Tonga được đổi class từball sanghuman; giữ bbox bóng nhỏ trên tay cầu thủ Việt Nam. Không thay tọa độ hay đoán bbox mới.
2. `pilot_0062`,542s: ghi chú nói bóng quá mờ để vẽ. Đổi thành `needs_review`, visibility=`uncertain`; chưa dùng như negative hoặc mẫu chấm recall. Giữ các human/rim boxes và ghi chú trong corrected subset, không mất công review đã làm.

[Quyết định và hashes](../../codebase/outputs/task07-checkpoint-a-return-20261105/user-label-decisions.json). [Subset corrected v2](../../codebase/outputs/task07-checkpoint-a-return-20261105/reviewed-subset-corrected-v2.json) có9approved,2skipped và1needs_review; đủ14identity reviewed. SHA corrected: `cab6fba16c19c6e59fb224935037b19e4221284f356d956b7f3c0453fcce311a`.

Hai ảnh bị loại `pilot_0141/0142` là cảnh cận đã được người dùng xác nhận. Check-ball/restart trong nhóm570–572s vẫn được giữ, không nhầm thành ngoài phạm vi vì trận tạm dừng.

## Snapshot dùng cho công việc tiếp theo

ROOT: `codebase/outputs/task07-checkpoint-a-return-20261105/accepted-v2/`.

- [Merged progress v3](../../codebase/outputs/task07-checkpoint-a-return-20261105/accepted-v2/merged-progress-v3.json): **49approved,2skipped,308unreviewed** trong359source samples.40ảnh approved cũ giữ nguyên từng row;9ảnh hoàn tất mới được thêm.
- 308unreviewed gồm307ảnh ngoài batch và `pilot_0062` chưa được nhập thành nhãn hoàn tất. Nhãn human/rim đang review củaframe này vẫn nằm trong corrected subset, không bị coi là empty negative.
- [14crop identity đã review](../../codebase/outputs/task07-checkpoint-a-return-20261105/accepted-v2/identity-reviewed-subset.json) tách khỏi predictions;190crop chưa review còn ở nguồn, không bị đánh dấu skipped.
- [Validation](../../codebase/outputs/task07-checkpoint-a-return-20261105/accepted-v2/subset-validation.json), [merged audit](../../codebase/outputs/task07-checkpoint-a-return-20261105/accepted-v2/merged-progress-audit.json), [readiness](../../codebase/outputs/task07-checkpoint-a-return-20261105/accepted-v2/training-readiness.json).

Sửa nhỏ merger để giữ `reviewer_note`, `reviewer` và `scope_decision` của nhãn mới; regression kiểm tra cả việc không thay40row cũ. Không sửa source packet, locked splits, canonical control/pass GT hoặc manifest run-08. Không nạp các fixture `ui-qa/synthetic-*.json`.

## Ball detection — số liệu trên batch mới

Chỉ9ảnh approved được chấm:8visible balls và1ảnh not_visible. Hai ảnh cận và1ảnh uncertain không vào mẫu số. Cùng cached predictions đã tạo trước review, IoU≥0,30:

| Proposal | TP | FP/unmatched | FN | Precision so với nhãn | Recall |
|---|---:|---:|---:|---:|---:|
| Raw candidates |6|21|2|22,22%|75%|
| Confidence top1 |4|5|4|44,44%|50%|

[Evaluation và per-frame rows](../../codebase/outputs/task07-checkpoint-a-return-20261105/accepted-v2/ball-proposal-evaluation.json).

- Detector thiếu candidate khớp ở541s và570s.570s là bóng trên tay trọng tài trước check-ball, cho thấy không được đòi bóng phải gần player đang kiểm soát mới được detection.
-920/921s có candidate đúng nhưng top1 chọn sai. Đây là lỗi selection riêng với detector miss.
- Ảnh740s người dùng xác nhận not_visible vẫn có3raw candidates; không dùng `pilot_0062` uncertain để tăng số negative.
- Historical context-selector artifacts không có kết quả cho các cửa sổ mới này. Không áp ROI thủ công của360–405s sang nhóm540/570/740/920s để tạo số accuracy giả.

75% ở đây không phải tiến bộ từ57,58% của40ảnh cũ: khác batch, số mẫu rất nhỏ và được chọn có mục đích. Continuous900frame observed recall vẫn là36/72=50%, chưa chạy lại detector/continuous tracking trong lần tiếp nhận này.

## Identity — nguyên nhân nay có nhãn xác nhận

Trong14crop được chọn để chẩn đoán:

| Crop assessment người dùng | Số crop |
|---|---:|
| Đúng người/vùng |7|
| Sai vùng |6|
| Sai đối tượng |1|

Đây là tần suất trong batch chọn lọc, không phải crop error rate toàn video.

- `crop_0038`: người dùng xác nhận đó là **bảng rổ, không phải cầu thủ**. Gợi ý OCR4/3 và roleplayer tại đây không phải bằng chứng identity.
- `crop_0145/0151`: người dùng xác nhận crop chứa **hai người**. Không diễn giải OCR18→6 trên cùngtrack là chắc chắn cầu thủ đổi số hoặc OCR engine đơn thuần đọc sai.
- `crop_0033/0055/0178/0192`: cần sửa vùng lấy số/ownership trước khi dùng làm benchmark chữ số.
- `crop_0059`: nhãn Tonga#18 nhưng historical team proposal làViệt Nam.
- `crop_0136`: nhãn Việt Nam#6 nhưng historical team proposal làTonga, OCR không có reading.

Có5crop đúng người/vùng và readable, dùng đo exact OCR có tính missing là lỗi. Historical proposal đúng4/5, coverage4/5. Trên7correct player crops có team đã xác định, historical team proposal đúng5/7. Đây là **raw proposal agreement**, chưa phải resolver identity accuracy theo thời gian. Không có trajectory labels để đếm ID switches hoặc tính coverage theo thời lượng.

[Identity diagnostic JSON](../../codebase/outputs/task07-checkpoint-a-return-20261105/accepted-v2/identity-proposal-evaluation.json), [gallery đối chiếu crop/nhãn/predictions](../../codebase/outputs/task07-checkpoint-a-return-20261105/accepted-v2/identity-diagnosis.html).

## Đã chạy probe OCR local, không dùng GT làm recognition input

Giữ nguyên14JPEG crops đã chọn trước review, cùng EasyOCR weights cached, CPU, `download_enabled=False`, confidence0,5. Probe chỉ nhận manifest và roster; chỉ evaluator đọc nhãn sau khi predictions được ghi và hash. Không lấy nhãn để chọn candidate OCR.

| Cấu hình | Exact OCR trên5readable correct crops | Có reading |
|---|---:|---:|
| Historical run v2, upscale3 |4/5|4/5|
| Fresh native1 |3/5|3/5|
| Fresh upscale2 |2/5|3/5|
| Fresh upscale3 — đúng cấu hình baseline v2 |4/5|4/5|

Sau khi kiểm metadata v2 xác nhận `ocr_upscale=3`, đã bổ sung probe3 để so đúng baseline. Fresh3 tái lập top number/không có reading trên cả5mẫu readable:0020→2,0076→1,0104→1,0136→missing,0165→6. Không chuyển production sang1/2; không tăng scale tiếp để tối ưu trên5nhãn nhỏ.

42crop calls tổng cộng trong2runs; không download, GPU, runtime error hoặc đổi weights. Tất cả crop qua numerical quality gate hiện tại, dù7crop được người dùng xác nhận sai vùng/đối tượng. Đây là bằng chứng gate kích thước/contrast/sharpness chưa đủ để kiểm tra crop thuộc đúng người/vùng số.

Prototype-masked color extraction hiện có, khi chạy trực tiếp trên7correct player crops, cho team đúng7/7 ở cả3scale. Historical5/7 và fresh7/7 không phải một A/B cô lập: historical dùng team evidence của tracker, fresh dùng pixel từ jersey crop cố định. Cần tích hợp/đối soát crop, thời điểm và consensus để chuyển tín hiệu này thành identity đúng theo thời gian; chưa promote hoặc tuyên bố team accuracy100% toàn video.

- [Fresh1/2 run](../../codebase/outputs/task07-checkpoint-a-return-20261105/fresh-identity-probe/run.json), [evaluation](../../codebase/outputs/task07-checkpoint-a-return-20261105/fresh-identity-evaluation/evaluation.json).
- [Fresh baseline3 run](../../codebase/outputs/task07-checkpoint-a-return-20261105/fresh-identity-baseline3/run.json), [evaluation](../../codebase/outputs/task07-checkpoint-a-return-20261105/fresh-identity-baseline3-evaluation/evaluation.json).

## Kiểm thử và bước tiếp theo

**278tests PASS**, [log](../../codebase/outputs/task07-checkpoint-a-return-20261105/tests-return.log). Thêm3tests bảo vệ mẫu số OCR/missing, top1 không đọc đáp án để chọn số, và uncertain không thành negative/recall sample. Testmerger bổ sung bảo toàn reviewer/note/scope; ingestion và42fresh OCR calls đã chạy thực tế.

Ưu tiên tiếp theo, không yêu cầu người dùng review lại batch:

1. **Crop/track ownership:** chặn crop bảng rổ/non-player; kiểm tra bbox chứa nhiều người và lựa chọn torso đúng trước OCR. Giữ raw evidence để audit, không dùng danh sách sample IDs đã gán nhãn làm whitelist/blacklist recognition.
2. **Team evidence:** đối chiếu region và event-time mapping cho hai team errors đã xác nhận; thử bộ trích màu hiện có trên source stream với causal consensus, không dùng team GT để điền runtime.
3. **Ball data:** giữ các mẫu miss bóng trên tay/trên không và false candidates làm nguồn QA dữ liệu; tiếp tục chuẩn bị clean split/recipe/checkpoint trước đề xuất fine-tune. Không có quyền train/đổi weights từ việc nhận nhãn này.
4. **Validation:** freeze trước khi đo lại continuous video; vẫn cần đủ GT theo protocol và nguồn khác nếu kết luận tổng quát. `pilot_0062` tiếp tục uncertain cho đến khi có quan sát đủ rõ, không cần hỏi lại xác nhận đã có.

Checkpoint A tiếp nhận dữ liệu đã hoàn thành với1mẫu được quarantine rõ ràng.07B/07C và toànTask07 chưa DONE. Nhãn source mới nhất để tiếp tục dataset preparation làmerged-progress-v3; để tiếp tục UI run-08, dùng corrected subsetv2, không nạp merged359sample packet vào UI12frame.
