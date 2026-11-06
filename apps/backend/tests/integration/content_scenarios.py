"""JD 內容寫入能力的原版本保護與可觀察內容；單項變更共用資源修改用例。"""

from collections.abc import Callable
from uuid import UUID

from caliburn.modules.job_description.application import (
    collaborations,
    conditions,
    duties,
    job_descriptions,
    knowledge,
    skills,
)
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.application.persistence import (
    JobDescriptionUnitOfWork,
)
from caliburn.modules.job_description.application.placement import PlacementInput
from caliburn.modules.job_description.application.tasks import (
    lifecycle,
)
from caliburn.modules.job_description.application.tasks.inputs import (
    AddOutcomeInput,
    AddRequirementInput,
    AddTaskInput,
    DeleteOutcomeInput,
    DeleteRequirementInput,
    LinkKnowledgeInput,
    LinkSkillInput,
    MoveKnowledgeReferenceInput,
    MoveOutcomeInput,
    MoveRequirementInput,
    MoveSkillReferenceInput,
    NewDefinitionInput,
    TaskPlacementInput,
    UnlinkKnowledgeInput,
    UnlinkSkillInput,
    UpdateOutcomeInput,
    UpdateRequirementInput,
    UpdateTaskInput,
)
from caliburn.modules.job_description.domain.models.collaboration_entry import (
    CollaborationEntry,
)
from caliburn.modules.job_description.domain.models.condition_kind import ConditionKind
from caliburn.modules.job_description.domain.models.duty import Duty
from caliburn.modules.job_description.domain.models.job_condition import JobCondition
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)
from caliburn.modules.job_description.domain.models.job_task import JobTask
from caliburn.modules.job_description.domain.models.knowledge import Knowledge
from caliburn.modules.job_description.domain.models.skill import Skill
from caliburn.modules.job_description.domain.models.task_outcome import TaskOutcome
from caliburn.modules.job_description.domain.models.task_requirement import (
    TaskRequirement,
)

JD = UUID(int=1)
WORKSPACE = UUID(int=2)
D1, D2, T1, T2, K1, K2, S1, S2, O1, O2, P1, P2, C1, C2, Q1, Q2 = (
    UUID(int=n) for n in range(10, 26)
)


def complete_root(*, workspace_id: UUID = WORKSPACE) -> JobDescription:
    return JobDescription(
        id=JD,
        workspace_id=workspace_id,
        purpose="原目的",
        duties=(
            Duty.create(id=D1, job_description_id=JD, name="職責一"),
            Duty.create(id=D2, job_description_id=JD, name="職責二"),
        ),
        knowledge=(
            Knowledge.create(id=K1, job_description_id=JD, name="知識一"),
            Knowledge.create(id=K2, job_description_id=JD, name="知識二"),
        ),
        skills=(
            Skill.create(id=S1, job_description_id=JD, name="技能一"),
            Skill.create(id=S2, job_description_id=JD, name="技能二"),
        ),
        tasks=(
            JobTask.create(
                id=T1,
                job_description_id=JD,
                name="任務一",
                duty_id=D1,
                outcomes=(
                    TaskOutcome(id=O1, text="成果一"),
                    TaskOutcome(id=O2, text="成果二"),
                ),
                requirements=(
                    TaskRequirement(id=P1, text="要求一"),
                    TaskRequirement(id=P2, text="要求二"),
                ),
                knowledge_ids=(K1,),
                skill_ids=(S1,),
            ),
            JobTask.create(id=T2, job_description_id=JD, name="任務二", duty_id=D1),
        ),
        collaborations=(
            CollaborationEntry(id=C1, collaborator_name="協作一"),
            CollaborationEntry(id=C2, collaborator_name="協作二"),
        ),
        conditions=(
            JobCondition(id=Q1, kind=ConditionKind.QUALIFICATION, text="條件一"),
            JobCondition(id=Q2, kind=ConditionKind.QUALIFICATION, text="條件二"),
        ),
    )


type WriteOperation = Callable[
    [JobDescriptionUnitOfWork, int, UUID], JobDescriptionResult
]
type ContentCheck = Callable[[JobDescriptionResult], bool]
CASES: tuple[tuple[str, WriteOperation, ContentCheck], ...] = (
    (
        "update_jd",
        lambda u, v, w: job_descriptions.update_job_description(
            workspace_id=w,
            input=job_descriptions.UpdateJobDescriptionInput(
                job_description_id=JD, expected_version=v, purpose="新目的"
            ),
            uow_factory=lambda: u,
        ),
        lambda r: r.purpose == "新目的",
    ),
    (
        "add_duty",
        lambda u, v, w: duties.add_duty(
            workspace_id=w,
            job_description_id=JD,
            expected_version=v,
            name="新增",
            scope=" 原文 ",
            uow_factory=lambda: u,
        ),
        lambda r: r.duties[-1].name == "新增" and r.duties[-1].scope == " 原文 ",
    ),
    (
        "update_duty",
        lambda u, v, w: duties.update_duty(
            workspace_id=w,
            input=duties.UpdateDutyInput(
                job_description_id=JD, duty_id=D1, expected_version=v, scope="新內容"
            ),
            uow_factory=lambda: u,
        ),
        lambda r: r.duties[0].scope == "新內容",
    ),
    (
        "move_duty",
        lambda u, v, w: duties.update_duty(
            workspace_id=w,
            input=duties.UpdateDutyInput(
                job_description_id=JD,
                duty_id=D1,
                expected_version=v,
                placement=PlacementInput(before_id=None),
            ),
            uow_factory=lambda: u,
        ),
        lambda r: tuple(x.id for x in r.duties) == (D2, D1),
    ),
    (
        "delete_duty",
        lambda u, v, w: duties.delete_duty(
            workspace_id=w,
            job_description_id=JD,
            duty_id=D1,
            expected_version=v,
            uow_factory=lambda: u,
        ),
        lambda r: tuple(x.id for x in r.duties) == (D2,),
    ),
    (
        "add_knowledge",
        lambda u, v, w: knowledge.add_knowledge(
            workspace_id=w,
            job_description_id=JD,
            expected_version=v,
            name="新增",
            description=" 原文 ",
            uow_factory=lambda: u,
        ),
        lambda r: (
            r.knowledge[-1].name == "新增" and r.knowledge[-1].description == " 原文 "
        ),
    ),
    (
        "update_knowledge",
        lambda u, v, w: knowledge.update_knowledge(
            workspace_id=w,
            input=knowledge.UpdateKnowledgeInput(
                job_description_id=JD,
                knowledge_id=K1,
                expected_version=v,
                description="新內容",
            ),
            uow_factory=lambda: u,
        ),
        lambda r: r.knowledge[0].description == "新內容",
    ),
    (
        "move_knowledge",
        lambda u, v, w: knowledge.update_knowledge(
            workspace_id=w,
            input=knowledge.UpdateKnowledgeInput(
                job_description_id=JD,
                knowledge_id=K1,
                expected_version=v,
                placement=PlacementInput(before_id=None),
            ),
            uow_factory=lambda: u,
        ),
        lambda r: tuple(x.id for x in r.knowledge) == (K2, K1),
    ),
    (
        "delete_knowledge",
        lambda u, v, w: knowledge.delete_knowledge(
            workspace_id=w,
            job_description_id=JD,
            knowledge_id=K1,
            expected_version=v,
            uow_factory=lambda: u,
        ),
        lambda r: tuple(x.id for x in r.knowledge) == (K2,),
    ),
    (
        "add_skill",
        lambda u, v, w: skills.add_skill(
            workspace_id=w,
            job_description_id=JD,
            expected_version=v,
            name="新增",
            description=" 原文 ",
            uow_factory=lambda: u,
        ),
        lambda r: r.skills[-1].name == "新增" and r.skills[-1].description == " 原文 ",
    ),
    (
        "update_skill",
        lambda u, v, w: skills.update_skill(
            workspace_id=w,
            input=skills.UpdateSkillInput(
                job_description_id=JD,
                skill_id=S1,
                expected_version=v,
                description="新內容",
            ),
            uow_factory=lambda: u,
        ),
        lambda r: r.skills[0].description == "新內容",
    ),
    (
        "move_skill",
        lambda u, v, w: skills.update_skill(
            workspace_id=w,
            input=skills.UpdateSkillInput(
                job_description_id=JD,
                skill_id=S1,
                expected_version=v,
                placement=PlacementInput(before_id=None),
            ),
            uow_factory=lambda: u,
        ),
        lambda r: tuple(x.id for x in r.skills) == (S2, S1),
    ),
    (
        "delete_skill",
        lambda u, v, w: skills.delete_skill(
            workspace_id=w,
            job_description_id=JD,
            skill_id=S1,
            expected_version=v,
            uow_factory=lambda: u,
        ),
        lambda r: tuple(x.id for x in r.skills) == (S2,),
    ),
    (
        "add_task",
        lambda u, v, w: lifecycle.add_task(
            workspace_id=w,
            input=AddTaskInput(
                job_description_id=JD,
                expected_version=v,
                name="新增任務",
                outcomes=("成果",),
                requirements=("要求",),
                knowledge=(NewDefinitionInput(name="新知識"),),
                skills=(NewDefinitionInput(name="新技能"),),
            ),
            uow_factory=lambda: u,
        ),
        lambda r: (
            r.tasks[0].name == "新增任務"
            and r.knowledge[-1].name == "新知識"
            and r.skills[-1].name == "新技能"
        ),
    ),
    (
        "update_task",
        lambda u, v, w: lifecycle.update_task(
            workspace_id=w,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=T1,
                expected_version=v,
                description="新描述",
            ),
            uow_factory=lambda: u,
        ),
        lambda r: r.tasks[0].description == "新描述",
    ),
    (
        "delete_task",
        lambda u, v, w: lifecycle.delete_task(
            workspace_id=w,
            job_description_id=JD,
            task_id=T1,
            expected_version=v,
            uow_factory=lambda: u,
        ),
        lambda r: tuple(x.id for x in r.tasks) == (T2,),
    ),
    (
        "move_task",
        lambda u, v, w: lifecycle.update_task(
            workspace_id=w,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=T1,
                expected_version=v,
                placement=TaskPlacementInput(destination_duty_id=D2),
            ),
            uow_factory=lambda: u,
        ),
        lambda r: (
            tuple(x.id for x in r.tasks) == (T2, T1) and r.tasks[-1].duty_id == D2
        ),
    ),
    (
        "add_outcome",
        lambda u, v, w: lifecycle.update_task(
            workspace_id=w,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=T1,
                expected_version=v,
                changes=(AddOutcomeInput(text="新增"),),
            ),
            uow_factory=lambda: u,
        ),
        lambda r: r.tasks[0].outcomes[-1].text == "新增",
    ),
    (
        "update_outcome",
        lambda u, v, w: lifecycle.update_task(
            workspace_id=w,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=T1,
                expected_version=v,
                changes=(UpdateOutcomeInput(id=O1, text="新文字"),),
            ),
            uow_factory=lambda: u,
        ),
        lambda r: r.tasks[0].outcomes[0].text == "新文字",
    ),
    (
        "move_outcome",
        lambda u, v, w: lifecycle.update_task(
            workspace_id=w,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=T1,
                expected_version=v,
                changes=(MoveOutcomeInput(id=O1),),
            ),
            uow_factory=lambda: u,
        ),
        lambda r: tuple(x.id for x in r.tasks[0].outcomes) == (O2, O1),
    ),
    (
        "delete_outcome",
        lambda u, v, w: lifecycle.update_task(
            workspace_id=w,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=T1,
                expected_version=v,
                changes=(DeleteOutcomeInput(id=O1),),
            ),
            uow_factory=lambda: u,
        ),
        lambda r: tuple(x.id for x in r.tasks[0].outcomes) == (O2,),
    ),
    (
        "add_requirement",
        lambda u, v, w: lifecycle.update_task(
            workspace_id=w,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=T1,
                expected_version=v,
                changes=(AddRequirementInput(text="新增"),),
            ),
            uow_factory=lambda: u,
        ),
        lambda r: r.tasks[0].requirements[-1].text == "新增",
    ),
    (
        "update_requirement",
        lambda u, v, w: lifecycle.update_task(
            workspace_id=w,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=T1,
                expected_version=v,
                changes=(UpdateRequirementInput(id=P1, text="新文字"),),
            ),
            uow_factory=lambda: u,
        ),
        lambda r: r.tasks[0].requirements[0].text == "新文字",
    ),
    (
        "move_requirement",
        lambda u, v, w: lifecycle.update_task(
            workspace_id=w,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=T1,
                expected_version=v,
                changes=(MoveRequirementInput(id=P1),),
            ),
            uow_factory=lambda: u,
        ),
        lambda r: tuple(x.id for x in r.tasks[0].requirements) == (P2, P1),
    ),
    (
        "delete_requirement",
        lambda u, v, w: lifecycle.update_task(
            workspace_id=w,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=T1,
                expected_version=v,
                changes=(DeleteRequirementInput(id=P1),),
            ),
            uow_factory=lambda: u,
        ),
        lambda r: tuple(x.id for x in r.tasks[0].requirements) == (P2,),
    ),
    (
        "link_knowledge",
        lambda u, v, w: lifecycle.update_task(
            workspace_id=w,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=T1,
                expected_version=v,
                changes=(LinkKnowledgeInput(id=K2),),
            ),
            uow_factory=lambda: u,
        ),
        lambda r: r.tasks[0].knowledge_ids == (K1, K2),
    ),
    (
        "unlink_knowledge",
        lambda u, v, w: lifecycle.update_task(
            workspace_id=w,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=T1,
                expected_version=v,
                changes=(UnlinkKnowledgeInput(id=K1),),
            ),
            uow_factory=lambda: u,
        ),
        lambda r: r.tasks[0].knowledge_ids == (),
    ),
    (
        "move_knowledge_reference",
        lambda u, v, w: lifecycle.update_task(
            workspace_id=w,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=T1,
                expected_version=v,
                changes=(MoveKnowledgeReferenceInput(id=K1),),
            ),
            uow_factory=lambda: u,
        ),
        lambda r: r.tasks[0].knowledge_ids == (K1,),
    ),
    (
        "link_skill",
        lambda u, v, w: lifecycle.update_task(
            workspace_id=w,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=T1,
                expected_version=v,
                changes=(LinkSkillInput(id=S2),),
            ),
            uow_factory=lambda: u,
        ),
        lambda r: r.tasks[0].skill_ids == (S1, S2),
    ),
    (
        "unlink_skill",
        lambda u, v, w: lifecycle.update_task(
            workspace_id=w,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=T1,
                expected_version=v,
                changes=(UnlinkSkillInput(id=S1),),
            ),
            uow_factory=lambda: u,
        ),
        lambda r: r.tasks[0].skill_ids == (),
    ),
    (
        "move_skill_reference",
        lambda u, v, w: lifecycle.update_task(
            workspace_id=w,
            input=UpdateTaskInput(
                job_description_id=JD,
                task_id=T1,
                expected_version=v,
                changes=(MoveSkillReferenceInput(id=S1),),
            ),
            uow_factory=lambda: u,
        ),
        lambda r: r.tasks[0].skill_ids == (S1,),
    ),
    (
        "add_collaboration",
        lambda u, v, w: collaborations.add_collaboration(
            workspace_id=w,
            job_description_id=JD,
            expected_version=v,
            collaborator_name="新增協作",
            uow_factory=lambda: u,
        ),
        lambda r: r.collaborations[-1].collaborator_name == "新增協作",
    ),
    (
        "update_collaboration",
        lambda u, v, w: collaborations.update_collaboration(
            workspace_id=w,
            input=collaborations.UpdateCollaborationInput(
                job_description_id=JD,
                collaboration_id=C1,
                expected_version=v,
                scope="新範圍",
            ),
            uow_factory=lambda: u,
        ),
        lambda r: r.collaborations[0].scope == "新範圍",
    ),
    (
        "move_collaboration",
        lambda u, v, w: collaborations.update_collaboration(
            workspace_id=w,
            input=collaborations.UpdateCollaborationInput(
                job_description_id=JD,
                collaboration_id=C1,
                expected_version=v,
                placement=PlacementInput(),
            ),
            uow_factory=lambda: u,
        ),
        lambda r: tuple(x.id for x in r.collaborations) == (C2, C1),
    ),
    (
        "delete_collaboration",
        lambda u, v, w: collaborations.delete_collaboration(
            workspace_id=w,
            job_description_id=JD,
            collaboration_id=C1,
            expected_version=v,
            uow_factory=lambda: u,
        ),
        lambda r: tuple(x.id for x in r.collaborations) == (C2,),
    ),
    (
        "add_condition",
        lambda u, v, w: conditions.add_condition(
            workspace_id=w,
            job_description_id=JD,
            expected_version=v,
            kind=ConditionKind.WORK_ENVIRONMENT,
            text="新增條件",
            uow_factory=lambda: u,
        ),
        lambda r: any(x.text == "新增條件" for x in r.conditions),
    ),
    (
        "update_condition",
        lambda u, v, w: conditions.update_condition(
            workspace_id=w,
            input=conditions.UpdateConditionInput(
                job_description_id=JD,
                condition_id=Q1,
                expected_version=v,
                text="新條件",
            ),
            uow_factory=lambda: u,
        ),
        lambda r: r.conditions[0].text == "新條件",
    ),
    (
        "reclassify_condition",
        lambda u, v, w: conditions.update_condition(
            workspace_id=w,
            input=conditions.UpdateConditionInput(
                job_description_id=JD,
                condition_id=Q1,
                expected_version=v,
                kind=ConditionKind.WORK_ENVIRONMENT,
            ),
            uow_factory=lambda: u,
        ),
        lambda r: (
            next(x for x in r.conditions if x.id == Q1).kind
            == ConditionKind.WORK_ENVIRONMENT
        ),
    ),
    (
        "move_condition",
        lambda u, v, w: conditions.update_condition(
            workspace_id=w,
            input=conditions.UpdateConditionInput(
                job_description_id=JD,
                condition_id=Q1,
                expected_version=v,
                placement=PlacementInput(),
            ),
            uow_factory=lambda: u,
        ),
        lambda r: tuple(x.id for x in r.conditions) == (Q2, Q1),
    ),
    (
        "delete_condition",
        lambda u, v, w: conditions.delete_condition(
            workspace_id=w,
            job_description_id=JD,
            condition_id=Q1,
            expected_version=v,
            uow_factory=lambda: u,
        ),
        lambda r: tuple(x.id for x in r.conditions) == (Q2,),
    ),
)
