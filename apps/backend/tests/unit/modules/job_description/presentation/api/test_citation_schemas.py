"""HTTP 原子內容編修可接引用；完整回覆保存正式定位。"""

from uuid import uuid4

from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.domain.models.citation import InterviewReference
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)
from caliburn.modules.job_description.presentation.api.schemas.citations import (
    AddCitationRequest,
)
from caliburn.modules.job_description.presentation.api.schemas.content import (
    JobDescriptionResponse,
    UpdateJobDescriptionRequest,
)


def test_full_http_response_keeps_citation_identity_and_locator() -> None:
    root = JobDescription.create(workspace_id=uuid4())
    source = InterviewReference(workspace_id=root.workspace_id, message_id=uuid4())
    identity = root.add_citation(
        target_kind="job_description", target_id=root.id, source=source
    )
    response = JobDescriptionResponse.model_validate(
        JobDescriptionResult.from_job_description(root, version=2)
    )
    assert response.model_dump(mode="json")["citations"][0]["id"] == str(identity)


def test_profile_patch_accepts_citation_only_intent() -> None:
    workspace_id, message_id = uuid4(), uuid4()
    body = UpdateJobDescriptionRequest.model_validate_json(
        '{"expected_version":1,"citations":[{"action":"add","source":{"kind":"interview","workspace_id":"'
        + str(workspace_id)
        + '","message_id":"'
        + str(message_id)
        + '"}}]}'
    )
    assert isinstance(body.citations[0], AddCitationRequest)
    assert body.citations[0].source.workspace_id == workspace_id
