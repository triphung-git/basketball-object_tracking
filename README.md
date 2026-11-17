# Basketball Object Tracking

Local video processing for basketball detection, human tracking, court projection,
2D visualization, and movement heatmaps.

The active pipeline does **not** calculate or display points, assists, rebounds,
shots, possession, event timelines, or box scores. Removing those features does
not imply an accuracy guarantee for detection, tracking, calibration, or heatmaps.
No ground-truth accuracy benchmark has been run for this spatial-only change.

## What remains

- Frame-level object detections and human bounding boxes.
- Human track IDs and optional manual player/team assignment.
- Court calibration, projected positions, 2D court map, and heatmap.
- Local dashboard for video playback and spatial outputs.

## Run video analysis

Use Windows PowerShell from the repository root. Set up the Python environment
and detector dependencies described in `codebase/requirements.txt` first.
Provide a source video and a new output directory for each run:

```powershell
.\run_demo.bat --mode video-analysis `
  --video "C:\path\to\game.mp4" `
  --output "codebase\outputs\spatial-run" `
  --court "codebase\configs\courts\vt_development_court.json" `
  --serve --open-browser
```

The court configuration must match the source video's camera and geometry. If
there is no verified calibration for the source, omit `--court`; tracking still
runs, but physical court coordinates and heatmaps are unavailable. Do not reuse
calibration from a different video or camera.

Run the spatial pipeline without starting the dashboard:

```powershell
.\run_demo.bat --mode video-analysis `
  --video "C:\path\to\game.mp4" `
  --output "codebase\outputs\spatial-run"
```

The dashboard viewer can be launched for an existing run with:

```powershell
codebase\.venv\Scripts\python.exe codebase\scripts\run_dashboard.py `
  --run-dir "codebase\outputs\spatial-run"
```

See the [user guide](docs/USER_GUIDE.md), [court calibration guide](docs/guides/court-calibration.md),
and [development notes](docs/DEVELOPMENT.md).

## Tests and validation

Run the focused spatial tests with the configured project interpreter:

```powershell
codebase\.venv\Scripts\python.exe -m pytest `
  codebase\tests\test_spatial_analysis.py `
  codebase\tests\test_run_spatial_pipeline.py `
  codebase\tests\test_web_video_upload.py `
  codebase\tests\test_task03_pipeline.py `
  codebase\tests\test_task05_court_heatmap.py `
  codebase\tests\test_task06_players_identity.py -q
```

Unit tests validate contracts and control flow; they do not prove model accuracy
on real game footage. Tracking and heatmap quality must be measured against
reviewed ground truth for each supported camera/setup.
