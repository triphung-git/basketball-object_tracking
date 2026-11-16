"""Verify that the court calibration matches CourtConfig schema and calibrates with low residuals."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from basketball_scoreboard.court import CourtConfig, CourtModel

cfg_dict = {
    "schema_version": "2.0.0",
    "camera_id": "cam_main",
    "segment_id": "session_vietnam_tonga_dev",
    "source_video_hash": "8fd370b0668860a5c70d56bf256c76e3783bc1fe6598b529944ad00ca0616b45",
    "original_image_wh": [1920, 1080],
    "status": "validated",
    "is_synthetic": False,
    "reference_frame_index": 0,
    "reference_pts_s": 0.0,
    "court_coordinate_system": {
        "origin": "basket_center_floor",
        "axes": {"x_positive": "right", "y_positive": "towards_half_court"},
        "units": "meters",
        "court_bounds": {"x_min": -7.5, "x_max": 7.5, "y_min": 0.0, "y_max": 11.0},
        "scale_factor": 1.0,
        "scale_status": "verified_meters",
    },
    "point_correspondences": [
        {
            "point_id": "P1_key_baseline_left",
            "name": "Key baseline left corner",
            "image_xy": [510.0, 617.0],
            "court_xy": [-2.45, 0.0],
            "is_coplanar": True,
            "usage": "fit",
        },
        {
            "point_id": "P2_key_baseline_right",
            "name": "Key baseline right corner",
            "image_xy": [916.0, 542.0],
            "court_xy": [2.45, 0.0],
            "is_coplanar": True,
            "usage": "fit",
        },
        {
            "point_id": "P3_key_ft_left",
            "name": "Key free-throw left corner",
            "image_xy": [862.0, 809.0],
            "court_xy": [-2.45, 5.80],
            "is_coplanar": True,
            "usage": "fit",
        },
        {
            "point_id": "P4_key_ft_right",
            "name": "Key free-throw right corner",
            "image_xy": [1318.0, 667.0],
            "court_xy": [2.45, 5.80],
            "is_coplanar": True,
            "usage": "fit",
        },
        {
            "point_id": "C1_ft_center",
            "name": "Free-throw line center",
            "image_xy": [1119.0, 729.0],
            "court_xy": [0.0, 5.80],
            "is_coplanar": True,
            "usage": "check",
        },
        {
            "point_id": "C2_arc_apex",
            "name": "2PT Arc Apex",
            "image_xy": [1390.0, 836.0],
            "court_xy": [0.0, 8.325],
            "is_coplanar": True,
            "usage": "check",
        },
        {
            "point_id": "B0_rim_floor",
            "name": "Rim Floor Projection",
            "image_xy": [815.0, 609.0],
            "court_xy": [0.0, 1.575],
            "is_coplanar": True,
            "usage": "check",
        },
    ],
    "court_roi_image": [
        [17.0, 706.0],
        [510.0, 617.0],
        [916.0, 542.0],
        [1165.0, 496.0],
        [1542.0, 658.0],
        [1390.0, 836.0],
        [60.0, 842.0],
    ],
    "provenance": {
        "review_status": "approved",
        "reviewed_by": "user_triphung",
        "reviewed_utc": "2026-11-15T15:19:00Z",
        "review_notes": "Court calibration landmarks approved by user",
    },
    "thresholds": {
        "max_reprojection_error_px": 25.0,
    },
}

cfg = CourtConfig.from_dict(cfg_dict)
model = CourtModel(cfg)
res = model.calibrate(allow_uncalibrated=False)
print("Calibrated successfully in production mode!")
print("Fit residuals px:", res.fit_residuals_px)
print("Check residuals px:", res.check_residuals_px)
print("Mean fit residual px:", res.mean_fit_residual_px)
print("Max fit residual px:", res.max_fit_residual_px)
print("Mean check residual px:", res.mean_check_residual_px)
print("Condition number:", res.condition_number)

# Save the standard CourtConfig JSON to configs/courts/vt_development_court.json
out_file = ROOT / "configs" / "courts" / "vt_development_court.json"
out_file.parent.mkdir(parents=True, exist_ok=True)
out_file.write_text(cfg.to_json(), encoding="utf-8")
print(f"Saved CourtConfig to {out_file}")
