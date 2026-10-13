"""Typed job-wide condition HTTP intents; no storage or transaction logic."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from caliburn.features.job_description import conditions
from caliburn.features.job_files.models import JobFileNotFoundError
from caliburn.transport.http.jd_dependencies import JdEditing
from caliburn.transport.http.models import jd_conditions_edits as wire
from caliburn.transport.http.models.jd_views import Condition, JdConditionsView

router = APIRouter(prefix="/api/job-files/{job_file_id}/jd", tags=["job-description"])


def _change_from_wire(
    change: wire.CreateCondition
    | wire.ReviseCondition
    | wire.DeleteCondition
    | wire.ReorderCondition,
) -> conditions.ConditionChange:
    match change:
        case wire.CreateCondition():
            return conditions.CreateCondition(
                change.kind,
                change.text,
            )
        case wire.ReviseCondition():
            return conditions.ReviseCondition(
                change.condition_id,
                tuple(
                    conditions.ConditionTextChange(item.value)
                    if isinstance(item, wire.ConditionTextChange)
                    else conditions.ConditionKindChange(item.value)
                    for item in change.changes
                ),
            )
        case wire.DeleteCondition():
            return conditions.DeleteCondition(change.condition_id)
        case wire.ReorderCondition():
            return conditions.ReorderCondition(change.condition_id, change.before_condition_id)


def conditions_view(result: conditions.JdConditionsRevision) -> JdConditionsView:
    return JdConditionsView(
        revision_id=result.revision_id,
        conditions=[
            Condition(
                condition_id=condition.condition_id,
                kind=condition.kind,
                text=condition.text,
            )
            for condition in result.conditions
        ],
    )


@router.get("/conditions", response_model=JdConditionsView, operation_id="read_jd_conditions")
async def read_conditions(job_file_id: UUID, workflow: JdEditing) -> JdConditionsView:
    try:
        return conditions_view(await workflow.read_conditions(job_file_id))
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error


@router.post("/conditions", response_model=JdConditionsView, operation_id="edit_jd_conditions")
async def edit_conditions(
    job_file_id: UUID,
    body: wire.EditJdConditionsRequest,
    workflow: JdEditing,
) -> JdConditionsView:
    try:
        command = conditions.EditJdConditions(
            body.command_id, body.expected_revision_id, _change_from_wire(body.change)
        )
        return conditions_view(await workflow.edit_conditions(job_file_id, command))
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error
    except conditions.ConditionNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "jd_condition_not_found"}) from error
    except conditions.InvalidConditionChangeError as error:
        raise HTTPException(status_code=422, detail={"code": "invalid_condition_change"}) from error
