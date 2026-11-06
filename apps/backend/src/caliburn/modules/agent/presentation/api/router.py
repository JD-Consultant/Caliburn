"""HTTP 只轉譯輪次用例與原生 SSE，服務由 lifespan 共用。"""

from collections.abc import AsyncIterator, Callable
from contextlib import aclosing
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.sse import EventSourceResponse, ServerSentEvent

from caliburn.modules.agent.application.agent_service import AgentService
from caliburn.modules.agent.application.events import TurnEvent
from caliburn.modules.agent.application.views import (
    StepView,
    TurnView,
)
from caliburn.modules.agent.presentation.api.errors import http_errors
from caliburn.modules.agent.presentation.api.event_schema import (
    AGENT_EVENTS_OPERATION_ID,
)
from caliburn.modules.agent.presentation.api.schemas import (
    SubmitTurnRequest,
)
from caliburn.shared.presentation.api.schemas import ErrorResponse
from caliburn.shared.presentation.api.values import HttpId


def build_agent_router(service_provider: Callable[[], AgentService]) -> APIRouter:
    router = APIRouter(
        prefix="/workspaces/{workspace_id}/agent",
        tags=["agent"],
        responses={
            404: {"model": ErrorResponse},
            409: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
    )

    @router.post(
        "/turns",
        response_model=TurnView,
        status_code=202,
        responses={200: {"model": TurnView}},
    )
    async def submit(
        workspace_id: HttpId,
        body: SubmitTurnRequest,
        request: Request,
        response: Response,
        service: Annotated[AgentService, Depends(service_provider)],
    ) -> TurnView:
        with http_errors():
            result = await service.submit_turn(
                workspace_id=workspace_id, turn_id=body.turn_id, input=body.input
            )
        response.status_code = 202 if result.created else 200
        response.headers["Location"] = str(
            request.url_for(
                "get_agent_turn", workspace_id=workspace_id, turn_id=body.turn_id
            )
        )
        return result.turn

    @router.get("/turns/{turn_id}", response_model=TurnView, name="get_agent_turn")
    async def get(
        workspace_id: HttpId,
        turn_id: HttpId,
        service: Annotated[AgentService, Depends(service_provider)],
    ) -> TurnView:
        with http_errors():
            return await service.get_turn(workspace_id=workspace_id, turn_id=turn_id)

    @router.get("/turns", response_model=list[TurnView])
    async def list_turns(
        workspace_id: HttpId,
        service: Annotated[AgentService, Depends(service_provider)],
    ) -> list[TurnView]:
        with http_errors():
            return await service.list_turns(workspace_id=workspace_id)

    @router.get("/turns/{turn_id}/steps", response_model=list[StepView])
    async def steps(
        workspace_id: HttpId,
        turn_id: HttpId,
        service: Annotated[AgentService, Depends(service_provider)],
    ) -> list[StepView]:
        with http_errors():
            return await service.list_steps(workspace_id=workspace_id, turn_id=turn_id)

    @router.post("/turns/{turn_id}/resume", response_model=TurnView, status_code=202)
    async def resume(
        workspace_id: HttpId,
        turn_id: HttpId,
        service: Annotated[AgentService, Depends(service_provider)],
    ) -> TurnView:
        with http_errors():
            return await service.resume_turn(workspace_id=workspace_id, turn_id=turn_id)

    @router.post("/turns/{turn_id}/cancel", status_code=204)
    async def cancel(
        workspace_id: HttpId,
        turn_id: HttpId,
        service: Annotated[AgentService, Depends(service_provider)],
    ) -> None:
        with http_errors():
            await service.cancel_turn(workspace_id=workspace_id, turn_id=turn_id)

    async def subscribe(
        workspace_id: HttpId,
        turn_id: HttpId,
        service: Annotated[AgentService, Depends(service_provider)],
    ) -> AsyncIterator[tuple[TurnEvent, AsyncIterator[TurnEvent]]]:
        async with aclosing(
            service.stream_turn(workspace_id=workspace_id, turn_id=turn_id)
        ) as stream:
            with http_errors():
                first = await anext(stream)
            yield first, stream

    @router.get(
        "/turns/{turn_id}/events",
        response_class=EventSourceResponse,
        operation_id=AGENT_EVENTS_OPERATION_ID,
    )
    async def events(
        subscription: Annotated[
            tuple[TurnEvent, AsyncIterator[TurnEvent]], Depends(subscribe)
        ],
    ) -> AsyncIterator[ServerSentEvent]:
        first, stream = subscription
        yield ServerSentEvent(event=first.event, data=first.data)
        async for event in stream:
            yield ServerSentEvent(event=event.event, data=event.data)

    return router
