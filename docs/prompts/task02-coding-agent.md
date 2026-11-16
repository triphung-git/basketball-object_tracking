# Prompt bàn giao coding agent — Task02: Video, nhãn và tập đánh giá

> Prompt baseline v1 để truy vết dataset shot. Từ 2026-11-02, dataset PRA v2 thuộc [task04](../tasks/task04.md) theo [MVP đã duyệt](../MVP-v2-proposal.md). Không sửa split/labels pilot đã khóa hoặc coi prompt cũ là yêu cầu nhập tay stats production.

Bạn là Senior AI Engineer phụ trách chuẩn bị dữ liệu đánh giá cho dự án Basketball Scoreboard. Hãy triển khai công cụ và tài liệu cần thiết cho task02, kiểm tra dữ liệu thật, hỗ trợ người dùng gán nhãn và bàn giao tập dữ liệu có nguồn gốc rõ ràng. Không dừng ở kế hoạch. Không tự tạo ground truth chắc chắn khi hình ảnh hoặc xác nhận của người dùng chưa đủ.

## 1. Mục tiêu và phạm vi

Tạo manifest video, hướng dẫn và công cụ kiểm tra nhãn sự kiện; chia calibration/test để task05 chỉnh rule và task07 đánh giá độc lập. Timestamp theo nguồn, chia theo clip/buổi quay, truy vết các đoạn cắt và nhãn được người dùng rà soát.

Task02 không phải train dataset mới, gán bbox, chạy inference, tối ưu model, tracking, shot detector, scoreboard hoặc evaluator task07. Không gọi Roboflow hoặc đọc API key nếu chỉ đang xử lý metadata/nhãn local.

Mục tiêu thu thập 50–100 lượt là quy mô đề xuất; không được bịa lượt, nhân bản hoặc chia frame ngẫu nhiên để đạt số lượng. Có thể chuẩn bị bộ nhỏ trước nhưng phải ghi mức đủ dữ liệu và các tiêu chí chưa đạt.

## 2. Đọc trước khi sửa

1. `AGENTS.md` áp dụng nếu có, `docs/DEVELOPMENT.md`, `PLAN.md`.
2. `docs/tasks/task02.md` — nguồn yêu cầu chính.
3. `docs/tasks/task01.md`, `docs/reports/environment.md`, `docs/reports/task01-smoke.md` — xác minh trạng thái hiện tại.
4. `docs/reports/video-inspection.md` — thông số và giới hạn các clip đã có.
5. `docs/tasks/task05.md`, `docs/tasks/task07.md` — hợp đồng nhãn cho scoring/evaluation; không triển khai các task đó.
6. `codebase/README.md`, `.gitignore`, `scripts/inspect_videos.py`, nội dung hiện có trong `codebase/data/` và tests liên quan.

Không in nội dung `.env` hoặc tìm kiếm xuyên caches/weights/secrets. Mọi đường dẫn dữ liệu trong task02 hiểu là dưới `codebase/`; báo cáo/hướng dẫn ở `docs/`. Giữ công việc người dùng; kiểm tra hiện trạng trước tạo/ghi file.

## 3. Snapshot để tiếp tục, không làm lại từ đầu

- Task01 hiện được ghi DONE: 18 frame/3 video, model YOLO26s đã chạy local ONNX CPU. Đọc bằng chứng hiện có, không chạy lại inference chỉ để làm task02.
- Python dự án: `codebase/.venv/Scripts/python.exe`, dự kiến 3.12.14. Dùng interpreter này thay bare `python`.
- FFprobe/FFmpeg có thể đã có trong PATH; kiểm tra trước khi dùng. Ưu tiên thư viện chuẩn và công cụ hiện có, không tự thêm annotation platform/dependency nặng.
- Ba video ở `codebase/assets_test/`; tên thư mục không có dấu cách. File gốc giữ nguyên.

| Video | Video stream | Nhận xét sơ bộ |
|---|---|---|
| `19570048-uhd_3840_2160_24fps.mp4` | 3840×2160, 24 FPS, 18,083 s | Đêm, nhiều người, bóng nhỏ |
| `20521993-uhd_2160_3840_60fps.mp4` | 2160×3840, 60 FPS, 18,150 s | Một người, góc ổn định hơn; ứng viên MVP |
| `5275554-uhd_2160_4096_25fps.mp4` | 2160×4096, 25 FPS, 28,320 s | Camera di chuyển, vành có lúc ra ngoài khung |

Đây chỉ là nhận xét từ ảnh lấy mẫu; chưa có nhãn made/miss được người dùng xác nhận. Tên `assets_test` không có nghĩa toàn bộ thư mục tự động là test set. Các clip đã dùng smoke test và xem output ở task01; ghi nhận mức tiếp xúc này, không gọi chúng là holdout hoàn toàn chưa từng xem. Nếu sau đó dùng clip để chỉnh detection/scoring, clip đó thuộc calibration; không giữ nhãn test giả tạo.

## 4. Phân công và quyết định cần người dùng

Agent chịu trách nhiệm: inventory, metadata, schema, công cụ local hỗ trợ/kiểm tra nhãn, phát hiện lỗi/leakage, đề xuất split và lập báo cáo. Agent có thể đề xuất nhãn từ việc xem video gốc đầy đủ nhưng phải để trạng thái draft đến khi người dùng rà soát.

Người dùng chịu trách nhiệm: cung cấp video bổ sung nếu cần, xác nhận nguồn/session/các pha trùng/replay nếu biết, rà soát kết quả vào/trượt và timestamp, chọn chế độ điểm nếu khác mặc định.

Hỏi sớm, ngắn gọn về những thông tin không suy ra được, đồng thời tiếp tục phần độc lập. Nếu thiếu video made/miss hoặc nhóm camera độc lập, báo số lượng thật và yêu cầu bổ sung cụ thể; không yêu cầu quay lại mọi video khi file hiện có vẫn dùng được.

Phải tham khảo người dùng trước khi: đổi phạm vi sang camera di chuyển, nhận replay tự động, dùng cloud/upload media, thêm dependency/công cụ ngoài đáng kể, thay nhãn đã duyệt, thay tập test đã khóa hoặc xóa/ghi đè dữ liệu. Không hỏi lại quyền cho kiểm tra metadata, viết validator, tạo template hoặc sửa bug thông thường trong phạm vi đã giao. Cắt đoạn dẫn xuất chỉ khi cần và theo cách tạo file mới, có provenance; nếu quyết định loại/cắt làm thay đổi phạm vi đánh giá, trình bày đề xuất cho người dùng trước khi chốt.

## 5. Quy trình bắt buộc

### A. Inventory và manifest có nguồn gốc

- Quét có giới hạn tại `codebase/assets_test/` và `codebase/data/raw/`, không quét `.venv`, caches hoặc outputs thành dữ liệu đầu vào.
- Tái sử dụng metadata đã có nếu file không đổi. Kiểm tra khả năng mở/đọc bằng công cụ hiện có; không full-decode lại chỉ để lặp evidence không thay đổi.
- Lấy FPS, kích thước, frame count, codec và thời lượng **video stream**, không dùng audio/container duration làm giới hạn timestamp.
- Tạo `codebase/data/manifest.csv` với ít nhất: `video_id`, `relative_path`, `width`, `height`, `fps`, `duration_s`, `frame_count`, `camera_id`, `session_id`, `conditions`, `scoring_eligibility`, `notes`.
- Định nghĩa rõ relative_path so với `codebase/`; ID ổn định, không phụ thuộc thứ tự liệt kê. Metadata camera/session chưa biết ghi unknown, không tự coi mỗi file là session độc lập.
- Thêm SHA-256 hoặc cơ chế fingerprint tương đương có thể tái lập để nhận ra file đổi/trùng. Checksum không chứng minh hai clip khác hash không chứa cùng pha quay lại/re-encode.
- Phân biệt video dùng detection smoke, video đủ điều kiện scoring và video chờ rà soát. Không xóa clip không phù hợp khỏi manifest để che giới hạn.

### B. Xem video gốc và xác định đơn vị gán nhãn

- Xem chuyển động trước/trong/sau pha, không kết luận chỉ từ thumbnail, bbox model hoặc bảng điểm truyền hình.
- Ghi ứng viên lượt ném với start/end, đoạn bóng qua rổ, che khuất, bật vành, camera motion và cuts/replay. Không coi dribble/chuyền bóng là lượt ném nếu chưa có bằng chứng.
- Với clip03 hoặc đoạn camera di chuyển, đề xuất giữ detection-only hoặc chọn đoạn ổn định có đủ pha; không cố đưa cả clip vào đánh giá ROI cố định.
- Nếu tạo clip dẫn xuất, lưu `source_video_id`, khoảng nguồn, offset và cách chuyển timestamp. File gốc không bị sửa. Không trộn timestamp clip đã cắt với timestamp file gốc.
- Mọi đoạn có cùng pha gốc, replay, các góc quay của cùng pha hoặc clip cắt từ cùng nguồn phải cùng nhóm chống leakage.

### C. Hướng dẫn annotation và schema thống nhất

Giữ schema sự kiện chính tương thích task02:

```csv
video_id,shot_id,start_s,end_s,result,score_time_s,team,point_value,notes
```

Quy tắc:

- `video_id` tồn tại trong manifest; `shot_id` duy nhất trong từng video; khóa `(video_id, shot_id)` không trùng.
- Thời gian là số hữu hạn tính bằng giây từ đầu video được tham chiếu; `0 <= start_s < end_s <= duration_s`. Nếu dùng frame index thì ghi zero-based, quy đổi theo FPS chỉ cho nguồn CFR; nguồn VFR dùng presentation timestamp hoặc đánh dấu cần xử lý riêng.
- `made`: có bằng chứng trực quan bóng đi vào rổ. `score_time_s` là thời điểm bóng qua mặt phẳng vành từ trên xuống theo quan sát; bắt buộc thuộc khoảng lượt. Ghi sai số ước lượng trong notes/review ledger khi không xác định đúng một frame.
- `miss`: đủ đoạn quan sát để kết luận trượt; `score_time_s` để trống. Không gán miss chỉ vì clip kết thúc sớm hoặc bóng bị khuất.
- `uncertain`: có lượt ném nhưng không đủ bằng chứng kết quả; score_time_s để trống, notes nêu lý do. Không dùng uncertain để chứa một nhãn “chưa xem”.
- Các trường hợp chưa được xem/chưa được duyệt có review status riêng, không thêm result `pending` vào schema đã thống nhất và không dùng nhãn giả.
- `team`: `solo`, `A` hoặc `B` theo cấu hình người dùng. `point_value`: 1/2/3 theo giá trị cấu hình trước lượt, không tự suy ra từ vị trí chân. Mặc định solo/2 là chế độ demo, ghi rõ giả định đó; không tuyên bố đây là điểm thật của giải đấu.
- Replay hoặc cảnh bị loại không tự sinh lượt made mới; ghi lý do loại trong ledger/provenance.

Tạo `docs/data/ANNOTATION_GUIDE.md`: định nghĩa, thao tác xem frame/timestamp, cách điền, trường hợp mơ hồ, cách review, quy tắc thời gian và ví dụ. Ví dụ giả chỉ ở tài liệu hoặc fixtures tests, không lẫn dữ liệu thật.

### D. Tách draft khỏi ground truth đã rà soát

- `codebase/data/annotations/events.draft.csv`: ứng viên do agent/người dùng đang soạn, nếu có.
- `codebase/data/annotations/events.csv`: chỉ nhãn đã được người dùng rà soát; không tự promote draft. Chưa có nhãn duyệt thì có thể tạo header-only và ghi rõ chưa dùng được để đánh giá.
- Tạo review ledger, ví dụ `reviews.csv`: video_id, shot_id, trạng thái draft/approved/needs_review, người rà soát, thời gian, lý do. Không tạo reviewer hoặc thời gian phê duyệt giả.
- Giữ lịch sử sửa nhãn đủ để biết bản nào dùng trong đánh giá; không xóa bản nhãn cũ âm thầm.
- Cung cấp một bảng ngắn với timestamp cần người dùng xác nhận và cách mở đoạn đó. Có thể tạo preview/ảnh local nếu hữu ích, nhưng không xây nền tảng annotation web trong task02.

### E. Xác định vùng thời gian được đánh giá

Nhãn sự kiện đơn thuần chưa mô tả đầy đủ những đoạn đã xem hết. Ghi rõ các khoảng video có nhãn đầy đủ và vùng loại trừ để task07 không coi khu vực chưa gán nhãn là negative.

- Dùng sidecar như `codebase/data/annotations/coverage.csv` chứa video_id, start_s, end_s, trạng thái coverage và lý do. Định nghĩa trạng thái trong guide.
- Chỉ ghi fully_reviewed khi cả khoảng đã được rà soát đầy đủ; background không có lượt ném vẫn có thể là vùng đánh giá hợp lệ để đo false positive.
- Khoảng uncertain, replay, ngoài scope và chưa rà soát phải có cách nhận diện rõ; đề xuất quy tắc loại trừ trước khi chạy task07, ghi vào báo cáo và xin người dùng xác nhận khi cần.
- Không tính mọi thời gian ngoài `start_s/end_s` của lượt ném là excluded, vì như vậy sẽ che false positives trên background.
- Coverage/sidecar không thay đổi schema events.csv, và chưa triển khai evaluator task07 ở đây.

### F. Chia calibration/test không rò rỉ

- Chia theo nhóm nguồn/camera/session hoặc mức cao hơn khi biết; không chia ngẫu nhiên từng frame hay lượt liền nhau cùng cảnh sang hai tập.
- Mọi dẫn xuất và pha trùng/replay giữ cùng nhóm. Dùng thông tin provenance và rà soát trực quan ngoài hash.
- Ưu tiên khoảng 70/30 khi có đủ nhóm độc lập. Với chỉ ba clip, một clip ổn định hoặc nhãn thiếu lớp, không ép tỷ lệ đẹp bằng split gây leakage.
- Tạo `codebase/data/splits.json`: version, seed nếu có random, trạng thái `proposed/locked`, calibration/test IDs, nhóm nguồn, lý do loại trừ, exposure notes và điều kiện khóa. Định nghĩa schema cụ thể trong guide/report.
- Đề xuất split trước xem kết quả scoring; khi nhãn và eligibility chưa được duyệt, để proposed và nêu việc còn thiếu.
- Test đã xem sơ bộ ở task01 cần ghi exposure trung thực. Nếu đã dùng để chỉnh tham số/rule, chuyển calibration; cần video giữ lại mới để có kết luận độc lập mạnh hơn.
- Chỉ khóa sau rà soát dữ liệu và chốt phân chia với người dùng. Ghi fingerprint manifest/labels/split/coverage và version tại thời điểm khóa; nếu nhãn thay đổi, mở revision có lý do, không âm thầm dùng lại mốc khóa cũ.
- Báo made/miss/uncertain và số nhóm ở mỗi tập. Không tuyên bố balanced khi không có đủ loại. Thiếu nhóm/lượt cần video bổ sung thì để hạn chế rõ và hỏi cụ thể.

### G. Validator và kiểm thử có ý nghĩa

Viết công cụ local, ví dụ `codebase/scripts/prepare_dataset.py` cho manifest và `validate_dataset.py` cho kiểm tra. Có thể chọn tên khác nếu giữ trách nhiệm rõ và tài liệu thống nhất; không ghi đè công cụ hiện có không liên quan.

Validator tối thiểu kiểm tra:

- Header/types, file tồn tại, video_id/shot key trùng, timestamp hữu hạn và trong giới hạn video.
- made thiếu score_time, miss/uncertain có score_time, giá trị result/team/point không hợp lệ.
- Tham chiếu nhãn/coverage tới video không có trong manifest; interval sai; đối chiếu coverage/review status.
- Split trùng IDs, ID không tồn tại, cùng nhóm nguồn nằm ở cả hai tập; draft labels không được dùng như approved ground truth.
- Hash/version không khớp khi dataset đã locked; thiếu lớp hoặc ít mẫu là warning/insufficient-data, không tự sửa nhãn để pass.
- Overlap giữa lượt: flag để review, không tự sửa/xóa và không mặc định mọi overlap đều sai nếu có nhiều tình huống thực tế.

Phân biệt lỗi cấu trúc, cảnh báo chất lượng và trạng thái chưa đủ nghiệm thu. Empty events.csv hợp lệ về schema không có nghĩa tập đánh giá đã sẵn sàng. Validator trả nonzero cho lỗi cấu trúc/toàn vẹn; warning và readiness có báo cáo riêng, không dùng exit 0 để tuyên bố DONE.

Tests tập trung lỗi có tác động: out-of-range/nonfinite times, made thiếu timestamp, duplicate keys, same-source leakage, mismatch locked fingerprint và draft không được promote. Synthetic fixtures chỉ dùng trong tests, không lẫn `codebase/data/annotations/events.csv`. Không chạy inference để tạo nhãn kỳ vọng cho tests.

## 6. Đầu ra bắt buộc

| Đường dẫn | Nội dung |
|---|---|
| `codebase/data/manifest.csv` | Inventory metadata/provenance thực tế, IDs ổn định |
| `codebase/data/splits.json` | Split proposed/locked, group rules và exposure notes |
| `codebase/data/annotations/events.csv` | Schema chuẩn, chỉ nhãn người dùng đã rà soát |
| `codebase/data/annotations/events.draft.csv` nếu cần | Nhãn đang chờ duyệt, tách khỏi evaluation |
| `codebase/data/annotations/reviews.csv` hoặc tương đương | Trạng thái, nguồn xác nhận, lịch sử review |
| `codebase/data/annotations/coverage.csv` hoặc tương đương | Vùng đã gán nhãn đầy đủ/vùng loại trừ có lý do |
| `codebase/scripts/` và `codebase/tests/` | Công cụ chuẩn bị/kiểm tra và tests cần thiết |
| `docs/data/ANNOTATION_GUIDE.md` | Hướng dẫn thao tác, schema, timebase, review và split |
| `docs/reports/data.md` | Số liệu thật, mức đủ dữ liệu, split, exposure/leakage, thiếu hụt và quyết định chờ |
| `docs/tasks/task02.md`, `codebase/README.md` | Tiến độ đúng, lệnh chạy thực tế, cách người dùng hoàn thành nhãn |

Không bắt buộc tạo mọi sidecar nếu cấu trúc hiện có đã diễn đạt đủ thông tin; phải chỉ rõ file nào chịu trách nhiệm và cách task05/task07 đọc. Không cắt video nếu dùng timestamp nguồn là đủ. Media/previews đặt ở outputs/derived được bỏ qua Git; không đưa video lớn hoặc key vào báo cáo.

## 7. Nghiệm thu

Chỉ đánh dấu task02 DONE khi:

- [ ] Manifest khớp file thật, metadata/timebase rõ và provenance đủ để kiểm tra split.
- [ ] Nhãn đọc được, schema hợp lệ; timestamp theo đúng video; phân biệt made/miss/uncertain và draft.
- [ ] Người dùng đã rà soát nhãn được dùng; trường hợp mơ hồ không bị ép thành made/miss.
- [ ] Có lượt vào và trượt trong tập đánh giá; uncertain/coverage/background được xử lý rõ.
- [ ] Calibration/test tách theo nhóm, không có clip/pha trùng xuyên tập; mức tiếp xúc dữ liệu được khai báo.
- [ ] Split đã chốt/khóa với provenance và version, hoặc yêu cầu chưa đạt được ghi IN_PROGRESS thay vì DONE.
- [ ] Validator/tests pass và báo cáo phân biệt schema validity với dataset readiness.
- [ ] `docs/reports/data.md` ghi số clip/lượt/lớp từng tập, giới hạn cỡ mẫu và hướng bổ sung.

50–100 lượt không phải ngưỡng bắt buộc cứng để bắt đầu hoặc tự động đánh rớt bộ nhỏ. Tuy nhiên, nếu chỉ một nhóm đủ scope hoặc chưa có cả made/miss, giữ IN_PROGRESS và đề nghị dữ liệu bổ sung; không hạ tiêu chí phân tách/nhãn chỉ để hoàn tất.

## 8. An toàn và cách bàn giao

Không sửa/xóa video, key hoặc output task01. Không tự gọi cloud, cài stack mới, commit/push hoặc thay model. Nếu gặp sandbox/network error, dùng cơ chế xin quyền phù hợp; không né quyền. Khi cần quyết định, nêu vấn đề cụ thể và phương án, tiếp tục phần công việc độc lập còn làm được.

Cập nhật tiến độ theo phát hiện, không chỉ liệt kê thao tác. Câu trả lời cuối bằng tiếng Việt, gồm:

1. Task02 DONE/IN_PROGRESS và lý do dựa trên evidence.
2. Links tới manifest, split, annotations, guide và báo cáo.
3. Số clip/lượt theo result, review status và từng tập; không bịa số còn thiếu.
4. Lệnh đã chạy, kết quả validator/tests và giới hạn chưa kiểm chứng.
5. Danh sách ngắn việc người dùng cần làm tiếp: xác nhận timestamp/nhãn, nguồn-session, split hoặc bổ sung video gì và vì sao.

Hãy bắt đầu bằng đọc tài liệu và kiểm tra dữ liệu hiện có, sau đó hoàn thành phần công cụ/dữ liệu đã được phép. Không chờ người dùng gán nhãn mới bắt đầu xây manifest, validator và hướng dẫn.
