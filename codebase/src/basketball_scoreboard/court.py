"""Court geometry, calibration config, homography projection, and trajectory contracts (v2)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import hashlib
import math
import os
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np


class CourtError(Exception):
    """Base error for court geometry and calibration."""
    pass


class UncalibratedCourtError(CourtError):
    """Raised when uncalibrated or draft court config is used in calibrated mode."""
    pass


class DegenerateGeometryError(CourtError):
    """Raised when point correspondences are collinear, degenerate, or insufficient."""
    pass


class ProjectionError(CourtError):
    """Raised when projection fails (e.g. near-zero projective denominator)."""
    pass


@dataclass
class PointCorrespondence:
    """A pair of corresponding points between original image space and court coordinate space."""
    point_id: str
    name: str
    image_xy: Tuple[float, float]
    court_xy: Tuple[float, float]
    is_coplanar: bool = True
    usage: str = "fit"  # "fit" or "check"
    uncertainty_px: float = 0.0
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.point_id:
            raise ValueError("point_id must be non-empty")
        if len(self.image_xy) != 2 or not all(math.isfinite(v) for v in self.image_xy):
            raise ValueError(f"image_xy must contain 2 finite numbers: {self.image_xy}")
        if len(self.court_xy) != 2 or not all(math.isfinite(v) for v in self.court_xy):
            raise ValueError(f"court_xy must contain 2 finite numbers: {self.court_xy}")
        self.image_xy = (float(self.image_xy[0]), float(self.image_xy[1]))
        self.court_xy = (float(self.court_xy[0]), float(self.court_xy[1]))
        if self.usage not in {"fit", "check"}:
            raise ValueError(f"usage must be 'fit' or 'check', got: {self.usage}")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PointCorrespondence:
        return cls(
            point_id=str(data["point_id"]),
            name=str(data.get("name", "")),
            image_xy=tuple(data["image_xy"]),  # type: ignore
            court_xy=tuple(data["court_xy"]),  # type: ignore
            is_coplanar=bool(data.get("is_coplanar", True)),
            usage=str(data.get("usage", "fit")),
            uncertainty_px=float(data.get("uncertainty_px", 0.0)),
            notes=str(data.get("notes", "")),
        )


@dataclass
class CourtCoordinateSystem:
    """Definition of court floor plane coordinate system."""
    origin: str  # e.g. "court_center", "basket_center_floor", "top_left"
    axes: Dict[str, str]  # e.g. {"x_positive": "right", "y_positive": "towards_basket"}
    units: str  # "meters", "normalized", "feet"
    court_bounds: Dict[str, float]  # x_min, x_max, y_min, y_max
    scale_factor: Optional[float] = None
    scale_status: str = "uncalibrated"  # "uncalibrated", "verified_meters", "normalized_0_1"

    def __post_init__(self) -> None:
        req_keys = {"x_min", "x_max", "y_min", "y_max"}
        if not req_keys.issubset(self.court_bounds.keys()):
            raise ValueError(f"court_bounds missing required keys: {req_keys - set(self.court_bounds.keys())}")
        if not all(math.isfinite(self.court_bounds[k]) for k in req_keys):
            raise ValueError("Court bounds must be finite")
        if self.units not in {"meters","normalized","feet"}:
            raise ValueError("Unknown court coordinate units")
        if self.scale_factor is not None and (not math.isfinite(self.scale_factor) or self.scale_factor <= 0):
            raise ValueError("Scale factor must be finite and positive")
        if self.court_bounds["x_max"] <= self.court_bounds["x_min"]:
            raise ValueError(f"Invalid x bounds: x_max <= x_min ({self.court_bounds})")
        if self.court_bounds["y_max"] <= self.court_bounds["y_min"]:
            raise ValueError(f"Invalid y bounds: y_max <= y_min ({self.court_bounds})")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CourtCoordinateSystem:
        return cls(
            origin=str(data.get("origin", "basket_center_floor")),
            axes=dict(data.get("axes", {"x_positive": "right", "y_positive": "up"})),
            units=str(data.get("units", "normalized")),
            court_bounds={k: float(v) for k, v in data["court_bounds"].items()},
            scale_factor=float(data["scale_factor"]) if data.get("scale_factor") is not None else None,
            scale_status=str(data.get("scale_status", "uncalibrated")),
        )


@dataclass
class HomographyResult:
    """Homography transformation matrices and residual diagnostics."""
    H_image_to_court: List[List[float]]
    H_court_to_image: List[List[float]]
    fit_residuals_px: List[float]
    mean_fit_residual_px: float
    max_fit_residual_px: float
    check_residuals_px: Optional[List[float]] = None
    mean_check_residual_px: Optional[float] = None
    inlier_mask: List[bool] = field(default_factory=list)
    condition_number: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def matrix_image_to_court(self) -> np.ndarray:
        return np.array(self.H_image_to_court, dtype=np.float64)

    @property
    def matrix_court_to_image(self) -> np.ndarray:
        return np.array(self.H_court_to_image, dtype=np.float64)


@dataclass
class CourtConfig:
    """Versioned court geometry and camera calibration configuration."""
    schema_version: str
    camera_id: str
    segment_id: str
    original_image_wh: Tuple[int, int]
    status: str  # "template", "draft", "validated"
    court_coordinate_system: CourtCoordinateSystem
    point_correspondences: List[PointCorrespondence] = field(default_factory=list)
    court_roi_image: List[Tuple[float, float]] = field(default_factory=list)
    court_roi_court: Optional[List[Tuple[float, float]]] = None
    source_video_hash: Optional[str] = None
    reference_frame_index: Optional[int] = None
    reference_pts_s: Optional[float] = None
    sub_zones: Dict[str, Any] = field(default_factory=dict)
    thresholds: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)
    is_synthetic: bool = False

    def __post_init__(self) -> None:
        if len(self.original_image_wh) != 2 or any(d <= 0 for d in self.original_image_wh):
            raise ValueError(f"original_image_wh must be positive dimensions: {self.original_image_wh}")
        self.original_image_wh = (int(self.original_image_wh[0]), int(self.original_image_wh[1]))
        if self.status not in {"template", "draft", "validated"}:
            raise ValueError(f"Unknown court config status: {self.status}")
        if not self.schema_version or not self.camera_id or not self.segment_id or not isinstance(self.is_synthetic,bool):
            raise ValueError("Court identifiers/version and boolean synthetic status required")
        for polygon in (self.court_roi_image,self.court_roi_court):
            if polygon and (len(polygon) < 3 or any(len(p) != 2 or not all(math.isfinite(v) for v in p) for p in polygon)
                            or abs(cv2.contourArea(np.array(polygon,dtype=np.float32))) < 1e-6):
                raise ValueError("Invalid/degenerate court ROI polygon")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "camera_id": self.camera_id,
            "segment_id": self.segment_id,
            "source_video_hash": self.source_video_hash,
            "original_image_wh": list(self.original_image_wh),
            "status": self.status,
            "is_synthetic": self.is_synthetic,
            "reference_frame_index": self.reference_frame_index,
            "reference_pts_s": self.reference_pts_s,
            "court_coordinate_system": self.court_coordinate_system.to_dict(),
            "point_correspondences": [p.to_dict() for p in self.point_correspondences],
            "court_roi_image": [list(pt) for pt in self.court_roi_image],
            "court_roi_court": [list(pt) for pt in self.court_roi_court] if self.court_roi_court else None,
            "sub_zones": self.sub_zones,
            "thresholds": self.thresholds,
            "provenance": self.provenance,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CourtConfig:
        if not isinstance(data.get("is_synthetic",False),bool):
            raise ValueError("is_synthetic must be a JSON boolean")
        coord_sys = CourtCoordinateSystem.from_dict(data["court_coordinate_system"])
        correspondences = [
            PointCorrespondence.from_dict(p)
            for p in data.get("point_correspondences", [])
        ]
        roi_img = [tuple(pt) for pt in data.get("court_roi_image", [])]  # type: ignore
        roi_court = [tuple(pt) for pt in data["court_roi_court"]] if data.get("court_roi_court") else None  # type: ignore
        return cls(
            schema_version=str(data.get("schema_version", "2.0.0")),
            camera_id=str(data["camera_id"]),
            segment_id=str(data.get("segment_id", "default")),
            source_video_hash=data.get("source_video_hash"),
            original_image_wh=tuple(data["original_image_wh"]),  # type: ignore
            status=str(data.get("status", "draft")),
            is_synthetic=bool(data.get("is_synthetic", False)),
            reference_frame_index=data.get("reference_frame_index"),
            reference_pts_s=data.get("reference_pts_s"),
            court_coordinate_system=coord_sys,
            point_correspondences=correspondences,
            court_roi_image=roi_img,
            court_roi_court=roi_court,
            sub_zones=dict(data.get("sub_zones", {})),
            thresholds=dict(data.get("thresholds", {})),
            provenance=dict(data.get("provenance", {})),
        )

    @classmethod
    def from_json_file(cls, path: str) -> CourtConfig:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


@dataclass
class TrajectoryObservation:
    """Contract for a single spatial observation on video and projected court coordinates."""
    schema_version: str
    observation_id: str
    source_run_id: str
    video_id: str
    source_fingerprint_sha256: str
    frame_index: int
    source_time_s: float
    timestamp_status: str
    segment_id: str
    camera_id: str
    bbox: List[float]  # [x1, y1, x2, y2]
    footpoint_image: Tuple[float, float]  # (x, y)
    position_method: str = "bbox_bottom_center"
    projected_court_xy: Optional[Tuple[float, float]] = None
    court_units: str = "normalized"
    validity_status: str = "valid"  # "valid", "outside_roi", "degenerate_projection", "occluded", "touch_boundary"
    validity_reason: Optional[str] = None
    calibration_version: Optional[str] = None
    track_id: Optional[str] = None
    player_id: Optional[str] = None
    team_id: Optional[str] = None
    role: str = "unknown"  # "player", "non_player", "referee", "spectator", "unknown"
    sample_type: str = "observed"  # "observed", "interpolated", "predicted"
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.source_time_s) or self.source_time_s < 0.0:
            raise ValueError(f"source_time_s must be finite and >= 0: {self.source_time_s}")
        if len(self.bbox) != 4 or not all(math.isfinite(v) for v in self.bbox):
            raise ValueError(f"Invalid bbox: {self.bbox}")
        if self.footpoint_image and (len(self.footpoint_image) != 2 or not all(math.isfinite(v) for v in self.footpoint_image)):
            raise ValueError(f"Invalid footpoint_image: {self.footpoint_image}")
        if self.projected_court_xy is not None:
            if len(self.projected_court_xy) != 2 or not all(math.isfinite(v) for v in self.projected_court_xy):
                raise ValueError(f"Invalid projected_court_xy: {self.projected_court_xy}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "observation_id": self.observation_id,
            "source_run_id": self.source_run_id,
            "video_id": self.video_id,
            "source_fingerprint_sha256": self.source_fingerprint_sha256,
            "frame_index": self.frame_index,
            "source_time_s": round(self.source_time_s, 6),
            "timestamp_status": self.timestamp_status,
            "segment_id": self.segment_id,
            "camera_id": self.camera_id,
            "bbox": [round(float(v), 2) for v in self.bbox],
            "footpoint_image": [round(float(v), 2) for v in self.footpoint_image],
            "position_method": self.position_method,
            "projected_court_xy": [round(float(v), 4) for v in self.projected_court_xy] if self.projected_court_xy else None,
            "court_units": self.court_units,
            "validity_status": self.validity_status,
            "validity_reason": self.validity_reason,
            "calibration_version": self.calibration_version,
            "track_id": self.track_id,
            "player_id": self.player_id,
            "team_id": self.team_id,
            "role": self.role,
            "sample_type": self.sample_type,
            "confidence": round(float(self.confidence), 4),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


def estimate_footpoint(
    bbox: List[float],
    original_wh: Tuple[int, int],
    boundary_margin_px: float = 5.0,
) -> Tuple[Tuple[float, float], str, Optional[str]]:
    """
    Estimate ground contact point from bounding box bottom-center.
    
    Returns:
        ((x_foot, y_foot), validity_status, reason)
    """
    x1, y1, x2, y2 = bbox
    width, height = original_wh
    x_foot = (x1 + x2) / 2.0
    y_foot = y2

    # Check image boundary touching
    touches_bottom = (y2 >= height - boundary_margin_px)
    touches_left = (x1 <= boundary_margin_px)
    touches_right = (x2 >= width - boundary_margin_px)
    touches_top = (y1 <= boundary_margin_px)

    if touches_bottom:
        return (x_foot, y_foot), "touch_boundary", "bbox touches image bottom boundary (feet likely cropped)"
    if touches_left or touches_right or touches_top:
        return (x_foot, y_foot), "touch_boundary", "bbox touches image boundary (potential partial occlusion)"

    return (x_foot, y_foot), "valid", None


def check_non_collinear(points: List[Tuple[float, float]], tolerance: float = 1e-4) -> bool:
    """Verify that no 3 points among the given points are collinear."""
    n = len(points)
    if n < 3:
        return True
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                p1, p2, p3 = points[i], points[j], points[k]
                # Area of triangle formed by 3 points: 0.5 * |x1(y2 - y3) + x2(y3 - y1) + x3(y1 - y2)|
                area2 = abs(p1[0] * (p2[1] - p3[1]) + p2[0] * (p3[1] - p1[1]) + p3[0] * (p1[1] - p2[1]))
                if area2 < tolerance:
                    return False
    return True


def solve_homography(
    correspondences: List[PointCorrespondence],
    min_points: int = 4,
    condition_threshold: float = 1e12,
) -> HomographyResult:
    """
    Compute explicit bidirectional homography between image and court plane.
    
    - Rejects < 4 correspondences.
    - Rejects non-coplanar points (e.g. rim).
    - Rejects collinear or degenerate configurations.
    - Computes fit residuals and independent check residuals.
    """
    fit_pts = [p for p in correspondences if p.usage == "fit" and p.is_coplanar]
    check_pts = [p for p in correspondences if p.usage == "check" and p.is_coplanar]

    # Non-coplanar points check
    non_coplanar = [p for p in correspondences if not p.is_coplanar and p.usage == "fit"]
    if non_coplanar:
        names = [p.name or p.point_id for p in non_coplanar]
        raise DegenerateGeometryError(
            f"Non-coplanar points cannot be used to fit floor homography: {names}. "
            "Rims and backboards are elevated above court plane."
        )

    if len(fit_pts) < min_points:
        raise DegenerateGeometryError(
            f"Insufficient coplanar fit points: required >= {min_points}, got {len(fit_pts)}"
        )

    img_pts = np.array([p.image_xy for p in fit_pts], dtype=np.float64)
    court_pts = np.array([p.court_xy for p in fit_pts], dtype=np.float64)

    # Check finite
    if not (np.all(np.isfinite(img_pts)) and np.all(np.isfinite(court_pts))):
        raise DegenerateGeometryError("Point correspondences contain non-finite values (NaN/Inf).")

    # Check duplicate points
    if len(np.unique(img_pts, axis=0)) < len(img_pts) or len(np.unique(court_pts, axis=0)) < len(court_pts):
        raise DegenerateGeometryError("Duplicate point coordinates detected in correspondences.")

    # Check collinearity of fit points
    if len(fit_pts) == 4 and not check_non_collinear([tuple(pt) for pt in img_pts]):  # type: ignore
        raise DegenerateGeometryError("First 4 fit points in image space are collinear or near-collinear.")
    if len(fit_pts) == 4 and not check_non_collinear([tuple(pt) for pt in court_pts]):  # type: ignore
        raise DegenerateGeometryError("First 4 fit points in court space are collinear or near-collinear.")

    # Calculate homography image -> court
    # OpenCV cv2.findHomography(srcPoints, dstPoints)
    H_img_to_court, mask = cv2.findHomography(img_pts, court_pts, method=0)
    if H_img_to_court is None:
        raise DegenerateGeometryError("Failed to calculate homography matrix (OpenCV solver returned None).")

    # Check determinant and invertibility
    det = np.linalg.det(H_img_to_court)
    if not np.isfinite(det) or abs(det) < 1e-12:
        raise DegenerateGeometryError(f"Singular or near-singular homography matrix: det={det}")

    # Check condition number
    cond = float(np.linalg.cond(H_img_to_court))
    if cond > condition_threshold:
        raise DegenerateGeometryError(f"Ill-conditioned homography matrix (condition number={cond:.2e} > {condition_threshold:.2e}).")

    try:
        H_court_to_img = np.linalg.inv(H_img_to_court)
    except np.linalg.LinAlgError as e:
        raise DegenerateGeometryError(f"Failed to invert homography matrix: {e}")

    # Compute fit residuals in image space: project court_pts back to image and compare with img_pts
    fit_residuals_px: List[float] = []
    for i, pt_court in enumerate(court_pts):
        proj_img = project_point(tuple(pt_court), H_court_to_img)
        if proj_img is None:
            fit_residuals_px.append(float("inf"))
        else:
            dist = math.hypot(proj_img[0] - img_pts[i][0], proj_img[1] - img_pts[i][1])
            fit_residuals_px.append(dist)

    mean_res_px = float(np.mean(fit_residuals_px)) if fit_residuals_px else 0.0
    max_res_px = float(np.max(fit_residuals_px)) if fit_residuals_px else 0.0

    # Compute check residuals if available
    check_residuals_px: Optional[List[float]] = None
    mean_check_res_px: Optional[float] = None
    if check_pts:
        check_residuals_px = []
        for p in check_pts:
            proj_img = project_point(p.court_xy, H_court_to_img)
            if proj_img is None:
                check_residuals_px.append(float("inf"))
            else:
                dist = math.hypot(proj_img[0] - p.image_xy[0], proj_img[1] - p.image_xy[1])
                check_residuals_px.append(dist)
        mean_check_res_px = float(np.mean(check_residuals_px))

    inlier_mask = [bool(m[0]) for m in mask] if mask is not None else [True] * len(fit_pts)

    return HomographyResult(
        H_image_to_court=H_img_to_court.tolist(),
        H_court_to_image=H_court_to_img.tolist(),
        fit_residuals_px=fit_residuals_px,
        mean_fit_residual_px=mean_res_px,
        max_fit_residual_px=max_res_px,
        check_residuals_px=check_residuals_px,
        mean_check_residual_px=mean_check_res_px,
        inlier_mask=inlier_mask,
        condition_number=cond,
    )


def project_point(
    xy: Tuple[float, float],
    H: Union[np.ndarray, List[List[float]]],
    min_denominator: float = 1e-8,
) -> Optional[Tuple[float, float]]:
    """
    Project 2D point using 3x3 homography matrix.
    
    Returns None if projective denominator is near zero (< min_denominator).
    """
    if isinstance(H, list):
        H = np.array(H, dtype=np.float64)
    x, y = xy
    p = np.array([x, y, 1.0], dtype=np.float64)
    p_prime = H @ p
    w = p_prime[2]
    if not math.isfinite(w) or abs(w) < min_denominator:
        return None
    result = (float(p_prime[0] / w),float(p_prime[1] / w))
    return result if all(math.isfinite(v) for v in result) else None


def is_point_in_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
    """Determine whether a 2D point lies inside or on the boundary of a 2D polygon."""
    if len(polygon) < 3:
        return False
    pts = np.array(polygon, dtype=np.float32).reshape((-1, 1, 2))
    res = cv2.pointPolygonTest(pts, (float(point[0]), float(point[1])), measureDist=False)
    return res >= 0  # 0 on boundary, 1 inside


class CourtModel:
    """Execution engine for court calibration, validation, and projection."""

    def __init__(self, config: CourtConfig) -> None:
        self.config = config
        self.homography: Optional[HomographyResult] = None
        self._is_calibrated = False

    @property
    def is_calibrated(self) -> bool:
        return self._is_calibrated

    @property
    def calibration_version(self) -> str:
        digest = hashlib.sha256(json.dumps(self.config.to_dict(),sort_keys=True).encode()).hexdigest()
        return self.config.schema_version + ":" + digest[:16]

    def calibrate(self, allow_uncalibrated: bool = False) -> HomographyResult:
        """
        Validate config and solve homography.
        
        If allow_uncalibrated=False, status must be 'validated' or is_synthetic=True.
        """
        if not allow_uncalibrated:
            if self.config.is_synthetic or self.config.status != "validated":
                raise UncalibratedCourtError(
                    f"Court configuration '{self.config.camera_id}' has status '{self.config.status}'. "
                    "Calibrated production mode requires 'validated' status with verified landmarks."
                )
            if (self.config.provenance.get("review_status") != "approved" or not self.config.provenance.get("reviewed_by")
                    or not self.config.source_video_hash or not self.config.court_roi_image):
                raise UncalibratedCourtError(
                    f"Court configuration '{self.config.camera_id}' has unapproved provenance: "
                    f"{self.config.provenance}. Independent review approval required."
                )

        # Solve homography from point correspondences
        homography_res = solve_homography(self.config.point_correspondences)
        max_error = self.config.thresholds.get("max_reprojection_error_px",15.0)
        if not math.isfinite(max_error) or max_error <= 0:
            raise ValueError("Reprojection threshold must be finite and positive")
        if not allow_uncalibrated and (homography_res.max_fit_residual_px > max_error
                or any(error > max_error for error in homography_res.check_residuals_px or [])):
            raise DegenerateGeometryError("Calibration exceeds configured reprojection error threshold")
        self.homography = homography_res
        self._is_calibrated = True
        return homography_res

    def project_image_to_court(self, image_xy: Tuple[float, float]) -> Optional[Tuple[float, float]]:
        """Project an image coordinate to court coordinate space."""
        if not self._is_calibrated or self.homography is None:
            raise UncalibratedCourtError("Court model is not calibrated. Call calibrate() first.")
        return project_point(image_xy, self.homography.matrix_image_to_court)

    def project_court_to_image(self, court_xy: Tuple[float, float]) -> Optional[Tuple[float, float]]:
        """Project a court coordinate to image space."""
        if not self._is_calibrated or self.homography is None:
            raise UncalibratedCourtError("Court model is not calibrated. Call calibrate() first.")
        return project_point(court_xy, self.homography.matrix_court_to_image)

    def is_in_court_roi(self, image_xy: Tuple[float, float]) -> bool:
        """Check if an image point falls inside the declared court ROI polygon."""
        if not self.config.court_roi_image:
            return False
        return is_point_in_polygon(image_xy, self.config.court_roi_image)

    def is_in_court_bounds(self, court_xy: Tuple[float, float]) -> bool:
        """Check if a court point falls within the declared coordinate system bounds."""
        bounds = self.config.court_coordinate_system.court_bounds
        x, y = court_xy
        return (bounds["x_min"] <= x <= bounds["x_max"] and bounds["y_min"] <= y <= bounds["y_max"])

    def process_detection(
        self,
        bbox: List[float],
        frame_index: int,
        source_time_s: float,
        timestamp_status: str,
        video_id: str,
        source_fingerprint_sha256: str,
        source_run_id: str,
        observation_id: str,
        track_id: Optional[str] = None,
        player_id: Optional[str] = None,
        team_id: Optional[str] = None,
        role: str = "unknown",
        sample_type: str = "observed",
        confidence: float = 1.0,
    ) -> TrajectoryObservation:
        """
        Process a single bounding box into a TrajectoryObservation contract.
        
        Evaluates boundary touches, ROI containment, and projective validities.
        """
        footpoint, foot_status, foot_reason = estimate_footpoint(bbox, self.config.original_image_wh)
        
        # Check ROI
        in_roi = self.is_in_court_roi(footpoint)
        validity_status = foot_status
        validity_reason = foot_reason

        if foot_status == "valid" and not in_roi:
            validity_status = "outside_roi"
            validity_reason = "Footpoint is outside designated court ROI polygon"

        projected_xy: Optional[Tuple[float, float]] = None
        if foot_status == "valid" and self._is_calibrated and in_roi:
            proj = self.project_image_to_court(footpoint)
            if proj is None:
                validity_status = "degenerate_projection"
                validity_reason = "Homography projection resulted in near-zero projective denominator"
            else:
                if not self.is_in_court_bounds(proj):
                    validity_status = "outside_court_bounds"
                    validity_reason = f"Projected coordinate {proj} exceeds court bounds {self.config.court_coordinate_system.court_bounds}"
                else:
                    projected_xy = proj

        return TrajectoryObservation(
            schema_version="2.0.0",
            observation_id=observation_id,
            source_run_id=source_run_id,
            video_id=video_id,
            source_fingerprint_sha256=source_fingerprint_sha256,
            frame_index=frame_index,
            source_time_s=source_time_s,
            timestamp_status=timestamp_status,
            segment_id=self.config.segment_id,
            camera_id=self.config.camera_id,
            bbox=bbox,
            footpoint_image=footpoint,
            position_method="bbox_bottom_center",
            projected_court_xy=projected_xy,
            court_units=self.config.court_coordinate_system.units,
            validity_status=validity_status,
            validity_reason=validity_reason,
            calibration_version=self.calibration_version if self._is_calibrated else None,
            track_id=track_id,
            player_id=player_id,
            team_id=team_id,
            role=role,
            sample_type=sample_type,
            confidence=confidence,
        )

