# Task07 — contracts ball/control/pass/possession v2.1.0

2026-11-04. Implementation/fixtures và diagnostic integration đã chạy; chất lượng trận thật chưa được nghiệm thu. Xem [report](../reports/task07-ball-possession.md) và [handoff](../handoffs/task07-to-task08-09-10.md).

## Input và clock

`track_ball_possession.py` nhận detection JSONL + G03 run, player tracking JSONL + tracking run, config, và identity ledger khi có player IDs. Input liên kết bằng SHA-256, source_run_id, video_id và PTS. Observed human bbox phải khớp một source human detection; predicted bbox có thể ra ngoài ảnh nhưng không được làm observed interaction evidence. Empty human log được phép cho ball-only timeline.

Mỗi run xử lý một camera/segment. Nhiều camera/segment trong tracking log bị từ chối; chạy riêng từng phần. Operational cuts/gaps có thể khai báo bằng `--exclusions`:

```json
{
  "source_video_sha256": "<actual source hash>",
  "intervals": [
    {"start_time_s": 5.0, "end_time_s": 5.0, "reason": "cut"},
    {"start_time_s": 10.0, "end_time_s": 12.0, "reason": "replay"}
  ]
}
```

Intervals là [start,end); cả hai boundaries reset state. Interval độ dài 0 là một cut. Không tự phát hiện cut, pan/zoom hoặc replay. Không tự đọc GT coverage làm exclusions. Source PTS valid/repaired được dùng; estimated/irregular tạo missing/unknown và reset. Timestamp trùng/lùi bị input validator từ chối. Không dùng frame/FPS làm event clock.

## BallTracker

`BallTracker(original_wh, namespace, BallConfig).update(frame_index,time_s,detections,segment,reset,clock_valid)`:
- Chọn ball bằng class_name, confidence, vị trí/vận tốc và size gate; dedup bbox gần trùng.
- Các candidates khó phân biệt xuất predicted/missing với reason; không lấy thứ tự bbox làm ID.
- Velocity dùng delta-time của observed samples. Prediction horizon mặc định 0.15s; stale/gap 0.30s, expire trước association.
- Reset/cut tạo ball track ID mới. Coordinates là image pixels, không dùng homography cho bóng đang bay.

`ball_tracks.jsonl`: observation_id, source run/video/hash, frame_index, source_time_s, timestamp_status, camera_id/segment_id, ball_track_id, sample_type (`observed/predicted/missing`), xyxy, center_image, confidence, reason/reset_reason, candidate_count, evidence_refs. Predicted không có observed bbox/confidence. `detection:<frame_index>:<index>` tham chiếu row detection gốc. Association score là heuristic, không phải probability đã calibrate.

## Control và trạng thái

`PossessionEngine(namespace, PossessionConfig).update(ball,observations,rims,reset_reason)` không đọc file, model hoặc GT.

Interaction dùng vùng torso/tay ước lượng từ bbox, khoảng cách chuẩn hóa theo chiều cao người, relative motion và tính liên tục. Đây không phải pose keypoints thật. Controller mới cần ít nhất 3 samples và 0.10s, role=player ở nguồn; unknown role chỉ được làm candidate. Hai contenders có score gần nhau → contested. Predicted ball, controller mất quan sát/role, identity/team đổi mâu thuẫn hoặc gap >0.25s ngắt xác nhận. Không coi mọi human trong ảnh là player.

`ball_control.jsonl`: một row/frame; control_id, frame/clock/source refs, state, certainty (`confirmed/provisional/unresolved`), controller nullable, candidate_actor nullable, possession_id, phase, interaction_score, evidence_refs và reason. Các states: `free`, `loose`, `unknown`, `contested`, `control_candidate`, `controlled`, `pass_candidate`, `shot_candidate`.

Actor snapshot gồm track_id, nullable player_id/team_id, identity_at_s và observation evidence_ref. Confirmed control là xác nhận heuristic ở **mức track**; player_id có thể null. Không đồng nghĩa actor đã đúng danh tính thực. CLI kiểm chứng player_id có nguồn trong event-time identity mapping; không lấy mapping cuối video gán ngược lịch sử.

Dribble thấp gần controller cũ có hold tối đa 0.45s và chỉ provisional, controller field null với previous_controller context. Prediction-only không tự duy trì confirmed control hoặc phát sinh possession/pass. Các ngắt nhỏ vì thiếu detection được xử lý bảo thủ, làm giảm coverage; không giấu các đoạn unknown.

## Pass và possession

`passes.jsonl` ghi các release/flight candidates đã được resolve hoặc unresolved ở EOF/gap:
- pass_id, passer/receiver actor snapshots, release_time_s, receive_time_s, confirmed_at_s;
- status/outcome/reason, observed_flight_samples, contested_seen, bounce_seen, optional shot_suspected;
- pass_kind, ball_track_id, possession_id, source/segment và evidence_refs.

Một completed pass cần flight có ít nhất 2 observed free samples, receiver khác track được xác nhận theo thời gian, hai bên có cùng known team, không phải cùng known player, không có contested hoặc shot-suspected context. Không dùng predicted flight để đạt số mẫu. Actor receiver giữ snapshot khi bắt đầu receiving evidence, không backfill danh tính mới biết lúc xác nhận.

Handoff/control switch không có flight → transition candidate, chưa khẳng định ý định chuyền. Đổi đội, deflection/tranh chấp, unknown team, shot suspicion hoặc timeout → unresolved transfer. Bounce label chỉ là `bounce_candidate` từ đổi chiều y ảnh, không chứng minh chạm sàn thật. Ball tiến lên gần rim có thể tạo shot_candidate; không phải shot made/miss/value hoặc points. Consumer phải xử lý uncertainty, không coi mọi pass candidate là assist.

`possessions.jsonl` là các đoạn **operational observed team control**, không phải quyết định possession chính thức theo luật. Cùng đội qua completed pass giữ ID; đổi đội/unknown, gap/cut hoặc mất bằng chứng đóng đoạn. Start là thời điểm đủ evidence; end là observed control cuối cùng, closed_at có thể muộn hơn. Các đoạn bị fragmentation không được cộng thành số lượt possession/turnover chính thức.

`transitions.jsonl` có event_id, kind, confirmed_at_s, các actor/evidence refs liên quan và effective_time_s khi có. `finish()` đóng candidates còn pending thành unresolved, không suy outcome ngoài footage.

## IDs, outputs và replay

Namespace là digest input fingerprints/config; IDs deterministic trong cùng input bundle. Không dùng tên output directory làm logical ID. Đổi input/config hoặc thêm input export-video có thể đổi namespace vì bundle fingerprints khác. Replay hoàn chỉnh cùng inputs tạo JSONL giống nhau. Chưa có checkpoint persistence cho incremental chunks; chạy lại fresh state từ input đầy đủ, không append vào run cũ.

CLI tạo directory mới và xuất ball_tracks/ball_control/passes/possessions/transitions JSONL, timeline.png, summary.json/run.json. Có `--video` sẽ xuất debug.mp4 giảm kích thước, explicit source PTS, không audio; decode readback kiểm số frame và timestamps. Lỗi sau khi tạo output ghi failed + exception class. Logs không chứa API keys. Diagnostic source hoặc roster/court synthetic cần `--diagnostic`.

Timing core chỉ bao gồm logic với detection/tracks đã có. Total của CLI thêm validation/replay/visualization/export; **không bao gồm detector/OCR**, nên không dùng core FPS để tuyên bố end-to-end real-time.

## Evaluator độc lập

`evaluate_ball_possession.py` đọc outputs và một packet JSON tường minh. Recognition không import evaluator hoặc đọc nhãn. Packet schema `task07-evaluation-1` gồm:
- source_video_sha256; is_synthetic; với real GT: review_status=approved, reviewer, protocol_status=approved, protocol_version;
- coverage: danh sách khoảng fully reviewed không overlap, start_time_s/end_time_s;
- control_intervals: start/end, player_id/team_id; uncertain intervals không chấm;
- passes: pass_id, release/receive_time_s, passer/receiver với player_id/team_id, optional uncertain;
- ball_samples: frame_index/source_time_s, xyxy, visible, optional uncertain;
- pass_tolerance_s và ball_iou_threshold chốt trước đánh giá.

Ví dụ packet được đánh dấu synthetic rõ ràng: `outputs/acceptance-20261104-task07/synthetic-fixture/ground-truth-synthetic.json`. Packet này không phải nhãn clip04 và không được copy thành GT thật.

Control accuracy tính theo thời lượng eligible GT; unknown/missed vẫn trong mẫu số. Left-hold tới sample kế tiếp trong max_gap; không extrapolate sample cuối hoặc nối gap dài. Ball recall chỉ tính observed matching, predicted không tăng recall. Pass matching một-một tối đa cardinality rồi tối thiểu sai số thời gian; event-only tách strict actors. Duplicates không match là FP; sai actor tạo FP/FN. Mẫu số 0 trả null/N/A.

Uncertain pass GT tạo cửa sổ không chấm ±pass_tolerance_s quanh release; số predictions bỏ qua được báo riêng. Không cho eligible GT pass chồng cửa sổ này. Policy phải chốt trước đánh giá thật. Mỗi packet hiện cho một video; chưa có benchmark toàn bộ PRA, confidence intervals hoặc aggregate multi-session của task13.

Evaluator generic để acceptance_pass=null khi không cung cấp profile đã duyệt. Với pilot Vietnam–Tonga, dùng profile riêng được duyệt như revision dưới đây. Syntax/reviewer field validation không chứng minh nhãn được kiểm chứng chuyên môn. Chưa có reviewed ball/control/pass GT cho clip04; metrics thật vẫn N/A.

## Revision Vietnam–Tonga 2026-11-04

Áp dụng cấu hình riêng cho hai đoạn pilot; legacy defaults không tự đổi. [Report](../reports/task07-vietnam-tonga-segments.md), [handoff](../handoffs/task07-vietnam-tonga.md) và [protocol đã duyệt](task07-vietnam-tonga-evaluation.md) ghi phạm vi và các gate còn mở.

- Detector phải nhận confidence threshold trước SDK filtering; tiled ball boxes quy về ảnh gốc, không thay full-frame human evidence bằng tile humans.
- Ball max diameter và observed-human context là gating/association heuristics, không biến candidate thành ground truth. `observed` nghĩa có detector evidence, không phải đã đối soát đúng bóng thật.
- Dribble cần nhiều observed near-floor samples và recent confirmed actor. Gap≤100ms của config pilot chỉ giữ hypothesis; predicted/missing không xác nhận controller. Pass cần observed flight và observed stable receiver; motion-ambiguous contact không tự tính là free flight.
- Operational cut intervals chuẩn hóa start floor/end ceil ở microsecond, reset ở boundary. Không nối qua camera cut. Image ROI chỉ negative filtering, không metric geometry hoặc bằng chứng player.
- Jersey TTL và team TTL độc lập. Masked torso color dựa prototypes roster, ambiguous→unknown. OCR evidence replay phải cùng source/detections/tracker parameters, đúng observed track bbox; không lấy resolved mappings hoặc GT làm OCR readings. Source cache status phải real local OCR completed, không mock.
- Run namespace gắn input/config và hashes `ball.py`, `possession.py`, `ball_pipeline.py`; cùng inputs/code cho IDs ổn định, code revision khác có namespace khác.
- Evaluator nhận profile approved và GT approved riêng biệt. Strict control giữ unknown/missed trong mẫu số; pass sai actor thành strict FP/FN. Minimum60visible ball samples và5GT passes, control seconds>0; thiếu mẫu hoặc N/A không PASS. Cùng trận và outputs đã triage phải công bố exposure, không independent match test.
- Hiện pilot chưa có reviewed GT,0completed passes và identity coverage thấp; contract tools có thể dùng cho fixtures Task08–10, chưa coi real attribution đã nghiệm thu.

