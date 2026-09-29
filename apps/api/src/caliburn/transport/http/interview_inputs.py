"""Input acceptance only; no public endpoint grants formal source eligibility."""

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from caliburn.contracts.generated.accepted_interview_input import AcceptedInterviewInput
from caliburn.contracts.generated.submit_interview_input import SubmitInterviewInput
from caliburn.features.executions.models import ExecutionBusyError
from caliburn.features.interviews.models import InputCommandConflictError
from caliburn.features.interviews.models import SubmitInterviewInput as InputCommand
from caliburn.features.job_files.models import JobFileNotFoundError
from caliburn.workflows.interview_inputs import InterviewInputWorkflow

router = APIRouter(prefix="/api/job-files", tags=["interviews"])


def get_interview_input_workflow(request: Request) -> InterviewInputWorkflow:
    workflow = request.app.state.interview_input_workflow
    if not isinstance(workflow, InterviewInputWorkflow):
        raise HTTPException(status_code=503, detail={"code": "database_not_configured"})
    return workflow


InterviewInputs = Annotated[InterviewInputWorkflow, Depends(get_interview_input_workflow)]


@router.post(
    "/{job_file_id}/inputs",
    status_code=202,
    response_model=AcceptedInterviewInput,
    responses={200: {"model": AcceptedInterviewInput}},
)
async def submit_interview_input(
    job_file_id: UUID, body: SubmitInterviewInput, response: Response, workflow: InterviewInputs
) -> AcceptedInterviewInput:
    try:
        result = await workflow.accept(InputCommand(job_file_id, body.command_id, body.text))
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error
    except InputCommandConflictError as error:
        raise HTTPException(status_code=409, detail={"code": "input_command_conflict"}) from error
    except ExecutionBusyError as error:
        raise HTTPException(status_code=409, detail={"code": "consultant_turn_active"}) from error
    response.status_code = 202 if result.is_new else 200
    return AcceptedInterviewInput.model_validate(asdict(result.accepted))
