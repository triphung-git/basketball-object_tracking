#!/usr/bin/env python3
"""Assemble the complete demo bundle with manifest and checksum verification (Task D10)."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
DEMO_RUN_DIR = ROOT / "outputs/demo-completion-20261116"
BUNDLE_DIR = DEMO_RUN_DIR / "demo-bundle-qa-v2"
sys.path.insert(0, str(ROOT / "src"))
from basketball_scoreboard.demo_bundle import summarize_run, verify_bundle_manifest


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=BUNDLE_DIR)
    parser.add_argument("--run-dir", type=Path, required=True, help="Completed run with matching annotated.mp4")
    args = parser.parse_args(argv)
    run_dir = args.run_dir.resolve()
    bundle_dir = args.output.resolve()
    if bundle_dir.exists():
        print(f"Error: Output directory already exists: {bundle_dir}. Overwrite prohibited.", file=sys.stderr)
        return 1
    print(f"=== Assembling Demo Bundle ===")
    print(f"Target bundle dir: {bundle_dir}")
    # 1. Source mappings
    files_to_copy = [
        # D08 Video overlay
        (run_dir / "annotated.mp4", bundle_dir / "annotated.mp4", "Video overlay from the selected run with normalized playback timestamps"),
        (DEMO_RUN_DIR / "D08/screenshots/01_desktop_dashboard.png", bundle_dir / "screenshots/01_desktop_dashboard.png", "Desktop dashboard screenshot (1280x800)"),
        (DEMO_RUN_DIR / "D08/screenshots/02_mobile_dashboard.png", bundle_dir / "screenshots/02_mobile_dashboard.png", "Mobile dashboard screenshot (375x812)"),
        (DEMO_RUN_DIR / "D08/browser_qa_report.json", bundle_dir / "browser_qa_report.json", "Headless Chrome automated browser QA report"),

        # D05 Execution artifacts
        (run_dir / "boxscore_auto.csv", bundle_dir / "boxscore_auto.csv", "Automatic FIBA 3x3 box score export"),
        (run_dir / "events_auto.jsonl", bundle_dir / "events_auto.jsonl", "Automatic event proposals and confirmed events; inspect status before counting"),
        (run_dir / "events_raw.jsonl", bundle_dir / "events_raw.jsonl", "Raw transaction events log"),
        (run_dir / "audit_trail.jsonl", bundle_dir / "audit_trail.jsonl", "Audit trail of ledger mutations"),
        (run_dir / "shots_auto.jsonl", bundle_dir / "shots_auto.jsonl", "Temporal shot FSM candidates and confirmed shots"),
        (run_dir / "ball_tracks.jsonl", bundle_dir / "ball_tracks.jsonl", "Ball trajectory tracking records"),
        (run_dir / "ball_control.jsonl", bundle_dir / "ball_control.jsonl", "Ball possession and proximity records"),
        (run_dir / "possession_control.jsonl", bundle_dir / "possession_control.jsonl", "Possession transition records"),
        (run_dir / "trajectories.jsonl", bundle_dir / "trajectories.jsonl", "Player metric court trajectories"),
        (run_dir / "identity_mappings.json", bundle_dir / "identity_mappings.json", "Player identity and jersey number mappings"),
        (run_dir / "jersey_evidence.json", bundle_dir / "jersey_evidence.json", "Raw OCR jersey evidence"),
        (run_dir / "heatmap.png", bundle_dir / "heatmap.png", "Accumulated player court occupancy heatmap (total)"),
        (run_dir / "heatmap_team_a.png", bundle_dir / "heatmap_team_a.png", "Team A (Việt Nam) court heatmap"),
        (run_dir / "heatmap_team_b.png", bundle_dir / "heatmap_team_b.png", "Team B (Tonga) court heatmap"),
        (run_dir / "heatmap_raw_grid.json", bundle_dir / "heatmap_raw_grid.json", "Raw metric 2D grid matrix of court occupancy"),
        (run_dir / "heatmap_summary.json", bundle_dir / "heatmap_summary.json", "Summary mass and coverage metrics of court heatmap"),
        (run_dir / "run.json", bundle_dir / "run.json", "Full continuous orchestration run configuration and state"),
        (run_dir / "checkpoint.json", bundle_dir / "checkpoint.json", "Task 05 / D05 ledger checkpoint"),

        (run_dir / "pass_events.jsonl", bundle_dir / "pass_events.jsonl", "Observed pass proposals; may be empty"),
        # D07 Evaluation
        (DEMO_RUN_DIR / "D07/evaluation/evaluation_summary.json", bundle_dir / "evaluation_summary.json", "Production evaluator v2 metrics and audit scope"),
        (DEMO_RUN_DIR / "D07/evaluation/error_index.json", bundle_dir / "error_index.json", "Bipartite match error index and diagnostic catalog"),

        # D09 Benchmark
        (DEMO_RUN_DIR / "D09/benchmark/benchmark.json", bundle_dir / "benchmark.json", "Dual-profile performance benchmark summary"),
    ]

    missing = [str(src) for src, _, _ in files_to_copy if not src.is_file()]
    if missing:
        print("Error: Required source files missing: " + ", ".join(missing), file=sys.stderr)
        return 1
    bundle_dir.mkdir(parents=True, exist_ok=False)
    (bundle_dir / "screenshots").mkdir()
    manifest_entries = []
    for src, dst, desc in files_to_copy:
        if not src.is_file():
            print(f"Error: Required source file missing: {src}", file=sys.stderr)
            return 1
        shutil.copy2(src, dst)
        size_bytes = dst.stat().st_size
        file_hash = sha256_file(dst)
        rel_path = dst.relative_to(bundle_dir).as_posix()
        manifest_entries.append({
            "path": rel_path,
            "bytes": size_bytes,
            "sha256": file_hash,
            "description": desc,
        })
        print(f"  + Bundled: {rel_path} ({size_bytes} bytes)")

    # 2. Build summary.json if not present
    summary_dst = bundle_dir / "summary.json"
    run_json_path = bundle_dir / "run.json"
    if run_json_path.is_file():
        run_data = json.loads(run_json_path.read_text(encoding="utf-8"))
        heatmap = json.loads((bundle_dir / "heatmap_summary.json").read_text(encoding="utf-8"))
        summary_payload = summarize_run(run_data, heatmap)
        summary_dst.write_text(json.dumps(summary_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        manifest_entries.append({
            "path": "summary.json",
            "bytes": summary_dst.stat().st_size,
            "sha256": sha256_file(summary_dst),
            "description": "Unified high-level run summary for dashboard and reporting",
        })
        print(f"  + Bundled: summary.json ({summary_dst.stat().st_size} bytes)")

    # 3. Write manifest.json
    manifest_data = {
        "schema_version": "demo-bundle-manifest-v1",
        "bundle_id": bundle_dir.name,
        "source_run_dir": str(run_dir),
        "related_evidence_scope": "evaluation_summary/error_index are historical long-run diagnostics; benchmark and screenshots are historical separate runs, not measurements of this bundle",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "total_files": len(manifest_entries),
        "total_bytes": sum(e["bytes"] for e in manifest_entries),
        "files": sorted(manifest_entries, key=lambda x: x["path"]),
    }
    manifest_dst = bundle_dir / "manifest.json"
    manifest_dst.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    verify_bundle_manifest(bundle_dir)
    print(f"\nManifest successfully created: {manifest_dst}")
    print(f"Total files: {len(manifest_entries)}, Total size: {manifest_data['total_bytes'] / (1024*1024):.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
