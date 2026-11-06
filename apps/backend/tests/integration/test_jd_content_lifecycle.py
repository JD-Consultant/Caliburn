"""完整內容編修旅程保留文字、引用順序、清理政策與不變更語意。"""

from collections.abc import Callable
from uuid import UUID

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from caliburn.modules.job_description.application import (
    collaborations,
    conditions,
    duties,
    job_descriptions,
    knowledge,
    skills,
)
from caliburn.modules.job_description.application.errors import (
    InvalidTaskReferenceError,
    JobDescriptionConcurrencyError,
)
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.application.tasks import (
    lifecycle,
)
from caliburn.modules.job_description.application.tasks.inputs import (
    AddTaskInput,
    ExistingDefinitionInput,
    LinkKnowledgeInput,
    NewDefinitionInput,
    UnlinkKnowledgeInput,
    UpdateOutcomeInput,
    UpdateTaskInput,
)
from caliburn.modules.job_description.domain.errors import InvalidCompetencyLevelError
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.content_scenarios import (
    C1,
    D1,
    JD,
    K1,
    K2,
    O1,
    P1,
    Q1,
    S1,
    T1,
    T2,
)
from tests.integration.content_support import factory, read_current, seed_root


def test_mixed_new_and_existing_references_preserve_input_order_and_created_identities(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    before = seed_root(pg_engine, jd_workspace_id)
    result = lifecycle.add_task(
        workspace_id=jd_workspace_id,
        input=AddTaskInput(
            job_description_id=JD,
            expected_version=before.version,
            name=" 完整新任務 ",
            description=" 原文\n ",
            competency_level=6,
            outcomes=("同文", "同文"),
            requirements=("要求",),
            knowledge=(
                ExistingDefinitionInput(id=K2),
                NewDefinitionInput(name="新知識"),
                ExistingDefinitionInput(id=K1),
                ExistingDefinitionInput(id=K2),
            ),
            skills=(NewDefinitionInput(name="新技能"), ExistingDefinitionInput(id=S1)),
        ),
        uow_factory=factory(pg_engine),
    )
    current = result
    task = next(item for item in current.tasks if item.name == "完整新任務")
    assert task.description == " 原文\n "
    assert task.competency_level == 6
    assert task.knowledge_ids == (K2, current.knowledge[-1].id, K1)
    assert task.skill_ids == (current.skills[-1].id, S1)
    assert task.outcomes[0].text == task.outcomes[1].text == "同文"
    assert task.outcomes[0].id != task.outcomes[1].id
    created_ids = {
        task.id,
        *(item.id for item in task.outcomes),
        *(item.id for item in task.requirements),
        current.knowledge[-1].id,
        current.skills[-1].id,
    }
    assert len(created_ids) == 6
    assert all(identity.version == 7 for identity in created_ids)
    assert read_current(pg_engine, workspace_id=jd_workspace_id) == current


def test_duty_and_definition_deletion_preserve_task_content_and_order(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    current = seed_root(pg_engine, jd_workspace_id)
    current = lifecycle.add_task(
        workspace_id=jd_workspace_id,
        input=AddTaskInput(
            job_description_id=JD, expected_version=current.version, name="原未分類"
        ),
        uow_factory=factory(pg_engine),
    )
    unclassified = current.tasks[0].id
    current = duties.delete_duty(
        workspace_id=jd_workspace_id,
        job_description_id=JD,
        duty_id=D1,
        expected_version=current.version,
        uow_factory=factory(pg_engine),
    )
    assert tuple(item.id for item in current.tasks) == (unclassified, T1, T2)
    assert all(item.duty_id is None for item in current.tasks)
    task = next(item for item in current.tasks if item.id == T1)
    assert task.outcomes[0].id == O1 and task.requirements[0].id == P1
    assert task.knowledge_ids == (K1,) and task.skill_ids == (S1,)
    current = knowledge.delete_knowledge(
        workspace_id=jd_workspace_id,
        job_description_id=JD,
        knowledge_id=K1,
        expected_version=current.version,
        uow_factory=factory(pg_engine),
    )
    task = next(item for item in current.tasks if item.id == T1)
    assert task.knowledge_ids == ()
    assert task.skill_ids == (S1,)
    current = lifecycle.delete_task(
        workspace_id=jd_workspace_id,
        job_description_id=JD,
        task_id=T1,
        expected_version=current.version,
        uow_factory=factory(pg_engine),
    )
    assert tuple(item.id for item in current.tasks) == (unclassified, T2)
    assert current.skills[0].id == S1
    assert current.knowledge[0].id == K2
    assert read_current(pg_engine, workspace_id=jd_workspace_id) == current
    with pg_engine.connect() as connection:
        for table in (
            "task_outcomes",
            "task_requirements",
            "task_knowledge",
            "task_skills",
        ):
            assert (
                connection.scalar(
                    text(f"SELECT count(*) FROM {table} WHERE task_id=:id"), {"id": T1}
                )
                == 0
            )


def test_nullable_patch_clears_only_explicit_fields_and_invalid_level_is_atomic(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    current = seed_root(pg_engine, jd_workspace_id)
    current = job_descriptions.update_job_description(
        workspace_id=jd_workspace_id,
        input=job_descriptions.UpdateJobDescriptionInput(
            job_description_id=JD,
            expected_version=current.version,
            job_title="職稱",
            organization_unit="部門",
            reports_to="主管",
            baseline_competency_level=3,
        ),
        uow_factory=factory(pg_engine),
    )
    with pytest.raises(InvalidCompetencyLevelError):
        job_descriptions.update_job_description(
            workspace_id=jd_workspace_id,
            input=job_descriptions.UpdateJobDescriptionInput(
                job_description_id=JD,
                expected_version=current.version,
                purpose="不可部分保存",
                baseline_competency_level=7,
            ),
            uow_factory=factory(pg_engine),
        )
    assert read_current(pg_engine, workspace_id=jd_workspace_id) == current
    cleared = job_descriptions.update_job_description(
        workspace_id=jd_workspace_id,
        input=job_descriptions.UpdateJobDescriptionInput(
            job_description_id=JD,
            expected_version=current.version,
            purpose=None,
            baseline_competency_level=None,
        ),
        uow_factory=factory(pg_engine),
    )
    assert cleared.purpose is None and cleared.baseline_competency_level is None
    assert (cleared.job_title, cleared.organization_unit, cleared.reports_to) == (
        "職稱",
        "部門",
        "主管",
    )
    changed = lifecycle.update_task(
        workspace_id=jd_workspace_id,
        input=UpdateTaskInput(
            job_description_id=JD,
            task_id=T1,
            expected_version=cleared.version,
            description="保留",
            competency_level=4,
        ),
        uow_factory=factory(pg_engine),
    )
    cleared_task = lifecycle.update_task(
        workspace_id=jd_workspace_id,
        input=UpdateTaskInput(
            job_description_id=JD,
            task_id=T1,
            expected_version=changed.version,
            description=None,
        ),
        uow_factory=factory(pg_engine),
    ).tasks[0]
    assert cleared_task.description is None
    assert cleared_task.competency_level == 4
    assert cleared_task.name == "任務一"


def test_noop_operations_preserve_content_and_version_but_reject_stale_version(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    current = seed_root(pg_engine, jd_workspace_id)
    operations: tuple[Callable[[int], JobDescriptionResult], ...] = (
        lambda version: job_descriptions.update_job_description(
            workspace_id=jd_workspace_id,
            input=job_descriptions.UpdateJobDescriptionInput(
                job_description_id=JD, expected_version=version, purpose="原目的"
            ),
            uow_factory=factory(pg_engine),
        ),
        lambda version: duties.update_duty(
            workspace_id=jd_workspace_id,
            input=duties.UpdateDutyInput(
                job_description_id=JD, duty_id=D1, expected_version=version, scope=None
            ),
            uow_factory=factory(pg_engine),
        ),
        lambda version: knowledge.update_knowledge(
            workspace_id=jd_workspace_id,
            input=knowledge.UpdateKnowledgeInput(
                job_description_id=JD,
                knowledge_id=K1,
                expected_version=version,
                description=None,
            ),
            uow_factory=factory(pg_engine),
        ),
        lambda version: skills.update_skill(
            workspace_id=jd_workspace_id,
            input=skills.UpdateSkillInput(
                job_description_id=JD,
                skill_id=S1,
                expected_version=version,
                description=None,
            ),
            uow_factory=factory(pg_engine),
        ),
        lambda version: lifecycle.update_task(
            workspace_id=jd_workspace_id,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=T1,
                expected_version=version,
                name="任務一",
            ),
            uow_factory=factory(pg_engine),
        ),
        lambda version: lifecycle.update_task(
            workspace_id=jd_workspace_id,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=T1,
                expected_version=version,
                changes=(LinkKnowledgeInput(id=K1),),
            ),
            uow_factory=factory(pg_engine),
        ),
        lambda version: lifecycle.update_task(
            workspace_id=jd_workspace_id,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=T1,
                expected_version=version,
                changes=(UnlinkKnowledgeInput(id=K2),),
            ),
            uow_factory=factory(pg_engine),
        ),
        lambda version: lifecycle.update_task(
            workspace_id=jd_workspace_id,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=T1,
                expected_version=version,
                changes=(UpdateOutcomeInput(id=O1, text="成果一"),),
            ),
            uow_factory=factory(pg_engine),
        ),
        lambda version: collaborations.update_collaboration(
            workspace_id=jd_workspace_id,
            input=collaborations.UpdateCollaborationInput(
                job_description_id=JD,
                collaboration_id=C1,
                expected_version=version,
                scope=None,
            ),
            uow_factory=factory(pg_engine),
        ),
        lambda version: conditions.update_condition(
            workspace_id=jd_workspace_id,
            input=conditions.UpdateConditionInput(
                job_description_id=JD,
                condition_id=Q1,
                expected_version=version,
                text="條件一",
            ),
            uow_factory=factory(pg_engine),
        ),
    )
    for operation in operations:
        result = operation(current.version)
        assert result == current
        assert result.version == current.version
        with pytest.raises(JobDescriptionConcurrencyError):
            operation(current.version + 10)
    assert read_current(pg_engine, workspace_id=jd_workspace_id) == current


def test_names_can_repeat_across_jds_but_cross_jd_references_cannot_be_saved(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    first = seed_root(pg_engine, jd_workspace_id)
    sessions = create_session_factory(pg_engine)
    workspace = WorkspaceService(
        lambda: SqlAlchemyWorkspaceUnitOfWork(sessions)
    ).create(interviewee_name="另一位受訪者")
    second = job_descriptions.create_job_description(
        workspace_id=workspace.workspace_id, uow_factory=factory(pg_engine)
    )
    second = lifecycle.add_task(
        workspace_id=workspace.workspace_id,
        input=AddTaskInput(
            job_description_id=second.job_description_id,
            expected_version=second.version,
            name="任務一",
            knowledge=(NewDefinitionInput(name="知識一"),),
        ),
        uow_factory=factory(pg_engine),
    )
    foreign_knowledge = second.knowledge[0].id
    with pytest.raises(InvalidTaskReferenceError):
        lifecycle.update_task(
            workspace_id=jd_workspace_id,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=T1,
                expected_version=first.version,
                changes=(LinkKnowledgeInput(id=foreign_knowledge),),
            ),
            uow_factory=factory(pg_engine),
        )
    with pg_engine.connect() as connection:
        connection.execute(
            text(
                "UPDATE task_knowledge SET knowledge_id=:knowledge_id "
                "WHERE task_id=:task_id"
            ),
            {"knowledge_id": foreign_knowledge, "task_id": T1},
        )
        with pytest.raises(IntegrityError):
            connection.commit()
        connection.rollback()
    assert read_current(pg_engine, workspace_id=jd_workspace_id) == first
    assert (
        read_current(
            pg_engine,
            workspace_id=workspace.workspace_id,
            job_description_id=second.job_description_id,
        )
        == second
    )
