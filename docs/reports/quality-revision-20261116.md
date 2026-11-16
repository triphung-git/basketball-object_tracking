# Triển khai revision Quality Gate — 2026-11-16

**Trạng thái: evaluator revision đã kiểm thử; inference 0–1000s đang chạy nền; fine-tune mới PENDING_LABEL_REVIEW; chưa nghiệm thu 06A.**

## Thay đổi

- [Quyết định revision](../decisions/20261116-quality-protocol-revision.md): basket-primary là phương án được chọn từ yêu cầu người dùng; profile cũ giữ nguyên và báo song song.
- `evaluator_v2.py`: thực thi flag `require_both_release_and_basket` vốn trước đây chưa được dùng; basket-only hard window khi tắt, strict attribution giữ nguyên. Kiểm tolerance finite/nonnegative và explicit video identities khi matching cả PTS/REB/AST. Canonical GT point values được đọc từ shot_type + rules của dataset, không yêu cầu cột point_value không tồn tại.
- `evaluation_scope.py` và CLI `evaluate_v2.py --evaluation-scope`: normalized source timeline, clip offsets, source-hash/processed-coverage validation, audit records bị loại do ngoài scope; không đếm nhãn nguồn khác vào mẫu số cùng clip. Scoped evaluation thiếu coverage metadata phải fail rõ.
- Continuous orchestration có progress callback và source coverage thực; CLI có start/end source timestamps. Sửa `--serve` dùng `run_dir` đúng API dashboard thay `data_dir` không tồn tại.
- `run_quality_recovery_20261116.py`: preflight media/hash/scope, chỉ dùng các canonical records có approved reviews; prepare near-rim draft packet, lưu source snapshot/heartbeat và chạy model approved trên video nguồn. Khi inference hoàn tất, script tự đánh giá hai protocols vào output riêng, giữ default model và historical 06A.

## Bằng chứng đã chạy

Từ `codebase`, interpreter `.venv/Scripts/python.exe`:

1. Target suite: `tests/test_quality_recovery_20261116.py`, evaluator 03A, orchestration 02B, stream 02A và CLI validation: **47 passed**. Logs/JUnit: `outputs/quality-revision-20261116/target-tests.*`.
2. Full suite lần đầu: 483 pass, 2 fail, 1 skip. Hai failures do tests dashboard/benchmark dùng đường dẫn tương đối `codebase/outputs/...` khi cwd đã là codebase; sửa path neo theo test file, giữ nguyên assertions.
3. Full suite sau sửa: **485 passed, 1 skipped, 61 subtests passed, 6 warnings, 41,53s**. [Log](../../codebase/outputs/quality-revision-20261116/full-suite-verified.log), [JUnit](../../codebase/outputs/quality-revision-20261116/full-suite-verified.xml).
4. Preflight/source extraction đã chạy thành công: [preparation](../../codebase/outputs/quality-revision-20261116/preparation-01/preflight.json). Source thật dài 1381,0667s; normalized approved rows có 16 shot records (14 made + 2 miss), 2 rebounds và 1 assist.
5. Re-evaluate historical development predictions trên đúng clip scope 0–28,5333s, không phải GT toàn trận: [comparison](../../codebase/outputs/quality-revision-20261116/existing-clip-comparison/comparison.json). Original detection PTS TP=0/FP=1/FN=1; basket-primary TP=1/FP=0/FN=0. **Strict PTS TP vẫn 0** do player attribution chưa xác định; REB 0/2; AST ở scope clip này không có GT. Một sample không chứng minh generalization hoặc đạt quality gate.

## Run đang chạy

Launch từ `codebase` bằng Start-Process cửa sổ hidden, Python `.venv/Scripts/python.exe -u`:

```powershell
.venv/Scripts/python.exe -u scripts/run_quality_recovery_20261116.py --output outputs/quality-revision-20261116/full-match-01 --execute
```

Không chạy lại lệnh đó khi job còn hoạt động. Output cũ bị từ chối overwrite.

- [Heartbeat/status](../../codebase/outputs/quality-revision-20261116/full-match-01/status.json): trạng thái/PID/frame/time/elapsed/ETA thực, cập nhật mỗi 30 frame.
- [Stdout](../../codebase/outputs/quality-revision-20261116/full-match-01.stdout.log), [stderr](../../codebase/outputs/quality-revision-20261116/full-match-01.stderr.log).
- [Preflight run](../../codebase/outputs/quality-revision-20261116/full-match-01/preflight.json), [source snapshot](../../codebase/outputs/quality-revision-20261116/full-match-01/source-snapshot.json).
- Khi hoàn tất sẽ có `video-run/run.json`, trace/event/ledger bundle, `original-protocol/`, `basket-primary-revision/` và `protocol-comparison.json`. Đây là outputs dự kiến, chưa coi là đã có lúc viết report.

Đã kiểm heartbeat đang `inference_running`, vượt 240 frames trên video thật, stderr không có lỗi tại thời điểm kiểm. PID trong status là worker thực; process launch có thể là Python launcher cha. Muốn audit process, so PID + command/executable + heartbeat freshness, không chỉ tên python.exe. Không cam kết assistant tự monitor sau lượt này; script đã có tự đánh giá sau inference và lưu status cuối nếu tiến trình không bị máy tắt/sleep hoặc lỗi runtime.

## Phần còn thiếu và giới hạn

- [Gói 8 frame near-rim cần review](../../codebase/outputs/quality-revision-20261116/full-match-01/near-rim-review/README.md), [packet](../../codebase/outputs/quality-revision-20261116/full-match-01/near-rim-review/packet.json). Cần bbox/visibility có evidence và đủ labels ball/human/rim trước khi tạo dataset train bổ sung. Training được yêu cầu nhưng **chưa bắt đầu**, không chạy lại recipe cũ để giả giải quyết domain mới.
- Continuous path hiện còn incomplete OCR/player attribution và heatmap accumulation; run không dùng calibration chỉ validated cho clip development áp sang toàn broadcast. Không fabricate coordinates/point values khi geometry không đủ. Do đó chỉ sửa matcher và mở coverage chưa bảo đảm strict PRA PASS.
- Sparse event labels ngoài coverage reviewed không đủ phân loại toàn bộ background FPs trên video dài. Same-match exposed run chưa phải test độc lập; test split hiện vẫn cần xét theo protocol.
- Benchmark cũ có timings fallback/default: không dùng FPS đó làm dự đoán thời gian của full run hoặc evidence realtime. Run này có elapsed/progress thật.
- State legacy `remaining-tasks-20261115/execution-state.json` đang malformed JSON; không rewrite lịch sử đó trong đợt này. Run mới có state JSON riêng hợp lệ, task 06B vẫn chưa được mở.
