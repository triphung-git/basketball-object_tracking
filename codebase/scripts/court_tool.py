#!/usr/bin/env python3
"""CLI tool for validating court configuration and generating calibration previews."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Ensure codebase/src is importable
current_dir = os.path.dirname(os.path.abspath(__file__))
codebase_dir = os.path.dirname(current_dir)
src_dir = os.path.join(codebase_dir, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from basketball_scoreboard.court import (
    CourtConfig,
    CourtModel,
    DegenerateGeometryError,
    UncalibratedCourtError,
)


def validate_court_config(
    config_path: str,
    allow_uncalibrated: bool = False,
    preview_output: Optional[str] = None,
    background_image_path: Optional[str] = None,
) -> int:
    """Validate a court config file and optionally render a preview."""
    if not os.path.isfile(config_path):
        print(f"[ERROR] Config file not found: {config_path}", file=sys.stderr)
        return 1
    if preview_output and Path(preview_output).exists():
        print("[ERROR] Refusing to overwrite preview output",file=sys.stderr)
        return 1

    try:
        config = CourtConfig.from_json_file(config_path)
    except Exception as e:
        print(f"[ERROR] Failed to parse court config: {e}", file=sys.stderr)
        return 1

    print(f"=== Validating Court Config: {config.camera_id} ===")
    print(f"Schema Version  : {config.schema_version}")
    print(f"Segment ID      : {config.segment_id}")
    print(f"Status          : {config.status} (synthetic: {config.is_synthetic})")
    print(f"Image WH        : {config.original_image_wh}")
    print(f"Court Units     : {config.court_coordinate_system.units} ({config.court_coordinate_system.scale_status})")
    print(f"Bounds          : {config.court_coordinate_system.court_bounds}")
    print(f"Correspondences : {len(config.point_correspondences)} total")

    model = CourtModel(config)
    try:
        homography = model.calibrate(allow_uncalibrated=allow_uncalibrated)
        print("\n[SUCCESS] Homography solved successfully.")
        print(f"Condition Number : {homography.condition_number:.2e}")
        print(f"Mean Fit Residual: {homography.mean_fit_residual_px:.2f} px (Max: {homography.max_fit_residual_px:.2f} px)")
        if homography.check_residuals_px is not None:
            print(f"Mean Check Residual: {homography.mean_check_residual_px:.2f} px ({len(homography.check_residuals_px)} check points)")
    except UncalibratedCourtError as e:
        print(f"\n[WARNING / PENDING] {e}")
        if not allow_uncalibrated:
            print("[NOTICE] To validate draft/template geometry math without approval, pass --allow-uncalibrated.")
            return 2
    except DegenerateGeometryError as e:
        print(f"\n[ERROR] Degenerate geometry: {e}", file=sys.stderr)
        return 3
    except Exception as e:
        print(f"\n[ERROR] Unexpected calibration error: {e}", file=sys.stderr)
        return 4

    # Optional headless preview render
    if preview_output:
        os.makedirs(os.path.dirname(os.path.abspath(preview_output)), exist_ok=True)
        w, h = config.original_image_wh
        fig, ax = plt.subplots(figsize=(10, 8), dpi=150)

        # Background
        if background_image_path and os.path.isfile(background_image_path):
            img = cv2.imread(background_image_path)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            ax.imshow(img)
        else:
            # Draw synthetic canvas
            ax.set_facecolor("#1e1e1e")
            ax.set_xlim(0, w)
            ax.set_ylim(h, 0)  # Invert y for image coordinates

        # Draw ROI polygon
        if config.court_roi_image:
            roi_np = np.array(config.court_roi_image)
            roi_closed = np.vstack([roi_np, roi_np[0]])
            ax.plot(roi_closed[:, 0], roi_closed[:, 1], "cyan", linestyle="--", linewidth=2, label="Court ROI")

        # Draw correspondences
        for pt in config.point_correspondences:
            px, py = pt.image_xy
            color = "lime" if pt.usage == "fit" else "yellow"
            marker = "o" if pt.is_coplanar else "x"
            ax.plot(px, py, marker=marker, color=color, markersize=8)
            ax.text(px + 15, py - 10, f"{pt.point_id}\n({pt.court_xy[0]},{pt.court_xy[1]})", color="white", fontsize=8, bbox=dict(boxstyle="round,pad=0.2", facecolor="black", alpha=0.6))

        if model.is_calibrated:
            bounds=config.court_coordinate_system.court_bounds
            for x in np.linspace(bounds['x_min'],bounds['x_max'],6):
                points=[model.project_court_to_image((x,y)) for y in np.linspace(bounds['y_min'],bounds['y_max'],30)]
                points=[p for p in points if p is not None]
                if points:
                    ax.plot(*np.array(points).T,color='white',alpha=.25,linewidth=.6)
            for y in np.linspace(bounds['y_min'],bounds['y_max'],6):
                points=[model.project_court_to_image((x,y)) for x in np.linspace(bounds['x_min'],bounds['x_max'],30)]
                points=[p for p in points if p is not None]
                if points:
                    ax.plot(*np.array(points).T,color='white',alpha=.25,linewidth=.6)
        label='DIAGNOSTIC / SYNTHETIC' if allow_uncalibrated else 'CALIBRATION PREVIEW'
        ax.set_title(f"{label}: {config.camera_id} [{config.status}]", fontsize=12)
        ax.set_xlabel("Image X (px)")
        ax.set_ylabel("Image Y (px)")
        ax.legend(loc="upper right")
        plt.tight_layout()
        plt.savefig(preview_output, dpi=150)
        plt.close(fig)
        print(f"[PREVIEW] Saved calibration preview to: {preview_output}")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Basketball Court Configuration & Homography Tool")
    parser.add_argument("--config", required=True, help="Path to court config JSON")
    parser.add_argument("--allow-uncalibrated", action="store_true", help="Allow solving draft/synthetic configs without production validation")
    parser.add_argument("--preview", help="Path to save preview visualization PNG")
    parser.add_argument("--background", help="Optional background video frame image")

    args = parser.parse_args()
    exit_code = validate_court_config(
        config_path=args.config,
        allow_uncalibrated=args.allow_uncalibrated,
        preview_output=args.preview,
        background_image_path=args.background,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

