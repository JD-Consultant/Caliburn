"""以 Connection 專屬證據分辨原生提交拒絕與提交後的事件錯誤。"""

from dataclasses import dataclass

from psycopg import Error as PostgresError
from sqlalchemy import Engine, ExceptionContext, event

FAILURE_EVIDENCE_OPTION = "_caliburn_jd_failure_evidence"


@dataclass(slots=True)
class DatabaseFailureEvidence:
    error: BaseException | None = None


@event.listens_for(Engine, "handle_error")
def _observe_database_failure(context: ExceptionContext) -> None:
    # 全域 listener 僅觀察明示 opt-in 的 Connection，不留 UoW／pool 全域 registry。
    if context.connection is None:
        return
    evidence = context.connection.get_execution_options().get(FAILURE_EVIDENCE_OPTION)
    if not isinstance(evidence, DatabaseFailureEvidence):
        return
    original = context.original_exception
    if isinstance(original, PostgresError):
        evidence.error = context.sqlalchemy_exception
