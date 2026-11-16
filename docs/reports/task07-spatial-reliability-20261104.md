# Task07 — giảm ball background và kiểm tra OCR/identity

2026-11-04. Người dùng phản ánh bóng bị detect ngoài sân và identity thấp. Đã sửa luồng spatial filtering và OCR consensus, thử nghiệm chỉ trên development, **240 tests PASS**. Candidate development v4 có ball recall50% thay43.06%; strict control/pass recall vẫn0%. **Task07 IN_PROGRESS, chưa đạt nghiệm thu.**

## Nguyên nhân xác định từ code và artifacts

- `track_players.py` áp `image_roi_normalized` cho footpoint của người; ball pipeline trước đó chỉ đọc cut intervals và bỏ qua spatial ROI cho ball. Candidate trên poster/khán đài vẫn có thể đi vào association.
- Ball context là soft score và acquisition gate theo bbox người, không chứng minh candidate là bóng thật. Khi active, kinematic gate cũng có thể tiếp tục một track sai. Người/poster bị nhận nhầm bên trong vùng sân còn có thể hỗ trợ nhầm context.
- OCR consensus trước đây lấy số có weighted votes cao nhất rồi mới kiểm tra roster, chưa chặn đủ phiếu gần hòa. Số ngoài roster có thể che mất số hợp lệ. Đọc thiếu chữ số hoặc track fragmentation vẫn có thể làm sai identity dù có consensus.
- Strict control0% không phải phép đo OCR character accuracy. Nó yêu cầu đồng thời đúng ball/control/team/player tại event time. Pilot chưa có benchmark OCR crops độc lập để kết luận OCR accuracy cụ thể.

## Code đã sửa

1. Thêm optional `ball_image_roi_normalized` gắn với source hash. Ball ROI là vùng tìm kiếm ảnh có cả không gian bóng bay, tách khỏi footpoint ROI của người. Không dùng polygon mặt sân để cắt mọi bóng ở trên không.
2. Loại candidate ngoài ball ROI **trước association**, nhưng giữ nguyên detection index gốc để evidence refs truy đúng raw cache. Ghi `spatially_rejected_candidates`; prediction cũng không được xuất tọa độ ngoài vùng này.
3. Gắn `tracking_policy.py` vào implementation fingerprint/namespace. Source/hash, cuts, observed/predicted/missing và prediction-only guards vẫn được kiểm tra.
4. Identity chỉ cộng phiếu các số có thật trên roster của đội đã resolve; giữ unknown khi hai số hợp lệ có tổng phiếu gần nhau. Không dùng vị trí, tên từ annotation hoặc GT để điền danh tính.

Đây là sửa postprocessing/consensus, **không train lại detector hoặc OCR**. Giữ nguyên model được duyệt, ONNX CPU và raw detection cache; không upload video hoặc thêm dependencies. OCR dùng lại cache thật đã xác minh source/tracker/observed bbox,0fresh OCR calls. Các nguyên nhân như số áo quá nhỏ, quay lưng/nghiêng, che khuất, mất track hoặc read sai chữ số chưa được giải quyết chỉ bằng consensus.

## Các lượt thử và kết quả

ROOT: `codebase/outputs/task07-vietnam-tonga-segments-20261104/`. Nhãn chấm giữ nguyên `codebase/data/matches/vietnam_tonga/reviewed-vt_development-v2.json`; tất cả72visible/certain samples vẫn trong mẫu số, không loại mẫu để tăng điểm.

| Lượt | Ball observed frames | GT ball matches /72 | Ball recall | Strict control | Pass recall |
|---|---:|---:|---:|---:|---:|
| Baseline masked |514|31|43.06%|0%|0%|
| Spatial v3, ROI đầu |441|29|40.28%|0%|0%|
| Spatial v4, aerial ROI rộng hơn + acquisition0.2height |475|36|50%|0%|0%|

V3 loại nhầm6GT centers ngoài ROI, giảm recall; giữ nguyên kết quả, không coi là bản cải thiện. Sau triage nguồn, v4 mở rộng vùng aerial/camera pan và siết acquisition quanh bbox người. V4 không loại tâm của72GT visible samples khỏi vùng tìm kiếm; điều này chỉ đúng trên đoạn đã đo, không chứng minh polygon phù hợp mọi cảnh/video.

Đã chạy sensitivity development cho acquisition distance0.2/0.35/0.5/0.75 trên ROI v3, giữ [toàn bộ kết quả](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/spatial-development-ablation-v3/results.json). V4 là cấu hình phát triển đã tune trên đoạn này, **không untouched validation**. Không áp v4 sang đoạn khác để báo test tổng quát.

Đối chiếu cùng vùng v4: baseline có121observed frames ngoài vùng khai báo; v4 có0,437ball candidates bị lọc. Đây là tính chất spatial guard, **không phải false-positive precision hoặc bằng chứng0false balls ngoài sân thật**. Polygon vẫn chứa một số background và có thể bỏ sót pha hợp lệ ở cảnh khác. Trong72visible GT samples, baseline có18observed không khớp IoU0.30, v4 còn13; các mẫu còn lại gồm matched/predicted/missing. Vẫn có detection/association sai bên trong ROI.

Identity replay có859observations gắn player_id, bằng baseline; counts không chứng minh đúng và không cho thấy cải thiện OCR thực tế. Strict control0%, completed passes0, precision N/A. Thresholds nghiệm thu không đổi; evaluator v4 vẫn `failed_criteria`.

## Artifacts để xem và tái chạy

- [Video debug v4](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/development-spatial-v4/debug.mp4).
- [Full evaluation v4](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/development-spatial-v4-evaluation/evaluation.json).
- [Spatial audit và so sánh](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/development-spatial-v4-evaluation/spatial-audit.json).
- [Player/OCR replay v3](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/development-tracking-roster-v3/run.json).
- [Policy v4](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/vt_development-policy-ball-roi-v4.json), [control config riêng](../../codebase/configs/ball-possession-vietnam-tonga-spatial.json).
- [Tests240PASS](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/tests-spatial-v3.json), [log](../../codebase/outputs/task07-vietnam-tonga-segments-20261104/tests-spatial-v3.log).

Player replay dùng policy v3; policy v4 chỉ đổi ball ROI, còn player ROI/cuts giữ nguyên. Có thể tái dùng player replay này. Không ghi đè output cũ:

```powershell
codebase/.venv/Scripts/python.exe codebase/scripts/track_ball_possession.py --detections codebase/outputs/task07-vietnam-tonga-segments-20261104/development-tiled/detections.jsonl --run-json codebase/outputs/task07-vietnam-tonga-segments-20261104/development-tiled/run.json --tracks codebase/outputs/task07-vietnam-tonga-segments-20261104/development-tracking-roster-v3/tracked_observations.jsonl --tracking-run codebase/outputs/task07-vietnam-tonga-segments-20261104/development-tracking-roster-v3/run.json --identity-mappings codebase/outputs/task07-vietnam-tonga-segments-20261104/development-tracking-roster-v3/identity_mappings.json --exclusions codebase/outputs/task07-vietnam-tonga-segments-20261104/vt_development-policy-ball-roi-v4.json --config codebase/configs/ball-possession-vietnam-tonga-spatial.json --video codebase/outputs/task07-vietnam-tonga-segments-20261104/media/vt_development.mp4 --output-dir codebase/outputs/vt-next-spatial
```

Tests bao gồm reject outside candidates mà giữ source index, aerial ball tách footpoint ROI, predicted outside ROI, sai source hash/invalid polygons, số ngoài roster và competing jersey votes. Audit xác nhận900frames, PTS trong2µs, observed ball refs và observed control sources đúng provenance; file GT, baseline outputs và dataset đã khóa không đổi. Causal replay determinism PASS.

## Phần còn cần làm để cải thiện sản phẩm

Với cache detector hiện tại, candidate recall tối đa41/72≈56.94% trên development như [failure analysis trước](task07-development-evaluation-v2-20261104.md). Postprocessing không thể tạo đủ detections còn thiếu để đạt90%. Cần thí nghiệm candidate recall với crop/scale/confidence của cùng model, đo false positives và latency; không chỉ hạ confidence rồi báo coverage tăng là accuracy tăng.

Với OCR, cần crop evidence theo từng track quanh các pha control, kiểm tra kích thước/độ nét, đọc thiếu chữ số và track switches; đo riêng recognition cùng identity temporal coverage. Nếu cùng model/weights vẫn thiếu năng lực, chuẩn bị dữ liệu domain/hard negatives và phương án fine-tune hoặc model chuyên biệt cụ thể trước xin đổi model/backend/dependency lớn. Chưa thực hiện thay đổi đó trong lượt này.

Ball ROI hiện là cấu hình thủ công theo đoạn/camera, không tự hiểu mọi sân và camera cuts. Muốn dùng video bất kỳ cần camera-aware region/calibration và kiểm chứng trên các đoạn/trận mới. Model/identity vẫn chưa sẵn sàng để ghi points/rebounds/assists đáng tin cậy; không chuyển Task07 sang DONE.
