# Code Review — Task05–06

2026-11-03. Review theo requirements và toàn bộ modules/scripts mới; workspace không có Git diff để review theo commit. Các lỗi bên dưới thuộc phần task05–06, không quy lỗi cho baseline v1.

**Verdict**: APPROVE — core tooling sau sửa lỗi; data/geometry/OCR acceptance vẫn pending.
**Confidence**: HIGH cho tests/artifact invariants đã chạy; chưa đánh giá accuracy trận hai đội.

## Summary

118 tests ban đầu pass nhưng bỏ lọt các lỗi P1. Đã tái hiện bằng regression độc lập, sửa core và CLI, chạy153 tests PASS và independent artifact audit. Không có P0/P1 còn mở trong các ca đã kiểm chứng; OCR provider và real-data gates chưa hoàn thành.

## Findings

| Priority | Issue | Location |
|---|---|---|
| P1 — fixed | Predicted samples, invalid gaps, trackless order tạo occupancy giả | heatmap.py:188,288 |
| P1 — fixed | Projection nâng predicted/occluded thành valid; nguồn/config/output không được chặn đúng | generate_heatmap.py:15; spatial_io.py:22 |
| P1 — fixed | Stale ID được match trước retire; class_id fallback và ROI tự gán player | players.py:175 |
| P1 — fixed | Evidence vô hạn/đếm trùng, backfill mapping, mutable snapshots và stale event lookup | identity.py:358,452 |
| P1 — fixed | Synthetic calibration bypass production, empty ROI=whole frame | court.py:514 |
| P1 — fixed | Classifier load nhưng không có video color evidence đi tới resolver | track_players.py:20 |
| P2 — fixed | Exclusions overlap trừ hai lần; replay counters tăng lặp | heatmap.py:188,288 |
| P2 — fixed | Origin/landmark guide, OCR size/latency/runtime và readiness claims thiếu evidence | guides/court-calibration.md; decisions/20261103-ocr-model-evaluation.md |

## Details

### [P1] Occupancy không bảo toàn ý nghĩa quan sát

Trước sửa, filter bỏ invalid observations rồi nối hai đầu còn lại; sample_type được nhận nhưng không kiểm, trackless records chung stream. Tổng grid có thể vẫn “conserved” dù dữ liệu không hợp lệ.

Fix: giữ barriers trong namespace đầy đủ; hai endpoints observed/valid, stable track và role policy; cut/gap ngắt; trackless mass0; union exclusions. Tests gồm prediction, invalid middle, non-player, multi-source/calibration, replay và independent interval summation.

### [P1] Adapter làm mất validity hoặc nguồn gốc

Projection trước đây gán validity=valid cho predicted point khi nằm trong ROI; scripts dùng exist_ok=True và thiếu source/dimensions/clock validation.

Fix: chỉ tính lại geometry status, giữ sample/visibility status; shared source loader kiểm metadata/hash/frames/holdout; new directory và sanitized failed metadata. CLI negative cases xác nhận đúng guards và không overwrite.

### [P1] Tracker/identity assignment có thể vượt evidence

Stale tracks được association trước timeout; numeric class fallback nhận ball thành human nếu order khác; ROI nhận staff thành player. Identity votes không expiry/dedup, mapping mới bắt đầu từ end cũ và lookup cuối video có thể gán ngược lịch sử.

Fix: expire-before-association, class_name, role unknown, TTL2s/ID dedup, roster-active lookup/conflicts, mapping start ở confirmation, snapshot copy và event-time mapping_at có evidence validity window. Tests gồm sparse gaps, refreshed TTL, duplicate OCR, no-backfill và higher-confidence duplicate conflict.

### [P1] Synthetic và classifier readiness bị hiểu quá mức

Synthetic được production guard bỏ qua; classifier tạo object nhưng CLI không feed RGB. Điều này khiến lệnh thành công mà chưa chứng minh đường phân đội chạy.

Fix: synthetic cần explicit diagnostic; --video cung cấp torso RGB và evidence logs. Tiny real-video fixture kiểm RGB→resolver. OCR provider vẫn chưa nối; không giả OCR readings hay nâng G06-D.

## Recommendation

Bàn giao core contracts/tooling cho phần task07 độc lập. Giữ task05/task06 IN_PROGRESS; cần real landmarks/GT, footage hai đội/roster/role evidence và quyết định OCR trước real attribution acceptance. Không dùng synthetic heatmap hoặc heuristic scores thay accuracy.

Chi tiết tests/commands/artifacts: [biên bản nghiệm thu](task05-task06-acceptance.md).
