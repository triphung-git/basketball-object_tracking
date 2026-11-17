# Release notes

## Spatial-only pipeline

- Removed game-statistics recognition, computation, APIs, UI panels, CLI scripts,
  evaluation assets, and their technical documentation.
- Kept video detection, human tracking, bbox overlays, court calibration, 2D
  spatial visualization, and movement heatmaps.
- Replaced the upload worker and demo orchestration with a spatial-only path.
- Added focused tests for spatial projection/heatmaps and dashboard/upload behavior.
- No new real-video accuracy benchmark was run as part of this change.

