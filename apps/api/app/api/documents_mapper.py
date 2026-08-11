"""Domain/wire mapping for document/header/Duty/Task transport seam."""

from job_analysis_contract import (
    DocumentMetadataView,
    DocumentReadinessView,
    DocumentSummary as WireDocumentSummary,
    DocumentView,
    DutyView,
    DutyWrite,
    JdHeaderView,
    JdHeaderWrite,
    JdTaskView,
    JdTaskWrite,
    ReadinessIssueView,
)

from app.api.opks_mapper import to_opks_item_view, to_opks_task_status
from app.core.domain import (
    Duty,
    Enabler,
    EnablerKind,
    JdHeader,
    JdTask,
    JdTaskFields,
    ResponsibilityRole,
)
from app.core.persistence import DocumentRecord, DocumentSummary, LoadedDocument
from app.documents import DocumentReadiness, assess_readiness


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def to_jd_header(body: JdHeaderWrite) -> JdHeader:
    return JdHeader(
        competency_name=_optional_text(body.competency_name),
        occupation_category_name=_optional_text(body.occupation_category_name),
        occupation_name=_optional_text(body.occupation_name),
        occupation_code=_optional_text(body.occupation_code),
        industry_name=_optional_text(body.industry_name),
        industry_code=_optional_text(body.industry_code),
        work_description=_optional_text(body.work_description),
        competency_level=body.competency_level,
        notes=_optional_text(body.notes),
    )


def to_jd_header_view(header: JdHeader) -> JdHeaderView:
    return JdHeaderView(
        competency_name=header.competency_name,
        occupation_category_name=header.occupation_category_name,
        occupation_name=header.occupation_name,
        occupation_code=header.occupation_code,
        industry_name=header.industry_name,
        industry_code=header.industry_code,
        work_description=header.work_description,
        competency_level=header.competency_level,
        notes=header.notes,
    )


def to_duty_statement(body: DutyWrite) -> str:
    return body.statement.strip()


def to_duty_view(duty: Duty) -> DutyView:
    return DutyView(
        duty_id=duty.duty_id,
        statement=duty.statement,
        display_order=duty.display_order,
    )


def to_document_readiness_view(
    readiness: DocumentReadiness,
) -> DocumentReadinessView:
    return DocumentReadinessView(
        issues=[ReadinessIssueView(code=issue.code.value) for issue in readiness.issues]
    )


def to_jd_task_fields(body: JdTaskWrite) -> JdTaskFields:
    role_value = (
        body.responsibility_role.value
        if body.responsibility_role is not None
        else None
    )
    return JdTaskFields(
        statement=body.statement.strip(),
        purpose_result=_optional_text(body.purpose_result),
        context=_optional_text(body.context),
        frequency_text=_optional_text(body.frequency_text),
        responsibility_role=(
            ResponsibilityRole(role_value) if role_value else None
        ),
        enablers=tuple(
            Enabler(
                kind=EnablerKind(item.kind.value),
                name=item.name.strip(),
            )
            for item in body.enablers
        ),
        duty_id=_optional_text(body.duty_id),
        competency_level=body.competency_level,
    )


def to_document_metadata_view(record: DocumentRecord) -> DocumentMetadataView:
    return DocumentMetadataView(
        document_id=record.document_id,
        title=record.title,
        updated_at=record.updated_at,
    )


def to_document_summary(summary: DocumentSummary) -> WireDocumentSummary:
    return WireDocumentSummary(
        document_id=summary.document_id,
        title=summary.title,
        task_count=summary.task_count,
        updated_at=summary.updated_at,
    )


def to_jd_task_view(task: JdTask) -> JdTaskView:
    return JdTaskView.model_validate(
        {
            "task_id": task.task_id,
            "statement": task.statement,
            "purpose_result": task.purpose_result,
            "context": task.context,
            "frequency_text": task.frequency_text,
            "responsibility_role": (
                task.responsibility_role.value
                if task.responsibility_role is not None
                else None
            ),
            "enablers": [
                {"kind": enabler.kind.value, "name": enabler.name}
                for enabler in task.enablers
            ],
            "duty_id": task.duty_id,
            "competency_level": task.competency_level,
            "display_order": task.display_order,
        }
    )


def to_document_view(loaded: LoadedDocument) -> DocumentView:
    return DocumentView(
        document_id=loaded.document.document_id,
        title=loaded.document.title,
        updated_at=loaded.document.updated_at,
        jd_header=to_jd_header_view(loaded.state.jd_header),
        readiness=to_document_readiness_view(
            assess_readiness(
                header=loaded.state.jd_header,
                duties=loaded.state.current_duties,
                tasks=loaded.state.current_jd,
                current_opks=loaded.state.current_opks,
            )
        ),
        duties=[to_duty_view(duty) for duty in loaded.state.current_duties],
        tasks=[to_jd_task_view(task) for task in loaded.state.current_jd],
        opks_items=[
            to_opks_item_view(item) for item in loaded.state.current_opks.items
        ],
        opks_task_status=to_opks_task_status(loaded.state),
    )
