# Task 01 — Detection runtime

## Scope

Establish a reproducible local runtime for video decoding and object detection.
The detector supplies frame-level bounding boxes used by downstream human
tracking. This task does not include game-event or player-statistics recognition.

## Runtime requirements

- Keep model/runtime dependencies pinned in the codebase manifests.
- Load credentials only from local environment configuration when required.
- Preserve original-frame bbox coordinates and source timestamps.
- Record model/runtime provenance without logging credentials or private media.
- Treat model-call latency and end-to-end video throughput as separate measures.

## Evidence and limits

Existing smoke/model reports are historical runtime checks, not ground-truth
accuracy benchmarks. Detection quality must be measured on a reviewed dataset
before claiming a precision/recall target or generalization to new cameras.
