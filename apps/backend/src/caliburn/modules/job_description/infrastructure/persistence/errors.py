"""依 PostgreSQL SQLSTATE 與具名約束轉譯，保留未知技術失敗。"""

from psycopg import Error as PostgresError
from sqlalchemy.exc import DBAPIError

from caliburn.modules.job_description.application.errors import (
    CommitStatus,
    JobDescriptionAlreadyExistsError,
    JobDescriptionConcurrencyError,
    JobDescriptionNameConflictError,
    JobDescriptionPersistenceError,
    JobDescriptionRetryableTransactionError,
    JobDescriptionWorkspaceNotFoundError,
)


def translate_persistence_error(
    error: Exception, *, commit_status: CommitStatus
) -> Exception:
    if commit_status == "committed":
        return JobDescriptionPersistenceError(commit_status="committed")
    if isinstance(error, DBAPIError) and isinstance(error.orig, PostgresError):
        cause = error.orig
        if cause.sqlstate == "40001":
            return JobDescriptionRetryableTransactionError("JD 序列化失敗，交易未提交")
        if cause.sqlstate in {"40P01", "55P03"}:
            return JobDescriptionConcurrencyError(
                "JD 並行寫入遭資料庫拒絕",
                reason="deadlock" if cause.sqlstate == "40P01" else "lock_timeout",
            )
        if cause.sqlstate is not None and cause.sqlstate.startswith("23"):
            # 伺服器明確拒絕約束；不把 40003／08007 的未知結果放入此類。
            commit_status = "not_committed"
        if (
            cause.sqlstate == "23503"
            and cause.diag.constraint_name == "fk_job_descriptions_workspace_id"
        ):
            return JobDescriptionWorkspaceNotFoundError("JD 指定的 Workspace 不存在")
        if (
            cause.sqlstate == "23505"
            and cause.diag.constraint_name == "uq_job_descriptions_workspace_id"
        ):
            return JobDescriptionAlreadyExistsError("Workspace 已有 JD")
        if cause.sqlstate == "23505" and cause.diag.constraint_name in {
            "uq_job_tasks_name",
            "uq_duties_name",
            "uq_knowledge_name",
            "uq_skills_name",
        }:
            return JobDescriptionNameConflictError("同 JD 同種類已有此名稱")
        if cause.sqlstate == "23505" and cause.diag.constraint_name in {
            "uq_job_tasks_position",
            "uq_duties_position",
            "uq_knowledge_position",
            "uq_skills_position",
            "uq_task_outcomes_position",
            "uq_task_requirements_position",
            "uq_task_knowledge_position",
            "uq_task_skills_position",
            "uq_collaboration_entries_position",
            "uq_job_conditions_position",
        }:
            return JobDescriptionConcurrencyError(
                "JD 組內位置發生並行競爭", reason="order"
            )
    return JobDescriptionPersistenceError(commit_status=commit_status)
