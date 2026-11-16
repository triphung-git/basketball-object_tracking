# Task07A — đối soát 40 frame đã review và thử nghiệm chọn bóng thi đấu

Ngày 2026-11-05. **Task07 IN_PROGRESS.** Đã dùng nhãn người dùng cung cấp để phân tích lỗi và chạy thử nghiệm local; chưa train, đổi weights hoặc promote cấu hình mới. Full regression: **269 tests PASS**. Các số dưới là diagnostics trên development cùng trận, không phải nghiệm thu độc lập.

## Dữ liệu nhận và quyết định nhãn

- [Draft gốc](../../codebase/outputs/task07a-dataset-first-20261105/draft-task07a-pilot.json): 359 frame, **40 approved ở cấp ảnh, 319 unreviewed**. Packet/policy/reviewer ở cấp toàn bộ vẫn draft; không tự chuyển thành dataset được duyệt để train.
- Soát source group/hash, danh sách và metadata cố định, SHA ảnh, bbox/class/visibility của 40 ảnh. Không coi null/unreviewed là negative.
- Có 33 frame visible, 7 frame not_visible; 31 ảnh được người dùng đánh dấu play và 9 background. Chưa tự sửa scene labels.
- `pilot_0017`, parent PTS 377s: người dùng xác nhận chỉ giữ bóng cầu thủ bên trái; bbox `[598,543,631,571]` trên đầu gối người ngồi là nhầm. Lưu [quyết định](../../codebase/outputs/task07a-reviewed-feedback-20261105/label-correction-decision.json) và [draft v2](../../codebase/outputs/task07a-reviewed-feedback-20261105/draft-task07a-pilot-corrected-v2.json), **không ghi đè file gốc**. Sau sửa có 33 bbox ball trên 40 frame, không còn ảnh được duyệt chứa hai bbox ball.

SHA draft gốc: `ca7776d790ffd3f01243d5be731a4fd45b1827c7165f64f9555bb3289f7dcf2e`.
SHA draft v2: `7fdb4dce1d513f591a2f6740c264b3a40fbe2ebfc5e38abafe3329f206f6291e`.

## Ba vấn đề người dùng nêu và bằng chứng

**Nhiều bbox ball trong cùng ảnh:** raw detector có 102 candidate trên 40 ảnh; 32 ảnh có nhiều hơn một candidate. Có 19 candidate khớp nhãn v2 tại IoU≥0,30, 83 unmatched và 14 ball GT không có candidate khớp. NMS tiled hiện đã dùng IoU0,35; nhiều bbox sai nằm ở các vật khác nhau, không phải tất cả là bbox trùng cùng quả bóng. Chỉ tăng NMS hoặc lấy confidence cao nhất không giải quyết nhầm vật thể.

**Các false positives thực tế:** đã xem source frame, contact sheet và crop. Các ví dụ rõ gồm đầu gối người ngồi sau sân lặp lại qua nhiều ảnh, vai người tiền cảnh, biểu tượng play của FPT Play; còn có chi tiết quanh bảng rổ/poster/khán đài cần phân loại tiếp. [6 ví dụ có tọa độ và kết luận](../../codebase/outputs/task07a-reviewed-feedback-20261105/final-preview/visual-findings.json). Không quy mọi bbox sai thành bóng ngoài sân hoặc khẳng định đã phân loại đủ 83 lỗi. Crop là tài liệu QA, chưa tự thành training negatives.

**Ball không liên kết human/frame trước:** trang annotation hiển thị raw candidate trên các ảnh lấy mẫu **1 Hz**, không phải output tracking 30 FPS. Tracker hiện hành đã có vận tốc, dt từ PTS, gate và tối đa một output ball/frame. Khoảng 1s giữa hai ảnh vượt max_gap0,30s; không kéo dài gap để tạo cảm giác đã track liên tục. Đồng thời, gần human chưa đủ: model có thể detect người trên poster hoặc người ngồi ngoài sân, còn bóng đang ném/chuyền phải được phép rời người.

**Bóng ngoài đường sân:** cần tách footprint mặt sân cho chân cầu thủ khỏi vùng tìm kiếm bóng có khoảng trời quanh rổ. Không cắt bbox bóng bằng polygon mặt sàn: bóng đang bay hoặc trên tay người đứng sát biên có thể nằm ngoài footprint trong ảnh. Các polygon thử nghiệm lấy theo cảnh nguồn, không dùng ball GT để crop. Cấu hình chỉ có scope cửa sổ `vt_pilot_06m`; pan/zoom/cut cần kiểm tra lại, không dùng chung cho mọi video.

## So sánh trên cùng 40 ảnh và nhãn v2

Các predictions được tạo và lưu **trước khi đọc draft review**; SHA predictions giống giữa lần đánh giá nhãn cũ và v2. Không truyền bbox/đáp án đã duyệt vào bộ chọn candidate. Giữ cùng cached detector, confidence và source; không inference lại hoặc đổi model.

| Phương án | Khớp | Không khớp | Bỏ sót | Precision so với draft v2 | Recall so với draft v2 |
|---|---:|---:|---:|---:|---:|
| Toàn bộ raw candidates | 19 | 83 | 14 | 18,63% | 57,58% |
| Luôn lấy confidence cao nhất, tối đa 1 | 13 | 27 | 20 | 32,50% | 39,39% |
| Spatial + human context, tối đa 1 hoặc missing | 13 | 16 | 20 | 44,83% | 39,39% |

Context giảm **11/27=40,74%** lựa chọn sai so với top1, giữ cùng 13 lựa chọn đúng; có 29 observed và 11 missing trên 40 ảnh. Trên 7 ảnh người dùng đánh dấu không thấy bóng, top1 tạo 7 lựa chọn sai, context còn 4. Đây là cải thiện giảm false selection trong phạm vi này, **chưa cải thiện recall**, chưa đạt gate90% và chưa được promote.

Raw và single-ball khác số lượng output, không dùng bảng để kết luận detector weights đã tốt hơn. Trên 33 bóng visible: 14 chưa có candidate đúng; 6 có candidate đúng nhưng context selector không chọn đúng; 13 được chọn đúng. Cần xử lý cả detector lẫn selection. Không thể dùng motion model để biến 14 detector misses thành observed đúng.

Human context trong preview được lọc bằng footpoint ROI từ detections; vẫn chỉ là proxy, chưa phải role/player identity đã xác minh. Trường hợp đầu gối bị chọn nhầm cho thấy ROI/human proximity chưa đủ. Các ảnh thuộc khoảng360–405s cùng trận, chỉ một phần packet; chưa đo precision toàn video hoặc tính tổng quát qua trận khác.

Xem [preview 40 ảnh](../../codebase/outputs/task07a-reviewed-feedback-20261105/final-preview/review.html): xanh lá là nhãn đã review, đỏ là raw candidates, cyan là bóng thử nghiệm được chọn; đường xanh dương là vùng chân human proxy, hồng là vùng tìm kiếm bóng có aerial margin. Preview vẫn có lỗi. [Evaluation JSON](../../codebase/outputs/task07a-reviewed-feedback-20261105/final-preview/evaluation.json), [queue83 crop cần phân loại](../../codebase/outputs/task07a-reviewed-feedback-20261105/final-preview/unmatched-review-queue.json), [contact sheet](../../codebase/outputs/task07a-reviewed-feedback-20261105/final-preview/unmatched-contact.jpg).

## Liên kết với cùng player track: triển khai và thử nghiệm

`BallConfig.actor_continuity_weight` mặc định **0**, thêm cue tùy chọn dựa trên vị trí bóng tương đối với torso của cùng track tại quan sát trước. Chỉ dùng human `observed`, role `player`, đúng frame/time, track_id duy nhất. Khi tranh chấp/không có torso phù hợp, không tạo anchor. Cue chỉ cộng điểm cho candidate có thật sau motion/size/ROI gate; không sinh bbox bóng, không xác nhận possession/identity, không ép bóng quay về người khi bay. State reset theo cut/gap như trước.

Đã chạy cached replay toàn bộ900frame development cũ với weight0,35, cùng detections/player tracks/ROI/cấu hình khác; GT chỉ dùng evaluator sau chạy:

| Chỉ số | Baseline v4 | Actor cue thử nghiệm |
|---|---:|---:|
| Observed ball khớp GT | 36/72 | 36/72 |
| Observed recall | 50% | 50% |
| Strict control accuracy | 0% | 0% |
| Strict pass recall | 0% | 0% |
| Strict pass precision | N/A | N/A |

Chỉ đổi lựa chọn trên1frame; observed count475→476 không phải accuracy tăng. Với weight0, cả900frame tương đương baseline ở geometry/sample_type/confidence/reason/candidate counts. **Giữ tùy chọn tắt, không promote.** Replay không gọi detector/OCR, không phải realtime benchmark. Không export video trong trial này nên PTS export check chưa đo, evaluator ghi false; không báo integrity acceptance đầy đủ.

[Trial run](../../codebase/outputs/task07a-actor-continuity-20261105/run.json), [evaluation](../../codebase/outputs/task07a-actor-continuity-20261105-evaluation/evaluation.json), [baseline equivalence/changed frames](../../codebase/outputs/task07a-reviewed-feedback-20261105/actor-trial-comparison.json).

## Code, kiểm thử và bàn giao

- Partial-draft audit dùng để nhận tiến độ mà không yêu cầu người dùng review lại40ảnh hoặc tự duyệt319ảnh còn lại.
- `audit_task07a_pilot_feedback.py` tái tạo predictions/evaluation/overlay từ cache và source policy; `ball_actor_context.py` + optional config là thử nghiệm temporal; pipeline truyền observed actor records và ghi hash implementation mới.
- 9 tests về actor cue: distraction, mặc định tắt, missing không thành observed, actor stale/predicted/unknown/đổi ID/trùng ID, flight, ROI, cut/gap, contested, cấu hình sai. Thêm3tests cho partial draft/source integrity/multiple-ball flags. **269 tests PASS**, log tại [tests.log](../../codebase/outputs/task07a-reviewed-feedback-20261105/tests.log). Lần sandbox lỗi quyền Windows Temp, chạy lại ngoài sandbox thành công; không thay dependency để né lỗi.
- Giữ nguyên draft gốc, video nguồn, GT control/pass chuẩn, dữ liệu/split khóa và weights; không upload, train, sửa cloud hoặc phát sinh job trả phí.

Để tiếp tục review, nạp **draft v2** vào trang annotation hiện có; cả40ảnh được duyệt vẫn giữ tiến độ. Preview là trang đối chiếu, không sửa labels. Phần còn lại nên tập trung true ball nhỏ/trên tay/trên không và negatives dễ nhầm đầu gối/vai/logo; không tự biến mọi unmatched bbox thành negative khi chưa đối soát nguồn. Sau label QA và split/checkpoint/recipe readiness mới trình phép thử fine-tune cụ thể để người dùng duyệt training. Mục tiêu đầu ra vẫn tối đa một **bóng thi đấu** hoặc missing/frame; detection-class labels phải nhất quán nếu nguồn khác có thêm bóng thật ngoài trận.

Lệnh tái lập preview:

```powershell
codebase/.venv/Scripts/python.exe codebase/scripts/audit_task07a_pilot_feedback.py --pilot-dir codebase/outputs/task07a-dataset-first-20261105/pilot-candidate --reviewed codebase/outputs/task07a-reviewed-feedback-20261105/draft-task07a-pilot-corrected-v2.json --settings codebase/configs/task07a/pilot-06m-context-preview.json --output-dir codebase/outputs/task07a-feedback-new-run
```

Không dùng output folder đã tồn tại. Raw training suggestions và trang annotation ban đầu giữ nguyên để audit.
