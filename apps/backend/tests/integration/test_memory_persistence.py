"""使用正式訪談保存與隔離 PostgreSQL 驗證 Memory 寫入、失敗與固定讀取。"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from psycopg.errors import TransactionResolutionUnknown
from sqlalchemy import Engine, event, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import PoolProxiedConnection

from caliburn.modules.interview.application.errors import InterviewConcurrencyError
from caliburn.modules.interview.application.recording import (
    record_consultant_message,
    record_turn_input,
)
from caliburn.modules.interview.application.withdrawal import withdraw_turn
from caliburn.modules.interview.infrastructure.persistence.unit_of_work import (
    SqlAlchemyInterviewUnitOfWork,
)
from caliburn.modules.memory.application.errors import (
    MemoryConcurrencyError,
    MemoryDataError,
    MemoryFailureBlockedError,
    MemoryPersistenceError,
    MemoryVersionNotFoundError,
    WorkspaceNotFoundError,
)
from caliburn.modules.memory.application.inputs import MemoryWriteContext
from caliburn.modules.memory.application.results import MemoryUpdateResult
from caliburn.modules.memory.application.service import MemoryService
from caliburn.modules.memory.domain.content import MemoryContent
from caliburn.modules.memory.domain.errors import (
    DuplicateMemoryTitleError,
    InvalidMemoryPhaseError,
    InvalidMemorySourceError,
    MemoryAnalysisConflictError,
)
from caliburn.modules.memory.domain.items import WorkUnderstanding
from caliburn.modules.memory.infrastructure.persistence.queries import (
    SqlAlchemyMemoryQueries,
)
from caliburn.modules.memory.infrastructure.persistence.unit_of_work import (
    SqlAlchemyMemoryUnitOfWork,
)
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory


@dataclass
class CompletedTurns:
    ids: frozenset[UUID] = frozenset()

    def completed_turn_ids(self, *, workspace_id: UUID) -> frozenset[UUID]:
        return self.ids


def test_publish_uses_completed_window_and_validates_version(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    turns = CompletedTurns()
    service = MemoryService(
        partial(SqlAlchemyMemoryUnitOfWork, sessions), completed_turns=turns
    )
    queries = SqlAlchemyMemoryQueries(pg_engine)
    workspace = jd_workspace_id
    turn = uuid4()
    through = record_turn_input(
        workspace_id=workspace,
        turn_id=turn,
        text="完成的訪談",
        uow_factory=partial(SqlAlchemyInterviewUnitOfWork, sessions),
    ).message_id
    analysis = uuid4()

    def context(version: int) -> MemoryWriteContext:
        return MemoryWriteContext(
            workspace_id=workspace,
            expected_version=version,
            analysis_id=analysis,
        )

    start = context(0)
    with pytest.raises(InvalidMemorySourceError):
        service.start(start, through_message_id=through)
    assert queries.get_current(workspace_id=workspace).version == 0
    turns.ids = frozenset({turn})
    service.start(start, through_message_id=through)
    assert (
        queries.list_analysis_sources(workspace_id=workspace, analysis_id=analysis)[
            0
        ].message_id
        == through
    )

    create = context(1)
    content = MemoryContent(title="  情境甲 ", description="  說明  ", body="正文")
    created = service.create_situation(
        create, content=content, interview_message_ids=(through,)
    )
    assert created.item_id is not None
    with pytest.raises(MemoryConcurrencyError):
        service.revise_situation(
            context(1),
            item_id=created.item_id,
            content=content,
            interview_message_ids=(through,),
        )
    unchanged = service.revise_situation(
        context(2),
        item_id=created.item_id,
        content=content,
        interview_message_ids=(through,),
    )
    assert (unchanged.changed, unchanged.version) == (False, 2)
    service.handoff(context(2))
    publish = context(3)
    published = service.publish(publish)
    assert published.snapshot is not None
    assert published.snapshot.items[0].content == content
    assert queries.get_published(workspace_id=workspace, published_version=None) is None
    assert (
        queries.get_published(workspace_id=workspace, published_version=4)
        == published.snapshot
    )

    with pytest.raises(MemoryConcurrencyError):
        service.publish(publish)


@dataclass(frozen=True)
class MemoryCase:
    sessions: sessionmaker[Session]
    workspace_id: UUID
    turn_id: UUID
    through: UUID
    analysis_id: UUID

    def context(self, version: int) -> MemoryWriteContext:
        return MemoryWriteContext(
            workspace_id=self.workspace_id,
            expected_version=version,
            analysis_id=self.analysis_id,
        )

    def service(self, sessions: Callable[[], Session] | None = None) -> MemoryService:
        return MemoryService(
            partial(SqlAlchemyMemoryUnitOfWork, sessions or self.sessions),
            completed_turns=CompletedTurns(frozenset({self.turn_id})),
        )


@pytest.fixture
def memory_case(pg_engine: Engine, jd_workspace_id: UUID) -> MemoryCase:
    sessions = create_session_factory(pg_engine)
    turn_id = uuid4()
    through = record_turn_input(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        text="可供引用的員工原話",
        uow_factory=partial(SqlAlchemyInterviewUnitOfWork, sessions),
    ).message_id
    case = MemoryCase(sessions, jd_workspace_id, turn_id, through, uuid4())
    case.service().start(case.context(0), through_message_id=through)
    return case


def test_b2_edit_rejects_previously_saved_situation_source_after_withdrawal(
    memory_case: MemoryCase,
) -> None:
    case = memory_case
    service = case.service()
    content = MemoryContent(title="情境", description="說明", body="正文")
    situation = service.create_situation(
        case.context(1), content=content, interview_message_ids=(case.through,)
    )
    assert situation.item_id is not None
    service.handoff(case.context(2))
    withdraw_turn(
        workspace_id=case.workspace_id,
        turn_id=case.turn_id,
        uow_factory=partial(SqlAlchemyInterviewUnitOfWork, case.sessions),
    )

    with pytest.raises(InvalidMemorySourceError):
        service.create_understanding(
            case.context(3), content=content, situation_ids=(situation.item_id,)
        )


def test_source_validation_keeps_the_turn_lock_until_memory_commit(
    memory_case: MemoryCase,
) -> None:
    case = memory_case
    session = case.sessions()
    tested_lock = False

    def check_withdrawal(session: Session) -> None:
        nonlocal tested_lock
        with pytest.raises(InterviewConcurrencyError) as rejected:
            withdraw_turn(
                workspace_id=case.workspace_id,
                turn_id=case.turn_id,
                uow_factory=partial(
                    SqlAlchemyInterviewUnitOfWork, case.sessions, lock_timeout_ms=50
                ),
            )
        assert rejected.value.reason == "lock_timeout"
        tested_lock = True

    event.listen(session, "before_commit", check_withdrawal)
    content = MemoryContent(title="測試", description="說明", body="正文")
    result = case.service(lambda: session).create_situation(
        case.context(1), content=content, interview_message_ids=(case.through,)
    )
    assert tested_lock
    assert result.version == 2

    withdraw_turn(
        workspace_id=case.workspace_id,
        turn_id=case.turn_id,
        uow_factory=partial(SqlAlchemyInterviewUnitOfWork, case.sessions),
    )
    with pytest.raises(InvalidMemorySourceError):
        case.service().handoff(case.context(2))


def test_parallel_same_title_only_saves_one_item(
    pg_engine: Engine, memory_case: MemoryCase
) -> None:
    case = memory_case
    service = case.service()
    content = MemoryContent(title="同名", description="說明", body="正文")
    barrier = Barrier(2)

    def create() -> MemoryUpdateResult:
        barrier.wait(timeout=5)
        return service.create_situation(case.context(1), content=content)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(create), pool.submit(create)
        rejected = 0
        for future in (first, second):
            try:
                assert future.result(timeout=5).version == 2
            except MemoryConcurrencyError as error:
                assert error.reason == "version"
                rejected += 1
    assert rejected == 1
    with pytest.raises(DuplicateMemoryTitleError):
        service.create_situation(case.context(2), content=content)
    memory = SqlAlchemyMemoryQueries(pg_engine).get_current(
        workspace_id=case.workspace_id
    )
    assert len(memory.situations) == 1
    assert memory.version == 2


def test_other_analysis_and_phase_cannot_modify_the_current_graph(
    pg_engine: Engine, memory_case: MemoryCase
) -> None:
    case = memory_case
    service = case.service()
    content = MemoryContent(title="項目", description="說明", body="正文")
    with pytest.raises(MemoryAnalysisConflictError):
        service.create_situation(
            replace(case.context(1), analysis_id=uuid4()), content=content
        )
    with pytest.raises(InvalidMemoryPhaseError):
        service.publish(case.context(1))
    assert service.handoff(case.context(1)).version == 2
    with pytest.raises(InvalidMemoryPhaseError):
        service.create_situation(case.context(2), content=content)
    current = SqlAlchemyMemoryQueries(pg_engine).get_current(
        workspace_id=case.workspace_id
    )
    assert current.analysis is not None and current.analysis.phase == "understanding"


def test_unfinished_later_and_other_workspace_sources_are_rejected(
    pg_engine: Engine, memory_case: MemoryCase
) -> None:
    case = memory_case
    service = case.service()
    interview = partial(SqlAlchemyInterviewUnitOfWork, case.sessions)
    workspaces = WorkspaceService(partial(SqlAlchemyWorkspaceUnitOfWork, case.sessions))
    other = workspaces.create(interviewee_name="另一 Workspace").workspace_id
    later_turn = uuid4()
    later = record_turn_input(
        workspace_id=case.workspace_id,
        turn_id=later_turn,
        text="在固定上界之外",
        uow_factory=interview,
    ).message_id
    foreign = record_turn_input(
        workspace_id=other,
        turn_id=uuid4(),
        text="不屬於目前 Workspace",
        uow_factory=interview,
    ).message_id
    content = MemoryContent(title="項目", description="說明", body="正文")
    for source in (later, foreign):
        with pytest.raises(InvalidMemorySourceError):
            service.create_situation(
                case.context(1), content=content, interview_message_ids=(source,)
            )
    current = SqlAlchemyMemoryQueries(pg_engine).get_current(
        workspace_id=case.workspace_id
    )
    assert current.version == 1 and not current.items


def test_publish_failure_rolls_back_and_commit_ack_loss_is_reported(
    pg_engine: Engine, memory_case: MemoryCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = memory_case
    service = case.service()
    service.handoff(case.context(1))
    publish = case.context(2)
    queries = SqlAlchemyMemoryQueries(pg_engine)
    with pg_engine.begin() as connection:
        connection.execute(
            text("""
            CREATE FUNCTION reject_memory_publish() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'synthetic publication failure' USING ERRCODE='23514';
            END $$
        """)
        )
        connection.execute(
            text("""
            CREATE TRIGGER reject_publish
            BEFORE UPDATE OF published_version ON work_memories
            FOR EACH ROW WHEN (NEW.published_version IS NOT NULL)
            EXECUTE FUNCTION reject_memory_publish()
        """)
        )
    with pytest.raises(MemoryPersistenceError) as rolled_back:
        service.publish(publish)
    assert rolled_back.value.commit_status == "not_committed"
    assert queries.get_current(workspace_id=case.workspace_id).version == 2
    with pytest.raises(MemoryVersionNotFoundError):
        queries.get_published(workspace_id=case.workspace_id, published_version=3)

    with pg_engine.begin() as connection:
        connection.execute(text("DROP TRIGGER reject_publish ON work_memories"))
    native_commit = pg_engine.dialect.do_commit

    def lose_reply(connection: PoolProxiedConnection) -> None:
        native_commit(connection)
        raise TransactionResolutionUnknown("synthetic lost commit reply")

    with monkeypatch.context() as injection:
        injection.setattr(pg_engine.dialect, "do_commit", lose_reply)
        with pytest.raises(MemoryPersistenceError) as unconfirmed:
            service.publish(publish)
    assert unconfirmed.value.commit_status == "unknown"
    with pytest.raises(MemoryConcurrencyError):
        service.publish(publish)
    snapshot = queries.get_published(
        workspace_id=case.workspace_id, published_version=3
    )
    assert snapshot is not None
    assert (
        queries.get_current(workspace_id=case.workspace_id).published_version
        == snapshot.version
    )


def test_snapshot_is_immutable_and_corruption_fails_instead_of_returning_empty(
    pg_engine: Engine, memory_case: MemoryCase
) -> None:
    case = memory_case
    service = case.service()
    service.handoff(case.context(1))
    result = service.publish(case.context(2))
    assert result.snapshot is not None
    for statement in (
        "UPDATE memory_snapshots SET schema_version = 2",
        "DELETE FROM memory_snapshots",
        "DELETE FROM work_memories",
    ):
        with pytest.raises(IntegrityError), pg_engine.begin() as connection:
            connection.execute(text(statement))
    with pg_engine.begin() as connection:
        connection.execute(text("ALTER TABLE memory_snapshots DISABLE TRIGGER USER"))
        connection.execute(text("UPDATE memory_snapshots SET content = '{}'::jsonb"))
        connection.execute(text("ALTER TABLE memory_snapshots ENABLE TRIGGER USER"))

    with pytest.raises(MemoryDataError):
        SqlAlchemyMemoryQueries(pg_engine).get_published(
            workspace_id=case.workspace_id, published_version=result.version
        )


def test_workspace_deletion_cascades_all_memory_data(
    pg_engine: Engine, memory_case: MemoryCase
) -> None:
    case = memory_case
    service = case.service()
    content = MemoryContent(title="情境", description="說明", body="正文")
    service.create_situation(case.context(1), content=content)
    service.handoff(case.context(2))
    service.publish(case.context(3))

    workspaces = WorkspaceService(partial(SqlAlchemyWorkspaceUnitOfWork, case.sessions))
    workspaces.delete(workspace_id=case.workspace_id)
    with pg_engine.connect() as connection:
        for table in (
            "work_memories",
            "memory_items",
            "memory_snapshots",
        ):
            assert connection.scalar(text(f"SELECT count(*) FROM {table}")) == 0
    with pytest.raises(WorkspaceNotFoundError):
        SqlAlchemyMemoryQueries(pg_engine).get_current(workspace_id=case.workspace_id)


def test_memory_migration_roundtrip_matches_orm_metadata(pg_engine: Engine) -> None:
    backend = Path(__file__).resolve().parents[2]
    config = Config(str(backend / "alembic.ini"))
    with pg_engine.begin() as connection:
        config.attributes["connection"] = connection
        tables = {
            "work_memories",
            "memory_items",
            "memory_snapshots",
        }
        command.downgrade(config, "0006_interviews")
        assert not tables & set(inspect(connection).get_table_names())
        command.upgrade(config, "head")
        found = {
            name
            for name in inspect(connection).get_table_names()
            if name.startswith("memory_")
        }
        assert found == tables - {"work_memories"}
        assert {
            column["name"]
            for column in inspect(connection).get_columns("work_memories")
        } == {"workspace_id", "version", "published_version", "analysis", "failure"}
        command.check(config)


def test_discard_restores_baseline_and_new_publish_keeps_original_source_graph(
    pg_engine: Engine, memory_case: MemoryCase
) -> None:
    case = memory_case
    service = case.service()
    queries = SqlAlchemyMemoryQueries(pg_engine)

    def content(title: str) -> MemoryContent:
        return MemoryContent(title=title, description="說明", body="正文")

    first = service.create_situation(
        case.context(1), content=content("甲"), interview_message_ids=(case.through,)
    ).item_id
    second = service.create_situation(case.context(2), content=content("乙")).item_id
    assert first is not None and second is not None
    service.handoff(case.context(3))
    understanding = service.create_understanding(
        case.context(4), content=content("理解"), situation_ids=(first, second)
    ).item_id
    assert understanding is not None
    first_snapshot = service.publish(case.context(5)).snapshot
    assert first_snapshot is not None
    assert not service.start(case.context(6), through_message_id=case.through).changed

    new_turn = uuid4()
    new_through = record_turn_input(
        workspace_id=case.workspace_id,
        turn_id=new_turn,
        text="後續原話",
        uow_factory=partial(SqlAlchemyInterviewUnitOfWork, case.sessions),
    ).message_id
    service = MemoryService(
        partial(SqlAlchemyMemoryUnitOfWork, case.sessions),
        completed_turns=CompletedTurns(frozenset({case.turn_id, new_turn})),
    )
    case = replace(case, analysis_id=uuid4())
    service.start(case.context(6), through_message_id=new_through)
    current = queries.get_current(workspace_id=case.workspace_id)
    assert current.analysis is not None
    assert current.analysis.source_window.required_message_ids == (new_through,)
    service.revise_situation(
        case.context(7),
        item_id=first,
        content=content("暫名"),
        interview_message_ids=(),
    )
    service.revise_situation(
        case.context(8), item_id=second, content=content("甲"), interview_message_ids=()
    )
    service.revise_situation(
        case.context(9), item_id=first, content=content("乙"), interview_message_ids=()
    )
    service.discard(case.context(10))
    restored = queries.get_current(workspace_id=case.workspace_id)
    assert restored.analysis is None
    assert restored.version == 11
    assert restored.get_situation(item_id=first).content.title == "甲"
    assert restored.get_situation(item_id=first).changed_version == 2
    assert restored.get_situation(item_id=first).interview_message_ids == (
        case.through,
    )
    assert restored.get_situation(item_id=second).content.title == "乙"
    assert restored.get_understanding(item_id=understanding).changed_version == 5

    case = replace(case, analysis_id=uuid4())
    service.start(case.context(11), through_message_id=new_through)
    service.delete_situation(case.context(12), item_id=first)
    service.handoff(case.context(13))
    service.publish(case.context(14))
    old = queries.get_published(workspace_id=case.workspace_id, published_version=6)
    new = queries.get_published(workspace_id=case.workspace_id, published_version=15)
    assert old is not None and new is not None
    assert old.model_dump() == first_snapshot.model_dump()
    (updated,) = [item for item in new.items if isinstance(item, WorkUnderstanding)]
    assert updated.situation_ids == (second,)
    assert updated.changed_version == 13
    assert (
        queries.get_published(workspace_id=case.workspace_id, published_version=None)
        is None
    )


def test_covered_start_is_no_work_and_checks_current_eligibility(
    pg_engine: Engine, memory_case: MemoryCase
) -> None:
    case = memory_case
    service = case.service()
    service.handoff(case.context(1))
    service.publish(case.context(2))

    no_work = case.context(3)
    original = service.start(no_work, through_message_id=case.through)
    assert original.version == 3
    assert original.changed is False
    assert original.snapshot is None
    assert (
        SqlAlchemyMemoryQueries(pg_engine)
        .get_current(workspace_id=case.workspace_id)
        .analysis
        is None
    )
    withdraw_turn(
        workspace_id=case.workspace_id,
        turn_id=case.turn_id,
        uow_factory=partial(SqlAlchemyInterviewUnitOfWork, case.sessions),
    )
    turns = CompletedTurns()
    restarted = MemoryService(
        partial(SqlAlchemyMemoryUnitOfWork, case.sessions), completed_turns=turns
    )
    with pytest.raises(InvalidMemorySourceError):
        restarted.start(case.context(3), through_message_id=case.through)


def test_final_failure_records_original_frontier_and_blocks_until_six_new_messages(
    pg_engine: Engine, memory_case: MemoryCase
) -> None:
    case = memory_case
    turns = CompletedTurns(frozenset({case.turn_id}))
    service = MemoryService(
        partial(SqlAlchemyMemoryUnitOfWork, case.sessions), completed_turns=turns
    )
    queries = SqlAlchemyMemoryQueries(pg_engine)
    interview = partial(SqlAlchemyInterviewUnitOfWork, case.sessions)
    original_reply = record_consultant_message(
        workspace_id=case.workspace_id,
        turn_id=case.turn_id,
        text="原有的最終回覆",
        uow_factory=interview,
    ).message_id
    discard = case.context(1)
    result = service.discard(discard, reason="invalid_completion")
    assert (result.changed, result.version) == (True, 2)
    current = queries.get_current(workspace_id=case.workspace_id)
    assert current.analysis is None and current.failure is not None
    assert current.failure.analysis_id == case.analysis_id
    assert current.failure.reason == "invalid_completion"
    assert current.failure.formal_message_ids == (case.through, original_reply)

    retry = replace(case.context(2), analysis_id=uuid4())
    for count in range(3):
        turn_id = uuid4()
        record_turn_input(
            workspace_id=case.workspace_id,
            turn_id=turn_id,
            text=f"員工第 {count} 次新發話",
            uow_factory=interview,
        )
        record_consultant_message(
            workspace_id=case.workspace_id,
            turn_id=turn_id,
            text=f"顧問第 {count} 次回覆",
            uow_factory=interview,
        )
        # Interview 已保存顧問末句但 Agent 尚未 END 時仍不計入。
        with pytest.raises(MemoryFailureBlockedError):
            service.start(retry, through_message_id=case.through)
        turns.ids = turns.ids | {turn_id}

    assert service.start(retry, through_message_id=case.through).changed
    during_retry = queries.get_current(workspace_id=case.workspace_id)
    assert during_retry.failure == current.failure
    service.handoff(replace(retry, expected_version=3))
    service.publish(replace(retry, expected_version=4))
    assert queries.get_current(workspace_id=case.workspace_id).failure is None
