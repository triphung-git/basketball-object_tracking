# Player and team identity contract

## Track and identity

A track ID identifies a temporary visual trajectory, not a confirmed person.
Roster/player/team fields may be populated only from explicit evidence or
user-configured assignments. If evidence conflicts or is insufficient, retain
unknown identity rather than forcing a match.

Identity annotations must not change source bbox coordinates, timestamps, or
observed/predicted status. Mapping changes are versioned and should be applied
to a rebuilt spatial map, not silently backfilled into raw tracking records.

## Team evidence

Color-based team classification is a suggestion, not a calibrated probability
or proof of player identity. Keep unknown team assignments when colors overlap,
lighting changes, or evidence is insufficient. A roster alone does not establish
which person appears in a frame.

## OCR

Jersey OCR is optional identity evidence. It is not enabled by default in the
spatial upload pipeline. When enabled in a separate local tracking workflow,
missing weights or runtime failures must remain explicit; OCR output must not
silently become a confirmed identity.

## Quality validation

Unit tests validate mapping intervals, conflicts, and identity guards. Real
identity quality requires reviewed track/person labels and reporting of coverage,
unknown rate, ID switches, and fragmentation. No accuracy target is inferred
from synthetic tests or color/OCR vote counts.
