"""Typed responsibility-group HTTP intents; no storage or transaction logic."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from caliburn.contracts.generated import edit_jd_areas_request as wire
from caliburn.contracts.generated.jd_areas_view import Area, JdAreasView
from caliburn.features.executions.models import ExecutionBusyError
from caliburn.features.job_description import areas
from caliburn.features.job_description.models import JdCommandConflictError, StaleJdRevisionError
from caliburn.features.job_files.models import JobFileNotFoundError
from caliburn.transport.http.jd_dependencies import JdEditing

router = APIRouter(prefix="/api/job-files/{job_file_id}/jd", tags=["job-description"])


def _change_from_wire(
    change: wire.CreateArea | wire.ReviseArea | wire.DeleteArea | wire.ReorderArea,
) -> areas.AreaChange:
    match change:
        case wire.CreateArea():
            return areas.CreateArea(
                change.title.root if change.title else None,
                change.scope_text.root if change.scope_text else None,
            )
        case wire.ReviseArea():
            return areas.ReviseArea(
                change.area_id,
                tuple(
                    areas.AreaFieldChange(
                        areas.AreaField(item.field.value), item.value.root if item.value else None
                    )
                    for item in change.changes
                ),
            )
        case wire.DeleteArea():
            return areas.DeleteArea(change.area_id)
        case wire.ReorderArea():
            return areas.ReorderArea(change.area_id, change.before_area_id)


def areas_view(result: areas.JdAreasRevision) -> JdAreasView:
    return JdAreasView(
        revision_id=result.revision_id,
        areas=[
            Area(area_id=area.area_id, title=area.title, scope_text=area.scope_text)
            for area in result.areas
        ],
    )


@router.get("/areas", response_model=JdAreasView)
async def read_areas(job_file_id: UUID, workflow: JdEditing) -> JdAreasView:
    try:
        return areas_view(await workflow.read_areas(job_file_id))
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error


@router.post("/areas", response_model=JdAreasView)
async def edit_areas(
    job_file_id: UUID, body: wire.EditJdAreasRequest, workflow: JdEditing
) -> JdAreasView:
    try:
        command = areas.EditJdAreas(
            body.command_id, body.expected_revision_id, _change_from_wire(body.change)
        )
        return areas_view(await workflow.edit_areas(job_file_id, command))
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error
    except areas.AreaNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "jd_area_not_found"}) from error
    except areas.InvalidAreaChangeError as error:
        raise HTTPException(status_code=422, detail={"code": "invalid_area_change"}) from error
    except JdCommandConflictError as error:
        raise HTTPException(status_code=409, detail={"code": "jd_command_conflict"}) from error
    except StaleJdRevisionError as error:
        raise HTTPException(status_code=409, detail={"code": "jd_revision_stale"}) from error
    except ExecutionBusyError as error:
        raise HTTPException(status_code=409, detail={"code": "consultant_turn_active"}) from error
