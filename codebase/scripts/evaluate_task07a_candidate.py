#!/usr/bin/env python3
"""Paired native detector evaluation for baseline vs fine-tuned candidate.

Evaluates both validation and test splits with per-class breakdowns, metric deltas,
and automated quality gate decisions.
Never substitutes for downstream OCR, identity, ROI, or full-pipeline acceptance.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from prepare_task07a_finetune import class_names, sha256
from train_task07a_candidate import verify_dataset


def evaluate_model(model_wrapper, dataset_yaml: str, split: str, output_dir: Path, name: str, class_list: list[str]) -> dict:
    """Run Ultralytics validation on a specific split and return structured metrics."""
    metrics = model_wrapper.val(
        data=str(dataset_yaml),
        split=split,
        device=0,
        batch=2,
        imgsz=640,
        workers=0,
        project=str(output_dir),
        name=f"{name}_{split}",
        plots=True,
    )
    per_class = {c: dict(precision=0.0, recall=0.0, map50=0.0, map50_95=0.0) for c in class_list}
    for position, class_id in enumerate(metrics.box.ap_class_index):
        if int(class_id) < len(class_list):
            c_name = class_list[int(class_id)]
            p, r, ap50, ap5095 = metrics.box.class_result(position)
            per_class[c_name] = dict(
                precision=round(float(p), 4),
                recall=round(float(r), 4),
                map50=round(float(ap50), 4),
                map50_95=round(float(ap5095), 4),
            )

    summary_metrics = {
        "precision": round(float(metrics.box.mp), 4),
        "recall": round(float(metrics.box.mr), 4),
        "map50": round(float(metrics.box.map50), 4),
        "map50_95": round(float(metrics.box.map), 4),
    }

    return dict(
        summary=summary_metrics,
        per_class=per_class,
        raw_results={k: float(v) for k, v in metrics.results_dict.items()},
    )


def compute_deltas(baseline_metrics: dict, candidate_metrics: dict) -> dict:
    """Compute candidate - baseline deltas for summary and per-class metrics."""
    deltas = {"summary": {}, "per_class": {}}
    for k, v in candidate_metrics["summary"].items():
        base_v = baseline_metrics["summary"].get(k, 0.0)
        deltas["summary"][k] = round(v - base_v, 4)

    for c_name, c_dict in candidate_metrics["per_class"].items():
        base_c_dict = baseline_metrics["per_class"].get(c_name, {})
        deltas["per_class"][c_name] = {
            m_key: round(c_dict[m_key] - base_c_dict.get(m_key, 0.0), 4)
            for m_key in c_dict
        }
    return deltas


def evaluate_paired(dataset_path: str, candidate_path: str, output_path: str, splits: list[str] = None):
    from ultralytics import YOLO

    splits = splits or ["val", "test"]
    manifest, names = verify_dataset(dataset_path)
    output = Path(output_path).resolve()
    output.mkdir(parents=True, exist_ok=True)

    dataset_yaml = Path(dataset_path).resolve() / "data.yaml"
    baseline_path = Path(manifest["checkpoint"]).resolve()
    candidate_file = Path(candidate_path).resolve()

    if not candidate_file.exists():
        raise FileNotFoundError(f"Candidate checkpoint not found at {candidate_file}")

    baseline_hash = sha256(baseline_path)
    candidate_hash = sha256(candidate_file)

    report = dict(
        scope="native_detector_paired_evaluation",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        classes=names,
        dataset=str(dataset_path),
        dataset_counts=manifest["counts"],
        baseline=dict(path=str(baseline_path), sha256=baseline_hash),
        candidate=dict(path=str(candidate_file), sha256=candidate_hash),
        splits_evaluated=splits,
        results={},
        deltas={},
        downstream_gates=dict(
            ocr_roi_identity_evaluated=False,
            control_pass_evaluated=False,
            production_promotion_allowed=False,
            promotion_status="REJECTED_DEFAULT_MODEL_PRESERVED",
        ),
    )

    baseline_model = YOLO(str(baseline_path))
    candidate_model = YOLO(str(candidate_file))

    for m_label, m_obj in [("baseline", baseline_model), ("candidate", candidate_model)]:
        m_classes = class_names(m_obj.names)
        if m_classes != names:
            raise ValueError(f"{m_label} class mapping mismatch: {m_classes} != {names}")

    for sp in splits:
        print(f"\n--- Evaluating split: {sp} ---")
        base_res = evaluate_model(baseline_model, dataset_yaml, sp, output, "baseline", names)
        cand_res = evaluate_model(candidate_model, dataset_yaml, sp, output, "candidate", names)

        report["results"][sp] = {
            "baseline": base_res,
            "candidate": cand_res,
        }
        report["deltas"][sp] = compute_deltas(base_res, cand_res)

    # Determine gate decision based on validation split (or test if val missing)
    primary_split = "val" if "val" in report["deltas"] else splits[0]
    pri_deltas = report["deltas"][primary_split]

    ball_map50_delta = pri_deltas["per_class"].get("ball", {}).get("map50", 0.0)
    ball_recall_delta = pri_deltas["per_class"].get("ball", {}).get("recall", 0.0)
    human_map50_delta = pri_deltas["per_class"].get("human", {}).get("map50", 0.0)
    rim_map50_delta = pri_deltas["per_class"].get("rim", {}).get("map50", 0.0)

    # Quality rules
    if ball_map50_delta > 0.01 and human_map50_delta >= -0.05 and rim_map50_delta >= -0.05:
        decision = "candidate_better"
        decision_reason = f"Ball mAP50 improved by {ball_map50_delta:+.4f} (recall {ball_recall_delta:+.4f}) without significant regression on human ({human_map50_delta:+.4f}) or rim ({rim_map50_delta:+.4f})."
    elif ball_map50_delta < -0.02 or human_map50_delta < -0.05 or rim_map50_delta < -0.05:
        decision = "candidate_regressed"
        decision_reason = f"Candidate regressed: ball {ball_map50_delta:+.4f}, human {human_map50_delta:+.4f}, rim {rim_map50_delta:+.4f}."
    else:
        decision = "inconclusive"
        decision_reason = f"Metrics within marginal variance: ball {ball_map50_delta:+.4f}, human {human_map50_delta:+.4f}, rim {rim_map50_delta:+.4f}."

    report["decision"] = decision
    report["decision_reason"] = decision_reason
    report["decision_split"] = primary_split
    report["status"] = "paired_detector_evaluation_complete"

    out_json = output / "comparison.json"
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nSaved paired comparison to {out_json}")
    print(f"Decision: {decision} ({decision_reason})")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--splits", nargs="+", default=["val", "test"])
    args = parser.parse_args()

    evaluate_paired(args.dataset, args.candidate, args.output, args.splits)
