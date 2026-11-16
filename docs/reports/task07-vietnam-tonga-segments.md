# Task07 — pilot Vietnam–Tonga, 2026-11-04

Cập nhật mới nhất: người dùng đã xác nhận hai xung đột control, canonical GT v2 đã qua validation và full evaluator đã chạy. **Ball recall43.06%, strict control0%, pass recall0%, precision N/A; `failed_criteria`, Task07 IN_PROGRESS.** Đọc [full evaluation và phân tích lỗi](task07-development-evaluation-v2-20261104.md); [intake cũ](task07-reviewed-development-20261104.md) giữ để truy vết. Phần dưới là snapshot trước khi nhận nhãn, không còn hiểu là chưa có GT development được review.

**Trạng thái: IN_PROGRESS.** Đã hoàn tất code, chạy hai đoạn thật và bàn giao bộ review. 233 tests PASS, audit tính toàn vẹn PASS. Chưa có GT được review, chưa đo accuracy; pipeline chưa tạo completed pass và định danh người kiểm soát còn rất thấp. Chưa đủ điều kiện nghiệm thu Task07 hoặc dùng kết quả để ghi PRA chính thức.

[Handoff và lệnh tái chạy](../handoffs/task07-vietnam-tonga.md) · [Review nhãn](../guides/task07-vietnam-tonga-review.md) · [Protocol đã duyệt](../specs/task07-vietnam-tonga-evaluation.md).

## Đầu vào và phạm vi

Người dùng xác nhận roster đề xuất, cho phép xử lý từng đoạn30–60s và duyệt ngưỡng pilot; nhãn thực tế sẽ review sau. Không cần xin lại quyền OCR local hoặc xác nhận roster/protocol.

- Nguồn `codebase/assets_test/vietnam-tonga.mp4`: 1920×1080,30fps, khoảng23phút; SHA-256 `1443c1d263c8037a5684f3dbc0ef9216beb5097d9a47c4c1c9b94d1363e26865`.
- Roster thật đã duyệt: `codebase/configs/rosters/vietnam_tonga.json`; canonical CSV và approval record ở `codebase/data/matches/vietnam_tonga/`. Không dùng roster giả lập cho pilot này. CSV partial ban đầu được giữ nguyên.
- Development: parent05:00–05:30; đoạn thứ hai: parent02:45–03:15. Mỗi đoạn30s/900frames. Mapping về nguồn là `parent_time_s=segment_source_time_s+300` hoặc `+165`.
- Các đoạn được transcode cục bộ, có child hashes và full-decode audit tại `media/segments.json`; không coi là pixel-identical với parent.
- Hai đoạn cùng trận, đã xem output để triage và sửa lọc màu/ROI. Tên thư mục `validation` được giữ để truy vết; **không còn untouched validation hoặc independent match test**. Exposure ghi tại `validation-exposure.json`. Không lựa chọn lại đoạn hoặc loại lỗi để tự tăng metrics.

ROOT dưới đây là `codebase/outputs/task07-vietnam-tonga-segments-20261104/`.

## Thay đổi thực hiện

1. Sửa lỗi confidence không truyền vào SDK: ngưỡng `.15` nay được áp dụng trước post-filter. Giữ đúng approved detector và ONNX CPU, không upload media.
2. Full-frame cho human/rim, kết hợp4tile có overlap cho ball; map bbox về ảnh gốc, deduplicate và loại overlay broadcast khai báo. Trên development, số frame có ít nhất một ball candidate tăng591→769/900. Đây là **candidate coverage, không phải recall hoặc số phát hiện đúng**.
3. OCR thật chạy local bằng weights đã có; crop upscale, khử duplicate cùng frame/số áo và ghi errors. Hạn chế CPU thread oversubscription. Team evidence TTL2s và jersey TTL6s độc lập, không kéo dài team evidence cũ hoặc gán mapping cuối video ngược thời gian.
4. Lọc pixel màu theo prototype áo, giữ unknown khi màu mơ hồ; image ROI chỉ dùng loại ngoài sân, không tự xác nhận player. Cuts reset tracking/identity; interval được chuẩn hóa microsecond để loại đúng frame đầu cảnh mới.
5. Replay raw OCR với kiểm tra cùng source/detections/tracker parameters và cùng observed bbox của track. Không gọi lại OCR hoặc lấy identity đã suy ra làm OCR evidence. Raw caches và lịch sử chạy được giữ nguyên.
6. Ball association thêm giới hạn kích thước và human context; dribble cần nhiều observed samples. Gap tối đa100ms chỉ giữ hypothesis, không xác nhận controller bằng predicted ball; completed pass vẫn cần observed flight và observed stable receiver.
7. Run IDs/input hashes gắn với implementation ball/control; video debug ghi rõ observed/predicted/missing, đội/số áo hoặc unknown. Thêm acceptance profile đã duyệt, từ chối draft/synthetic GT và không cho thiếu mẫu/N/A thành PASS.

ROI/cuts là cấu hình vận hành theo từng đoạn, không phải tự động camera calibration, không tạo metric heatmap. Thuật toán bbox/color còn có thể nhận nhầm trọng tài, poster hoặc đội; các frame contact sheet vẫn cho thấy false candidates và track fragmentation. Không coi việc có nhãn đội/số áo trên overlay là bằng chứng đúng.

## Kết quả chạy cuối

Canonical outputs: `development-tracking-masked/`, `validation-tracking-masked/`, `development-masked-delivery/`, `validation-masked-delivery/`. Các thư mục `*-delivery` trước revision masked là lịch sử, không ghi đè.

| Quan sát tự động, chưa phải accuracy | Development | Đoạn thứ hai |
|---|---:|---:|
| Frames xử lý / debug export | 900 / 900 | 900 / 900 |
| Ball observed / predicted / missing | 514 / 247 / 139 | 530 / 169 / 201 |
| Confirmed control frames | 75 | 159 |
| Confirmed control có player_id | 0 | 4 |
| Completed passes xuất ra | 0 | 0 |
| Player observations có player_id (gồm nhiều track/frame) | 859 | 1150 |
| Frames loại do closeup/cut | 44 | 147 |
| PTS error decode so với source, tối đa | ≈0.333µs | ≈0.333µs |

Raw OCR trước replay có129/167 jersey evidence records, lần lượt1817/1578 crop attempts,2/0 crop rejects,0 runtime errors. Không phải129/167 lượt nhận diện đúng. Replay không gọi OCR mới, có thể bỏ records thuộc ngoài ROI/cuts; counts chi tiết trong `*-tracking-masked/run.json`.

Core replay từ cache rất nhanh nhưng loại detector/OCR khỏi thời gian; **không phải end-to-end realtime**. Full-frame detection development ban đầu khoảng560.5s cho30s footage trên CPU trong phiên có tác vụ đồng thời; tiled thêm model calls. Benchmark3frame chỉ dùng chọn4ONNXthreads trên development, không chứng minh realtime hoặc accuracy.

Video cuối: [development](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/development-masked-delivery/debug.mp4), [đoạn thứ hai](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/validation-masked-delivery/debug.mp4). Contact sheets: [development](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/development-delivery-contact.jpg), [đoạn thứ hai](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/validation-delivery-contact.jpg).

## Kiểm thử và audit

- [Tests cuối](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/tests-signoff.json):233 tests,0failures/errors/skipped,19.86s. [Log](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/tests-signoff.log). Chạy ngoài sandbox để fixture video/thư mục tạm hoạt động trên Windows; không thay môi trường production.
- Regression gồm threshold SDK, tile coordinates, OCR duplicate/error, independent TTL, masked jersey pixels, cross-source/mock OCR cache rejection, cut microseconds, observed dribble, bounded missing hypotheses và minimum-sample acceptance. Các fixture tổng hợp chỉ kiểm tra logic.
- [Independent artifact audit](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/delivery-audit.json): đầy đủ1800frames, observed ball truy về đúng detector ref/bbox; confirmed control có observed ball và observed player record cùng thời điểm; không controller trong exclusions; core/input hashes đúng; MP4 decode/PTS trong2µs; draft GT bị evaluator từ chối.
- Nguồn video/CSV partial và19file dataset/annotations/splits lịch sử không đổi. Không tự đóng G04/G05/G06.
- JavaScript hai trang review cuối đã qua `node --check`, assets tương đối có sẵn. Chưa kiểm thử tương tác end-to-end bằng trình duyệt; không gọi đây là browser acceptance.

Audit này kiểm tra provenance/causality, không chứng minh rằng detection là quả bóng thật hoặc controller là cầu thủ thật.

## Nghiệm thu còn thiếu và bước tiếp theo

Ngưỡng đã duyệt: ball recall≥90% tại IoU≥0.30; strict team/player control accuracy theo thời lượng≥90%; strict completed-pass precision≥95% và recall≥90%; PTS≤2µs, zero prediction-only control và zero completed pass qua cut. Cần ít nhất60visible GT ball samples,5GT completed passes và control coverage hợp lệ. Unknown/missed vẫn tính lỗi.

Hai gói review source-only có108/94ball samples; gợi ý HSV đều draft/uncertain, control/pass lists cần được annotator điền đầy đủ. Người dùng review theo [hướng dẫn](../guides/task07-vietnam-tonga-review.md), lưu packets rồi agent chạy evaluator và phân tích lỗi. Không tự đổi nhãn thành approved hoặc ghi accuracy từ candidate coverage.

**Review GT không tự làm Task07 DONE.** Với0completed pass hiện tại, nếu GT có completed passes thì pass recall sẽ không đạt; controller player_id cũng là rủi ro rõ ràng. Sau đo cần sửa ball continuity/track identity và release–receive errors trên development, freeze revision rồi kiểm chứng thêm đoạn30–60s chưa dùng để chỉnh. Nếu đủ bằng chứng model/backend hiện tại không đáp ứng, trình failure và phương án cụ thể trước thay model/dependencies. Không hạ ngưỡng hoặc dùng manual corrections làm automatic stats.

Task08–10 có thể phát triển contract/fixtures độc lập; chưa được coi task07 real attribution đã bàn giao PASS. Khả năng bất kỳ video, gần100% và realtime chưa được chứng minh.
