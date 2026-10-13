"""Unified live activity and saved summaries, separate from formal interview completion."""

import asyncio
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.sse import EventSourceResponse, ServerSentEvent

from caliburn.adapters.reasoning_summaries import PublicReasoningSummary
from caliburn.features.executions.models import ExecutionNotFoundError, ExecutionStatus
from caliburn.features.interviews.models import InterviewInputNotFoundError
from caliburn.transport.http.consultant_turns import ConsultantStatus
from caliburn.transport.http.models.consultant import CommentaryUpdate, ReasoningSummary
from caliburn.workflows.consultant_turns.activity import (
    ConsultantActivityHub,
    PublicActivityUpdate,
    PublicStreamCapacityError,
)
from caliburn.workflows.consultant_turns.status import ConsultantTurnUnavailableError

router = APIRouter(prefix="/api/job-files", tags=["interviews"])


@router.get(
    "/{job_file_id}/consultant-turns/{execution_id}/reasoning-summaries",
    response_model=list[ReasoningSummary],
    operation_id="read_reasoning_summaries",
)
async def read_reasoning_summaries(
    job_file_id: UUID,
    execution_id: UUID,
    response: Response,
    workflow: ConsultantStatus,
) -> list[ReasoningSummary]:
    response.headers["Cache-Control"] = "no-store"
    try:
        summaries = await workflow.read_reasoning_summaries(job_file_id, execution_id)
    except (ExecutionNotFoundError, InterviewInputNotFoundError) as error:
        raise HTTPException(404, detail={"code": "consultant_turn_not_found"}) from error
    except ConsultantTurnUnavailableError as error:
        raise HTTPException(503, detail={"code": "consultant_result_unavailable"}) from error
    return [ReasoningSummary.model_validate(summary, from_attributes=True) for summary in summaries]


async def subscribe_consultant_activity(
    job_file_id: UUID,
    execution_id: UUID,
    request: Request,
    response: Response,
    workflow: ConsultantStatus,
) -> AsyncIterator[asyncio.Queue[PublicActivityUpdate] | None]:
    response.headers["Cache-Control"] = "no-store"
    try:
        status = await workflow.read(job_file_id, execution_id)
    except (ExecutionNotFoundError, InterviewInputNotFoundError) as error:
        raise HTTPException(404, detail={"code": "consultant_turn_not_found"}) from error
    except ConsultantTurnUnavailableError as error:
        raise HTTPException(503, detail={"code": "consultant_result_unavailable"}) from error
    if status.status in (
        ExecutionStatus.COMPLETED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.FAILED,
    ):
        response.status_code = 204
        yield None
        return
    hub = getattr(request.app.state, "consultant_activity_hub", None)
    if not isinstance(hub, ConsultantActivityHub):
        raise HTTPException(503, detail={"code": "activity_stream_not_configured"})
    try:
        with hub.subscribe(job_file_id, execution_id) as queue:
            yield queue
    except PublicStreamCapacityError as error:
        raise HTTPException(503, detail={"code": "activity_stream_capacity"}) from error


ActivitySubscription = Annotated[
    asyncio.Queue[PublicActivityUpdate] | None, Depends(subscribe_consultant_activity)
]


@router.get(
    "/{job_file_id}/consultant-turns/{execution_id}/activity-stream",
    response_class=EventSourceResponse,
    operation_id="stream_consultant_activity",
    responses={
        200: {
            "model": ReasoningSummary | CommentaryUpdate,
            "description": "Public activity events",
        },
        204: {"description": "The turn has ended; no event stream"},
    },
)
async def stream_consultant_activity(
    subscription: ActivitySubscription,
) -> AsyncIterator[ServerSentEvent]:
    if subscription is None:
        return
    while True:
        update = await subscription.get()
        if isinstance(update, PublicReasoningSummary):
            yield ServerSentEvent(
                event="reasoning_summary",
                data=ReasoningSummary.model_validate(update, from_attributes=True),
            )
        else:
            yield ServerSentEvent(
                event="commentary",
                data=CommentaryUpdate.model_validate(update, from_attributes=True),
            )
