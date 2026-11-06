"""開場參與既有真 PG 交易，外層保留唯一提交／回滾責任。"""

from uuid import UUID

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from caliburn.modules.interview.infrastructure.persistence.opening import stage_opening
from caliburn.modules.interview.infrastructure.persistence.queries import (
    SqlAlchemyInterviewQueries,
)


@pytest.mark.parametrize("commit", [True, False])
def test_opening_flushes_into_outer_transaction_without_committing_or_closing_it(
    pg_engine: Engine, jd_workspace_id: UUID, commit: bool
) -> None:
    queries = SqlAlchemyInterviewQueries(pg_engine)
    with (
        pg_engine.connect().execution_options(
            isolation_level="SERIALIZABLE"
        ) as connection,
        Session(connection) as session,
    ):
        transaction = session.begin()
        staged = stage_opening(
            session=session, workspace_id=jd_workspace_id, text=" 原開場\n "
        )
        assert connection.in_transaction()
        assert not connection.closed
        assert connection.get_isolation_level() == "SERIALIZABLE"
        assert (
            connection.scalar(
                text("SELECT count(*) FROM interview_messages WHERE workspace_id=:id"),
                {"id": jd_workspace_id},
            )
            == 1
        )
        assert queries.list_messages(workspace_id=jd_workspace_id) == ()
        repeated = stage_opening(
            session=session, workspace_id=jd_workspace_id, text=" 原開場\n "
        )
        assert repeated.message_id == staged.message_id
        if commit:
            transaction.commit()
        else:
            transaction.rollback()
    actual = queries.list_messages(workspace_id=jd_workspace_id)
    assert [message.text for message in actual] == ([" 原開場\n "] if commit else [])


def test_stage_opening_requires_an_existing_transaction(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    with Session(pg_engine) as session:
        with pytest.raises(ValueError, match="transaction"):
            stage_opening(
                session=session, workspace_id=jd_workspace_id, text="不能偷開"
            )
        assert not session.in_transaction()
