"""Profile HTTP input/output; shared JD rules and transaction live below transport."""

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from caliburn.contracts.generated.jd_profile_view import JdProfileView
from caliburn.contracts.generated.revise_jd_profile_request import ReviseJdProfileRequest, SetField
from caliburn.features.executions.models import ExecutionBusyError
from caliburn.features.job_description.models import (
    ClearProfileField,
    InvalidProfileChangeError,
    JdCommandConflictError,
    ProfileField,
    ReviseJdProfile,
    SetProfileField,
    StaleJdRevisionError,
)
from caliburn.features.job_files.models import JobFileNotFoundError
from caliburn.workflows.jd_editing import JdEditingWorkflow

router = APIRouter(prefix="/api/job-files/{job_file_id}/jd", tags=["job-description"])


def get_jd_workflow(request: Request) -> JdEditingWorkflow:
    workflow = request.app.state.jd_editing_workflow
    if not isinstance(workflow, JdEditingWorkflow):
        raise HTTPException(status_code=503, detail={"code": "database_not_configured"})
    return workflow


JdEditing = Annotated[JdEditingWorkflow, Depends(get_jd_workflow)]


@router.get("/profile", response_model=JdProfileView)
async def read_profile(job_file_id: UUID, workflow: JdEditing) -> JdProfileView:
    try:
        result = await workflow.read_profile(job_file_id)
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error
    return JdProfileView.model_validate(asdict(result))


@router.post("/profile", response_model=JdProfileView)
async def revise_profile(
    job_file_id: UUID, body: ReviseJdProfileRequest, workflow: JdEditing
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
    except JdCommandConflictError as error:
        raise HTTPException(status_code=409, detail={"code": "jd_command_conflict"}) from error
    except StaleJdRevisionError as error:
        raise HTTPException(status_code=409, detail={"code": "jd_revision_stale"}) from error
    except ExecutionBusyError as error:
        raise HTTPException(status_code=409, detail={"code": "consultant_turn_active"}) from error
    return JdProfileView.model_validate(asdict(result))
