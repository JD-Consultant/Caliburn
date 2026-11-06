"""配置失敗不回傳暫存短碼，後續以同一業務 UUID 重新配置。"""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, event, text
from sqlalchemy.orm import Session

from caliburn.modules.model_references import (
    ReferenceTarget,
    UnknownModelReferenceError,
)
from caliburn.modules.model_references.persistence import SqlAlchemyModelReferences
from caliburn.shared.infrastructure.persistence.database import create_session_factory


class CommitRejectedError(RuntimeError):
    pass


def test_failed_commit_never_publishes_or_retains_tentative_reference(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    target = ReferenceTarget("task", uuid4())
    tentative_refs: list[str] = []

    def reject_commit(session: Session) -> None:
        # 只在真交易故障注入點觀察暫存號碼；正常驗收仍走公開解析接口。
        number = session.scalar(
            text("SELECT reference_number FROM model_references WHERE resource_id=:id"),
            {"id": target.resource_id},
        )
        assert isinstance(number, int)
        tentative_refs.append(f"task_{number}")
        raise CommitRejectedError("injected before commit")

    def failing_session() -> Session:
        session = sessions()
        event.listen(session, "before_commit", reject_commit)
        return session

    with pytest.raises(CommitRejectedError):
        SqlAlchemyModelReferences(failing_session).get_or_create_refs(
            jd_workspace_id, [target]
        )

    references = SqlAlchemyModelReferences(sessions)
    with pytest.raises(UnknownModelReferenceError):
        references.resolve_refs(jd_workspace_id, tentative_refs)
    saved = references.get_or_create_refs(jd_workspace_id, [target])[target]
    assert saved not in tentative_refs
    assert references.resolve_refs(jd_workspace_id, [saved]) == {saved: target}
