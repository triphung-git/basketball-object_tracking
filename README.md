# Basketball Object Tracking

Local basketball video analysis with object tracking, player identity, court heatmaps,
and automatic points/rebounds/assists (PRA) event processing. Includes an interactive
dashboard and a verified sample demo bundle.

**Current status: `DEMO_PARTIAL`; AI quality: `NOT_ACCEPTED`.** The demo can be opened
and replayed. Recognition accuracy and real-time processing have not been accepted.
Passing software tests does not establish accuracy on real basketball footage.

## Quick start: view the included demo

Run from the repository root. The development environment uses Python 3.12 on Windows.

```powershell
git clone https://github.com/triphung-git/basketball-object_tracking.git
cd basketball-object_tracking
py -3.12 -m venv codebase/.venv
codebase/.venv/Scripts/python.exe -m pip install -r codebase/requirements-view.txt
codebase/.venv/Scripts/python.exe run_demo.py --check
.\run_demo.bat
```

The small viewer dependency set opens the bundled dashboard without downloading
detector/OCR weights, providing an API key, or obtaining the original match video.
The included `annotated.mp4` is the demo playback source. For an explicit launch:

```powershell
codebase/.venv/Scripts/python.exe run_demo.py --preset default --mode view --open-browser
```

The bundle remains at
`codebase/outputs/demo-completion-20261116/demo-bundle-qa-v2/` so existing launcher
paths remain valid. Its manifest verifies the exact artifact bytes. Historical
absolute paths in run metadata document the original machine; the viewer resolves
the bundled overlay and the repository roster locally.

## Run analysis on your own video

Install the existing full runtime snapshot instead of the viewer-only dependencies:

```powershell
codebase/.venv/Scripts/python.exe -m pip install -r codebase/requirements.txt
Copy-Item codebase/.env.example codebase/.env
```

Configure the Roboflow key locally in `.env`. Supply an input video, roster and
appropriate court calibration. Never reuse source-bound calibration for unrelated
footage. Source videos, model weights and training datasets are not bundled.

See the [current user guide](docs/USER_GUIDE.md) for analysis commands, calibration
scope, exports and limitations, and the [QA report](docs/reports/qa-project-review-20261116.md)
for measured behavior. The [technical README](codebase/README.md) and
[development guide](docs/DEVELOPMENT.md) retain earlier experiment instructions;
dated results there are historical evidence.

## Repository contents

| Path | Contents |
| --- | --- |
| `run_demo.py`, `run_demo.bat` | Public demo launchers |
| `codebase/src/basketball_scoreboard/` | Detection, tracking, identity, events, heatmaps and dashboard |
| `codebase/scripts/` | CLI, dataset preparation, review, evaluation and training tools |
| `codebase/configs/` | Runtime configuration, rosters, court and evaluation profiles |
| `codebase/tests/` | Software regression tests and historical artifact checks |
| `codebase/data/` | Small dataset manifests, annotations, schemas and split metadata |
| `codebase/outputs/demo-completion-20261116/demo-bundle-qa-v2/` | Verified sample demo |
| `docs/` | Specifications, guides, decisions, reports and handoffs |

Local virtual environments, credentials, caches, original media, training datasets,
weights and other experiment outputs are ignored. They are not deleted from the
development workspace. This repository preserves the existing source structure and
recognition behavior; it does not promote a new model or change evaluation rules.

## Validation

Validate the included bundle with `run_demo.py --check` as shown above. For the full
development regression suite, install the runtime and test dependencies, then run:

```powershell
codebase/.venv/Scripts/python.exe -m pip install pytest
codebase/.venv/Scripts/python.exe -m pytest codebase/tests -q
```

Several existing tests require historical experiment outputs, original media or
cached models that are intentionally not published. A fresh clone does not contain
all inputs for that full suite. The reported 539-pass regression in the QA report
was measured in the development workspace; it is not a clean-clone result. Packaging
validation is recorded separately in [the publication report](docs/reports/github-publication-20261116.md).

