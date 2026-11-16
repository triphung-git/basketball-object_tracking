# Task07A — checkpoint gốc và fine-tune cục bộ

**Khôi phục 2026-11-09:** theo yêu cầu người dùng, đã khởi động lại dưới supervisor Windows chạy nền riêng; run hiện hành `job/restart-03/` (restart-01/02 giữ để audit). Supervisor quản lý cả hai download workers, cập nhật `job/status.json` mỗi khoảng 5 giây và lưu stage logs. Resume dùng strong ETag/range để giữ chunks hợp lệ dù URL export được cấp lại; chunks mới có SHA-256. CUDA wheels lấy từ official PyTorch cu128 index và xác minh SHA-256 từ index trước khi cài offline trong `.venv-train`.

Luồng khôi phục hiện hành **chuẩn bị đến trạng thái `ready_for_finetune`**: tải đủ → cài CUDA → kiểm ZIP CRC/giải nén → audit và tạo mixed dataset → GPU forward/loss/backward/optimizer smoke (batch 2, 640, AMP, chỉ dữ liệu synthetic, không lưu weights) → preflight/hashes/dependency lock. Đây thay cho supervisor cũ chờ PID; chưa tự chạy 30 epochs trong lượt chuẩn bị này. `training_started=false` chỉ trở thành run training khi lệnh fine-tune thật được chạy. Không khẳng định đã sẵn sàng chỉ vì worker còn hoạt động; xem `status.json` và `restart-03/readiness.json` sau khi hoàn tất.

Trạng thái `preparation_failed`/`interrupted` có error type và stage log; không đổi thành ready khi lỗi. File `status.json` gồm tiến độ từng artifact và PID supervisor. Khi đọc trạng thái cũ, đối chiếu heartbeat/PID thực tế. Lệnh khôi phục có kiểm tra worker còn hoạt động để tránh chạy trùng:

```powershell
powershell -NoProfile -File codebase/scripts/start_task07a_preparation.ps1
```

Không chạy thêm khi supervisor hiện hành còn sống. Artifact data/model gốc, OCR và ROI production được giữ nguyên; candidate vẫn cần downstream acceptance trước khi promote. Các ghi chú chờ/dừng bên dưới là lịch sử.

Kiểm tra sau khôi phục: **333 tests và 61 subtests PASS**, 6 warnings thư viện; log tại `job/restart-03/tests.log`. Có regression về refreshed-URL/ETag resume, checksum, giữ file cũ khi checksum sai và chờ manifest đủ hai CUDA wheels trước khi chuyển stage. Launcher PowerShell đã qua syntax parse. Đây là kiểm tra code; GPU backward smoke và data readiness chỉ được xác nhận bởi artifacts của stage tương ứng sau download.

**Kiểm tra lại tối 2026-11-08:** các tiến trình download/CUDA/supervisor cũ không còn chạy. Dataset mới có 218/779 chunks hoàn tất (228,589,568/816,591,898 bytes, 28%); môi trường vẫn torch 2.15.0+cpu, CUDA=False. Chưa train. Đã sửa `job/status.json` thành `interrupted_downloads_not_running`, lưu bằng chứng tại `job/interruption-check-20261108.json`. Chưa xác định nguyên nhân kết thúc từ artifacts hiện có; không coi trạng thái chờ cũ là tiến trình vẫn hoạt động. Cần khôi phục phần tải/cài trước khi mở lại supervisor. Các nội dung phía dưới mô tả lúc triển khai ban đầu.

Ngày 2026-11-08. Người dùng yêu cầu tải model gốc và thực hiện fine-tune trên dữ liệu cũ cùng dữ liệu bổ sung. Yêu cầu này cho phép thực hiện training candidate cục bộ; các trường `training_authorized=false` trong artifacts ngày 05/11 là lịch sử, không được sửa thành phê duyệt giả cho nhãn.

## Đã xác minh

- Đã tải raw checkpoint của `phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1` về `codebase/models/checkpoints/task07a-original/best.pt`, 20,317,125 bytes.
- SHA-256: `2c081e9ee45d0e942d9f03c9b48e632cefd3b43a1dbfd748ff5a02f052221761`.
- Ultralytics 8.4.207 nạp checkpoint thành công: detection, 9,950,186 parameters, thứ tự class `0=ball, 1=human, 2=rim`. Synthetic inference CPU thành công; đây không phải phép đo accuracy.
- Môi trường `.venv-train` tách khỏi `.venv` inference/OCR. Probe đầu dùng torch 2.15.0+cpu; đang tải torch 2.11.0+cu128 và torchvision 0.26.0+cu128 để dùng RTX 2050 4 GB. Chỉ coi CUDA sẵn sàng sau GPU probe thực tế.
- Đã validate và xuất 49 ảnh/nhãn supplemental đã được người dùng duyệt trong `accepted-v2/merged-progress-v3.json`. Giữ nguyên packet nguồn, loại khỏi export 308 ảnh chưa duyệt và 2 ảnh skipped; không dùng predictions làm nhãn.
- Full regression suite: **319 tests và 61 subtests PASS**, 6 warnings từ thư viện hiện có. Log: `codebase/outputs/task07a-finetune-20261108/tests.log`.

## Trạng thái job hiện hành

Đọc `codebase/outputs/task07a-finetune-20261108/job/status.json` để biết trạng thái thực tế. Tại thời điểm lập report, dataset version 1 (YOLO export, 816,591,898 bytes) và CUDA wheel vẫn đang tải; **chưa bắt đầu fine-tune**. Không coi việc có script/job là đã train xong.

Supervisor chờ hai tác vụ tải hiện hành, kiểm tra ZIP và giải nén vào thư mục mới, audit ảnh/nhãn, tạo mixed dataset, chạy preflight, rồi chạy một candidate 30 epochs / batch 2 / imgsz 640 / AdamW lr0 0.0001 / seed 7 / workers 0 / patience 10. Recipe là thử nghiệm ban đầu cho GPU 4 GB, chưa phải cấu hình tối ưu. Không fallback sang CPU training nhiều giờ nếu CUDA không hoạt động.

Khi tải thất bại, thiếu class/label, hash thay đổi, CUDA không dùng được hoặc OOM, job dừng và ghi lỗi trong `status.json`/stage log. Download hỗ trợ chunks có binding URL hash/range/ETag; không dùng chunk thiếu binding. URL tải riêng không lưu trong report hay source.

## Dữ liệu và giới hạn đánh giá

`prepare_task07a_finetune.py` giữ original train, chỉ bổ sung các rows approved vào train. Original valid/test có cùng filename family hoặc exact decoded pixels với train bị quarantine; test trùng valid theo hai tiêu chí đó cũng bị quarantine. Không chuyển holdout cũ sang train và không gọi checkpoint-exposed source là unseen.

Filename-family/exact-pixel audit không phát hiện hết near-duplicates và không chứng nhận completeness của nhãn bằng ngữ nghĩa. Dataset cũ đã có cảnh báo source leakage; native validation/test sau cleanup vẫn chỉ là phép đo chẩn đoán. Dữ liệu bổ sung thuộc trận Việt Nam–Tonga development: sau training không dùng trận đó làm bằng chứng independent-match generalization.

Sau training, job chạy paired native detector evaluation cho checkpoint gốc và candidate trên cùng test subset. Kết quả ở `job/detector-evaluation/comparison.json`. Preprocessing native Ultralytics không tự được coi tương đương pipeline Roboflow ONNX hiện hành.

## Bảo vệ OCR, ROI và đầu ra

Không thay approved model ID, weights ONNX, OCR engine, tracker hoặc ROI hiện hành. Training script chụp hashes `src/`, `configs/` và ONNX cache trước/sau training; lưu `runtime_unchanged` trong training run report. Candidate được lưu riêng, không tự promote.

Trước khi đưa candidate vào inference cần paired evaluation qua đúng preprocessing/tile/mapping và toàn pipeline: observed ball recall/false observations; human/rim regression; crop OCR coverage và exact jersey accuracy; identity/ID switches; ROI exclusion; strict control/pass; latency. Tests PASS và mAP detector không chứng minh OCR không giảm.

**Không cam kết hiệu suất candidate trước khi đo.** `production_promotion_allowed=false` được giữ cho đến khi có downstream evidence và điều kiện nghiệm thu đã chốt. Sau khi candidate được tạo vẫn còn công việc acceptance; Task07 chưa DONE.

## Các entrypoint

- `codebase/scripts/inspect_task07a_checkpoint.py`: xác minh checkpoint và synthetic inference.
- `codebase/scripts/prepare_task07a_finetune.py`: export approved subset hoặc audit/stage mixed dataset.
- `codebase/scripts/train_task07a_candidate.py`: kiểm tra hash, class mapping, split membership; preflight mặc định, `--execute` để train candidate.
- `codebase/scripts/evaluate_task07a_candidate.py`: paired native detector metrics, không promote.
- `codebase/scripts/run_task07a_finetune_job.py`: supervisor, status và stage logs.

Không khởi chạy job thứ hai khi job hiện hành còn hoạt động. Không tái sử dụng output directory đã có khi chạy lại.
