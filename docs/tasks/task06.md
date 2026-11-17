# Task 06 — Human tracking and identity

## Scope

Maintain human bounding boxes and track IDs across frames. Optional roster,
team-color, or manual identity evidence may annotate tracks; it must not alter
the original detections or invent court positions.

## Reliability rules

- Preserve observed and predicted track samples as distinct states.
- Do not infer identity from track ID alone.
- Keep unknown team/player assignment when evidence is insufficient.
- Maintain source timestamps and raw bbox provenance.
- Keep event/game-statistics logic outside the tracking pipeline.

## Verification status

Unit and integration tests validate track lifecycle, identity guards, and output
contracts. Real tracking quality still requires annotated video for the target
camera and measurement of ID switches, fragmentation, missed detections, and
coverage. Test results are not an accuracy guarantee.
