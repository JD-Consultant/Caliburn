"""全部既有內容用例以真 PG 驗提交、過期及提交前故障的原子性。"""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, event, text

from caliburn.modules.job_description.application.errors import (
    JobDescriptionConcurrencyError,
    JobDescriptionNotFoundError,
    JobDescriptionPersistenceError,
)
from caliburn.modules.job_description.application.queries import get_job_description
from caliburn.modules.job_description.infrastructure.persistence.queries import (
    SqlAlchemyJobDescriptionQueries,
)
from caliburn.modules.job_description.infrastructure.persistence.unit_of_work import (
    SqlAlchemyJobDescriptionUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.content_scenarios import (
    CASES,
    JD,
    ContentCheck,
    WriteOperation,
    complete_root,
)


@pytest.mark.parametrize(
    "operation, check",
    [pytest.param(operation, check, id=name) for name, operation, check in CASES],
)
def test_content_write_rejects_stale_input_rolls_back_failure_and_commits(
    pg_engine: Engine,
    jd_workspace_id: UUID,
    operation: WriteOperation,
    check: ContentCheck,
) -> None:
    sessions = create_session_factory(pg_engine)
    # 完整聚合為固定輸入資料；受測入口仍是公開 Application。
    with SqlAlchemyJobDescriptionUnitOfWork(sessions) as setup:
        setup.job_descriptions.add(complete_root(workspace_id=jd_workspace_id))
        setup.commit()
    before = get_job_description(
        workspace_id=jd_workspace_id,
        job_description_id=JD,
        queries=SqlAlchemyJobDescriptionQueries(pg_engine),
    )
    with pg_engine.connect() as connection:
        original_snapshots = connection.scalar(
            text("SELECT count(*) FROM job_description_snapshots")
        )

    with pytest.raises(JobDescriptionNotFoundError):
        operation(SqlAlchemyJobDescriptionUnitOfWork(sessions), before.version, uuid4())

    with pytest.raises(JobDescriptionConcurrencyError):
        operation(
            SqlAlchemyJobDescriptionUnitOfWork(sessions),
            before.version + 10,
            jd_workspace_id,
        )

    failure = OSError("合成提交前故障")
    session = sessions()

    def fail_commit(*args: object) -> None:
        raise failure

    event.listen(session, "before_commit", fail_commit)
    with pytest.raises(JobDescriptionPersistenceError) as rejected:
        operation(
            SqlAlchemyJobDescriptionUnitOfWork(lambda: session),
            before.version,
            jd_workspace_id,
        )
    assert rejected.value.commit_status == "not_committed"
    assert rejected.value.__cause__ is failure
    assert (
        get_job_description(
            workspace_id=jd_workspace_id,
            job_description_id=JD,
            queries=SqlAlchemyJobDescriptionQueries(pg_engine),
        )
        == before
    )
    with pg_engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT count(*) FROM job_description_snapshots"))
            == original_snapshots
        )

    result = operation(
        SqlAlchemyJobDescriptionUnitOfWork(sessions), before.version, jd_workspace_id
    )
    assert check(result)
    changed = result != before
    assert result.version == before.version + int(changed)
    assert (
        get_job_description(
            workspace_id=jd_workspace_id,
            job_description_id=JD,
            queries=SqlAlchemyJobDescriptionQueries(pg_engine),
        )
        == result
    )
    with pg_engine.connect() as connection:
        assert connection.scalar(
            text("SELECT count(*) FROM job_description_snapshots")
        ) == original_snapshots + int(changed)
