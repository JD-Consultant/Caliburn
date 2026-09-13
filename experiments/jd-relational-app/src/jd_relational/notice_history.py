"""Bounded notification material from the existing immutable revision history.

This reader establishes a change-notice boundary, not proof that a model read JD
content. It issues no refs and never reads snapshots or calls a source/provider.
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

import sqlalchemy as sa

from jd_relational.snapshots import ENGINE_PROFILE, FORMAT_VERSION
from jd_relational.storage import schema as db
from jd_relational.storage.history import HistoryError, HistoryReader, _document_id, _uuid
from jd_relational.storage.receipts import CommandKind, SavedOperation


@dataclass(frozen=True)
class NoticeBoundary:
    revision_id: UUID
    revision_number: int


@dataclass(frozen=True)
class NoticeEvent:
    operation_id: UUID
    base_revision_id: UUID
    base_revision_number: int
    result_revision_id: UUID
    result_revision_number: int
    origin: Literal["manual", "ai"]
    command_kind: CommandKind


@dataclass(frozen=True)
class NoticeMaterial:
    document_id: str
    baseline: NoticeBoundary | None
    head: NoticeBoundary
    events: tuple[NoticeEvent, ...]
    manual_count: int
    ai_count: int
    omitted_count: int

    @property
    def total_count(self) -> int:
        return self.manual_count + self.ai_count


_REVISION = db.jd_revision
_PARENT = db.jd_revision.alias("notice_parent")
_PRODUCER = db.jd_operation.alias("notice_producer")
_BOUNDARY_READ = sa.select(
    _REVISION.c.revision_id, _REVISION.c.revision_number,
    _REVISION.c.parent_revision_id, _REVISION.c.origin,
    _REVISION.c.format_version, _REVISION.c.engine_profile,
)
_EVENT_FROM = _REVISION.outerjoin(
    _PARENT, sa.and_(
        _PARENT.c.document_id == _REVISION.c.document_id,
        _PARENT.c.revision_id == _REVISION.c.parent_revision_id,
    ),
).outerjoin(
    _PRODUCER, sa.and_(
        _PRODUCER.c.document_id == _REVISION.c.document_id,
        _PRODUCER.c.result_revision_id == _REVISION.c.revision_id,
        _PRODUCER.c.status == "committed",
    ),
)
_VALID_EVENT = sa.and_(
    _REVISION.c.format_version == FORMAT_VERSION,
    _REVISION.c.engine_profile == ENGINE_PROFILE,
    _REVISION.c.origin.in_(("manual", "ai")),
    _REVISION.c.revision_number > 1,
    _PARENT.c.revision_number == _REVISION.c.revision_number - 1,
    _PRODUCER.c.operation_id.is_not(None),
    _PRODUCER.c.origin == _REVISION.c.origin,
    _PRODUCER.c.base_revision_id == _REVISION.c.parent_revision_id,
    _PRODUCER.c.result_revision_id == _REVISION.c.revision_id,
)
_EVENT_READ = sa.select(
    _REVISION.c.document_id, _REVISION.c.revision_id,
    _REVISION.c.revision_number, _REVISION.c.parent_revision_id,
    _REVISION.c.origin, _PARENT.c.revision_number.label("_parent_number"),
    *[column.label(f"_op_{column.name}") for column in _PRODUCER.c],
).select_from(_EVENT_FROM)


def _boundary(conn, document_id: str, revision_id: UUID, missing_code: str) -> NoticeBoundary:
    row = conn.execute(_BOUNDARY_READ.where(
        _REVISION.c.document_id == document_id,
        _REVISION.c.revision_id == revision_id,
    )).mappings().one_or_none()
    if row is None:
        raise HistoryError(missing_code)
    if (row["format_version"] != FORMAT_VERSION or row["engine_profile"] != ENGINE_PROFILE
            or type(row["revision_number"]) is not int or row["revision_number"] < 1
            or (row["origin"] == "initial" and (
                row["revision_number"] != 1 or row["parent_revision_id"] is not None))
            or (row["origin"] != "initial" and (
                row["origin"] not in {"manual", "ai"} or row["revision_number"] <= 1
                or row["parent_revision_id"] is None))):
        raise HistoryError("stored_content_mismatch")
    return NoticeBoundary(row["revision_id"], row["revision_number"])


def _event(row) -> NoticeEvent:
    try:
        receipt = SavedOperation.from_row({
            column.name: row[f"_op_{column.name}"] for column in _PRODUCER.c
        })
        if (receipt.status != "committed" or receipt.document_id != row["document_id"]
                or receipt.origin != row["origin"] or receipt.origin not in {"manual", "ai"}
                or receipt.base_revision_id != row["parent_revision_id"]
                or receipt.result_revision_id != row["revision_id"]
                or row["_parent_number"] != row["revision_number"] - 1):
            raise HistoryError("stored_content_mismatch")
        return NoticeEvent(receipt.operation_id, receipt.base_revision_id, row["_parent_number"],
                           receipt.result_revision_id, row["revision_number"],
                           receipt.origin, receipt.body.command_kind)
    except HistoryError:
        raise
    except Exception:
        raise HistoryError("stored_content_mismatch") from None


class NoticeHistoryReader(HistoryReader):
    """A fixed lightweight query using HistoryReader's read-only transaction seam."""

    def read(self, document_id: str, baseline: NoticeBoundary | None = None,
             *, limit: int = 20) -> NoticeMaterial:
        _document_id(document_id)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise HistoryError("invalid_input")
        if baseline is not None:
            if not isinstance(baseline, NoticeBoundary):
                raise HistoryError("invalid_input")
            _uuid(baseline.revision_id)
            if type(baseline.revision_number) is not int or baseline.revision_number < 1:
                raise HistoryError("invalid_input")
        with self._read() as conn:
            if conn.execute(sa.select(db.jd_document.c.id).where(
                    db.jd_document.c.id == document_id)).scalar_one_or_none() is None:
                raise HistoryError("document_missing")
            head_row = conn.execute(sa.select(
                db.jd_head.c.current_revision_id, db.jd_head.c.revision_number,
            ).where(db.jd_head.c.document_id == document_id)).mappings().one_or_none()
            if head_row is None:
                raise HistoryError("head_missing")
            head = _boundary(conn, document_id, head_row["current_revision_id"], "stored_content_mismatch")
            if head.revision_number != head_row["revision_number"]:
                raise HistoryError("stored_content_mismatch")
            if baseline is not None:
                # Never look in another document or silently replace a missing B.
                stored_base = _boundary(conn, document_id, baseline.revision_id, "baseline_missing")
                if stored_base != baseline:
                    raise HistoryError("baseline_mismatch")
                if baseline.revision_number > head.revision_number:
                    raise HistoryError("baseline_ahead")
            lower_number = baseline.revision_number if baseline else 1
            window = sa.and_(
                _REVISION.c.document_id == document_id,
                _REVISION.c.revision_number > lower_number,
                _REVISION.c.revision_number <= head.revision_number,
            )
            counts = conn.execute(sa.select(
                sa.func.count().label("total"),
                sa.func.count().filter(_REVISION.c.origin == "manual").label("manual"),
                sa.func.count().filter(_REVISION.c.origin == "ai").label("ai"),
                sa.func.count().filter(sa.not_(sa.func.coalesce(_VALID_EVENT, False))).label("invalid"),
            ).select_from(_EVENT_FROM).where(window)).mappings().one()
            # The schema's unique revision numbers and committed producers make
            # this an exact closed interval; a missing event is not a no_change.
            if (counts["invalid"] or counts["total"] != head.revision_number - lower_number
                    or counts["manual"] + counts["ai"] != counts["total"]):
                raise HistoryError("stored_content_mismatch")
            rows = conn.execute(_EVENT_READ.where(window).order_by(
                _REVISION.c.revision_number.desc(),
            ).limit(limit)).mappings().all()
            events = tuple(_event(row) for row in rows)
            if len(events) != min(limit, counts["total"]):
                raise HistoryError("stored_content_mismatch")
            return NoticeMaterial(document_id, baseline, head, events, counts["manual"],
                                  counts["ai"], counts["total"] - len(events))
