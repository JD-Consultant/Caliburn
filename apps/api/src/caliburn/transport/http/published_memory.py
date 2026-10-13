"""Browse the latest publication map and its fixed snapshot bodies."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from caliburn.features.job_files.models import JobFileNotFoundError
from caliburn.features.work_memory.revisions import MemoryRevisionNotFoundError
from caliburn.transport.http.models.memory import (
    MemoryMapItem,
    PublishedMemory,
    PublishedMemoryObject,
)
from caliburn.workflows.work_memory.published_reads import PublishedMemoryWorkflow

router = APIRouter(prefix="/api/job-files/{job_file_id}/memory", tags=["memory"])


def get_published_memory(request: Request, response: Response) -> PublishedMemoryWorkflow:
    response.headers["Cache-Control"] = "no-store"
    workflow = getattr(request.app.state, "published_memory_workflow", None)
    if not isinstance(workflow, PublishedMemoryWorkflow):
        raise HTTPException(status_code=503, detail={"code": "database_not_configured"})
    return workflow


async def require_no_arguments(request: Request) -> None:
    if request.query_params or await request.body():
        raise HTTPException(status_code=422, detail={"code": "unexpected_memory_read_arguments"})


@router.get("", response_model=PublishedMemory, operation_id="read_latest_memory")
async def read_latest_memory(
    job_file_id: UUID,
    request: Request,
    workflow: Annotated[PublishedMemoryWorkflow, Depends(get_published_memory)],
) -> PublishedMemory:
    await require_no_arguments(request)
    try:
        value = await workflow.read_latest(job_file_id)
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error
    return PublishedMemory(
        snapshot_id=value.snapshot_id,
        covered_through_sequence=value.covered_through_sequence,
        work_situations=[
            MemoryMapItem(object_id=item.object_id, title=item.title, description=item.description)
            for item in value.work_situations
        ],
        work_understandings=[
            MemoryMapItem(object_id=item.object_id, title=item.title, description=item.description)
            for item in value.work_understandings
        ],
    )


@router.get(
    "/{snapshot_id}/objects/{object_id}",
    response_model=PublishedMemoryObject,
    operation_id="read_memory_object",
)
async def read_memory_object(
    job_file_id: UUID,
    snapshot_id: UUID,
    object_id: UUID,
    request: Request,
    workflow: Annotated[PublishedMemoryWorkflow, Depends(get_published_memory)],
) -> PublishedMemoryObject:
    await require_no_arguments(request)
    try:
        value = await workflow.read_object(job_file_id, snapshot_id, object_id)
    except (JobFileNotFoundError, MemoryRevisionNotFoundError) as error:
        raise HTTPException(status_code=404, detail={"code": "memory_object_not_found"}) from error
    return PublishedMemoryObject(
        snapshot_id=snapshot_id,
        object_id=value.object_id,
        layer=value.layer,
        title=value.content.title,
        description=value.content.description,
        body=value.content.body,
    )
