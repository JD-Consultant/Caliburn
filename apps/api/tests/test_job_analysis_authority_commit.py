"""Authority writes validate the complete state before touching repositories."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.job_analysis.application import DocumentRecord, add_jd_task, create_document
from app.job_analysis.domain import CurrentWorkModel, JdTask, JdTaskFields


pytestmark = pytest.mark.asyncio
NOW = datetime(2026, 7, 30, 9, 0, tzinfo=UTC)
DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000045")


class _Documents:
    def __init__(self, record: DocumentRecord, writes: list[str]) -> None:
        self.record = record
        self.writes = writes

    async def get(self, document_id: UUID, *, for_update: bool = False):
        assert document_id == DOCUMENT_ID
        assert for_update
        return self.record

    async def update_authority(self, *args, **kwargs) -> bool:
        self.writes.append("update_authority")
        return True

    async def update_title(
        self,
        document_id: UUID,
        *,
        title: str,
        updated_at: datetime,
    ) -> bool:
        assert document_id == DOCUMENT_ID
        self.writes.append("update_title")
        self.record = replace(self.record, title=title, updated_at=updated_at)
        return True


class _Tasks:
    def __init__(self, writes: list[str]) -> None:
        self.writes = writes
        self.values = (
            JdTask(task_id="task-1", statement="工作一", display_order=0),
            JdTask(task_id="task-2", statement="工作二", display_order=0),
        )

    async def list(self, document_id: UUID):
        assert document_id == DOCUMENT_ID
        return self.values

    async def replace(self, document_id: UUID, tasks) -> None:
        self.writes.append("replace_tasks")
        self.values = tasks


class _Proposals:
    def __init__(self, writes: list[str]) -> None:
        self.writes = writes

    async def list(self, document_id: UUID, *, statuses=None):
        assert document_id == DOCUMENT_ID
        return ()

    async def replace(self, document_id: UUID, proposals) -> None:
        self.writes.append("replace_proposals")


class _Journal:
    def __init__(self, writes: list[str]) -> None:
        self.writes = writes

    async def get(self, document_id: UUID, entry_id: str):
        assert document_id == DOCUMENT_ID
        return None

    async def add(self, entry) -> None:
        self.writes.append("add_journal")


class _UnitOfWork:
    def __init__(self) -> None:
        self.writes: list[str] = []
        record = DocumentRecord(
            document_id=DOCUMENT_ID,
            title="門市營運專員",
            work_model=CurrentWorkModel(),
            active_question=None,
            authority_generation=0,
            created_at=NOW,
            updated_at=NOW,
        )
        self.documents = _Documents(record, self.writes)
        self.tasks = _Tasks(self.writes)
        self.proposals = _Proposals(self.writes)
        self.journal = _Journal(self.writes)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def commit(self) -> None:
        self.writes.append("commit")


async def test_direct_edit_rejects_invalid_complete_state_before_any_write():
    """Removing complete-state validation would allow duplicate JD order writes."""

    uow = _UnitOfWork()

    with pytest.raises(ValidationError, match="display orders must be unique"):
        await add_jd_task(
            lambda: uow,
            document_id=DOCUMENT_ID,
            entry_id="add-3",
            fields=JdTaskFields(statement="工作三"),
        )

    assert uow.writes == []


async def test_rename_updates_only_document_metadata():
    """Routing a title change through authority commit would stale paid turns."""

    uow = _UnitOfWork()

    renamed = await create_document(
        lambda: uow,
        document_id=DOCUMENT_ID,
        title="資深門市營運專員",
    )

    assert renamed.title == "資深門市營運專員"
    assert renamed.authority_generation == 0
    assert uow.writes == ["update_title", "commit"]
