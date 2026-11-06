"""依真正資料庫錯誤與已觀察提交證據分類，不推測重試資格。"""

from dataclasses import dataclass
from typing import Literal

from psycopg import Error as PostgresError
from sqlalchemy import Engine, ExceptionContext, event
from sqlalchemy.exc import DBAPIError

from caliburn.modules.interview.application.errors import (
    InterviewConcurrencyError,
    InterviewPersistenceError,
)

type CommitStatus = Literal["not_committed", "committed", "unknown"]

FAILURE_EVIDENCE_OPTION = "_caliburn_interview_failure_evidence"


@dataclass(slots=True)
class DatabaseFailureEvidence:
    error: BaseException | None = None


@event.listens_for(Engine, "handle_error")
def _observe_database_error(context: ExceptionContext) -> None:
    if context.connection is None:
        return
    evidence = context.connection.get_execution_options().get(FAILURE_EVIDENCE_OPTION)
    if isinstance(evidence, DatabaseFailureEvidence):
        evidence.error = context.sqlalchemy_exception


def translate_persistence_error(
    error: Exception,
    *,
    commit_status: CommitStatus,
    database_error: BaseException | None = None,
) -> Exception:
    if commit_status == "committed":
        return InterviewPersistenceError(commit_status="committed")
    # COMMIT 區段的 Session hook 可以偽裝相同 SQLSTATE；只信原生錯誤事件。
    if commit_status == "unknown" and error is not database_error:
        return InterviewPersistenceError(commit_status="unknown")
    if isinstance(error, DBAPIError) and isinstance(error.orig, PostgresError):
        state = error.orig.sqlstate
        if state == "40001":
            return InterviewConcurrencyError(reason="serialization")
        if state == "40P01":
            return InterviewConcurrencyError(reason="deadlock")
        if state == "55P03":
            return InterviewConcurrencyError(reason="lock_timeout")
        if state is not None and state.startswith("23"):
            commit_status = "not_committed"
    return InterviewPersistenceError(commit_status=commit_status)
