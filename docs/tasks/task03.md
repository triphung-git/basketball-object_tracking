# Task 03 — Video decoding and detection

## Scope

Decode MP4 frames with source timestamps, run object detection, and save
frame-aligned detection records. Downstream consumers use this output for human
tracking and bbox overlays.

## Contracts

- Preserve original frame dimensions and bbox coordinate space.
- Keep an output record for frames with no detections.
- Preserve observed source timestamps; do not treat average FPS as the video clock.
- Record run configuration and status; never present a failed/partial run as complete.
- Write to a new run directory rather than replacing previous evidence.

## Verification

Use the detection/video unit and integration tests alongside the task-specific
spatial tests. Test success validates software behavior only; it is not a
real-footage accuracy or real-time performance claim.
