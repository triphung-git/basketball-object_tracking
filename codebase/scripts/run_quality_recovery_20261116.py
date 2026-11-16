"""Prepare, run and compare an isolated 0..1000s diagnostic quality revision.

Keeps approved model/dataset/rules and historical 06A artifacts unchanged.
Fine-tuning is not started from unreviewed near-rim frames.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from basketball_scoreboard.evaluation_scope import normalize_scope, validate_prediction_binding
from basketball_scoreboard.evaluator_v2 import (
    EvaluatorV2Protocol, ProductionEvaluatorV2, export_evaluation_bundle,
    load_ground_truth, load_predictions_from_bundle,
)
from basketball_scoreboard.video import compute_file_sha256, probe_video


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def prepare_near_rim_review(output):
    """Audit approved supplementals; extract new frames as draft, never approved."""
    import cv2
    review = output / "near-rim-review"
    review.mkdir()
    mixed = ROOT / "data/finetune/task07a/mixed-20261108"
    manifest = json.loads((mixed / "manifest.json").read_text(encoding="utf-8"))
    near_rim = []
    for sample in manifest["supplemental"]:
        rows = [[float(v) for v in line.split()] for line in Path(sample["label"]).read_text().splitlines() if line.strip()]
        balls, rims = [r for r in rows if int(r[0]) == 0], [r for r in rows if int(r[0]) == 2]
        if any(abs(b[1] - r[1]) <= 2 * r[3] and abs(b[2] - r[2]) <= 3 * r[4]
               for b in balls for r in rims):
            near_rim.append({"sample_id": sample["sample_id"], "image": sample["image"],
                             "label": sample["label"], "occlusion_review_status": "not_recorded"})
    clip = ROOT / "outputs/task07-vietnam-tonga-segments-20261104/media/vt_development.mp4"
    cap = cv2.VideoCapture(str(clip))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not cap.isOpened() or abs(fps - 30) > 0.01:
        raise ValueError("Review extraction requires the verified 30 FPS development clip")
    clip_hash = compute_file_sha256(clip)
    frames = []
    for index in (108, 115, 123, 744, 754, 769, 780, 789):
        cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, image = cap.read()
        if not ok:
            raise ValueError(f"Cannot read review frame {index}")
        actual = int(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
        if actual != index:
            raise ValueError("Review frame seek mismatch")
        name = f"frame-{index:05d}.jpg"
        if not cv2.imwrite(str(review / name), image):
            raise OSError("Cannot write review image")
        frames.append({"sample_id": f"near_rim_{index}", "image": name,
                       "image_sha256": compute_file_sha256(review / name),
                       "source_clip_sha256": clip_hash, "frame_index": index,
                       "clip_time_s": index / fps, "parent_time_s": 300 + index / fps,
                       "review_status": "draft", "ball_bbox_xyxy": None,
                       "ball_visibility": "needs_review", "rim_bbox_xyxy": None,
                       "human_boxes_reviewed": False})
    cap.release()
    audit = {"status": "PENDING_LABEL_REVIEW", "training_authorized_by_user": True,
             "training_started": False, "approved_supplemental_count": len(manifest["supplemental"]),
             "near_rim_spatial_candidates_in_approved_data": near_rim,
             "limitation": "Spatial proximity does not certify partial occlusion or missing-ball labels; no new bbox approval is inferred.",
             "draft_frames": frames,
             "required_before_training": ["Review ball visibility and bbox on each extracted frame",
                                          "Review complete human/rim/ball labels before mixed-data export",
                                          "Keep source-family separation and evaluate on held-out reviewed near-rim samples"]}
    write_json(review / "packet.json", audit)
    (review / "README.md").write_text(
        "# Near-rim label review\n\nTraining is authorized; labels are not automatically approved. "
        "Review the eight source frames in packet.json. Record visible/partially_occluded/"
        "fully_occluded/uncertain, tight visible ball bbox when justified, and complete "
        "human/rim labels. Fully hidden balls are not invented bounding boxes. "
        "New data must retain draft status until review. Original datasets are unchanged.\n\n" +
        "\n".join(f"- [{r['sample_id']}]({r['image']}) — parent {r['parent_time_s']:.3f}s" for r in frames),
        encoding="utf-8")
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise ValueError("Choose a new output directory")
    output.mkdir(parents=True)
    state_path = output / "status.json"
    state = {"schema_version": "quality-recovery-20261116-v1", "pid": os.getpid(),
             "started_utc": datetime.now(timezone.utc).isoformat(),
             "status": "preparing", "quality_gate": "NOT_EVALUATED",
             "historical_06A_preserved": True, "default_model_preserved": True,
             "independent_holdout": False}

    def update(status, **extra):
        state.update(status=status, updated_utc=datetime.now(timezone.utc).isoformat(), **extra)
        write_json(state_path, state)

    started = time.perf_counter()
    try:
        scope = json.loads((ROOT / "configs/evaluation/vietnam-tonga-parent-1000s-20261116.json").read_text(encoding="utf-8"))
        source = ROOT / "assets_test/vietnam-tonga.mp4"
        actual_hash = compute_file_sha256(source)
        if actual_hash != scope["source_sha256"]:
            raise ValueError("Unexpected source video hash")
        meta = probe_video(source)
        if meta.duration_s < scope["end_time_s"]:
            raise ValueError("Source is shorter than requested range")
        for clip_id, mapping in scope["video_mappings"].items():
            child = ROOT / "outputs/task07-vietnam-tonga-segments-20261104/media" / f"{clip_id}.mp4"
            if compute_file_sha256(child) != mapping["source_clip_sha256"]:
                raise ValueError("Clip provenance does not match timeline mapping")
        gt, gt_meta = load_ground_truth(ROOT / "data/v2")
        reviews = list(csv.DictReader((ROOT / "data/v2/annotations/reviews.csv").open(encoding="utf-8-sig")))
        approved = {(r["table_name"], r["record_id"]) for r in reviews if r["review_status"] == "approved"}
        for stat, table, id_key in (("pts", "shots", "shot_id"), ("reb", "rebounds", "rebound_id"), ("ast", "assists", "assist_id")):
            gt[stat] = [r for r in gt[stat] if (table, r[id_key]) in approved]
        normalized_gt, audit = normalize_scope(gt, scope)
        write_json(output / "scope.json", scope)
        write_json(output / "normalized-ground-truth.json", {"ground_truth": normalized_gt,
                   "source_metadata": gt_meta, "audit": audit, "review_status": "derived_from_approved_records"})
        training = prepare_near_rim_review(output)
        hashes = {str(p.relative_to(ROOT)): compute_file_sha256(p)
                  for directory in (ROOT / "src", ROOT / "configs")
                  for p in sorted(directory.rglob("*"))
                  if p.is_file() and "__pycache__" not in p.parts}
        for name in ("run_quality_recovery_20261116.py", "run_demo.py", "evaluate_v2.py"):
            script = ROOT / "scripts" / name
            hashes[str(script.relative_to(ROOT))] = compute_file_sha256(script)
        write_json(output / "source-snapshot.json", hashes)
        write_json(output / "preflight.json", {"source": meta.to_dict(), "scope": scope,
                   "gt_counts": {k: len(v) for k, v in normalized_gt.items()}, "scope_audit": audit,
                   "gt_made_scoring_events": sum(r.get("result") == "made" for r in normalized_gt["pts"]),
                   "source_sha256": actual_hash, "disk_free_bytes": shutil.disk_usage(output).free,
                   "training_status": training["status"],
                   "limitations": ["Same-match exposed diagnostic", "No exhaustive GT coverage outside reviewed intervals",
                                   "Development calibration is not reused across full broadcast cameras",
                                   "Existing continuous path has incomplete OCR and heatmap integration"]})
        if not args.execute:
            update("prepared", training_status=training["status"])
            print(json.dumps(state, ensure_ascii=False))
            return 0
        if shutil.disk_usage(output).free < 4 * 1024**3:
            raise OSError("Insufficient free disk for a long trace-producing run")
        from basketball_scoreboard.continuous_orchestration import run_continuous_orchestration

        def progress(values):
            values["estimated_remaining_s"] = ((scope["end_time_s"] - values["source_time_s"]) *
                values["elapsed_s"] / max(values["source_time_s"], 0.1))
            update("inference_running", **values)
            if values["frames_processed"] == 1 or values["frames_processed"] % 300 == 0:
                print(json.dumps({"status": "inference_running", **values}), flush=True)

        update("initializing_inference", training_status=training["status"])
        result = run_continuous_orchestration(
            video_path=source, output_dir=output / "video-run",
            roster_config_path=ROOT / "configs/rosters/vietnam_tonga.json",
            allow_uncalibrated=True, start_time_s=scope["start_time_s"],
            end_time_s=scope["end_time_s"], progress_callback=progress, quiet=True)
        if result["status"] not in ("completed", "partial"):
            raise RuntimeError("Video inference did not complete")
        validate_prediction_binding(result, scope)
        predictions = load_predictions_from_bundle(output / "video-run")
        predictions, pred_audit = normalize_scope(predictions, scope, predictions=True)
        old_protocol = EvaluatorV2Protocol()
        revision = EvaluatorV2Protocol(**json.loads((ROOT / "configs/evaluation/pra-basket-primary-20261116.json").read_text()))
        comparison = {}
        for name, protocol in (("original-protocol", old_protocol), ("basket-primary-revision", revision)):
            summary = ProductionEvaluatorV2(protocol).evaluate_all(predictions, normalized_gt, metadata={
                "is_diagnostic": True, "evaluation_scope": scope, "prediction_scope_audit": pred_audit,
                "independent_holdout": False, "coverage_status": scope["coverage_status"]})
            export_evaluation_bundle(summary, output / name)
            comparison[name] = {stat: summary["stats"][stat]["strict"] for stat in ("pts", "reb", "ast")}
        write_json(output / "protocol-comparison.json", comparison)
        update("diagnostic_complete", elapsed_s=time.perf_counter() - started,
               quality_gate="NOT_ACCEPTED_SPARSE_EXPOSED_DATA", training_status=training["status"])
        return 0
    except Exception as exc:
        update("failed", error_type=type(exc).__name__, error=str(exc), elapsed_s=time.perf_counter() - started)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
