"""Consultant-loop transport routes: consultation view, employee turns, Task
Proposal decisions."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from job_analysis_contract import (
    ConsultationView,
    EmployeeTurnWrite,
    ProblemFieldError,
    ProposalDecisionWrite,
)
from pydantic import ValidationError

from app.adapters.openrouter import OpenRouterAdapter
from app.api.consultation_mapper import to_consultation_view, to_proposal_decision
from app.api.deps import get_job_analysis_adapter, get_job_analysis_uow_factory
from app.api.problems import (
    DOCUMENT_NOT_FOUND,
    INVALID_REQUEST,
    application_error_response,
    consultant_unavailable_response,
    domain_validation_error_response,
    problem_response,
)
from app.consultation import (
    TransitionCommitRejected,
    UncommittableOperationResult,
    submit_employee_turn,
)
from app.core.errors import JobAnalysisApplicationError
from app.core.persistence import JobAnalysisUnitOfWorkFactory
from app.documents import load_document
from app.task_analysis import decide_proposal


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/job-analysis/documents", tags=["job-analysis"])
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1),
]


@router.get("/{document_id}/consultation", response_model=ConsultationView)
async def get_consultation(
    document_id: UUID,
    uow_factory: JobAnalysisUnitOfWorkFactory = Depends(
        get_job_analysis_uow_factory
    ),
):
    loaded = await load_document(uow_factory, document_id)
    if loaded is None:
        return problem_response(
            type_uri=DOCUMENT_NOT_FOUND,
            title="Document not found",
            status=404,
        )
    return to_consultation_view(loaded)


@router.post("/{document_id}/turns", response_model=ConsultationView)
async def post_employee_turn(
    document_id: UUID,
    body: EmployeeTurnWrite,
    idempotency_key: IdempotencyKey,
    uow_factory: JobAnalysisUnitOfWorkFactory = Depends(
        get_job_analysis_uow_factory
    ),
    adapter: OpenRouterAdapter = Depends(get_job_analysis_adapter),
):
    text = body.text.strip()
    if not text:
        return problem_response(
            type_uri=INVALID_REQUEST,
            title="Invalid request",
            status=422,
            errors=[
                ProblemFieldError(
                    field="text",
                    message="Employee response cannot be blank.",
                )
            ],
        )
    try:
        await submit_employee_turn(
            uow_factory,
            task_analysis_adapter=adapter,
            opks_adapter=adapter,
            document_id=document_id,
            operation_id=idempotency_key,
            text=text,
        )
    except (UncommittableOperationResult, TransitionCommitRejected) as error:
        if isinstance(error, UncommittableOperationResult):
            logger.warning(
                "job-analysis consultant turn was not committable: %s "
                "outcome=%s verifier_codes=%s",
                type(error).__name__,
                error.outcome.value,
                ",".join(error.verifier_codes) or "none",
            )
        else:
            logger.warning(
                "job-analysis consultant turn was not committable: %s",
                type(error).__name__,
            )
        return consultant_unavailable_response()
    except JobAnalysisApplicationError as error:
        return application_error_response(error)
    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    return to_consultation_view(loaded)


# `POST /{document_id}/tasks/{task_id}/opks-proposals` 已退役(ADR 0054 決定 1)。
#
# **不得復活。** OPKS 的唯一 AI 入口是主回合排定的 child(`submit_employee_turn`);
# 員工不需要理解 OPKS 階段的存在,也不該由他判斷哪個 Task 已經談夠、何時該按。
# 員工手動新增／編輯／刪除 O/P/K/S 的端點保留——那不是 AI 入口。


@router.post(
    "/{document_id}/proposals/{proposal_id}/decisions",
    response_model=ConsultationView,
)
async def post_proposal_decision(
    document_id: UUID,
    proposal_id: str,
    body: ProposalDecisionWrite,
    idempotency_key: IdempotencyKey,
    uow_factory: JobAnalysisUnitOfWorkFactory = Depends(
        get_job_analysis_uow_factory
    ),
):
    try:
        decision, edited_jd_after, reason = to_proposal_decision(body)
        await decide_proposal(
            uow_factory,
            document_id=document_id,
            proposal_id=proposal_id,
            decision_id=idempotency_key,
            decision=decision,
            edited_jd_after=edited_jd_after,
            reason=reason,
        )
    except ValidationError as error:
        return domain_validation_error_response(error)
    except JobAnalysisApplicationError as error:
        return application_error_response(error)
    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    return to_consultation_view(loaded)
