"""Typed job-wide condition HTTP intents; no storage or transaction logic."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException

from caliburn.contracts.generated import edit_jd_conditions_request as wire
from caliburn.contracts.generated.jd_conditions_view import Condition, JdConditionsView, Kind
from caliburn.features.job_description import conditions
from caliburn.features.job_files.models import JobFileNotFoundError
from caliburn.transport.http.contracts import canonical_body
from caliburn.transport.http.jd_dependencies import JdEditing

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
                conditions.ConditionKind(change.kind.value),
                change.text,
            )
        case wire.ReviseCondition():
            return conditions.ReviseCondition(
                change.condition_id,
                tuple(
                    conditions.ConditionTextChange(item.value)
                    if isinstance(item, wire.ConditionTextChange)
                    else conditions.ConditionKindChange(conditions.ConditionKind(item.value.value))
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
                kind=Kind(condition.kind.value),
                text=condition.text,
            )
            for condition in result.conditions
        ],
    )


@router.get("/conditions", response_model=JdConditionsView)
async def read_conditions(job_file_id: UUID, workflow: JdEditing) -> JdConditionsView:
    try:
        return conditions_view(await workflow.read_conditions(job_file_id))
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error


@router.post("/conditions", response_model=JdConditionsView)
async def edit_conditions(
    job_file_id: UUID,
    body: Annotated[wire.EditJdConditionsRequest, canonical_body(wire.EditJdConditionsRequest)],
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
