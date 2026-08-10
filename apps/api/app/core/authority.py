"""One atomic write seam for validated job-analysis authority changes."""

from __future__ import annotations

from datetime import datetime

from app.core.errors import ConcurrentAuthorityChange
from app.core.journal import JournalEntry
from app.core.persistence import (
    DocumentRecord,
    JobAnalysisUnitOfWork,
)
from app.core.state import JobAnalysisState


async def commit_authority_change(
    uow: JobAnalysisUnitOfWork,
    *,
    record: DocumentRecord,
    state: JobAnalysisState,
    updated_at: datetime,
    journal_entries: tuple[JournalEntry, ...] = (),
) -> None:
    """Validate the complete state, then persist it in the caller's UoW."""

    validated = JobAnalysisState.model_validate(state.model_dump())
    await uow.duties.replace(record.document_id, validated.current_duties)
    await uow.tasks.replace(record.document_id, validated.current_jd)
    await uow.proposals.replace(record.document_id, validated.proposals)
    await uow.opks.replace(record.document_id, validated.current_opks.items)
    await uow.opks_proposals.replace(
        record.document_id,
        validated.opks_proposals,
    )
    for journal_entry in journal_entries:
        await uow.journal.add(journal_entry)
    updated = await uow.documents.update_authority(
        record.document_id,
        expected_generation=record.authority_generation,
        jd_header=validated.jd_header,
        work_model=validated.work_model,
        active_question=record.active_question,
        updated_at=updated_at,
    )
    if not updated:
        raise ConcurrentAuthorityChange(
            f"document {record.document_id} authority changed concurrently"
        )
    await uow.commit()
