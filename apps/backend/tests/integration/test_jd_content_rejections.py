"""名稱、引用、目標及版本優先序均以公開用例與持久內容驗證。"""

from collections.abc import Callable
from uuid import UUID

import pytest
from sqlalchemy import Engine

from caliburn.modules.job_description.application import (
    collaborations,
    conditions,
    duties,
    job_descriptions,
    knowledge,
    skills,
)
from caliburn.modules.job_description.application.errors import (
    DutyNotFoundError,
    InvalidTaskReferenceError,
    JobDescriptionConcurrencyError,
    JobDescriptionNameConflictError,
    JobDescriptionNotFoundError,
    KnowledgeNotFoundError,
    SkillNotFoundError,
    TaskNotFoundError,
)
from caliburn.modules.job_description.application.persistence import (
    JobDescriptionUnitOfWork,
)
from caliburn.modules.job_description.application.placement import PlacementInput
from caliburn.modules.job_description.application.tasks import (
    lifecycle,
)
from caliburn.modules.job_description.application.tasks.inputs import (
    AddTaskInput,
    DeleteOutcomeInput,
    DeleteRequirementInput,
    ExistingDefinitionInput,
    LinkKnowledgeInput,
    MoveOutcomeInput,
    NewDefinitionInput,
    TaskPlacementInput,
    UnlinkSkillInput,
    UpdateTaskInput,
)
from caliburn.modules.job_description.domain.errors import (
    CollaborationNotFoundError,
    InvalidDefinitionOrderError,
    InvalidJobDescriptionRecordOrderError,
    InvalidNameError,
    InvalidTaskOrderError,
    JobConditionNotFoundError,
    TaskOutcomeNotFoundError,
    TaskRequirementNotFoundError,
)
from tests.integration.content_scenarios import (
    C1,
    D1,
    D2,
    JD,
    K1,
    O1,
    P1,
    Q1,
    S1,
    T1,
    T2,
)
from tests.integration.content_support import factory, read_current, seed_root

type RejectedOperation = Callable[
    [Callable[[], JobDescriptionUnitOfWork], int, UUID], object
]
MISSING = UUID(int=999)

ROOT_IDENTITY_CASES: tuple[tuple[str, RejectedOperation, type[Exception]], ...] = (
    (
        "jd",
        lambda f, v, w: job_descriptions.update_job_description(
            workspace_id=w,
            input=job_descriptions.UpdateJobDescriptionInput(
                job_description_id=MISSING,
                expected_version=v,
                baseline_competency_level=99,
            ),
            uow_factory=f,
        ),
        JobDescriptionNotFoundError,
    ),
    (
        "duty",
        lambda f, v, w: duties.update_duty(
            workspace_id=w,
            input=duties.UpdateDutyInput(
                job_description_id=JD, duty_id=MISSING, expected_version=v, name=""
            ),
            uow_factory=f,
        ),
        DutyNotFoundError,
    ),
    (
        "knowledge",
        lambda f, v, w: knowledge.update_knowledge(
            workspace_id=w,
            input=knowledge.UpdateKnowledgeInput(
                job_description_id=JD, knowledge_id=MISSING, expected_version=v, name=""
            ),
            uow_factory=f,
        ),
        KnowledgeNotFoundError,
    ),
    (
        "skill",
        lambda f, v, w: skills.update_skill(
            workspace_id=w,
            input=skills.UpdateSkillInput(
                job_description_id=JD, skill_id=MISSING, expected_version=v, name=""
            ),
            uow_factory=f,
        ),
        SkillNotFoundError,
    ),
    (
        "task",
        lambda f, v, w: lifecycle.update_task(
            workspace_id=w,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=MISSING,
                expected_version=v,
                name="",
                competency_level=99,
            ),
            uow_factory=f,
        ),
        TaskNotFoundError,
    ),
    (
        "collaboration",
        lambda f, v, w: collaborations.update_collaboration(
            workspace_id=w,
            input=collaborations.UpdateCollaborationInput(
                job_description_id=JD,
                collaboration_id=Q1,
                expected_version=v,
                placement=PlacementInput(before_id=Q1),
            ),
            uow_factory=f,
        ),
        CollaborationNotFoundError,
    ),
    (
        "condition",
        lambda f, v, w: conditions.update_condition(
            workspace_id=w,
            input=conditions.UpdateConditionInput(
                job_description_id=JD,
                condition_id=C1,
                expected_version=v,
                placement=PlacementInput(before_id=C1),
            ),
            uow_factory=f,
        ),
        JobConditionNotFoundError,
    ),
)

TASK_CHANGE_IDENTITY_CASES: tuple[
    tuple[str, RejectedOperation, type[Exception]], ...
] = (
    (
        "outcome",
        lambda f, v, w: lifecycle.update_task(
            workspace_id=w,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=T1,
                expected_version=v,
                changes=(DeleteOutcomeInput(id=P1),),
            ),
            uow_factory=f,
        ),
        TaskOutcomeNotFoundError,
    ),
    (
        "requirement",
        lambda f, v, w: lifecycle.update_task(
            workspace_id=w,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=T1,
                expected_version=v,
                changes=(DeleteRequirementInput(id=O1),),
            ),
            uow_factory=f,
        ),
        TaskRequirementNotFoundError,
    ),
    (
        "knowledge_link",
        lambda f, v, w: lifecycle.update_task(
            workspace_id=w,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=T1,
                expected_version=v,
                changes=(LinkKnowledgeInput(id=S1),),
            ),
            uow_factory=f,
        ),
        InvalidTaskReferenceError,
    ),
    (
        "skill_unlink",
        lambda f, v, w: lifecycle.update_task(
            workspace_id=w,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=T1,
                expected_version=v,
                changes=(UnlinkSkillInput(id=K1),),
            ),
            uow_factory=f,
        ),
        InvalidTaskReferenceError,
    ),
)


@pytest.mark.parametrize(
    "operation, expected",
    [pytest.param(op, error, id=name) for name, op, error in ROOT_IDENTITY_CASES],
)
def test_resource_identity_precedes_stale_version_and_invalid_content(
    pg_engine: Engine,
    jd_workspace_id: UUID,
    operation: RejectedOperation,
    expected: type[Exception],
) -> None:
    before = seed_root(pg_engine, jd_workspace_id)
    with pytest.raises(expected):
        operation(factory(pg_engine), before.version + 10, jd_workspace_id)
    assert read_current(pg_engine, workspace_id=jd_workspace_id) == before


@pytest.mark.parametrize(
    "operation, expected",
    [
        pytest.param(op, error, id=name)
        for name, op, error in TASK_CHANGE_IDENTITY_CASES
    ],
)
def test_task_patch_version_precedes_child_identity_and_current_version_checks_child(
    pg_engine: Engine,
    jd_workspace_id: UUID,
    operation: RejectedOperation,
    expected: type[Exception],
) -> None:
    """Task PATCH 先核整次原版本，再依序驗 changes 的子項身分。"""
    before = seed_root(pg_engine, jd_workspace_id)
    with pytest.raises(JobDescriptionConcurrencyError):
        operation(factory(pg_engine), before.version + 10, jd_workspace_id)
    with pytest.raises(expected):
        operation(factory(pg_engine), before.version, jd_workspace_id)
    assert read_current(pg_engine, workspace_id=jd_workspace_id) == before


@pytest.mark.parametrize("kind", ["duty", "knowledge", "skill", "task"])
@pytest.mark.parametrize("name", ["", " \t\n", "x" * 256])
def test_invalid_named_content_is_rejected_without_partial_save(
    pg_engine: Engine, jd_workspace_id: UUID, kind: str, name: str
) -> None:
    before = seed_root(pg_engine, jd_workspace_id)
    operations: dict[str, RejectedOperation] = {
        "duty": lambda f, v, w: duties.add_duty(
            workspace_id=w,
            job_description_id=JD,
            expected_version=v,
            name=name,
            uow_factory=f,
        ),
        "knowledge": lambda f, v, w: knowledge.add_knowledge(
            workspace_id=w,
            job_description_id=JD,
            expected_version=v,
            name=name,
            uow_factory=f,
        ),
        "skill": lambda f, v, w: skills.add_skill(
            workspace_id=w,
            job_description_id=JD,
            expected_version=v,
            name=name,
            uow_factory=f,
        ),
        "task": lambda f, v, w: lifecycle.add_task(
            workspace_id=w,
            input=AddTaskInput(
                job_description_id=JD,
                expected_version=v,
                name=name,
                knowledge=(NewDefinitionInput(name="候選知識"),),
            ),
            uow_factory=f,
        ),
    }
    with pytest.raises(InvalidNameError):
        operations[kind](factory(pg_engine), before.version, jd_workspace_id)
    assert read_current(pg_engine, workspace_id=jd_workspace_id) == before


@pytest.mark.parametrize("kind", ["duty", "knowledge", "skill", "task"])
def test_exact_name_conflict_rejects_but_255_codepoints_are_stored(
    pg_engine: Engine, jd_workspace_id: UUID, kind: str
) -> None:
    before = seed_root(pg_engine, jd_workspace_id)
    creators: dict[str, Callable[[str, int], object]] = {
        "duty": lambda name, version: duties.add_duty(
            workspace_id=jd_workspace_id,
            job_description_id=JD,
            expected_version=version,
            name=name,
            uow_factory=factory(pg_engine),
        ),
        "knowledge": lambda name, version: knowledge.add_knowledge(
            workspace_id=jd_workspace_id,
            job_description_id=JD,
            expected_version=version,
            name=name,
            uow_factory=factory(pg_engine),
        ),
        "skill": lambda name, version: skills.add_skill(
            workspace_id=jd_workspace_id,
            job_description_id=JD,
            expected_version=version,
            name=name,
            uow_factory=factory(pg_engine),
        ),
        "task": lambda name, version: lifecycle.add_task(
            workspace_id=jd_workspace_id,
            input=AddTaskInput(
                job_description_id=JD, expected_version=version, name=name
            ),
            uow_factory=factory(pg_engine),
        ),
    }
    create = creators[kind]
    create("Straße", before.version)
    current = read_current(pg_engine, workspace_id=jd_workspace_id)
    with pytest.raises(JobDescriptionNameConflictError):
        create(" Straße ", current.version)
    assert read_current(pg_engine, workspace_id=jd_workspace_id) == current
    create("界" * 255, current.version)
    assert (
        read_current(pg_engine, workspace_id=jd_workspace_id).version
        == current.version + 1
    )


@pytest.mark.parametrize("reference", ["duty", "knowledge", "skill"])
def test_task_creation_rejects_missing_or_wrong_kind_references_atomically(
    pg_engine: Engine, jd_workspace_id: UUID, reference: str
) -> None:
    before = seed_root(pg_engine, jd_workspace_id)
    inputs = {
        "duty": AddTaskInput(
            job_description_id=JD,
            expected_version=before.version,
            name="新任務",
            duty_id=K1,
            skills=(NewDefinitionInput(name="新技能"),),
        ),
        "knowledge": AddTaskInput(
            job_description_id=JD,
            expected_version=before.version,
            name="新任務",
            knowledge=(
                ExistingDefinitionInput(id=S1),
                NewDefinitionInput(name="新知識"),
            ),
        ),
        "skill": AddTaskInput(
            job_description_id=JD,
            expected_version=before.version,
            name="新任務",
            skills=(ExistingDefinitionInput(id=K1), NewDefinitionInput(name="新技能")),
        ),
    }
    with pytest.raises(InvalidTaskReferenceError):
        lifecycle.add_task(
            workspace_id=jd_workspace_id,
            input=inputs[reference],
            uow_factory=factory(pg_engine),
        )
    assert read_current(pg_engine, workspace_id=jd_workspace_id) == before


@pytest.mark.parametrize(
    "operation, expected",
    [
        (
            lambda f, v, w: duties.update_duty(
                workspace_id=w,
                input=duties.UpdateDutyInput(
                    job_description_id=JD,
                    duty_id=D1,
                    expected_version=v,
                    placement=PlacementInput(before_id=D1),
                ),
                uow_factory=f,
            ),
            InvalidDefinitionOrderError,
        ),
        (
            lambda f, v, w: lifecycle.update_task(
                workspace_id=w,
                input=UpdateTaskInput(
                    job_description_id=JD,
                    task_id=T1,
                    expected_version=v,
                    placement=TaskPlacementInput(destination_duty_id=D2, before_id=T2),
                ),
                uow_factory=f,
            ),
            InvalidTaskOrderError,
        ),
        (
            lambda f, v, w: lifecycle.update_task(
                workspace_id=w,
                input=UpdateTaskInput(
                    job_description_id=JD,
                    task_id=T1,
                    expected_version=v,
                    changes=(MoveOutcomeInput(id=O1, before_id=P1),),
                ),
                uow_factory=f,
            ),
            InvalidTaskOrderError,
        ),
        (
            lambda f, v, w: collaborations.update_collaboration(
                workspace_id=w,
                input=collaborations.UpdateCollaborationInput(
                    job_description_id=JD,
                    collaboration_id=C1,
                    expected_version=v,
                    placement=PlacementInput(before_id=Q1),
                ),
                uow_factory=f,
            ),
            InvalidJobDescriptionRecordOrderError,
        ),
        (
            lambda f, v, w: conditions.update_condition(
                workspace_id=w,
                input=conditions.UpdateConditionInput(
                    job_description_id=JD,
                    condition_id=Q1,
                    expected_version=v,
                    placement=PlacementInput(before_id=C1),
                ),
                uow_factory=f,
            ),
            InvalidJobDescriptionRecordOrderError,
        ),
    ],
)
def test_stale_version_precedes_invalid_anchor_then_current_version_rejects_anchor(
    pg_engine: Engine,
    jd_workspace_id: UUID,
    operation: RejectedOperation,
    expected: type[Exception],
) -> None:
    before = seed_root(pg_engine, jd_workspace_id)
    with pytest.raises(JobDescriptionConcurrencyError):
        operation(factory(pg_engine), before.version + 10, jd_workspace_id)
    with pytest.raises(expected):
        operation(factory(pg_engine), before.version, jd_workspace_id)
    assert read_current(pg_engine, workspace_id=jd_workspace_id) == before


@pytest.mark.parametrize(
    "new_knowledge, new_skills, task_name, expected",
    [
        (
            (NewDefinitionInput(name="同名"), NewDefinitionInput(name="同名")),
            (NewDefinitionInput(name=""),),
            "任務",
            JobDescriptionNameConflictError,
        ),
        (
            (),
            (NewDefinitionInput(name="同名"), NewDefinitionInput(name="同名")),
            "",
            JobDescriptionNameConflictError,
        ),
        (
            (NewDefinitionInput(name="知識一"),),
            (NewDefinitionInput(name=""),),
            "任務",
            InvalidNameError,
        ),
    ],
)
def test_mixed_definition_failures_follow_group_priority_without_saving(
    pg_engine: Engine,
    jd_workspace_id: UUID,
    new_knowledge: tuple[NewDefinitionInput, ...],
    new_skills: tuple[NewDefinitionInput, ...],
    task_name: str,
    expected: type[Exception],
) -> None:
    before = seed_root(pg_engine, jd_workspace_id)
    with pytest.raises(expected):
        lifecycle.add_task(
            workspace_id=jd_workspace_id,
            input=AddTaskInput(
                job_description_id=JD,
                expected_version=before.version,
                name=task_name,
                knowledge=new_knowledge,
                skills=new_skills,
            ),
            uow_factory=factory(pg_engine),
        )
    assert read_current(pg_engine, workspace_id=jd_workspace_id) == before
