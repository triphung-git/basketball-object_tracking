# Prompt 01 — CLI → Rebound → Assist

Bạn là kỹ sư Python/CV phụ trách thực thi đợt 01. **Làm lần lượt 01A → 01B → 01C, hoàn tất checkpoint từng task trước khi mở task kế tiếp.** Đọc và tuân thủ [execution-contract.md](execution-contract.md). Sửa code, chạy tests và chạy thử thực tế; không chỉ viết kế hoạch. Không triển khai đợt 02 trong lượt này.

Đọc thêm source/tests tương ứng, `docs/tasks/task09.md`, `task10.md`, `task11.md`, `task15.md`, contracts/rules v2 và reports Task08 ngày 12/11, Task11 ngày 11/11. Mục tiêu là khôi phục correctness, chưa tuyên bố có continuous pipeline hoặc quality PRA đạt chuẩn.

## 01A — Sửa entrypoint demo và input/output validation

Điểm vào: `run_demo.py` ở root, `codebase/scripts/run_demo.py`, `run_task08_temporal_shot_engine.py`.

1. Tái hiện CLI crash `unexpected keyword argument 'is_play_006'`. Đồng bộ caller với API production hiện tại; không đưa lại GT hints từ `play_006`, danh sách FT hoặc metadata review.
2. CLI phải phân biệt rõ chế độ diagnostic cache replay với video analysis. Trong đợt này chưa có continuous pipeline: chọn mode/name/summary giúp người dùng thấy đúng điều đó; không in “full pipeline” khi chỉ replay cache. Chế độ video chưa có phải báo unsupported rõ thay vì fallback ngầm sang cache.
3. Validate source/roster/cache/config, required files, source/model/config binding nếu dùng cache; cache legacy thiếu binding phải có migration/diagnostic path minh bạch. Input sai fail trước khi tạo kết quả completed. Không mặc nhiên “verified” khi source missing.
4. Không dùng `play_001..010` như danh sách reviewed windows mặc định nếu manifest thực có IDs khác; đọc inventory/manifest có provenance. Liệt kê processed/skipped/invalid windows và lý do.
5. Output directory mới, không overwrite; failed/partial/completed phản ánh thực tế. Các exports ledger/checkpoint/audit hiện có phải giữ đúng.

Tests bắt buộc: CLI qua subprocess thật; valid diagnostic run, missing video/roster/cache file, cache/source mismatch, output đã tồn tại, no-events; kiểm không còn GT hints ở call path. Tests API và full suite theo quy trình chung.

Real-run: replay cache development hiện có qua root entrypoint; kiểm manifest windows, events/boxscore/checkpoint/raw replay identity và scope diagnostic. Không bịa event khi upstream không nhận diện được.

**Gate 01A:** hết crash; positive/negative CLI cases đạt đúng exit/status; raw exports hợp lệ và scope trung thực; tests + report + handoff đầy đủ. Chỉ sau đó mở 01B.

## 01B — Rebound eligibility và sustained control

Điểm vào: `codebase/src/basketball_scoreboard/rebounds.py`, `events.py`, `tests/test_task09_rebounds.py`.

1. Rebound chỉ bắt đầu từ eligible missed shot theo rules. `unknown`, `unresolved`, `not_a_shot`, made hoặc shot chưa đủ eligibility không tạo auto-confirmed rebound.
2. Thêm shot-kind/FT-series applicability vào contract; phân biệt field goal, final/non-final FT và context không đủ bằng chứng. Không tự xác lập rule mới khi nguồn chưa duyệt; ambiguous giữ unresolved.
3. Sustained control yêu cầu observed evidence có confidence và liên tục theo source PTS. Chặn predicted-only, duplicate/nonmonotonic, gap dài, cut/replay/dead-ball và đổi actor. Số frames hoặc duration riêng không được làm hai quan sát rời rạc thành sustained control.
4. Giữ OREB/DREB/team/unknown đúng nghĩa và causal link đến missed shot. Một physical miss không tạo hai rebounds; event revision/void và raw replay không làm sai totals. Nếu parent miss chưa thuộc ledger contract, tạo migration rõ; không giả made-score parent để thỏa dependency.

Chạy probe subset từ `codebase` với `PYTHONPATH=src;scripts`:

```powershell
.venv/Scripts/python.exe -m pytest outputs/acceptance-demo-20261110/test_acceptance_requirements.py -q -k 'rebound or isolated_controls or ft_series' --tb=short
```

Thêm regression vào `tests` với positive/negative observations độc lập, rule/FT boundaries, actor switch, observed-vs-predicted và replay/idempotency. Chạy tests mục tiêu + full suite. Chạy development control/shot artifact nếu đủ binding; nếu không có eligible sequence thật, báo real-data limitation và xuất synthetic diagnostic riêng để chứng minh contract, không tuyên bố recognition accuracy.

**Gate 01B:** sáu rebound probes của snapshot được giải quyết bằng hành vi production đúng; các case dương thực sự tạo đúng event; integration ledger/raw replay và tests pass; output/report/handoff có đầy đủ. Chỉ sau đó mở 01C.

## 01C — Assist pass/action/chain và dependency correctness

Điểm vào: `assists.py`, `events.py`, `tests/test_task10_assists.py`, contracts/rules đã duyệt.

1. Require eligible confirmed made score và pass/control evidence hợp lệ; receiver phải được xác định và khớp scorer, cùng possession, passer khác scorer và cùng đội. Low-confidence/candidate/unknown pass không được tự confirmed.
2. Enforce `require_direct_shot`, `allow_dribbles` và action evidence theo profile; thiếu action evidence cần thiết thì unresolved, không đoán từ “last pass trong 4s”. Không hard-code số dribble như luật chính thức nếu chưa có profile duyệt.
3. Break chain với turnover, deflection, loose ball, cut/replay, possession reset, rebound và các case rule profile bắt buộc; kiểm thời gian/ordering và boundaries.
4. Assist lifecycle bám parent eligibility/team/scorer/void; dependency revision, late arrival và replay không để assist không hợp lệ được cộng. Giữ invariants core Task11 đã có.

Chạy riêng probes `-k 'assist_requires or assist_chain or assist_checks'`, tests assist/ledger, full suite. Positive chain phải tạo được assist; không sửa bằng cách từ chối mọi input. Thử ledger ingestion → boxscore → parent revision/void → checkpoint/reload; kiểm totals và evidence links độc lập.

**Gate 01C:** sáu assist probes snapshot và positive/negative chain tests PASS; đầy đủ logs, event/audit/checkpoint/boxscore artifacts, report và handoff. Cuối đợt chạy lại combined 12-defect probe subset nếu shared-code thay đổi sau 01B. Nếu không có thay đổi ảnh hưởng thì tái sử dụng bằng chứng đã có, không lặp full suite vô ích.

Bàn giao chung chỉ rõ 01A/B/C riêng biệt, API adapter/migration và command chạy thực tế; đưa điểm vào đợt 02, không tự chạy đợt 02. Task09/10 toàn sản phẩm vẫn IN_PROGRESS nếu chưa có real-data P/R.
