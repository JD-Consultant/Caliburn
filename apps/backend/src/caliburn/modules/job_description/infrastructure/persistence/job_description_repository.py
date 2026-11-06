"""唯一 JD 根的鎖定載入、關聯式差異與完整快照；不自行提交。"""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from caliburn.modules.job_description.application.content import JobDescriptionContent
from caliburn.modules.job_description.application.content_comparison import same_content
from caliburn.modules.job_description.application.errors import (
    JobDescriptionNotFoundError,
)
from caliburn.modules.job_description.application.history_types import RestoreMetadata
from caliburn.modules.job_description.application.persistence import (
    LoadedJobDescription,
)
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)

from .content_mapping import ContentRows, load_current_content
from .content_saving import save_content
from .errors import translate_persistence_error
from .orm_models import JobDescriptionRow, JobDescriptionSnapshotRow
from .snapshot_codec import SCHEMA_VERSION, encode_snapshot


class SqlAlchemyJobDescriptionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._rows: ContentRows | None = None
        self._original: JobDescriptionContent | None = None
        self._version: int | None = None
        self._saved = False

    def get_for_update(
        self, *, workspace_id: UUID, job_description_id: UUID
    ) -> LoadedJobDescription:
        if self._rows is not None:
            raise RuntimeError("每個 JD 用例須使用自己的新 UoW")
        try:
            with self._session.no_autoflush:
                row = self._session.scalar(
                    select(JobDescriptionRow)
                    .where(
                        JobDescriptionRow.workspace_id == workspace_id,
                        JobDescriptionRow.id == job_description_id,
                    )
                    .with_for_update()
                )
                if row is None:
                    raise JobDescriptionNotFoundError("指定 JD 不存在")
                rows = load_current_content(self._session, row)
            job_description = rows.to_domain()
            self._rows = rows
            self._original = JobDescriptionContent.from_domain(job_description)
            self._version = row.version
            return LoadedJobDescription(job_description, row.version)
        except SQLAlchemyError as error:
            raise translate_persistence_error(
                error, commit_status="not_committed"
            ) from error

    def add(
        self, job_description: JobDescription, /, *, correlation_id: str | None = None
    ) -> int:
        if self._rows is not None or self._saved:
            raise RuntimeError("每個 JD 用例只能保存同一份 JD")
        level = job_description.baseline_competency_level
        row = JobDescriptionRow(
            id=job_description.id,
            workspace_id=job_description.workspace_id,
            job_title=job_description.job_title,
            organization_unit=job_description.organization_unit,
            reports_to=job_description.reports_to,
            purpose=job_description.purpose,
            baseline_competency_level=level.value if level else None,
            version=1,
        )
        try:
            self._session.add(row)
            self._session.flush()
            save_content(
                self._session, ContentRows(job_description_row=row), job_description
            )
            self._record(job_description, 1, "created", correlation_id, None)
            self._session.flush()
        except SQLAlchemyError as error:
            raise translate_persistence_error(
                error, commit_status="not_committed"
            ) from error
        self._saved = True
        return 1

    def save(
        self,
        job_description: JobDescription,
        *,
        correlation_id: str | None = None,
        restore: RestoreMetadata | None = None,
    ) -> int:
        if self._saved:
            raise RuntimeError("每個 JD UoW 只能完成一次保存，包含 no-op")
        rows, original, version = self._loaded(job_description)
        changed = not same_content(
            original, JobDescriptionContent.from_domain(job_description)
        )
        if not changed and restore is None:
            self._saved = True
            return version
        try:
            # 明確恢復總是建立下一版；內容相同時不改寫任何子列。
            rows.job_description_row.version = version + 1
            if changed:
                save_content(self._session, rows, job_description)
            self._record(
                job_description,
                version + 1,
                "restored" if restore else "edited",
                correlation_id,
                restore,
            )
            self._session.flush()
        except SQLAlchemyError as error:
            raise translate_persistence_error(
                error, commit_status="not_committed"
            ) from error
        self._saved = True
        return version + 1

    def _loaded(
        self, job_description: JobDescription
    ) -> tuple[ContentRows, JobDescriptionContent, int]:
        if self._rows is None or self._original is None or self._version is None:
            raise RuntimeError("保存前須在本 UoW 鎖定並載入 JD")
        if (
            job_description.id != self._original.job_description_id
            or job_description.workspace_id != self._original.workspace_id
        ):
            raise ValueError("保存不能替換 JD 身分或 Workspace 歸屬")
        return self._rows, self._original, self._version

    def _record(
        self,
        job_description: JobDescription,
        version: int,
        kind: Literal["created", "edited", "restored"],
        correlation_id: str | None,
        restore: RestoreMetadata | None,
    ) -> None:
        self._session.add(
            JobDescriptionSnapshotRow(
                job_description_id=job_description.id,
                version=version,
                schema_version=SCHEMA_VERSION,
                content=encode_snapshot(job_description),
                recorded_at=datetime.now(UTC),
                kind=kind,
                restored_from_version=restore.target_version if restore else None,
                correlation_id=correlation_id,
                reverts_correlation_id=restore.reverts_correlation_id
                if restore
                else None,
            )
        )
