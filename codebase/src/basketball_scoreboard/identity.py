"""Player identity resolution, jersey OCR evidence aggregation, and team classification (v2)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np


class IdentityError(Exception):
    """Base error for identity resolution and roster validation."""
    pass


class ModelWeightsUnavailableError(IdentityError):
    """Raised when OCR or ReID model weights are not cached locally and require download."""
    pass


@dataclass
class RosterPlayer:
    """Player entry in team roster."""
    player_id: str
    team_id: str
    jersey_number: str
    name: str
    is_active: bool = True
    aliases: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.player_id or not self.team_id or not self.jersey_number:
            raise ValueError("player_id, team_id, and jersey_number must be non-empty strings")
        self.jersey_number = str(self.jersey_number).strip()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RosterConfig:
    """Official roster configuration for dual-team session."""
    team_a_id: str
    team_b_id: str
    team_a_name: str
    team_b_name: str
    team_a_color_rgb: Tuple[int, int, int]
    team_b_color_rgb: Tuple[int, int, int]
    players: List[RosterPlayer] = field(default_factory=list)
    session_id: Optional[str] = None
    provenance_status: str = "draft"  # "draft", "approved"

    def __post_init__(self) -> None:
        if self.team_a_id == self.team_b_id:
            raise ValueError(f"team_a_id and team_b_id cannot be identical: {self.team_a_id}")
        for color in (self.team_a_color_rgb,self.team_b_color_rgb):
            if len(color) != 3 or not all(isinstance(v,(int,float)) and math.isfinite(v) and 0 <= v <= 255 for v in color):
                raise ValueError("Team colors must be finite RGB triples in [0,255]")

        # Validate player_id uniqueness across entire roster
        player_ids = set()
        for p in self.players:
            if p.player_id in player_ids:
                raise ValueError(f"Duplicate player_id in roster: {p.player_id}")
            player_ids.add(p.player_id)

        # Validate jersey number uniqueness WITHIN each team
        # (Opposing teams CAN legally have the same jersey number in FIBA 3x3)
        team_a_jerseys = set()
        team_b_jerseys = set()
        for p in self.players:
            if p.team_id == self.team_a_id:
                if p.jersey_number in team_a_jerseys:
                    raise ValueError(f"Duplicate jersey number in Team {self.team_a_id}: #{p.jersey_number}")
                team_a_jerseys.add(p.jersey_number)
            elif p.team_id == self.team_b_id:
                if p.jersey_number in team_b_jerseys:
                    raise ValueError(f"Duplicate jersey number in Team {self.team_b_id}: #{p.jersey_number}")
                team_b_jerseys.add(p.jersey_number)
            else:
                raise ValueError(f"Player {p.player_id} has invalid team_id '{p.team_id}' not matching {self.team_a_id} or {self.team_b_id}")

    def get_player(self, team_id: str, jersey_number: str) -> Optional[RosterPlayer]:
        """Look up player by team and jersey number."""
        num = str(jersey_number).strip()
        for p in self.players:
            if p.is_active and p.team_id == team_id and p.jersey_number == num:
                return p
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "team_a_id": self.team_a_id,
            "team_b_id": self.team_b_id,
            "team_a_name": self.team_a_name,
            "team_b_name": self.team_b_name,
            "team_a_color_rgb": list(self.team_a_color_rgb),
            "team_b_color_rgb": list(self.team_b_color_rgb),
            "session_id": self.session_id,
            "provenance_status": self.provenance_status,
            "players": [p.to_dict() for p in self.players],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RosterConfig:
        players = [RosterPlayer(**p) for p in data.get("players", [])]
        return cls(
            team_a_id=str(data["team_a_id"]),
            team_b_id=str(data["team_b_id"]),
            team_a_name=str(data.get("team_a_name", data["team_a_id"])),
            team_b_name=str(data.get("team_b_name", data["team_b_id"])),
            team_a_color_rgb=tuple(data["team_a_color_rgb"]),  # type: ignore
            team_b_color_rgb=tuple(data["team_b_color_rgb"]),  # type: ignore
            players=players,
            session_id=data.get("session_id"),
            provenance_status=str(data.get("provenance_status", "draft")),
        )


@dataclass
class JerseyEvidenceRecord:
    """Single observation of a jersey number reading from OCR or detector."""
    evidence_id: str
    track_id: str
    frame_index: int
    source_time_s: float
    detected_number: str
    confidence: float
    ocr_engine: str = "mock_ocr"
    is_valid: bool = True
    rejection_reason: Optional[str] = None

    def __post_init__(self):
        if (not self.evidence_id or not self.track_id or not math.isfinite(self.source_time_s) or self.source_time_s < 0
                or not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1):
            raise ValueError("Invalid jersey evidence")
        self.detected_number = str(self.detected_number).strip()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate_crop_quality(
    crop: Optional[np.ndarray],
    min_width: int = 16,
    min_height: int = 24,
    min_std_dev: float = 8.0,
    min_aspect_ratio: float = 0.25,
    max_aspect_ratio: float = 4.0,
) -> Tuple[bool, Optional[str]]:
    """
    Validate that an extracted crop is suitable for OCR processing.

    Checks:
    - Non-null, non-empty numpy array.
    - Adequate pixel dimensions (width >= min_width, height >= min_height).
    - Sufficient contrast and texture variation (intensity standard deviation >= min_std_dev).
    - A plausible single-player torso crop ratio; very wide or very tall crops are likely
      background/multiple players or badly cropped regions.
    """
    if crop is None or not isinstance(crop, np.ndarray) or crop.size == 0:
        return False, "Empty or non-array crop"
    if crop.ndim < 2:
        return False, f"Invalid crop dimensions: ndim={crop.ndim}"
    h, w = crop.shape[:2]
    if w < min_width or h < min_height:
        return False, f"Crop dimensions ({w}x{h}) below minimum threshold ({min_width}x{min_height})"
    ratio = float(h) / max(float(w), 1.0)
    if ratio < min_aspect_ratio or ratio > max_aspect_ratio:
        return False, (
            f"Crop aspect ratio ({ratio:.2f}) outside plausible torso range "
            f"({min_aspect_ratio:.2f}-{max_aspect_ratio:.2f})"
        )
    std = float(np.std(crop))
    if not math.isfinite(std) or std < min_std_dev:
        return False, f"Insufficient crop texture/contrast (std_dev={std:.2f} < {min_std_dev})"
    return True, None


class OCRProvider:
    """Abstract interface for local jersey number OCR engines."""
    name: str = "base_ocr"
    is_production: bool = False

    def read_jersey(
        self,
        crop: np.ndarray,
        track_id: str,
        frame_index: int,
        source_time_s: float,
    ) -> List[JerseyEvidenceRecord]:
        """Process a player torso/jersey image crop and return jersey number candidate records."""
        raise NotImplementedError


class LocalEasyOCRProvider(OCRProvider):
    """
    Local EasyOCR provider enforcing offline governance and zero silent downloads.
    
    Guarantees:
    - Never triggers automated network downloads of model weights (download_enabled=False).
    - Proactively checks that required weights ('craft_mlt_25k.pth' and 'english_g2.pth')
      exist in model_storage_directory before attempting inference.
    - Raises ModelWeightsUnavailableError if weights are missing.
    - Filters outputs to valid basketball jersey number patterns (1-2 digits, 0-99).
    """
    name: str = "easyocr_local"
    is_production: bool = True

    def __init__(
        self,
        model_storage_directory: Optional[Union[str, Path]] = None,
        gpu: bool = False,
        confidence_threshold: float = 0.5,
        crop_upscale: int = 1,
        min_number_height_fraction: float = 0.,
    ) -> None:
        if model_storage_directory:
            self.storage_dir = Path(model_storage_directory).expanduser().resolve()
        else:
            project_root = Path(__file__).resolve().parents[2]
            managed_ocr = (project_root / "models" / "ocr").resolve()
            repo_cache = (project_root / ".model-cache" / "easyocr").resolve()
            if (managed_ocr / "craft_mlt_25k.pth").is_file() and (managed_ocr / "english_g2.pth").is_file():
                self.storage_dir = managed_ocr
            elif (repo_cache / "craft_mlt_25k.pth").is_file() and (repo_cache / "english_g2.pth").is_file():
                self.storage_dir = repo_cache
            else:
                self.storage_dir = managed_ocr
        self.gpu = bool(gpu)
        self.confidence_threshold = float(confidence_threshold)
        if isinstance(crop_upscale, bool) or not isinstance(crop_upscale,int) or not 1 <= crop_upscale <= 4:
            raise ValueError("OCR crop upscale must be an integer 1-4")
        self.crop_upscale = crop_upscale
        if not 0 <= min_number_height_fraction <= 1:
            raise ValueError('Invalid minimum number height fraction')
        self.min_number_height_fraction = min_number_height_fraction
        self.stats = dict(attempts=0,rejected_crops=0,runtime_errors=0)
        self._validate_weights_exist()
        self._reader = None

    def _validate_weights_exist(self) -> None:
        craft_weight = self.storage_dir / "craft_mlt_25k.pth"
        recog_weight = self.storage_dir / "english_g2.pth"
        missing = []
        if not craft_weight.is_file():
            missing.append(craft_weight.name)
        if not recog_weight.is_file():
            missing.append(recog_weight.name)
        if missing:
            raise ModelWeightsUnavailableError(
                f"Local EasyOCR weights {missing} not found in '{self.storage_dir}'. "
                f"Silent automated download is forbidden by governance protocol. "
                f"Please obtain user authorization and place weights locally before enabling OCR."
            )

    @property
    def reader(self):
        if self._reader is None:
            import easyocr
            if not self.gpu:
                import torch
                torch.set_num_threads(1)
            self._reader = easyocr.Reader(
                ['en'],
                gpu=self.gpu,
                model_storage_directory=str(self.storage_dir),
                download_enabled=False,
                verbose=False,
            )
        return self._reader

    def read_jersey(
        self,
        crop: np.ndarray,
        track_id: str,
        frame_index: int,
        source_time_s: float,
    ) -> List[JerseyEvidenceRecord]:
        self.stats['attempts'] += 1
        is_valid, _ = evaluate_crop_quality(crop)
        if not is_valid:
            self.stats['rejected_crops'] += 1
            return []
        if self.crop_upscale > 1:
            import cv2
            crop = cv2.resize(crop,None,fx=self.crop_upscale,fy=self.crop_upscale,interpolation=cv2.INTER_CUBIC)
        try:
            results = self.reader.readtext(crop, allowlist='0123456789',min_size=8)
        except Exception as exc:
            self.stats['runtime_errors'] += 1
            raise RuntimeError(f"Local jersey OCR inference failed: {type(exc).__name__}") from exc
        # Duplicate text regions of one number are one observation, not extra votes.
        best = {}
        for polygon,text,prob in results:
            if self.min_number_height_fraction:
                coordinates = np.asarray(polygon,dtype=float)
                if coordinates.shape != (4,2) or not np.isfinite(coordinates).all():
                    continue
                left,top=coordinates.min(axis=0);right,bottom=coordinates.max(axis=0)
                # Tiny chest/sponsor lettering and partial digits cannot vote
                # as a jersey number merely because OCR returned a digit.
                if (bottom-top < self.min_number_height_fraction*crop.shape[0]
                        or (top+bottom)/2 < .28*crop.shape[0]
                        or left<=0 or right>=crop.shape[1]-1 or top<=0 or bottom>=crop.shape[0]-1):
                    continue
            cleaned=str(text).strip()
            if cleaned.isdigit() and 1 <= len(cleaned) <= 2 and math.isfinite(float(prob)) and self.confidence_threshold <= float(prob) <= 1:
                best[cleaned]=max(best.get(cleaned,0.),float(prob))
        records: List[JerseyEvidenceRecord] = []
        for cleaned,prob in best.items():
            rec = JerseyEvidenceRecord(
                evidence_id=f"ocr_{track_id}_{frame_index}_{cleaned}",
                track_id=track_id,
                frame_index=frame_index,
                source_time_s=source_time_s,
                detected_number=cleaned,
                confidence=round(float(prob), 4),
                ocr_engine=self.name,
            )
            records.append(rec)
        return records


class MockOCRProvider(OCRProvider):
    """
    Diagnostic/mock OCR provider for deterministic unit and contract testing.
    Must only be used when diagnostic opt-in (--allow-uncalibrated) is present.
    """
    name: str = "mock_ocr"
    is_production: bool = False

    def __init__(
        self,
        scripted_readings: Optional[Dict[Tuple[str, int], List[Tuple[str, float]]]] = None,
        default_number: Optional[str] = None,
        default_confidence: float = 0.95,
    ) -> None:
        self.scripted_readings = scripted_readings or {}
        self.default_number = default_number
        self.default_confidence = float(default_confidence)

    def read_jersey(
        self,
        crop: np.ndarray,
        track_id: str,
        frame_index: int,
        source_time_s: float,
    ) -> List[JerseyEvidenceRecord]:
        is_valid, _ = evaluate_crop_quality(crop)
        if not is_valid:
            return []
        key = (track_id, frame_index)
        records: List[JerseyEvidenceRecord] = []
        if key in self.scripted_readings:
            for num, conf in self.scripted_readings[key]:
                records.append(
                    JerseyEvidenceRecord(
                        evidence_id=f"mock_{track_id}_{frame_index}_{num}",
                        track_id=track_id,
                        frame_index=frame_index,
                        source_time_s=source_time_s,
                        detected_number=str(num).strip(),
                        confidence=round(float(conf), 4),
                        ocr_engine=self.name,
                    )
                )
        elif self.default_number is not None:
            records.append(
                JerseyEvidenceRecord(
                    evidence_id=f"mock_{track_id}_{frame_index}_{self.default_number}",
                    track_id=track_id,
                    frame_index=frame_index,
                    source_time_s=source_time_s,
                    detected_number=str(self.default_number).strip(),
                    confidence=self.default_confidence,
                    ocr_engine=self.name,
                )
            )
        return records


@dataclass
class TrackIdentityMapping:
    """Interval assignment of a track to a resolved team and player identity."""
    track_id: str
    start_time_s: float
    end_time_s: float
    team_id: Optional[str]
    player_id: Optional[str]
    revision_id: int = 1
    confidence: float = 1.0
    evidence_summary: Dict[str, Any] = field(default_factory=dict)
    conflict_status: str = "none"  # "none", "duplicate_active_player", "ambiguous_team"
    role: str = "unknown"  # "player", "referee", "non_player", "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "track_id": self.track_id,
            "start_time_s": round(self.start_time_s, 6),
            "end_time_s": round(self.end_time_s, 6),
            "team_id": self.team_id,
            "player_id": self.player_id,
            "role": self.role,
            "revision_id": self.revision_id,
            "confidence": round(self.confidence, 4),
            "conflict_status": self.conflict_status,
            "evidence_summary": self.evidence_summary,
        }


class TeamColorClassifier:
    """
    Classifies player jersey color into Team A, Team B, or Unknown.
    
    Uses color distance against declared prototype colors with an ambiguity threshold.
    """

    def __init__(
        self,
        team_a_id: str,
        team_b_id: str,
        team_a_color_rgb: Tuple[int, int, int],
        team_b_color_rgb: Tuple[int, int, int],
        ambiguity_margin: float = 30.0,
        max_color_distance: float = 120.0,
        allow_referee_heuristic: bool = False,
    ) -> None:
        self.team_a_id = team_a_id
        self.team_b_id = team_b_id
        self.team_a_rgb = np.array(team_a_color_rgb, dtype=np.float64)
        self.team_b_rgb = np.array(team_b_color_rgb, dtype=np.float64)
        self.ambiguity_margin = float(ambiguity_margin)
        self.max_color_distance = float(max_color_distance)
        self.allow_referee_heuristic = allow_referee_heuristic

    def classify_rgb(self, observed_rgb: Tuple[float, float, float]) -> Tuple[Optional[str], float, str]:
        """
        Classify an observed mean jersey color.
        
        Returns:
            (team_id, confidence, reason)
        """
        obs = np.array(observed_rgb, dtype=np.float64)
        if obs.shape != (3,) or not np.all(np.isfinite(obs)) or np.any(obs < 0) or np.any(obs > 255):
            raise ValueError("RGB sample must be finite values in [0,255]")
        dist_a = float(np.linalg.norm(obs - self.team_a_rgb))
        dist_b = float(np.linalg.norm(obs - self.team_b_rgb))

        diff = abs(dist_a - dist_b)
        if diff < self.ambiguity_margin:
            return (None, 0.5, f"Ambiguous jersey color: dist_A={dist_a:.1f}, dist_B={dist_b:.1f}, diff={diff:.1f} < {self.ambiguity_margin}")
        if min(dist_a,dist_b) > self.max_color_distance:
            return (None,0.0,"Color is too far from both configured prototypes")

        if dist_a < dist_b:
            conf = min(1.0, max(0.5, 1.0 - (dist_a / 255.0)))
            return (self.team_a_id, conf, f"Matched {self.team_a_id} (dist={dist_a:.1f})")
        else:
            conf = min(1.0, max(0.5, 1.0 - (dist_b / 255.0)))
            return (self.team_b_id, conf, f"Matched {self.team_b_id} (dist={dist_b:.1f})")

    def classify_entity(self, observed_rgb: Tuple[float, float, float]) -> Tuple[Optional[str], float, str, str]:
        """
        Classify an observed crop color into (team_id, confidence, role, reason).
        role can be: 'player', 'referee', or 'unknown'.
        """
        team_id, conf, reason = self.classify_rgb(observed_rgb)
        if team_id is not None:
            return (team_id, conf, "player", reason)

        # Check for referee attire: neutral gray/black/dark shirt with low saturation
        obs = np.array(observed_rgb, dtype=np.float64)
        max_c = float(np.max(obs))
        min_c = float(np.min(obs))
        saturation = (max_c - min_c) / max(max_c, 1.0)
        dist_a = float(np.linalg.norm(obs - self.team_a_rgb))
        dist_b = float(np.linalg.norm(obs - self.team_b_rgb))

        # Referee uniform in basketball: low saturation (gray/black) and far from both teams
        team_saturations = [(float(np.max(c)) - float(np.min(c))) / max(float(np.max(c)), 1.0)
                            for c in (self.team_a_rgb, self.team_b_rgb)]
        if (self.allow_referee_heuristic and min(team_saturations) > 0.28
                and saturation < 0.28 and min(dist_a, dist_b) > 75.0):
            ref_conf = min(0.95, max(0.60, 1.0 - saturation))
            return (None, ref_conf, "referee", f"Referee attire detected: neutral shirt (sat={saturation:.2f}, dist_A={dist_a:.1f}, dist_B={dist_b:.1f})")

        return (None, conf, "unknown", reason)


def extract_jersey_rgb(bgr_crop, prototypes, valid_mask=None):
    """Prototype-aware color pixels avoid treating skin/gray as red/white shirts."""
    import cv2
    if bgr_crop is None or not bgr_crop.size:
        return None, {'reason': 'empty_crop'}
    if not isinstance(bgr_crop, np.ndarray) or bgr_crop.ndim < 2 or bgr_crop.shape[-1] != 3:
        return None, {'reason': 'invalid_crop_shape'}
    if not prototypes:
        return None, {'reason': 'empty_prototypes'}
    if valid_mask is not None and (not isinstance(valid_mask, np.ndarray) or valid_mask.shape != bgr_crop.shape[:2] or
                                   valid_mask.dtype != np.bool_ or not valid_mask.any()):
        return None, {'reason': 'invalid_visible_pixel_mask'}
    if not evaluate_crop_quality(bgr_crop, min_width=8, min_height=8, min_std_dev=4.0)[0]:
        return None, {'reason': 'crop_failed_quality_gate'}
    hsv = cv2.cvtColor(bgr_crop, cv2.COLOR_BGR2HSV)
    masks = []
    for rgb in prototypes:
        reference = cv2.cvtColor(np.array([[list(reversed(rgb))]], dtype=np.uint8), cv2.COLOR_BGR2HSV)[0, 0]
        hue, saturation, value = map(float, reference)
        if saturation < 50 and value > 180:
            mask = (hsv[:, :, 1] < 65) & (hsv[:, :, 2] > 180)
        elif value < 80:
            mask = (hsv[:, :, 2] < 90) & (hsv[:, :, 1] < 120)
        else:
            delta = np.abs(hsv[:, :, 0].astype(float) - hue)
            delta = np.minimum(delta, 180.0 - delta)
            mask = (delta < 14) & (hsv[:, :, 1] > 90) & (hsv[:, :, 2] > 65)
        masks.append(mask)
    fractions = [float(mask[valid_mask].mean()) if valid_mask is not None else float(mask.mean()) for mask in masks]
    order = sorted(range(len(masks)), key=lambda i: -fractions[i])
    if not fractions or fractions[order[0]] < 0.20:
        return None, dict(reason='insufficient_or_ambiguous_jersey_pixels', fractions=fractions)
    if len(fractions) > 1 and fractions[order[0]] - fractions[order[1]] < 0.08:
        return None, dict(reason='insufficient_or_ambiguous_jersey_pixels', fractions=fractions)
    selected_mask = masks[order[0]] if valid_mask is None else masks[order[0]] & valid_mask
    pixels = bgr_crop[selected_mask]
    if pixels.size == 0:
        return None, dict(reason='empty_masks_after_filtering', fractions=fractions)
    rgb = tuple(float(x) for x in np.median(pixels, axis=0)[::-1])
    return rgb, dict(reason='prototype_masked_torso_pixels', fractions=fractions)


class IdentityResolver:
    """
    Evidence-based identity resolver combining team classification and jersey OCR.
    
    Guarantees:
    1. Multi-frame hysteresis: single-frame noise does not flip confirmed player identity.
    2. Zero evidence -> unresolved player_id (never guessed from position or index).
    3. Conflict detection: flags duplicate active player assignments across tracks.
    4. Immutable mapping revision ledger supporting deterministic replay.
    """

    def __init__(
        self,
        roster: RosterConfig,
        color_classifier: Optional[TeamColorClassifier] = None,
        min_ocr_confidence: float = 0.5,
        confirmation_hits_threshold: int = 3,
        evidence_ttl_s: float = 2.0,
        jersey_evidence_ttl_s: Optional[float] = None,
    ) -> None:
        self.roster = roster
        self.color_classifier = color_classifier
        self.min_ocr_confidence = float(min_ocr_confidence)
        self.confirmation_hits_threshold = int(confirmation_hits_threshold)
        self.evidence_ttl_s = float(evidence_ttl_s)
        self.jersey_evidence_ttl_s = self.evidence_ttl_s if jersey_evidence_ttl_s is None else float(jersey_evidence_ttl_s)
        if not math.isfinite(self.jersey_evidence_ttl_s) or self.jersey_evidence_ttl_s <= 0:
            raise ValueError("Invalid jersey evidence TTL")
        if not math.isfinite(evidence_ttl_s) or evidence_ttl_s <= 0 or confirmation_hits_threshold < 1:
            raise ValueError("Invalid evidence TTL/confirmation threshold")
        self._clock = {}
        self._evidence_ids = {}

        # Track evidence accumulators
        # track_id -> list of JerseyEvidenceRecord
        self.jersey_evidence: Dict[str, List[JerseyEvidenceRecord]] = {}
        # track_id -> list of team classifications (team_id, conf, source_time_s)
        self.team_evidence: Dict[str, List[Tuple[Optional[str], float, Optional[float]]]] = {}
        # track_id -> list of referee attire classifications (conf, source_time_s)
        self.referee_evidence: Dict[str, List[Tuple[float, Optional[float]]]] = {}
        # Active track mappings: track_id -> TrackIdentityMapping
        self.current_mappings: Dict[str, TrackIdentityMapping] = {}
        # History revisions
        self.mapping_ledger: List[TrackIdentityMapping] = []
        self._revision_counter = 1

    def add_referee_observation(self, track_id: str, confidence: float, source_time_s: Optional[float] = None) -> None:
        """Register a referee attire observation for a track."""
        if not str(track_id or '').strip():
            raise ValueError("Invalid track_id for referee observation")
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("Invalid referee confidence")
        if source_time_s is not None and (not math.isfinite(source_time_s) or source_time_s < 0):
            raise ValueError("Invalid referee evidence timestamp")
        if track_id not in self.referee_evidence:
            self.referee_evidence[track_id] = []
        self.referee_evidence[track_id].append((float(confidence), source_time_s))

    def add_team_observation(self, track_id: str, team_id: Optional[str], confidence: float, source_time_s=None) -> None:
        """Register a team classification observation for a track."""
        if not str(track_id or '').strip():
            raise ValueError("Invalid track_id for team observation")
        if team_id not in {None, self.roster.team_a_id, self.roster.team_b_id} or not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("Invalid team observation")
        if source_time_s is not None and (not math.isfinite(source_time_s) or source_time_s < 0):
            raise ValueError("Invalid team evidence timestamp")
        if track_id not in self.team_evidence:
            self.team_evidence[track_id] = []
        self.team_evidence[track_id].append((team_id, float(confidence), source_time_s))

    def add_jersey_evidence(self, evidence: JerseyEvidenceRecord) -> None:
        """Register an OCR jersey number reading for a track."""
        if evidence.evidence_id in self._evidence_ids:
            if self._evidence_ids[evidence.evidence_id] != evidence.to_dict():
                raise ValueError("Evidence ID reused with different contents")
            return
        if evidence.confidence < self.min_ocr_confidence:
            evidence.is_valid = False
            evidence.rejection_reason = f"Confidence {evidence.confidence:.2f} < threshold {self.min_ocr_confidence}"
        self._evidence_ids[evidence.evidence_id] = evidence.to_dict()

        if evidence.track_id not in self.jersey_evidence:
            self.jersey_evidence[evidence.track_id] = []
        self.jersey_evidence[evidence.track_id].append(evidence)

    def resolve_team(self, track_id: str) -> Tuple[Optional[str], float]:
        """Resolve consensus team for a track based on temporal voting."""
        obs = self.team_evidence.get(track_id, [])
        if not obs:
            return (None, 0.0)

        score_a = sum(conf for t,conf,_ in obs if t == self.roster.team_a_id)
        score_b = sum(conf for t,conf,_ in obs if t == self.roster.team_b_id)
        total = sum(conf for _,conf,_ in obs)

        if total <= 0.0:
            return (None, 0.0)

        diff = abs(score_a - score_b)
        if max(score_a,score_b) <= total / 2:
            return (None,0.0)
        if diff < 1.0 and min(score_a, score_b) > 0.0:
            return (None, 0.5)  # Conflict/ambiguity

        if score_a > score_b:
            return (self.roster.team_a_id, score_a / total)
        else:
            return (self.roster.team_b_id, score_b / total)

    def resolve_role(self, track_id: str) -> Tuple[str, float]:
        """Resolve role between 'player', 'referee', and 'unknown'."""
        team_id, team_conf = self.resolve_team(track_id)
        if team_id is not None:
            return ("player", team_conf)

        # Check referee evidence
        ref_obs = self.referee_evidence.get(track_id, [])
        if ref_obs:
            total_ref_conf = sum(conf for conf, _ in ref_obs)
            stamps = [t for _, t in ref_obs if t is not None]
            total_votes = sum(conf for _, conf, _ in self.team_evidence.get(track_id, []))
            if (total_ref_conf >= 2.0 and len(ref_obs) >= 3 and len(stamps) >= 3
                    and max(stamps) - min(stamps) >= .25
                    and total_ref_conf >= .8 * total_votes):
                return ("referee", min(0.95, total_ref_conf / (total_ref_conf + 1.0)))
        return ("unknown", 0.0)

    def resolve_player(
        self,
        track_id: str,
        resolved_team_id: Optional[str],
    ) -> Tuple[Optional[str], float, str]:
        """
        Resolve player identity by combining resolved team and jersey OCR readings.
        
        Requires multi-frame consensus (hysteresis).
        """
        if not resolved_team_id:
            return (None, 0.0, "Cannot resolve player: team is unknown")

        readings = [
            e for e in self.jersey_evidence.get(track_id, [])
            if e.is_valid
        ]
        if not readings:
            return (None, 0.0, "No valid jersey OCR evidence recorded for track")

        # Count weighted votes per jersey number
        votes: Dict[str, float] = {}
        for r in readings:
            if self.roster.get_player(resolved_team_id,r.detected_number):
                votes[r.detected_number] = votes.get(r.detected_number, 0.0) + r.confidence

        if not votes:
            return (None,0.,'No observed jersey number belongs to the resolved team roster')

        best_jersey, best_score = max(votes.items(), key=lambda item: item[1])
        scores=sorted(votes.values(),reverse=True)
        if len(scores)>1 and best_score-scores[1]<max(.5,.15*best_score):
            return (None,0.,'Ambiguous competing jersey OCR evidence')

        # Hysteresis: require at least confirmation_hits_threshold weighted votes
        if best_score < float(self.confirmation_hits_threshold):
            return (
                None,
                0.0,
                f"Jersey #{best_jersey} score ({best_score:.2f}) < confirmation threshold ({self.confirmation_hits_threshold})",
            )

        # Look up in roster for this specific team
        player = self.roster.get_player(resolved_team_id, best_jersey)
        if not player:
            return (
                None,
                0.0,
                f"Jersey #{best_jersey} not found on roster for team {resolved_team_id}",
            )

        conf = min(1.0, best_score / (best_score + 1.0))
        return (player.player_id, conf, f"Confirmed #{best_jersey} ({player.name}) with score {best_score:.2f}")

    def update_track_mapping(
        self,
        track_id: str,
        current_time_s: float,
        active_track_ids: Optional[Set[str]] = None,
    ) -> TrackIdentityMapping:
        """
        Compute and record the identity mapping for a track at current timestamp.
        
        Performs conflict detection for duplicate active players.
        """
        if not math.isfinite(current_time_s) or current_time_s < self._clock.get(track_id,0):
            raise ValueError("Non-finite/backward identity timestamp")
        self._clock[track_id] = current_time_s
        cutoff = current_time_s - self.evidence_ttl_s
        pending = self.team_evidence.get(track_id,[])
        self.team_evidence[track_id] = [(team,conf,current_time_s if stamp is None else stamp)
                                      for team,conf,stamp in pending if stamp is None or cutoff <= stamp <= current_time_s]
        jersey_cutoff = current_time_s - self.jersey_evidence_ttl_s
        self.jersey_evidence[track_id] = [e for e in self.jersey_evidence.get(track_id,[])
                                          if jersey_cutoff <= e.source_time_s <= current_time_s]
        ref_cutoff = current_time_s - self.evidence_ttl_s
        self.referee_evidence[track_id] = [
            (conf, current_time_s if stamp is None else stamp)
            for conf, stamp in self.referee_evidence.get(track_id, [])
            if stamp is None or ref_cutoff <= stamp <= current_time_s
        ]
        team_id, team_conf = self.resolve_team(track_id)
        role, role_conf = self.resolve_role(track_id)
        if role == "referee":
            team_id = None
            player_id = None
            player_conf = 0.0
            reason = "Referee attire: low-saturation neutral shirt on court"
        else:
            player_id, player_conf, reason = self.resolve_player(track_id, team_id)

        conflict_status = "none"

        # Check for duplicate active player conflict
        if player_id and active_track_ids:
            for other_tid in active_track_ids:
                if other_tid == track_id:
                    continue
                other_mapping = self.current_mappings.get(other_tid)
                if other_mapping and other_mapping.player_id == player_id:
                    conflict_status = "duplicate_active_player"
                    # Invalidate both or keep higher confidence
                    if other_mapping.confidence >= player_conf:
                        player_id = None
                        reason = f"Conflict: player {player_id} already assigned to {other_tid}"
                    else:
                        closed = replace(other_mapping,end_time_s=current_time_s)
                        for index in range(len(self.mapping_ledger)-1,-1,-1):
                            if self.mapping_ledger[index].revision_id == other_mapping.revision_id:
                                self.mapping_ledger[index] = closed
                                break
                        cleared = replace(other_mapping,start_time_s=current_time_s,end_time_s=current_time_s,player_id=None,
                                          conflict_status="duplicate_active_player",revision_id=self._revision_counter)
                        self._revision_counter += 1
                        self.current_mappings[other_tid] = cleared
                        self.mapping_ledger.append(cleared)

        team_stamps = [stamp for team,conf,stamp in self.team_evidence.get(track_id,[]) if team == team_id]
        valid_until = max(team_stamps,default=current_time_s) + self.evidence_ttl_s
        if role == "referee":
            valid_until = max(stamp for _, stamp in self.referee_evidence[track_id]) + self.evidence_ttl_s
        if player_id:
            jersey = next(player.jersey_number for player in self.roster.players if player.player_id == player_id)
            jersey_stamps = [e.source_time_s for e in self.jersey_evidence.get(track_id,[]) if e.is_valid and e.detected_number == jersey]
            valid_until = min(valid_until,max(jersey_stamps,default=current_time_s) + self.jersey_evidence_ttl_s)
        existing = self.current_mappings.get(track_id)
        if existing and existing.team_id == team_id and existing.player_id == player_id and existing.role == role and existing.conflict_status == conflict_status:
            # Extend end time
            updated = replace(existing,end_time_s=current_time_s,evidence_summary={**existing.evidence_summary,"valid_until_s":valid_until})
            self.current_mappings[track_id] = updated
            for index in range(len(self.mapping_ledger)-1,-1,-1):
                if self.mapping_ledger[index].revision_id == existing.revision_id:
                    self.mapping_ledger[index] = updated
                    break
            return updated

        # Create new mapping revision
        rev_id = self._revision_counter
        self._revision_counter += 1

        start_t = current_time_s
        if existing:
            expiry = existing.evidence_summary.get("valid_until_s",current_time_s) if (existing.team_id or existing.role == "referee") else current_time_s
            closed = replace(existing,end_time_s=min(current_time_s,expiry))
            for index in range(len(self.mapping_ledger)-1,-1,-1):
                if self.mapping_ledger[index].revision_id == existing.revision_id:
                    self.mapping_ledger[index] = closed
                    break
        new_mapping = TrackIdentityMapping(
            track_id=track_id,
            start_time_s=start_t,
            end_time_s=current_time_s,
            team_id=team_id,
            player_id=player_id,
            role=role,
            revision_id=rev_id,
            confidence=player_conf if player_id else (team_conf if team_id else role_conf),
            conflict_status=conflict_status,
            evidence_summary={"reason": reason, "team_conf": team_conf, "player_conf": player_conf,
                "role": role, "valid_until_s": valid_until},
        )
        self.current_mappings[track_id] = new_mapping
        self.mapping_ledger.append(new_mapping)
        return new_mapping

    def invalidate_track_evidence(self, track_id, source_time_s, reason):
        """Close identity causally when the current crop/evidence is untrusted."""
        if not math.isfinite(source_time_s) or source_time_s < self._clock.get(track_id, 0):
            raise ValueError('Invalid identity invalidation timestamp')
        self.team_evidence[track_id] = []
        self.jersey_evidence[track_id] = []
        self.referee_evidence[track_id] = []
        mapping = self.update_track_mapping(track_id, source_time_s)
        updated = replace(mapping, evidence_summary={**mapping.evidence_summary, 'invalidation_reason': reason})
        self.current_mappings[track_id] = updated
        for index in range(len(self.mapping_ledger)-1,-1,-1):
            if self.mapping_ledger[index].revision_id == updated.revision_id:
                self.mapping_ledger[index] = updated
                break
        return updated

    def mapping_at(self, track_id, source_time_s):
        """Lookup a causal mapping at event time, never the final identity of a track."""
        current = self.current_mappings.get(track_id)
        if current and current.start_time_s <= source_time_s <= current.end_time_s:
            return replace(current, evidence_summary=dict(current.evidence_summary))
        matches = [m for m in self.mapping_ledger if m.track_id == track_id and m.start_time_s <= source_time_s <= m.end_time_s]
        selected = max(matches,key=lambda m:(m.start_time_s,m.revision_id)) if matches else None
        return replace(selected,evidence_summary=dict(selected.evidence_summary)) if selected else None


def enrich_observations_with_identity(
    observations: List[Any],  # TrajectoryObservation
    resolver: IdentityResolver,
) -> None:
    """
    In-place update of TrajectoryObservation records with resolved team, player IDs, and roles.
    
    Enforces that non-player / predicted observations remain excluded from confirmed identities.
    If an entity is within the court ROI and has confirmed team or player evidence, its role
    is updated from 'unknown' to 'player'. If confirmed as referee, its role is set to 'referee'.
    """
    for obs in observations:
        obs.team_id = None
        obs.player_id = None
        if obs.track_id and obs.sample_type == "observed":
            mapping = resolver.mapping_at(obs.track_id, obs.source_time_s)
            if mapping:
                if mapping.role == "referee" and obs.role != "non_player":
                    obs.role = "referee"
                    obs.team_id = None
                    obs.player_id = None
                elif obs.role == "player" or obs.role == "unknown":
                    obs.team_id = mapping.team_id
                    obs.player_id = mapping.player_id
                    if (mapping.player_id or mapping.team_id) and obs.role == "unknown":
                        obs.role = "player"

