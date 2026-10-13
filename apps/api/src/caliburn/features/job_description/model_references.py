"""Short-locator translation, not authorization or a second JD identity authority."""

import re
from collections.abc import Collection
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.job_description import model_reference_persistence as persistence
from caliburn.features.job_description.navigation import JdReadTargetNotFoundError

_KINDS = r"(?:area|task|outcome|requirement|knowledge|skill|collaborator|condition|citation)"
_CANONICAL = re.compile(rf"{_KINDS}_[0-9a-f]{{32}}")
_SHORT = re.compile(rf"{_KINDS}_([1-9][0-9]{{0,18}})")


class JdModelReferences:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], job_file_id: UUID) -> None:
        self.sessions = sessions
        self.job_file_id = job_file_id

    async def assign(self, canonical_refs: Collection[str]) -> dict[str, str]:
        if any(not _CANONICAL.fullmatch(ref) for ref in canonical_refs):
            raise ValueError("Only canonical JD identities may receive model aliases")
        if not canonical_refs:
            return {}
        async with self.sessions.begin() as session:
            return await persistence.assign_references(session, self.job_file_id, canonical_refs)

    async def resolve(self, model_refs: Collection[str]) -> dict[str, str]:
        """Translate known aliases; existing JD workflows still enforce current scope/target."""
        requested = set(model_refs)
        numbers = []
        for ref in requested:
            match = _SHORT.fullmatch(ref)
            if match is None or int(match[1]) > 2**63 - 1:
                raise JdReadTargetNotFoundError("Unknown JD model reference")
            numbers.append(int(match[1]))
        if not numbers:
            return {}
        async with self.sessions() as session:
            resolved = await persistence.read_references(session, self.job_file_id, numbers)
        if not requested <= resolved.keys():
            raise JdReadTargetNotFoundError("No matching JD model reference in this file")
        return resolved
