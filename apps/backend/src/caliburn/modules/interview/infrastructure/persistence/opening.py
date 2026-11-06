"""將開場加入呼叫端既有的交易。"""

from uuid import UUID

from sqlalchemy.orm import Session

from caliburn.modules.interview.application.recording import prepare_opening
from caliburn.modules.interview.application.results import MessageView
from caliburn.modules.interview.infrastructure.persistence.repository import (
    SqlAlchemyInterviewRepository,
)


def stage_opening(*, session: Session, workspace_id: UUID, text: str) -> MessageView:
    """寫入並 flush，提交與回滾留給持有 Session 的用例。"""
    if not session.in_transaction():
        raise ValueError("stage_opening requires an active outer transaction")
    result = prepare_opening(
        workspace_id=workspace_id,
        text=text,
        turns=SqlAlchemyInterviewRepository(session),
    )
    session.flush()
    return result
