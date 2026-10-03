"""Durable JD model aliases; domain object and citation identities remain UUIDs."""

from collections.abc import Collection
from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, Identity, Text, UniqueConstraint, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.adapters.database import Base


class JdModelReferenceRecord(Base):
    __tablename__ = "jd_model_references"
    __table_args__ = (UniqueConstraint("job_file_id", "canonical_ref"),)

    reference_number: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    job_file_id: Mapped[UUID] = mapped_column(ForeignKey("job_files.job_file_id"))
    canonical_ref: Mapped[str] = mapped_column(Text)

    @property
    def model_ref(self) -> str:
        return f"{self.canonical_ref.rsplit('_', 1)[0]}_{self.reference_number}"


async def assign_references(
    session: AsyncSession, job_file_id: UUID, canonical_refs: Collection[str]
) -> dict[str, str]:
    """Never update/recycle an alias, including deleted or abandoned candidate objects."""
    if not canonical_refs:
        return {}
    query = select(JdModelReferenceRecord).where(
        JdModelReferenceRecord.job_file_id == job_file_id,
        JdModelReferenceRecord.canonical_ref.in_(canonical_refs),
    )
    rows = list(await session.scalars(query))
    existing = {row.canonical_ref for row in rows}
    missing = sorted(set(canonical_refs) - existing)
    if missing:
        await session.execute(
            insert(JdModelReferenceRecord)
            .values([{"job_file_id": job_file_id, "canonical_ref": ref} for ref in missing])
            .on_conflict_do_nothing(index_elements=["job_file_id", "canonical_ref"])
        )
        # A separate SELECT sees a concurrent inserter after ON CONFLICT has waited.
        rows = list(await session.scalars(query))
    return {row.canonical_ref: row.model_ref for row in rows}


async def read_references(
    session: AsyncSession, job_file_id: UUID, reference_numbers: Collection[int]
) -> dict[str, str]:
    if not reference_numbers:
        return {}
    rows = await session.scalars(
        select(JdModelReferenceRecord).where(
            JdModelReferenceRecord.job_file_id == job_file_id,
            JdModelReferenceRecord.reference_number.in_(reference_numbers),
        )
    )
    return {row.model_ref: row.canonical_ref for row in rows}
