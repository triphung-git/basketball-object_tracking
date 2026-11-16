# Tái nghiệm thu Task06 — tracking/team/identity

2026-11-04. **CORE TOOLING & LOCAL OCR ENGINE READY (160 tests PASS) — Evaluation Benchmark pending dual-team GT footage.**

| Gate | Kết quả |
|---|---|
| G06-T core | **PASS** cho tracker, color evidence adapter, resolver interfaces và regressions |
| OCR provider/runtime | **PASS** (LocalEasyOCRProvider đã tải weights offline CRAFT + Gen2 English ~130MB, đã kiểm tra offline `download_enabled=False`, MockOCRProvider, crop quality validation, CLI wiring) |
| G06-D | **PENDING** cho benchmark metric định lượng; pipeline đã hỗ trợ cấu hình per-video cho trận đấu bất kỳ |
| G56 | **PASS** computational/synthetic; bảo toàn mass, xác minh replay deterministic |

## Sửa lỗi và chức năng thực có

- Tracker retire trước association; không revive stale ID khi thấy bbox giống. Dùng timeout giây, bỏ extra cutoff30frames phụ thuộc FPS.
- Class_name từ runtime quyết định human, không fallback class_id1 khi class_name=ball. Dedup boxes gần trùng; giữ observed/predicted và dimensions source thật.
- ROI chỉ giới hạn không gian, không chứng minh người là player. Trong ROI thiếu role evidence là unknown; ngoài ROI non_player. Nếu có team/player evidence trong ROI, tự động thăng cấp thành player.
- CLI --video kiểm media hash và frame/PTS, lấy torso RGB vào classifier/resolver.
- **Local EasyOCR Engine tích hợp hoàn chỉnh**: Trích xuất crop vùng số áo, kiểm tra độ tương phản/chất lượng, nhận diện ký số áo đấu (0–99), tích hợp vào resolver với multi-frame hysteresis consensus.
- Evidence có TTL 2s, OCR ID dedup, active-roster lookup, conflict handling và snapshot không mutate khi kéo dài view.
- Mapping bắt đầu lúc xác nhận; mapping_at tra cứu lịch sử và ngăn stale evidence kéo qua gap. Predicted/non-player không nhận confirmed identity. Không dùng mapping cuối video gán ngược quá khứ.
- CLI yêu cầu completed source run/approved detector metadata hoặc explicit synthetic diagnostic, kiểm refs/PTS/hash/config và tạo output directory mới.

## Integration local đã chạy

Input G03 verified 1089 frames; source SHA-256:
`3ed25e1b246ccebbe7904d76a22fbea65ebfcb86701499417cd52962f1fc4c26`.

outputs/real-ocr-clip02-eval/:
- 1416 observations: 1100 observed, 316 predicted; 6 tracks initiated.
- Role counts: player 873, non_player 260, unknown 283.
- 900 torso-color evidence records từ video local; score heuristic.
- `ocr_status`: `enabled_easyocr_local`.
- `ocr_provider`: `easyocr` (sampling cadence: 15 frames/track).
- `total_jersey_evidence_count`: 0 (do clip02 là người tập ném áo trơn, OCR không bịa số áo ảo).

Heatmap integration:
- 12.116667s total player occupancy.
- Bảo toàn khối lượng tuyệt đối (`is_conserved: true`).
- `replay_verified: true`.

## Kiểm thử

Suite **160 tests PASS (~27s)**:
- 92 baseline G01–04
- 14 court/heatmap
- 11 tracker/identity (bao gồm test khởi tạo và nhận diện số áo thực tế của `LocalEasyOCRProvider`)
- 2 G56 integration
- 35 regressions core/CLI
- 6 regressions về OCR provider, crop quality, và CLI security

Tests OCR gồm:
- Crop quality evaluation: kiểm tra kích thước tối thiểu ($16\times 24\,\text{px}$) và độ biến thiên cường độ (std $\ge 8.0$), loại trừ crop phẳng/trơn/mờ.
- Local EasyOCR offline security: kiểm tra proactive check không tự ý tải weights và ném `ModelWeightsUnavailableError` nếu weights vắng mặt trên đĩa.
- Local EasyOCR execution: kiểm tra load weights offline và nhận diện chính xác số áo từ crop ảnh (`test_local_easyocr_initializes_with_cached_weights`).
- Mock OCR provider: kiểm tra tạo `JerseyEvidenceRecord`s chuẩn, xác nhận multi-frame consensus hysteresis và giải quyết identity causally.
- CLI OCR execution: kiểm tra `--enable-ocr --ocr-provider easyocr` và mock trong diagnostic mode; kiểm tra từ chối mock trong production.

## Lệnh từ workspace root

```powershell
# Chạy toàn bộ test suite (160 tests):
codebase/.venv/Scripts/python.exe -m pytest codebase/tests/ -q

# Chạy Player Tracking với Local EasyOCR Engine trên video:
codebase/.venv/Scripts/python.exe codebase/scripts/track_players.py `
  --detections codebase/outputs/acceptance-20261102/g03-clip02-verified/detections.jsonl `
  --run-json codebase/outputs/acceptance-20261102/g03-clip02-verified/run.json `
  --court-config codebase/configs/courts/synthetic_half_court.json `
  --roster-config codebase/configs/rosters/synthetic_dual_team_roster.json `
  --video codebase/assets_test/20521993-uhd_2160_3840_60fps.mp4 `
  --allow-uncalibrated `
  --enable-ocr `
  --ocr-provider easyocr `
  --ocr-sampling-cadence 15 `
  --output-dir codebase/outputs/real-ocr-clip02-eval

# Sinh Heatmap tích hợp từ kết quả tracking:
codebase/.venv/Scripts/python.exe codebase/scripts/generate_heatmap.py `
  --court-config codebase/configs/courts/synthetic_half_court.json `
  --detections codebase/outputs/real-ocr-clip02-eval/tracked_observations.jsonl `
  --run-json codebase/outputs/acceptance-20261102/g03-clip02-verified/run.json `
  --allow-uncalibrated `
  --verify-replay `
  --output-dir codebase/outputs/real-ocr-clip02-eval/heatmap
```
