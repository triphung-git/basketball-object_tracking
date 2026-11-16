"""CLI entrypoint for shared production evaluator (evaluate_v2.py).

Evaluates PTS, REB, and AST predictions against ground truth using
maximum cardinality min-cost bipartite matching, and exports
evaluation_summary.json, match_table.json, matched_events.csv, and error_index.json.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from basketball_scoreboard.evaluator_v2 import (
    EvaluatorV2Protocol,
    ProductionEvaluatorV2,
    export_evaluation_bundle,
    load_ground_truth,
    load_predictions_from_bundle,
)
from basketball_scoreboard.evaluation_scope import normalize_scope, validate_prediction_binding


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--predictions",
        "-p",
        type=Path,
        required=True,
        help="Path to prediction file (events_auto.jsonl/shots_auto.jsonl) or run bundle directory.",
    )
    parser.add_argument(
        "--ground-truth",
        "-g",
        type=Path,
        required=True,
        help="Path to ground truth dataset v2 directory, annotations folder, or review JSON file.",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=ROOT / "outputs" / "evaluation_v2",
        help="Directory to write evaluation artifacts.",
    )
    parser.add_argument(
        "--stats",
        type=str,
        default="pts,reb,ast",
        help="Comma-separated stats to evaluate (pts,reb,ast). Default: pts,reb,ast",
    )
    parser.add_argument(
        "--protocol-config",
        type=Path,
        default=None,
        help="Optional path to custom protocol config JSON.",
    )
    parser.add_argument(
        "--diagnostic",
        action="store_true",
        help="Enable diagnostic mode for unreviewed/draft/synthetic evaluations.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress console metric tables.",
    )
    parser.add_argument("--evaluation-scope", type=Path,
                        help="Explicit source hash, timeline, interval and clip-to-parent mapping JSON")

    args = parser.parse_args()

    # Protocol config
    protocol_kwargs = {}
    if args.protocol_config:
        try:
            with args.protocol_config.open(encoding="utf-8") as handle:
                cfg = json.load(handle)
                protocol_kwargs.update(cfg)
        except Exception as exc:
            print(f"Error loading protocol config: {exc}", file=sys.stderr)
            return 1

    try:
        protocol = EvaluatorV2Protocol(**protocol_kwargs)
    except (TypeError, ValueError) as exc:
        print(f"Error loading protocol: {exc}", file=sys.stderr)
        return 1
    evaluator = ProductionEvaluatorV2(protocol=protocol)

    # Load predictions
    if not args.predictions.exists():
        print(f"Error: Predictions path not found: {args.predictions}", file=sys.stderr)
        return 1

    try:
        predictions = load_predictions_from_bundle(args.predictions)
    except Exception as exc:
        print(f"Error loading predictions: {exc}", file=sys.stderr)
        return 1

    # Load ground truth
    if not args.ground_truth.exists():
        print(f"Error: Ground truth path not found: {args.ground_truth}", file=sys.stderr)
        return 1

    try:
        gt_data, gt_meta = load_ground_truth(args.ground_truth)
    except Exception as exc:
        print(f"Error loading ground truth: {exc}", file=sys.stderr)
        return 1

    metadata = {
        "predictions_path": str(args.predictions.resolve()),
        "ground_truth_path": str(args.ground_truth.resolve()),
        "gt_metadata": gt_meta,
        "is_diagnostic": args.diagnostic or gt_meta.get("is_synthetic", False) or gt_meta.get("data_status") == "draft_unreviewed",
    }

    if args.evaluation_scope:
        try:
            scope = json.loads(args.evaluation_scope.read_text(encoding="utf-8"))
            if not args.predictions.is_dir():
                raise ValueError("Scoped evaluation requires a prediction run bundle")
            run = json.loads((args.predictions / "run.json").read_text(encoding="utf-8"))
            validate_prediction_binding(run, scope)
            predictions, pred_audit = normalize_scope(predictions, scope, predictions=True)
            gt_data, gt_audit = normalize_scope(gt_data, scope)
            metadata.update(evaluation_scope=scope, prediction_scope_audit=pred_audit,
                            ground_truth_scope_audit=gt_audit)
            metadata["is_diagnostic"] |= scope.get("coverage_status") != "fully_reviewed"
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"Error validating evaluation scope: {exc}", file=sys.stderr)
            return 1

    # Filter stats to evaluate
    selected_stats = [s.strip().lower() for s in args.stats.split(",") if s.strip()]

    # Run evaluation
    summary = evaluator.evaluate_all(predictions, gt_data, metadata=metadata)

    # Export bundle
    exported_paths = export_evaluation_bundle(summary, args.output_dir)

    if not args.quiet:
        print("=" * 70)
        print("BASKETBALL SCOREBOARD — PRA PRODUCTION EVALUATOR V2")
        print("=" * 70)
        print(f"Protocol:       {protocol.protocol_version}")
        print(f"Diagnostic:     {metadata['is_diagnostic']}")
        print(f"Predictions:    {args.predictions}")
        print(f"Ground Truth:   {args.ground_truth}")
        print("-" * 70)
        print(f"{'STAT':<6} | {'GT':<4} | {'PRED':<5} | {'DET P':<7} | {'DET R':<7} | {'DET F1':<7} | {'STRICT P':<8} | {'STRICT R':<8}")
        print("-" * 70)

        for stat_name in ("pts", "reb", "ast"):
            if stat_name not in selected_stats:
                continue
            st = summary["stats"][stat_name]
            det = st["detection"]
            strict = st["strict"]
            det_p = f"{det['precision']:.3f}" if det["precision"] is not None else "N/A"
            det_r = f"{det['recall']:.3f}" if det["recall"] is not None else "N/A"
            det_f1 = f"{det['f1']:.3f}" if det["f1"] is not None else "N/A"
            str_p = f"{strict['precision']:.3f}" if strict["precision"] is not None else "N/A"
            str_r = f"{strict['recall']:.3f}" if strict["recall"] is not None else "N/A"
            print(f"{stat_name.upper():<6} | {st['n_gt']:<4} | {st['n_pred']:<5} | {det_p:<7} | {det_r:<7} | {det_f1:<7} | {str_p:<8} | {str_r:<8}")

        print("-" * 70)
        comb = summary["combined_pra"]
        c_det = comb["detection"]
        c_str = comb["strict"]
        cd_p = f"{c_det['precision']:.3f}" if c_det["precision"] is not None else "N/A"
        cd_r = f"{c_det['recall']:.3f}" if c_det["recall"] is not None else "N/A"
        cd_f1 = f"{c_det['f1']:.3f}" if c_det["f1"] is not None else "N/A"
        cs_p = f"{c_str['precision']:.3f}" if c_str["precision"] is not None else "N/A"
        cs_r = f"{c_str['recall']:.3f}" if c_str["recall"] is not None else "N/A"
        print(f"{'TOTAL':<6} | {comb['total_events_gt']:<4} | {comb['total_events_pred']:<5} | {cd_p:<7} | {cd_r:<7} | {cd_f1:<7} | {cs_p:<8} | {cs_r:<8}")
        print("=" * 70)
        print(f"Total Errors Recorded: {len(summary['error_index'])}")
        print(f"Artifacts exported to: {args.output_dir.resolve()}")
        for k, p in exported_paths.items():
            print(f"  - {k}: {p.name}")
        print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
