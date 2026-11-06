"""六個公開查詢的完整內容、同 JD 隔離與持久版本投影。"""

from collections.abc import Callable
from uuid import UUID, uuid7

import pytest
from sqlalchemy import Engine

from caliburn.modules.job_description.application import queries
from caliburn.modules.job_description.application.errors import (
    DutyNotFoundError,
    JobDescriptionNotFoundError,
    KnowledgeNotFoundError,
    SkillNotFoundError,
    TaskNotFoundError,
)
from caliburn.modules.job_description.application.job_descriptions import (
    create_job_description,
)
from caliburn.modules.job_description.infrastructure.persistence.queries import (
    SqlAlchemyJobDescriptionQueries,
)
from tests.integration.content_scenarios import D1, JD, K1, S1, T1
from tests.integration.content_support import factory, seed_root


def test_all_six_queries_share_the_same_committed_jd_version_and_contents(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    current = seed_root(pg_engine, jd_workspace_id)
    reader = SqlAlchemyJobDescriptionQueries(pg_engine)
    assert (
        queries.get_job_description(
            workspace_id=jd_workspace_id, job_description_id=JD, queries=reader
        )
        == current
    )
    assert (
        queries.find_job_description_by_workspace(
            workspace_id=jd_workspace_id, queries=reader
        )
        == current
    )
    task = queries.get_task(
        workspace_id=jd_workspace_id, job_description_id=JD, task_id=T1, queries=reader
    )
    duty = queries.get_duty(
        workspace_id=jd_workspace_id, job_description_id=JD, duty_id=D1, queries=reader
    )
    knowledge = queries.get_knowledge(
        workspace_id=jd_workspace_id,
        job_description_id=JD,
        knowledge_id=K1,
        queries=reader,
    )
    skill = queries.get_skill(
        workspace_id=jd_workspace_id, job_description_id=JD, skill_id=S1, queries=reader
    )
    assert task.task == current.tasks[0]
    assert duty.duty == current.duties[0]
    assert knowledge.knowledge == current.knowledge[0]
    assert skill.skill == current.skills[0]
    for item in (task, duty, knowledge, skill):
        assert item.jd_version == current.version
        assert item.job_description_id == JD


def test_empty_and_absent_jd_are_distinct(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    reader = SqlAlchemyJobDescriptionQueries(pg_engine)
    assert (
        queries.find_job_description_by_workspace(
            workspace_id=jd_workspace_id, queries=reader
        )
        is None
    )
    with pytest.raises(JobDescriptionNotFoundError):
        queries.get_job_description(
            workspace_id=jd_workspace_id, job_description_id=uuid7(), queries=reader
        )
    result = create_job_description(
        workspace_id=jd_workspace_id, uow_factory=factory(pg_engine)
    )
    current = result
    assert (
        queries.find_job_description_by_workspace(
            workspace_id=jd_workspace_id, queries=reader
        )
        == current
    )
    assert current.tasks == () and current.duties == ()
    assert current.knowledge == () and current.skills == ()


@pytest.mark.parametrize(
    "read, expected",
    [
        (
            lambda reader, identity, w: queries.get_task(
                workspace_id=w, job_description_id=identity, task_id=T1, queries=reader
            ),
            TaskNotFoundError,
        ),
        (
            lambda reader, identity, w: queries.get_duty(
                workspace_id=w, job_description_id=identity, duty_id=D1, queries=reader
            ),
            DutyNotFoundError,
        ),
        (
            lambda reader, identity, w: queries.get_knowledge(
                workspace_id=w,
                job_description_id=identity,
                knowledge_id=K1,
                queries=reader,
            ),
            KnowledgeNotFoundError,
        ),
        (
            lambda reader, identity, w: queries.get_skill(
                workspace_id=w, job_description_id=identity, skill_id=S1, queries=reader
            ),
            SkillNotFoundError,
        ),
    ],
)
def test_child_query_never_returns_another_jds_entity(
    pg_engine: Engine,
    jd_workspace_id: UUID,
    read: Callable[[SqlAlchemyJobDescriptionQueries, UUID, UUID], object],
    expected: type[Exception],
) -> None:
    seed_root(pg_engine, jd_workspace_id)
    with pytest.raises(expected):
        read(SqlAlchemyJobDescriptionQueries(pg_engine), uuid7(), jd_workspace_id)
