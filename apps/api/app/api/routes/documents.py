"""Document/header/Duty/Task CRUD and order routes."""

from typing import Annotated
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
    JdHeaderView,
    JdHeaderWrite,
    JdTaskView,
    JdTaskWrite,
    ProblemFieldError,
    TaskOrderWrite,
)
from pydantic import ValidationError

from app.api.deps import get_job_analysis_uow_factory
from app.api.documents_mapper import (
    to_document_metadata_view,
    to_document_summary,
    to_document_view,
    to_duty_statement,
    to_duty_view,
    to_jd_header,
    to_jd_header_view,
    to_jd_task_fields,
    to_jd_task_view,
)
from app.api.problems import (
    DOCUMENT_NOT_FOUND,
    INVALID_REQUEST,
    application_error_response,
    domain_validation_error_response,
    problem_response,
)
from app.core.errors import JobAnalysisApplicationError
from app.core.persistence import JobAnalysisUnitOfWorkFactory
from app.documents import (
    add_duty,
    add_jd_task,
    delete_duty,
    delete_jd_task,
    edit_duty,
    edit_jd_task,
    list_documents,
    load_document,
    put_document_metadata,
    put_jd_header,
    reorder_duties,
    reorder_jd_tasks,
)


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
            statement=to_duty_statement(body),
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
            statement=to_duty_statement(body),
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
async def reorder_duty_route(
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
