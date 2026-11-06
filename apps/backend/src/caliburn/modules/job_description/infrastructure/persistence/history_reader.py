"""在已核對 Workspace／JD 範圍內讀取版本摘要及完整快照。"""

import base64
import binascii
import json
from datetime import UTC
from typing import Literal
from uuid import UUID

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, load_only

from caliburn.modules.job_description.application.errors import (
    InvalidHistoryPaginationError,
    JobDescriptionHistoryDataError,
    JobDescriptionHistoryNotFoundError,
    JobDescriptionNotFoundError,
)
from caliburn.modules.job_description.application.history_types import (
    DEFAULT_HISTORY_PAGE_SIZE,
    HistoryEntry,
    HistoryPage,
    normalize_history_page_size,
)
from caliburn.modules.job_description.application.persistence import (
    HistoricalJobDescription,
)

from .orm_models import JobDescriptionRow, JobDescriptionSnapshotRow
from .snapshot_codec import decode_snapshot

# PostgreSQL INTEGER stores positive JD versions up to this bound.
_MAX_STORED_VERSION = 2**31 - 1
_KIND = TypeAdapter(Literal["created", "edited", "restored"])


class SqlAlchemyJobDescriptionHistoryReader:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _require_scope(self, workspace_id: UUID, job_description_id: UUID) -> None:
        if (
            self._session.scalar(
                select(JobDescriptionRow.id).where(
                    JobDescriptionRow.workspace_id == workspace_id,
                    JobDescriptionRow.id == job_description_id,
                )
            )
            is None
        ):
            raise JobDescriptionNotFoundError("指定 JD 不存在於此 Workspace")

    def list(
        self,
        *,
        workspace_id: UUID,
        job_description_id: UUID,
        page_size: int = DEFAULT_HISTORY_PAGE_SIZE,
        page_token: str | None = None,
        correlation_id: str | None = None,
        reverts_correlation_id: str | None = None,
    ) -> HistoryPage:
        size = normalize_history_page_size(page_size)
        self._require_scope(workspace_id, job_description_id)
        scope = [
            str(workspace_id),
            str(job_description_id),
            correlation_id,
            reverts_correlation_id,
        ]
        cursor = _decode_cursor(page_token, scope)
        snapshot = JobDescriptionSnapshotRow
        statement = (
            select(snapshot)
            .options(
                load_only(
                    snapshot.job_description_id,
                    snapshot.version,
                    snapshot.kind,
                    snapshot.recorded_at,
                    snapshot.restored_from_version,
                    snapshot.correlation_id,
                    snapshot.reverts_correlation_id,
                )
            )
            .where(snapshot.job_description_id == job_description_id)
        )
        if correlation_id is not None:
            statement = statement.where(snapshot.correlation_id == correlation_id)
        if reverts_correlation_id is not None:
            statement = statement.where(
                snapshot.reverts_correlation_id == reverts_correlation_id
            )
        if cursor is not None:
            if (
                self._session.scalar(statement.where(snapshot.version == cursor))
                is None
            ):
                raise InvalidHistoryPaginationError("續頁版本不屬於指定範圍")
            statement = statement.where(snapshot.version < cursor)
        rows = tuple(
            self._session.scalars(
                statement.order_by(snapshot.version.desc()).limit(size + 1)
            )
        )
        items = tuple(_entry(row) for row in rows[:size])
        token = _encode_cursor(scope, items[-1].version) if len(rows) > size else None
        return HistoryPage(items=items, next_page_token=token)

    def get(
        self, *, workspace_id: UUID, job_description_id: UUID, version: int
    ) -> HistoricalJobDescription:
        self._require_scope(workspace_id, job_description_id)
        if version > _MAX_STORED_VERSION:
            raise JobDescriptionHistoryNotFoundError("指定版本不是這份 JD 的有效保存")
        row = self._session.get(
            JobDescriptionSnapshotRow, (job_description_id, version)
        )
        if row is None:
            raise JobDescriptionHistoryNotFoundError("指定版本不是這份 JD 的有效保存")
        entry = _entry(row)
        job_description = decode_snapshot(
            row.content,
            schema_version=row.schema_version,
            workspace_id=workspace_id,
            job_description_id=job_description_id,
        )
        return HistoricalJobDescription(job_description=job_description, entry=entry)


def _entry(row: JobDescriptionSnapshotRow) -> HistoryEntry:
    try:
        return HistoryEntry(
            job_description_id=row.job_description_id,
            version=row.version,
            kind=_KIND.validate_python(row.kind),
            recorded_at=row.recorded_at.astimezone(UTC),
            restored_from_version=row.restored_from_version,
            correlation_id=row.correlation_id,
            reverts_correlation_id=row.reverts_correlation_id,
        )
    except (ValidationError, ValueError, TypeError, AttributeError) as error:
        raise JobDescriptionHistoryDataError("歷史保存摘要不完整") from error


def _encode_cursor(scope: list[str | None], version: int) -> str:
    payload = json.dumps([1, scope, version], ensure_ascii=False, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def _decode_cursor(token: str | None, scope: list[str | None]) -> int | None:
    if token is None:
        return None
    try:
        if not isinstance(token, str) or len(token) > 4096:
            raise ValueError("無效續頁資料")
        format_version, saved_scope, version = json.loads(
            base64.b64decode(token, altchars=b"-_", validate=True)
        )
        if (
            type(format_version) is not int
            or format_version != 1
            or saved_scope != scope
            or type(version) is not int
            or not 1 <= version <= _MAX_STORED_VERSION
        ):
            raise ValueError("續頁資料與查詢不符")
        return version
    except (ValueError, TypeError, binascii.Error, UnicodeError) as error:
        raise InvalidHistoryPaginationError("無效或不同範圍的歷史續頁資料") from error
