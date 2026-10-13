"""Public tool observations, never full diagnostics or model context."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from caliburn.features.executions.models import ExecutionNotFoundError, ExecutionStateError
from caliburn.transport.http.models.consultant import Call, TurnTools
from caliburn.workflows.consultant_turns.tool_history import TurnToolsWorkflow

router = APIRouter(prefix="/api/job-files/{job_file_id}/consultant-turns", tags=["interviews"])


def get_turn_tools(request: Request, response: Response) -> TurnToolsWorkflow:
    response.headers["Cache-Control"] = "no-store"
    workflow = getattr(request.app.state, "turn_tools_workflow", None)
    if not isinstance(workflow, TurnToolsWorkflow):
        raise HTTPException(status_code=503, detail={"code": "database_not_configured"})
    return workflow


@router.get("/{execution_id}/tools", response_model=TurnTools, operation_id="read_turn_tools")
async def read_turn_tools(
    job_file_id: UUID,
    execution_id: UUID,
    request: Request,
    workflow: Annotated[TurnToolsWorkflow, Depends(get_turn_tools)],
) -> TurnTools:
    if request.query_params or await request.body():
        raise HTTPException(status_code=422, detail={"code": "unexpected_tool_read_arguments"})
    try:
        calls = await workflow.read(job_file_id, execution_id)
    except ExecutionNotFoundError as error:
        raise HTTPException(
            status_code=404, detail={"code": "consultant_turn_not_found"}
        ) from error
    except ExecutionStateError as error:
        raise HTTPException(status_code=409, detail={"code": "turn_tools_unavailable"}) from error
    return TurnTools(
        execution_id=execution_id,
        calls=[
            Call(
                request_id=call.request_id,
                response_id=call.response_id,
                call_id=call.call_id,
                name=call.name,
                arguments=call.arguments,
                result_state=call.result_state,
                output=call.output,
            )
            for call in calls
        ],
    )
