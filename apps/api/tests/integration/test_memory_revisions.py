"""Fixed bodies and version-bound sources survive edits without copying unchanged Markdown."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import replace
from uuid import UUID, uuid4

import psycopg
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.adapters.database import Database
from caliburn.features.interviews.models import InterviewReadError
from caliburn.features.work_memory.models import (
    InvalidMemoryChangeError,
    MemoryContent,
    MemorySourceWindow,
)
from caliburn.features.work_memory.revision_service import (
    read_fixed_revision,
    write_object_revision,
)
from caliburn.features.work_memory.revisions import (
    MemoryLayer,
    MemoryObjectRevision,
    MemoryRevisionNotFoundError,
    MemoryRevisionReference,
)
from caliburn.settings import DatabaseSettings

pytestmark = pytest.mark.postgres


def execute[T](settings: DatabaseSettings, operation: Callable[[AsyncSession], Awaitable[T]]) -> T:
    async def run() -> T:
        database = Database(settings)
        try:
            async with database.sessions.begin() as session:
                return await operation(session)
        finally:
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        return runner.run(run())


def ref(revision: MemoryObjectRevision) -> MemoryRevisionReference:
    return MemoryRevisionReference(revision.object_id, revision.revision_id)


@pytest.fixture
def source_window(database_connection: psycopg.Connection) -> MemorySourceWindow:
    file_id, source_id = uuid4(), uuid4()
    database_connection.execute(
        "INSERT INTO job_files (job_file_id, creation_command_id, initial_display_name, "
        "display_name, employee_name) VALUES (%s,%s,'Memory','Memory','合成員工')",
        (file_id, uuid4()),
    )
    for sequence, role, identity in ((1, "app", uuid4()), (2, "employee", source_id)):
        database_connection.execute(
            "INSERT INTO interview_texts (job_file_id,source_id,speaker,interview_text) "
            "VALUES (%s,%s,%s,'合成原文')",
            (file_id, identity, role),
        )
        database_connection.execute(
            "INSERT INTO formal_interviews (job_file_id,interview_sequence,source_id) "
            "VALUES (%s,%s,%s)",
            (file_id, sequence, identity),
        )
    return MemorySourceWindow(file_id, source_id, 0, 2)


def create_situation(
    settings: DatabaseSettings, window: MemorySourceWindow
) -> MemoryObjectRevision:
    return execute(
        settings,
        lambda s: write_object_revision(
            s,
            window,
            layer=MemoryLayer.WORK_SITUATION,
            content=MemoryContent("每月盤點", "庫存差異處理", "## 工作過程\n核對實物與清單。\n"),
            interview_references=frozenset({window.through_source_id}),
        ),
    )


def test_title_and_reference_edits_reuse_body_but_never_rewrite_old_revision(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    source_window: MemorySourceWindow,
) -> None:
    first = create_situation(database_settings, source_window)
    second = execute(
        database_settings,
        lambda s: write_object_revision(
            s,
            source_window,
            layer=first.layer,
            previous=ref(first),
            content=replace(first.content, title="月底盤點"),
            interview_references=frozenset(),
        ),
    )
    assert second.object_id == first.object_id
    assert second.revision_id != first.revision_id
    assert second.body_id == first.body_id
    assert not second.interview_references
    assert (
        execute(
            database_settings,
            lambda s: read_fixed_revision(
                s, job_file_id=source_window.job_file_id, reference=ref(first)
            ),
        )
        == first
    )
    assert database_connection.execute("SELECT count(*) FROM memory_bodies").fetchone() == (1,)


def test_same_edit_is_noop_but_changing_back_creates_a_new_revision(
    database_settings: DatabaseSettings,
    source_window: MemorySourceWindow,
) -> None:
    first = create_situation(database_settings, source_window)
    unchanged = execute(
        database_settings,
        lambda s: write_object_revision(
            s,
            source_window,
            layer=first.layer,
            previous=ref(first),
            content=first.content,
            interview_references=first.interview_references,
        ),
    )
    assert unchanged == first
    changed = execute(
        database_settings,
        lambda s: write_object_revision(
            s,
            source_window,
            layer=first.layer,
            previous=ref(first),
            content=replace(first.content, body="## 工作過程\n清點並追查差異。"),
            interview_references=first.interview_references,
        ),
    )
    reverted = execute(
        database_settings,
        lambda s: write_object_revision(
            s,
            source_window,
            layer=first.layer,
            previous=ref(changed),
            content=first.content,
            interview_references=first.interview_references,
        ),
    )
    assert reverted.content == first.content
    assert len({first.revision_id, changed.revision_id, reverted.revision_id}) == 3
    assert first.body_id != changed.body_id != reverted.body_id


def test_fixed_understanding_sources_change_revision_even_when_body_is_unchanged(
    database_settings: DatabaseSettings,
    source_window: MemorySourceWindow,
) -> None:
    situation = create_situation(database_settings, source_window)
    understanding = execute(
        database_settings,
        lambda s: write_object_revision(
            s,
            source_window,
            layer=MemoryLayer.WORK_UNDERSTANDING,
            content=MemoryContent("庫存管理", "現場庫存可靠性", "辨認帳實差異並回報。"),
            work_situation_references=frozenset({ref(situation)}),
        ),
    )
    revised_situation = execute(
        database_settings,
        lambda s: write_object_revision(
            s,
            source_window,
            layer=situation.layer,
            previous=ref(situation),
            content=replace(situation.content, description="月底庫存差異處理"),
            interview_references=situation.interview_references,
        ),
    )
    revised_understanding = execute(
        database_settings,
        lambda s: write_object_revision(
            s,
            source_window,
            layer=understanding.layer,
            previous=ref(understanding),
            content=understanding.content,
            work_situation_references=frozenset({ref(revised_situation)}),
        ),
    )
    assert revised_understanding.body_id == understanding.body_id
    assert revised_understanding.revision_id != understanding.revision_id
    old = execute(
        database_settings,
        lambda s: read_fixed_revision(
            s, job_file_id=source_window.job_file_id, reference=ref(understanding)
        ),
    )
    assert old.work_situation_references == frozenset({ref(situation)})


def test_missing_or_foreign_revision_is_not_available(
    database_settings: DatabaseSettings,
    source_window: MemorySourceWindow,
) -> None:
    situation = create_situation(database_settings, source_window)
    for file_id, reference in (
        (uuid4(), ref(situation)),
        (source_window.job_file_id, MemoryRevisionReference(situation.object_id, uuid4())),
    ):
        with pytest.raises(MemoryRevisionNotFoundError):
            execute(
                database_settings,
                lambda s, file_id=file_id, reference=reference: read_fixed_revision(
                    s, job_file_id=file_id, reference=reference
                ),
            )


def test_wrong_layer_or_multiple_revisions_of_same_source_are_rejected(
    database_settings: DatabaseSettings,
    source_window: MemorySourceWindow,
) -> None:
    situation = create_situation(database_settings, source_window)
    with pytest.raises(InvalidMemoryChangeError):
        execute(
            database_settings,
            lambda s: write_object_revision(
                s,
                source_window,
                layer=MemoryLayer.WORK_UNDERSTANDING,
                previous=ref(situation),
                content=situation.content,
            ),
        )
    with pytest.raises(InvalidMemoryChangeError):
        execute(
            database_settings,
            lambda s: write_object_revision(
                s,
                source_window,
                layer=MemoryLayer.WORK_UNDERSTANDING,
                content=situation.content,
                work_situation_references=frozenset(
                    {ref(situation), MemoryRevisionReference(situation.object_id, uuid4())}
                ),
            ),
        )


def test_bad_interview_source_aborts_without_persisting_partial_object(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    source_window: MemorySourceWindow,
) -> None:
    with pytest.raises(InterviewReadError):
        execute(
            database_settings,
            lambda s: write_object_revision(
                s,
                source_window,
                layer=MemoryLayer.WORK_SITUATION,
                content=MemoryContent("情境", "範圍", "正文"),
                interview_references=frozenset({uuid4()}),
            ),
        )
    assert database_connection.execute("SELECT count(*) FROM memory_objects").fetchone() == (0,)


def test_outer_transaction_rollback_discards_the_whole_revision(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    source_window: MemorySourceWindow,
) -> None:
    async def abort(session: AsyncSession) -> None:
        await write_object_revision(
            session,
            source_window,
            layer=MemoryLayer.WORK_SITUATION,
            content=MemoryContent("情境", "範圍", "正文"),
        )
        raise RuntimeError("synthetic outer failure")

    with pytest.raises(RuntimeError, match="synthetic outer failure"):
        execute(database_settings, abort)
    for table in ("memory_objects", "memory_bodies", "memory_object_revisions"):
        assert database_connection.execute(
            psycopg.sql.SQL("SELECT count(*) FROM {}").format(psycopg.sql.Identifier(table))
        ).fetchone() == (0,)


def test_fixed_revision_and_its_source_membership_cannot_be_rewritten_or_appended(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    source_window: MemorySourceWindow,
) -> None:
    situation = create_situation(database_settings, source_window)
    understanding = execute(
        database_settings,
        lambda s: write_object_revision(
            s,
            source_window,
            layer=MemoryLayer.WORK_UNDERSTANDING,
            content=MemoryContent("庫存責任", "庫存", "辨識差異。"),
            work_situation_references=frozenset({ref(situation)}),
        ),
    )
    for statement in (
        "UPDATE memory_objects SET layer = 'work_understanding'",
        "DELETE FROM memory_objects",
        "UPDATE memory_bodies SET body = 'rewritten'",
        "DELETE FROM memory_bodies",
        "UPDATE memory_object_revisions SET title = 'rewritten'",
        "UPDATE memory_object_revisions SET is_sealed = false",
        "DELETE FROM memory_object_revisions",
        "UPDATE memory_interview_references SET source_id = source_id",
        "DELETE FROM memory_interview_references",
        "UPDATE memory_situation_references SET source_revision_id = source_revision_id",
        "DELETE FROM memory_situation_references",
    ):
        with pytest.raises(psycopg.errors.CheckViolation):
            database_connection.execute(statement)
    with pytest.raises(psycopg.errors.CheckViolation):
        database_connection.execute(
            "INSERT INTO memory_interview_references "
            "(job_file_id,object_id,revision_id,source_id) VALUES (%s,%s,%s,%s)",
            (
                source_window.job_file_id,
                situation.object_id,
                situation.revision_id,
                source_window.through_source_id,
            ),
        )
    with pytest.raises(psycopg.errors.CheckViolation):
        database_connection.execute(
            "INSERT INTO memory_situation_references "
            "(job_file_id,object_id,revision_id,source_object_id,source_revision_id) "
            "VALUES (%s,%s,%s,%s,%s)",
            (
                source_window.job_file_id,
                understanding.object_id,
                understanding.revision_id,
                situation.object_id,
                situation.revision_id,
            ),
        )


def insert_unsealed_revision(
    connection: psycopg.Connection,
    window: MemorySourceWindow,
    original: MemoryObjectRevision,
) -> UUID:
    revision_id = uuid4()
    connection.execute(
        "INSERT INTO memory_object_revisions "
        "(job_file_id,object_id,revision_id,body_id,title,description) "
        "VALUES (%s,%s,%s,%s,'Unsealed','Synthetic')",
        (window.job_file_id, original.object_id, revision_id, original.body_id),
    )
    return revision_id


def test_transaction_cannot_commit_an_incomplete_revision(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    source_window: MemorySourceWindow,
) -> None:
    original = create_situation(database_settings, source_window)
    with pytest.raises(psycopg.errors.CheckViolation):
        with database_connection.transaction():
            insert_unsealed_revision(database_connection, source_window, original)
    assert database_connection.execute(
        "SELECT count(*) FROM memory_object_revisions"
    ).fetchone() == (1,)


def test_source_reference_requires_formal_membership_not_just_saved_original(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    source_window: MemorySourceWindow,
) -> None:
    original = create_situation(database_settings, source_window)
    pending_id = uuid4()
    database_connection.execute(
        "INSERT INTO interview_texts (job_file_id,source_id,speaker,interview_text) "
        "VALUES (%s,%s,'employee','Pending synthetic input')",
        (source_window.job_file_id, pending_id),
    )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with database_connection.transaction():
            revision_id = insert_unsealed_revision(database_connection, source_window, original)
            database_connection.execute(
                "INSERT INTO memory_interview_references "
                "(job_file_id,object_id,revision_id,source_id) VALUES (%s,%s,%s,%s)",
                (source_window.job_file_id, original.object_id, revision_id, pending_id),
            )


def test_database_rejects_situation_to_situation_edge_even_before_sealing(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    source_window: MemorySourceWindow,
) -> None:
    original = create_situation(database_settings, source_window)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with database_connection.transaction():
            revision_id = insert_unsealed_revision(database_connection, source_window, original)
            database_connection.execute(
                "INSERT INTO memory_situation_references "
                "(job_file_id,object_id,revision_id,source_object_id,source_revision_id) "
                "VALUES (%s,%s,%s,%s,%s)",
                (
                    source_window.job_file_id,
                    original.object_id,
                    revision_id,
                    original.object_id,
                    original.revision_id,
                ),
            )


def test_database_cannot_use_another_files_body_or_source(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    source_window: MemorySourceWindow,
) -> None:
    original = create_situation(database_settings, source_window)
    other_file_id = uuid4()
    database_connection.execute(
        "INSERT INTO job_files (job_file_id,creation_command_id,initial_display_name,display_name,"
        "employee_name) VALUES (%s,%s,'Other','Other','Synthetic')",
        (other_file_id, uuid4()),
    )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        database_connection.execute(
            "INSERT INTO memory_object_revisions "
            "(job_file_id,object_id,revision_id,body_id,title,description,is_sealed) "
            "VALUES (%s,%s,%s,%s,'Other','Other',true)",
            (other_file_id, original.object_id, uuid4(), original.body_id),
        )
    other_source_id = uuid4()
    database_connection.execute(
        "INSERT INTO interview_texts (job_file_id,source_id,speaker,interview_text) "
        "VALUES (%s,%s,'employee','Other formal input')",
        (other_file_id, other_source_id),
    )
    database_connection.execute(
        "INSERT INTO formal_interviews (job_file_id,interview_sequence,source_id) VALUES (%s,1,%s)",
        (other_file_id, other_source_id),
    )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with database_connection.transaction():
            revision_id = insert_unsealed_revision(database_connection, source_window, original)
            database_connection.execute(
                "INSERT INTO memory_interview_references "
                "(job_file_id,object_id,revision_id,source_id) VALUES (%s,%s,%s,%s)",
                (source_window.job_file_id, original.object_id, revision_id, other_source_id),
            )
