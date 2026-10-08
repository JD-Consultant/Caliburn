"""Undo the JD effects of one completed Turn, never accept a client-selected old revision."""

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from caliburn.contracts.generated.jd_profile_view import JdProfileView
from caliburn.features.executions.models import (
    ExecutionBusyError,
    ExecutionNotFoundError,
    ExecutionStateError,
)
from caliburn.features.job_description.candidates import CandidateStateError
from caliburn.features.job_description.models import JdCommandConflictError, StaleJdRevisionError
from caliburn.features.job_files.models import JobFileNotFoundError
from caliburn.workflows.jd_undo import JdUndoUnconfirmedError, JdUndoWorkflow

router = APIRouter(prefix="/api/job-files/{job_file_id}/consultant-turns", tags=["job-description"])


def get_jd_undo_workflow(request: Request) -> JdUndoWorkflow:
    workflow = getattr(request.app.state, "jd_undo_workflow", None)
    if not isinstance(workflow, JdUndoWorkflow):
        raise HTTPException(status_code=503, detail={"code": "database_not_configured"})
    return workflow


@router.post("/{execution_id}/undo-jd", response_model=JdProfileView)
async def undo_completed_jd(
    job_file_id: UUID,
    execution_id: UUID,
    request: Request,
    workflow: Annotated[JdUndoWorkflow, Depends(get_jd_undo_workflow)],
) -> JdProfileView:
    if request.query_params or await request.body():
        raise HTTPException(status_code=422, detail={"code": "unexpected_undo_arguments"})
    try:
        result = await workflow.undo(job_file_id, execution_id)
    except (JobFileNotFoundError, ExecutionNotFoundError) as error:
        raise HTTPException(
            status_code=404, detail={"code": "consultant_turn_not_found"}
        ) from error
    except ExecutionBusyError as error:
        raise HTTPException(status_code=409, detail={"code": "consultant_turn_active"}) from error
    except (ExecutionStateError, CandidateStateError) as error:
        raise HTTPException(status_code=409, detail={"code": "jd_undo_unavailable"}) from error
    except StaleJdRevisionError as error:
        raise HTTPException(status_code=409, detail={"code": "jd_undo_conflict"}) from error
    except JdCommandConflictError as error:
        raise HTTPException(status_code=409, detail={"code": "jd_command_conflict"}) from error
    except JdUndoUnconfirmedError as error:
        raise HTTPException(status_code=503, detail={"code": "jd_undo_unconfirmed"}) from error
    return JdProfileView.model_validate(asdict(result))
