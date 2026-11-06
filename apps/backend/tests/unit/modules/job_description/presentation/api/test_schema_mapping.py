"""HTTP 的 task union 與回覆映射覆蓋真正跨層格式差異。"""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from caliburn.modules.job_description.application.content import (
    CollaborationResult,
    DutyResult,
    JobConditionResult,
    KnowledgeResult,
    SkillResult,
    TaskResult,
    TaskTextResult,
)
from caliburn.modules.job_description.application.history.results import (
    CollectionDifference,
    FieldDifference,
    ItemDifference,
    JobDescriptionDifference,
    JobDescriptionHistoryResult,
)
from caliburn.modules.job_description.application.history_types import (
    HistoryEntry,
    HistoryPage,
)
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.application.tasks.inputs import (
    ExistingDefinitionInput,
    NewDefinitionInput,
)
from caliburn.modules.job_description.domain.models.condition_kind import ConditionKind
from caliburn.modules.job_description.presentation.api.schemas.content import (
    AddConditionRequest,
    JobDescriptionResponse,
)
from caliburn.modules.job_description.presentation.api.schemas.history import (
    HistoryPageResponse,
    HistoryResponse,
    JobDescriptionDifferenceResponse,
    RestoreJobDescriptionRequest,
)
from caliburn.modules.job_description.presentation.api.schemas.tasks import (
    AddTaskRequest,
    TaskPlacementRequest,
)

JD_ID = UUID("00112233-4455-6677-8899-aabbccddeeff")
DUTY_ID = UUID("00112233-4455-6677-8899-aabbccddee01")
TASK_ID = UUID("00112233-4455-6677-8899-aabbccddee02")
KNOWLEDGE_ID = UUID("00112233-4455-6677-8899-aabbccddee03")
SKILL_ID = UUID("00112233-4455-6677-8899-aabbccddee04")


def test_add_task_maps_ordered_union_and_lists_to_application_inputs() -> None:
    request = AddTaskRequest.model_validate(
        {
            "expected_version": 1.0,
            "correlation_id": "run-1",
            "name": "任務",
            "description": "原文",
            "duty_id": str(DUTY_ID),
            "competency_level": 2.0,
            "outcomes": ["成果一", "成果二"],
            "requirements": ["要求"],
            "knowledge": [
                {"kind": "existing", "id": str(KNOWLEDGE_ID)},
                {"kind": "new", "name": "新知識", "description": None},
            ],
            "skills": [{"kind": "new", "name": "新技能", "description": "說明"}],
        }
    )
    result = request.to_application(JD_ID)

    assert result.job_description_id == JD_ID
    assert result.expected_version == 1
    assert result.correlation_id == "run-1"
    assert result.name == "任務"
    assert result.description == "原文"
    assert result.duty_id == DUTY_ID
    assert result.competency_level == 2
    assert result.outcomes == ("成果一", "成果二")
    assert result.requirements == ("要求",)
    assert result.knowledge == (
        ExistingDefinitionInput(id=KNOWLEDGE_ID),
        NewDefinitionInput(name="新知識", description=None),
    )
    assert result.skills == (NewDefinitionInput(name="新技能", description="說明"),)


@pytest.mark.parametrize(
    "item",
    [
        {"id": str(KNOWLEDGE_ID)},
        {"kind": "unknown", "id": str(KNOWLEDGE_ID)},
        {"kind": "existing", "id": str(KNOWLEDGE_ID), "name": "unexpected"},
        {"kind": "new", "id": str(KNOWLEDGE_ID), "name": "unexpected"},
        {"kind": "new", "name": " "},
        {"kind": "new", "name": "知識", "description": "\x00"},
    ],
)
def test_task_definition_union_rejects_missing_unknown_or_ambiguous_tag(
    item: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        AddTaskRequest.model_validate(
            {"expected_version": 1, "name": "任務", "knowledge": [item]}
        )


def test_task_definition_schema_exposes_discriminator_and_exclusive_shapes() -> None:
    schema = AddTaskRequest.model_json_schema()
    union = schema["properties"]["knowledge"]["items"]
    assert union["discriminator"]["propertyName"] == "kind"
    assert set(union["discriminator"]["mapping"]) == {"existing", "new"}
    assert len(union["oneOf"]) == 2
    for variant in union["oneOf"]:
        definition = schema["$defs"][variant["$ref"].rsplit("/", 1)[-1]]
        assert definition["additionalProperties"] is False
        assert "kind" in definition["required"]


def test_move_task_requires_destination_but_explicit_null_unclassifies() -> None:
    with pytest.raises(ValidationError):
        TaskPlacementRequest.model_validate({})
    request = TaskPlacementRequest.model_validate({"destination_duty_id": None})
    assert request.destination_duty_id is None
    assert request.before_id is None
    assert "destination_duty_id" in TaskPlacementRequest.model_json_schema()["required"]


def test_condition_kind_is_internal_enum_after_wire_validation() -> None:
    request = AddConditionRequest.model_validate(
        {"expected_version": 1, "kind": "qualification", "text": "條件"}
    )
    assert request.kind is ConditionKind.QUALIFICATION
    assert request.model_dump()["kind"] is ConditionKind.QUALIFICATION


@pytest.fixture
def description() -> JobDescriptionResult:
    return JobDescriptionResult(
        job_description_id=JD_ID,
        workspace_id=UUID("00112233-4455-6677-8899-aabbccddee00"),
        job_title="職稱",
        organization_unit=None,
        reports_to=None,
        purpose="目的",
        baseline_competency_level=3,
        duties=(DutyResult(id=DUTY_ID, name="職責", scope=None),),
        tasks=(
            TaskResult(
                id=TASK_ID,
                duty_id=DUTY_ID,
                name="任務",
                description=None,
                competency_level=2,
                outcomes=(TaskTextResult(id=UUID(int=5), text="成果"),),
                requirements=(TaskTextResult(id=UUID(int=6), text="要求"),),
                knowledge_ids=(KNOWLEDGE_ID,),
                skill_ids=(SKILL_ID,),
            ),
        ),
        knowledge=(KnowledgeResult(id=KNOWLEDGE_ID, name="知識", description=None),),
        skills=(SkillResult(id=SKILL_ID, name="技能", description="說明"),),
        collaborations=(
            CollaborationResult(id=UUID(int=7), collaborator_name="對象", scope=None),
        ),
        conditions=(
            JobConditionResult(
                id=UUID(int=8), kind=ConditionKind.QUALIFICATION, text="條件"
            ),
        ),
        version=3,
    )


def test_write_response_projects_complete_content_and_version(
    description: JobDescriptionResult,
) -> None:
    response = JobDescriptionResponse.model_validate(description).model_dump(
        mode="json"
    )
    assert response["version"] == 3
    assert response["tasks"][0]["outcomes"][0]["text"] == "成果"
    assert response["tasks"][0]["knowledge_ids"] == [str(KNOWLEDGE_ID)]
    assert response["conditions"][0]["kind"] == "qualification"
    assert not {"position", "created_items", "before", "changed"} & response.keys()


def test_history_response_identifies_version_and_restore_source(
    description: JobDescriptionResult,
) -> None:
    entry = HistoryEntry(
        job_description_id=JD_ID,
        version=3,
        kind="restored",
        recorded_at=datetime(2026, 10, 26, tzinfo=UTC),
        correlation_id="restore-1",
        reverts_correlation_id="edit-1",
        restored_from_version=1,
    )
    page = HistoryPageResponse.model_validate(
        HistoryPage(items=(entry,), next_page_token="opaque")
    ).model_dump(mode="json")
    assert page["items"][0]["job_description_id"] == str(JD_ID)
    assert page["items"][0]["version"] == 3
    assert page["items"][0]["restored_from_version"] == 1
    assert page["next_page_token"] == "opaque"
    snapshot = HistoryResponse.model_validate(
        JobDescriptionHistoryResult(content=description, entry=entry)
    ).model_dump(mode="json")
    assert snapshot["content"]["job_title"] == "職稱"
    assert "version" not in snapshot["content"]


def test_difference_response_maps_uuid_values_and_collection_order() -> None:
    response = JobDescriptionDifferenceResponse.model_validate(
        JobDescriptionDifference(
            job_description_id=JD_ID,
            before_version=1,
            after_version=3,
            items=(
                ItemDifference(
                    kind="task",
                    id=TASK_ID,
                    change="modified",
                    fields=(
                        FieldDifference(field="duty_id", before=None, after=DUTY_ID),
                    ),
                ),
            ),
            collections=(
                CollectionDifference(
                    collection="tasks",
                    owner_id=JD_ID,
                    group=DUTY_ID,
                    before_ids=(),
                    after_ids=(TASK_ID,),
                ),
            ),
        )
    ).model_dump(mode="json")
    assert response["after_version"] == 3
    assert response["items"][0]["fields"] == [
        {"field": "duty_id", "before": None, "after": str(DUTY_ID)}
    ]
    assert response["collections"][0]["group"] == str(DUTY_ID)
    assert response["collections"][0]["after_ids"] == [str(TASK_ID)]


def test_restore_request_maps_versions_and_optional_metadata() -> None:
    request = RestoreJobDescriptionRequest.model_validate(
        {
            "expected_version": 3,
            "target_version": 1,
            "correlation_id": "restore-1",
            "reverts_correlation_id": "edit-1",
        }
    )
    application = request.to_application(job_description_id=JD_ID)
    assert application.job_description_id == JD_ID
    assert application.target_version == 1
    assert application.expected_version == 3
    assert application.correlation_id == "restore-1"
    assert application.reverts_correlation_id == "edit-1"
