"""In-memory Capture composition used before the durable persistence adapter exists."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from threading import RLock
from uuid import UUID

from app.interview_vnext.domain.hashing import canonical_json

from .artifacts import ArtifactRef, ArtifactStore
from .events import (
    ExecutionEvent,
    ExecutionEventBody,
    ExecutionTaxonomy,
    RunManifest,
    build_execution_event,
    validate_event_chain,
)
from .outbox import Outbox


class CaptureConflict(ValueError):
    pass


class CaptureRecorder:
    """Builds one ordered event chain per run and enqueues each immutable event."""

    def __init__(
        self,
        *,
        taxonomy: ExecutionTaxonomy,
        artifacts: ArtifactStore,
        outbox: Outbox,
    ) -> None:
        self._taxonomy = taxonomy
        self._artifacts = artifacts
        self._outbox = outbox
        self._events: dict[UUID, list[ExecutionEvent]] = defaultdict(list)
        self._lock = RLock()

    def record(
        self,
        *,
        event_id: UUID,
        occurred_at,
        architecture_id: str,
        workflow_version: str,
        run_id: UUID,
        session_id: UUID | None,
        event_type: str,
        stage: str,
        status,
        turn_id: UUID | None = None,
        operation_id: UUID | None = None,
        parent_operation_id: UUID | None = None,
        attempt_id: UUID | None = None,
        attempt: int | None = None,
        input_artifacts: tuple[ArtifactRef, ...] = (),
        output_artifacts: tuple[ArtifactRef, ...] = (),
        state_before_hash: str | None = None,
        state_after_hash: str | None = None,
        metadata: Mapping | None = None,
    ) -> ExecutionEvent:
        self._taxonomy.validate_names(event_type=event_type, stage=stage)
        for ref in (*input_artifacts, *output_artifacts):
            stored = self._artifacts.get(ref.artifact_id)
            if stored.ref != ref:
                raise ValueError(f"artifact reference mismatch: {ref.artifact_id}")
        with self._lock:
            chain = self._events.get(run_id, [])
            existing = next((event for event in chain if event.event_id == event_id), None)
            if existing is not None:
                supplied = {
                    "occurred_at": occurred_at,
                    "architecture_id": architecture_id,
                    "workflow_version": workflow_version,
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "operation_id": operation_id,
                    "parent_operation_id": parent_operation_id,
                    "attempt_id": attempt_id,
                    "event_type": event_type,
                    "stage": stage,
                    "attempt": attempt,
                    "status": status,
                    "input_artifacts": input_artifacts,
                    "output_artifacts": output_artifacts,
                    "state_before_hash": state_before_hash,
                    "state_after_hash": state_after_hash,
                    "metadata_json": canonical_json(dict(metadata or {})),
                }
                actual = {name: getattr(existing, name) for name in supplied}
                if actual != supplied:
                    raise CaptureConflict(
                        f"event {event_id} already exists with different content"
                    )
                self._outbox.enqueue(existing, occurred_at=existing.occurred_at)
                return existing
            if chain:
                first = chain[0]
                if (
                    first.architecture_id != architecture_id
                    or first.workflow_version != workflow_version
                    or first.session_id != session_id
                ):
                    raise CaptureConflict("run identity cannot change inside one event chain")
            body = ExecutionEventBody(
                event_id=event_id,
                occurred_at=occurred_at,
                architecture_id=architecture_id,
                workflow_version=workflow_version,
                taxonomy_id=self._taxonomy.taxonomy_id,
                taxonomy_version=self._taxonomy.version,
                taxonomy_hash=self._taxonomy.content_hash,
                run_id=run_id,
                session_id=session_id,
                turn_id=turn_id,
                operation_id=operation_id,
                parent_operation_id=parent_operation_id,
                attempt_id=attempt_id,
                event_type=event_type,
                stage=stage,
                attempt=attempt,
                status=status,
                sequence=len(chain) + 1,
                previous_event_hash=chain[-1].event_hash if chain else None,
                input_artifacts=input_artifacts,
                output_artifacts=output_artifacts,
                state_before_hash=state_before_hash,
                state_after_hash=state_after_hash,
                metadata_json=canonical_json(dict(metadata or {})),
            )
            event = build_execution_event(body)
            self._outbox.enqueue(event, occurred_at=occurred_at)
            if run_id not in self._events:
                self._events[run_id] = chain
            chain.append(event)
            return event

    def events(self, run_id: UUID) -> tuple[ExecutionEvent, ...]:
        with self._lock:
            return tuple(self._events.get(run_id, ()))

    def build_manifest(
        self,
        *,
        run_id: UUID,
        completed_at,
        root_artifacts: tuple[ArtifactRef, ...] = (),
        limitations: tuple[str, ...] = (),
    ) -> RunManifest:
        events = self.events(run_id)
        if not events:
            raise ValueError("cannot build a manifest for an empty run")
        if completed_at < events[-1].occurred_at:
            raise ValueError("run cannot complete before its final execution event")
        for ref in root_artifacts:
            if self._artifacts.get(ref.artifact_id).ref != ref:
                raise ValueError(f"root artifact reference mismatch: {ref.artifact_id}")
        manifest = RunManifest(
            architecture_id=events[0].architecture_id,
            workflow_version=events[0].workflow_version,
            taxonomy_id=self._taxonomy.taxonomy_id,
            taxonomy_version=self._taxonomy.version,
            taxonomy_hash=self._taxonomy.content_hash,
            run_id=run_id,
            session_id=events[0].session_id,
            started_at=events[0].occurred_at,
            completed_at=completed_at,
            event_count=len(events),
            first_event_hash=events[0].event_hash,
            last_event_hash=events[-1].event_hash,
            root_artifacts=root_artifacts,
            limitations=limitations,
        )
        validate_event_chain(
            events,
            taxonomy=self._taxonomy,
            artifact_store=self._artifacts,
            manifest=manifest,
        )
        return manifest
