"""Execution owner 公開的具名唯讀 SQL 投影，不暴露可寫入的 ORM。"""

from uuid import UUID

from sqlalchemy import Select

from caliburn.features.executions import persistence


def completed_consultant_executions_projection(job_file_id: UUID) -> Select[UUID]:
    """提供同職務的 completed 顧問身分，供固定上界的跨域讀取組合。"""
    return persistence.completed_consultant_executions_projection(job_file_id)


def consolidation_executions_projection(job_file_id: UUID | None = None) -> Select[UUID, UUID, str]:
    """Qualification metadata; include terminal and incomplete A for explicit validation."""
    return persistence.consolidation_executions_projection(job_file_id)
