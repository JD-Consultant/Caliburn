"""PostgreSQL Saver/Store ownership for one durable consultant document.

This adapter intentionally exposes product commands over LangGraph's public
Saver/Store APIs.  It does not mirror semantic state into application tables:
the only Caliburn-owned table is a minimal document catalog/tombstone.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Mapping, Sequence
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid5

import psycopg
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.store.base import PutOp
from langgraph.store.postgres.aio import AsyncPostgresStore
from langgraph.types import Command
from pydantic import JsonValue
from psycopg import AsyncConnection
from psycopg.rows import DictRow, dict_row

from app.consultant.graph import StaleThreadRevision, build_consultant_graph
from app.consultant.clarification import ClarificationAnswer
from app.consultant.candidate_wire import map_candidate_edit_batch
from app.consultant.candidate_workspace import (
    CandidateEditReceipt,
    CandidateRevisionConflict,
    CandidateStageRequest,
    CandidateToolCallConflict,
    CandidateWorkspace,
    VerifiedCandidateStage,
    candidate_mapping_authority,
    candidate_request_sha256,
    materialize_candidate_workspace,
)
from app.consultant.document_authority import edited_action_source_payload
from app.consultant.document_review import apply_review_command
from app.consultant.interview import VerifiedConsultantCommit
from app.consultant.state import (
    ApprovedJobDocument,
    CalibrationDecision,
    CalibrationStatus,
    CommandReceipt,
    CommandReceiptConflict,
    DocumentChangeSet,
    DocumentChangeStatus,
    DurableModel,
    EmployeeSource,
    EmployeeSourceKind,
    QuoteAnchor,
    SourceProcessingStatus,
    SourcePositionAnchor,
    SourceReference,
    SourceValidity,
    RequiredClarification,
    RunReceipt,
    RunExecutionEvidence,
    RunStatus,
    UnderstandingCalibration,
    inspect_command_receipt,
)
from app.consultant.views import ConsultantSnapshot, snapshot_from_state
from app.consultant.verification import verify_candidate_document_changes


SourceHook = Callable[[EmployeeSource], Awaitable[None]]


class ConsultantPersistenceError(RuntimeError):
    pass


class DocumentNotFound(ConsultantPersistenceError):
    pass


class SourceConflict(ConsultantPersistenceError):
    pass


class IdempotencyConflict(ConsultantPersistenceError):
    pass


class PendingSourceRequiresReconciliation(ConsultantPersistenceError):
    pass


class StaleRevision(ConsultantPersistenceError):
    pass


class QuoteAnchorMismatch(ConsultantPersistenceError):
    pass


class UnknownEvidenceSource(ConsultantPersistenceError):
    pass


class ActiveConsultantRun(ConsultantPersistenceError):
    pass


class ConsultantDocumentCatalogEntry(DurableModel):
    document_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


def psycopg_connection_string(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if database_url.startswith("postgresql://"):
        return database_url
    raise ValueError("consultant runtime requires a PostgreSQL connection URL")


class PostgresConsultantRuntime:
    def __init__(
        self,
        *,
        saver: AsyncPostgresSaver,
        store: AsyncPostgresStore,
        catalog_connection: AsyncConnection[DictRow],
        strict_serializer: JsonPlusSerializer,
    ) -> None:
        self.saver = saver
        self.store = store
        self._catalog_connection = catalog_connection
        self._strict_serializer = strict_serializer
        self.graph = build_consultant_graph(saver, store)
        self._document_locks: dict[UUID, asyncio.Lock] = {}
        self._after_source_store: SourceHook = self._noop_source_hook
        self._after_source_checkpoint: SourceHook = self._noop_source_hook

    @staticmethod
    async def _noop_source_hook(_source: EmployeeSource) -> None:
        return None

    async def setup(self) -> None:
        """Run only the framework-owned, idempotent Saver/Store migrations."""
        await self.saver.setup()
        await self.store.setup()

    @staticmethod
    def graph_config(document_id: UUID) -> dict[str, dict[str, str]]:
        if not isinstance(document_id, UUID):
            raise TypeError("document_id must be an application-issued UUID")
        return {"configurable": {"thread_id": str(document_id)}}

    @staticmethod
    def source_namespace(document_id: UUID) -> tuple[str, str, str, str]:
        if not isinstance(document_id, UUID):
            raise TypeError("document_id must be an application-issued UUID")
        return ("caliburn", "consultant", str(document_id), "sources")

    def connection_invariants(self) -> dict[str, bool]:
        saver_connection = self.saver.conn
        store_connection = self.store.conn
        return {
            "saver_autocommit": bool(saver_connection.autocommit),
            "saver_dict_rows": saver_connection.row_factory is dict_row,
            "store_autocommit": bool(store_connection.autocommit),
            "store_dict_rows": store_connection.row_factory is dict_row,
            "strict_msgpack": (
                self._strict_serializer._allowed_msgpack_modules is None  # noqa: SLF001
                and not self._strict_serializer.pickle_fallback
            ),
        }

    def _lock_for(self, document_id: UUID) -> asyncio.Lock:
        return self._document_locks.setdefault(document_id, asyncio.Lock())

    async def _catalog_row(self, document_id: UUID) -> dict[str, Any] | None:
        async with self._catalog_connection.cursor() as cursor:
            await cursor.execute(
                """
                SELECT document_id, thread_id, title, created_at, updated_at,
                       deleted_at
                FROM consultant_documents
                WHERE document_id = %s
                """,
                (document_id,),
            )
            return await cursor.fetchone()

    async def _require_active_catalog(self, document_id: UUID) -> dict[str, Any]:
        row = await self._catalog_row(document_id)
        if row is None or row["deleted_at"] is not None:
            raise DocumentNotFound(f"consultant document {document_id} was not found")
        if row["thread_id"] != document_id:
            raise ConsultantPersistenceError("catalog thread scope is inconsistent")
        return row

    async def list_documents(self) -> tuple[ConsultantDocumentCatalogEntry, ...]:
        async with self._catalog_connection.cursor() as cursor:
            await cursor.execute(
                """
                SELECT document_id, title, created_at, updated_at
                FROM consultant_documents
                WHERE deleted_at IS NULL
                ORDER BY created_at, document_id
                """
            )
            rows = await cursor.fetchall()
        return tuple(
            ConsultantDocumentCatalogEntry.model_validate(row) for row in rows
        )

    async def get_document_catalog_entry(
        self, document_id: UUID
    ) -> ConsultantDocumentCatalogEntry:
        row = await self._require_active_catalog(document_id)
        return ConsultantDocumentCatalogEntry(
            document_id=row["document_id"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def _touch_catalog(self, document_id: UUID) -> None:
        async with self._catalog_connection.cursor() as cursor:
            await cursor.execute(
                """
                UPDATE consultant_documents
                SET updated_at = now()
                WHERE document_id = %s AND deleted_at IS NULL
                """,
                (document_id,),
            )
            if cursor.rowcount != 1:
                raise DocumentNotFound(
                    f"consultant document {document_id} was not found"
                )

    async def create_document(
        self, document_id: UUID, *, title: str
    ) -> ConsultantSnapshot:
        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError("document title must not be empty")
        async with self._lock_for(document_id):
            async with self._catalog_connection.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO consultant_documents (
                        document_id, thread_id, title
                    ) VALUES (%s, %s, %s)
                    ON CONFLICT (document_id) DO NOTHING
                    """,
                    (document_id, document_id, normalized_title),
                )
                created = cursor.rowcount == 1
            catalog = await self._require_active_catalog(document_id)
            if not created and catalog["title"] != normalized_title:
                raise IdempotencyConflict(
                    "document idempotency key was reused with another title"
                )
            config = self.graph_config(document_id)
            state = await self.graph.aget_state(config)
            if not state.values:
                await self.graph.ainvoke(
                    {},
                    config,
                    context={
                        "action": "initialize",
                        "document_id": str(document_id),
                    },
                )
            return await self._snapshot(document_id)

    async def reopen_document(self, document_id: UUID) -> ConsultantSnapshot:
        await self._require_active_catalog(document_id)
        return await self._snapshot(document_id)

    async def _snapshot(self, document_id: UUID) -> ConsultantSnapshot:
        state = await self.graph.aget_state(self.graph_config(document_id))
        if not state.values:
            raise DocumentNotFound(
                f"consultant checkpoint for {document_id} was not found"
            )
        return snapshot_from_state(state.values)

    async def raw_state(self, document_id: UUID) -> dict[str, Any]:
        await self._require_active_catalog(document_id)
        state = await self.graph.aget_state(self.graph_config(document_id))
        return deepcopy(state.values)

    async def get_source_or_none(
        self, document_id: UUID, source_id: UUID
    ) -> EmployeeSource | None:
        item = await self.store.aget(self.source_namespace(document_id), str(source_id))
        if item is None:
            return None
        return EmployeeSource.model_validate(item.value)

    async def get_source(
        self, document_id: UUID, source_id: UUID
    ) -> EmployeeSource:
        source = await self.get_source_or_none(document_id, source_id)
        if source is None:
            raise KeyError(f"employee source {source_id} was not found")
        return source

    async def list_sources(self, document_id: UUID) -> tuple[EmployeeSource, ...]:
        await self._require_active_catalog(document_id)
        namespace = self.source_namespace(document_id)
        sources: list[EmployeeSource] = []
        offset = 0
        while items := await self.store.asearch(
            namespace,
            limit=100,
            offset=offset,
        ):
            sources.extend(EmployeeSource.model_validate(item.value) for item in items)
            if len(items) < 100:
                break
            offset += len(items)
        sources.sort(key=lambda item: (item.created_at, str(item.source_id)))
        return tuple(sources)

    @staticmethod
    def _same_immutable_source(
        persisted: EmployeeSource, requested: EmployeeSource
    ) -> bool:
        return all(
            getattr(persisted, field) == getattr(requested, field)
            for field in (
                "source_id",
                "document_id",
                "kind",
                "speaker",
                "text",
                "text_sha256",
                "supersedes_source_id",
                "positions",
            )
        )

    async def _pending_sources(self, document_id: UUID) -> list[EmployeeSource]:
        items = await self.store.asearch(
            self.source_namespace(document_id),
            filter={"processing_status": SourceProcessingStatus.PENDING.value},
            limit=10,
        )
        return [EmployeeSource.model_validate(item.value) for item in items]

    async def _put_source(self, source: EmployeeSource) -> None:
        await self.store.aput(
            self.source_namespace(source.document_id),
            str(source.source_id),
            source.model_dump(mode="json"),
            index=False,
        )

    async def _put_sources_atomically(
        self, sources: Iterable[EmployeeSource]
    ) -> None:
        operations = [
            PutOp(
                self.source_namespace(source.document_id),
                str(source.source_id),
                source.model_dump(mode="json"),
                index=False,
            )
            for source in sources
        ]
        await self.store.abatch(operations)

    async def _prepare_new_source(self, requested: EmployeeSource) -> EmployeeSource:
        pending = await self._pending_sources(requested.document_id)
        if pending:
            raise PendingSourceRequiresReconciliation(
                f"source {pending[0].source_id} must be reconciled before new input"
            )
        if requested.supersedes_source_id is not None:
            original = await self.get_source(
                requested.document_id, requested.supersedes_source_id
            )
            if original.validity is SourceValidity.SUPERSEDED:
                raise SourceConflict(
                    f"source {original.source_id} was already superseded"
                )
            superseded = original.model_copy(
                update={
                    "validity": SourceValidity.SUPERSEDED,
                    "superseded_by_source_id": requested.source_id,
                }
            )
            await self._put_sources_atomically((superseded, requested))
            return requested
        await self._put_source(requested)
        return requested

    async def _load_or_prepare_source(
        self, requested: EmployeeSource
    ) -> EmployeeSource:
        existing = await self.get_source_or_none(
            requested.document_id, requested.source_id
        )
        if existing is None:
            return await self._prepare_new_source(requested)
        if not self._same_immutable_source(existing, requested):
            raise SourceConflict(
                f"source {requested.source_id} immutable payload conflicts"
            )
        return existing

    async def _commit_source_reference(
        self,
        *,
        source: EmployeeSource,
        snapshot: ConsultantSnapshot,
        action: str,
        approved_document: ApprovedJobDocument | None = None,
        command_fields: Mapping[str, Any] | None = None,
    ) -> ConsultantSnapshot:
        if snapshot.latest_source_id == source.source_id and not command_fields:
            return snapshot
        reference = SourceReference(
            source_id=source.source_id,
            kind=source.kind,
            created_at=source.created_at,
            supersedes_source_id=source.supersedes_source_id,
        )
        command: dict[str, Any] = {
            "action": action,
            "document_id": str(source.document_id),
            "expected_revision": snapshot.revision,
            "source_reference": reference.model_dump(mode="json"),
        }
        if approved_document is not None:
            command["approved_document"] = approved_document.model_dump(mode="json")
        if command_fields is not None:
            command.update(command_fields)
        try:
            await self.graph.ainvoke(
                {},
                self.graph_config(source.document_id),
                context=command,
            )
        except StaleThreadRevision as error:
            raise StaleRevision(str(error)) from error
        return await self._snapshot(source.document_id)

    async def _mark_source_committed(self, source: EmployeeSource) -> None:
        if source.processing_status is SourceProcessingStatus.COMMITTED:
            return
        await self._put_source(
            source.model_copy(
                update={"processing_status": SourceProcessingStatus.COMMITTED}
            )
        )

    @staticmethod
    def _inspect_command_receipt(
        raw_state: Mapping[str, Any],
        receipt: CommandReceipt | None,
    ) -> Literal["new", "replay"]:
        if receipt is None:
            return "new"
        try:
            return inspect_command_receipt(raw_state, receipt)
        except CommandReceiptConflict as error:
            raise IdempotencyConflict(str(error)) from error

    async def _reconcile_replayed_command_source(
        self,
        document_id: UUID,
        source_id: UUID | None,
    ) -> None:
        """Finish Store status after a checkpoint-first crash on exact replay."""

        if source_id is None:
            return
        source = await self.get_source_or_none(document_id, source_id)
        if (
            source is not None
            and source.processing_status is SourceProcessingStatus.PENDING
        ):
            await self._mark_source_committed(source)

    async def record_employee_source(
        self,
        *,
        document_id: UUID,
        source_id: UUID,
        kind: EmployeeSourceKind,
        text: str,
        supersedes_source_id: UUID | None = None,
    ) -> ConsultantSnapshot:
        if kind is not EmployeeSourceKind.EMPLOYEE_TURN:
            raise ValueError(
                "direct-edit evidence can only be minted by an authority command"
            )
        async with self._lock_for(document_id):
            await self._require_active_catalog(document_id)
            requested = EmployeeSource.pending(
                source_id=source_id,
                document_id=document_id,
                kind=kind,
                text=text,
                supersedes_source_id=supersedes_source_id,
            )
            source = await self._load_or_prepare_source(requested)
            snapshot = await self._snapshot(document_id)
            if source.processing_status is SourceProcessingStatus.COMMITTED:
                return snapshot
            await self._after_source_store(source)
            snapshot = await self._commit_source_reference(
                source=source,
                snapshot=snapshot,
                action="register_source",
            )
            await self._touch_catalog(document_id)
            await self._after_source_checkpoint(source)
            await self._mark_source_committed(source)
            return snapshot

    async def admit_employee_answer(
        self,
        *,
        document_id: UUID,
        run_id: UUID,
        source_id: UUID,
        text: str,
        supersedes_source_id: UUID | None = None,
    ) -> tuple[ConsultantSnapshot, bool]:
        """Persist the exact answer before allowing any model-bearing work."""

        async with self._lock_for(document_id):
            await self._require_active_catalog(document_id)
            requested = EmployeeSource.pending(
                source_id=source_id,
                document_id=document_id,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text=text,
                supersedes_source_id=supersedes_source_id,
            )
            existing = await self.get_source_or_none(document_id, source_id)
            if existing is not None and not self._same_immutable_source(
                existing, requested
            ):
                raise SourceConflict(
                    f"source {source_id} immutable payload conflicts"
                )

            snapshot = await self._snapshot(document_id)
            latest = (
                RunReceipt.model_validate(snapshot.latest_run)
                if snapshot.latest_run is not None
                else None
            )
            if latest is not None and latest.status in {
                RunStatus.SOURCE_SAVED,
                RunStatus.FAILED,
            }:
                replaces_failed_source = (
                    latest.status is RunStatus.FAILED
                    and supersedes_source_id == latest.source_id
                    and source_id != latest.source_id
                    and run_id != latest.run_id
                )
                if not replaces_failed_source:
                    if latest.run_id != run_id or latest.source_id != source_id:
                        raise ActiveConsultantRun(
                            f"consultant run {latest.run_id} must be resolved first"
                        )
                    if existing is None:
                        raise ConsultantPersistenceError(
                            "recoverable run is missing its employee source"
                        )
                    if existing.processing_status is SourceProcessingStatus.PENDING:
                        await self._mark_source_committed(existing)
                    if latest.status is RunStatus.SOURCE_SAVED:
                        return snapshot, False
                    receipt = RunReceipt(
                        run_id=run_id,
                        status=RunStatus.SOURCE_SAVED,
                        source_id=source_id,
                        started_at=datetime.now(UTC),
                    )
                    try:
                        await self.graph.ainvoke(
                            {},
                            self.graph_config(document_id),
                            context={
                                "action": "restart_consultant_run",
                                "document_id": str(document_id),
                                "expected_revision": snapshot.revision,
                                "run_receipt": receipt.model_dump(mode="json"),
                            },
                        )
                    except StaleThreadRevision as error:
                        raise StaleRevision(str(error)) from error
                    await self._touch_catalog(document_id)
                    return await self._snapshot(document_id), True
            if (
                latest is not None
                and latest.status is RunStatus.COMPLETED
                and latest.run_id == run_id
                and latest.source_id == source_id
            ):
                if existing is None:
                    raise ConsultantPersistenceError(
                        "completed run is missing its employee source"
                    )
                return snapshot, False
            if (
                existing is not None
                and existing.processing_status is SourceProcessingStatus.COMMITTED
            ):
                raise SourceConflict(
                    f"source {source_id} already belongs to an earlier run"
                )

            source = await self._load_or_prepare_source(requested)
            receipt = RunReceipt(
                run_id=run_id,
                status=RunStatus.SOURCE_SAVED,
                source_id=source_id,
                started_at=datetime.now(UTC),
            )
            await self._after_source_store(source)
            snapshot = await self._commit_source_reference(
                source=source,
                snapshot=snapshot,
                action="register_source",
                command_fields={
                    "run_receipt": receipt.model_dump(mode="json"),
                },
            )
            await self._touch_catalog(document_id)
            await self._after_source_checkpoint(source)
            await self._mark_source_committed(source)
            return snapshot, True

    async def mark_consultant_run_failed(
        self,
        *,
        document_id: UUID,
        run_id: UUID,
        error_code: str,
        execution_evidence: RunExecutionEvidence | None = None,
    ) -> ConsultantSnapshot:
        safe_error_code = error_code.strip()
        if not safe_error_code:
            raise ValueError("consultant failure requires a safe error code")
        async with self._lock_for(document_id):
            await self._require_active_catalog(document_id)
            snapshot = await self._snapshot(document_id)
            latest = (
                RunReceipt.model_validate(snapshot.latest_run)
                if snapshot.latest_run is not None
                else None
            )
            if latest is None or latest.run_id != run_id:
                raise ActiveConsultantRun("consultant failure targets another run")
            if latest.status in {RunStatus.FAILED, RunStatus.COMPLETED}:
                return snapshot
            receipt = RunReceipt(
                run_id=run_id,
                status=RunStatus.FAILED,
                source_id=latest.source_id,
                started_at=latest.started_at,
                completed_at=datetime.now(UTC),
                error_code=safe_error_code,
                execution_evidence=execution_evidence,
            )
            try:
                await self.graph.ainvoke(
                    {},
                    self.graph_config(document_id),
                    context={
                        "action": "mark_consultant_run_failed",
                        "document_id": str(document_id),
                        "expected_revision": snapshot.revision,
                        "run_receipt": receipt.model_dump(mode="json"),
                    },
                )
            except StaleThreadRevision as error:
                raise StaleRevision(str(error)) from error
            await self._touch_catalog(document_id)
            return await self._snapshot(document_id)

    async def stage_candidate_revision(
        self,
        *,
        document_id: UUID,
        request: CandidateStageRequest,
    ) -> CandidateEditReceipt:
        """Stage one verified candidate through the existing product graph."""

        async with self._lock_for(document_id):
            await self._require_active_catalog(document_id)
            raw_state = await self.raw_state(document_id)
            latest_payload = raw_state.get("latest_run")
            if latest_payload is None:
                raise ActiveConsultantRun(
                    "candidate staging requires an active consultant run"
                )
            latest = RunReceipt.model_validate(latest_payload)
            if (
                latest.run_id != request.run_id
                or latest.status is not RunStatus.SOURCE_SAVED
            ):
                raise ActiveConsultantRun(
                    "candidate staging does not match the active consultant run"
                )
            actual_revision = int(raw_state.get("revision", 0))
            if actual_revision != request.baseline_revision:
                raise CandidateRevisionConflict(
                    f"expected baseline revision {request.baseline_revision}, "
                    f"found {actual_revision}"
                )
            request_sha256 = candidate_request_sha256(request)
            active_payload = raw_state.get("active_candidate")
            active = (
                CandidateWorkspace.model_validate(active_payload)
                if active_payload is not None
                else None
            )
            if active is not None:
                replay = active.tool_receipts.get(request.tool_call_id)
                if replay is not None:
                    if replay.request_sha256 != request_sha256:
                        raise CandidateToolCallConflict(
                            f"candidate tool call {request.tool_call_id} was reused "
                            "with another payload"
                        )
                    return CandidateEditReceipt(
                        candidate_revision=replay.candidate_revision,
                        revision_digest=replay.revision_digest,
                        changeset_id=replay.changeset_id,
                        action_ids=replay.action_ids,
                        external_dependency_action_ids=(
                            replay.external_dependency_action_ids
                        ),
                    )
            current_candidate_revision = active.candidate_revision if active else 0
            if request.batch.base_candidate_revision != current_candidate_revision:
                raise CandidateRevisionConflict(
                    "expected candidate revision "
                    f"{current_candidate_revision}, found "
                    f"{request.batch.base_candidate_revision}"
                )
            next_candidate_revision = current_candidate_revision + 1
            dependency_action_ids = tuple(
                action_id
                for change in request.batch.replacement_changes
                for action_id in change.depends_on_action_ids
            )
            superseded_action_ids = tuple(
                action_id
                for change in request.batch.replacement_changes
                for action_id in change.supersedes_action_ids
            )
            allowed_entity_ids, allowed_action_ids = candidate_mapping_authority(
                raw_state,
                depends_on_action_ids=dependency_action_ids,
                supersedes_action_ids=superseded_action_ids,
            )
            materialization_run_id = uuid5(
                request.run_id,
                f"candidate-revision:{next_candidate_revision}",
            )
            changes = map_candidate_edit_batch(
                request.batch,
                document_id=document_id,
                materialization_run_id=materialization_run_id,
                allowed_entity_ids=allowed_entity_ids,
                allowed_action_ids=allowed_action_ids,
            )
            source_ids = tuple(
                sorted(
                    {
                        source_id
                        for change in changes
                        for source_id in change.basis.source_ids
                    },
                    key=str,
                )
            )
            sources = tuple(
                await asyncio.gather(
                    *(self.get_source(document_id, source_id) for source_id in source_ids)
                )
            )
            if any(
                source.processing_status is not SourceProcessingStatus.COMMITTED
                for source in sources
            ):
                raise PendingSourceRequiresReconciliation(
                    "candidate evidence includes an uncommitted employee source"
                )
            used_skill_ids = verify_candidate_document_changes(
                changes,
                document_id=document_id,
                selected_skill_ids=request.selected_skill_ids,
                loaded_skill_ids=request.loaded_skill_ids,
                employee_sources=sources,
            )
            stage = VerifiedCandidateStage(
                run_id=request.run_id,
                baseline_revision=request.baseline_revision,
                base_candidate_revision=request.batch.base_candidate_revision,
                tool_call_id=request.tool_call_id,
                request_sha256=request_sha256,
                summary=request.batch.summary,
                changes=changes,
                used_skill_ids=used_skill_ids,
            )
            _, receipt = materialize_candidate_workspace(raw_state, stage)
            await self.graph.ainvoke(
                {},
                self.graph_config(document_id),
                context={
                    "action": "stage_candidate_revision",
                    "document_id": str(document_id),
                    "candidate_stage": stage.model_dump(mode="json"),
                },
            )
            return receipt

    @staticmethod
    def _changed_employee_text(
        before: ApprovedJobDocument,
        after: ApprovedJobDocument,
    ) -> tuple[str, tuple[SourcePositionAnchor, ...]] | None:
        """Extract only employee-authored text, never IDs or control values."""

        def pointer_part(value: object) -> str:
            return str(value).replace("~", "~0").replace("/", "~1")

        def add_text(
            fields: list[tuple[str, str]], path: str, value: str | None
        ) -> None:
            if value is not None and value.strip():
                fields.append((path, value.strip()))

        def authored_fields(document: ApprovedJobDocument) -> list[tuple[str, str]]:
            fields: list[tuple[str, str]] = []
            for name in (
                "job_title",
                "occupation_category_name",
                "occupation_name",
                "occupation_code",
                "industry_name",
                "industry_code",
                "work_description",
                "notes",
            ):
                add_text(fields, f"/{name}", getattr(document, name))
            for duty in document.duties:
                duty_path = f"/duties/{pointer_part(duty.duty_id)}"
                add_text(fields, f"{duty_path}/statement", duty.statement)
            for task in document.tasks:
                task_path = f"/tasks/{pointer_part(task.task_id)}"
                for name in (
                    "statement",
                    "action",
                    "object",
                    "purpose_result",
                    "context",
                    "frequency_text",
                ):
                    add_text(fields, f"{task_path}/{name}", getattr(task, name))
                for index, enabler in enumerate(task.enablers):
                    add_text(
                        fields,
                        f"{task_path}/enablers/{index}/name",
                        enabler.name,
                    )
            for item in document.opks:
                add_text(
                    fields,
                    f"/opks/{pointer_part(item.item_id)}/text",
                    item.text,
                )
            return fields

        before_fields = dict(authored_fields(before))
        changes = [
            (path, value)
            for path, value in authored_fields(after)
            if before_fields.get(path) != value
        ]
        if not changes:
            return None
        chunks: list[str] = []
        spans: dict[str, tuple[int, int]] = {}
        positions: list[SourcePositionAnchor] = []
        cursor = 0
        for path, value in changes:
            if value not in spans:
                if chunks:
                    cursor += 1
                start = cursor
                chunks.append(value)
                cursor += len(value)
                spans[value] = (start, cursor)
            start, end = spans[value]
            positions.append(
                SourcePositionAnchor(
                    document_path=path,
                    start=start,
                    end=end,
                )
            )
        return "\n".join(chunks), tuple(positions)

    async def _require_known_evidence_sources(
        self,
        document: ApprovedJobDocument,
        *,
        pending_direct_edit_source_id: UUID | None,
    ) -> None:
        source_ids = tuple(
            sorted(
                {
                    source_id
                    for item in document.opks
                    for source_id in item.evidence_source_ids
                    if source_id != pending_direct_edit_source_id
                },
                key=str,
            )
        )
        if not source_ids:
            return
        sources = await asyncio.gather(
            *(self.get_source_or_none(document.document_id, item) for item in source_ids)
        )
        unknown = [
            source_id
            for source_id, source in zip(source_ids, sources)
            if source is None
        ]
        if unknown:
            raise UnknownEvidenceSource(
                "unknown employee evidence source "
                + ", ".join(str(source_id) for source_id in unknown)
            )

    async def apply_direct_edit(
        self,
        *,
        document_id: UUID,
        expected_revision: int,
        document: ApprovedJobDocument,
        source_id: UUID,
        command_receipt: CommandReceipt | None = None,
    ) -> ConsultantSnapshot:
        async with self._lock_for(document_id):
            await self._require_active_catalog(document_id)
            snapshot = await self._snapshot(document_id)
            raw_state = await self.raw_state(document_id)
            if self._inspect_command_receipt(raw_state, command_receipt) == "replay":
                await self._reconcile_replayed_command_source(
                    document_id,
                    source_id,
                )
                return snapshot
            document = ApprovedJobDocument.model_validate(
                document.model_dump(mode="json")
            )
            if document.document_id != document_id:
                raise ValueError("edited document does not match document_id")
            existing_source = await self.get_source_or_none(document_id, source_id)
            if snapshot.approved_document == document and command_receipt is None:
                if existing_source is not None:
                    if existing_source.kind is not EmployeeSourceKind.DIRECT_EDIT:
                        raise SourceConflict(
                            f"source {source_id} is not a direct-edit source"
                        )
                    if (
                        existing_source.processing_status
                        is SourceProcessingStatus.PENDING
                    ):
                        await self._touch_catalog(document_id)
                    await self._mark_source_committed(existing_source)
                return snapshot
            if snapshot.revision != expected_revision:
                raise StaleRevision(
                    f"expected revision {expected_revision}, found {snapshot.revision}"
                )
            if existing_source is not None and (
                existing_source.kind is not EmployeeSourceKind.DIRECT_EDIT
                or existing_source.processing_status
                is SourceProcessingStatus.COMMITTED
            ):
                raise SourceConflict(f"direct-edit source {source_id} was already used")
            changed = self._changed_employee_text(
                snapshot.approved_document, document
            )
            await self._require_known_evidence_sources(
                document,
                pending_direct_edit_source_id=(source_id if changed is not None else None),
            )
            source: EmployeeSource | None = None
            if changed is not None:
                changed_text, positions = changed
                requested = EmployeeSource.pending(
                    source_id=source_id,
                    document_id=document_id,
                    kind=EmployeeSourceKind.DIRECT_EDIT,
                    text=changed_text,
                    positions=positions,
                )
                source = await self._load_or_prepare_source(requested)
                if source.processing_status is SourceProcessingStatus.PENDING:
                    await self._after_source_store(source)

            command: dict[str, Any] = {
                "action": "direct_edit",
                "document_id": str(document_id),
                "expected_revision": expected_revision,
                "source_reference": None,
                "approved_document": document.model_dump(mode="json"),
            }
            if command_receipt is not None:
                command["command_receipt"] = command_receipt.model_dump(mode="json")
            if source is not None:
                command["source_reference"] = SourceReference(
                    source_id=source.source_id,
                    kind=source.kind,
                    created_at=source.created_at,
                ).model_dump(mode="json")
            try:
                await self.graph.ainvoke(
                    {}, self.graph_config(document_id), context=command
                )
            except StaleThreadRevision as error:
                raise StaleRevision(str(error)) from error
            result = await self._snapshot(document_id)
            await self._touch_catalog(document_id)
            if source is not None:
                await self._after_source_checkpoint(source)
                await self._mark_source_committed(source)
            return result

    @staticmethod
    def _review_replay_matches(
        bundle: DocumentChangeSet,
        *,
        action: str,
        action_ids: Sequence[UUID],
        edited_after_by_action_id: Mapping[UUID, JsonValue | None],
        rejection_reason: str | None,
    ) -> bool:
        selected = [
            item for item in bundle.actions if item.action_id in set(action_ids)
        ]
        if len(selected) != len(set(action_ids)):
            return False
        if action == "accept_changes":
            return all(
                item.status is DocumentChangeStatus.ACCEPTED for item in selected
            )
        if action == "edit_and_accept_changes":
            return all(
                item.status is DocumentChangeStatus.EDIT_ACCEPTED
                and item.employee_after
                == edited_after_by_action_id.get(item.action_id)
                for item in selected
            )
        if action == "reject_changes":
            reason = (rejection_reason or "").strip()
            return bool(reason) and all(
                item.status is DocumentChangeStatus.REJECTED
                and item.rejection_reason == reason
                for item in selected
            )
        if action == "defer_changes":
            return all(
                item.status is DocumentChangeStatus.DEFERRED for item in selected
            )
        return False

    async def decide_document_changes(
        self,
        *,
        document_id: UUID,
        expected_revision: int,
        action: Literal[
            "accept_changes",
            "edit_and_accept_changes",
            "reject_changes",
            "defer_changes",
        ],
        changeset_id: UUID,
        action_ids: Sequence[UUID],
        edited_after_by_action_id: Mapping[UUID, JsonValue | None] | None = None,
        rejection_reason: str | None = None,
        source_id: UUID | None = None,
        command_receipt: CommandReceipt | None = None,
    ) -> ConsultantSnapshot:
        """Apply one employee review decision without invoking a provider."""

        async with self._lock_for(document_id):
            await self._require_active_catalog(document_id)
            snapshot = await self._snapshot(document_id)
            raw_state = await self.raw_state(document_id)
            if self._inspect_command_receipt(raw_state, command_receipt) == "replay":
                await self._reconcile_replayed_command_source(
                    document_id,
                    source_id,
                )
                return snapshot
            raw_bundle = raw_state.get("review_queue", {}).get(str(changeset_id))
            if raw_bundle is None:
                raise KeyError(f"changeset {changeset_id} was not found")
            bundle = DocumentChangeSet.model_validate(raw_bundle)
            edited = dict(edited_after_by_action_id or {})
            if snapshot.revision != expected_revision:
                if self._review_replay_matches(
                    bundle,
                    action=action,
                    action_ids=action_ids,
                    edited_after_by_action_id=edited,
                    rejection_reason=rejection_reason,
                ) and command_receipt is None:
                    if source_id is not None:
                        source = await self.get_source_or_none(document_id, source_id)
                        if (
                            source is not None
                            and source.processing_status
                            is SourceProcessingStatus.PENDING
                        ):
                            await self._mark_source_committed(source)
                    return snapshot
                raise StaleRevision(
                    f"expected revision {expected_revision}, found {snapshot.revision}"
                )
            selected = tuple(
                item for item in bundle.actions if item.action_id in set(action_ids)
            )
            if len(selected) != len(set(action_ids)):
                raise ValueError("review decision references an unknown patch action")
            employee_payload = (
                edited_action_source_payload(selected, edited)
                if action == "edit_and_accept_changes"
                else None
            )
            source: EmployeeSource | None = None
            source_reference: SourceReference | None = None
            if employee_payload is not None:
                if source_id is None:
                    raise ValueError(
                        "employee text edit requires an application-issued source_id"
                    )
                text, positions = employee_payload
                requested = EmployeeSource.pending(
                    source_id=source_id,
                    document_id=document_id,
                    kind=EmployeeSourceKind.DIRECT_EDIT,
                    text=text,
                    positions=positions,
                )
                source = await self._load_or_prepare_source(requested)
                source_reference = SourceReference(
                    source_id=source.source_id,
                    kind=source.kind,
                    created_at=source.created_at,
                )

            preflight = apply_review_command(
                raw_state,
                action=action,
                changeset_id=changeset_id,
                action_ids=action_ids,
                revision=expected_revision + 1,
                edited_after_by_action_id=edited,
                rejection_reason=rejection_reason,
                source_reference=source_reference,
            )
            prospective_document = ApprovedJobDocument.model_validate(
                preflight["approved_document"]
            )
            await self._require_known_evidence_sources(
                prospective_document,
                pending_direct_edit_source_id=(
                    source.source_id if source is not None else None
                ),
            )
            if source is not None and source.processing_status is SourceProcessingStatus.PENDING:
                await self._after_source_store(source)

            command: dict[str, Any] = {
                "action": action,
                "document_id": str(document_id),
                "expected_revision": expected_revision,
                "changeset_id": str(changeset_id),
                "action_ids": [str(item) for item in action_ids],
                "edited_after_by_action_id": {
                    str(key): value for key, value in edited.items()
                },
            }
            if rejection_reason is not None:
                command["rejection_reason"] = rejection_reason
            if source_reference is not None:
                command["source_reference"] = source_reference.model_dump(mode="json")
            if command_receipt is not None:
                command["command_receipt"] = command_receipt.model_dump(mode="json")
            try:
                await self.graph.ainvoke(
                    {}, self.graph_config(document_id), context=command
                )
            except StaleThreadRevision as error:
                raise StaleRevision(str(error)) from error
            result = await self._snapshot(document_id)
            await self._touch_catalog(document_id)
            if source is not None:
                await self._after_source_checkpoint(source)
                await self._mark_source_committed(source)
            return result

    async def answer_required_clarification(
        self,
        *,
        document_id: UUID,
        expected_revision: int,
        clarification_id: UUID,
        choice: str,
        text: str,
        source_id: UUID,
        command_receipt: CommandReceipt | None = None,
    ) -> ConsultantSnapshot:
        """Resume a durable interrupt with employee evidence, never document authority."""

        async with self._lock_for(document_id):
            await self._require_active_catalog(document_id)
            snapshot = await self._snapshot(document_id)
            raw_state = await self.raw_state(document_id)
            if self._inspect_command_receipt(raw_state, command_receipt) == "replay":
                await self._reconcile_replayed_command_source(
                    document_id,
                    source_id,
                )
                return snapshot
            existing_source = await self.get_source_or_none(document_id, source_id)
            if snapshot.required_clarification is None:
                if snapshot.latest_source_id == source_id and existing_source is not None:
                    if (
                        existing_source.processing_status
                        is SourceProcessingStatus.PENDING
                    ):
                        await self._mark_source_committed(existing_source)
                    return snapshot
                raise ValueError("no required clarification is waiting")
            request = RequiredClarification.model_validate(
                snapshot.required_clarification
            )
            if request.clarification_id != clarification_id:
                raise ValueError("clarification answer targets a different request")
            if snapshot.revision != expected_revision:
                raise StaleRevision(
                    f"expected revision {expected_revision}, found {snapshot.revision}"
                )
            normalized_text = text if text.strip() else choice
            requested = EmployeeSource.pending(
                source_id=source_id,
                document_id=document_id,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text=normalized_text,
                positions=(
                    SourcePositionAnchor(
                        document_path=f"/clarifications/{clarification_id}/answer",
                        start=0,
                        end=len(normalized_text),
                    ),
                ),
            )
            source = await self._load_or_prepare_source(requested)
            if source.processing_status is SourceProcessingStatus.PENDING:
                await self._after_source_store(source)
            answer = ClarificationAnswer(
                choice=choice,
                text=normalized_text,
                source_reference=SourceReference(
                    source_id=source.source_id,
                    kind=source.kind,
                    created_at=source.created_at,
                ),
                command_receipt=command_receipt,
            )
            await self.graph.ainvoke(
                Command(resume=answer.model_dump(mode="json")),
                self.graph_config(document_id),
            )
            result = await self._snapshot(document_id)
            await self._touch_catalog(document_id)
            await self._after_source_checkpoint(source)
            await self._mark_source_committed(source)
            return result

    async def decide_understanding_calibration(
        self,
        *,
        document_id: UUID,
        expected_revision: int,
        calibration_id: UUID,
        decision: Literal["confirm", "later"],
        employee_text: str | None = None,
        source_id: UUID | None = None,
        command_receipt: CommandReceipt | None = None,
    ) -> ConsultantSnapshot:
        """Apply an employee calibration action without invoking a model."""

        async with self._lock_for(document_id):
            await self._require_active_catalog(document_id)
            snapshot = await self._snapshot(document_id)
            raw_state = await self.raw_state(document_id)
            if self._inspect_command_receipt(raw_state, command_receipt) == "replay":
                await self._reconcile_replayed_command_source(
                    document_id,
                    source_id,
                )
                return snapshot
            raw_calibration = raw_state.get(
                "understanding_calibrations", {}
            ).get(str(calibration_id))
            if raw_calibration is None:
                raise KeyError(
                    f"understanding calibration {calibration_id} was not found"
                )
            calibration = UnderstandingCalibration.model_validate(raw_calibration)
            expected_status = (
                CalibrationStatus.CONFIRMED
                if decision == "confirm"
                else CalibrationStatus.LATER
            )
            if calibration.status is expected_status and command_receipt is None:
                if source_id is not None:
                    source = await self.get_source_or_none(document_id, source_id)
                    if source is None:
                        raise SourceConflict(
                            "calibration replay is missing its employee source"
                        )
                    if source.processing_status is SourceProcessingStatus.PENDING:
                        await self._mark_source_committed(source)
                return snapshot
            if snapshot.revision != expected_revision:
                raise StaleRevision(
                    f"expected revision {expected_revision}, found {snapshot.revision}"
                )

            source: EmployeeSource | None = None
            source_reference: SourceReference | None = None
            if decision == "confirm":
                normalized_text = (employee_text or "").strip()
                if not normalized_text or source_id is None:
                    raise ValueError(
                        "confirming understanding requires employee text and source_id"
                    )
                requested = EmployeeSource.pending(
                    source_id=source_id,
                    document_id=document_id,
                    kind=EmployeeSourceKind.EMPLOYEE_TURN,
                    text=normalized_text,
                    positions=(
                        SourcePositionAnchor(
                            document_path=(
                                f"/understanding_calibrations/{calibration_id}/decision"
                            ),
                            start=0,
                            end=len(normalized_text),
                        ),
                    ),
                )
                source = await self._load_or_prepare_source(requested)
                source_reference = SourceReference(
                    source_id=source.source_id,
                    kind=source.kind,
                    created_at=source.created_at,
                )
                if source.processing_status is SourceProcessingStatus.PENDING:
                    await self._after_source_store(source)
            elif employee_text is not None or source_id is not None:
                raise ValueError(
                    "deferring understanding must not create employee evidence"
                )

            command: dict[str, Any] = {
                "action": "decide_understanding_calibration",
                "document_id": str(document_id),
                "expected_revision": expected_revision,
                "calibration_id": str(calibration_id),
                "calibration_decision": CalibrationDecision(decision).value,
                "source_reference": (
                    source_reference.model_dump(mode="json")
                    if source_reference is not None
                    else None
                ),
            }
            if command_receipt is not None:
                command["command_receipt"] = command_receipt.model_dump(mode="json")
            try:
                await self.graph.ainvoke(
                    {},
                    self.graph_config(document_id),
                    context=command,
                )
            except StaleThreadRevision as error:
                raise StaleRevision(str(error)) from error
            result = await self._snapshot(document_id)
            await self._touch_catalog(document_id)
            if source is not None:
                await self._after_source_checkpoint(source)
                await self._mark_source_committed(source)
            return result

    async def export_approved_document(
        self, document_id: UUID
    ) -> ApprovedJobDocument:
        return (await self.reopen_document(document_id)).approved_document

    async def commit_verified_consultant_result(
        self,
        *,
        document_id: UUID,
        expected_revision: int,
        commit: VerifiedConsultantCommit,
    ) -> ConsultantSnapshot:
        """Atomically publish one already-verified semantic consultant result."""

        async with self._lock_for(document_id):
            await self._require_active_catalog(document_id)
            source = await self.get_source(document_id, commit.answer_source_id)
            if source.processing_status is not SourceProcessingStatus.COMMITTED:
                raise PendingSourceRequiresReconciliation(
                    f"source {source.source_id} is not committed"
                )
            if source.validity is not SourceValidity.CURRENT:
                raise SourceConflict(
                    f"source {source.source_id} was superseded before semantic commit"
                )
            snapshot = await self._snapshot(document_id)
            if snapshot.revision != expected_revision:
                raise StaleRevision(
                    f"expected revision {expected_revision}, found {snapshot.revision}"
                )
            try:
                await self.graph.ainvoke(
                    {},
                    self.graph_config(document_id),
                    context={
                        "action": "commit_consultant_result",
                        "document_id": str(document_id),
                        "expected_revision": expected_revision,
                        "semantic_commit": commit.model_dump(mode="json"),
                    },
                )
            except StaleThreadRevision as error:
                raise StaleRevision(str(error)) from error
            await self._touch_catalog(document_id)
            return await self._snapshot(document_id)

    async def resolve_quote(
        self,
        document_id: UUID,
        source_id: UUID,
        *,
        start: int,
        end: int,
        expected_quote: str,
    ) -> QuoteAnchor:
        source = await self.get_source(document_id, source_id)
        if start < 0 or end <= start or source.text[start:end] != expected_quote:
            raise QuoteAnchorMismatch(
                f"quote does not match source {source_id} at [{start}:{end}]"
            )
        return QuoteAnchor(
            source_id=source_id,
            start=start,
            end=end,
            quote=expected_quote,
        )

    async def delete_document(self, document_id: UUID) -> None:
        async with self._lock_for(document_id):
            async with self._catalog_connection.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE consultant_documents
                    SET deleted_at = COALESCE(deleted_at, now()),
                        updated_at = now()
                    WHERE document_id = %s
                    """,
                    (document_id,),
                )
            await self.saver.adelete_thread(str(document_id))
            namespace = self.source_namespace(document_id)
            while items := await self.store.asearch(namespace, limit=100):
                await asyncio.gather(
                    *(self.store.adelete(namespace, item.key) for item in items)
                )
        self._document_locks.pop(document_id, None)


async def _cancel_store_batcher(store: AsyncPostgresStore) -> None:
    """The framework Store has no public batch-worker close method in 3.1.2."""
    task = store._task  # noqa: SLF001
    if task is not None:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@asynccontextmanager
async def open_postgres_consultant_runtime(
    database_url: str,
) -> AsyncIterator[PostgresConsultantRuntime]:
    connection_string = psycopg_connection_string(database_url)
    strict_serializer = JsonPlusSerializer(
        pickle_fallback=False,
        allowed_msgpack_modules=None,
    )
    async with AsyncPostgresSaver.from_conn_string(
        connection_string,
        serde=strict_serializer,
    ) as saver:
        async with AsyncPostgresStore.from_conn_string(connection_string) as store:
            async with await psycopg.AsyncConnection.connect(
                connection_string,
                autocommit=True,
                prepare_threshold=0,
                row_factory=dict_row,
            ) as catalog_connection:
                runtime = PostgresConsultantRuntime(
                    saver=saver,
                    store=store,
                    catalog_connection=catalog_connection,
                    strict_serializer=strict_serializer,
                )
                await runtime.setup()
                try:
                    yield runtime
                finally:
                    await _cancel_store_batcher(store)
