"""HTTP validation and projection only; application workflow owns the transaction."""

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from caliburn.contracts.generated.create_job_file_request import CreateJobFileRequest
from caliburn.contracts.generated.interview_history import InterviewHistory, InterviewMessage
from caliburn.contracts.generated.job_file_list import JobFile, JobFileList
from caliburn.contracts.generated.rename_job_file_request import RenameJobFileRequest
from caliburn.features.executions.models import ExecutionBusyError
from caliburn.features.job_files.models import (
    CreateJobFile,
    CreationCommandConflictError,
    JobFileCreationDeletedError,
    JobFileNotFoundError,
    RenameCommandConflictError,
    RenameJobFile,
    StaleJobFileNameError,
)
from caliburn.transport.http.contracts import canonical_body
from caliburn.workflows.job_files import JobFileWorkflow

router = APIRouter(prefix="/api/job-files", tags=["job-files"])


def get_job_file_workflow(request: Request) -> JobFileWorkflow:
    workflow = request.app.state.job_file_workflow
    if not isinstance(workflow, JobFileWorkflow):
        raise HTTPException(status_code=503, detail={"code": "database_not_configured"})
    return workflow


JobFiles = Annotated[JobFileWorkflow, Depends(get_job_file_workflow)]


@router.delete("/{job_file_id}", status_code=204)
async def delete_job_file(job_file_id: UUID, workflow: JobFiles) -> Response:
    try:
        await workflow.delete(job_file_id)
    except ExecutionBusyError as error:
        raise HTTPException(status_code=409, detail={"code": "job_file_busy"}) from error
    return Response(status_code=204)


@router.post("", status_code=201, response_model=JobFile, responses={200: {"model": JobFile}})
async def create_job_file(
    body: Annotated[CreateJobFileRequest, canonical_body(CreateJobFileRequest)],
    response: Response,
    workflow: JobFiles,
) -> JobFile:
    try:
        created = await workflow.create(
            CreateJobFile(
                command_id=body.command_id,
                display_name=body.display_name,
                employee_name=body.employee_name,
            )
        )
    except JobFileCreationDeletedError as error:
        raise HTTPException(status_code=410, detail={"code": "creation_result_deleted"}) from error
    except CreationCommandConflictError as error:
        raise HTTPException(
            status_code=409, detail={"code": "creation_command_conflict"}
        ) from error
    response.status_code = 201 if created.is_new else 200
    return JobFile.model_validate(asdict(created.job_file))


@router.get("", response_model=JobFileList)
async def list_job_files(workflow: JobFiles) -> JobFileList:
    return JobFileList(
        job_files=[JobFile.model_validate(asdict(file)) for file in await workflow.list_files()]
    )


@router.get("/{job_file_id}", response_model=JobFile)
async def read_job_file(job_file_id: UUID, workflow: JobFiles) -> JobFile:
    try:
        result = await workflow.read_file(job_file_id)
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error
    return JobFile.model_validate(asdict(result))


@router.get("/{job_file_id}/interviews", response_model=InterviewHistory)
async def read_interview_history(job_file_id: UUID, workflow: JobFiles) -> InterviewHistory:
    try:
        messages = await workflow.read_interviews(job_file_id)
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error
    return InterviewHistory(
        messages=[
            InterviewMessage.model_validate(
                {**asdict(entry.message), "execution_id": entry.execution_id}
            )
            for entry in messages
        ]
    )


@router.post("/{job_file_id}/rename", response_model=JobFile)
async def rename_job_file(
    job_file_id: UUID,
    body: Annotated[RenameJobFileRequest, canonical_body(RenameJobFileRequest)],
    workflow: JobFiles,
) -> JobFile:
    try:
        result = await workflow.rename(
            job_file_id,
            RenameJobFile(
                command_id=body.command_id,
                display_name=body.display_name,
                expected_name_revision=body.expected_name_revision,
            ),
        )
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error
    except RenameCommandConflictError as error:
        raise HTTPException(status_code=409, detail={"code": "rename_command_conflict"}) from error
    except StaleJobFileNameError as error:
        raise HTTPException(status_code=409, detail={"code": "stale_job_file_name"}) from error
    return JobFile.model_validate(asdict(result))
