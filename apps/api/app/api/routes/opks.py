"""OPKS CRUD, order, and OPKS Proposal decision routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response
from job_analysis_contract import (
    ConsultationView,
    OpksItemView,
    OpksItemWrite,
    OpksOrderWrite,
    OpksProposalDecisionWrite,
)
from pydantic import ValidationError

from app.api.consultation_mapper import to_consultation_view
from app.api.deps import get_job_analysis_uow_factory
from app.api.opks_mapper import (
    to_opks_item_view,
    to_opks_proposal_decision,
    to_opks_write,
)
from app.api.problems import (
    INVALID_REQUEST,
    application_error_response,
    domain_validation_error_response,
    problem_response,
)
from app.core.errors import JobAnalysisApplicationError
from app.core.persistence import JobAnalysisUnitOfWorkFactory
from app.documents import load_document
from app.opks import (
    add_opks_item,
    decide_opks_proposal,
    delete_opks_item,
    edit_opks_item,
    reorder_opks_items,
)


router = APIRouter(prefix="/job-analysis/documents", tags=["job-analysis"])
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1),
]


@router.post(
    "/{document_id}/opks-proposals/{proposal_id}/decisions",
    response_model=ConsultationView,
)
async def post_opks_proposal_decision(
    document_id: UUID,
    proposal_id: str,
    body: OpksProposalDecisionWrite,
    idempotency_key: IdempotencyKey,
    uow_factory: JobAnalysisUnitOfWorkFactory = Depends(
        get_job_analysis_uow_factory
    ),
):
    try:
        decision, edited_text, reason = to_opks_proposal_decision(body)
        await decide_opks_proposal(
            uow_factory,
            document_id=document_id,
            proposal_id=proposal_id,
            decision_id=idempotency_key,
            decision=decision,
            edited_text=edited_text,
            reason=reason,
        )
    except ValidationError as error:
        return domain_validation_error_response(error)
    except JobAnalysisApplicationError as error:
        return application_error_response(error)
    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    return to_consultation_view(loaded)


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


@router.put("/{document_id}/opks-order", response_model=list[OpksItemView])
async def reorder_opks(
    document_id: UUID,
    body: OpksOrderWrite,
    idempotency_key: IdempotencyKey,
    uow_factory: JobAnalysisUnitOfWorkFactory = Depends(
        get_job_analysis_uow_factory
    ),
):
    try:
        items = await reorder_opks_items(
            uow_factory,
            document_id=document_id,
            entry_id=idempotency_key,
            entity_kind=body.entity_kind,
            ordered_entity_ids=tuple(body.ordered_entity_ids),
        )
    except JobAnalysisApplicationError as error:
        return application_error_response(error)
    return [to_opks_item_view(item) for item in items]
