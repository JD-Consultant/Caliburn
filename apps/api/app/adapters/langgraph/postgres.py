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
from hashlib import sha256
import json
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
from app.consultant.current_document_edit import plan_current_document_edit
from app.consultant.document_authority import DocumentAuthorityError, edited_action_source_payload
from app.consultant.interview import VerifiedConsultantCommit
from app.consultant.understanding import semantic_progress_from_workspace
from app.consultant.state import (
    ApprovedJobDocument,
    CalibrationDecision,
    CalibrationStatus,
    CommandReceipt,
    CommandReceiptConflict,
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
from app.consultant.workspace_resources import WorkspaceCatalog
from app.consultant.workspace_authority import (
    WorkspaceAuthorityService,
    WorkspaceReviewCommand,
)
from app.consultant.workspace_review import (
    WorkspaceReviewDecision,
    derive_workspace_review,
)
from app.consultant.workspace_state import (
    StoreBackedWorkspace,
    WorkspaceValidationStatus,
    approved_document_digest,
)
from app.consultant.workspace_validation import (
    active_conflict_diagnostics,
    evidence_basis_digest,
    validate_workspace_payload,
)
from app.consultant.workspace_state import (
    workspace_decision_namespace as _workspace_decision_namespace,
    workspace_metadata_namespace as _workspace_metadata_namespace,
    workspace_namespace as _workspace_namespace,
)
from app.consultant.views import (
    ConsultantSnapshot,
    document_review_projection_from_workspace,
    snapshot_from_state,
)
from app.consultant.skill_backend import CONSULTANT_SKILL_IDS


SourceHook = Callable[[EmployeeSource], Awaitable[None]]
WorkspaceHook = Callable[[], Awaitable[None]]


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


class ConsultantRunAlreadyActive(ConsultantPersistenceError):
    """One process-local model run currently owns this document."""


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
        self._active_model_runs: set[UUID] = set()
        self._active_employee_mutations: dict[UUID, int] = {}
        self._after_source_store: SourceHook = self._noop_source_hook
        self._after_source_checkpoint: SourceHook = self._noop_source_hook
        self._after_workspace_authority_checkpoint: WorkspaceHook = (
            self._noop_workspace_hook
        )
        self._after_workspace_decision_record: WorkspaceHook = (
            self._noop_workspace_hook
        )

    @staticmethod
    async def _noop_source_hook(_source: EmployeeSource) -> None:
        return None

    @staticmethod
    async def _noop_workspace_hook() -> None:
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

    @staticmethod
    def workspace_namespace(document_id: UUID) -> tuple[str, str, str, str]:
        return _workspace_namespace(document_id)

    @staticmethod
    def workspace_metadata_namespace(
        document_id: UUID,
    ) -> tuple[str, str, str, str]:
        return _workspace_metadata_namespace(document_id)

    @staticmethod
    def workspace_decision_namespace(
        document_id: UUID,
    ) -> tuple[str, str, str, str]:
        return _workspace_decision_namespace(document_id)

    async def workspace_review_decisions(
        self,
        document_id: UUID,
    ) -> tuple[WorkspaceReviewDecision, ...]:
        return await WorkspaceAuthorityService(self).review_decisions(document_id)

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

    @asynccontextmanager
    async def active_consultant_run(self, document_id: UUID) -> AsyncIterator[None]:
        """Own one document's model mutation admission in this local process."""

        async with self._lock_for(document_id):
            if (
                document_id in self._active_model_runs
                or self._active_employee_mutations.get(document_id, 0) > 0
            ):
                raise ConsultantRunAlreadyActive(
                    f"document mutation already active for {document_id}"
                )
            self._active_model_runs.add(document_id)
        try:
            yield
        finally:
            async with self._lock_for(document_id):
                self._active_model_runs.discard(document_id)

    @asynccontextmanager
    async def employee_mutation_admission(
        self,
        document_id: UUID,
    ) -> AsyncIterator[None]:
        """Reserve one route's preflight and authority mutation against the model."""

        async with self._lock_for(document_id):
            self._require_employee_mutation_admitted(document_id)
            self._active_employee_mutations[document_id] = (
                self._active_employee_mutations.get(document_id, 0) + 1
            )
        try:
            yield
        finally:
            async with self._lock_for(document_id):
                remaining = self._active_employee_mutations.get(document_id, 1) - 1
                if remaining > 0:
                    self._active_employee_mutations[document_id] = remaining
                else:
                    self._active_employee_mutations.pop(document_id, None)

    def _require_employee_mutation_admitted(self, document_id: UUID) -> None:
        if document_id in self._active_model_runs:
            raise ConsultantRunAlreadyActive(
                f"document {document_id} is busy with a consultant model run"
            )

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
        async with self._lock_for(document_id):
            await self._require_active_catalog(document_id)
            await WorkspaceAuthorityService(self).recover(document_id)
            return await self._snapshot(document_id)

    async def workspace_review_context(self, document_id: UUID) -> Any:
        """Load the current workspace review context for the HTTP command seam."""

        return await WorkspaceAuthorityService(self)._review_context(document_id)

    async def _snapshot(self, document_id: UUID) -> ConsultantSnapshot:
        state = await self.graph.aget_state(self.graph_config(document_id))
        if not state.values:
            raise DocumentNotFound(
                f"consultant checkpoint for {document_id} was not found"
            )
        snapshot = snapshot_from_state(state.values)
        workspace = StoreBackedWorkspace(
            store=self.store,
            document_id=document_id,
        )
        await workspace.ensure_initialized(
            approved_document=snapshot.approved_document,
            approved_revision=snapshot.revision,
        )
        workspace_snapshot = await workspace.read_snapshot()
        sources = await self.list_sources(document_id)
        catalog = WorkspaceCatalog.from_snapshot(
            snapshot.approved_document,
            sources=sources,
            handle_registry=workspace_snapshot.manifest.entity_ids_by_handle,
        )
        validation = validate_workspace_payload(
            workspace_snapshot.files,
            catalog=catalog,
            selected_skill_ids=CONSULTANT_SKILL_IDS,
            loaded_skill_ids=CONSULTANT_SKILL_IDS,
        )
        manifest = workspace_snapshot.manifest
        effective_manifest = manifest
        if manifest.validation_status in {
            WorkspaceValidationStatus.VALID,
            WorkspaceValidationStatus.CONFLICTED,
        } and validation.document is not None:
            conflicts = active_conflict_diagnostics(
                files=workspace_snapshot.files,
                approved_document=snapshot.approved_document,
                manifest=manifest,
            )
            effective_manifest = manifest.model_copy(
                update={
                    "validation_status": (
                        WorkspaceValidationStatus.CONFLICTED
                        if validation.diagnostics or conflicts
                        else WorkspaceValidationStatus.VALID
                    ),
                    "diagnostics": tuple(
                        dict.fromkeys((*validation.diagnostics, *conflicts))
                    ),
                }
            )
        decisions = await self.workspace_review_decisions(document_id)
        projection = derive_workspace_review(
            snapshot.approved_document,
            validation,
            effective_manifest,
            decisions,
        )
        # Invalid canonical workspace JSON cannot produce a safe current document;
        # keep the approved checkpoint baseline visible while review carries diagnostics.
        current_document = (
            validation.document.approved_document
            if validation.document is not None
            else snapshot.approved_document
        )
        updates: dict[str, Any] = {
            "current_document": current_document,
            "document_review": document_review_projection_from_workspace(
                state.values,
                workspace_generation=workspace_snapshot.manifest.generation,
                validation_status=effective_manifest.validation_status,
                workspace_review=projection,
            )
        }
        if validation.document is not None:
            updates["semantic_progress"] = semantic_progress_from_workspace(
                state.values,
                working_document=validation.document.approved_document,
                workspace_review=projection,
            )
        return snapshot.model_copy(
            update=updates
        )

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

    async def _require_current_committed_sources(
        self,
        document_id: UUID,
        source_ids: Iterable[UUID],
    ) -> tuple[EmployeeSource, ...]:
        ordered_ids = tuple(source_ids)
        loaded = await asyncio.gather(
            *(self.get_source_or_none(document_id, source_id) for source_id in ordered_ids)
        )
        unknown = [
            source_id
            for source_id, source in zip(ordered_ids, loaded)
            if source is None or source.document_id != document_id
        ]
        if unknown:
            raise UnknownEvidenceSource(
                "unknown employee evidence source "
                + ", ".join(str(source_id) for source_id in unknown)
            )
        sources = tuple(source for source in loaded if source is not None)
        if any(
            source.processing_status is not SourceProcessingStatus.COMMITTED
            for source in sources
        ):
            raise PendingSourceRequiresReconciliation(
                "workspace Evidence includes an uncommitted employee source"
            )
        superseded = next(
            (
                source
                for source in sources
                if source.validity is not SourceValidity.CURRENT
            ),
            None,
        )
        if superseded is not None:
            raise SourceConflict(
                f"source {superseded.source_id} was superseded before workspace staging"
            )
        return sources

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

    async def _reconcile_source_supersession(
        self,
        *,
        document_id: UUID,
        current_source_id: UUID,
        superseded_source_id: UUID,
    ) -> None:
        """Persist one exact old/current source pair before the checkpoint."""

        if current_source_id == superseded_source_id:
            raise SourceConflict("source supersession cannot target itself")
        current = await self.get_source(document_id, current_source_id)
        superseded = await self.get_source(document_id, superseded_source_id)
        stored_target = await self._stored_supersession_target_for_current(
            document_id=document_id,
            current_source=current,
        )
        if current.document_id != document_id or superseded.document_id != document_id:
            raise SourceConflict("source supersession crosses document scope")
        if current.processing_status is not SourceProcessingStatus.COMMITTED:
            raise PendingSourceRequiresReconciliation(
                f"source {current.source_id} is not committed"
            )
        if superseded.processing_status is not SourceProcessingStatus.COMMITTED:
            raise PendingSourceRequiresReconciliation(
                f"source {superseded.source_id} is not committed"
            )
        if current.validity is not SourceValidity.CURRENT:
            raise SourceConflict(
                f"source {current.source_id} was superseded before semantic commit"
            )
        if stored_target is not None and stored_target != superseded_source_id:
            raise SourceConflict(
                "source supersession relation is partial or belongs to another source"
            )
        if (
            current.supersedes_source_id == superseded_source_id
            and superseded.validity is SourceValidity.SUPERSEDED
            and superseded.superseded_by_source_id == current_source_id
        ):
            return
        if (
            current.supersedes_source_id is not None
            or superseded.superseded_by_source_id is not None
            or superseded.validity is not SourceValidity.CURRENT
        ):
            raise SourceConflict(
                "source supersession relation is partial or belongs to another source"
            )
        updated_superseded = superseded.model_copy(
            update={
                "validity": SourceValidity.SUPERSEDED,
                "superseded_by_source_id": current_source_id,
            }
        )
        updated_current = current.model_copy(
            update={"supersedes_source_id": superseded_source_id}
        )
        await self._put_sources_atomically((updated_superseded, updated_current))
        await self._after_source_store(updated_current)

    async def _stored_supersession_target_for_current(
        self,
        *,
        document_id: UUID,
        current_source: EmployeeSource,
    ) -> UUID | None:
        incoming = tuple(
            source
            for source in await self.list_sources(document_id)
            if source.superseded_by_source_id == current_source.source_id
        )
        if current_source.supersedes_source_id is None:
            if incoming:
                raise SourceConflict(
                    "source supersession relation is partial or belongs to another source"
                )
            return None
        if len(incoming) != 1 or incoming[0].source_id != current_source.supersedes_source_id:
            raise SourceConflict(
                "source supersession relation is partial or belongs to another source"
            )
        return current_source.supersedes_source_id

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
            same_requested_source = existing is not None and self._same_immutable_source(
                existing, requested
            )
            relation_was_reconciled = (
                existing is not None
                and requested.supersedes_source_id is None
                and existing.supersedes_source_id is not None
                and self._same_immutable_source(
                    existing,
                    requested.model_copy(
                        update={
                            "supersedes_source_id": existing.supersedes_source_id
                        }
                    ),
                )
            )
            if existing is not None and not (
                same_requested_source or relation_was_reconciled
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
            if latest is not None and latest.status is RunStatus.SOURCE_SAVED:
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
                return snapshot, False
            if latest is not None and latest.status is RunStatus.FAILED:
                same_run = latest.run_id == run_id
                same_source = latest.source_id == source_id
                if same_run != same_source:
                    raise IdempotencyConflict(
                        "failed consultant run identity conflicts"
                    )
            if (
                latest is not None
                and latest.status is RunStatus.FAILED
                and latest.run_id == run_id
                and latest.source_id == source_id
            ):
                if existing is None:
                    raise ConsultantPersistenceError(
                        "recoverable run is missing its employee source"
                    )
                pending = await self._pending_sources(document_id)
                if pending:
                    raise PendingSourceRequiresReconciliation(
                        f"source {pending[0].source_id} must be reconciled before "
                        "restarting the failed run"
                    )
                if existing.processing_status is not SourceProcessingStatus.COMMITTED:
                    raise PendingSourceRequiresReconciliation(
                        f"source {existing.source_id} is not committed"
                    )
                if existing.validity is not SourceValidity.CURRENT:
                    raise SourceConflict(
                        f"source {existing.source_id} was superseded before restart"
                    )
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

    @staticmethod
    def _changed_employee_text(
        before: ApprovedJobDocument,
        after: ApprovedJobDocument,
        *,
        allowed_paths: Sequence[str] | None = None,
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
        allowed = frozenset(allowed_paths) if allowed_paths is not None else None
        changes = [
            (path, value)
            for path, value in authored_fields(after)
            if before_fields.get(path) != value
            and (allowed is None or path in allowed)
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

    @staticmethod
    def _attach_direct_edit_evidence(
        document: ApprovedJobDocument,
        *,
        employee_text_paths: Sequence[str],
        source_id: UUID,
    ) -> ApprovedJobDocument:
        opk_paths = {
            f"/opks/{item.item_id}/text"
            for item in document.opks
            if f"/opks/{item.item_id}/text" in employee_text_paths
        }
        if not opk_paths:
            return document
        opks = tuple(
            item.model_copy(
                update={
                    "evidence_source_ids": tuple(
                        dict.fromkeys((*item.evidence_source_ids, source_id))
                    )
                }
            )
            if f"/opks/{item.item_id}/text" in opk_paths
            else item
            for item in document.opks
        )
        return document.model_copy(update={"opks": opks})

    async def apply_current_document_edit(
        self,
        *,
        document_id: UUID,
        expected_revision: int,
        workspace_generation: int,
        workspace_digest: str,
        document: ApprovedJobDocument,
        source_id: UUID,
        command_receipt: CommandReceipt | None = None,
    ) -> ConsultantSnapshot:
        """Commit the employee delta from the shared current JD surface.

        The workspace planner is the only source of employee override paths and
        employee text paths.  This keeps a full current Store catalog in the
        planner while the existing authority seam remains responsible for the
        approved checkpoint and replayable Store rebase.
        """

        async with self._lock_for(document_id):
            self._require_employee_mutation_admitted(document_id)
            await self._require_active_catalog(document_id)
            raw_state = await self.raw_state(document_id)
            if self._inspect_command_receipt(raw_state, command_receipt) == "replay":
                await WorkspaceAuthorityService(self).recover(document_id)
                await self._reconcile_replayed_command_source(
                    document_id,
                    source_id,
                )
                return await self._snapshot(document_id)

            snapshot, _workspace, workspace_snapshot, review = await (
                WorkspaceAuthorityService(self)._review_context(document_id)
            )
            if snapshot.revision != expected_revision:
                raise StaleRevision(
                    f"expected revision {expected_revision}, found {snapshot.revision}"
                )
            if workspace_snapshot.manifest.generation != workspace_generation:
                raise StaleRevision("workspace generation changed")
            if workspace_snapshot.manifest.resource_digest != workspace_digest:
                raise StaleRevision("workspace digest changed")
            current = snapshot.current_document
            if current is None:
                raise ConsultantPersistenceError(
                    "current document projection is unavailable"
                )
            document = ApprovedJobDocument.model_validate(
                document.model_dump(mode="json")
            )
            if document.document_id != document_id:
                raise ValueError("edited document does not match document_id")

            sources = await self.list_sources(document_id)
            potential_changed = self._changed_employee_text(current, document)
            catalog_sources = sources
            if potential_changed is not None and not any(
                item.source_id == source_id for item in sources
            ):
                changed_text, positions = potential_changed
                catalog_sources = (
                    *sources,
                    EmployeeSource.pending(
                        source_id=source_id,
                        document_id=document_id,
                        kind=EmployeeSourceKind.DIRECT_EDIT,
                        text=changed_text,
                        positions=positions,
                    ),
                )
            catalog = WorkspaceCatalog.from_snapshot(
                current,
                sources=catalog_sources,
                handle_registry=workspace_snapshot.manifest.entity_ids_by_handle,
            )
            plan = plan_current_document_edit(
                approved=snapshot.approved_document,
                current=current,
                submitted=document,
                workspace_files=workspace_snapshot.files,
                handle_registry=catalog.handle_to_stable,
                review=review,
                employee_source_id=(source_id if potential_changed is not None else None),
            )
            changed = self._changed_employee_text(
                current,
                document,
                allowed_paths=plan.employee_text_paths,
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

            approved_after = self._attach_direct_edit_evidence(
                plan.approved_after,
                employee_text_paths=plan.employee_text_paths,
                source_id=source_id,
            )
            workspace_authority = WorkspaceAuthorityService(self)
            direct_rebase_command_id = (
                command_receipt.command_id
                if command_receipt is not None
                else source_id
            )
            await workspace_authority.prepare_direct_edit_rebase(
                document_id=document_id,
                command_id=direct_rebase_command_id,
                source_id=source_id,
                old_approved=snapshot.approved_document,
                new_approved=approved_after,
                approved_revision=snapshot.revision + 1,
                employee_override_paths=plan.employee_override_paths,
                employee_evidence_files=plan.employee_evidence_files,
            )
            command: dict[str, Any] = {
                "action": "direct_edit",
                "document_id": str(document_id),
                "expected_revision": snapshot.revision,
                "source_reference": None,
                "approved_document": approved_after.model_dump(mode="json"),
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
                    {},
                    self.graph_config(document_id),
                    context=command,
                )
            except StaleThreadRevision as error:
                raise StaleRevision(str(error)) from error
            await self._after_workspace_authority_checkpoint()
            await self._touch_catalog(document_id)
            if source is not None:
                await self._after_source_checkpoint(source)
                await self._mark_source_committed(source)
            await workspace_authority.finish_direct_edit_rebase(
                document_id,
                direct_rebase_command_id,
            )
            return await self._snapshot(document_id)

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
            self._require_employee_mutation_admitted(document_id)
            await self._require_active_catalog(document_id)
            snapshot = await self._snapshot(document_id)
            raw_state = await self.raw_state(document_id)
            if self._inspect_command_receipt(raw_state, command_receipt) == "replay":
                await WorkspaceAuthorityService(self).recover(document_id)
                await self._reconcile_replayed_command_source(
                    document_id,
                    source_id,
                )
                return await self._snapshot(document_id)
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
            workspace_authority = WorkspaceAuthorityService(self)
            direct_rebase_command_id = (
                command_receipt.command_id if command_receipt is not None else source_id
            )
            await workspace_authority.prepare_direct_edit_rebase(
                document_id=document_id,
                command_id=direct_rebase_command_id,
                source_id=source_id,
                old_approved=snapshot.approved_document,
                new_approved=document,
                approved_revision=expected_revision + 1,
            )
            try:
                await self.graph.ainvoke(
                    {}, self.graph_config(document_id), context=command
                )
            except StaleThreadRevision as error:
                raise StaleRevision(str(error)) from error
            await self._touch_catalog(document_id)
            if source is not None:
                await self._after_source_checkpoint(source)
                await self._mark_source_committed(source)
            await workspace_authority.finish_direct_edit_rebase(
                document_id,
                direct_rebase_command_id,
            )
            return await self._snapshot(document_id)


    async def decide_workspace_changes(
        self,
        command: WorkspaceReviewCommand,
    ) -> ConsultantSnapshot:
        """Apply one employee decision to the persistent workspace authority seam."""

        async with self._lock_for(command.document_id):
            self._require_employee_mutation_admitted(command.document_id)
            await self._require_active_catalog(command.document_id)
            return await WorkspaceAuthorityService(self).decide(command)

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
        """Atomically commit one already-verified semantic consultant result."""

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
            latest = (
                RunReceipt.model_validate(snapshot.latest_run)
                if snapshot.latest_run is not None
                else None
            )
            if (
                latest is not None
                and latest.status is RunStatus.COMPLETED
                and latest.run_id == commit.run_id
                and latest.source_id == commit.answer_source_id
            ):
                if (
                    latest.semantic_commit_sha256
                    != commit.semantic_payload_sha256()
                ):
                    raise IdempotencyConflict(
                        "completed consultant run semantic payload conflicts"
                    )
                return snapshot
            if snapshot.revision != expected_revision:
                raise StaleRevision(
                    f"expected revision {expected_revision}, found {snapshot.revision}"
                )
            stored_target = await self._stored_supersession_target_for_current(
                document_id=document_id,
                current_source=source,
            )
            requested_target = (
                commit.result.source_supersession.superseded_source_id
                if commit.result.source_supersession is not None
                else None
            )
            if stored_target != requested_target:
                if stored_target is not None and requested_target is None:
                    registered_target = snapshot.source_supersessions.get(
                        str(stored_target)
                    )
                    if registered_target == str(commit.answer_source_id):
                        requested_target = stored_target
                    else:
                        raise SourceConflict(
                            "stored source supersession requires an exact semantic replay"
                        )
                elif stored_target is not None:
                    raise SourceConflict(
                        "source supersession relation is partial or belongs to another source"
                    )
            if requested_target is not None:
                await self._reconcile_source_supersession(
                    document_id=document_id,
                    current_source_id=commit.answer_source_id,
                    superseded_source_id=requested_target,
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
            namespaces = (
                self.source_namespace(document_id),
                self.workspace_namespace(document_id),
                self.workspace_metadata_namespace(document_id),
                self.workspace_decision_namespace(document_id),
            )
            for namespace in namespaces:
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
