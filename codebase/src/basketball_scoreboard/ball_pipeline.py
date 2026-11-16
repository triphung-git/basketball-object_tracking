"""Task07 batch adapter, input provenance checks and inspectable local exports."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import time

from .ball import BallConfig, BallTracker, iou
from .possession import PossessionConfig, PossessionEngine
from .spatial_io import file_hash, load_spatial_input, new_output, runtime_snapshot, write_json
from .tracking_policy import normalize_interval,load_ball_roi


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path, rows):
    with Path(path).open("x", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, allow_nan=False) + "\n")


def load_config(path=None):
    raw = json.loads(Path(path).read_text(encoding="utf-8")) if path else {}
    if set(raw) - {"schema_version", "ball", "control"} or raw.get("schema_version", "2.1.0") != "2.1.0":
        raise ValueError("Unknown task07 configuration schema")
    ball, control = BallConfig(**raw.get("ball", {})), PossessionConfig(**raw.get("control", {}))
    return ball, control, dict(schema_version="2.1.0", ball=asdict(ball), control=asdict(control))


def prepare_inputs(detections, run_json, tracks, tracking_run, diagnostic=False,
                   identity_mappings=None, exclusions=None, development_authorization=None):
    run, frames = load_spatial_input(detections, run_json, diagnostic=diagnostic,
                                    development_authorization=development_authorization)
    people = []
    if Path(tracks).read_text(encoding="utf-8").strip():
        _, people = load_spatial_input(tracks, run_json, tracked=True, diagnostic=diagnostic,
                                      development_authorization=development_authorization)
    meta = json.loads(Path(tracking_run).read_text(encoding="utf-8"))
    if run.get("counts", {}).get("total_frames_read", len(frames)) != len(frames) or meta.get("total_frames_processed", len(frames)) != len(frames):
        raise ValueError("Incomplete frame stream relative to source metadata")
    if (meta.get("status") != "completed" or meta.get("source_run_id") != run["run_id"] or
            meta.get("source_fingerprint_sha256") != run["source_fingerprint_sha256"] or
            meta.get("input_detections_sha256") != file_hash(detections)):
        raise ValueError("Tracking provenance mismatch")
    if meta.get("acceptance_scope") not in {"technical", "diagnostic"}:
        raise ValueError("Unknown tracking acceptance scope")
    if not diagnostic and (meta.get("acceptance_scope") == "diagnostic" or
                           (meta.get("roster_config") or {}).get("is_synthetic") or
                           (meta.get("court_config") or {}).get("is_synthetic")):
        raise ValueError("Diagnostic upstream requires explicit diagnostic mode")
    lookup = {frame["frame_index"]: frame for frame in frames}
    by_frame = defaultdict(list)
    mapping_rows = json.loads(Path(identity_mappings).read_text(encoding="utf-8")) if identity_mappings else []
    for mapping in mapping_rows:
        start, end = mapping["start_time_s"], mapping["end_time_s"]
        expiry = mapping.get("evidence_summary", {}).get("valid_until_s", end)
        if not all(math.isfinite(x) for x in (start, end, expiry)) or not 0 <= start <= end or expiry < start:
            raise ValueError("Invalid identity mapping interval")
    dimensions = (run["video_metadata"]["width"], run["video_metadata"]["height"])
    for row in people:
        frame = lookup.get(row["frame_index"])
        if frame is None or abs(frame["source_time_s"]-row["source_time_s"]) > 1e-6 or row["timestamp_status"] != frame["timestamp_status"]:
            raise ValueError("Tracking/detection clock mismatch")
        if row.get("sample_type") not in {"observed", "predicted"} or row.get("role") not in {"player", "unknown", "non_player"}:
            raise ValueError("Invalid track observation semantics")
        if not isinstance(row.get("track_id"), str) or not row["track_id"]:
            raise ValueError("Missing track ID")
        box = row.get("bbox", [])
        if len(box) != 4 or not all(math.isfinite(x) for x in box) or not (box[0] < box[2] and box[1] < box[3]):
            raise ValueError("Invalid tracked bbox")
        if row["sample_type"] == "observed" and not (0 <= box[0] < box[2] <= dimensions[0] and 0 <= box[1] < box[3] <= dimensions[1]):
            raise ValueError("Observed bbox exceeds source image")
        if row["sample_type"] == "observed" and not any(d["class_name"] == "human" and iou(box, d["xyxy"]) >= .98 for d in frame["detections"]):
            raise ValueError("Observed human has no supporting source detection")
        if row.get("player_id"):
            t = row["source_time_s"]
            candidates = [m for m in mapping_rows if m["track_id"] == row["track_id"] and
                          m["start_time_s"] <= t <= m["end_time_s"] and
                          t <= m.get("evidence_summary", {}).get("valid_until_s", m["end_time_s"])]
            current = max(candidates, key=lambda m: (m["start_time_s"], m["revision_id"])) if candidates else None
            if not current or current.get("player_id") != row["player_id"] or current.get("team_id") != row.get("team_id"):
                raise ValueError("Identity is not supported by event-time mapping")
        if any(old["track_id"] == row["track_id"] for old in by_frame[row["frame_index"]]):
            raise ValueError("Duplicate track within a frame")
        by_frame[row["frame_index"]].append(row)
    scopes = {(r.get("camera_id", "unknown"), r.get("segment_id", "default")) for r in people}
    if not scopes:
        court = meta.get("court_config") or {}
        scopes = {(court.get("camera_id", "unknown"), court.get("segment_id", "default"))}
    if len(scopes) != 1:
        raise ValueError("Use one camera/segment per run; explicit cut intervals reset within it")
    intervals = []
    if exclusions:
        exclusion_data = json.loads(Path(exclusions).read_text(encoding="utf-8"))
        if exclusion_data.get("source_video_sha256") != run["source_fingerprint_sha256"]:
            raise ValueError("Exclusion source mismatch")
        for interval in exclusion_data["intervals"]:
            start, end = interval["start_time_s"], interval["end_time_s"]
            if not all(isinstance(x, (float, int)) and not isinstance(x, bool) and math.isfinite(x) for x in (start, end)) or not 0 <= start <= end:
                raise ValueError("Invalid exclusion interval")
            if not interval.get("reason"):
                raise ValueError("Exclusion requires an operational reason")
            intervals.append(normalize_interval(dict(start_time_s=start, end_time_s=end, reason=interval["reason"])))
    return run, frames, by_frame, meta, sorted(scopes)[0], intervals


def process_frames(run, frames, by_frame, scope, intervals, namespace, ball_config, control_config,ball_roi=None):
    tracker = BallTracker((run["video_metadata"]["width"], run["video_metadata"]["height"]), namespace, ball_config)
    engine = PossessionEngine(namespace, control_config)
    balls, controls = [], []
    previous_time = -1.
    common = dict(video_id=run["video_id"], source_run_id=run["run_id"],
                  source_fingerprint_sha256=run["source_fingerprint_sha256"], camera_id=scope[0])
    for frame in frames:
        t = frame["source_time_s"]
        excluded = any(i["start_time_s"] <= t < i["end_time_s"] for i in intervals)
        boundary = any(previous_time < edge <= t for i in intervals for edge in (i["start_time_s"], i["end_time_s"]))
        valid_clock = frame["timestamp_status"] in {"valid", "repaired"}
        ball = tracker.update(frame["frame_index"], t, frame["detections"], scope[1],
                              reset=boundary or excluded, clock_valid=valid_clock and not excluded,
                              ball_roi=ball_roi,
                              human_observations=by_frame[frame['frame_index']],
                              human_boxes=[p['bbox'] for p in by_frame[frame['frame_index']]
                                           if p.get('sample_type')=='observed' and p.get('role')!='non_player'])
        ball.update(common, timestamp_status=frame["timestamp_status"])
        control = engine.update(ball, by_frame[frame["frame_index"]],
                                rims=[d for d in frame["detections"] if d["class_name"] == "rim"],
                                reset_reason="operational_exclusion" if excluded or boundary else None)
        control.update(common, timestamp_status=frame["timestamp_status"])
        balls.append(ball)
        controls.append(control)
        previous_time = t
    engine.finish()
    for rows in (engine.passes, engine.possessions, engine.transitions):
        for row in rows:
            row.update(common, segment_id=scope[1])
    return dict(balls=balls, controls=controls, passes=engine.passes,
                possessions=engine.possessions, transitions=engine.transitions)


def plot_timeline(result, output, diagnostic):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    balls, controls = result["balls"], result["controls"]
    times = [r["source_time_s"] for r in balls]
    fig, axes = plt.subplots(3, 1, figsize=(14, 7), sharex=True)
    for sample, color in (("observed", "#267b38"), ("predicted", "#e19a17"), ("missing", "#b83a3a")):
        selected = [r for r in balls if r["sample_type"] == sample]
        axes[0].scatter([r["source_time_s"] for r in selected], [sample]*len(selected), s=8, color=color)
    states = sorted({r["state"] for r in controls})
    for index, state in enumerate(states):
        selected = [r for r in controls if r["state"] == state]
        axes[1].scatter([r["source_time_s"] for r in selected], [index]*len(selected), s=8, label=state)
    axes[1].set_yticks(range(len(states)), states)
    axes[2].scatter(times, [r["center_image"][1] if r["sample_type"] == "observed" else float("nan") for r in balls], s=8)
    axes[2].invert_yaxis()
    axes[2].set_ylabel("Observed ball y (px)")
    axes[2].set_xlabel("Normalized source PTS (seconds)")
    axes[0].set_title("Task07 DIAGNOSTIC — no accuracy claim" if diagnostic else "Task07 technical timeline — no GT accuracy claim")
    for axis in axes:
        axis.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(output / "timeline.png", dpi=120)
    plt.close(fig)


def export_debug_video(video, run, frames, people, result, output, roster=None):
    import cv2
    import unicodedata
    from .video import VideoReader, VideoWriter
    if file_hash(video) != run["source_fingerprint_sha256"]:
        raise ValueError("Debug video source hash mismatch")
    width, height = run["video_metadata"]["width"], run["video_metadata"]["height"]
    scale = min(1., 960/max(width, height))
    ow, oh = max(2, int(width*scale)//2*2), max(2, int(height*scale)//2*2)
    roster=roster or {}
    players={p['player_id']:p for p in roster.get('players',[])}
    team_labels={roster.get('team_a_id'):roster.get('team_a_name','A'),roster.get('team_b_id'):roster.get('team_b_name','B')}
    colors={roster.get('team_a_id'):tuple(reversed(roster.get('team_a_color_rgb',[220,80,60]))),
            roster.get('team_b_id'):tuple(reversed(roster.get('team_b_color_rgb',[220,220,220])))}
    def actor_label(person):
        team=team_labels.get(person.get('team_id'),'unknown')
        team=unicodedata.normalize('NFKD',team).encode('ascii','ignore').decode()
        jersey=players.get(person.get('player_id'),{}).get('jersey_number','?')
        return f"{team} #{jersey}"
    with VideoReader(video) as reader, VideoWriter(output / "debug.mp4", ow, oh, run["video_metadata"]["fps"]) as writer:
        decoded = iter(reader.frames())
        for frame, ball, control in zip(frames, result["balls"], result["controls"]):
            source_frame, image = next(decoded)
            if source_frame.frame_index != frame["frame_index"] or abs(source_frame.source_time_s-frame["source_time_s"]) > 1e-6:
                raise ValueError("Debug frame clock mismatch")
            canvas = cv2.resize(image, (ow, oh))
            sx, sy = ow/width, oh/height
            for person in people[frame["frame_index"]]:
                if person.get('role')=='non_player':continue
                x1,y1,x2,y2 = person["bbox"]
                color = colors.get(person.get('team_id'),(140,140,140)) if person["sample_type"] == "observed" else (100,100,100)
                cv2.rectangle(canvas, (int(x1*sx),int(y1*sy)), (int(x2*sx),int(y2*sy)), color, 1)
                name=actor_label(person)+(' [pred]' if person['sample_type']!='observed' else '')
                cv2.putText(canvas,name,(max(0,int(x1*sx)),max(12,int(y1*sy)-3)),cv2.FONT_HERSHEY_SIMPLEX,.35,color,1)
            if ball["center_image"]:
                x,y = ball["center_image"]
                cv2.circle(canvas, (int(x*sx),int(y*sy)), 6,
                           (0,220,255) if ball["sample_type"] == "observed" else (80,80,220), 2)
            label = f"t={frame['source_time_s']:.3f}  {ball['sample_type']} / {control['state']}"
            cv2.rectangle(canvas, (0,0), (ow,min(66,oh)), (20,20,20), -1)
            cv2.putText(canvas, label, (8,22), cv2.FONT_HERSHEY_SIMPLEX, .45, (240,240,240), 1)
            controller = control["controller"] or control.get("candidate_actor") or {}
            cv2.putText(canvas, "TECHNICAL | "+control['certainty']+" | actor=" + (actor_label(controller) if controller else 'unknown'),
                        (8,45), cv2.FONT_HERSHEY_SIMPLEX, .4, (200,200,200), 1)
            writer.write_frame(canvas, source_frame.source_time_s)
    # Independent decoder readback, without applying the repair policy a second time.
    import av
    with av.open(str(output / "debug.mp4")) as handle:
        exported = [float(f.pts*f.time_base) for f in handle.decode(video=0)]
    expected = [r["source_time_s"] for r in frames]
    if len(exported) != len(expected) or any(abs(a-b) > 2e-6 for a,b in zip(exported, expected)):
        raise ValueError("Debug export PTS readback mismatch")
    return dict(frames=len(exported), max_pts_error_s=max(abs(a-b) for a,b in zip(exported, expected)),
                dimensions=[ow, oh], timestamp_policy="explicit_source_pts", audio=False)


def run_ball_pipeline(detections, run_json, tracks, tracking_run, output_dir, config=None,
                      diagnostic=False, identity_mappings=None, exclusions=None, video=None,
                      development_authorization=None, verify_replay=True):
    output = None
    started = time.perf_counter()
    try:
        ball_config, control_config, config_data = load_config(config)
        run, frames, people, meta, scope, intervals = prepare_inputs(
            detections, run_json, tracks, tracking_run, diagnostic, identity_mappings, exclusions, development_authorization)
        ball_roi=load_ball_roi(exclusions,run['source_fingerprint_sha256'])
        sources = [detections, run_json, tracks, tracking_run, config, identity_mappings, exclusions, video, development_authorization]
        input_hashes = {name: file_hash(path) for name, path in zip(
            ("detections", "source_run", "tracks", "tracking_run", "config", "identity_mappings", "exclusions", "video", "development_authorization"), sources) if path}
        implementation={name:file_hash(Path(__file__).parent/name) for name in ('ball.py','ball_actor_context.py','possession.py','ball_pipeline.py','tracking_policy.py')}
        namespace = hashlib.sha256(json.dumps(dict(inputs=input_hashes, config=config_data,implementation=implementation), sort_keys=True).encode()).hexdigest()[:20]
        output = new_output(output_dir, sources)
        write_json(output / "run.json", dict(status="running", namespace=namespace))
        core_started = time.perf_counter()
        result = process_frames(run, frames, people, scope, intervals, namespace, ball_config, control_config,ball_roi)
        core_s = time.perf_counter()-core_started
        if verify_replay:
            replay = process_frames(run, frames, people, scope, intervals, namespace, ball_config, control_config,ball_roi)
            if result != replay:
                raise AssertionError("Task07 replay is not deterministic")
        for key, filename in (("balls", "ball_tracks.jsonl"), ("controls", "ball_control.jsonl"),
                              ("passes", "passes.jsonl"), ("possessions", "possessions.jsonl"), ("transitions", "transitions.jsonl")):
            write_jsonl(output / filename, result[key])
        plot_timeline(result, output, diagnostic)
        video_export = export_debug_video(video, run, frames, people, result, output,roster=meta.get('roster_config')) if video else None
        runtime = runtime_snapshot(__file__)
        runtime["implementation_revision"] = "task07-20261104"
        summary = dict(status="completed", schema_version="2.1.0", namespace=namespace,
                       source_run_id=run["run_id"], video_id=run["video_id"],
                       source_fingerprint_sha256=run["source_fingerprint_sha256"],
                       acceptance_scope="diagnostic" if diagnostic else "technical_unbenchmarked",
                       config=config_data, input_sha256=input_hashes, runtime=runtime,
                       implementation_sha256=implementation,
                       upstream_acceptance_scope=meta["acceptance_scope"],
                       development_authorization=json.loads(Path(development_authorization).read_text(encoding="utf-8")) if development_authorization else None,
                       exclusions=intervals,ball_image_roi_normalized=ball_roi,frames=len(frames),
                       ball_samples=dict(Counter(row["sample_type"] for row in result["balls"])),
                       control_states=dict(Counter(row["state"] for row in result["controls"])),
                       pass_outcomes=dict(Counter(row["outcome"] for row in result["passes"])),
                       possession_count=len(result["possessions"]), transition_count=len(result["transitions"]),
                       replay_verified=verify_replay, video_export=video_export,
                       timings=dict(core_processing_s=core_s, core_fps=len(frames)/core_s,
                                    total_processing_s=time.perf_counter()-started,
                                    scope="cached detections/tracks; detector/OCR excluded; total includes replay and exports"),
                       metrics=dict(ball_recall=None, control_accuracy=None, pass_precision=None, pass_recall=None,
                                    reason="No reviewed ground truth supplied to evaluator; engine never reads GT"),
                       limitations=["BBox temporal heuristics; no pose/intent model",
                                    "Handoff/deflection/shot labels are candidates, not official stat events",
                                    "Operational possession is not an official rules decision",
                                    "No independent real-match accuracy acceptance"])
        write_json(output / "summary.json", summary)
        write_json(output / "run.json", summary)
        return summary
    except Exception as error:
        if output:
            write_json(output / "run.json", dict(status="failed", error_class=type(error).__name__))
        raise
