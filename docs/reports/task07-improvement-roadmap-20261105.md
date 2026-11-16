# Task07 — nguyên nhân, phép thử và thứ tự cải thiện

**Cập nhật 2026-11-08:** đã tải và xác minh native checkpoint YOLO26s, xuất 49 ảnh/nhãn bổ sung đã duyệt, chuẩn bị local fine-tune job theo yêu cầu người dùng. Job đang chờ dataset gốc/CUDA tải xong; chưa train, chưa thay model inference và chưa có accuracy candidate. [Report và đường dẫn trạng thái job](task07a-local-finetune-20261108.md). Regression: 319 tests và 61 subtests PASS; OCR/ROI/full-pipeline acceptance vẫn phải đo sau training. Các đoạn dưới là lịch sử checkpoint 05/11.

Đã nhận40frame được review: [report feedback](task07a-reviewed-feedback-20261105.md),269tests PASS. Nhãn v2 theo xác nhận người dùng bỏ đầu gối nhầm ball. Detector có14/33visible balls thiếu candidate; spatial/context giảm false selections27→16so với top1 nhưng chưa tăng recall. Actor cue đã thử900frame theo yêu cầu mới, không vượt50%, tắt mặc định; đây là thử nghiệm chẩn đoán, chưa nghiệm thu07B. Tiếp tục dataset-first, chưa train/promote.

Dataset-first đã được người dùng duyệt và thực hiện: [QA ảnh thật và359frame pilot](task07a-dataset-first-20261105.md),257tests PASS; shared-source train/test current project đã có pixel/registration evidence. Nhãn pilot vẫn draft chờ review, chưa train, chưa thay weights; gate07A/07B/07Cgiữ trạng thái chưa đạt như report.

Đã thực thi checkpoint07A: [report mới nhất](task07a-improvement-checkpoint.md),251tests PASS; tái lập baseline113/113frame. Square960 và letterbox640 đều không vượt candidate baseline, giữ v4. Đã đọc Roboflow metadata/geometry samples, checkpoint raw có thể cấp URL nhưng chưa tải/train; [phương án dataset-first](task07a-data-finetune-proposal.md) là bước duyệt tiếp theo. Các kết luận phía dưới mô tả trạng thái trước checkpoint;07B/07Cchưa được mở để nghiệm thu.

Ngày2026-11-05. **Task07 IN_PROGRESS.** Mục tiêu là chọn phương án có bằng chứng tốt nhất trong phạm vi pilot, không cam kết một cấu hình tối ưu cho mọi video. Kết quả continuous development hiện hành vẫn là ball observed recall36/72=50%, strict control0%, pass recall0%, precision N/A. Việc có nguyên nhân được mô tả hoặc tests PASS không thay thế nghiệm thu accuracy.

## Kiểm tra đã thực hiện

- Đọc code detector, tiled inference, player/ball tracker, OCR consensus và reports hiện hành.
- Audit hai nhóm artifacts ngày05/11, kiểm tra result hashes, video/GT fingerprints và independently recompute21tổ hợp profile/confidence từ raw candidate boxes trên72GT visible samples. Các số khớp artifacts.
- Rà126OCR records trong player replay, đối chiếu exact-number với approved roster; đếm track IDs để chọn phần cần kiểm tra.
- [Diagnostic audit JSON](../../codebase/outputs/task07-improvement-audit-20261105/diagnostic-audit.json) lưu hashes, số liệu và giới hạn.
- Không chạy thêm inference, training, GPU hoặc cloud upload; không sửa production code, GT hay dataset đã khóa trong lần lập roadmap.

File `docs/reports/task07a-resolution-root-cause-20261105.md` được IDE tham chiếu nhưng chưa tìm thấy trên đĩa lúc kiểm tra. Roadmap này dùng artifacts có thật và lưu riêng, không thay thế nội dung chưa lưu của file đó. Các scripts/tests resolution gốc cũng chưa có trên đĩa; có executed analysis-script snapshot trong output, nhưng thiếu snapshot đúng phiên bản detector wrapper đã chạy.

## Bằng chứng và điều chưa thể kết luận

| Thành phần | Đã xác nhận | Chưa xác nhận | Phép thử quyết định tiếp theo |
|---|---|---|---|
| Khả năng tái lập | Detector hash trong resolution artifacts khác current wrapper; current `detect` chưa nhận `image_size` như script snapshot | Wrapper lịch sử có biến đổi nào khác ngoài input-size override | Khôi phục revision/source đầy đủ hoặc tái dựng thay đổi tối thiểu có tests; ghi actual tensor shape và preprocessing |
| Độ phân giải | Metadata ghi training input640×640, stretch; phép chiếu full-frame cho29/72GT min-side≤8px và66/72≤12px | Resize là nguyên nhân chính của31detector misses; phân bố kích thước trong dataset train | Đo pixel size ở tensor thật, tách tác động resolution khỏi aspect ratio/crop; dùng cùng GT và coordinate mapping |
| Ball detector | Baseline thiếu candidate đúng31/72mẫu;5mẫu khác có candidate nhưng tracker không chọn. Có102unmatched candidates trên các frame GT | Model chưa học đủ dữ liệu, nhãn sai hay domain shift là nguyên nhân gốc nào chi phối | Audit dataset gốc/checkpoint, đối chiếu ảnh lỗi theo kích thước, background, occlusion và môi trường |
| Background | Nhiều candidate nằm trên poster/khán đài; spatial filter đã giảm các quan sát ngoài search ROI | Precision toàn video; mọi candidate bên trong ROI đều là bóng thật | Nhãn positive/negative từ nguồn, phân tích false positives theo vùng; kiểm tra ROI không loại bóng trên không |
| Player tracking | Code đã dùng Hungarian; replay có62track IDs,46IDs từng mang role player | Số ID switches thật, mức trùng người, bao nhiêu tracks là referee/poster | Review các đoạn crossing/occlusion, tạo trajectory/track labels đủ để đo continuity và role |
| OCR/identity |126readings,45không exact-match số áo nào trong roster; strict control vẫn0% |45readings đều là OCR sai hay bao gồm crop nhầm người/logo; OCR accuracy và team accuracy độc lập | Review crop gốc cùng số đúng, team/role và độ nhìn rõ; tách detection crop/OCR/consensus/association failures |
| Control/pass | Chưa có completed pass; strict controller attribution chưa đạt | Sai tầng nào tại từng release/receive khi dùng detector/identity mới | Dựng event trace với ball, people, identity, state/reason tại cùng PTS; phân loại error, không chỉ xem tổng score |
| GT/validation | Development đã review; có cảnh báo #18 control start10.999890s trước pass receive11.566551s | Timestamp đối soát cuối; kết quả trên đoạn chưa tune và trận mới | Review cảnh báo, version GT nếu sửa; freeze trước validation và ghi exposure |

Các proxy không được coi là nguyên nhân đã xác nhận: trong31baseline detector misses có11bóng min-side≤20px,19gần human bbox,7có local-flow proxy cao và4có sharpness proxy thấp. Các nhóm overlap; gần bbox không tự chứng minh occlusion, flow cao không tự chứng minh motion blur. Dataset train gốc chưa có cục bộ nên chưa đánh giá được nhãn, leakage, class balance hoặc domain coverage.

Đã tính lại taxonomy từ raw cache và ball output v4:36mẫu đúng;31mẫu không có candidate gồm6missing,16predicted và9observed sai;5mẫu có candidate đúng nhưng tracker lỗi gồm4observed sai và1predicted. Do đó tổng observed không khớp là13, còn con số9trong phân tích detector misses chỉ là một subset. Khi so precision/false association phải dùng cùng định nghĩa, tránh cộng trùng hoặc bỏ sót4mẫu thuộc association.

## Diễn giải đúng các thử nghiệm resolution mới

Các số dưới là candidate hits trên72frame lấy mẫu, **không phải observed tracking recall của900frames**:

| Profile | Input WH | Hits tại conf0.05 /0.10 /0.15 |
|---|---|---:|
| Full frame |640×640|28 /24 /23|
| Full frame |960×544|18 /17 /16|
| Full frame |1280×736|27 /23 /22|
| Full-frame2×2 tiles |960×544|33 /26 /23|
| Court crop2×2 |960×384|26 /21 /21|
| Court crop3×3 |960×384|32 /32 /31|
| Court polygon3×3 |960×384|24 /22 /21|

Baseline tiled cache ởconf0.15 có41hits, cao hơn tất cả các profile mới này. Không promote các profile mới. Chúng đồng thời đổi resolution/aspect ratio/crop nên chưa cô lập đầy đủ tác động của resolution; nhất là640×640 so với960×544 không phải chỉ tăng kích thước. Polygon ROI metadata còn ghi resize_mode=None, không dùng làm bằng chứng cho một preprocessing đã được tái lập đầy đủ.

Hai kết luận cần phân biệt:

1. Đã có bằng chứng rằng **các cấu hình đã thử chưa giải quyết được detector misses**.
2. Chưa có bằng chứng rằng **mọi phương án tăng resolution đều vô ích**, hoặc **fine-tune chắc chắn là phương án tốt nhất**.

## 07A — Chốt detection bằng chẩn đoán có kiểm soát

### A1. Chốt phép đo và khả năng tái lập

Giữ raw video/PTS, GT, class mapping và evaluator như baseline; kiểm tra source/hash của model, code và preprocessing. Tái dựng input-size override đúng SDK nếu cần, không chỉ upscale ảnh rồi để SDK resize lại. Ghi actual input tensor WH, scale/padding và bbox mapping về nguồn. Test bằng ảnh kích thước khác nhau để phát hiện lệch coordinate.

**Đầu ra:** manifest tái lập, tests mapping/threshold, log actual input shapes, baseline chạy lại tương đương hoặc giải thích chênh lệch. Chưa đủ các phần này thì không dùng thử nghiệm mới để kết luận thay model.

### A2. Thử nghiệm ngắn, mỗi lần một biến

Giữ cùng preprocessing/aspect-ratio policy khi thử resolution; giữ nguyên resolution khi thử crop/tile. So sánh ở cùng confidence, sau đó sweep confidence riêng. Chọn một số ít cấu hình có giả thuyết cụ thể, giữ mọi kết quả kể cả regression. Search ROI lấy từ camera/source context, có aerial margin, không lấy vị trí bóng GT để crop lúc inference.

Khi đo tác động riêng của ball detection, giữ human/rim/OCR/cuts nhất quán hoặc ghi rõ thay đổi upstream nào chưa giữ được. Trial không OCR không được dùng để suy ra OCR/strict identity tốt hơn hay xấu hơn baseline có OCR; hạ confidence toàn detector còn có thể đổi human detections và association context.

**Đo:** candidate recall, unmatched candidates trên mẫu đã review, observed ball recall sau association, coverage missing/predicted và latency tổng. Đo candidate precision toàn video chỉ khi có nhãn đủ cho phạm vi đó. Không biến observed/predicted coverage thành accuracy.

**Quyết định:** chỉ promote cấu hình có lợi ích đo được và tradeoff latency rõ. Không lặp lại confidence0.10 hoặc upscale1.5 nếu không có giả thuyết mới, vì các lượt trước đã regression. Khi candidate recall vẫn không đủ ngưỡng, chuyển A3; không dùng tracking để che detector misses.

### A3. Audit dữ liệu trước quyết định fine-tune

Kiểm tra quyền truy cập dataset/version/checkpoint train được; ONNX inference package không tự xác nhận có checkpoint để tiếp tục train. Audit missing/inconsistent labels, kích thước bóng sau preprocessing, sample khó và negative backgrounds. Kiểm tra frames gần trùng/leakage giữa splits theo source/trận. Nếu giữ3classes ball/human/rim, tiêu chuẩn nhãn cần đầy đủ cho các class được train.

Nếu dữ liệu thiếu domain, chuẩn bị subset đa dạng: bóng nhỏ/trên tay/trên không/gần rổ, foreground/background dễ nhầm và điều kiện quay khác nhau. Giữ nhãn bóng nhìn thấy/che khuất nhất quán; không bịa bbox quả bóng hoàn toàn không quan sát được. Không train/test bằng các frame sát nhau để có điểm cao giả.

**Quyết định:** fine-tune khi audit chỉ ra khoảng trống có thể khắc phục bằng dữ liệu và có training checkpoint/backend phù hợp. Nếu sai preprocessing/labels, sửa phần đó trước. Nếu fine-tune không cải thiện, mới so phương án detector chuyên biệt hoặc kiến trúc khác. Mọi phương án cần so cùng test/latency, không chỉ train loss/mAP của nền tảng.

**Checkpoint07A:** báo nguyên nhân đã xác nhận, giả thuyết còn lại, bảng accuracy/latency, cấu hình tốt nhất và giới hạn. Người dùng duyệt candidate hoặc phương án train/model trước07B. Giữ ngưỡng observed ball recall≥90%; candidate recall chỉ là chẩn đoán.

## 07B — Tách lỗi identity khỏi lỗi temporal control/pass

### B1. Sửa crop/track trước khi đổi OCR

Lưu crop số áo thật theo frame/track, kích thước, sharpness và visibility; chọn các track quanh pha giữ/chuyền để review. Tách4trường hợp: crop sai người/vùng; crop đúng nhưng chữ không đọc được; chữ rõ nhưng OCR sai; OCR đúng nhưng consensus/track association sai.

62track IDs/30s là dấu hiệu cần review, không tự gọi là62người hoặc một con số ID switches. Đánh giá track continuity, human duplicates, team/role và crossing bằng source evidence. Roster cùng số ở hai đội cần team evidence độc lập. Reading09không nên tự strip zero toàn cục; chỉ chuẩn hóa theo roster khi không có xung đột với số0/00/09khác.

**Phương án:** cải thiện torso/jersey crop, chọn frame có chữ rõ, consensus causal nhiều frame và xử lý track conflict; chỉ cân nhắc OCR mới nếu crop đọc được nhưng OCR hiện tại vẫn sai có hệ thống. Giữ unknown khi không nhìn đủ; không gán lại mapping cuối clip về quá khứ.

**Đo riêng:** exact jersey accuracy trên crop đọc được đã review, tỷ lệ crop đủ điều kiện, team accuracy và player identity theo thời lượng/coverage. Ngưỡng nghiệm thu strict controller≥90% không bị thay bằng accuracy chỉ trên các crop đẹp.45/126readings ngoài exact roster là diagnostic count, không được gọi là35.7%OCR error rate.

### B2. Thử motion model khi detections đã được kiểm soát

Ball tracker hiện dùng vận tốc làm mượt; player tracker đã có Hungarian. So Kalman với baseline bằng cùng detections, giữ dt theo PTS. Dùng uncertainty gating, size/context và no-match option; reset qua cuts/gaps và hạn chế extrapolation. Nảy sàn/chạm vành/camera pan phải được test, không ép cùng quỹ đạo vận tốc hằng.

**Đo:** observed matching, false association, fragmentation/reacquisition, prediction-only duration và latency. Đường vẽ mượt hơn không tự là tốt hơn. Với một ball track, không mặc định thêm Hungarian sẽ cải thiện; chỉ giữ thuật toán khi so sánh có lợi.

### B3. Truy vết từng sự kiện control/pass

Tạo timeline quanh từng GT release/receive với: candidate/selected ball, observed person, team/player evidence age, controller state/reason, flight/receive confirmation và cut flags. Với mỗi FN/FP phân về detector, association, identity hay state transition; không cộng trùng các nhóm lỗi.

Chỉ sửa tầng thực sự gây lỗi. Control cần đủ evidence nhiều frame, pass cần observed flight/stable receiver; không coi mọi gap/đổi người gần bóng là pass. GT chỉ nằm trong evaluator và bảng chẩn đoán, không truyền vào engine. Đối soát cảnh báo timing củaTonga#18 trong GT, lưu revision nếu người dùng sửa.

**Checkpoint07B:** ball recall≥90%, strict control≥90%, strict pass precision≥95%/recall≥90%, các integrity guards PASS trên development. Không có pass predictions thì precision N/A, không100%. Nếu fail, báo root cause theo event, không đóng task bằng manual corrections. Người dùng duyệt revision freeze trước07C.

## 07C — Kiểm chứng độc lập và bàn giao hiệu quả

Freeze model/code/config, chuẩn bị GT trên đoạn30–60s chưa dùng để tune. Dùng nguồn hiện có cho same-match pilot; muốn kết luận tổng quát cần trận/nguồn khác. Hai đoạn đã triage không trở lại untouched test. Không chọn bỏ các đoạn khó sau khi thấy metrics.

Tối thiểu60visible GT ball samples,5GT completed passes và eligible control coverage; nếu thiếu thì bổ sung đoạn, không nới ngưỡng. Source-bind profile theo revision/hash của đoạn mới, giữ nguyên các ngưỡng đã duyệt và provenance. Người dùng review nhãn nguồn, agent chạy raw automatic pipeline trước mọi manual correction.

Đo full ball/control/pass metrics và đủ tình huống trong checklist Task07: dribble, handoff/bounce pass, loose/contested, deflection, occlusion/reacquire, shot candidates và cut/gap. Samples/mẫu số bị loại/uncertain phải công bố. Kiểm tra PTS≤2µs,0prediction-only confirmed control,0completed pass qua cut, replay và source binding.

Đo latency **end-to-end**, gồm decode/detection/OCR/tracking/export trong phạm vi được công bố; không lấy core replay FPS làm realtime. Chọn cấu hình theo accuracy + error severity + latency + mức can thiệp thủ công, không chọn score cao nhất trên một clip. Không hạ accuracy thresholds để đổi lấy tốc độ.

**Checkpoint07C:** báo PASS/FAIL, limitations, source exposure, config/model hashes, lệnh tái chạy và handoff. Chỉ đề xuất Task07 DONE khi mọi checklist/criteria có bằng chứng trong phạm vi đã chốt. Task08 còn cần court/arc geometry, rule profile và shooter/release/outcome/value GT; không tự đóng Task04–06 hoặc tự coi pilot tương đương mọi video/gần100%.

## Vai trò, phê duyệt và ưu tiên thực thi

Agent có thể làm ngay A1, chẩn đoán crop/track B1, chuẩn bị error traces và audit dữ liệu sẵn có mà không thay model. Cần người dùng review nhãn chưa có và chốt cảnh báo timestamp; không hỏi lại roster, quyềnOCR local, các ngưỡng hoặc hai xác nhận control đã được duyệt.

Train/thay model/weights/backend, dependency lớn, GPU, cloud upload/cost hoặc thay dữ liệu đã khóa cần trình phương án và được duyệt trước. Khi tới quyết định này, agent bàn giao trước dataset manifest/label QA/split, checkpoint khả dụng, cấu hình so sánh, tài nguyên/chi phí nếu xác minh được và tiêu chí rollback; không xin phép một yêu cầu train mơ hồ. Hiện chưa có phê duyệt train và chưa thực hiện train trong roadmap này.

Ưu tiên thực tế: **A1 tái lập/preprocessing → A2 thử có kiểm soát → A3 dữ liệu/model nếu có bằng chứng → B1identity và B2tracking → B3control/pass → Cvalidation.** Không cần chờ fine-tune để chuẩn bị crop review; nhưng không dùng việc chuẩn bị các phần độc lập để báo chuỗi end-to-end đã nghiệm thu.
