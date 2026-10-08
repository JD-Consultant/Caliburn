"""Read-only adopted plan projection; its workflow owns formal qualification and storage."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from caliburn.contracts.generated.interview_plan_view import InterviewPlanView
from caliburn.features.interview_plans.models import PlanStateError
from caliburn.features.job_files.models import JobFileNotFoundError
from caliburn.workflows.interview_plans import InterviewPlanReadWorkflow

router = APIRouter(prefix="/api/job-files", tags=["interviews"])


def get_interview_plan_read_workflow(request: Request) -> InterviewPlanReadWorkflow:
    workflow = getattr(request.app.state, "interview_plan_read_workflow", None)
    if not isinstance(workflow, InterviewPlanReadWorkflow):
        raise HTTPException(status_code=503, detail={"code": "database_not_configured"})
    return workflow


InterviewPlans = Annotated[InterviewPlanReadWorkflow, Depends(get_interview_plan_read_workflow)]


@router.get("/{job_file_id}/interview-plan", response_model=InterviewPlanView)
async def read_adopted_interview_plan(
    job_file_id: UUID, response: Response, workflow: InterviewPlans
) -> InterviewPlanView:
    response.headers["Cache-Control"] = "no-store"
    try:
        snapshot = await workflow.read_adopted(job_file_id)
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error
    except PlanStateError as error:
        raise HTTPException(
            status_code=503, detail={"code": "interview_plan_unavailable"}
        ) from error
    return InterviewPlanView.model_validate(
        {"job_file_id": job_file_id, "plan": snapshot.body if snapshot is not None else None}
    )
