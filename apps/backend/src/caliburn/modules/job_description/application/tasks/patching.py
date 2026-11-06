"""Task 的有界內容修改；只協調聚合方法，不持有交易或 HTTP 動作字串。"""

from typing import assert_never
from uuid import UUID

from caliburn.modules.job_description.application.tasks.inputs import (
    AddOutcomeInput,
    AddRequirementInput,
    CreateAndLinkKnowledgeInput,
    CreateAndLinkSkillInput,
    DeleteOutcomeInput,
    DeleteRequirementInput,
    LinkKnowledgeInput,
    LinkSkillInput,
    MoveKnowledgeReferenceInput,
    MoveOutcomeInput,
    MoveRequirementInput,
    MoveSkillReferenceInput,
    TaskChange,
    UnlinkKnowledgeInput,
    UnlinkSkillInput,
    UpdateOutcomeInput,
    UpdateRequirementInput,
)
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)


def apply_task_changes(
    job_description: JobDescription, *, task_id: UUID, changes: tuple[TaskChange, ...]
) -> None:
    """依輸入次序操作同一工作根，保存及提交由完整 Task 用例負責。"""
    for change in changes:
        match change:
            case AddOutcomeInput():
                job_description.add_outcome(task_id=task_id, text=change.text)
            case AddRequirementInput():
                job_description.add_requirement(
                    task_id=task_id,
                    text=change.text,
                )
            case LinkKnowledgeInput():
                job_description.link_knowledge(task_id=task_id, knowledge_id=change.id)
            case LinkSkillInput():
                job_description.link_skill(task_id=task_id, skill_id=change.id)
            case CreateAndLinkKnowledgeInput():
                knowledge_id = job_description.add_knowledge(
                    name=change.name,
                    description=change.description,
                )
                job_description.link_knowledge(
                    task_id=task_id, knowledge_id=knowledge_id
                )
            case CreateAndLinkSkillInput():
                skill_id = job_description.add_skill(
                    name=change.name,
                    description=change.description,
                )
                job_description.link_skill(task_id=task_id, skill_id=skill_id)
            case UpdateOutcomeInput():
                job_description.update_outcome(
                    task_id=task_id, outcome_id=change.id, text=change.text
                )
            case DeleteOutcomeInput():
                job_description.remove_outcome(task_id=task_id, outcome_id=change.id)
            case MoveOutcomeInput():
                job_description.move_outcome(
                    task_id=task_id, outcome_id=change.id, before_id=change.before_id
                )
            case UpdateRequirementInput():
                job_description.update_requirement(
                    task_id=task_id, requirement_id=change.id, text=change.text
                )
            case DeleteRequirementInput():
                job_description.remove_requirement(
                    task_id=task_id, requirement_id=change.id
                )
            case MoveRequirementInput():
                job_description.move_requirement(
                    task_id=task_id,
                    requirement_id=change.id,
                    before_id=change.before_id,
                )
            case UnlinkKnowledgeInput():
                job_description.unlink_knowledge(
                    task_id=task_id, knowledge_id=change.id
                )
            case UnlinkSkillInput():
                job_description.unlink_skill(task_id=task_id, skill_id=change.id)
            case MoveKnowledgeReferenceInput():
                job_description.move_knowledge_reference(
                    task_id=task_id, knowledge_id=change.id, before_id=change.before_id
                )
            case MoveSkillReferenceInput():
                job_description.move_skill_reference(
                    task_id=task_id, skill_id=change.id, before_id=change.before_id
                )
            case _:
                assert_never(change)
