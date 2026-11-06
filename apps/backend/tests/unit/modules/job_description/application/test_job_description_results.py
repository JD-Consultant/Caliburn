"""JD 結果保留明示內容，不推造未載入的集合。"""

from uuid import UUID

from caliburn.modules.job_description.application.content import (
    CollaborationResult,
    JobConditionResult,
)
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.domain.models.collaboration_entry import (
    CollaborationEntry,
)
from caliburn.modules.job_description.domain.models.competency_level import (
    CompetencyLevel,
)
from caliburn.modules.job_description.domain.models.condition_kind import ConditionKind
from caliburn.modules.job_description.domain.models.job_condition import JobCondition
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)


def test_result_preserves_supplied_details_and_original_state() -> None:
    """明示非空集合、原文、級別與版本完整保留，結果不隨原聚合改變。"""
    collaborations = (
        CollaborationResult(id=UUID(int=3), collaborator_name="顧問", scope=None),
        CollaborationResult(id=UUID(int=4), collaborator_name="主管", scope="覆核"),
    )
    conditions = (
        JobConditionResult(
            id=UUID(int=5), kind=ConditionKind.WORK_ENVIRONMENT, text=" 室內 "
        ),
        JobConditionResult(
            id=UUID(int=6), kind=ConditionKind.QUALIFICATION, text="相關經驗"
        ),
    )

    job_description = JobDescription(
        id=UUID(int=1),
        workspace_id=UUID(int=2),
        purpose=" 原文\n ",
        baseline_competency_level=CompetencyLevel(value=4),
        collaborations=tuple(
            CollaborationEntry(
                id=item.id, collaborator_name=item.collaborator_name, scope=item.scope
            )
            for item in collaborations
        ),
        conditions=tuple(
            JobCondition(id=item.id, kind=item.kind, text=item.text)
            for item in conditions
        ),
    )
    result = JobDescriptionResult.from_job_description(
        job_description,
        version=7,
    )
    job_description.set_purpose(purpose="之後的修改")
    job_description.update_collaboration(
        collaboration_id=collaborations[0].id,
        collaborator_name="後改名稱",
        scope="後改範圍",
    )
    job_description.update_condition(condition_id=conditions[0].id, text="後改條件")

    assert result.collaborations == collaborations
    assert result.conditions == conditions
    assert result.purpose == " 原文\n "
    assert result.baseline_competency_level == 4
    assert result.version == 7
