# Nghiệm thu task01 và task02 — 2026-11-01

## Kết luận và phạm vi

**Task01: PASS. Task02: PASS cho bộ dữ liệu pilot. Sẵn sàng bắt đầu task03 với clip02.** Không triển khai task03 trong đợt nghiệm thu này. Chưa chứng minh real-time hoặc độ chính xác scoring; tập test chỉ có 7 lượt trong một session.

Nghiệm thu dựa trên code/dữ liệu hiện tại, output cũ đã đối chiếu, một lần inference mới trên calibration và kiểm thử hồi quy. Không thay đổi video gốc, nhãn, reviews, coverage hay split đã khóa. Phê duyệt nhãn dựa trên reviews.csv được bàn giao, không tạo phê duyệt mới.

## Bằng chứng task01

| Kiểm tra | Kết quả |
|---|---|
| Interpreter / backend | Python 3.12.14 trong codebase/.venv; ONNX CPU |
| Model | phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1 |
| Runtime class | YOLO26ForObjectDetectionOnnx |
| Mapping metadata | 0: ball, 1: human, 2: rim |
| Output cũ | smoke-20261031-215143: 18 samples/3 video, đủ 18 ảnh |
| Detections cũ | 8 ball, 64 human, 15 rim; 0 bbox ngoài phạm vi hoặc class-name mismatch theo audit |
| Median cũ tính lại từ samples | 490,376 ms |
| Run mới | acceptance-20261101/model-smoke-online: 3 samples, chỉ clip02 |
| Detections mới | 2 ball, 3 human, 3 rim; class metadata khớp |
| Init mới | 12,404 s; bao gồm việc truy xuất/nạp model, không đo riêng download |
| Warm-up mới | 912,402 và 658,293 ms, tách khỏi measured samples |
| Latency measured mới | Median 723,964 ms; mean 609,017 ms; mẫu rất nhỏ, có dao động |

Timing là model call CPU gồm preprocessing/postprocessing trong runtime; không tính decode, resize ngoài SDK, vẽ và ghi. Không quy đổi thành FPS toàn pipeline hoặc gọi là real-time. Init có thể liên quan truy xuất metadata/cache, không kết luận tải weights một lần là mọi lần sau không cần mạng.

Đã mở ảnh output cũ từ cả ba clip: video dọc giữ tỷ lệ, bbox người/vành nhìn phù hợp trên các ví dụ; clip đêm có frame không bắt được vành. Run mới đã xem các frame 181 và 544: vị trí bbox phù hợp hình ảnh, bóng bị bỏ sót ở sample đầu và phát hiện ở sample sau. Không có bbox ground truth nên đây là kiểm tra định tính/hệ tọa độ, không xác nhận bbox chính xác từng pixel hay precision/recall.

Tên overlay của run mới bắt đầu bằng clip01 vì đó là thứ tự video trong run, **không phải dataset video_id**. Nguồn thật trong trường samples[].video là 20521993-uhd_2160_3840_60fps.mp4 (clip02). Task03 phải lưu video_id/filename rõ ràng trong metadata.

### Kiểm tra offline và quyền đã dùng

- Thử với OFFLINE_MODE=True tại outputs/acceptance-20261101/model-smoke: ModelRetrievalError; không có success report. Thư mục này là run thất bại, không dùng làm bằng chứng model pass.
- Đã hỏi và nhận đồng ý của người dùng cho truy xuất metadata/weights đúng model từ Roboflow, sau đó inference local trên clip02. Không upload media và không dùng inference cloud.
- Với OFFLINE_MODE=False, run mới hoàn thành. Không tái kiểm chứng offline sau lần kết nối này; không cam kết chế độ hoàn toàn offline.

Lệnh thành công, từ gốc workspace:

```powershell
$env:OFFLINE_MODE = 'False'
codebase/.venv/Scripts/python.exe codebase/scripts/smoke_model.py --source codebase/assets_test --video-name 20521993-uhd_2160_3840_60fps.mp4 --samples 3 --output codebase/outputs/acceptance-20261101/model-smoke-online
```

Khi chạy lại, phải dùng output mới. Key được đọc bởi script cục bộ; không đưa vào lệnh, log hoặc báo cáo.

## Bằng chứng task02

| Tiêu chí | Kết quả |
|---|---|
| Manifest và media | 7 file tồn tại, SHA-256 khớp manifest |
| Approved / draft | 10 approved theo ledger, 0 draft |
| Tổng nhãn | 6 made, 4 miss; 0 uncertain |
| Calibration | clip02: 1 made |
| Test | clip04–07: 4 made, 3 miss; cùng session broadcast |
| Ngoài scoring | clip01 và clip03, vẫn giữ trong manifest |
| Split | 1.0.0-locked; không đổi phân chia |
| Fingerprint khóa | manifest.csv, events.csv, coverage.csv đều khớp |
| Snapshot bổ sung | audit.json ghi hash cả reviews, draft và splits để đối chiếu bàn giao |
| Validator --require-ready | PASS cho pilot; cảnh báo dưới mục tiêu thu thập 50–100 lượt |

Đã kiểm tra một lần nữa các frozen-file hashes sau thao tác code/docs: **không đổi**. Không sửa câu trả lời made/miss hoặc timestamp được duyệt.

FFprobe packet PTS xác nhận clip04–07 có nhịp biến thiên khoảng 33,3–70,0 ms; clip01–03 có khoảng PTS đều. Task03/07 cần dùng PTS thay vì frame_index/avg_fps cho broadcast. Số frame trong notes của nhãn VFR chỉ là tham chiếu gần đúng; audit thấy sai lệch quy đổi tới khoảng 65 ms, không tự sửa ground truth vì lý do này.

## Kiểm thử và review code

Áp dụng hướng dẫn code-review để đánh giá correctness, secrets, tính toàn vẹn dữ liệu và phạm vi. Không có Git repo để tạo diff theo commit; kiểm tra trực tiếp các file thuộc task01–02.

**Verdict: APPROVE cho phạm vi task01–02 và bắt đầu task03. Confidence: HIGH cho các kiểm tra đã chạy, không suy rộng chất lượng scoring.**

| Mức | Vấn đề phát hiện | Xử lý và bằng chứng |
|---|---|---|
| P1 | Split khóa có events/coverage hashes nhưng validator chỉ kiểm tra manifest | Kiểm tra cả ba, thêm test thay nhãn/coverage phải fail |
| P1 | Readiness lấy made/miss từ toàn corpus, không phải test thực tế | Lọc test IDs; test thiếu miss không được mượn class từ calibration |
| P1 | Media thay đổi không bị kiểm tra hash; thiếu ledger chỉ là warning | So SHA-256 media, ledger bắt buộc; regression pass |
| P1 | Coverage overlap/excluded có thể bị xem như tập đủ điều kiện | Kiểm tra overlap, coverage đã review và containment của event |
| P1 | Group JSON thiếu có thể bỏ qua leakage từ manifest | Kiểm tra camera/session/hash từ manifest và membership nhóm |
| P1 | prepare_dataset ghi đè manifest và IDs mới phụ thuộc thứ tự file | Refuse overwrite, giữ metadata theo hash, ID mới ổn định theo hash |
| P1 | Smoke mặc định sẽ nhận cả 4 holdout mới; lỗi SDK có thể in raw message | Tự loại holdout locked, thêm chọn basename; chỉ in loại lỗi upstream |
| P1 | Windows copy fallback bắt mọi OSError; bản vá thiếu một số guard cache | Chỉ fallback WinError 1314, không overwrite; kiểm tra blob/symlink/path/checksum sau copy |
| P2 | 50–100 lượt bị biến thành readiness gate cứng; docs còn draft counts | Đưa về cảnh báo đúng kế hoạch; cập nhật docs theo dữ liệu thật |

**31 tests PASS**: 21 validator, 2 prepare-manifest, 8 smoke/security/Windows-compat. Test dùng fixtures local; không dùng nhãn model để tự tạo expected output. Lần đầu sandbox chặn thư mục tempfile; chạy lại với quyền phù hợp thành công. Không thay hệ điều hành/driver/dependency.

Các lệnh đã chạy:

```powershell
codebase/.venv/Scripts/python.exe -m unittest discover -s codebase/tests -v
codebase/.venv/Scripts/python.exe codebase/scripts/validate_dataset.py --require-ready
codebase/.venv/Scripts/python.exe codebase/scripts/audit_handoff.py --output codebase/outputs/acceptance-20261101/audit.json
```

Kiểm tra phủ định CLI: prepare_dataset.py mặc định từ chối ghi đè manifest hiện có (exit 1, đúng kỳ vọng); nội dung manifest không đổi. audit_handoff là kiểm tra đọc metadata/hash/archived output, không chạy model hoặc đọc .env.

## Các giới hạn còn lại

- 7 lượt test trong một session và calibration thiếu miss: chưa đủ đánh giá tổng quát hoặc chỉnh rule chắc chắn. Giữ cảnh báo cỡ mẫu, không dùng holdout để tối ưu.
- Ledger là bằng chứng xác nhận nhãn được bàn giao; đợt nghiệm thu không tái gán nhãn từng pha hoặc xác minh độc lập danh tính người duyệt.
- Camera/session group chống rò rỉ theo thông tin hiện có; không chứng minh tuyệt đối mọi footage không trùng ngữ nghĩa. Holdout đã được xem để gán nhãn, không phải blind chưa từng thấy.
- Model runtime CPU hiện chậm hơn FPS nguồn; giữ baseline offline đầy đủ frame. Skip-frame có thể mất khoảnh khắc bóng qua rổ, chưa được nghiệm thu.
- Git chưa được khởi tạo tại workspace/codebase; đã kiểm tra ignore rules và credential handling, chưa có tracked-file audit/historical secret scan bằng Git. Không tự git init/commit/push.
- Bản vá Windows phụ thuộc API nội bộ inference-models 0.39.7. Khi nâng dependency phải kiểm thử lại; không tự nâng.

## Bàn giao và evidence paths

- [Hợp đồng task03](../handoffs/task03.md).
- [Dữ liệu hiện tại](data.md), [hướng dẫn nhãn](../data/ANNOTATION_GUIDE.md).
- [Task01](../tasks/task01.md), [task02](../tasks/task02.md), [README](../../codebase/README.md).
- [Snapshot audit](../../codebase/outputs/acceptance-20261101/audit.json).
- [Smoke mới](../../codebase/outputs/acceptance-20261101/model-smoke-online/smoke.json), [ảnh ví dụ](../../codebase/outputs/acceptance-20261101/model-smoke-online/clip01_frame00544.jpg).

Outputs lớn/local vẫn bị Git ignore. Giữ các file này trên máy khi bàn giao; không giả định chúng xuất hiện trong clone mới.
