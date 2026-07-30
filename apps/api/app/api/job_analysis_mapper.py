"""Explicit mapping between job-analysis domain records and wire DTOs."""

from job_analysis_contract import (
    DocumentMetadataView,
    DocumentSummary as WireDocumentSummary,
    DocumentView,
    JdTaskWrite,
    JdTaskView,
)

from app.job_analysis.application import (
    DocumentRecord,
    DocumentSummary,
    LoadedDocument,
)
from app.job_analysis.domain import (
    Enabler,
    EnablerKind,
    JdTask,
    JdTaskFields,
    ResponsibilityRole,
)


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


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
            "display_order": task.display_order,
        }
    )


def to_document_view(loaded: LoadedDocument) -> DocumentView:
    return DocumentView(
        document_id=loaded.document.document_id,
        title=loaded.document.title,
        updated_at=loaded.document.updated_at,
        tasks=[to_jd_task_view(task) for task in loaded.state.current_jd],
    )
