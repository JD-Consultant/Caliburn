"""Explicit mapping between job-analysis domain records and wire DTOs."""

from job_analysis_contract import (
    DocumentMetadataView,
    DocumentSummary as WireDocumentSummary,
    DocumentView,
    JdTaskView,
)

from app.job_analysis.application import (
    DocumentRecord,
    DocumentSummary,
    LoadedDocument,
)
from app.job_analysis.domain import JdTask


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
