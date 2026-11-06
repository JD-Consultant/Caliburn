"""複合新增按 K 全組、S 全組、Task、既有占用的契約順序拒絕。"""

import pytest

from caliburn.modules.job_description.application.errors import (
    JobDescriptionNameConflictError,
)
from caliburn.modules.job_description.application.tasks.inputs import (
    AddTaskInput,
    NewDefinitionInput,
)
from caliburn.modules.job_description.application.tasks.lifecycle import add_task
from caliburn.modules.job_description.domain.errors import InvalidNameError
from tests.integration.content_scenarios import JD, complete_root
from tests.unit.modules.job_description.application.recording_uow import (
    RecordingUnitOfWork,
)


@pytest.mark.parametrize(
    "knowledge, skills, task_name, expected",
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
def test_group_validation_precedes_the_next_group_and_existing_name_conflicts(
    knowledge: tuple[NewDefinitionInput, ...],
    skills: tuple[NewDefinitionInput, ...],
    task_name: str,
    expected: type[Exception],
) -> None:
    root = complete_root()
    before = root.model_dump()
    unit = RecordingUnitOfWork(root)
    with pytest.raises(expected):
        add_task(
            workspace_id=root.workspace_id,
            input=AddTaskInput(
                job_description_id=JD,
                expected_version=4,
                name=task_name,
                knowledge=knowledge,
                skills=skills,
            ),
            uow_factory=lambda: unit,
        )
    assert root.model_dump() == before
    assert not unit.committed
