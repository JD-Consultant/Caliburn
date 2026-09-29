"""Manual shared knowledge/skill edits; wire types do not own JD rules."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from caliburn.contracts.generated import edit_jd_capabilities_request as wire
from caliburn.contracts.generated import jd_capabilities_view as view
from caliburn.features.executions.models import ExecutionBusyError
from caliburn.features.job_description import capabilities
from caliburn.features.job_description.models import JdCommandConflictError, StaleJdRevisionError
from caliburn.features.job_files.models import JobFileNotFoundError
from caliburn.transport.http.jd_dependencies import JdEditing

router = APIRouter(prefix="/api/job-files/{job_file_id}/jd", tags=["job-description"])


def _nullable_text(value: str | wire.OptionalText | None) -> str | None:
    return value.root if isinstance(value, wire.OptionalText) else value


def _change_from_wire(
    change: wire.CreateCapability
    | wire.ReviseCapability
    | wire.DeleteCapability
    | wire.ReorderCapability
    | wire.SetTaskCapability
    | wire.ReorderTaskCapability,
) -> capabilities.CapabilityChange:
    match change:
        case wire.CreateCapability():
            item = change.root
            return capabilities.CreateCapability(
                capabilities.CapabilityKind(item.kind.value),
                _nullable_text(item.name),
                _nullable_text(item.description),
            )
        case wire.ReviseCapability():
            return capabilities.ReviseCapability(
                change.capability_id,
                tuple(
                    capabilities.CapabilityFieldChange(
                        capabilities.CapabilityField(item.field.value), _nullable_text(item.value)
                    )
                    for item in change.changes
                ),
            )
        case wire.DeleteCapability():
            return capabilities.DeleteCapability(change.capability_id)
        case wire.ReorderCapability():
            return capabilities.ReorderCapability(change.capability_id, change.before_capability_id)
        case wire.SetTaskCapability():
            return capabilities.SetTaskCapability(
                change.task_id, change.capability_id, change.linked
            )
        case wire.ReorderTaskCapability():
            return capabilities.ReorderTaskCapability(
                change.task_id, change.capability_id, change.before_capability_id
            )


def capabilities_view(result: capabilities.JdCapabilitiesRevision) -> view.JdCapabilitiesView:
    return view.JdCapabilitiesView(
        revision_id=result.revision_id,
        capabilities=[
            view.Capability(
                capability_id=item.capability_id,
                kind=view.Kind(item.kind.value),
                name=item.name,
                description=item.description,
            )
            for item in result.capabilities
        ],
        task_links=[
            view.TaskLink(task_id=item.task_id, capability_id=item.capability_id)
            for item in result.task_links
        ],
    )


@router.get("/capabilities", response_model=view.JdCapabilitiesView)
async def read_capabilities(job_file_id: UUID, workflow: JdEditing) -> view.JdCapabilitiesView:
    try:
        return capabilities_view(await workflow.read_capabilities(job_file_id))
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error


@router.post("/capabilities", response_model=view.JdCapabilitiesView)
async def edit_capabilities(
    job_file_id: UUID,
    body: wire.EditJdCapabilitiesRequest,
    workflow: JdEditing,
) -> view.JdCapabilitiesView:
    try:
        command = capabilities.EditJdCapabilities(
            body.command_id, body.expected_revision_id, _change_from_wire(body.change)
        )
        return capabilities_view(await workflow.edit_capabilities(job_file_id, command))
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error
    except capabilities.CapabilityTargetNotFoundError as error:
        raise HTTPException(
            status_code=404, detail={"code": "jd_capability_target_not_found"}
        ) from error
    except capabilities.InvalidCapabilityChangeError as error:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_capability_change"}
        ) from error
    except capabilities.CapabilityInUseError as error:
        raise HTTPException(status_code=409, detail={"code": "capability_in_use"}) from error
    except JdCommandConflictError as error:
        raise HTTPException(status_code=409, detail={"code": "jd_command_conflict"}) from error
    except StaleJdRevisionError as error:
        raise HTTPException(status_code=409, detail={"code": "jd_revision_stale"}) from error
    except ExecutionBusyError as error:
        raise HTTPException(status_code=409, detail={"code": "consultant_turn_active"}) from error
