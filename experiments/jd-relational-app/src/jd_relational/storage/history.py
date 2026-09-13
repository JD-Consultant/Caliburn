"""Fixed, read-only historical JD material; no tokens, sources or writer authority.

Every public read materializes its result in one short READ ONLY REPEATABLE READ
transaction. Historical identity never falls back to the latest current head.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

import sqlalchemy as sa

from jd_relational.snapshots import (
    ENGINE_PROFILE, FORMAT_VERSION, domain_from_snapshot, snapshot_digest, snapshot_from_domain,
)
from . import schema as db
from .receipts import SavedOperation


class HistoryError(ValueError):
    """Fixed safe code; driver diagnostics and content are not external output."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class HistoricalRevision:
    document_id: str
    revision_id: UUID
    revision_number: int
    parent_revision_id: UUID | None
    origin: str
    created_at: datetime
    producer_operation_id: UUID | None
    format_version: int
    engine_profile: str
    content_digest: str
    snapshot: dict

    @property
    def domain(self) -> dict:
        return domain_from_snapshot(self.snapshot, str(self.revision_id))


@dataclass(frozen=True)
class ChangeMaterial:
    receipt: SavedOperation
    base: HistoricalRevision | None
    result: HistoricalRevision | None


@dataclass(frozen=True)
class RunChangeMaterial:
    """A captured committed-operation range, not proof of a complete native run."""

    continuity: Literal["none", "continuous", "discontinuous"]
    receipts: tuple[SavedOperation, ...]
    base: HistoricalRevision | None
    result: HistoricalRevision | None


@dataclass(frozen=True)
class RevisionPage:
    document_id: str
    anchor_revision_id: UUID
    anchor_revision_number: int
    revisions: tuple[HistoricalRevision, ...]
    has_more: bool
    next_before: int | None


# A fixed join for this schema, including the unique committed producer and
# immediate parent number. No per-row lookup or general repository abstraction.
_PARENT = db.jd_revision.alias("parent")
_PRODUCER = db.jd_operation.alias("producer")
_REVISION_READ = sa.select(
    db.jd_revision,
    _PARENT.c.revision_number.label("_parent_number"),
    *[column.label(f"_op_{column.name}") for column in _PRODUCER.c],
).select_from(db.jd_revision.outerjoin(
    _PARENT,
    sa.and_(_PARENT.c.document_id == db.jd_revision.c.document_id,
            _PARENT.c.revision_id == db.jd_revision.c.parent_revision_id),
).outerjoin(
    _PRODUCER,
    sa.and_(_PRODUCER.c.document_id == db.jd_revision.c.document_id,
            _PRODUCER.c.result_revision_id == db.jd_revision.c.revision_id,
            _PRODUCER.c.status == "committed"),
))


def _document_id(value):
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise HistoryError("invalid_input")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise HistoryError("invalid_input") from None


def _uuid(value):
    if not isinstance(value, UUID):
        raise HistoryError("invalid_input")


def _receipt(row) -> SavedOperation:
    try:
        return SavedOperation.from_row(row)
    except Exception:
        raise HistoryError("stored_content_mismatch") from None


def _revision_producer(row) -> SavedOperation | None:
    """Shared revision/parent/receipt invariants without loading snapshot JSON."""
    try:
        if row["format_version"] != FORMAT_VERSION or row["engine_profile"] != ENGINE_PROFILE:
            raise HistoryError("stored_content_mismatch")
        producer = None
        if row["origin"] == "initial":
            if (row["revision_number"] != 1 or row["parent_revision_id"] is not None
                    or row["_op_operation_id"] is not None):
                raise HistoryError("stored_content_mismatch")
        else:
            if (row["revision_number"] <= 1 or row["parent_revision_id"] is None
                    or row["_parent_number"] != row["revision_number"] - 1
                    or row["_op_operation_id"] is None):
                raise HistoryError("stored_content_mismatch")
            producer = _receipt({column.name: row[f"_op_{column.name}"] for column in _PRODUCER.c})
            if (producer.document_id != row["document_id"] or producer.origin != row["origin"]
                    or producer.base_revision_id != row["parent_revision_id"]
                    or producer.result_revision_id != row["revision_id"] or producer.status != "committed"):
                raise HistoryError("stored_content_mismatch")
        return producer
    except HistoryError:
        raise
    except Exception:
        raise HistoryError("stored_content_mismatch") from None


def _verified_revision(row) -> HistoricalRevision:
    try:
        snapshot = snapshot_from_domain(domain_from_snapshot(row["snapshot"], str(row["revision_id"])))
        if (snapshot["document_id"] != row["document_id"] or snapshot != row["snapshot"]
                or snapshot_digest(snapshot) != row["content_digest"]):
            raise HistoryError("stored_content_mismatch")
        producer = _revision_producer(row)
        return HistoricalRevision(
            row["document_id"], row["revision_id"], row["revision_number"], row["parent_revision_id"],
            row["origin"], row["created_at"], producer.operation_id if producer else None,
            row["format_version"], row["engine_profile"], row["content_digest"], snapshot,
        )
    except HistoryError:
        raise
    except Exception:
        raise HistoryError("stored_content_mismatch") from None


class HistoryReader:
    def __init__(self, engine: sa.Engine):
        if engine.dialect.name != "postgresql" or engine.dialect.driver != "psycopg":
            raise HistoryError("unsupported_database")
        self.engine = engine

    @contextmanager
    def _read(self):
        try:
            # Set both options before the first query/autobegin; release before
            # the caller projects refs or calls an external source owner.
            with self.engine.connect().execution_options(
                isolation_level="REPEATABLE READ", postgresql_readonly=True,
            ) as conn, conn.begin():
                yield conn
        except HistoryError:
            raise
        except Exception:
            raise HistoryError("read_failed") from None

    @staticmethod
    def _revision(conn, document_id, revision_id):
        row = conn.execute(_REVISION_READ.where(
            db.jd_revision.c.document_id == document_id,
            db.jd_revision.c.revision_id == revision_id,
        )).mappings().one_or_none()
        if row is None:
            raise HistoryError("revision_missing")
        return _verified_revision(row)

    def read_revision(self, document_id: str, revision_id: UUID) -> HistoricalRevision:
        _document_id(document_id)
        _uuid(revision_id)
        with self._read() as conn:
            return self._revision(conn, document_id, revision_id)

    def read_change(self, document_id: str, operation_id: UUID) -> ChangeMaterial:
        _document_id(document_id)
        _uuid(operation_id)
        with self._read() as conn:
            row = conn.execute(sa.select(db.jd_operation).where(
                db.jd_operation.c.document_id == document_id,
                db.jd_operation.c.operation_id == operation_id,
            )).mappings().one_or_none()
            if row is None:
                raise HistoryError("operation_missing")
            receipt = _receipt(row)
            if receipt.status not in {"committed", "no_change"}:
                return ChangeMaterial(receipt, None, None)
            if receipt.base_revision_id is None or receipt.result_revision_id is None:
                raise HistoryError("stored_content_mismatch")
            base = self._revision(conn, document_id, receipt.base_revision_id)
            if receipt.status == "no_change":
                if receipt.result_revision_id != receipt.base_revision_id:
                    raise HistoryError("stored_content_mismatch")
                return ChangeMaterial(receipt, base, base)
            result = self._revision(conn, document_id, receipt.result_revision_id)
            if result.producer_operation_id != receipt.operation_id or result.parent_revision_id != base.revision_id:
                raise HistoryError("stored_content_mismatch")
            return ChangeMaterial(receipt, base, result)

    def read_run_operations(self, document_id: str, run_id: str, *, limit: int = 96) -> tuple[SavedOperation, ...]:
        """Return this snapshot's saved AI receipts, never a truncated run result.

        UUID ordering is stable presentation only, not transaction execution
        order. An empty tuple proves no visible saved rows, not a missing run,
        failed operation, or stopped writer. The native run owner must join its
        original bindings and establish whether that observation is complete.
        """
        _document_id(document_id)
        _document_id(run_id)  # Preserve existing persisted identifier semantics.
        if type(limit) is not int or not 1 <= limit <= 96:
            raise HistoryError("invalid_input")
        with self._read() as conn:
            if conn.execute(sa.select(db.jd_document.c.id).where(
                    db.jd_document.c.id == document_id)).scalar_one_or_none() is None:
                raise HistoryError("document_missing")
            rows = conn.execute(sa.select(db.jd_operation).where(
                db.jd_operation.c.document_id == document_id,
                db.jd_operation.c.ai_run_id == run_id,
                db.jd_operation.c.origin == "ai",
            ).order_by(db.jd_operation.c.operation_id).limit(limit + 1)).mappings().all()
            if len(rows) > limit:
                raise HistoryError("run_operations_limit_exceeded")
            return tuple(_receipt(row) for row in rows)

    def read_run_change(self, document_id: str, run_id: str,
                        operation_ids: tuple[UUID, ...]) -> RunChangeMaterial:
        """Read one captured AI change range in one read-only SQL snapshot.

        The caller owns native run membership/completeness. Only these exact
        committed IDs are read, even if the same run later commits more work.
        Metadata for every operation is checked in one batch; only a continuous
        range loads its two full endpoint snapshots. No Saver or current head
        is consulted and no operation, diff or terminal state is invented.
        """
        _document_id(document_id)
        _document_id(run_id)
        if (type(operation_ids) is not tuple or len(operation_ids) > 96
                or any(not isinstance(identity, UUID) for identity in operation_ids)
                or len(set(operation_ids)) != len(operation_ids)):
            raise HistoryError("invalid_input")
        with self._read() as conn:
            if conn.execute(sa.select(db.jd_document.c.id).where(
                    db.jd_document.c.id == document_id)).scalar_one_or_none() is None:
                raise HistoryError("document_missing")
            if not operation_ids:
                return RunChangeMaterial("none", (), None, None)
            # Keep the existing same-document producer/parent joins, but never
            # materialize intermediate snapshot JSON merely to check a chain.
            statement = _REVISION_READ.with_only_columns(
                *[column for column in _REVISION_READ.selected_columns if column.key != "snapshot"],
            ).where(db.jd_revision.c.document_id == document_id,
                    _PRODUCER.c.document_id == document_id,
                    _PRODUCER.c.ai_run_id == run_id,
                    _PRODUCER.c.origin == "ai",
                    _PRODUCER.c.operation_id.in_(operation_ids))
            rows = conn.execute(statement).mappings().all()
            requested = set(operation_ids)
            found, revisions, numbers, verified = set(), set(), set(), []
            for row in rows:
                producer = _revision_producer(row)
                if (producer is None or producer.operation_id not in requested
                        or producer.operation_id in found or producer.document_id != document_id
                        or producer.origin != "ai" or producer.ai_run_id != run_id
                        or row["revision_id"] in revisions or row["revision_number"] in numbers):
                    raise HistoryError("stored_content_mismatch")
                found.add(producer.operation_id)
                revisions.add(row["revision_id"])
                numbers.add(row["revision_number"])
                verified.append((row["revision_number"], producer))
            if found != requested:
                raise HistoryError("operation_missing")
            verified.sort(key=lambda item: item[0])
            receipts = tuple(producer for _, producer in verified)
            if any(right.base_revision_id != left.result_revision_id or right_number != left_number + 1
                   for (left_number, left), (right_number, right) in zip(verified, verified[1:])):
                return RunChangeMaterial("discontinuous", receipts, None, None)
            base = self._revision(conn, document_id, receipts[0].base_revision_id)
            result = self._revision(conn, document_id, receipts[-1].result_revision_id)
            if (base.document_id != document_id or result.document_id != document_id
                    or base.revision_id != receipts[0].base_revision_id
                    or base.revision_number != verified[0][0] - 1
                    or result.revision_id != receipts[-1].result_revision_id
                    or result.revision_number != verified[-1][0]
                    or result.producer_operation_id != receipts[-1].operation_id):
                raise HistoryError("stored_content_mismatch")
            return RunChangeMaterial("continuous", receipts, base, result)

    def list_revisions(self, document_id: str, anchor_revision_id: UUID | None = None,
                       before_number: int | None = None, limit: int = 50) -> RevisionPage:
        _document_id(document_id)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise HistoryError("invalid_input")
        if anchor_revision_id is not None:
            _uuid(anchor_revision_id)
        if before_number is not None and (anchor_revision_id is None or type(before_number) is not int or before_number < 1):
            raise HistoryError("invalid_input")
        with self._read() as conn:
            if conn.execute(sa.select(db.jd_document.c.id).where(db.jd_document.c.id == document_id)).scalar_one_or_none() is None:
                raise HistoryError("document_missing")
            head = None
            if anchor_revision_id is None:
                head = conn.execute(sa.select(db.jd_head).where(
                    db.jd_head.c.document_id == document_id)).mappings().one_or_none()
                if head is None:
                    raise HistoryError("head_missing")
                anchor_revision_id = head["current_revision_id"]
            anchor = self._revision(conn, document_id, anchor_revision_id)
            if head is not None and head["revision_number"] != anchor.revision_number:
                raise HistoryError("stored_content_mismatch")
            if before_number is not None and before_number > anchor.revision_number:
                raise HistoryError("invalid_input")
            statement = _REVISION_READ.where(db.jd_revision.c.document_id == document_id,
                                             db.jd_revision.c.revision_number <= anchor.revision_number)
            if before_number is not None:
                statement = statement.where(db.jd_revision.c.revision_number < before_number)
            rows = conn.execute(statement.order_by(db.jd_revision.c.revision_number.desc()).limit(limit + 1)).mappings().all()
            revisions = tuple(_verified_revision(row) for row in rows)
            has_more = len(revisions) > limit
            revisions = revisions[:limit]
            return RevisionPage(document_id, anchor.revision_id, anchor.revision_number,
                                revisions, has_more, revisions[-1].revision_number if has_more else None)
