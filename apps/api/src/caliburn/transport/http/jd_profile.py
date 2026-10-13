"""Profile HTTP input/output; shared JD rules and transaction live below transport."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from caliburn.features.job_description.models import (
    ClearProfileField,
    InvalidProfileChangeError,
    ReviseJdProfile,
    SetProfileField,
)
from caliburn.features.job_files.models import JobFileNotFoundError
from caliburn.transport.http.jd_dependencies import JdEditing
from caliburn.transport.http.models.jd_profile_edits import ReviseJdProfileRequest, SetField
from caliburn.transport.http.models.jd_views import JdProfileView

router = APIRouter(prefix="/api/job-files/{job_file_id}/jd", tags=["job-description"])


@router.get("/profile", response_model=JdProfileView, operation_id="read_jd_profile")
async def read_profile(job_file_id: UUID, workflow: JdEditing) -> JdProfileView:
    try:
        result = await workflow.read_profile(job_file_id)
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error
    return JdProfileView.model_validate(result, from_attributes=True)


@router.post("/profile", response_model=JdProfileView, operation_id="revise_jd_profile")
async def revise_profile(
    job_file_id: UUID,
    body: ReviseJdProfileRequest,
    workflow: JdEditing,
) -> JdProfileView:
    try:
        command = ReviseJdProfile(
            command_id=body.command_id,
            expected_revision_id=body.expected_revision_id,
            changes=tuple(
                SetProfileField(change.field, change.value)
                if isinstance(change, SetField)
                else ClearProfileField(change.field)
                for change in body.changes
            ),
        )
        result = await workflow.revise_profile(job_file_id, command)
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error
    except InvalidProfileChangeError as error:
        raise HTTPException(status_code=422, detail={"code": "invalid_profile_changes"}) from error
    return JdProfileView.model_validate(result, from_attributes=True)
