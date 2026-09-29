"""One read-only projection for related manual-editor collections."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from caliburn.contracts.generated.jd_work_view import JdWorkView
from caliburn.features.job_description.areas import JdAreasRevision
from caliburn.features.job_description.tasks import JdTasksRevision
from caliburn.features.job_files.models import JobFileNotFoundError
from caliburn.transport.http.jd_areas import areas_view
from caliburn.transport.http.jd_dependencies import JdEditing
from caliburn.transport.http.jd_tasks import tasks_view

router = APIRouter(prefix="/api/job-files/{job_file_id}/jd", tags=["job-description"])


@router.get("/work", response_model=JdWorkView)
async def read_work(job_file_id: UUID, workflow: JdEditing) -> JdWorkView:
    try:
        result = await workflow.read_work(job_file_id)
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error
    # Recompose the existing wire projections; both derive from the same immutable revision.
    areas = areas_view(JdAreasRevision(result.revision_id, result.areas))
    tasks = tasks_view(JdTasksRevision(result.revision_id, result.tasks))
    return JdWorkView.model_validate({**areas.model_dump(), "tasks": tasks.model_dump()["tasks"]})
