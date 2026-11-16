# Prompt thực thi Task07 — Training readiness, fine-tune và paired evaluation

Ngày tạo: **2026-11-13**. Ưu tiên sau bản sửa core Ledger/Box Score ngày 11/11 và core Shot Engine/Evaluator ngày 12/11. Tài liệu này là yêu cầu thực thi, chưa phải kết quả training hoặc nghiệm thu.

## 1. Vai trò và kết quả cần đạt

Bạn là Senior AI/Python Engineer. Hãy triển khai Task07 theo thứ tự: kiểm kê hiện trạng → sửa training readiness bằng detection loss thật → kiểm chứng batch dữ liệu thật → fine-tune model gốc trên dataset cũ và bổ sung đã duyệt → đánh giá paired detector và downstream → bàn giao checkpoint, artifacts và quyết định chất lượng có bằng chứng.

Không chỉ lập kế hoạch hoặc dừng ở chạy launcher. Thực hiện các phần đã được người dùng cho phép bằng môi trường và dữ liệu có sẵn. Fine-tune local trên model gốc đã được cho phép trong cuộc hội thoại; không hỏi lại quyền chạy cùng công việc đó. Không tự upload media, mua dịch vụ, thuê GPU/cloud, đổi model family/backend/GPU stack hoặc thay frozen holdout. Nếu thật sự cần một thay đổi ngoài phạm vi, hoàn tất các phần độc lập, đưa ra phương án cụ thể cùng lý do rồi mới xin quyết định.

Mục tiêu gồm hai lớp riêng: (a) training hợp lệ có artifact thật; (b) candidate cải thiện chất lượng trong coverage đo được và không gây hồi quy OCR/ROI/identity hoặc các engine downstream. Train xong không đồng nghĩa đạt lớp (b). Không cam kết chỉ fine-tune detector là sửa được OCR, strict control, pass và PRA.

## 2. Đọc hiện trạng và giữ bằng chứng cũ

Tìm `AGENTS.md` áp dụng nếu có. Đọc `docs/DEVELOPMENT.md`, `PLAN.md`, `docs/tasks/task07.md`, các contracts/rules/protocol liên quan cùng:

- `docs/reports/demo-completion-acceptance-20261110.md`: P1-K, audit dataset, source snapshot drift và giới hạn evaluation.
- `docs/reports/task07a-local-finetune-20261108.md`, `checkpoint-p1-data-qa-and-training.md`; các claim training/smoke của ngày 09/11 phải đối chiếu audit ngày 10/11, không coi là sự thật hiện hành.
- `docs/reports/task07-improvement-roadmap-20261105.md`, `task07c-acceptance-report-20261107.md` và các báo cáo crop/ownership/team/identity gần nhất.
- `docs/reports/task11-ledger-correctness-20261111.md`, `task08-shot-correctness-20261112.md`, outputs liên quan. Giữ các bản sửa core đã kiểm chứng; không khôi phục source cũ để vượt hash guard.
- `codebase/scripts/prepare_task07a_finetune.py`, `probe_task07a_gpu_training.py`, `gpu_training_smoke_test.py`, `train_task07a_candidate.py`, `evaluate_task07a_candidate.py`.
- `codebase/scripts/prepare_task07a_ready.py`, `run_task07a_finetune_job.py`, `start_task07a_preparation.ps1` và các scripts launcher/evaluator Task07C thực có.
- `codebase/tests/test_task07a_finetune.py`, `test_task07a_readiness.py`, các tests Task07C/Task08/Task11 và acceptance probes 10/11 liên quan.

Kiểm tra các report/source/artifact mới hơn; nếu một lỗi đã được sửa hợp lệ thì giữ regression, không sửa lại theo giả định cũ. Lưu input inventory và code/config snapshot cho run mới, không sửa manifests/hashes/weights/logs của các experiment cũ.

## 3. Các tài nguyên đã có — phải xác minh lại khi thực thi

| Thành phần | Snapshot đã kiểm ngày 13/11 |
|---|---|
| Model gốc | `codebase/models/checkpoints/task07a-original/best.pt` |
| SHA-256 model gốc | `2c081e9ee45d0e942d9f03c9b48e632cefd3b43a1dbfd748ff5a02f052221761` |
| Class order | `0=ball`, `1=human`, `2=rim` |
| Dataset gốc | `codebase/data/finetune/task07a/original/` |
| Bản dẫn xuất | `codebase/data/finetune/task07a/derived_export_v1/` |
| Dataset mixed | `codebase/data/finetune/task07a/mixed-20261108/` |
| Mixed split | Train 6.711, validation 515, test 219; gồm 49 supplemental approved; không gồm 308 draft |
| Môi trường train | `codebase/.venv-train/Scripts/python.exe`; PyTorch `2.11.0+cu128`, Ultralytics `8.4.207`; CUDA available |
| Phần cứng | RTX 2050; snapshot trước ghi nhận VRAM 4 GB |
| Dung lượng trống | Khoảng 12,2 GiB trên C tại lần kiểm; phải đo lại trước run |

Dataset đã qua audit kỹ thuật integrity/hình học; không đồng nghĩa semantic labels, near-duplicate audit hoặc độc lập theo trận đã được nghiệm thu. Manifest mixed vẫn có trạng thái staging; đọc giới hạn và xác minh điều kiện sử dụng, không tự đổi thành approved/promoted để vượt gate.

Job cũ `codebase/outputs/task07a-finetune-20261108/job/status.json` ghi `preparation_failed`. Candidate cũ `codebase/outputs/task07a-candidate-20261109/run.json` ghi `training`, nhưng thư mục candidate đã kiểm chỉ có args/labels/batch previews, chưa có results.csv/best.pt/last.pt. Xem đây là metadata lịch sử chưa đủ chứng minh training đang chạy hoặc đã hoàn tất.

Không tải lại ZIP/wheels/checkpoint khi bản local còn khớp checksum. Không cài lại dependencies chỉ để bắt đầu. Kiểm dung lượng dự kiến cho checkpoints/cache/logs/exports; hạn chế artifact dư thừa trong run mới và tránh bản sao dataset không cần thiết. Không tự xóa dữ liệu gốc, venv, weights hay outputs cũ để lấy chỗ.

## 4. Phase A — Kiểm kê và dựng experiment có thể tái lập

1. Kiểm tra Python/package versions, CUDA/device/VRAM thực, free disk và các process train/preparation hiện hành. Xác minh command line, start time và run ID; PID tồn tại không đủ do có thể đã được tái sử dụng. Không kill process ngoài run của mình, không launch trùng job.
2. Xác minh checkpoint hash/class mapping và dataset manifests/image-label bindings bằng các hàm production hiện có. Kiểm full split membership, bbox finite/positive/in-bounds, ảnh decode được, ảnh trống hợp lệ và approved supplemental membership. Không sửa bản gốc để làm QA pass.
3. Kiểm leakage: exact/pixel duplicates, source family, adjacent frame/physical play và replay/original. Giữ quarantine đã có; nếu phát hiện vấn đề mới thì tạo version/manifest dẫn xuất với provenance, không thay frozen labels/splits. Bổ sung nhãn chỉ khi có approved review thật, không tự duyệt draft.
4. Phân biệt tập train, validation dùng model selection và untouched test. Dữ liệu Vietnam–Tonga đã dùng training/calibration hoặc đã xem nhiều lần là development diagnostic, không gọi independent match validation. Ghi rõ exposure history của split test cũ trước khi dùng lại.
5. Tạo run mới `codebase/outputs/task07-finetune-recovery-<run-id>/` có run ID, UTC timestamps và nguồn model/dataset/code/config/hash. Chạy từ source snapshot mới sau các sửa Task08/11; không resume experiment cũ với source/config khác bằng cách sửa expected hashes. Freeze implementation sau bước sửa/test trước khi chạy dài.
6. Định nghĩa trước recipe, validation criteria và downstream regression gates dựa trên protocol hiện hành. Nếu chưa có tolerance chất lượng cho một chiều, ghi tiêu chí diagnostic đề xuất và giữ pending; không tự nới protocol hoặc chọn tiêu chí sau khi thấy kết quả.

## 5. Phase B — Sửa và kiểm chứng detection training loss thật

Audit 10/11 chỉ ra `gpu_training_smoke_test.py` lấy trung bình outputs boxes/scores làm scalar loss và không dùng labels; smoke đó không chứng minh detection training. `probe_task07a_gpu_training.py` thật sự gọi criterion nhưng gặp thiếu `hyp.box` trong runtime đã kiểm. Tái hiện đúng lỗi trên môi trường hiện tại, lưu traceback trước khi sửa.

Sửa bằng API/recipe phù hợp phiên bản Ultralytics đã cài và checkpoint YOLO26s đang có. Đọc implementation cục bộ của trainer/criterion/default config để xác định thiếu gì; dùng tài liệu chính thức tương ứng nếu cần tra cứu. Không đoán loss theo model khác, không thay criterion bằng surrogate hoặc chỉ gán mỗi `box` rồi mặc định đầy đủ. Dùng hyperparameters/defaults hợp lệ cho đúng architecture, kiểm end-to-end heads theo implementation thực.

Readiness phải chứng minh:

- Native checkpoint load được, parameters cần train có `requires_grad=True`, class mapping giữ nguyên.
- Forward → detection loss với batch có ảnh/labels thật từ training split → backward → optimizer update chạy được trên CUDA. Synthetic labels chỉ là bước chẩn đoán bổ sung, không thay real-batch readiness.
- Loss và các components hữu hạn, gradients hữu hạn và có gradient khác 0 ở trainable parameters, optimizer thật sự cập nhật weights trong bộ nhớ. Với AMP, kiểm step không bị bỏ qua do overflow; không chỉ thấy lệnh `step()` được gọi rồi kết luận weights đổi.
- Batch dictionary đúng schema, bbox format/normalization và class IDs. Kiểm nhãn thực sự đi vào criterion; có kiểm chứng hợp lý rằng thay labels trên cùng input ảnh tác động target assignment/loss, không test theo giả định scalar nhất thiết tăng hoặc giảm.
- Không ghi đè checkpoint gốc; hash file gốc trước/sau không đổi. Dùng model copy cho smoke để không đưa trạng thái smoke vào candidate training.
- Đo elapsed time, actual batch/imgsz/AMP setting, peak allocated/reserved VRAM và các giới hạn phép đo; không dùng PyTorch allocated như toàn bộ VRAM tiến trình.

Nếu AMP/loss gặp lỗi, chẩn đoán finite/precision/config trước; có thể thử FP32 trong recipe diagnostic có ghi rõ. Không tự đổi CUDA stack. Test readiness cần fail khi loss không dùng labels, gradients không hữu hạn/không tồn tại hoặc optimizer không cập nhật; không chỉ kiểm một chuỗi status.

Tiếp theo chạy một training pilot ngắn qua **trainer production thật**, với train/validation samples có nguồn gốc rõ và output riêng. Nếu dùng subset để kiểm fit/IO, ghi membership/hash và synthetic/diagnostic scope; không gọi đó là training đầy đủ. Chỉ chuyển sang run dài khi có epoch thực và checkpoint/load-back kiểm chứng được, cùng ước lượng dung lượng/runtime từ phép đo thực.

## 6. Phase C — Fine-tune có giám sát và phục hồi được

Recipe ban đầu để kiểm chứng khả năng chạy: model gốc verified, `imgsz=640`, batch 2, AdamW `lr0=1e-4`, seed 7, workers 0, cache=False, tối đa 30 epochs, patience 10. Đây là cấu hình khởi đầu, không phải bảo đảm vừa VRAM hay đạt chất lượng. Kiểm trainer có tự thay batch/optimizer/AMP/recipe hay không và ghi actual config sau resolve.

Sau pilot, chạy fine-tune trên toàn mixed training set và validation phù hợp. Không chỉ train 49 ảnh bổ sung rồi gọi là mixed fine-tune. Kiểm sampling/augmentation để không vô tình mất lớp hoặc bỏ labels. Nếu thiếu VRAM, giảm batch xuống 1 trong một recipe/run version mới hoặc dùng giải pháp tích lũy gradient được framework hỗ trợ; ghi effective batch/LR thực. Không âm thầm giảm resolution, đổi weights/model family hoặc cherry-pick dữ liệu.

Model selection/early stopping chỉ dùng validation theo protocol; không dùng test để chọn epoch/confidence/recipe. Không yêu cầu mAP phải tăng trước khi lưu artifact hoặc giữ mọi epoch khi dung lượng không cho phép; giữ best/last và checkpoints cần thiết theo policy đã khai báo.

Sửa quản lý job để phản ánh trạng thái thật:

- Có `preflight -> smoke -> pilot -> training -> trained_pending_evaluation -> evaluated`, và `failed/interrupted` với reason; không để `training` bất động khi process đã chết.
- Heartbeat atomic, supervisor/worker identity, epoch/batch progress, last log update, device, checkpoint path/hash, errors và timestamps. Phân biệt process alive nhưng stalled với tiến độ thật.
- Native Windows launcher nếu cần phải chạy `Start-Process -WindowStyle Hidden` với stdout/stderr logs, không phụ thuộc PTY ngắn hạn. Dùng paths được quote đúng, không ghi credentials/signed URLs.
- Checkpoint resume cần tương thích optimizer/epoch/dataset/model/recipe/source snapshot; checkpoint weight initialization và true training resume là hai thao tác khác nhau. Không có checkpoint hợp lệ thì tạo run mới từ model gốc, không giả resume.
- Dùng đường dẫn run mới và snapshot phù hợp để bảo vệ runtime đang dùng. Hash drift phải được giải thích/ghi artifact, không khôi phục code cũ hoặc sửa lịch sử để qua guard. Không tuyên bố full training fail chỉ vì workspace có thay đổi ngoài experiment mà không xác định source ảnh hưởng; thiết kế snapshot/guard đúng phạm vi.

Chứng minh run hoàn tất bằng logs epoch, `results.csv` hoặc artifact metric tương đương của trainer, `weights/best.pt`, `weights/last.pt`, resolved args, checkpoint reload và validation output. Previews `train_batch*.jpg` không thay các bằng chứng này.

Nếu run kéo dài, giữ progress updates ngắn, theo dõi job và tiếp tục các phần độc lập. Không gọi task complete chỉ vì launch thành công. Nếu phải bàn giao khi job còn active, final phải nói rõ epoch/heartbeat/checkpoint hiện có, trạng thái chưa hoàn tất và cách kiểm tra; không bịa số liệu tương lai.

## 7. Phase D — Paired evaluation và bảo vệ downstream

### 7.1. Detector native và runtime thực tế

Đánh giá model gốc và candidate trên cùng inputs/coverage, preprocessing, class map và cấu hình metric. Báo precision/recall/AP50/AP50–95 từng class cùng counts; ưu tiên phân tích ball misses/FP, bóng nhỏ/che khuất/sát rổ và rim/human regressions. Lưu raw predictions để phân tích lại, không chỉ summary scalar.

Validation dùng chọn model. Chỉ dùng test theo freeze/protocol cho evaluation cuối; test cũ đã exposed cần ghi diagnostic scope, không đổi tên thành untouched holdout. Thiếu independent GT thì tạo missing-data/review packet và giữ acceptance pending. Không đem labels/notes/scoreboard vào inference để đạt điểm cao.

`evaluate_task07a_candidate.py` hiện chỉ native detector comparison, chưa chứng minh OCR/pipeline. Nếu cần điều chỉnh script để chọn split an toàn/protocol rõ thì làm trước khi đo. Không dùng native PyTorch candidate đối chiếu application ONNX baseline rồi quy mọi khác biệt cho fine-tune.

Xuất candidate sang backend/runtime hiện dùng trong experiment riêng nếu đủ khả năng môi trường; verify input shape, letterbox/tile transforms, class map, output format, confidence/NMS/postprocessing và parity trên cùng frames. Không tự động tải thêm model assets nếu không cần. Không có adapter/export hợp lệ thì bàn giao native candidate và ghi runtime integration pending, không đổi backend chính để che việc chưa tích hợp.

### 7.2. OCR, ROI, tracking và identity

Giữ nguyên OCR provider/weights, roster, team mapping, ROI/court config và identity thresholds trong paired comparison. Reset tracker/state/cache giữa hai model và bind cache với đúng checkpoint/preprocessing hash; không dùng observations/OCR crops của baseline làm như candidate đã chạy.

Đo và xuất evidence cho:

- Player/human detection coverage, track continuity/ID switches và crop ownership/jersey crop quality.
- OCR invocation coverage, readable-crop coverage, jersey/identity correctness trên approved GT, số sai attribution và unknown. Không dùng riêng confidence OCR làm accuracy.
- Team attribution, identity history/causal availability. Shooter history không đọc bằng chứng tương lai; team-only fallback không tính là strict player đúng.
- ROI adherence và coordinate transforms sau resize/tile, court projection validity, camera-cut boundaries; geometry chưa đủ thì giữ unresolved, không default point value.

Hash cấu hình không đổi chỉ chứng minh cấu hình không đổi; crop/track do model thay đổi vẫn có thể làm OCR xấu đi. Thiếu OCR GT đủ thì báo giới hạn contract/output regression, không tuyên bố “đảm bảo OCR accuracy 100%”. Nếu candidate gây hồi quy, giữ baseline và phân tích nguyên nhân; không giảm threshold theo từng play để sửa số đo.

### 7.3. Task07 control/pass và Task08/11

Chạy các segments/protocol Task07C hiện hành với adapter đúng: `human` cho player tracking, `ball` cho ball tracking, `rim` cho geometry; bảo toàn source PTS, observed/predicted/unknown semantics. Đo ball recall, observed continuity/gaps, strict control accuracy, strict pass recall và camera-cut/false-control violations cùng denominators/GT coverage.

Sửa integration trong phạm vi cần thiết nếu hợp đồng sai. Phân biệt detector miss, selector/tracker miss, crop/identity failure, control/pass heuristic và thiếu GT để không quy mọi lỗi cho model. Nếu control/pass còn lỗi độc lập cần nhiều thay đổi, lập bounded follow-up với reproduction/evidence, không bỏ khỏi báo cáo hoặc gọi Task07 DONE chỉ vì detector tốt hơn.

Chạy downstream Task08 bằng production evaluator đã sửa: event TP/FP/FN, actor/team/value correctness, unresolved geometry và negative diagnostics. Giữ observed crossing/gap guards; không tăng recall bằng prediction-only baskets. Negative cohort còn draft phải giữ official specificity N/A.

Qua Task11 adapter, kiểm event time/confirmation time, one physical shot one score, status eligibility, refinement/void/dependencies, replay/checkpoint và bảo toàn tổng. Candidate model không được làm ledger cộng provisional/unresolved hoặc tạo default points để khớp scoreboard.

## 8. Tests và lệnh khởi đầu

Chạy các kiểm thử phù hợp sau khi sửa implementation; giữ tests có ý nghĩa cho lỗi thực tế:

- Dataset/hash/class/split/approved membership và leakage guards.
- Readiness/config/loss label usage, finite gradients, optimizer update và checkpoint gốc bất biến; GPU integration tests có phân biệt rõ skipped trên máy không CUDA với GPU pass thật.
- Job lifecycle, heartbeat/process identity, failed/interrupted, resume không tương thích và atomic status.
- Runtime adapter/class mapping/preprocessing parity và cache model binding.
- Task08 và Task11 regressions, production evaluator và points-unresolved invariants.

Lệnh baseline từ workspace root trên PowerShell:

```powershell
$env:PYTHONPATH='codebase/src;codebase/scripts'
$env:PYTHONIOENCODING='utf-8'

codebase/.venv/Scripts/python.exe -m pytest codebase/tests/test_task07a_finetune.py codebase/tests/test_task07a_readiness.py codebase/tests/test_task08_temporal_shot_engine.py codebase/tests/test_task08_evaluator.py codebase/tests/test_task11_ledger_and_boxscore.py -q

# Chẩn đoán lỗi actual criterion trước sửa; output path mới phải tồn tại thư mục cha.
# Dùng tên run thực tế của bạn; không ghi đè artifact cũ.
codebase/.venv-train/Scripts/python.exe codebase/scripts/probe_task07a_gpu_training.py --checkpoint codebase/models/checkpoints/task07a-original/best.pt --output codebase/outputs/task07-finetune-recovery-<run-id>/actual-loss-probe.json

# Preflight hiện hữu; không có --execute thì không train.
codebase/.venv-train/Scripts/python.exe codebase/scripts/train_task07a_candidate.py --dataset codebase/data/finetune/task07a/mixed-20261108 --output codebase/outputs/task07-finetune-recovery-<run-id>/candidate-training --epochs 30 --batch 2

codebase/.venv/Scripts/python.exe -m pytest codebase/tests -q
```

Các lệnh chứa `<run-id>` là template, phải thay bằng ID thật trước khi chạy; kiểm `--help`/API sau sửa trước lệnh train/evaluate. Tạo output dir đúng policy của script. Script readiness hiện còn lỗi được phép fail ở baseline nhưng phải lưu traceback. Bổ sung real-batch probe/pilot và test commands sau khi sửa; không chỉ chạy probe synthetic cũ rồi báo đủ điều kiện.

Chỉ thêm `--execute` vào recipe đã preflight/pilot hợp lệ. Ghi actual command, exit code, resolved config và versions. Chạy full suite sau code edits; không lặp toàn bộ suite chỉ vì model có thêm một epoch khi không có source changes hoặc failure mới.

## 9. Bàn giao và quyết định chất lượng

Trong run output mới cần có:

- `run.json`, atomic job status/heartbeat, source/config/environment/input snapshots và command/exit-code logs.
- Dataset QA/membership/provenance/leakage summary, limitations và missing-label inventory.
- Actual loss + real-batch readiness reports, pilot epoch/checkpoint evidence, VRAM/runtime observations.
- Training logs, resolved recipe, results.csv hoặc metrics tương đương, best/last checkpoint hashes và reload result.
- Paired native/runtime detector metrics và raw predictions; classification theo failure/cohort và split exposure.
- Paired OCR/ROI/identity/tracking/control/pass/shot regression report với evidence refs, counts và N/A reasons.
- Tests, export/parity/integration checks, decision `candidate_better / candidate_regressed / inconclusive` theo tiêu chí đã khai báo; tách khỏi `accepted_for_production`.

Tạo `docs/reports/task07-finetune-recovery-20261113.md` và handoff kế tiếp; cập nhật task07/PLAN theo bằng chứng. Không tự đặt Task07 DONE khi thiếu control/pass/identity hoặc validation GT; không giữ claim `training` của job đã chết như trạng thái hiện hành. Không dùng manual corrections thay raw automatic outputs.

Giữ model mặc định hiện hành trong đợt này; bàn giao candidate và phương án tích hợp/rollback cụ thể. Chỉ thay model mặc định trong bước promotion có gate chất lượng và authorization phù hợp; không suy “đã cho phép fine-tune” thành “tự promote dù chưa qua evaluation”. Không hỏi lại quyền train local đã được cho phép.

Final bằng tiếng Việt: phần đã thực thi, checkpoint/run thật, tests và số đo trước/sau, quality gates đã/chưa đạt, OCR/ROI có bằng chứng gì, links report/artifacts và task kế tiếp. Nếu còn thiếu GT/review hoặc job còn active thì nêu rõ; không kết luận demo hoàn tất từ training loss/mAP hoặc tests pass.
