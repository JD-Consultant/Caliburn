"""正式與候選 JD 共用同一份查閱投影。"""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from caliburn.features.job_description.work_models import JdWorkRevision
from caliburn.features.job_files.models import JobFileNotFoundError
from caliburn.transport.http.jd_dependencies import JdEditing
from caliburn.transport.http.jd_tasks import task_view
from caliburn.transport.http.models.jd_views import (
    Area,
    Capability,
    Collaborator,
    Condition,
    JdWorkView,
    TaskLink,
)

router = APIRouter(prefix="/api/job-files/{job_file_id}/jd", tags=["job-description"])


@router.get("/work", response_model=JdWorkView, operation_id="read_jd_work")
async def read_work(job_file_id: UUID, workflow: JdEditing) -> JdWorkView:
    try:
        result = await workflow.read_work(job_file_id)
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error
    return work_view(result)


def work_view(result: JdWorkRevision) -> JdWorkView:
    return JdWorkView(
        revision_id=result.revision_id,
        areas=[Area.model_validate(item) for item in result.areas],
        tasks=[task_view(item) for item in result.tasks],
        capabilities=[Capability.model_validate(item) for item in result.capabilities],
        task_links=[TaskLink.model_validate(item) for item in result.task_links],
        collaborators=[Collaborator.model_validate(item) for item in result.collaborators],
        conditions=[Condition.model_validate(item) for item in result.conditions],
    )
