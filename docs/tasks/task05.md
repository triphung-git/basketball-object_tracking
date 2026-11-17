# Task 05 — Court calibration and heatmaps

## Scope

Map valid observed player footpoints from image coordinates to a calibrated
2D court, then accumulate time-weighted occupancy. Calibration is bound to the
source camera/video; it must not be reused across unrelated sources.

## Reliability rules

- Require at least four non-degenerate image-to-court correspondences.
- Validate projection and reject points outside the configured court bounds.
- Use valid observed endpoints only; predicted, invalid, occluded, or cropped
  footpoints cannot create physical positions.
- Break accumulation across long gaps, exclusions, or calibration segments.
- Keep raw image-space observations so a map can be recomputed after calibration
  or identity changes.

## Verification status

Unit tests exercise homography guards, observed-position projection, and
time-weighted heatmap accumulation. They do not establish accuracy on real
footage. Acceptance requires reviewed court landmarks and independent visible
footpoint ground truth for each target camera.
