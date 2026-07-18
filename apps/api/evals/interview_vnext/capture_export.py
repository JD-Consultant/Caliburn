"""Read-only PostgreSQL Capture bundle export for the turn eval harness (§12).

Production has no external Capture exporter in this slice, so V3-5 exports the
already-durable rows of one finalized run to a gitignored bundle. It only
reads:it may import production persistence models/serialization, but production
never imports it. Every row is re-validated through production serialization,
the event chain is verified against the persisted manifest, and a secret /
reasoning scan runs before anything is returned — a hit fails the export.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.interview_vnext.observability.artifacts import ArtifactRecord
from app.interview_vnext.observability.events import (
    ExecutionEvent,
    RunManifest,
    validate_event_chain,
)
from app.interview_vnext.observability.taxonomy import resolve_execution_taxonomy
from app.interview_vnext.persistence import serialization as ser
from app.interview_vnext.persistence.models import (
    VNextArtifactRow,
    VNextExecutionEventRow,
    VNextRunRow,
)


# §12.3 secret / reasoning gate:命中任一即 harness_invalid,不得刪字串後宣稱通過。
_SECRET_PATTERNS = (
    re.compile(r"sk-or-[A-Za-z0-9]"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"Authorization\s*[:=]"),
    re.compile(r"OPENROUTER_API_KEY"),
)


class CaptureExportError(RuntimeError):
    """A Capture bundle could not be exported cleanly (harness_invalid)."""


class SecretLeakError(CaptureExportError):
    """A secret or raw reasoning payload was found in the run's artifacts."""


class _MemoryArtifactStore:
    """In-memory ArtifactStore (duck-typed) over one run's artifacts for chain validation."""

    def __init__(self, records: dict[UUID, ArtifactRecord]) -> None:
        self._records = records

    def get(self, artifact_id: UUID) -> ArtifactRecord:
        record = self._records.get(artifact_id)
        if record is None:
            raise CaptureExportError(
                f"event references an artifact absent from the run: {artifact_id}"
            )
        return record


@dataclass(frozen=True)
class CaptureBundle:
    """Validated, secret-scanned in-memory view of one run's Capture rows."""

    tenant_id: UUID
    run_id: UUID
    run: RunManifest
    events: tuple[ExecutionEvent, ...]
    artifacts: tuple[ArtifactRecord, ...]
    manifest: RunManifest

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def last_event_hash(self) -> str:
        return self.events[-1].event_hash


def _scan_secret(text: str | None, *, where: str) -> None:
    if not text:
        return
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            raise SecretLeakError(f"possible secret in {where}: pattern {pattern.pattern}")


def _scan_reasoning(record: ArtifactRecord) -> None:
    """Raw provider reasoning may only survive as redacted metadata (§12.3)."""

    if "reasoning" in record.ref.kind and record.redaction_status != "applied":
        raise SecretLeakError(
            f"raw reasoning artifact is not redacted: {record.ref.artifact_id}"
        )


async def export_run_bundle(
    session_factory: async_sessionmaker, *, tenant_id: UUID, run_id: UUID
) -> CaptureBundle:
    """Load, revalidate and secret-scan one finalized run's Capture rows."""

    async with session_factory() as session:
        run_row = (
            await session.execute(
                sa.select(VNextRunRow).where(
                    VNextRunRow.tenant_id == tenant_id,
                    VNextRunRow.run_id == run_id,
                )
            )
        ).scalar_one_or_none()
        if run_row is None:
            raise CaptureExportError(f"run does not exist: {run_id}")
        if run_row.manifest_artifact_id is None:
            raise CaptureExportError("cannot export a non-finalized run")

        event_rows = (
            await session.execute(
                sa.select(VNextExecutionEventRow)
                .where(
                    VNextExecutionEventRow.tenant_id == tenant_id,
                    VNextExecutionEventRow.run_id == run_id,
                )
                .order_by(VNextExecutionEventRow.sequence)
            )
        ).scalars().all()
        artifact_rows = (
            await session.execute(
                sa.select(VNextArtifactRow)
                .where(
                    VNextArtifactRow.tenant_id == tenant_id,
                    VNextArtifactRow.run_id == run_id,
                )
                .order_by(VNextArtifactRow.created_at, VNextArtifactRow.artifact_id)
            )
        ).scalars().all()

    events = tuple(
        ser.load_event(
            row.event_json, row.event_hash,
            event_id=row.event_id, run_id=row.run_id, sequence=row.sequence,
        )
        for row in event_rows
    )
    if not events:
        raise CaptureExportError("finalized run has no events")

    records: dict[UUID, ArtifactRecord] = {}
    ordered_records: list[ArtifactRecord] = []
    for row in artifact_rows:
        record = ser.load_artifact(row)  # re-verifies inline hash/byte size
        _scan_secret(record.inline_content, where=f"artifact {record.ref.artifact_id}")
        _scan_reasoning(record)
        records[record.ref.artifact_id] = record
        ordered_records.append(record)

    manifest_record = records.get(run_row.manifest_artifact_id)
    if manifest_record is None or manifest_record.inline_content is None:
        raise CaptureExportError("run manifest artifact is missing or external")
    manifest = RunManifest.model_validate_json(manifest_record.inline_content)

    taxonomy = resolve_execution_taxonomy(
        run_row.taxonomy_id, run_row.taxonomy_version
    )
    store = _MemoryArtifactStore(records)
    # 事件 chain + manifest + 每個 artifact ref 的 scope/hash 一致性一起驗
    validate_event_chain(
        events, taxonomy=taxonomy, artifact_store=store, manifest=manifest
    )

    for event in events:
        _scan_secret(event.metadata_json, where=f"event {event.event_id} metadata")

    return CaptureBundle(
        tenant_id=tenant_id,
        run_id=run_id,
        run=manifest,
        events=events,
        artifacts=tuple(ordered_records),
        manifest=manifest,
    )
