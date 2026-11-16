# GitHub publication preparation — 2026-11-16

Target: https://github.com/triphung-git/basketball-object_tracking

The existing workspace root is the repository root. The `origin` remote points to
the target repository, which was empty at preflight. Publication was explicitly
requested by the project owner.

## Included and excluded files

- Include existing source, scripts, tests, configurations, small dataset metadata
  and annotations, documentation, plans, and both root demo launchers.
- Include the current verified `demo-bundle-qa-v2` at its existing path. The bundle
  has 27 manifest-bound payload files plus its manifest, approximately 7.06 MiB.
- Exclude `.env`, virtual environments, tool/model caches, original videos,
  fine-tuning datasets, weights, and all other experiment outputs. Existing local
  files are retained; publication does not delete them.
- Preserve original file bytes with `.gitattributes` to keep source/data/artifact
  hashes and the existing demo manifest valid across Git checkouts.

Only publication metadata, ignore rules, the root README and a viewer dependency
file were added or adjusted. Source code, launcher behavior, model settings,
weights, schemas, reviewed labels, splits and evaluation thresholds are unchanged.
Historical reports retain their original context and local artifact references.

## Verification performed before publication

1. Staged content: approximately 10.6 MiB, including source and demo. The scan found
   no exact occurrences of local `.env` secret values and no matches for the checked
   GitHub token, private-key, AWS access-key and token-in-URL patterns. This is a
   targeted check, not a claim that every possible secret pattern is detected.
2. Staged file bytes and the staged checkout match the existing workspace source,
   scripts, tests, configs, included data, launchers and selected demo artifacts.
3. Source and scripts compile successfully in the staged checkout.
4. Local regression command:

   ```powershell
   codebase/.venv/Scripts/python.exe -m pytest codebase/tests/test_qa_demo_regressions.py codebase/tests/test_demo_cli_validation.py -q
   ```

   Result: **27 passed in 23.16 seconds**.
5. A new Python 3.12 virtual environment installed `requirements-view.txt` from the
   package index. `pip check` reported no broken requirements.
6. A checkout containing only the staged files, at a different directory, passed
   `run_demo.py --check` using that new interpreter. It contains no original video,
   `.env`, inference weights, model cache or original virtual environment.
7. The public viewer entrypoint served that checkout successfully. HTTP checks
   passed for the dashboard, status/events/boxscore/heatmap APIs, the PNG heatmap,
   and JSONL/CSV/JSON exports. Video `Range: bytes=0-1023` returned HTTP 206 and
   exactly 1,024 bytes.
8. Exported summary retained 0 confirmed PTS/REB/AST, heatmap mass 17.4 person-seconds,
   `DEMO_PARTIAL` and `NOT_ACCEPTED`. The original manifest verified successfully.

Local preparation logs and the disposable environment reside under the ignored
`.publish-check/` directory. No new inference, training or accuracy evaluation was
performed for publication. Existing historical artifact tests require inputs not
included in the published repository; the full suite is not claimed to pass in a
fresh clone. Browser visual QA remains the separately documented prior QA evidence;
the new publication checks exercise HTTP endpoints and artifact preservation.

## Remaining cleanup

Keep a separate change set for removing unused scripts, moving historical documents,
refactoring imports, splitting artifact-dependent tests, or optimizing performance.
Those changes need their own behavior comparison against this published baseline.
