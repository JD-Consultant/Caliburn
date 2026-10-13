"""Accepted originals and formal membership stay distinct in local inspection."""

from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import CompoundSelect, func, select, union_all

from caliburn.features.interviews import persistence


def exchange_projection(
    job_file_id: UUID, execution_id: UUID, *, include_text: bool
) -> CompoundSelect[dict[str, JsonValue]]:
    original = persistence.InterviewTextRecord
    formal = persistence.FormalInterviewRecord
    statements = []
    for owner, speaker in (
        (persistence.InterviewInputRecord, "employee"),
        (persistence.InterviewReplyRecord, "consultant"),
    ):
        fields = [
            "source_id",
            owner.source_id,
            "speaker",
            speaker,
            "sequence",
            formal.interview_sequence,
        ]
        if include_text:
            fields.extend(["text", original.interview_text])
        statement = (
            select(func.jsonb_build_object(*fields))
            .select_from(owner)
            .outerjoin(
                formal,
                (formal.job_file_id == owner.job_file_id) & (formal.source_id == owner.source_id),
            )
            .where(owner.job_file_id == job_file_id, owner.execution_id == execution_id)
        )
        if include_text:
            statement = statement.outerjoin(
                original,
                (original.job_file_id == owner.job_file_id)
                & (original.source_id == owner.source_id),
            )
        statements.append(statement)
    return union_all(*statements)
