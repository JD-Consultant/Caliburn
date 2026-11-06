"""完整及局部查詢使用單一唯讀快照，失敗後不污染連線池。"""

from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID

import pytest
from sqlalchemy import Connection, CursorResult, Engine, event, text
from sqlalchemy.sql import ClauseElement, Select

from caliburn.modules.job_description.application.duties import delete_duty
from caliburn.modules.job_description.application.errors import JobDescriptionQueryError
from caliburn.modules.job_description.application.job_descriptions import (
    UpdateJobDescriptionInput,
    update_job_description,
)
from caliburn.modules.job_description.application.knowledge import delete_knowledge
from caliburn.modules.job_description.application.queries import get_task
from caliburn.modules.job_description.application.tasks.inputs import AddTaskInput
from caliburn.modules.job_description.application.tasks.lifecycle import add_task
from caliburn.modules.job_description.infrastructure.persistence.orm_models import (
    JobDescriptionRow,
)
from caliburn.modules.job_description.infrastructure.persistence.queries import (
    SqlAlchemyJobDescriptionQueries,
)
from tests.integration.content_scenarios import D1, JD, K1, T1
from tests.integration.content_support import factory, read_current, seed_root


@pytest.mark.parametrize("deletion", ["knowledge", "duty"])
@pytest.mark.parametrize("projection", ["overview", "task"])
def test_concurrent_cleanup_cannot_mix_query_snapshots(
    pg_engine: Engine, jd_workspace_id: UUID, deletion: str, projection: str
) -> None:
    original = seed_root(pg_engine, jd_workspace_id)
    reader = SqlAlchemyJobDescriptionQueries(pg_engine)

    def read() -> object:
        if projection == "overview":
            return read_current(pg_engine, workspace_id=jd_workspace_id)
        return get_task(
            workspace_id=jd_workspace_id,
            job_description_id=JD,
            task_id=T1,
            queries=reader,
        )

    before = read()
    ready, release = Event(), Event()

    def hold_snapshot(
        connection: Connection,
        statement: ClauseElement,
        multiparams: Sequence[Mapping[str, object]],
        params: Mapping[str, object],
        execution_options: Mapping[str, object],
        result: CursorResult[tuple[object, ...]],
    ) -> None:
        if (
            not ready.is_set()
            and isinstance(statement, Select)
            and any(
                source.compare(JobDescriptionRow.__table__)
                for source in statement.get_final_froms()
            )
        ):
            ready.set()
            assert release.wait(8), "查詢快照未獲釋放"

    event.listen(pg_engine, "after_execute", hold_snapshot)
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            pending = executor.submit(read)
            try:
                assert ready.wait(5), "查詢未讀到 JD 根版本"
                if deletion == "knowledge":
                    delete_knowledge(
                        workspace_id=jd_workspace_id,
                        job_description_id=JD,
                        knowledge_id=K1,
                        expected_version=original.version,
                        uow_factory=factory(pg_engine),
                    )
                else:
                    delete_duty(
                        workspace_id=jd_workspace_id,
                        job_description_id=JD,
                        duty_id=D1,
                        expected_version=original.version,
                        uow_factory=factory(pg_engine),
                    )
            finally:
                release.set()
            assert pending.result(timeout=5) == before
    finally:
        event.remove(pg_engine, "after_execute", hold_snapshot)
    after = read_current(pg_engine, workspace_id=jd_workspace_id)
    task = get_task(
        workspace_id=jd_workspace_id,
        job_description_id=JD,
        task_id=T1,
        queries=SqlAlchemyJobDescriptionQueries(pg_engine),
    )
    assert task.jd_version == original.version + 1
    if deletion == "knowledge":
        assert task.task.knowledge_ids == ()
        assert all(item.id != K1 for item in after.knowledge)
    else:
        assert task.task.duty_id is None
        assert all(item.id != D1 for item in after.duties)


def test_query_is_read_only_and_pool_connection_is_reset(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    before = seed_root(pg_engine, jd_workspace_id)
    settings: list[tuple[object, object]] = []

    def attempt_write(
        connection: Connection,
        statement: ClauseElement,
        multiparams: Sequence[Mapping[str, object]],
        params: Mapping[str, object],
        execution_options: Mapping[str, object],
    ) -> None:
        if isinstance(statement, Select) and not settings:
            settings.append(
                (
                    connection.exec_driver_sql(
                        "SHOW transaction_isolation"
                    ).scalar_one(),
                    connection.exec_driver_sql(
                        "SHOW transaction_read_only"
                    ).scalar_one(),
                )
            )
            connection.exec_driver_sql("UPDATE job_descriptions SET purpose='不可寫入'")

    event.listen(pg_engine, "before_execute", attempt_write)
    try:
        with pytest.raises(JobDescriptionQueryError):
            read_current(pg_engine, workspace_id=jd_workspace_id)
    finally:
        event.remove(pg_engine, "before_execute", attempt_write)
    assert settings == [("repeatable read", "on")]
    assert read_current(pg_engine, workspace_id=jd_workspace_id) == before
    with pg_engine.connect() as connection:
        assert connection.scalar(text("SHOW transaction_read_only")) == "off"
        assert connection.scalar(text("SHOW transaction_isolation")) == "read committed"
    result = update_job_description(
        workspace_id=jd_workspace_id,
        input=UpdateJobDescriptionInput(
            job_description_id=JD,
            expected_version=before.version,
            purpose="後續合法寫入",
        ),
        uow_factory=factory(pg_engine),
    )
    assert read_current(pg_engine, workspace_id=jd_workspace_id) == result


def test_complete_query_batch_count_does_not_grow_per_task(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    current = seed_root(pg_engine, jd_workspace_id)
    statements: list[ClauseElement] = []

    def capture(
        connection: Connection,
        statement: ClauseElement,
        multiparams: Sequence[Mapping[str, object]],
        params: Mapping[str, object],
        execution_options: Mapping[str, object],
    ) -> None:
        if isinstance(statement, Select):
            statements.append(statement)

    event.listen(pg_engine, "before_execute", capture)
    try:
        read_current(pg_engine, workspace_id=jd_workspace_id)
        first_count = len(statements)
        for name in ("第三任務", "第四任務", "第五任務"):
            current = add_task(
                workspace_id=jd_workspace_id,
                input=AddTaskInput(
                    job_description_id=JD,
                    expected_version=current.version,
                    name=name,
                    outcomes=("自己的成果",),
                    requirements=("自己的要求",),
                ),
                uow_factory=factory(pg_engine),
            )
        statements.clear()
        after = read_current(pg_engine, workspace_id=jd_workspace_id)
        assert len(after.tasks) == 5
        assert len(statements) == first_count
    finally:
        event.remove(pg_engine, "before_execute", capture)
