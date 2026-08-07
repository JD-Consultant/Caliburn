"""Local Web document, Current JD, and consultant-loop transport routes."""

import logging
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response
from job_analysis_contract import (
    DocumentMetadataView,
    DocumentMetadataWrite,
    DocumentSummary,
    DocumentView,
    DutyOrderWrite,
    DutyView,
    DutyWrite,
    ConsultationView,
    EmployeeTurnWrite,
    JdHeaderView,
    JdHeaderWrite,
    JdTaskView,
    JdTaskWrite,
    OpksGenerationView,
    OpksItemView,
    OpksItemWrite,
    OpksOrderWrite,
    OpksProposalDecisionWrite,
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
    to_duty_view,
    to_jd_header,
    to_jd_header_view,
    to_jd_task_fields,
    to_jd_task_view,
    to_opks_generation_view,
    to_opks_item_view,
    to_opks_proposal_decision,
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
    assemble_export_document,
    assess_readiness,
    OpksGroundingUnavailable,
    TransitionCommitRejected,
    UncommittableOperationResult,
    add_duty,
    add_jd_task,
    add_opks_item,
    delete_duty,
    delete_jd_task,
    delete_opks_item,
    edit_duty,
    edit_jd_task,
    edit_opks_item,
    generate_opks_proposals,
    list_documents,
    load_document,
    decide_proposal,
    decide_opks_proposal,
    put_document_metadata,
    put_jd_header,
    reorder_duties,
    reorder_jd_tasks,
    reorder_opks_items,
    submit_employee_turn,
)
from app.job_analysis.application.errors import JobAnalysisApplicationError
from app.job_analysis.application.export_xlsx import XLSX_MEDIA_TYPE, render_xlsx
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


def export_filename(title: str) -> str:
    """`Content-Disposition` 的檔名。

    中文標題不能直接放進 `filename=`——那個欄位只認 ASCII，瀏覽器會存成亂碼。
    RFC 6266／5987 的做法是同時給 ASCII fallback 與百分比編碼的 `filename*`。
    """

    cleaned = "".join(
        character
        for character in title
        if character not in '\\/:*?"<>|' and character.isprintable()
    ).strip()
    encoded = quote(f"{cleaned or 'job-description'}.xlsx", safe="")
    return f"attachment; filename=\"export.xlsx\"; filename*=UTF-8\'\'{encoded}"


@router.get("/{document_id}/export")
async def export_document(
    document_id: UUID,
    uow_factory: JobAnalysisUnitOfWorkFactory = Depends(
        get_job_analysis_uow_factory
    ),
):
    """匯出 XLSX。**永遠放行**——缺漏不阻擋匯出（ADR 0052 決定 5／0058 決定 11），
    缺漏由檔案裡的第二張工作表呈現。GET 無副作用，不需要 `Idempotency-Key`。
    """

    loaded = await load_document(uow_factory, document_id)
    if loaded is None:
        return problem_response(
            type_uri=DOCUMENT_NOT_FOUND,
            title="Document not found",
            status=404,
        )
    state = loaded.state
    payload = render_xlsx(
        assemble_export_document(state, title=loaded.document.title),
        assess_readiness(
            header=state.jd_header,
            duties=state.current_duties,
            tasks=state.current_jd,
        ),
    )
    return Response(
        content=payload,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": export_filename(loaded.document.title)},
    )


@router.put("/{document_id}/jd-header", response_model=JdHeaderView)
async def put_jd_header_route(
    document_id: UUID,
    body: JdHeaderWrite,
    idempotency_key: IdempotencyKey,
    uow_factory: JobAnalysisUnitOfWorkFactory = Depends(
        get_job_analysis_uow_factory
    ),
):
    try:
        header = await put_jd_header(
            uow_factory,
            document_id=document_id,
            entry_id=idempotency_key,
            header=to_jd_header(body),
        )
    except ValidationError as error:
        return domain_validation_error_response(error)
    except JobAnalysisApplicationError as error:
        return application_error_response(error)
    return to_jd_header_view(header)


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
            "job-analysis consultant turn was not committable: %s: %s",
            type(error).__name__,
            error,
        )
        return consultant_unavailable_response()
    except JobAnalysisApplicationError as error:
        return application_error_response(error)
    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    return to_consultation_view(loaded)


@router.post(
    "/{document_id}/tasks/{task_id}/opks-proposals",
    response_model=OpksGenerationView,
)
async def post_opks_generation(
    document_id: UUID,
    task_id: str,
    idempotency_key: IdempotencyKey,
    uow_factory: JobAnalysisUnitOfWorkFactory = Depends(
        get_job_analysis_uow_factory
    ),
    adapter: OpenRouterAdapter = Depends(get_job_analysis_adapter),
):
    try:
        result = await generate_opks_proposals(
            uow_factory,
            adapter=adapter,
            document_id=document_id,
            task_id=task_id,
            operation_id=idempotency_key,
        )
    except (UncommittableOperationResult, OpksGroundingUnavailable) as error:
        logger.warning(
            "job-analysis OPKS generation was not committable: %s",
            type(error).__name__,
        )
        return consultant_unavailable_response()
    except JobAnalysisApplicationError as error:
        return application_error_response(error)
    return to_opks_generation_view(result)


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


@router.post("/{document_id}/duties", response_model=DutyView, status_code=201)
async def add_duty_route(
    document_id: UUID,
    body: DutyWrite,
    idempotency_key: IdempotencyKey,
    uow_factory: JobAnalysisUnitOfWorkFactory = Depends(
        get_job_analysis_uow_factory
    ),
):
    try:
        duty = await add_duty(
            uow_factory,
            document_id=document_id,
            entry_id=idempotency_key,
            statement=body.statement.strip(),
        )
    except ValidationError as error:
        return domain_validation_error_response(error)
    except JobAnalysisApplicationError as error:
        return application_error_response(error)
    return to_duty_view(duty)


@router.put("/{document_id}/duties/{duty_id}", response_model=DutyView)
async def edit_duty_route(
    document_id: UUID,
    duty_id: str,
    body: DutyWrite,
    idempotency_key: IdempotencyKey,
    uow_factory: JobAnalysisUnitOfWorkFactory = Depends(
        get_job_analysis_uow_factory
    ),
):
    try:
        duty = await edit_duty(
            uow_factory,
            document_id=document_id,
            entry_id=idempotency_key,
            duty_id=duty_id,
            statement=body.statement.strip(),
        )
    except ValidationError as error:
        return domain_validation_error_response(error)
    except JobAnalysisApplicationError as error:
        return application_error_response(error)
    return to_duty_view(duty)


@router.delete("/{document_id}/duties/{duty_id}", status_code=204)
async def delete_duty_route(
    document_id: UUID,
    duty_id: str,
    idempotency_key: IdempotencyKey,
    uow_factory: JobAnalysisUnitOfWorkFactory = Depends(
        get_job_analysis_uow_factory
    ),
):
    """204。哪幾條 Task 因此變成未指派，客戶端重讀文件就看得到，不另開回應形狀。"""

    try:
        await delete_duty(
            uow_factory,
            document_id=document_id,
            entry_id=idempotency_key,
            duty_id=duty_id,
        )
    except JobAnalysisApplicationError as error:
        return application_error_response(error)
    return Response(status_code=204)


@router.put("/{document_id}/duty-order", response_model=list[DutyView])
async def reorder_duties_route(
    document_id: UUID,
    body: DutyOrderWrite,
    idempotency_key: IdempotencyKey,
    uow_factory: JobAnalysisUnitOfWorkFactory = Depends(
        get_job_analysis_uow_factory
    ),
):
    try:
        duties = await reorder_duties(
            uow_factory,
            document_id=document_id,
            entry_id=idempotency_key,
            ordered_duty_ids=tuple(body.ordered_duty_ids),
        )
    except JobAnalysisApplicationError as error:
        return application_error_response(error)
    return [to_duty_view(duty) for duty in duties]


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


@router.put("/{document_id}/opks-order", response_model=list[OpksItemView])
async def reorder_opks(
    document_id: UUID,
    body: OpksOrderWrite,
    idempotency_key: IdempotencyKey,
    uow_factory: JobAnalysisUnitOfWorkFactory = Depends(
        get_job_analysis_uow_factory
    ),
):
    """重排單一 kind。O 只跟 O 換位置——範圍與 `display_order` 的唯一性一致。"""

    try:
        items = await reorder_opks_items(
            uow_factory,
            document_id=document_id,
            entry_id=idempotency_key,
            entity_kind=body.entity_kind.value,
            ordered_entity_ids=tuple(body.ordered_entity_ids),
        )
    except ValidationError as error:
        return domain_validation_error_response(error)
    except JobAnalysisApplicationError as error:
        return application_error_response(error)
    return [to_opks_item_view(item) for item in items]


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
