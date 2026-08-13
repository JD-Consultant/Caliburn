"""PostgreSQL Saver/Store ownership for one durable consultant document.

This adapter intentionally exposes product commands over LangGraph's public
Saver/Store APIs.  It does not mirror semantic state into application tables:
the only Caliburn-owned table is a minimal document catalog/tombstone.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import psycopg
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.store.base import PutOp
from langgraph.store.postgres.aio import AsyncPostgresStore
from psycopg import AsyncConnection
from psycopg.rows import DictRow, dict_row

from app.consultant.graph import StaleThreadRevision, build_consultant_graph
from app.consultant.interview import VerifiedConsultantCommit
from app.consultant.state import (
    ApprovedJobDocument,
    EmployeeSource,
    EmployeeSourceKind,
    QuoteAnchor,
    SourceProcessingStatus,
    SourcePositionAnchor,
    SourceReference,
    SourceValidity,
)
from app.consultant.views import ConsultantSnapshot, snapshot_from_state


SourceHook = Callable[[EmployeeSource], Awaitable[None]]


class ConsultantPersistenceError(RuntimeError):
    pass


class DocumentNotFound(ConsultantPersistenceError):
    pass


class SourceConflict(ConsultantPersistenceError):
    pass


class PendingSourceRequiresReconciliation(ConsultantPersistenceError):
    pass


class StaleRevision(ConsultantPersistenceError):
    pass


class QuoteAnchorMismatch(ConsultantPersistenceError):
    pass


class UnknownEvidenceSource(ConsultantPersistenceError):
    pass


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
            await self._require_active_catalog(document_id)
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
    ) -> ConsultantSnapshot:
        if snapshot.latest_source_id == source.source_id:
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
    ) -> ConsultantSnapshot:
        async with self._lock_for(document_id):
            await self._require_active_catalog(document_id)
            snapshot = await self._snapshot(document_id)
            document = ApprovedJobDocument.model_validate(
                document.model_dump(mode="json")
            )
            if document.document_id != document_id:
                raise ValueError("edited document does not match document_id")
            existing_source = await self.get_source_or_none(document_id, source_id)
            if snapshot.approved_document == document:
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
