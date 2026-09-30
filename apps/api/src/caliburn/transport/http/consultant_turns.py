"""Public consultant status and App controls; execution internals never enter the response."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.sse import EventSourceResponse, ServerSentEvent

from caliburn.contracts.generated.commentary_update import CommentaryUpdate
from caliburn.contracts.generated.consultant_turn import ConsultantTurn
from caliburn.contracts.generated.current_consultant_turn import CurrentConsultantTurn
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionNotFoundError,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
)
from caliburn.features.interviews.models import InterviewInputNotFoundError
from caliburn.features.job_files.models import JobFileNotFoundError
from caliburn.transport.http.jd_work import work_view
from caliburn.workflows.consultant_commentary import (
    CommentaryCapacityError,
    ConsultantCommentaryHub,
    PublicCommentaryUpdate,
)
from caliburn.workflows.consultant_controls import ConsultantControlWorkflow
from caliburn.workflows.consultant_status import (
    ConsultantStatusWorkflow,
    ConsultantTurnStatus,
    ConsultantTurnUnavailableError,
)

router = APIRouter(prefix="/api/job-files", tags=["interviews"])


def get_consultant_status_workflow(request: Request) -> ConsultantStatusWorkflow:
    workflow = getattr(request.app.state, "consultant_status_workflow", None)
    if not isinstance(workflow, ConsultantStatusWorkflow):
        raise HTTPException(status_code=503, detail={"code": "database_not_configured"})
    return workflow


ConsultantStatus = Annotated[ConsultantStatusWorkflow, Depends(get_consultant_status_workflow)]


async def subscribe_consultant_commentary(
    job_file_id: UUID,
    execution_id: UUID,
    request: Request,
    response: Response,
    workflow: ConsultantStatus,
) -> AsyncIterator[asyncio.Queue[PublicCommentaryUpdate] | None]:
    """Validate with the original status owner before headers or hub subscription."""
    response.headers["Cache-Control"] = "no-store"
    try:
        status = await workflow.read(job_file_id, execution_id)
    except (ExecutionNotFoundError, InterviewInputNotFoundError) as error:
        raise HTTPException(
            status_code=404, detail={"code": "consultant_turn_not_found"}
        ) from error
    except ConsultantTurnUnavailableError as error:
        raise HTTPException(
            status_code=503, detail={"code": "consultant_result_unavailable"}
        ) from error
    if status.status in {
        ExecutionStatus.COMPLETED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.FAILED,
    }:
        response.status_code = 204
        yield None
        return
    hub = getattr(request.app.state, "consultant_commentary_hub", None)
    if not isinstance(hub, ConsultantCommentaryHub):
        raise HTTPException(status_code=503, detail={"code": "commentary_stream_not_configured"})
    try:
        with hub.subscribe(job_file_id, execution_id) as queue:
            yield queue
    except CommentaryCapacityError as error:
        raise HTTPException(
            status_code=503, detail={"code": "commentary_stream_capacity"}
        ) from error


CommentarySubscription = Annotated[
    asyncio.Queue[PublicCommentaryUpdate] | None, Depends(subscribe_consultant_commentary)
]


@router.get(
    "/{job_file_id}/consultant-turns/{execution_id}/commentary-stream",
    response_class=EventSourceResponse,
)
async def stream_consultant_commentary(
    subscription: CommentarySubscription,
) -> AsyncIterator[ServerSentEvent]:
    """Presentation only: no replay, execution control, SDK event, or private content."""
    if subscription is None:
        return
    while True:
        update = await subscription.get()
        yield ServerSentEvent(
            event="commentary",
            data=CommentaryUpdate.model_validate(asdict(update)),
        )


def find_consultant_controls(request: Request) -> ConsultantControlWorkflow | None:
    workflow = getattr(request.app.state, "consultant_control_workflow", None)
    return workflow if isinstance(workflow, ConsultantControlWorkflow) else None


OptionalControls = Annotated[ConsultantControlWorkflow | None, Depends(find_consultant_controls)]


@router.get("/{job_file_id}/consultant-turns/current", response_model=CurrentConsultantTurn)
async def read_current_consultant_turn(
    job_file_id: UUID,
    response: Response,
    workflow: ConsultantStatus,
    controls: OptionalControls,
) -> CurrentConsultantTurn:
    response.headers["Cache-Control"] = "no-store"
    try:
        status = await workflow.read_current(job_file_id)
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error
    except (InterviewInputNotFoundError, ConsultantTurnUnavailableError) as error:
        raise HTTPException(
            status_code=503, detail={"code": "consultant_result_unavailable"}
        ) from error
    return CurrentConsultantTurn.model_validate(
        {"turn": None if status is None else turn_view(status, controls).model_dump(mode="json")}
    )


@router.get("/{job_file_id}/consultant-turns/{execution_id}", response_model=ConsultantTurn)
async def read_consultant_turn(
    job_file_id: UUID,
    execution_id: UUID,
    response: Response,
    workflow: ConsultantStatus,
    controls: OptionalControls,
) -> ConsultantTurn:
    response.headers["Cache-Control"] = "no-store"
    try:
        status = await workflow.read(job_file_id, execution_id)
    except (ExecutionNotFoundError, InterviewInputNotFoundError) as error:
        raise HTTPException(
            status_code=404, detail={"code": "consultant_turn_not_found"}
        ) from error
    except ConsultantTurnUnavailableError as error:
        raise HTTPException(
            status_code=503, detail={"code": "consultant_result_unavailable"}
        ) from error
    return turn_view(status, controls)


@router.get(
    "/{job_file_id}/consultant-turns/by-command/{command_id}", response_model=ConsultantTurn
)
async def read_consultant_turn_by_command(
    job_file_id: UUID,
    command_id: UUID,
    response: Response,
    workflow: ConsultantStatus,
    controls: OptionalControls,
) -> ConsultantTurn:
    response.headers["Cache-Control"] = "no-store"
    try:
        status = await workflow.read_by_command(job_file_id, command_id)
    except (ExecutionNotFoundError, InterviewInputNotFoundError) as error:
        raise HTTPException(
            status_code=404, detail={"code": "consultant_turn_not_found"}
        ) from error
    except ConsultantTurnUnavailableError as error:
        raise HTTPException(
            status_code=503, detail={"code": "consultant_result_unavailable"}
        ) from error
    return turn_view(status, controls)


@router.post("/{job_file_id}/consultant-turns/{execution_id}/pause", response_model=ConsultantTurn)
async def pause_consultant_turn(
    job_file_id: UUID,
    execution_id: UUID,
    request: Request,
    response: Response,
    workflow: ConsultantStatus,
    controls: OptionalControls,
) -> ConsultantTurn:
    return await _control_turn(
        "pause", job_file_id, execution_id, request, response, workflow, controls
    )


@router.post("/{job_file_id}/consultant-turns/{execution_id}/cancel", response_model=ConsultantTurn)
async def cancel_consultant_turn(
    job_file_id: UUID,
    execution_id: UUID,
    request: Request,
    response: Response,
    workflow: ConsultantStatus,
    controls: OptionalControls,
) -> ConsultantTurn:
    return await _control_turn(
        "cancel", job_file_id, execution_id, request, response, workflow, controls
    )


@router.post("/{job_file_id}/consultant-turns/{execution_id}/resume", response_model=ConsultantTurn)
async def resume_consultant_turn(
    job_file_id: UUID,
    execution_id: UUID,
    request: Request,
    response: Response,
    workflow: ConsultantStatus,
    controls: OptionalControls,
) -> ConsultantTurn:
    return await _control_turn(
        "resume", job_file_id, execution_id, request, response, workflow, controls
    )


async def _control_turn(
    action: Literal["pause", "cancel", "resume"],
    job_file_id: UUID,
    execution_id: UUID,
    request: Request,
    response: Response,
    workflow: ConsultantStatus,
    controls: ConsultantControlWorkflow | None,
) -> ConsultantTurn:
    response.headers["Cache-Control"] = "no-store"
    if request.query_params:
        raise HTTPException(status_code=422, detail={"code": "unexpected_control_arguments"})
    async for chunk in request.stream():
        if chunk:
            raise HTTPException(status_code=422, detail={"code": "unexpected_control_arguments"})
    if controls is None:
        raise HTTPException(status_code=503, detail={"code": "consultant_controls_unavailable"})
    try:
        # Verify the public Turn/input binding before any mutation, not just an ID match.
        await workflow.read(job_file_id, execution_id)
        if action != "cancel" and not controls.supervisor.running:
            raise HTTPException(status_code=503, detail={"code": "consultant_unavailable"})
        scope = ExecutionScope(job_file_id, execution_id, ExecutionKind.CONSULTANT_TURN)
        if action == "pause":
            await controls.pause(scope)
        elif action == "cancel":
            await controls.cancel(scope)
        else:
            await controls.resume(scope)
        # Ignore ExecutionInfo: public state is always re-read from its existing owner.
        status = await workflow.read(job_file_id, execution_id)
    except (ExecutionNotFoundError, InterviewInputNotFoundError) as error:
        raise HTTPException(
            status_code=404, detail={"code": "consultant_turn_not_found"}
        ) from error
    except ExecutionStateError as error:
        raise HTTPException(
            status_code=409, detail={"code": "consultant_control_conflict"}
        ) from error
    except ConsultantTurnUnavailableError as error:
        raise HTTPException(
            status_code=503, detail={"code": "consultant_result_unavailable"}
        ) from error
    except TimeoutError as error:
        # Stop may already be durable even if a local task has not returned. Re-read;
        # do not claim rollback or expose exception/checkpoint/provider contents.
        raise HTTPException(
            status_code=503, detail={"code": "consultant_control_unconfirmed"}
        ) from error
    return turn_view(status, controls)


def turn_view(
    status: ConsultantTurnStatus, controls: ConsultantControlWorkflow | None = None
) -> ConsultantTurn:
    """Explicit allowlist; never serialize the candidate scope or native checkpoint."""
    return ConsultantTurn.model_validate(
        {
            "job_file_id": status.job_file_id,
            "execution_id": status.execution_id,
            "status": status.status,
            "pause_requested": status.pause_requested,
            "input_text": status.input_text,
            "allowed_controls": _allowed_controls(status, controls),
            "commentary": None
            if status.commentary is None
            else [asdict(item) for item in status.commentary],
            "candidate": None
            if status.candidate is None
            else {
                "profile": asdict(status.candidate.profile),
                "work": work_view(status.candidate.work).model_dump(mode="json"),
            },
        }
    )


def _allowed_controls(
    status: ConsultantTurnStatus, controls: ConsultantControlWorkflow | None
) -> list[str]:
    if controls is None or status.status not in (ExecutionStatus.ACTIVE, ExecutionStatus.PAUSED):
        return []
    if not controls.supervisor.running:
        return ["cancel"]
    if status.status == ExecutionStatus.PAUSED:
        return ["resume", "cancel"]
    return ["cancel"] if status.pause_requested else ["pause", "cancel"]
