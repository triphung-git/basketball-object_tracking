#!/usr/bin/env python3
"""Post-run Task07A diagnostics; reviewed GT is read only after inference."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from basketball_scoreboard.ball import center, iou
from basketball_scoreboard.ball_pipeline import jsonl
from basketball_scoreboard.spatial_io import file_hash, write_json


def _read_frames(video_path, wanted, samples, patch_metrics):
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError("Unable to open local development video")
    previous = None
    index = 0
    try:
        while index <= max(wanted, default=-1):
            ok, frame = capture.read()
            if not ok:
                break
            if index in wanted:
                sample = samples[index]
                x1, y1, x2, y2 = sample["gt_xyxy"]
                cx, cy = center((x1, y1, x2, y2))
                left, top = max(0, int(cx - 240)), max(0, int(cy - 160))
                right, bottom = min(frame.shape[1], left + 480), min(frame.shape[0], top + 320)
                left, top = max(0, right - 480), max(0, bottom - 320)
                crop = frame[top:bottom, left:right].copy()
                if crop.shape[:2] != (320, 480):
                    crop = cv2.copyMakeBorder(crop, 0, 320 - crop.shape[0], 0, 480 - crop.shape[1],
                                              cv2.BORDER_REPLICATE)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                roi_x1, roi_y1 = max(0, int(x1)), max(0, int(y1))
                roi_x2, roi_y2 = min(gray.shape[1], int(x2)), min(gray.shape[0], int(y2))
                roi = gray[roi_y1:roi_y2, roi_x1:roi_x2]
                sample["gt_roi_laplacian_variance"] = (
                    float(cv2.Laplacian(roi, cv2.CV_64F).var()) if roi.size else None)
                flow_median = None
                if previous is not None:
                    px1, py1 = max(0, int(cx - 32)), max(0, int(cy - 32))
                    px2, py2 = min(frame.shape[1], int(cx + 32)), min(frame.shape[0], int(cy + 32))
                    flow = cv2.calcOpticalFlowFarneback(previous[py1:py2, px1:px2], gray[py1:py2, px1:px2],
                                                        None, .5, 2, 15, 2, 5, 1.1, 0)
                    if flow.size:
                        flow_median = float(np.median(np.linalg.norm(flow, axis=2)))
                sample["median_local_flow_px_per_frame"] = flow_median
                patch_metrics[index] = dict(crop=crop, left=left, top=top,
                                            scene=cv2.resize(frame, (480, 270), interpolation=cv2.INTER_AREA))
                previous = gray
            else:
                previous = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            index += 1
    finally:
        capture.release()


def _draw_case(sample, crop, left, top):
    image = crop.copy()
    gx1, gy1, gx2, gy2 = sample["gt_xyxy"]
    cv2.rectangle(image, (int(gx1 - left), int(gy1 - top)), (int(gx2 - left), int(gy2 - top)), (0, 255, 0), 2)
    for candidate in sample["candidates"]:
        x1, y1, x2, y2 = candidate["xyxy"]
        cv2.rectangle(image, (int(x1 - left), int(y1 - top)), (int(x2 - left), int(y2 - top)), (0, 165, 255), 2)
        cv2.putText(image, f"{candidate['confidence']:.2f}", (int(x1 - left), max(12, int(y1 - top) - 3)),
                    cv2.FONT_HERSHEY_SIMPLEX, .35, (0, 165, 255), 1, cv2.LINE_AA)
    label = f"f{sample['frame_index']} {sample['category']} size={sample['gt_size_px']}"
    cv2.rectangle(image, (0, 0), (480, 23), (0, 0, 0), -1)
    cv2.putText(image, label[:70], (5, 16), cv2.FONT_HERSHEY_SIMPLEX, .42, (255, 255, 255), 1, cv2.LINE_AA)
    return image


def _write_sheet(samples, crops, path):
    failures = [sample for sample in samples if sample["category"] != "correct_observed"]
    if not failures:
        return
    columns, tile_w, tile_h = 3, 480, 320
    rows = math.ceil(len(failures) / columns)
    sheet = np.zeros((rows * tile_h, columns * tile_w, 3), dtype=np.uint8)
    for index, sample in enumerate(failures):
        x, y = (index % columns) * tile_w, (index // columns) * tile_h
        patch = crops[sample["frame_index"]]
        sheet[y:y + tile_h, x:x + tile_w] = _draw_case(sample, patch["crop"], patch["left"], patch["top"])
    if not cv2.imwrite(str(path), sheet):
        raise RuntimeError(f"Unable to write diagnostic contact sheet: {path}")


def _write_background_sheet(samples, crops, path, frame_wh):
    examples = [sample for sample in samples if sample["upper_background_candidates"]]
    if not examples:
        return
    columns, tile_w, tile_h = 4, 480, 270
    rows = math.ceil(len(examples) / columns)
    sheet = np.zeros((rows * tile_h, columns * tile_w, 3), dtype=np.uint8)
    scale_x, scale_y = tile_w / frame_wh[0], tile_h / frame_wh[1]
    for index, sample in enumerate(examples):
        x, y = (index % columns) * tile_w, (index // columns) * tile_h
        image = crops[sample["frame_index"]]["scene"].copy()
        gx1, gy1, gx2, gy2 = sample["gt_xyxy"]
        cv2.rectangle(image, (round(gx1 * scale_x), round(gy1 * scale_y)),
                      (round(gx2 * scale_x), round(gy2 * scale_y)), (0, 255, 0), 2)
        for candidate in sample["upper_background_candidates"]:
            x1, y1, x2, y2 = candidate["xyxy"]
            cv2.rectangle(image, (round(x1 * scale_x), round(y1 * scale_y)),
                          (round(x2 * scale_x), round(y2 * scale_y)), (0, 165, 255), 2)
        cv2.rectangle(image, (0, 0), (480, 20), (0, 0, 0), -1)
        cv2.putText(image, f"frame {sample['frame_index']} upper-background candidates={len(sample['upper_background_candidates'])}",
                    (5, 15), cv2.FONT_HERSHEY_SIMPLEX, .38, (255, 255, 255), 1, cv2.LINE_AA)
        sheet[y:y + tile_h, x:x + tile_w] = image
    if not cv2.imwrite(str(path), sheet):
        raise RuntimeError(f"Unable to write background-candidate contact sheet: {path}")


def analyze(gt_path, detection_dir, ball_dir, video_path, output_dir):
    gt = json.loads(Path(gt_path).read_text(encoding="utf-8"))
    detection_dir, ball_dir = Path(detection_dir), Path(ball_dir)
    detection_run = json.loads((detection_dir / "run.json").read_text(encoding="utf-8"))
    ball_run = json.loads((ball_dir / "run.json").read_text(encoding="utf-8"))
    if detection_run["status"] != "completed" or ball_run["status"] != "completed":
        raise ValueError("Both detection and ball runs must be completed")
    if detection_run["source_fingerprint_sha256"] != gt["source_video_sha256"]:
        raise ValueError("Detection video fingerprint differs from reviewed GT")
    if (ball_run["source_fingerprint_sha256"] != gt["source_video_sha256"] or
            ball_run["source_run_id"] != detection_run["run_id"]):
        raise ValueError("Ball output is not bound to this detection run and GT source")
    detections = {row["frame_index"]: row for row in jsonl(detection_dir / "detections.jsonl")}
    balls = {row["frame_index"]: row for row in jsonl(ball_dir / "ball_tracks.jsonl")}
    people_class = "human"
    samples, wanted = [], set()
    for target in gt["ball_samples"]:
        if not target["visible"] or target["uncertain"]:
            continue
        index, box = target["frame_index"], target["xyxy"]
        frame = detections.get(index)
        selected = balls.get(index)
        if frame is None or selected is None:
            raise ValueError(f"Missing frame {index} from a completed output")
        candidates = [dict(xyxy=item["xyxy"], confidence=item["confidence"])
                      for item in frame["detections"] if item["class_name"] == "ball"]
        matching = [candidate for candidate in candidates if iou(box, candidate["xyxy"]) >= .30]
        selected_iou = iou(box, selected["xyxy"]) if selected["sample_type"] == "observed" else 0.0
        if selected["sample_type"] == "observed" and selected_iou >= .30:
            category = "correct_observed"
        elif matching:
            category = "candidate_available_not_selected"
        elif selected["sample_type"] == "observed":
            category = "observed_unmatched"
        else:
            category = "no_matching_candidate"
        humans = [item["xyxy"] for item in frame["detections"] if item["class_name"] == people_class]
        cx, cy = center(box)
        inside_person = any(x1 <= cx <= x2 and y1 <= cy <= y2 for x1, y1, x2, y2 in humans)
        width, height = box[2] - box[0], box[3] - box[1]
        upper_background_candidates = [
            candidate for candidate in candidates
            if iou(box, candidate["xyxy"]) < .30 and center(candidate["xyxy"])[1] < .56 * gt["original_wh"][1]]
        sample = dict(frame_index=index, source_time_s=target["source_time_s"], gt_xyxy=box, category=category,
                      gt_size_px=[width, height], min_side_px=min(width, height), candidates=candidates,
                      matching_candidate_count=len(matching),
                      best_candidate_iou=max((iou(box, candidate["xyxy"]) for candidate in candidates), default=0.0),
                      selected_type=selected["sample_type"], selected_iou=selected_iou,
                      selected_reason=selected.get("reason"), ball_track_id=selected.get("ball_track_id"),
                      acquisition_or_reacquisition=(selected["sample_type"] == "missing" and
                                                     selected.get("ball_track_id") is None),
                      gt_center_inside_human_bbox=inside_person,
                      upper_background_candidates=upper_background_candidates,
                      upper_background_unmatched_candidates=len(upper_background_candidates))
        samples.append(sample)
        wanted.add(index)

    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    crops = {}
    _read_frames(video_path, wanted, {sample["frame_index"]: sample for sample in samples}, crops)
    for sample in samples:
        if sample["frame_index"] not in crops:
            raise ValueError(f"Unable to decode sample frame {sample['frame_index']}")
    counts = Counter(sample["category"] for sample in samples)
    size_counts = Counter("small_min_side_le_20px" if sample["min_side_px"] <= 20 else "min_side_gt_20px"
                          for sample in samples)
    flow_values = [sample["median_local_flow_px_per_frame"] for sample in samples
                   if sample["median_local_flow_px_per_frame"] is not None]
    failures = [sample for sample in samples if sample["category"] != "correct_observed"]
    blur_values = [sample["gt_roi_laplacian_variance"] for sample in samples
                   if sample["gt_roi_laplacian_variance"] is not None]
    failure_characteristics = {}
    for label, group in (("all", samples), ("missed_or_wrong", failures),
                         ("no_matching_candidate", [s for s in samples if s["category"] == "no_matching_candidate"]),
                         ("candidate_available_not_selected", [s for s in samples if s["category"] == "candidate_available_not_selected"]),
                         ("observed_unmatched", [s for s in samples if s["category"] == "observed_unmatched"])):
        flows = [s["median_local_flow_px_per_frame"] for s in group
                 if s["median_local_flow_px_per_frame"] is not None]
        failure_characteristics[label] = dict(
            samples=len(group),
            min_side_le_20px=sum(s["min_side_px"] <= 20 for s in group),
            gt_center_inside_human_bbox=sum(s["gt_center_inside_human_bbox"] for s in group),
            acquisition_or_reacquisition=sum(s["acquisition_or_reacquisition"] for s in group),
            local_flow_gt_2px_per_frame=sum(value > 2 for value in flows),
            local_flow_gt_4px_per_frame=sum(value > 4 for value in flows),
            upper_background_unmatched_candidates=sum(s["upper_background_unmatched_candidates"] for s in group),
        )
    metrics = dict(
        scope="post_inference_development_diagnostics_only",
        source_video_sha256=gt["source_video_sha256"],
        reviewed_gt_sha256=file_hash(gt_path),
        analysis_script_sha256=file_hash(__file__),
        detection_run_id=detection_run["run_id"],
        detection_run_json_sha256=file_hash(detection_dir / "run.json"),
        detections_sha256=file_hash(detection_dir / "detections.jsonl"),
        detection_config=dict(model=detection_run["config"]["model"],
                              tiling=detection_run["runtime"].get("ball_tiling", {}),
                              experiment_settings=detection_run.get("experiment_settings")),
        ball_run_id=ball_dir.name,
        ball_run_json_sha256=file_hash(ball_dir / "run.json"),
        ball_tracks_sha256=file_hash(ball_dir / "ball_tracks.jsonl"),
        parameters=dict(iou_threshold=.30, gt_samples=len(samples), upper_background_y_fraction=.56,
                        motion_metric="median Farneback flow magnitude in 64x64 crop vs immediately prior frame; diagnostic proxy only"),
        counts=dict(counts),
        candidate_recall=sum(sample["best_candidate_iou"] >= .30 for sample in samples) / len(samples),
        observed_ball_recall=sum(sample["category"] == "correct_observed" for sample in samples) / len(samples),
        observed_nonmatches=sum(sample["category"] == "observed_unmatched" for sample in samples),
        raw_nonmatching_candidates_at_gt_frames=sum(
            sum(iou(sample["gt_xyxy"], candidate["xyxy"]) < .30 for candidate in sample["candidates"])
            for sample in samples),
        size_counts=dict(size_counts),
        gt_center_inside_human_bbox=sum(sample["gt_center_inside_human_bbox"] for sample in samples),
        upper_background_candidates_at_gt_frames=sum(sample["upper_background_unmatched_candidates"] for sample in samples),
        median_local_flow_px_per_frame=float(np.median(flow_values)) if flow_values else None,
        median_gt_roi_laplacian_variance=float(np.median(blur_values)) if blur_values else None,
        failure_characteristics=failure_characteristics,
        samples=samples,
    )
    write_json(output / "diagnostics.json", metrics)
    _write_sheet(samples, crops, output / "failure-cases.jpg")
    _write_background_sheet(samples, crops, output / "background-candidates.jpg", gt["original_wh"])
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ground-truth", required=True)
    parser.add_argument("--detection-run-dir", required=True)
    parser.add_argument("--ball-run-dir", required=True)
    parser.add_argument("--video", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    try:
        result = analyze(args.ground_truth, args.detection_run_dir, args.ball_run_dir,
                         args.video, args.output_dir)
        print(json.dumps({key: result[key] for key in ("counts", "candidate_recall", "observed_ball_recall",
                                                       "observed_nonmatches", "raw_nonmatching_candidates_at_gt_frames")}))
        return 0
    except Exception as error:
        print(f"Task07A analysis failed ({type(error).__name__})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
