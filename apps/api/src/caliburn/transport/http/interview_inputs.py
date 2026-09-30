"""Input acceptance only; no public endpoint grants formal source eligibility."""

from collections.abc import Callable
from dataclasses import asdict
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from caliburn.contracts.generated.accepted_interview_input import AcceptedInterviewInput
from caliburn.contracts.generated.submit_interview_input import SubmitInterviewInput
from caliburn.features.executions.models import ExecutionBusyError, ExecutionKind, ExecutionScope
from caliburn.features.interviews.models import InputCommandConflictError
from caliburn.features.interviews.models import SubmitInterviewInput as InputCommand
from caliburn.features.job_files.models import JobFileNotFoundError
from caliburn.workflows.consultant_supervisor import ConsultantSupervisor
from caliburn.workflows.interview_inputs import InterviewInputWorkflow

router = APIRouter(prefix="/api/job-files", tags=["interviews"])


def get_interview_input_workflow(request: Request) -> InterviewInputWorkflow:
    workflow = request.app.state.interview_input_workflow
    if not isinstance(workflow, InterviewInputWorkflow):
        raise HTTPException(status_code=503, detail={"code": "database_not_configured"})
    return workflow


InterviewInputs = Annotated[InterviewInputWorkflow, Depends(get_interview_input_workflow)]


class ConsultantUnavailable(StrEnum):
    MODEL_NOT_CONFIGURED = "model_not_configured"
    STOPPED = "consultant_unavailable"


def get_consultant_dispatch(
    request: Request,
) -> Callable[[ExecutionScope], None] | ConsultantUnavailable:
    """Report availability; only new admission is gated on this result."""
    supervisor = getattr(request.app.state, "consultant_supervisor", None)
    if not isinstance(supervisor, ConsultantSupervisor):
        return ConsultantUnavailable.MODEL_NOT_CONFIGURED
    if not supervisor.running:
        return ConsultantUnavailable.STOPPED
    return supervisor.notify


ConsultantDispatch = Annotated[
    Callable[[ExecutionScope], None] | ConsultantUnavailable, Depends(get_consultant_dispatch)
]


@router.post(
    "/{job_file_id}/inputs",
    status_code=202,
    response_model=AcceptedInterviewInput,
    responses={200: {"model": AcceptedInterviewInput}},
)
async def submit_interview_input(
    job_file_id: UUID,
    body: SubmitInterviewInput,
    response: Response,
    workflow: InterviewInputs,
    dispatch: ConsultantDispatch,
) -> AcceptedInterviewInput:
    try:
        command = InputCommand(job_file_id, body.command_id, body.text)
        result = await workflow.read_accepted(command)
        if result is None:
            if isinstance(dispatch, ConsultantUnavailable):
                raise HTTPException(status_code=503, detail={"code": dispatch.value})
            result = await workflow.accept(command)
            if result.is_new:
                dispatch(
                    ExecutionScope(
                        job_file_id, result.accepted.execution_id, ExecutionKind.CONSULTANT_TURN
                    )
                )
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error
    except InputCommandConflictError as error:
        raise HTTPException(status_code=409, detail={"code": "input_command_conflict"}) from error
    except ExecutionBusyError as error:
        raise HTTPException(status_code=409, detail={"code": "consultant_turn_active"}) from error
    response.status_code = 202 if result.is_new else 200
    return AcceptedInterviewInput.model_validate(asdict(result.accepted))
