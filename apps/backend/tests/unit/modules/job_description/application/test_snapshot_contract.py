"""完整 JD 結果只帶單一版本，不再交付寫入封套。"""

from uuid import uuid7

from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.application.job_descriptions import (
    UpdateJobDescriptionInput,
    create_job_description,
    update_job_description,
)
from caliburn.modules.job_description.domain.models.competency_level import (
    CompetencyLevel,
)
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)
from tests.unit.modules.job_description.application.recording_uow import (
    RecordingUnitOfWork,
)


def test_creation_returns_complete_content_with_one_version() -> None:
    unit = RecordingUnitOfWork()
    result = create_job_description(workspace_id=uuid7(), uow_factory=lambda: unit)
    assert isinstance(result, JobDescriptionResult)
    assert result.version == 1
    assert set(type(result).model_fields) == {
        "job_description_id",
        "workspace_id",
        "job_title",
        "organization_unit",
        "reports_to",
        "purpose",
        "baseline_competency_level",
        "duties",
        "tasks",
        "knowledge",
        "skills",
        "collaborations",
        "conditions",
        "citations",
        "version",
    }


def test_ordinary_no_op_returns_the_original_content_and_version() -> None:
    """省略已填的級別仍保留，沒有實質修改時不增加版本。"""
    root = JobDescription(
        id=uuid7(),
        workspace_id=uuid7(),
        purpose="原文",
        baseline_competency_level=CompetencyLevel(value=4),
    )
    unit = RecordingUnitOfWork(root, version=4)
    result = update_job_description(
        workspace_id=root.workspace_id,
        input=UpdateJobDescriptionInput(
            job_description_id=root.id,
            expected_version=4,
            purpose="原文",
        ),
        uow_factory=lambda: unit,
    )
    assert result.purpose == "原文"
    assert result.baseline_competency_level == 4
    assert result.version == 4
    assert unit.committed and unit.closed
