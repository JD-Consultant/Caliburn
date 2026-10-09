"""Profile HTTP input/output; shared JD rules and transaction live below transport."""

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException

from caliburn.contracts.generated.jd_profile_view import JdProfileView
from caliburn.contracts.generated.revise_jd_profile_request import ReviseJdProfileRequest, SetField
from caliburn.features.job_description.models import (
    ClearProfileField,
    InvalidProfileChangeError,
    ProfileField,
    ReviseJdProfile,
    SetProfileField,
)
from caliburn.features.job_files.models import JobFileNotFoundError
from caliburn.transport.http.contracts import canonical_body
from caliburn.transport.http.jd_dependencies import JdEditing

router = APIRouter(prefix="/api/job-files/{job_file_id}/jd", tags=["job-description"])


@router.get("/profile", response_model=JdProfileView)
async def read_profile(job_file_id: UUID, workflow: JdEditing) -> JdProfileView:
    try:
        result = await workflow.read_profile(job_file_id)
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error
    return JdProfileView.model_validate(asdict(result))


@router.post("/profile", response_model=JdProfileView)
async def revise_profile(
    job_file_id: UUID,
    body: Annotated[ReviseJdProfileRequest, canonical_body(ReviseJdProfileRequest)],
    workflow: JdEditing,
) -> JdProfileView:
    try:
        command = ReviseJdProfile(
            command_id=body.command_id,
            expected_revision_id=body.expected_revision_id,
            changes=tuple(
                SetProfileField(ProfileField(change.field.value), change.value)
                if isinstance(change, SetField)
                else ClearProfileField(ProfileField(change.field.value))
                for change in body.changes
            ),
        )
        result = await workflow.revise_profile(job_file_id, command)
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error
    except InvalidProfileChangeError as error:
        raise HTTPException(status_code=422, detail={"code": "invalid_profile_changes"}) from error
    return JdProfileView.model_validate(asdict(result))
