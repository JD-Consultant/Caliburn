"""One read-only projection for related manual-editor collections."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from caliburn.contracts.generated.jd_work_view import JdWorkView
from caliburn.features.job_description.areas import JdAreasRevision
from caliburn.features.job_description.capabilities import JdCapabilitiesRevision
from caliburn.features.job_description.collaborators import JdCollaboratorsRevision
from caliburn.features.job_description.conditions import JdConditionsRevision
from caliburn.features.job_description.tasks import JdTasksRevision
from caliburn.features.job_files.models import JobFileNotFoundError
from caliburn.transport.http.jd_areas import areas_view
from caliburn.transport.http.jd_capabilities import capabilities_view
from caliburn.transport.http.jd_collaborators import collaborators_view
from caliburn.transport.http.jd_conditions import conditions_view
from caliburn.transport.http.jd_dependencies import JdEditing
from caliburn.transport.http.jd_tasks import tasks_view

router = APIRouter(prefix="/api/job-files/{job_file_id}/jd", tags=["job-description"])


@router.get("/work", response_model=JdWorkView)
async def read_work(job_file_id: UUID, workflow: JdEditing) -> JdWorkView:
    try:
        result = await workflow.read_work(job_file_id)
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error
    # Recompose wire values, not distinct generated Enum classes, from one revision.
    areas = areas_view(JdAreasRevision(result.revision_id, result.areas))
    tasks = tasks_view(JdTasksRevision(result.revision_id, result.tasks))
    capabilities = capabilities_view(
        JdCapabilitiesRevision(result.revision_id, result.capabilities, result.task_links)
    )
    collaborators = collaborators_view(
        JdCollaboratorsRevision(result.revision_id, result.collaborators)
    )
    conditions = conditions_view(JdConditionsRevision(result.revision_id, result.conditions))
    return JdWorkView.model_validate(
        {
            **areas.model_dump(mode="json"),
            **tasks.model_dump(mode="json"),
            **capabilities.model_dump(mode="json"),
            **collaborators.model_dump(mode="json"),
            **conditions.model_dump(mode="json"),
        }
    )
