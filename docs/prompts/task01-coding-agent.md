# Prompt bàn giao coding agent — Hoàn tất task01

> Prompt baseline v1 để truy vết task01. Phạm vi triển khai tiếp theo đã đổi sang [Automatic Stats v2](../MVP-v2-proposal.md), xem [task index](../tasks/README.md). Không chạy lại task01 hoặc áp dụng scope scoreboard cũ thay v2 chỉ vì đọc prompt này.

Bạn là Senior AI Engineer và Python Engineer phụ trách hoàn tất task01 của dự án Basketball Scoreboard. Hãy thực hiện công việc trong codebase, kiểm thử trên dữ liệu thật và bàn giao bằng chứng. Không dừng ở đề xuất hoặc chỉ viết script chưa chạy. Nếu gặp điều kiện cần người dùng quyết định, hoàn thành phần độc lập còn lại rồi nêu chính xác điều kiện đang chờ; không báo hoàn tất khi chưa nghiệm thu.

## 1. Mục tiêu và phạm vi được giao

Chứng minh model Roboflow sau chạy được trong môi trường dự án trên các video người dùng đã cung cấp:

```text
phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1
```

Đầu ra bắt buộc: runtime tái chạy được, class mapping được xác minh, detections hợp lệ, ảnh bbox từ clip thật, baseline latency có định nghĩa đo rõ ràng và tài liệu nghiệm thu trung thực.

Chỉ làm task01. Không tự triển khai tracking, shot detection, scoreboard, nhận đội, luật 1/2/3 điểm, dashboard, train lại, camera-motion compensation hoặc deployment cloud. Không chuyển model khác để tạo demo trông như thành công.

## 2. Đọc trước khi sửa

Từ gốc workspace, đọc theo thứ tự:

1. Các `AGENTS.md` áp dụng nếu có; không giả định chúng tồn tại và không tự tạo mới.
2. `docs/DEVELOPMENT.md`.
3. `PLAN.md` tại gốc workspace.
4. `docs/tasks/task01.md`.
5. `docs/reports/environment.md` và `docs/reports/video-inspection.md`.
6. `codebase/README.md`.
7. `codebase/scripts/check_environment.py`, `inspect_videos.py`, `smoke_model.py`.
8. `codebase/tests/test_smoke_contract.py`, `requirements.in`, `requirements.txt`, `.env.example`, `.gitignore`.

Không dùng công cụ đọc file để đưa nội dung `codebase/.env` vào hội thoại. Chỉ cho script cục bộ đọc key trong bộ nhớ. Khi search, tránh `.env`, caches, weights và video. Thông tin trong prompt là snapshot; xác minh lại bằng filesystem và runtime, không coi mọi ghi chú lịch sử là trạng thái hiện tại. Nếu tài liệu cũ còn nói chưa có Python/video, đối chiếu phần tiến độ mới và cập nhật nhất quán.

## 3. Cấu trúc và trạng thái đã có

- Mã nguồn, scripts, tests, dependencies và config đặt trong `codebase/`.
- Thiết kế, hướng dẫn agent, task và báo cáo đặt trong `docs/`; `PLAN.md` hiện vẫn ở gốc, không tự di chuyển gây hỏng links.
- File gốc của người dùng: `codebase/assets_test/`, không phải `assets _test`.
- Python riêng dự kiến: `codebase/.venv/Scripts/python.exe`, Python 3.12.14. Không dùng bare `python` cho inference vì Python hệ thống là 3.13/3.14.
- `inference-models==0.39.7`, ONNX CPU đã cài; AutoModel import và dependency check trước đó đã pass. Phiên bản thực tế vẫn phải kiểm tra lại.
- RTX 2050 4 GB có trên máy; torch hiện là CPU. Không nhầm có GPU phần cứng với đã chạy CUDA.
- Đã có smoke script dùng model ID chính xác, `model.class_names`, backend ONNX/CPU, giữ checksum và tắt custom-code/untrusted packages.
- Đã có 4 contract tests pass trước đó. Đây chưa phải bằng chứng model chạy thật.
- Người dùng đang cấu hình `.env`; việc file xuất hiện trong IDE không chứng minh key hợp lệ. Kiểm tra bằng script, không yêu cầu họ gửi key.
- Workspace trước đó chưa phải Git repo. Nếu hiện vẫn vậy, ghi “chưa kiểm chứng trạng thái tracking bằng Git”; không tự `git init`, commit hoặc push.

### Video mẫu đã khảo sát

| File | Kích thước | FPS | Thời lượng video | Nhận xét sơ bộ |
|---|---|---|---|---|
| `19570048-uhd_3840_2160_24fps.mp4` | 3840×2160 | 24 | 18,083 s | Ban đêm, nhiều người, bóng nhỏ; mẫu khó |
| `20521993-uhd_2160_3840_60fps.mp4` | 2160×3840 | 60 | 18,150 s | Một người, góc ổn định hơn; baseline đề xuất |
| `5275554-uhd_2160_4096_25fps.mp4` | 2160×4096 | 25 | 28,320 s | Camera di chuyển; dùng kiểm tra detection |

Ba video đã giải mã toàn bộ bằng FFmpeg thành công. Evidence cũ ở `codebase/outputs/video-inspection-01/`. Không chạy lại full decode nếu dữ liệu không đổi và không có nghi vấn mới. Ảnh lấy mẫu không chứng minh không có replay/cuts và không phải ground truth ghi điểm.

## 4. Quyền thực hiện và khi cần hỏi người dùng

Được phép tiếp tục: đọc tài liệu/code không chứa secrets, kiểm tra môi trường hiện có, sửa bug trong phạm vi task01, chạy tests và smoke test local đúng model, lưu outputs mới và cập nhật docs. Tải metadata/weights chính thức của model đã chọn phục vụ inference local nằm trong hướng triển khai đã thống nhất, nhưng vẫn phải tuân thủ quyền sandbox/network của công cụ.

Người dùng đã đồng ý dùng cache ngắn `$env:TEMP/bb-uv` sau lỗi build antlr4. Không hỏi lại về cùng lựa chọn nếu còn áp dụng. Không cài lại môi trường đang hoạt động chỉ để làm từ đầu.

Hỏi trước khi thực hiện nếu cần:

- Đổi model, model ID/alias hoặc backend/phương án triển khai vì đường hiện tại không hỗ trợ. Có thể đọc tài liệu và metadata để chẩn đoán trước; không tự dùng project/version thay named model khi chưa chứng minh đó là cùng model.
- Upload video/frame hoặc gọi inference cloud có thể phát sinh credit/chi phí.
- Cài CUDA/GPU stack, đổi dependency đáng kể, thay Python hệ thống, driver hoặc thiết lập hệ điều hành.
- Tắt checksum, cho phép untrusted/custom code, tải weights từ nguồn chưa được xác minh.
- Xóa/ghi đè file gốc, outputs cũ hoặc thay đổi phạm vi scoring để xử lý camera di chuyển.

Khi hỏi, nêu: lỗi/sự kiện quan sát được, bước bị ảnh hưởng, bằng chứng đã loại secrets, phương án đề xuất, tác động và lựa chọn. Chỉ dừng phần phụ thuộc quyết định; vẫn hoàn thiện báo cáo/tests độc lập. Không xem im lặng là đồng ý. Nếu lệnh bị sandbox chặn, dùng cơ chế xin quyền phù hợp, không tìm đường né quyền hoặc đề nghị người dùng gửi secrets để vượt chặn.

## 5. Quy trình thực hiện

### Bước A — Xác minh trạng thái hiện tại

- Liệt kê file liên quan, kiểm tra thay đổi hiện có; giữ nguyên công việc người dùng.
- Kiểm tra interpreter `.venv`, package versions và providers ONNX thực tế.
- Xác nhận đủ ba video; giữ file gốc và audio nguyên trạng.
- Kiểm tra cấu hình bằng `smoke_model.py --check-credentials`. Lệnh này chỉ chứng minh key đã cấu hình và ID khớp, chưa xác thực với server.
- Nếu key chưa có/không đọc được, yêu cầu người dùng cấu hình cục bộ và báo lại, không tạo key giả hay sửa `.env` thay họ.

### Bước B — Review smoke script trước khi dùng key thật

Đọc kỹ logic, sửa lỗi có bằng chứng trong phạm vi task01 trước khi inference:

- Chỉ gọi đúng model, không fallback sang pretrained COCO hoặc model khác.
- Input ảnh là BGR từ OpenCV; xác minh convention với SDK đang cài. Không đổi RGB/BGR theo suy đoán.
- Class name/ID lấy từ metadata model, không hard-code thứ tự `ball/rim/human`.
- Kích thước resize giữ tỷ lệ; tọa độ JSON quy về frame gốc; overlay cùng hệ tọa độ với ảnh đang vẽ.
- Kiểm tra NaN/Inf, confidence ngoài [0,1], class ID không hợp lệ, array length không khớp và bbox sai thứ tự. Không che lỗi bằng cách trả empty detections để giả thành công.
- Clip dọc cần kiểm tra riêng; việc giảm cạnh dài xuống 1280 chưa có nghĩa network input là 1280. SDK có thể resize/letterbox thêm; ghi rõ nếu biết.
- Có cleanup video handles, giới hạn sample, thông báo lỗi an toàn và từ chối ghi đè output cũ.
- Không có đường upload frame trong đường inference local; không bật custom code để chữa lỗi nhanh.
- Tránh in key, authenticated URL, raw HTTP body hoặc traceback chứa secrets. Nếu cần chẩn đoán, bổ sung stage/error code hoặc thông báo đã lọc, không mở lại toàn bộ log mạng.

Không refactor toàn bộ project hoặc thêm abstraction không cần thiết cho task01. Không coi script hiện có là chắc chắn đúng chỉ vì đã có tests.

### Bước C — Tests và một lần smoke test có kiểm soát

Các lệnh dưới đây chạy từ gốc workspace, dùng PowerShell. Với smoke test, dùng output directory mới hoặc để script tự tạo timestamp:

```powershell
codebase/.venv/Scripts/python.exe codebase/scripts/check_environment.py --output codebase/outputs/environment-python312-current.json
codebase/.venv/Scripts/python.exe codebase/scripts/smoke_model.py --check-credentials
codebase/.venv/Scripts/python.exe -m unittest discover -s codebase/tests -v
codebase/.venv/Scripts/python.exe codebase/scripts/smoke_model.py --source codebase/assets_test --samples 6
```

- Chạy 6 frame/clip làm lượt baseline: dự kiến 18 frame measured tổng cộng và 2 warm-up theo script hiện tại.
- Không benchmark lặp dài hoặc xử lý cả video chỉ để lấy smoke evidence.
- Nếu sample đều bỏ lỡ khoảnh khắc có bóng/vành rõ, đọc video cục bộ để chọn thêm ít frame có timestamp cụ thể. Lưu lựa chọn và lý do; không che mẫu thất bại hoặc ghi thành độ chính xác toàn video.
- Nếu SDK/model ID/backend không tương thích, dừng bước inference, chẩn đoán bằng tài liệu chính thức và xin quyết định theo mục 4. Không đổi model âm thầm.
- Nếu lỗi giữa chừng, output phải được nhận diện là incomplete/failed; không tạo báo cáo `completed` giả hoặc trộn ảnh run cũ vào run mới.

### Bước D — Xem output bằng mắt và kiểm tra schema

- Mở ảnh bbox thực tế từ cả ba clip, bao gồm clip dọc và clip đêm.
- Đối chiếu `class_mapping`, `observed_classes`, confidence và bbox JSON với ảnh gốc/overlay.
- Phân biệt “metadata có class” với “đã phát hiện đúng class đó trên ảnh”. Với class chưa xuất hiện trong sample, ghi rõ và kiểm tra thêm frame phù hợp nếu có; không tự điền detections.
- Kiểm tra có bbox người/vành/bóng hợp lý, không lệch hệ tọa độ, không kéo dãn ảnh và không dùng bbox cả bảng rổ thay cho vành mà không ghi nhận.
- Ghi các lỗi quan sát được: bóng mất, ánh sáng yếu, bóng quá nhỏ, che khuất, false positive, camera motion. Chọn ví dụ thành công và lỗi nếu có.
- Chưa có ground truth bbox/event đầy đủ thì không tuyên bố precision/recall/mAP hoặc độ chính xác scoreboard từ 18 frame.

### Bước E — Đo baseline và chốt runtime

Tối thiểu ghi:

1. Máy, OS, interpreter và package versions; ONNX provider và device thực sự dùng.
2. Model ID chính xác, runtime class, class mapping và thông tin model được SDK xác nhận nếu có.
3. Độ phân giải gốc, kích thước ảnh đưa vào SDK, threshold, cách chọn frame, số mẫu/clip và warm-up.
4. `model_init_s` kèm trạng thái cache; nếu bao gồm download thì ghi rõ “download + initialization”, không coi đó là thời gian load thuần.
5. Hai warm-up tách khỏi measured samples; median và mean model-call latency sau warm-up, đơn vị ms. Thêm min/max nếu hữu ích.
6. Scope timing: model call có preprocessing/forward/postprocessing nào; có loại trừ decode, resize ngoài SDK, vẽ và ghi không. Không gọi nghịch đảo latency này là FPS toàn pipeline.
7. Chất lượng detection định tính theo từng clip và giới hạn của cỡ mẫu.

Task01 không yêu cầu CPU phải đạt 60 FPS. Nếu CPU chạy được nhưng chậm, có thể nghiệm thu khả năng chạy model và ghi baseline; ghi yêu cầu real-time chưa được chứng minh và xin ý kiến trước bước GPU. Nếu latency quá chậm đến mức không chạy xong smoke test hợp lý, báo rõ thay vì bỏ qua clip.

## 6. Bảo mật và tính toàn vẹn

- Key chỉ được đọc cục bộ trong bộ nhớ; không đưa vào prompt, log, filename, JSON, README, tests hoặc câu lệnh shell hiển thị key.
- Kiểm tra `.env`, `.env.*` trừ example, video lớn, `.venv`, `.tools`, caches, weights và outputs được bỏ qua bởi Git. Gitignore không loại được file đã tracked; nếu có Git, kiểm tra tên file tracked mà không in nội dung secrets.
- Nếu phát hiện secret đã tracked/lộ, báo người dùng và đề xuất xử lý; không tự viết lại lịch sử Git hoặc tự xoay key.
- Không đọc credential store của plugin để lấy key cho Python.
- Không sửa/xóa video gốc. Không xóa outputs cũ để “làm sạch” khi chưa được yêu cầu.
- Không commit/push/publish. Không tắt kiểm tra TLS, không nâng quyền rộng hoặc chạy script remote chưa kiểm tra.
- Dùng đường dẫn/lệnh Windows an toàn, ưu tiên thao tác có phạm vi rõ. Giữ cache ngắn đã được người dùng đồng ý nếu cần cài lại.

## 7. Đầu ra cần bàn giao

Giữ code trong `codebase/`, docs trong `docs/`. Tái sử dụng file hiện có thay vì tạo bản trùng không cần thiết.

| Đầu ra | Yêu cầu |
|---|---|
| `codebase/scripts/smoke_model.py` | Chạy được với đúng model, schema/tọa độ đúng, lỗi an toàn |
| `codebase/scripts/check_environment.py` | Báo môi trường đang dùng; không ghi key |
| `codebase/tests/test_smoke_contract.py` | Tests liên quan pass; bổ sung khi sửa lỗi có rủi ro thực tế |
| `codebase/requirements.in`, `requirements.txt` | Nhất quán với môi trường đã kiểm tra; không chỉ khóa một tập dependency chưa chạy được model |
| `codebase/.env.example`, `.gitignore` | Không có key thật, bỏ qua đủ artifacts cục bộ |
| `codebase/outputs/smoke-<run_id>/` hoặc `codebase/outputs/smoke/<run_id>/` | Run directory duy nhất, ảnh bbox thật trên 3 clip, `smoke.json` và evidence cần thiết |
| `docs/reports/task01-smoke.md` | Lệnh chạy, run path, trạng thái, class mapping, bảng latency, review ảnh từng clip, hạn chế và quyết định runtime |
| `docs/reports/environment.md` | Trạng thái hiện tại, phiên bản và phần chưa kiểm chứng rõ ràng |
| `docs/tasks/task01.md` | Checklist nghiệm thu cập nhật theo bằng chứng |
| `codebase/README.md` | Hướng dẫn tái chạy chính xác, đường dẫn output và xử lý lỗi không lộ key |

Nếu paths khác tài liệu cũ, cập nhật links và giải thích ngắn. Không tạo ảnh bbox giả, không dùng metrics train để thay baseline thực tế. Output local không cần đưa vào Git nhưng báo cáo phải chỉ rõ vị trí để người dùng mở.

## 8. Definition of Done

Chỉ đánh dấu task01 DONE khi có đủ bằng chứng sau:

- [ ] Runtime dự án thực sự gọi đúng model YOLO26s đã chỉ định; metadata training đơn thuần không đủ.
- [ ] Chạy smoke test thành công trên cả 3 video; có sample counts và output paths tái kiểm tra được.
- [ ] Mapping `ball/rim/human` lấy từ model; schema hợp lệ và có ảnh đối chiếu quan sát thực tế. Nếu class chưa quan sát được, ghi nhận và chưa đánh dấu mục đó đã xác minh thực tế.
- [ ] Đã xem ảnh bbox cả video ngang/dọc; xác nhận tọa độ sau resize đúng.
- [ ] Init/cache/warm-up/measured latency tách rõ; không có claim real-time chưa đo.
- [ ] Tests liên quan pass; dependency/runtime đã dùng được ghi phiên bản và hướng tái chạy.
- [ ] Secrets/video gốc được bảo vệ; không có output log chứa key.
- [ ] Báo cáo, README, task status và quyết định runtime nhất quán.

Nếu chưa đáp ứng, giữ IN_PROGRESS và ghi phần chờ cụ thể. Một quyết định về hướng khắc phục không thay thế việc chạy model thật. Không chuyển sang task02–08 như cách né việc chưa hoàn thành task01.

## 9. Cách giao tiếp và câu trả lời cuối

Trong lúc chạy, cập nhật ngắn khi có phát hiện, lỗi hoặc quyết định; không để người dùng phải suy đoán tiến độ. Phân biệt “đã cài”, “import thành công”, “đã inference”, “đã review output” và “đã nghiệm thu”.

Câu trả lời cuối bằng tiếng Việt, gồm:

1. Task01 DONE hay IN_PROGRESS và lý do.
2. Các file thay đổi quan trọng, links tới báo cáo và ảnh/run output.
3. Model/backend/device thật, số mẫu và class mapping.
4. Latency đo được cùng giới hạn đo; không gọi model-call throughput là end-to-end FPS.
5. Kết quả tests và vấn đề chất lượng còn lại.
6. Nếu cần người dùng quyết định, một câu hỏi cụ thể cùng phương án đề xuất và tác động; không yêu cầu cung cấp key trong chat.

Hãy bắt đầu bằng đọc tài liệu và xác minh trạng thái, sau đó tiến hành phần được phép đến khi có kết quả kiểm chứng hoặc một điều kiện thực sự cần người dùng quyết định.
