"""Execution owner 公開的具名唯讀 SQL 投影，不暴露可寫入的 ORM。"""

from uuid import UUID

from sqlalchemy import Select

from caliburn.features.executions import persistence


def completed_consultant_executions_projection(job_file_id: UUID) -> Select[UUID]:
    """提供同職務的 completed 顧問身分，供固定上界的跨域讀取組合。"""
    return persistence.completed_consultant_executions_projection(job_file_id)
