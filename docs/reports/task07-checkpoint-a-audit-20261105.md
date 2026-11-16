# Task07 Checkpoint A — audit and bounded review batch

Đã nhận JSON người dùng và xử lý hai xác nhận bổ sung: [kết quả tiếp nhận](task07-checkpoint-a-reviewed-20261105.md),278tests PASS. Các đoạn waiting-for-labels bên dưới là snapshot trước khi nhận. Dữ liệu mới gồm9approved,2skipped,1uncertain và14crop reviewed;40approval cũ được bảo toàn. Chưa nghiệm thu accuracy hoặc train.

Cập nhật UI2026-11-05: run-08 đã có giao diện tiếng Việt đơn giản, import/autosave và sửa bbox. Dùng [hướng dẫn mới](../guides/task07-checkpoint-a-simple-review.md) và [report kiểm thử34browser checks](task07-checkpoint-a-review-ui-20261105.md). Source/manifest và scope12frame/14crop giữ nguyên. Mô tả GIF/UI cũ bên dưới là lịch sử; trang mới dùng video WebM có controls và lưu nháp khi trình duyệt cho phép.

**Status:** Checkpoint A audit and packet preparation complete; waiting for human labels. Task07 remains **IN_PROGRESS**. No detector, tracker, OCR, roster, weights, GT, or split was changed.

## Source and artifact integrity

- Main source `vietnam-tonga.mp4`: SHA-256 `1443c1d263c8037a5684f3dbc0ef9216beb5097d9a47c4c1c9b94d1363e26865`; H.264, 1920×1080, 30 fps, 41,432 frames, stream time base `1/15360`.
- The 359-image pilot and its image hashes/PTS were checked against the source. Its sampling audit records one exact duplicate at 743s (`pilot_0142`); that duplicate was not re-added or labeled negative.
- The corrected-v2 review snapshot is hash-bound in the final manifest. It still contains 40 approved images and 319 unreviewed images. The 40 approved labels (360–405s, all in `vt_pilot_06m`) are reused; the source packet, corrected-v2 labels, GT, and split remain untouched.
- The 30-second identity clip hash is `8fd370b0668860a5c70d56bf256c76e3783bc1fe6598b529944ad00ca0616b45`. Source-frame correlation verifies `parent_time_s = 300 + segment_time_s` at all 14 selected crop times; minimum downsampled grayscale correlation was 0.999912. The crop-preparation manifest says `gt_read=false` and `ocr_calls=0`. The OCR values shown in the packet are separate historical evidence from `development-tracking-v2`, not new OCR calls.
- No replay was verified from an isolated still. Uncertain close-ups, transitions, graphics, and late-game frames remain unreviewed rather than being marked skipped or background by assumption.

## Confirmed diagnosis from existing artifacts

The table below is the existing 40-image diagnostic after the user-confirmed correction to `pilot_0017`; it is not an independent benchmark or acceptance result.

| Profile | TP / FP / FN | Precision | Recall | Interpretation |
|---|---:|---:|---:|---|
| Raw ball candidates | 19 / 83 / 14 | 18.6% | 57.6% | 14 of 33 visible-ball labels have no matching raw candidate. |
| Confidence top-1 | 13 / 27 / 20 | 32.5% | 39.4% | One candidate per image lowers recall. |
| Existing context selector | 13 / 16 / 20 | 44.8% | 39.4% | Fewer false selections than top-1, but no recall gain. |

Across those 40 images there are 102 raw candidates, 33 visible-ball labels, and 7 no-ball-visible labels. Of the 19 labels matched by raw candidates, 6 are not recovered by the context selector. The 83 unmatched boxes are not automatically training negatives; their causes have not been adjudicated as a class-balanced hard-negative set. `pilot_0017` is one confirmed knee false label, removed by the user-confirmed corrected-v2 packet. The available measurements do not count shoulder/logo/poster/background error types separately.

The continuous development baseline remains **36/72 observed recall (50%)**. Prediction-only samples are not counted as observed. The strict controller metric of 0% is not an OCR accuracy estimate.

### Identity findings are hypotheses, not accuracy claims

There is no independently reviewed OCR, team, jersey, identity, ID-switch, or fragmentation benchmark. The selected crops target concrete disagreements: track 2 reads `2` then `09`; track 4 has alternatives `4`/`3`; track 41 changes from `18` to `6` within 0.5s; track 59 changes from `3` to `5` within 0.33s; crop 0136 has no recorded OCR read. These are review questions, not confirmed OCR or tracker errors. Team evidence is a heuristic score, not a probability. No player name or roster identity is prefilled.

## Scene triage and review budget

| Window | Triage | New frames | Decision |
|---|---|---:|---|
| `vt_pilot_06m` (360–419s) | Mixed wide play and tight broadcast views; medium confidence | 0 | Reuse the 40 existing approvals. The remaining 20 source samples stay unreviewed. A close-up is not automatically called replay. |
| `vt_pilot_09m` (540–599s) | Wide-play moments with a cutaway elsewhere; medium confidence | 6 | Review two short 3-frame motion clusters at 540–542s and 570–572s. |
| `vt_pilot_12m` (720–779s) | Mixed close-up and wide court; restart/pause at 740s uncertain | 3 | Review 740–742s with a clip. Standing players are not treated as out of scope. |
| `vt_pilot_15m` (900–959s) | Tight framing transitions to wide court near 920s; medium confidence | 3 | Review 920–922s with a clip before deciding scope. |
| `vt_pilot_18m` (1080–1139s) | Mixed close-ups, graphics, and wide-court views; low confidence | 0 | Not selected for this bounded batch; every sample remains unreviewed. |
| `vt_pilot_20m` (1200–1259s) | Late tight court-side/celebration-like views; low confidence | 0 | Not selected; insufficient evidence to label the whole window post-game or replay. Every sample remains unreviewed. |

The final scene manifest records a disposition, source PTS, and image hash for every pilot sample: 40 reused approvals, 12 selected for new review, and 307 still unreviewed. The three consecutive-frame clusters are limited to cases where motion or candidate persistence matters. The 12 new frames are below the 24-frame hard cap; the 14 identity crops are within the 12–16 target. The remaining 190 identity crops are not marked skipped.

## Packet and validation

Final, valid output is [task07-checkpoint-a-review-20261105-run-08](../../codebase/outputs/task07-checkpoint-a-review-20261105-run-08/):

- [Offline review page](../../codebase/outputs/task07-checkpoint-a-review-20261105-run-08/review.html) — raw boxes and OCR/team predictions are visually distinct and read-only; user annotations start unreviewed. Unsaved field edits and drawn boxes remain `needs_review` drafts while navigating.
- [Review manifest](../../codebase/outputs/task07-checkpoint-a-review-20261105-run-08/review-manifest.json) — source hashes, image hashes, PTS, candidates, selector availability, crop evidence, and nine short context clips.
- [Scene manifest](../../codebase/outputs/task07-checkpoint-a-review-20261105-run-08/scene-manifest.json) — per-sample reuse/selection/unreviewed decisions and exact-duplicate audit.
- [Initial review packet](../../codebase/outputs/task07-checkpoint-a-review-20261105-run-08/review-packet.json) — draft only; it is not a label approval.
- [Source clips](../../codebase/outputs/task07-checkpoint-a-review-20261105-run-08/clips/) — four 7-second ball-context clips and five 7-second identity-context clips, with 640×360 animated GIF previews and full-rate WebM downloads. All 18 files start at the declared source PTS. Full-rate clip minimum downsampled correlation is 0.997769; GIF-preview minimum is 0.911370 due to resizing and palette quantization.
- Existing [unmatched-ball contact sheet](../../codebase/outputs/task07a-reviewed-feedback-20261105/unmatched-contact.jpg) remains the preview of previously observed misses; the new page overlays raw candidate evidence for the 12 pending frames.

Open the review page locally. For each frame, choose scene/scope/visibility, draw only user-verified boxes, or save as needs-review. For each identity crop, review crop ownership, number visibility, actual number (optional), team, role, and track association. Unknown is valid; do not snap a number to the roster. Export the JSON and keep it beside the unchanged `review-manifest.json`.

Browser smoke tests confirmed that frame scene/scope/visibility, notes, a drawn box, and identity labels/notes persist across navigation as `needs_review`. The UI smoke-test edits were not exported; reloading the page restores the original unreviewed draft. The review-page GIF preview loaded in the integrated browser; full-rate WebM files remain available for external playback.

Validate a returned export from the codebase root:

```powershell
.\.venv\Scripts\python.exe scripts\validate_task07a_checkpoint_a_subset.py `
  --reviewed outputs\task07-checkpoint-a-review-20261105-run-08\task07-checkpoint-a-review.json `
  --manifest outputs\task07-checkpoint-a-review-20261105-run-08\review-manifest.json
```

The validator checks manifest/source hashes, scope, PTS/image binding, bbox bounds, scene/visibility consistency, identity crop binding, prediction/label separation, and unresolved statuses. It reuses the 40 prior approved IDs and reports `training_authorized=false`. Do not mark the remaining 307 frames or 190 crops skipped to pass validation.

The first generated folder, `run-01`, is explicitly `superseded_invalid` because identity preview clips had the parent offset applied twice. `run-02` was superseded by `run-03` to add per-sample disposition and duplicate audit. `run-04` fixed draft persistence; `run-05`/`run-06`/`run-07` were intermediate media-preview trials (`run-06` failed its timed palette-generation attempt). `run-08` is the tested final packet with animated GIF previews and downloadable full-rate WebM clips. Use **run-08 only**.

## Baseline and experiment record

| Trial | Existing measured result | Decision |
|---|---|---|
| Current continuous development | 36/72 observed recall (50%) | Keep as baseline; below Task07 gate. |
| Confidence 0.10 | 42/72 candidate recall; 29/72 observed recall | Regression in observed recall; do not promote. |
| Ball tile upscale 1.5× | 31/72 observed recall; about 3.3× latency | Regression/cost tradeoff; do not promote. |
| Earlier square-960 probe | 39/72 candidate matches versus 41/72 baseline | Regression; do not promote. |
| Earlier letterbox-640 probe | 18/72 candidate matches | Regression; do not promote. |
| Checkpoint-A run | Reused the approved ONNX/CPU detector suggestions; no new model inference or algorithm ablation | Data review only; no performance claim or configuration promotion. |

## Handoff and decision

- **Promote:** no detector, selector, ROI, continuity, OCR, or identity configuration from this checkpoint.
- **Keep disabled:** optional actor-continuity trial remains off; do not treat sparse 1Hz samples as tracking.
- **Next dependency:** user review of these 12 frames and 14 crops. After return, validate and preserve prior labels, then continue bounded detection and identity diagnosis. Do not start label-dependent tuning before the relevant labels exist.
- **Training/weights:** not included in the existing dataset-first approval; no training, fine-tuning, weight replacement, or paid job was run or requested.
- **Acceptance:** Task07 remains **IN_PROGRESS**. Tools/tests passing and improvements in two subcomponents do not satisfy the full Task07 protocol. The same-match pilot is not an independent test.
