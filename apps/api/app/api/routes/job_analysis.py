"""Local Web document, Current JD, and consultant-loop transport routes."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response
from job_analysis_contract import (
    DocumentMetadataView,
    DocumentMetadataWrite,
    DocumentSummary,
    DocumentView,
    ConsultationView,
    EmployeeTurnWrite,
    JdTaskView,
    JdTaskWrite,
    OpksItemView,
    OpksItemWrite,
    ProblemFieldError,
    ProposalDecisionWrite,
    TaskOrderWrite,
)
from pydantic import ValidationError

from app.api.deps import get_job_analysis_adapter, get_job_analysis_uow_factory
from app.api.job_analysis_mapper import (
    to_document_metadata_view,
    to_document_summary,
    to_document_view,
    to_jd_task_fields,
    to_jd_task_view,
    to_opks_item_view,
    to_opks_write,
    to_consultation_view,
    to_proposal_decision,
)
from app.api.job_analysis_problems import (
    DOCUMENT_NOT_FOUND,
    INVALID_REQUEST,
    application_error_response,
    consultant_unavailable_response,
    domain_validation_error_response,
    problem_response,
)
from app.job_analysis.application import (
    JobAnalysisUnitOfWorkFactory,
    TransitionCommitRejected,
    UncommittableOperationResult,
    add_jd_task,
    add_opks_item,
    delete_jd_task,
    delete_opks_item,
    edit_jd_task,
    edit_opks_item,
    list_documents,
    load_document,
    decide_proposal,
    put_document_metadata,
    reorder_jd_tasks,
    submit_employee_turn,
)
from app.job_analysis.application.errors import JobAnalysisApplicationError
from app.job_analysis.providers import OpenRouterAdapter


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/job-analysis/documents", tags=["job-analysis"])
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1),
]


@router.get("", response_model=list[DocumentSummary])
async def get_documents(
    uow_factory: JobAnalysisUnitOfWorkFactory = Depends(
        get_job_analysis_uow_factory
    ),
):
    summaries = await list_documents(uow_factory)
    return [to_document_summary(summary) for summary in summaries]


@router.put("/{document_id}", response_model=DocumentMetadataView)
async def put_document(
    document_id: UUID,
    body: DocumentMetadataWrite,
    response: Response,
    uow_factory: JobAnalysisUnitOfWorkFactory = Depends(
        get_job_analysis_uow_factory
    ),
):
    title = body.title.strip()
    if not title:
        return problem_response(
            type_uri=INVALID_REQUEST,
            title="Invalid request",
            status=422,
            detail="Document title cannot be blank.",
            errors=[
                ProblemFieldError(
                    field="title",
                    message="Document title cannot be blank.",
                )
            ],
        )
    result = await put_document_metadata(
        uow_factory,
        document_id=document_id,
        title=title,
    )
    response.status_code = 201 if result.created else 200
    return to_document_metadata_view(result.document)


@router.get("/{document_id}", response_model=DocumentView)
async def get_document(
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
    return to_document_view(loaded)


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
            adapter=adapter,
            document_id=document_id,
            operation_id=idempotency_key,
            text=text,
        )
    except (UncommittableOperationResult, TransitionCommitRejected) as error:
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


@router.post("/{document_id}/tasks", response_model=JdTaskView, status_code=201)
async def add_task(
    document_id: UUID,
    body: JdTaskWrite,
    idempotency_key: IdempotencyKey,
    uow_factory: JobAnalysisUnitOfWorkFactory = Depends(
        get_job_analysis_uow_factory
    ),
):
    try:
        task = await add_jd_task(
            uow_factory,
            document_id=document_id,
            entry_id=idempotency_key,
            fields=to_jd_task_fields(body),
        )
    except ValidationError as error:
        return domain_validation_error_response(error)
    except JobAnalysisApplicationError as error:
        return application_error_response(error)
    return to_jd_task_view(task)


@router.put("/{document_id}/tasks/{task_id}", response_model=JdTaskView)
async def edit_task(
    document_id: UUID,
    task_id: str,
    body: JdTaskWrite,
    idempotency_key: IdempotencyKey,
    uow_factory: JobAnalysisUnitOfWorkFactory = Depends(
        get_job_analysis_uow_factory
    ),
):
    try:
        task = await edit_jd_task(
            uow_factory,
            document_id=document_id,
            entry_id=idempotency_key,
            task_id=task_id,
            fields=to_jd_task_fields(body),
        )
    except ValidationError as error:
        return domain_validation_error_response(error)
    except JobAnalysisApplicationError as error:
        return application_error_response(error)
    return to_jd_task_view(task)


@router.delete("/{document_id}/tasks/{task_id}", status_code=204)
async def delete_task(
    document_id: UUID,
    task_id: str,
    idempotency_key: IdempotencyKey,
    uow_factory: JobAnalysisUnitOfWorkFactory = Depends(
        get_job_analysis_uow_factory
    ),
):
    try:
        await delete_jd_task(
            uow_factory,
            document_id=document_id,
            entry_id=idempotency_key,
            task_id=task_id,
        )
    except JobAnalysisApplicationError as error:
        return application_error_response(error)
    return Response(status_code=204)


@router.post("/{document_id}/opks", response_model=OpksItemView, status_code=201)
async def add_opks(
    document_id: UUID,
    body: OpksItemWrite,
    idempotency_key: IdempotencyKey,
    uow_factory: JobAnalysisUnitOfWorkFactory = Depends(
        get_job_analysis_uow_factory
    ),
):
    try:
        entity_kind, text, task_refs, indicator_refs = to_opks_write(body)
        item = await add_opks_item(
            uow_factory,
            document_id=document_id,
            entry_id=idempotency_key,
            entity_kind=entity_kind,
            text=text,
            task_refs=task_refs,
            indicator_refs=indicator_refs,
        )
    except ValidationError as error:
        return domain_validation_error_response(error)
    except JobAnalysisApplicationError as error:
        return application_error_response(error)
    return to_opks_item_view(item)


@router.put("/{document_id}/opks/{entity_id}", response_model=OpksItemView)
async def edit_opks(
    document_id: UUID,
    entity_id: str,
    body: OpksItemWrite,
    idempotency_key: IdempotencyKey,
    uow_factory: JobAnalysisUnitOfWorkFactory = Depends(
        get_job_analysis_uow_factory
    ),
):
    try:
        entity_kind, text, task_refs, indicator_refs = to_opks_write(body)
        item = await edit_opks_item(
            uow_factory,
            document_id=document_id,
            entry_id=idempotency_key,
            entity_id=entity_id,
            entity_kind=entity_kind,
            text=text,
            task_refs=task_refs,
            indicator_refs=indicator_refs,
        )
    except ValidationError as error:
        return domain_validation_error_response(error)
    except ValueError as error:
        return problem_response(
            type_uri=INVALID_REQUEST,
            title="Invalid request",
            status=422,
            detail=str(error),
        )
    except JobAnalysisApplicationError as error:
        return application_error_response(error)
    return to_opks_item_view(item)


@router.delete("/{document_id}/opks/{entity_id}", status_code=204)
async def delete_opks(
    document_id: UUID,
    entity_id: str,
    idempotency_key: IdempotencyKey,
    uow_factory: JobAnalysisUnitOfWorkFactory = Depends(
        get_job_analysis_uow_factory
    ),
):
    try:
        await delete_opks_item(
            uow_factory,
            document_id=document_id,
            entry_id=idempotency_key,
            entity_id=entity_id,
        )
    except JobAnalysisApplicationError as error:
        return application_error_response(error)
    return Response(status_code=204)


@router.put("/{document_id}/task-order", response_model=list[JdTaskView])
async def reorder_tasks(
    document_id: UUID,
    body: TaskOrderWrite,
    idempotency_key: IdempotencyKey,
    uow_factory: JobAnalysisUnitOfWorkFactory = Depends(
        get_job_analysis_uow_factory
    ),
):
    try:
        tasks = await reorder_jd_tasks(
            uow_factory,
            document_id=document_id,
            entry_id=idempotency_key,
            ordered_task_ids=tuple(body.ordered_task_ids),
        )
    except JobAnalysisApplicationError as error:
        return application_error_response(error)
    return [to_jd_task_view(task) for task in tasks]
