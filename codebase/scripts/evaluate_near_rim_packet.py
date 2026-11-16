#!/usr/bin/env python3
"""Evaluate baseline vs candidate detector on reviewed near-rim frames (R01 evaluation)."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from ultralytics import YOLO


def compute_iou(box1: list[float], box2: list[float]) -> float:
    xA = max(box1[0], box2[0])
    yA = max(box1[1], box2[1])
    xB = min(box1[2], box2[2])
    yB = min(box1[3], box2[3])
    inter_area = max(0.0, xB - xA) * max(0.0, yB - yA)
    box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
    box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union_area = box1_area + box2_area - inter_area
    return inter_area / union_area if union_area > 0 else 0.0


def evaluate_packet(
    review_json_path: str,
    images_dir: str,
    baseline_weights: str,
    candidate_weights: str,
    output_json_path: str,
    conf_threshold: float = 0.15,
) -> dict:
    review_data = json.loads(Path(review_json_path).read_text(encoding="utf-8"))
    frames = review_data.get("reviewed_frames", [])
    img_dir = Path(images_dir).resolve()

    baseline_model = YOLO(baseline_weights)
    candidate_model = YOLO(candidate_weights)

    results = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "confidence_threshold": conf_threshold,
        "baseline_weights": baseline_weights,
        "candidate_weights": candidate_weights,
        "total_frames": len(frames),
        "frame_evaluations": [],
        "metrics": {
            "baseline": {"tp": 0, "fp": 0, "fn": 0, "tn": 0, "ious": []},
            "candidate": {"tp": 0, "fp": 0, "fn": 0, "tn": 0, "ious": []},
        },
    }

    for f in frames:
        sample_id = f["sample_id"]
        img_name = f["image"]
        vis = f["visibility"]
        gt_box = f.get("ball_bbox_xyxy")
        img_path = img_dir / img_name

        if not img_path.exists():
            raise FileNotFoundError(f"Frame image not found: {img_path}")

        # Run inference
        base_pred = baseline_model.predict(str(img_path), conf=conf_threshold, verbose=False)[0]
        cand_pred = candidate_model.predict(str(img_path), conf=conf_threshold, verbose=False)[0]

        def get_best_ball_box(pred):
            ball_boxes = []
            for box in pred.boxes:
                cls_id = int(box.cls[0].item())
                cls_name = pred.names[cls_id]
                if cls_name == "ball":
                    xyxy = [float(v) for v in box.xyxy[0].tolist()]
                    conf = float(box.conf[0].item())
                    ball_boxes.append((xyxy, conf))
            if not ball_boxes:
                return None, 0.0
            # Return box with highest confidence
            ball_boxes.sort(key=lambda x: x[1], reverse=True)
            return ball_boxes[0]

        base_box, base_conf = get_best_ball_box(base_pred)
        cand_box, cand_conf = get_best_ball_box(cand_pred)

        frame_res = {
            "sample_id": sample_id,
            "visibility": vis,
            "gt_bbox": gt_box,
            "baseline": {"detected": base_box is not None, "bbox": base_box, "conf": round(base_conf, 4), "iou": 0.0},
            "candidate": {"detected": cand_box is not None, "bbox": cand_box, "conf": round(cand_conf, 4), "iou": 0.0},
        }

        # Evaluate baseline
        if vis in {"visible", "partially_occluded"} and gt_box is not None:
            if base_box is not None:
                iou = compute_iou(gt_box, base_box)
                frame_res["baseline"]["iou"] = round(iou, 4)
                if iou >= 0.3:
                    results["metrics"]["baseline"]["tp"] += 1
                    results["metrics"]["baseline"]["ious"].append(iou)
                else:
                    results["metrics"]["baseline"]["fp"] += 1
            else:
                results["metrics"]["baseline"]["fn"] += 1

            if cand_box is not None:
                iou = compute_iou(gt_box, cand_box)
                frame_res["candidate"]["iou"] = round(iou, 4)
                if iou >= 0.3:
                    results["metrics"]["candidate"]["tp"] += 1
                    results["metrics"]["candidate"]["ious"].append(iou)
                else:
                    results["metrics"]["candidate"]["fp"] += 1
            else:
                results["metrics"]["candidate"]["fn"] += 1

        elif vis == "fully_occluded":
            if base_box is not None:
                results["metrics"]["baseline"]["fp"] += 1
            else:
                results["metrics"]["baseline"]["tn"] += 1

            if cand_box is not None:
                results["metrics"]["candidate"]["fp"] += 1
            else:
                results["metrics"]["candidate"]["tn"] += 1

        results["frame_evaluations"].append(frame_res)

    for m_key in ["baseline", "candidate"]:
        m = results["metrics"][m_key]
        m["mean_iou"] = round(sum(m["ious"]) / len(m["ious"]), 4) if m["ious"] else 0.0
        p = m["tp"] / (m["tp"] + m["fp"]) if (m["tp"] + m["fp"]) > 0 else 0.0
        r = m["tp"] / (m["tp"] + m["fn"]) if (m["tp"] + m["fn"]) > 0 else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        m["precision"] = round(p, 4)
        m["recall"] = round(r, 4)
        m["f1"] = round(f1, 4)

    out_p = Path(output_json_path).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-json", required=True)
    parser.add_argument("--images-dir", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--conf", type=float, default=0.15)
    args = parser.parse_args()

    res = evaluate_packet(
        args.review_json,
        args.images_dir,
        args.baseline,
        args.candidate,
        args.output,
        conf_threshold=args.conf,
    )
    print(json.dumps(res["metrics"], indent=2))


if __name__ == "__main__":
    main()
