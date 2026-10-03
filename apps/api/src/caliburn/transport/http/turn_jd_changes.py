"""Read completed-Turn JD changes; clients never choose historical comparison endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from caliburn.contracts.generated.turn_jd_changes import TurnJdChanges
from caliburn.features.executions.models import ExecutionNotFoundError, ExecutionStateError
from caliburn.features.job_description.change_queries import JdChangeHistoryUnavailableError
from caliburn.transport.turn_jd_markdown import project_turn_jd_changes
from caliburn.workflows.turn_jd_changes import TurnJdChangesWorkflow

router = APIRouter(prefix="/api/job-files/{job_file_id}/consultant-turns", tags=["job-description"])


def get_turn_jd_changes(request: Request, response: Response) -> TurnJdChangesWorkflow:
    response.headers["Cache-Control"] = "no-store"
    workflow = getattr(request.app.state, "turn_jd_changes_workflow", None)
    if not isinstance(workflow, TurnJdChangesWorkflow):
        raise HTTPException(status_code=503, detail={"code": "database_not_configured"})
    return workflow


@router.get("/{execution_id}/jd-changes", response_model=TurnJdChanges)
async def read_turn_jd_changes(
    job_file_id: UUID,
    execution_id: UUID,
    request: Request,
    workflow: Annotated[TurnJdChangesWorkflow, Depends(get_turn_jd_changes)],
) -> TurnJdChanges:
    if request.query_params or await request.body():
        raise HTTPException(status_code=422, detail={"code": "unexpected_jd_changes_arguments"})
    try:
        before, after = await workflow.read(job_file_id, execution_id)
    except ExecutionNotFoundError as error:
        raise HTTPException(
            status_code=404, detail={"code": "consultant_turn_not_found"}
        ) from error
    except (ExecutionStateError, JdChangeHistoryUnavailableError) as error:
        raise HTTPException(status_code=409, detail={"code": "jd_changes_unavailable"}) from error
    return TurnJdChanges(execution_id=execution_id, markdown=project_turn_jd_changes(before, after))
