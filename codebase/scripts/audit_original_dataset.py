#!/usr/bin/env python3
"""Audit labels in the original dataset export for bounding box errors.

Measures:
- Bounding box coordinates and out-of-bounds amounts (normalized and pixel)
- Error categories:
    * epsilon_rounding: exceeded by <= 1e-4
    * clipped_by_border: slightly cut by image boundary (exceeded by <= 0.05 / 5% or <= 32px)
    * severe_out_of_bounds: exceeded by > 0.05
    * nonfinite_or_zero_area: w <= 0 or h <= 0 or nonfinite
    * invalid_class: class ID not in [0, 1, 2]
    * missing_label: image without label file
- Breakdown by split and class
- Reports all affected images, source families, and boxes
"""
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "data/finetune/task07a/original/export"
CLASS_NAMES = ["ball", "human", "rim"]


def audit():
    splits = ["train", "valid", "test"]
    audit_results = {
        "summary": {
            "total_images": 0,
            "valid_images": 0,
            "problematic_images": 0,
            "total_boxes": 0,
            "out_of_bounds_boxes": 0,
            "by_category": Counter(),
            "by_split": {s: {"images": 0, "boxes": 0, "problem_images": 0, "problem_boxes": 0, "classes": Counter()} for s in splits},
            "by_class": {c: {"total": 0, "problem": 0, "by_category": Counter()} for c in CLASS_NAMES},
        },
        "errors": [],
    }

    for split in splits:
        split_dir = EXPORT_DIR / split
        img_dir = split_dir / "images"
        lbl_dir = split_dir / "labels"
        images = sorted(img_dir.glob("*"))

        for img_path in images:
            if img_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
                continue

            audit_results["summary"]["total_images"] += 1
            audit_results["summary"]["by_split"][split]["images"] += 1

            lbl_path = lbl_dir / (img_path.stem + ".txt")
            if not lbl_path.is_file():
                audit_results["summary"]["problematic_images"] += 1
                audit_results["summary"]["by_split"][split]["problem_images"] += 1
                audit_results["summary"]["by_category"]["missing_label"] += 1
                audit_results["errors"].append({
                    "image": img_path.name,
                    "split": split,
                    "error_type": "missing_label",
                    "details": "Label file does not exist",
                })
                continue

            with Image.open(img_path) as im:
                img_w, img_h = im.size

            lines = lbl_path.read_text(encoding="utf-8").splitlines()
            img_has_error = False

            for line_idx, line in enumerate(lines):
                fields = line.strip().split()
                if not fields:
                    continue
                audit_results["summary"]["total_boxes"] += 1
                audit_results["summary"]["by_split"][split]["boxes"] += 1

                if len(fields) != 5:
                    img_has_error = True
                    audit_results["summary"]["by_category"]["malformed_line"] += 1
                    audit_results["errors"].append({
                        "image": img_path.name,
                        "split": split,
                        "line_idx": line_idx,
                        "error_type": "malformed_line",
                        "raw_line": line,
                    })
                    continue

                cls_id = int(fields[0])
                if cls_id < 0 or cls_id >= len(CLASS_NAMES):
                    img_has_error = True
                    audit_results["summary"]["by_category"]["invalid_class"] += 1
                    audit_results["errors"].append({
                        "image": img_path.name,
                        "split": split,
                        "line_idx": line_idx,
                        "error_type": "invalid_class",
                        "class_id": cls_id,
                    })
                    continue

                cls_name = CLASS_NAMES[cls_id]
                audit_results["summary"]["by_split"][split]["classes"][cls_name] += 1
                audit_results["summary"]["by_class"][cls_name]["total"] += 1

                cx, cy, w, h = map(float, fields[1:])
                if not all(math.isfinite(v) for v in (cx, cy, w, h)):
                    img_has_error = True
                    audit_results["summary"]["by_category"]["nonfinite"] += 1
                    audit_results["errors"].append({
                        "image": img_path.name,
                        "split": split,
                        "line_idx": line_idx,
                        "class": cls_name,
                        "error_type": "nonfinite",
                    })
                    continue

                if w <= 0 or h <= 0:
                    img_has_error = True
                    audit_results["summary"]["by_category"]["zero_area"] += 1
                    audit_results["errors"].append({
                        "image": img_path.name,
                        "split": split,
                        "line_idx": line_idx,
                        "class": cls_name,
                        "error_type": "zero_area",
                        "dimensions": [w, h],
                    })
                    continue

                x1 = cx - w / 2.0
                y1 = cy - h / 2.0
                x2 = cx + w / 2.0
                y2 = cy + h / 2.0

                # Check bounds
                oob_left = -x1 if x1 < 0 else 0.0
                oob_top = -y1 if y1 < 0 else 0.0
                oob_right = x2 - 1.0 if x2 > 1.0 else 0.0
                oob_bottom = y2 - 1.0 if y2 > 1.0 else 0.0
                max_oob = max(oob_left, oob_top, oob_right, oob_bottom)

                if max_oob > 1e-5:
                    img_has_error = True
                    audit_results["summary"]["out_of_bounds_boxes"] += 1
                    audit_results["summary"]["by_split"][split]["problem_boxes"] += 1
                    audit_results["summary"]["by_class"][cls_name]["problem"] += 1

                    # Categorize severity
                    max_oob_px = max(oob_left * img_w, oob_right * img_w, oob_top * img_h, oob_bottom * img_h)
                    if max_oob <= 1e-4:
                        cat = "epsilon_rounding"
                    elif max_oob <= 0.05 or max_oob_px <= 32:
                        cat = "clipped_by_border"
                    else:
                        cat = "severe_out_of_bounds"

                    audit_results["summary"]["by_category"][cat] += 1
                    audit_results["summary"]["by_class"][cls_name]["by_category"][cat] += 1

                    audit_results["errors"].append({
                        "image": img_path.name,
                        "split": split,
                        "line_idx": line_idx,
                        "class": cls_name,
                        "error_type": cat,
                        "raw_box": [cx, cy, w, h],
                        "xyxy_norm": [round(x1, 6), round(y1, 6), round(x2, 6), round(y2, 6)],
                        "xyxy_px": [round(x1 * img_w, 2), round(y1 * img_h, 2), round(x2 * img_w, 2), round(y2 * img_h, 2)],
                        "img_wh": [img_w, img_h],
                        "max_oob_norm": round(max_oob, 6),
                        "max_oob_px": round(max_oob_px, 2),
                        "oob_directions": {
                            "left": round(oob_left, 6),
                            "top": round(oob_top, 6),
                            "right": round(oob_right, 6),
                            "bottom": round(oob_bottom, 6),
                        },
                    })

            if img_has_error:
                audit_results["summary"]["problematic_images"] += 1
                audit_results["summary"]["by_split"][split]["problem_images"] += 1
            else:
                audit_results["summary"]["valid_images"] += 1

    # Convert Counters to dicts for JSON serialization
    audit_results["summary"]["by_category"] = dict(audit_results["summary"]["by_category"])
    for s in splits:
        audit_results["summary"]["by_split"][s]["classes"] = dict(audit_results["summary"]["by_split"][s]["classes"])
    for c in CLASS_NAMES:
        audit_results["summary"]["by_class"][c]["by_category"] = dict(audit_results["summary"]["by_class"][c]["by_category"])

    return audit_results


if __name__ == "__main__":
    res = audit()
    out_file = ROOT / "outputs/task07a-finetune-20261108/original_dataset_label_audit.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"Total Images: {res['summary']['total_images']}")
    print(f"Valid Images: {res['summary']['valid_images']}")
    print(f"Problematic Images: {res['summary']['problematic_images']}")
    print(f"Total Boxes: {res['summary']['total_boxes']}")
    print(f"Out-of-Bounds Boxes: {res['summary']['out_of_bounds_boxes']}")
    print("By Category:", res["summary"]["by_category"])
    print("\nBy Split:")
    for s, info in res["summary"]["by_split"].items():
        print(f"  {s}: {info['images']} images ({info['problem_images']} problem), {info['boxes']} boxes ({info['problem_boxes']} problem)")
    print("\nBy Class:")
    for c, info in res["summary"]["by_class"].items():
        print(f"  {c}: {info['total']} boxes, {info['problem']} problem: {info['by_category']}")
