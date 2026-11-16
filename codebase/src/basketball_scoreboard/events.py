"""Unified Event Ledger for Automatic Basketball Stats Engine (Task 11).

Provides an append-only, versioned transaction ledger for basketball events:
  - Event types: SHOT, REBOUND, ASSIST, TURNOVER, FOUL
  - Event statuses: AUTO_CONFIRMED, CANDIDATE, PROVISIONAL, UNRESOLVED, VOID
  - Idempotency guards: suppresses duplicate frames, seek/re-read repeats, and out-of-order notifications.
  - Causal invalidation cascade: voiding an event cascades to dependent children (e.g. shot void -> assist void).
  - Attribution mutation guards: upgrading unknown -> known player preserves team score invariants without duplicate counting.
  - Eligibility contract: only AUTO_CONFIRMED, non-void events with valid payload and eligible dependencies contribute to confirmed box scores.
  - Immutable representation: defensive copying on ingestion and read access prevents out-of-band caller mutations.
  - Complete provenance & audit: atomic checkpoints, transaction replay, and distinction between automatic logs and human corrections.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# Sentinel for distinguishing unset parameters from explicit None values
_UNSET = object()


class EventType(str, Enum):
    """Categorical type of basketball event."""
    SHOT = "shot"
    REBOUND = "rebound"
    ASSIST = "assist"
    TURNOVER = "turnover"
    FOUL = "foul"


class EventStatus(str, Enum):
    """Lifecycle and confirmation status of an event record."""
    AUTO_CONFIRMED = "auto_confirmed"
    CANDIDATE = "candidate"
    PROVISIONAL = "provisional"
    UNRESOLVED = "unresolved"
    VOID = "void"


@dataclass
class LedgerEventRecord:
    """Canonical representation of an adjudicated basketball event."""
    event_id: str
    event_type: EventType
    source_time_s: float
    frame_index: int
    team_id: Optional[str] = None
    player_id: Optional[str] = None
    player_number: Optional[int] = None
    point_value: Optional[int] = None
    subtype: Optional[str] = None
    status: EventStatus = EventStatus.AUTO_CONFIRMED
    parent_event_id: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    revision: int = 1
    is_void: bool = False
    void_reason: Optional[str] = None
    confirmation_time_s: Optional[float] = None
    source_namespace: str = "default"
    schema_version: str = "event-ledger-v1"
    created_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if isinstance(self.event_type, str):
            self.event_type = EventType(self.event_type)
        if isinstance(self.status, str):
            self.status = EventStatus(self.status)

        # Numerical and type integrity validation
        if not math.isfinite(self.source_time_s):
            raise ValueError(f"source_time_s must be finite: {self.source_time_s}")
        if self.confirmation_time_s is not None and not math.isfinite(self.confirmation_time_s):
            raise ValueError(f"confirmation_time_s must be finite: {self.confirmation_time_s}")
        if self.frame_index < 0:
            raise ValueError(f"frame_index must be non-negative: {self.frame_index}")

        # Strict point_value validation: reject bool, floats, or invalid values
        if self.point_value is not None:
            if isinstance(self.point_value, bool) or not isinstance(self.point_value, int):
                raise ValueError(f"point_value must be int or None, got {type(self.point_value).__name__}: {self.point_value}")
            if self.point_value not in {1, 2, 3}:
                raise ValueError(f"Invalid point value: {self.point_value}")

        # Synchronize status and is_void consistently
        if self.status == EventStatus.VOID:
            self.is_void = True
        elif self.is_void:
            self.status = EventStatus.VOID

    @property
    def fingerprint(self) -> str:
        """Deterministic fingerprint for duplicate/seek idempotency."""
        parts = [
            self.source_namespace,
            self.event_type.value,
            f"{self.source_time_s:.2f}",
            str(self.team_id or "noteam"),
            str(self.player_id or "noplayer"),
            str(self.point_value or "noval"),
            str(self.parent_event_id or "noparent"),
        ]
        return hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to JSON-serializable dictionary with defensive copy of evidence."""
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "source_time_s": round(self.source_time_s, 3),
            "frame_index": self.frame_index,
            "team_id": self.team_id,
            "player_id": self.player_id,
            "player_number": self.player_number,
            "point_value": self.point_value,
            "subtype": self.subtype,
            "status": self.status.value,
            "parent_event_id": self.parent_event_id,
            "evidence": copy.deepcopy(self.evidence),
            "revision": self.revision,
            "is_void": self.is_void,
            "void_reason": self.void_reason,
            "confirmation_time_s": round(self.confirmation_time_s, 3) if self.confirmation_time_s is not None else None,
            "source_namespace": self.source_namespace,
            "fingerprint": self.fingerprint,
            "created_utc": self.created_utc,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LedgerEventRecord:
        """Reconstruct LedgerEventRecord from dictionary representation."""
        d = copy.deepcopy(data)
        d.pop("fingerprint", None)
        return cls(
            event_id=d["event_id"],
            event_type=EventType(d["event_type"]),
            source_time_s=float(d["source_time_s"]),
            frame_index=int(d["frame_index"]),
            team_id=d.get("team_id"),
            player_id=d.get("player_id"),
            player_number=d.get("player_number"),
            point_value=d.get("point_value"),
            subtype=d.get("subtype"),
            status=EventStatus(d.get("status", "auto_confirmed")),
            parent_event_id=d.get("parent_event_id"),
            evidence=d.get("evidence", {}),
            revision=int(d.get("revision", 1)),
            is_void=bool(d.get("is_void", False)),
            void_reason=d.get("void_reason"),
            confirmation_time_s=float(d["confirmation_time_s"]) if d.get("confirmation_time_s") is not None else None,
            source_namespace=d.get("source_namespace", "default"),
            schema_version=d.get("schema_version", "event-ledger-v1"),
            created_utc=d.get("created_utc", datetime.now(timezone.utc).isoformat()),
        )


@dataclass
class AuditMutation:
    """Historical record of an event modification, ingestion, or status transition."""
    mutation_id: str
    sequence: int
    event_id: str
    action: str  # "created", "revised", "voided", "cascaded_void", "dependency_invalidated", "duplicate_rejected", "no_op"
    revision: int
    previous_state: Optional[Dict[str, Any]]
    new_state: Optional[Dict[str, Any]]
    reason: str
    provenance: str = "automatic"  # "automatic", "adjudication", "human_correction"
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mutation_id": self.mutation_id,
            "sequence": self.sequence,
            "event_id": self.event_id,
            "action": self.action,
            "revision": self.revision,
            "previous_state": copy.deepcopy(self.previous_state),
            "new_state": copy.deepcopy(self.new_state),
            "reason": self.reason,
            "provenance": self.provenance,
            "timestamp_utc": self.timestamp_utc,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AuditMutation:
        return cls(
            mutation_id=data["mutation_id"],
            sequence=int(data.get("sequence", 0)),
            event_id=data["event_id"],
            action=data["action"],
            revision=int(data.get("revision", 1)),
            previous_state=data.get("previous_state"),
            new_state=data.get("new_state"),
            reason=data.get("reason", ""),
            provenance=data.get("provenance", "automatic"),
            timestamp_utc=data.get("timestamp_utc", datetime.now(timezone.utc).isoformat()),
        )


class EventLedger:
    """Append-only transaction ledger with idempotency, causal dependency tracking, and immutability."""

    def __init__(self, ledger_id: str = "default_ledger") -> None:
        self.ledger_id = ledger_id
        self._events: Dict[str, LedgerEventRecord] = {}
        self._fingerprints: Set[str] = set()
        self._fingerprint_to_event_id: Dict[str, str] = {}
        self._physical_key_to_event_id: Dict[str, str] = {}
        self._aliases: Dict[str, str] = {}  # alias_event_id -> canonical_event_id
        self._children_by_parent: Dict[str, List[str]] = {}
        self._audit_trail: List[AuditMutation] = []
        self._mutation_counter: int = 0

    def _next_mutation_id(self) -> str:
        self._mutation_counter += 1
        return f"mut_{self._mutation_counter:06d}"

    def _compute_physical_keys(self, ev: LedgerEventRecord) -> List[str]:
        """Compute authoritative physical event keys to suppress reingestion after refinement."""
        keys = []
        ns = ev.source_namespace or "default"

        # 1. Explicit external shot or source reference
        explicit_ref = (
            ev.evidence.get("source_event_id")
            or ev.evidence.get("physical_event_id")
            or ev.evidence.get("shot_id")
        )
        if explicit_ref:
            keys.append(f"{ns}:{ev.event_type.value}:ref:{explicit_ref}")

        # For SHOT events, parent_event_id is often an external shot_id (e.g. shot_123)
        if ev.event_type == EventType.SHOT and ev.parent_event_id:
            keys.append(f"{ns}:{ev.event_type.value}:ref:{ev.parent_event_id}")

        # 2. Physical temporal coordinate on court:
        # Same event_type, same temporal frame/sub-frame, and compatible team
        time_q = f"{round(ev.source_time_s, 2):.2f}"
        frame_str = str(ev.frame_index) if ev.frame_index >= 0 else "noframe"

        # Key with team
        if ev.team_id:
            keys.append(f"{ns}:{ev.event_type.value}:{ev.team_id}:{time_q}:{frame_str}")
        # Key without team (for matching team-only to player-refined events)
        keys.append(f"{ns}:{ev.event_type.value}:noteam:{time_q}:{frame_str}")

        return keys

    def _find_existing_canonical_id(self, ev: LedgerEventRecord) -> Optional[str]:
        """Check if an event is already present as an ID, alias, fingerprint, or physical event."""
        # 1. Exact ID
        if ev.event_id in self._events:
            return ev.event_id
        if ev.event_id in self._aliases:
            return self._aliases[ev.event_id]

        # 2. Fingerprint
        fp = ev.fingerprint
        if fp in self._fingerprint_to_event_id:
            return self._fingerprint_to_event_id[fp]

        # 3. Physical event keys
        for key in self._compute_physical_keys(ev):
            if key in self._physical_key_to_event_id:
                existing_id = self._physical_key_to_event_id[key]
                existing_ev = self._events.get(existing_id)
                if existing_ev:
                    # Incompatible event types or voided parent checks
                    if existing_ev.event_type == ev.event_type:
                        # If both have explicit different teams, they are not the same shot
                        if existing_ev.team_id and ev.team_id and existing_ev.team_id != ev.team_id:
                            continue
                        return existing_id

        return None

    def record_event(self, event: LedgerEventRecord, provenance: str = "automatic") -> bool:
        """Record an event with idempotency protection and defensive copying.

        Returns True if newly recorded, False if rejected as duplicate or alias.
        """
        if not isinstance(event, LedgerEventRecord):
            raise TypeError(f"Expected LedgerEventRecord, got {type(event).__name__}")

        # Check for existing canonical event
        existing_id = self._find_existing_canonical_id(event)
        if existing_id is not None:
            # Register incoming event_id as alias if different
            if event.event_id != existing_id and event.event_id not in self._aliases:
                self._aliases[event.event_id] = existing_id

            mut_id = self._next_mutation_id()
            self._audit_trail.append(
                AuditMutation(
                    mutation_id=mut_id,
                    sequence=self._mutation_counter,
                    event_id=event.event_id,
                    action="duplicate_rejected",
                    revision=0,
                    previous_state=None,
                    new_state=None,
                    reason=f"Rejected as duplicate of canonical event '{existing_id}'",
                    provenance=provenance,
                )
            )
            return False

        # Defensive deep copy: caller mutations will never affect the ledger
        ev = copy.deepcopy(event)

        # Causal dependency guard: if parent event exists and is already void, late child is void
        if ev.parent_event_id:
            parent = self._events.get(ev.parent_event_id)
            if parent and parent.is_void:
                ev.is_void = True
                ev.status = EventStatus.VOID
                ev.void_reason = f"Parent event '{ev.parent_event_id}' was already void upon arrival"

        # Register canonical event
        self._events[ev.event_id] = ev

        fp = ev.fingerprint
        self._fingerprints.add(fp)
        self._fingerprint_to_event_id[fp] = ev.event_id

        for pk in self._compute_physical_keys(ev):
            self._physical_key_to_event_id[pk] = ev.event_id

        if ev.parent_event_id:
            self._children_by_parent.setdefault(ev.parent_event_id, []).append(ev.event_id)

        mut_id = self._next_mutation_id()
        self._audit_trail.append(
            AuditMutation(
                mutation_id=mut_id,
                sequence=self._mutation_counter,
                event_id=ev.event_id,
                action="created",
                revision=ev.revision,
                previous_state=None,
                new_state=ev.to_dict(),
                reason="initial_event_ingestion",
                provenance=provenance,
            )
        )
        return True

    def get_event(self, event_id: str) -> Optional[LedgerEventRecord]:
        """Retrieve a defensive copy of a recorded event."""
        canon_id = self._aliases.get(event_id, event_id)
        ev = self._events.get(canon_id)
        return copy.deepcopy(ev) if ev is not None else None

    def revise_event(
        self,
        event_id: str,
        new_player_id: Any = _UNSET,
        new_player_number: Any = _UNSET,
        new_team_id: Any = _UNSET,
        new_point_value: Any = _UNSET,
        new_status: Any = _UNSET,
        expected_revision: Optional[int] = None,
        reason: str = "manual_or_ocr_refinement",
        provenance: str = "automatic",
    ) -> Optional[LedgerEventRecord]:
        """Revise an existing event and log the audit entry.

        Distinguishes unset fields from clearing fields to None.
        Supports expected_revision checking for optimistic locking.
        """
        canon_id = self._aliases.get(event_id, event_id)
        ev = self._events.get(canon_id)
        if not ev or ev.is_void:
            return None

        # Check expected revision conflict
        if expected_revision is not None and ev.revision != expected_revision:
            mut_id = self._next_mutation_id()
            self._audit_trail.append(
                AuditMutation(
                    mutation_id=mut_id,
                    sequence=self._mutation_counter,
                    event_id=canon_id,
                    action="conflict_rejected",
                    revision=ev.revision,
                    previous_state=ev.to_dict(),
                    new_state=None,
                    reason=f"Revision conflict: expected revision {expected_revision}, current is {ev.revision}",
                    provenance=provenance,
                )
            )
            return None

        prev_dict = ev.to_dict()

        # Validate proposed revisions
        if new_point_value is not _UNSET and new_point_value is not None:
            if isinstance(new_point_value, bool) or not isinstance(new_point_value, int) or new_point_value not in {1, 2, 3}:
                raise ValueError(f"Invalid revised point value: {new_point_value}")

        if new_status is not _UNSET and new_status is not None:
            if isinstance(new_status, str):
                new_status = EventStatus(new_status)

        # Check for no-op revision
        changed = False
        if new_player_id is not _UNSET and ev.player_id != new_player_id:
            changed = True
        if new_player_number is not _UNSET and ev.player_number != new_player_number:
            changed = True
        if new_team_id is not _UNSET and ev.team_id != new_team_id:
            changed = True
        if new_point_value is not _UNSET and ev.point_value != new_point_value:
            changed = True
        if new_status is not _UNSET and ev.status != new_status:
            changed = True

        if not changed:
            mut_id = self._next_mutation_id()
            self._audit_trail.append(
                AuditMutation(
                    mutation_id=mut_id,
                    sequence=self._mutation_counter,
                    event_id=canon_id,
                    action="no_op",
                    revision=ev.revision,
                    previous_state=prev_dict,
                    new_state=prev_dict,
                    reason=f"No-op revision: no fields changed ({reason})",
                    provenance=provenance,
                )
            )
            return copy.deepcopy(ev)

        # Apply mutations
        old_team_id = ev.team_id
        old_status = ev.status

        if new_player_id is not _UNSET:
            ev.player_id = new_player_id
        if new_player_number is not _UNSET:
            ev.player_number = new_player_number
        if new_team_id is not _UNSET:
            ev.team_id = new_team_id
        if new_point_value is not _UNSET:
            ev.point_value = new_point_value
        if new_status is not _UNSET:
            ev.status = new_status
            if ev.status == EventStatus.VOID:
                ev.is_void = True
                ev.void_reason = reason

        ev.revision += 1

        # Re-index new fingerprint and physical keys while preserving older index lookups
        new_fp = ev.fingerprint
        self._fingerprints.add(new_fp)
        self._fingerprint_to_event_id[new_fp] = canon_id

        for pk in self._compute_physical_keys(ev):
            self._physical_key_to_event_id[pk] = canon_id

        mut_id = self._next_mutation_id()
        self._audit_trail.append(
            AuditMutation(
                mutation_id=mut_id,
                sequence=self._mutation_counter,
                event_id=canon_id,
                action="revised",
                revision=ev.revision,
                previous_state=prev_dict,
                new_state=ev.to_dict(),
                reason=reason,
                provenance=provenance,
            )
        )

        # Invalidation notifications for causal children if team or confirmation status changed
        status_changed_to_ineligible = (new_status is not _UNSET and new_status != EventStatus.AUTO_CONFIRMED)
        team_changed = (new_team_id is not _UNSET and new_team_id != old_team_id)

        if status_changed_to_ineligible or team_changed:
            children = self._children_by_parent.get(canon_id, [])
            for cid in children:
                child_ev = self._events.get(cid)
                if child_ev and not child_ev.is_void:
                    c_mut_id = self._next_mutation_id()
                    self._audit_trail.append(
                        AuditMutation(
                            mutation_id=c_mut_id,
                            sequence=self._mutation_counter,
                            event_id=cid,
                            action="dependency_invalidated",
                            revision=child_ev.revision,
                            previous_state=child_ev.to_dict(),
                            new_state=child_ev.to_dict(),
                            reason=f"Parent event '{canon_id}' revised to incompatible state (team={ev.team_id}, status={ev.status.value})",
                            provenance=provenance,
                        )
                    )

        return copy.deepcopy(ev)

    def void_event(self, event_id: str, reason: str = "adjudication_correction", provenance: str = "automatic") -> List[str]:
        """Void an event and cascade invalidation to all causal children.

        Returns the list of all voided event IDs (including children).
        """
        canon_id = self._aliases.get(event_id, event_id)
        ev = self._events.get(canon_id)
        if not ev or ev.is_void:
            return []

        voided_ids = [canon_id]
        prev_dict = ev.to_dict()
        ev.is_void = True
        ev.status = EventStatus.VOID
        ev.void_reason = reason
        ev.revision += 1

        mut_id = self._next_mutation_id()
        self._audit_trail.append(
            AuditMutation(
                mutation_id=mut_id,
                sequence=self._mutation_counter,
                event_id=canon_id,
                action="voided",
                revision=ev.revision,
                previous_state=prev_dict,
                new_state=ev.to_dict(),
                reason=reason,
                provenance=provenance,
            )
        )

        # Invalidation cascade: any event having this event as parent_event_id is also voided
        children = self._children_by_parent.get(canon_id, [])
        for cid in children:
            child_ev = self._events.get(cid)
            if child_ev and not child_ev.is_void:
                cascade_reason = f"Cascaded invalidation: parent event {canon_id} voided ({reason})"
                sub_voided = self.void_event(cid, reason=cascade_reason, provenance=provenance)
                voided_ids.extend(sub_voided)

        return voided_ids

    def is_event_eligible(self, ev: LedgerEventRecord) -> bool:
        """Centralized eligibility evaluation contract.

        Only events that are AUTO_CONFIRMED, non-void, have valid payload,
        and whose causal dependencies are satisfied can contribute to confirmed box scores.
        """
        if ev.is_void or ev.status != EventStatus.AUTO_CONFIRMED:
            return False

        # Event-specific eligibility contracts
        if ev.event_type == EventType.SHOT:
            # A shot without resolved point value is an unresolved shot
            if ev.point_value is None:
                return False
            if ev.point_value not in {1, 2, 3}:
                return False
            return True

        if ev.event_type == EventType.ASSIST:
            # Assist must be linked to an eligible made shot event
            if not ev.parent_event_id:
                return False
            parent = self._events.get(ev.parent_event_id)
            if not parent:
                # Parent has not arrived yet: assist remains pending/ineligible
                return False
            if parent.is_void or parent.status != EventStatus.AUTO_CONFIRMED:
                return False
            # Team compatibility: passer and scorer must be on the same team
            if parent.team_id and ev.team_id and parent.team_id != ev.team_id:
                return False
            # Self-assist guard: passer cannot be scorer
            if parent.player_id and ev.player_id and parent.player_id == ev.player_id:
                return False
            return True

        if ev.event_type == EventType.REBOUND:
            # Rebound must have valid classification and eligible parent if present in ledger
            if ev.parent_event_id:
                parent = self._events.get(ev.parent_event_id)
                if parent:
                    if parent.is_void:
                        return False
                    # A rebound parent cannot be a confirmed made basket!
                    if (
                        parent.event_type == EventType.SHOT
                        and parent.point_value is not None
                        and parent.point_value > 0
                        and not parent.is_void
                    ):
                        return False
            return True

        if ev.event_type == EventType.TURNOVER:
            return True

        return True

    def get_active_events(
        self,
        event_types: Optional[Set[EventType]] = None,
        statuses: Optional[Set[EventStatus]] = None,
    ) -> List[LedgerEventRecord]:
        """Retrieve defensive copies of active (non-void) events matching criteria in temporal sequence."""
        res = [e for e in self._events.values() if not e.is_void]
        if event_types:
            res = [e for e in res if e.event_type in event_types]
        if statuses:
            res = [e for e in res if e.status in statuses]
        res = sorted(res, key=lambda x: (x.source_time_s, x.frame_index))
        return [copy.deepcopy(e) for e in res]

    def get_all_events(self) -> List[LedgerEventRecord]:
        """Retrieve defensive copies of all recorded events (including void)."""
        res = sorted(self._events.values(), key=lambda x: (x.source_time_s, x.frame_index))
        return [copy.deepcopy(e) for e in res]

    def get_audit_trail(self) -> List[AuditMutation]:
        """Retrieve defensive copy of the audit trail."""
        return [copy.deepcopy(m) for m in self._audit_trail]

    def export_jsonl(self, path: Path | str) -> int:
        """Export active confirmed and unresolved events to JSONL (materialized view)."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        active = self.get_active_events()
        with p.open("w", encoding="utf-8") as handle:
            for ev in active:
                handle.write(json.dumps(ev.to_dict(), ensure_ascii=False) + "\n")
        return len(active)

    def export_raw_transactions(self, path: Path | str) -> int:
        """Export append-only raw transaction mutations to JSONL."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        mutations = self.get_audit_trail()
        with p.open("w", encoding="utf-8") as handle:
            for mut in mutations:
                handle.write(json.dumps(mut.to_dict(), ensure_ascii=False) + "\n")
        return len(mutations)

    def export_audit_log(self, path: Path | str) -> int:
        """Backwards-compatible alias for export_raw_transactions."""
        return self.export_raw_transactions(path)

    def save_checkpoint(self, path: Path | str) -> Dict[str, Any]:
        """Atomically save complete ledger checkpoint to disk with integrity checksum."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp_p = p.with_suffix(".tmp")

        serialized_events = {eid: ev.to_dict() for eid, ev in sorted(self._events.items())}
        events_json = json.dumps(serialized_events, sort_keys=True, ensure_ascii=False)
        checksum = hashlib.sha256(events_json.encode("utf-8")).hexdigest()

        checkpoint_data = {
            "schema_version": "event-ledger-checkpoint-v1",
            "ledger_id": self.ledger_id,
            "sequence_position": self._mutation_counter,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "checksum": checksum,
            "events": serialized_events,
            "aliases": dict(sorted(self._aliases.items())),
            "fingerprints": sorted(self._fingerprints),
            "fingerprint_to_event_id": dict(sorted(self._fingerprint_to_event_id.items())),
            "physical_key_to_event_id": dict(sorted(self._physical_key_to_event_id.items())),
            "children_by_parent": {pid: sorted(cids) for pid, cids in sorted(self._children_by_parent.items())},
        }

        with tmp_p.open("w", encoding="utf-8") as f:
            json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())

        tmp_p.replace(p)
        return checkpoint_data

    @classmethod
    def load_checkpoint(cls, path: Path | str) -> EventLedger:
        """Load and verify an atomic checkpoint from disk."""
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"Checkpoint file does not exist: {path}")

        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if data.get("schema_version") != "event-ledger-checkpoint-v1":
            raise ValueError(f"Unsupported checkpoint schema: {data.get('schema_version')}")

        # Verify integrity checksum
        serialized_events = data.get("events", {})
        events_json = json.dumps(serialized_events, sort_keys=True, ensure_ascii=False)
        expected_checksum = data.get("checksum")
        actual_checksum = hashlib.sha256(events_json.encode("utf-8")).hexdigest()

        if expected_checksum != actual_checksum:
            raise ValueError(f"Checkpoint integrity failure: expected checksum {expected_checksum}, calculated {actual_checksum}")

        ledger = cls(ledger_id=data.get("ledger_id", "default_ledger"))
        ledger._mutation_counter = int(data.get("sequence_position", 0))

        # Reconstruct canonical events
        for eid, ev_dict in serialized_events.items():
            ev = LedgerEventRecord.from_dict(ev_dict)
            ledger._events[eid] = ev

        ledger._aliases = dict(data.get("aliases", {}))
        ledger._fingerprints = set(data.get("fingerprints", []))
        ledger._fingerprint_to_event_id = dict(data.get("fingerprint_to_event_id", {}))
        ledger._physical_key_to_event_id = dict(data.get("physical_key_to_event_id", {}))
        ledger._children_by_parent = {pid: list(cids) for pid, cids in data.get("children_by_parent", {}).items()}

        return ledger

    def replay_transactions(self, log_path: Path | str) -> int:
        """Replay transaction mutations from an append-only JSONL log starting after sequence_position."""
        p = Path(log_path)
        if not p.is_file():
            raise FileNotFoundError(f"Transaction log does not exist: {log_path}")

        applied = 0
        with p.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                raw = line.strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw)
                    mut = AuditMutation.from_dict(row)
                except Exception as e:
                    raise ValueError(f"Malformed transaction at line {line_no}: {e}")

                if mut.sequence <= self._mutation_counter:
                    continue  # Already applied prior to checkpoint

                # Apply mutation
                action = mut.action
                if action == "created" and mut.new_state:
                    ev = LedgerEventRecord.from_dict(mut.new_state)
                    self._events[ev.event_id] = ev
                    self._fingerprints.add(ev.fingerprint)
                    self._fingerprint_to_event_id[ev.fingerprint] = ev.event_id
                    for pk in self._compute_physical_keys(ev):
                        self._physical_key_to_event_id[pk] = ev.event_id
                    if ev.parent_event_id:
                        self._children_by_parent.setdefault(ev.parent_event_id, []).append(ev.event_id)
                elif action == "revised" and mut.new_state:
                    ev = LedgerEventRecord.from_dict(mut.new_state)
                    self._events[ev.event_id] = ev
                    self._fingerprints.add(ev.fingerprint)
                    self._fingerprint_to_event_id[ev.fingerprint] = ev.event_id
                    for pk in self._compute_physical_keys(ev):
                        self._physical_key_to_event_id[pk] = ev.event_id
                elif action in {"voided", "cascaded_void"} and mut.new_state:
                    ev = LedgerEventRecord.from_dict(mut.new_state)
                    self._events[ev.event_id] = ev

                self._mutation_counter = max(self._mutation_counter, mut.sequence)
                self._audit_trail.append(mut)
                applied += 1

        return applied

    @classmethod
    def from_raw_log(cls, log_path: Path | str, ledger_id: str = "default_ledger") -> EventLedger:
        """Construct complete EventLedger state from scratch by replaying raw append-only transaction log."""
        ledger = cls(ledger_id=ledger_id)
        ledger.replay_transactions(log_path)
        return ledger


def point_event_to_ledger_record(
    point_ev: Any,
    frame_index: Optional[int] = None,
) -> LedgerEventRecord:
    """Helper to convert a PointEventRecord into a canonical LedgerEventRecord.

    Preserves source event timestamp (source_time_s), confirmation_time_s,
    and external shot references in evidence without conflation.
    """
    src_t = getattr(point_ev, "source_time_s", None)
    conf_t = getattr(point_ev, "confirmation_time_s", None)

    # Actual event timestamp is source_time_s; fallback to confirmation_time_s if source missing
    t_s = float(src_t if src_t is not None else (conf_t if conf_t is not None else 0.0))
    fidx = int(frame_index if frame_index is not None else 0)
    pt_val = getattr(point_ev, "point_value", None)
    status_str = str(getattr(point_ev, "status", "unresolved")).lower()

    if status_str in {"confirmed", "auto_confirmed"} and pt_val is not None:
        status = EventStatus.AUTO_CONFIRMED
    elif status_str == "void":
        status = EventStatus.VOID
    elif status_str == "candidate":
        status = EventStatus.CANDIDATE
    elif status_str == "provisional":
        status = EventStatus.PROVISIONAL
    else:
        status = EventStatus.UNRESOLVED

    ev_id = getattr(point_ev, "event_id", None) or f"shot_{int(t_s*100):06d}_{pt_val or 0}pt"
    attr_lvl = getattr(point_ev, "attribution_level", None)
    val_reason = getattr(point_ev, "value_reason", None)
    shot_id = getattr(point_ev, "shot_id", None)

    evidence_refs = copy.deepcopy(getattr(point_ev, "evidence_refs", {}))
    if conf_t is not None:
        evidence_refs["confirmation_time_s"] = conf_t
    if shot_id:
        evidence_refs["shot_id"] = shot_id

    return LedgerEventRecord(
        event_id=ev_id,
        event_type=EventType.SHOT,
        source_time_s=t_s,
        frame_index=fidx,
        team_id=getattr(point_ev, "scoring_team_id", None),
        player_id=getattr(point_ev, "scoring_player_id", None),
        player_number=None,
        point_value=pt_val,
        subtype="free_throw" if (val_reason and "free_throw" in str(val_reason).lower()) else "field_goal",
        status=status,
        parent_event_id=shot_id,
        confirmation_time_s=float(conf_t) if conf_t is not None else None,
        evidence={
            "attribution_level": attr_lvl.value if hasattr(attr_lvl, "value") else str(attr_lvl),
            "value_reason": val_reason.value if hasattr(val_reason, "value") else str(val_reason),
            "evidence_refs": evidence_refs,
        },
    )
