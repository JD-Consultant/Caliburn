"""Fixed, read-only historical JD material; no tokens, sources or writer authority.

Every public read materializes its result in one short READ ONLY REPEATABLE READ
transaction. Historical identity never falls back to the latest current head.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
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


def _verified_revision(row) -> HistoricalRevision:
    try:
        snapshot = snapshot_from_domain(domain_from_snapshot(row["snapshot"], str(row["revision_id"])))
        if (row["format_version"] != FORMAT_VERSION or row["engine_profile"] != ENGINE_PROFILE
                or snapshot["document_id"] != row["document_id"] or snapshot != row["snapshot"]
                or snapshot_digest(snapshot) != row["content_digest"]):
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
