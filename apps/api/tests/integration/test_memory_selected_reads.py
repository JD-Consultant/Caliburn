"""單物件與來源導覽只載入固定位置內指定的成員。"""

from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import ORMExecuteState

from caliburn.features.work_memory import candidate_queries, position_persistence, read_queries
from caliburn.features.work_memory.candidates import MemoryCandidateStateError
from caliburn.features.work_memory.models import MemoryContent, MemorySourceWindow
from caliburn.features.work_memory.read_models import MemoryReadView
from caliburn.features.work_memory.revision_service import write_object_revision
from caliburn.features.work_memory.revisions import MemoryLayer, MemoryRevisionReference
from caliburn.settings import DatabaseSettings
from tests.integration.test_memory_position_storage import execute
from tests.integration.test_memory_position_storage import window as window

pytestmark = pytest.mark.postgres


def test_single_object_and_navigation_ignore_unrelated_position_members(
    database_settings: DatabaseSettings, window: MemorySourceWindow
) -> None:
    async def scenario(session: AsyncSession) -> None:
        situation = await write_object_revision(
            session,
            window,
            layer=MemoryLayer.WORK_SITUATION,
            content=MemoryContent("情境", "導覽描述", "來源正文"),
        )
        source = MemoryRevisionReference(situation.object_id, situation.revision_id)
        understanding = await write_object_revision(
            session,
            window,
            layer=MemoryLayer.WORK_UNDERSTANDING,
            content=MemoryContent("理解", "目標描述", "目標正文"),
            work_situation_references=frozenset({source}),
        )
        references = [
            source,
            MemoryRevisionReference(understanding.object_id, understanding.revision_id),
        ]
        for index in range(24):
            unrelated = await write_object_revision(
                session,
                window,
                layer=MemoryLayer.WORK_SITUATION,
                content=MemoryContent(f"無關 {index}", "不應載入", "無關正文"),
            )
            references.append(MemoryRevisionReference(unrelated.object_id, unrelated.revision_id))
        position_id = uuid4()
        await position_persistence.insert_position(
            session, window.job_file_id, position_id, None, tuple(references)
        )
        statements: list[str] = []

        def capture(state: ORMExecuteState) -> None:
            statements.append(str(state.statement))

        event.listen(session.sync_session, "do_orm_execute", capture)
        try:
            result = await read_queries.read_object(
                session,
                MemoryReadView(window.job_file_id, position_id, MemoryLayer.WORK_UNDERSTANDING, 2),
                understanding.object_id,
            )
        finally:
            event.remove(session.sync_session, "do_orm_execute", capture)
        assert result.content == understanding.content
        assert [(item.title, item.description) for item in result.work_situation_references] == [
            ("情境", "導覽描述")
        ]
        member_reads = [sql for sql in statements if "memory_position_members" in sql]
        assert member_reads
        assert all("memory_position_members.object_id IN (" in sql for sql in member_reads)
        # 導覽只需來源標頭；目標正文是唯一的 body 查詢。
        assert sum("memory_bodies" in sql for sql in statements) == 1

    execute(database_settings, scenario)


def test_selected_metadata_distinguishes_unavailable_positions_from_absent_members(
    database_settings: DatabaseSettings, window: MemorySourceWindow
) -> None:
    async def scenario(session: AsyncSession) -> None:
        position_id, object_id = uuid4(), uuid4()
        for selected in ((object_id,), ()):
            with pytest.raises(MemoryCandidateStateError):
                await candidate_queries.read_position_selection(
                    session, window.job_file_id, position_id, selected
                )
        position = position_persistence.MemoryPositionRecord(
            job_file_id=window.job_file_id, position_id=position_id
        )
        session.add(position)
        await session.flush()
        with pytest.raises(MemoryCandidateStateError):
            await candidate_queries.read_position_selection(
                session, window.job_file_id, position_id, (object_id,)
            )
        position.is_sealed = True
        await session.flush()
        for selected in ((object_id,), ()):
            assert (
                await candidate_queries.read_position_selection(
                    session, window.job_file_id, position_id, selected
                )
                == {}
            )
        with pytest.raises(MemoryCandidateStateError):
            await candidate_queries.read_position_selection(
                session, uuid4(), position_id, (object_id,)
            )

    execute(database_settings, scenario)
