# Court calibration and heatmap contract

## Coordinate spaces

- Image coordinates and bbox/footpoints use original decoded frame dimensions.
- Court coordinates use the units and bounds declared by the calibration config.
- A calibration belongs to its source video/camera and must not be reused across
  unrelated views.
- A court projection is unavailable when calibration is missing, invalid, stale,
  or produces a point outside the configured court.

## Calibration

Provide at least four non-degenerate image-to-court correspondences on the floor
plane. Elevated rim/backboard points are not floor correspondences. Keep
independent check points when validating a real camera; fit residual alone does
not prove geometry accuracy.

## Position and heatmap rules

- Use observed human tracks with valid timestamps and footpoints.
- Predicted, invalid, occluded, cropped, or out-of-court positions cannot create
  physical coordinates.
- Accumulate occupancy only between adjacent valid observations of the same
  track/identity and calibration segment.
- Break intervals across long gaps, exclusions, or camera/calibration changes.
- Retain raw image-space observations so spatial output can be recomputed.

The heatmap represents observed occupancy time, not an official activity or game
statistic. Correct mass accounting does not prove that the underlying tracks or
positions are correct.

## Accuracy evidence

Software tests cover homography validation, projection bounds, and
time-weighted aggregation. Real-world acceptance requires reviewed landmarks
and independent visible-foot ground truth for each target camera, with reported
sample size, coverage, and position error.
