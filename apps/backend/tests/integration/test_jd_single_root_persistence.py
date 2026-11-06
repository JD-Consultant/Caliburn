"""單根鎖、局部 ORM 更新與完整快照的真 PostgreSQL 保證。"""

from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Event
from time import monotonic
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Connection, Engine, event, inspect, text
from sqlalchemy.engine import ExecutionContext
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from caliburn.modules.job_description.application.errors import (
    JobDescriptionConcurrencyError,
    JobDescriptionHistoryDataError,
    JobDescriptionNotFoundError,
)
from caliburn.modules.job_description.application.history_types import RestoreMetadata
from caliburn.modules.job_description.application.job_descriptions import (
    UpdateJobDescriptionInput,
    update_job_description,
)
from caliburn.modules.job_description.domain.models.condition_kind import ConditionKind
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)
from caliburn.modules.job_description.infrastructure.persistence import content_mapping
from caliburn.modules.job_description.infrastructure.persistence.orm_models import (
    JobDescriptionRow,
)
from caliburn.modules.job_description.infrastructure.persistence.snapshot_codec import (
    SCHEMA_VERSION,
    decode_snapshot,
    encode_snapshot,
)
from caliburn.modules.job_description.infrastructure.persistence.unit_of_work import (
    SqlAlchemyJobDescriptionUnitOfWork,
)
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory


def _create(engine: Engine, workspace_id: UUID) -> tuple[UUID, int]:
    root = JobDescription(id=uuid4(), workspace_id=workspace_id)
    with SqlAlchemyJobDescriptionUnitOfWork(create_session_factory(engine)) as uow:
        version = uow.job_descriptions.add(root)
        uow.commit()
    return root.id, version


def _populate(root: JobDescription) -> None:
    duty_id = root.add_duty(name="職責", scope="範圍")
    knowledge_id = root.add_knowledge(name="知識", description="內容")
    skill_id = root.add_skill(name="技能", description="內容")
    root.add_task(
        name="任務",
        duty_id=duty_id,
        outcomes=("成果",),
        requirements=("原要求",),
        knowledge=(knowledge_id,),
        skills=(skill_id,),
    )
    root.add_collaboration(collaborator_name="協作對象", scope="範圍")
    root.add_condition(kind=ConditionKind.WORK_ENVIRONMENT, text="條件")


def test_decoding_the_same_snapshot_builds_independent_editable_graphs() -> None:
    root = JobDescription(id=uuid4(), workspace_id=uuid4())
    _populate(root)
    content = encode_snapshot(root)
    first = decode_snapshot(
        content,
        schema_version=SCHEMA_VERSION,
        workspace_id=root.workspace_id,
        job_description_id=root.id,
    )
    second = decode_snapshot(
        content,
        schema_version=SCHEMA_VERSION,
        workspace_id=root.workspace_id,
        job_description_id=root.id,
    )
    original = root.model_dump()
    assert first.model_dump() == second.model_dump() == original
    task_id = first.tasks[0].id
    first.update_duty(duty_id=first.duties[0].id, name="新職責", scope="新範圍")
    first.update_task(
        task_id=task_id, name="新任務", description="新說明", competency_level=4
    )
    first.update_outcome(
        task_id=task_id, outcome_id=first.tasks[0].outcomes[0].id, text="新成果"
    )
    first.update_requirement(
        task_id=task_id, requirement_id=first.tasks[0].requirements[0].id, text="新要求"
    )
    first.update_knowledge(
        knowledge_id=first.knowledge[0].id, name="新知識", description="新說明"
    )
    first.update_skill(skill_id=first.skills[0].id, name="新技能", description="新說明")
    first.update_collaboration(
        collaboration_id=first.collaborations[0].id,
        collaborator_name="新對象",
        scope="新範圍",
    )
    first.update_condition(condition_id=first.conditions[0].id, text="新條件")

    assert first.model_dump() != original
    assert second.model_dump() == root.model_dump() == original
    assert content == encode_snapshot(root)
    first_content = first.model_dump()
    second.update_requirement(
        task_id=task_id,
        requirement_id=second.tasks[0].requirements[0].id,
        text="另一份的要求",
    )
    assert second.tasks[0].requirements[0].text == "另一份的要求"
    assert first.model_dump() == first_content
    assert root.model_dump() == original
    assert content == encode_snapshot(root)


def test_mapping_the_same_rows_builds_independent_editable_graphs(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    root = JobDescription(id=uuid4(), workspace_id=jd_workspace_id)
    _populate(root)
    with SqlAlchemyJobDescriptionUnitOfWork(create_session_factory(pg_engine)) as uow:
        uow.job_descriptions.add(root)
        uow.commit()
    original = root.model_dump()
    with Session(pg_engine) as session:
        row = session.get(JobDescriptionRow, root.id)
        assert row is not None
        rows = content_mapping.load_current_content(session, row)
        first, second = rows.to_domain(), rows.to_domain()
        assert first.model_dump() == second.model_dump() == original
        task_id = first.tasks[0].id
        first.update_duty(duty_id=first.duties[0].id, name="新職責", scope="新範圍")
        first.update_task(
            task_id=task_id, name="新任務", description="新說明", competency_level=4
        )
        first.update_outcome(
            task_id=task_id, outcome_id=first.tasks[0].outcomes[0].id, text="新成果"
        )
        first.update_requirement(
            task_id=task_id,
            requirement_id=first.tasks[0].requirements[0].id,
            text="新要求",
        )
        first.update_knowledge(
            knowledge_id=first.knowledge[0].id, name="新知識", description="新說明"
        )
        first.update_skill(
            skill_id=first.skills[0].id, name="新技能", description="新說明"
        )
        first.update_collaboration(
            collaboration_id=first.collaborations[0].id,
            collaborator_name="新對象",
            scope="新範圍",
        )
        first.update_condition(condition_id=first.conditions[0].id, text="新條件")

        assert first.model_dump() != original
        assert second.model_dump() == original
        first_content = first.model_dump()
        second.update_requirement(
            task_id=task_id,
            requirement_id=second.tasks[0].requirements[0].id,
            text="另一份的要求",
        )
        assert first.model_dump() == first_content
        assert second.tasks[0].requirements[0].text == "另一份的要求"
        assert rows.to_domain().model_dump() == root.model_dump() == original
        assert not session.dirty


def test_current_content_and_snapshots_replace_all_row_history(
    pg_engine: Engine,
) -> None:
    schema = inspect(pg_engine)
    tables = set(schema.get_table_names())
    assert "job_description_snapshots" in tables
    assert not {"transaction", "transaction_meta"} & tables
    assert not any(
        name.endswith("_version") and name != "alembic_version" for name in tables
    )
    for table in ("duties", "job_tasks", "knowledge", "skills"):
        assert not {"version", "name_key"} & {
            column["name"] for column in schema.get_columns(table)
        }


def test_empty_creation_has_committed_snapshot_and_scoped_root_reload(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    root = JobDescription(id=uuid4(), workspace_id=jd_workspace_id)
    with SqlAlchemyJobDescriptionUnitOfWork(sessions) as uow:
        assert uow.job_descriptions.add(root, correlation_id="create") == 1
        uow.commit()
    with SqlAlchemyJobDescriptionUnitOfWork(sessions) as uow:
        loaded = uow.job_descriptions.get_for_update(
            workspace_id=jd_workspace_id, job_description_id=root.id
        )
        assert loaded.version == 1
        assert loaded.job_description.model_dump() == root.model_dump()
        historic = uow.history.get(
            workspace_id=jd_workspace_id, job_description_id=root.id, version=1
        )
        assert historic.job_description.model_dump() == root.model_dump()
        assert historic.entry.kind == "created"
        assert historic.entry.correlation_id == "create"
        assert historic.entry.version == 1
        assert historic.entry.restored_from_version is None
        offset = historic.entry.recorded_at.utcoffset()
        assert offset is not None and offset.total_seconds() == 0
    with SqlAlchemyJobDescriptionUnitOfWork(sessions) as uow:
        with pytest.raises(JobDescriptionNotFoundError):
            uow.job_descriptions.get_for_update(
                workspace_id=uuid4(), job_description_id=root.id
            )
        with pytest.raises(JobDescriptionNotFoundError):
            uow.history.get(workspace_id=uuid4(), job_description_id=root.id, version=1)


def test_deep_edit_updates_only_changed_rows_and_preserves_complete_versions(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    jd_id, initial = _create(pg_engine, jd_workspace_id)
    sessions = create_session_factory(pg_engine)
    with SqlAlchemyJobDescriptionUnitOfWork(sessions) as uow:
        loaded = uow.job_descriptions.get_for_update(
            workspace_id=jd_workspace_id, job_description_id=jd_id
        )
        _populate(loaded.job_description)
        first = uow.job_descriptions.save(loaded.job_description)
        before_content = loaded.job_description.model_dump()
        uow.commit()
    writes: list[str] = []

    def capture(
        connection: Connection,
        cursor: object,
        statement: str,
        parameters: object,
        context: ExecutionContext,
        executemany: bool,
    ) -> None:
        if statement.lstrip().upper().startswith(("UPDATE ", "INSERT ", "DELETE ")):
            writes.append(statement)

    event.listen(pg_engine, "before_cursor_execute", capture)
    try:
        with SqlAlchemyJobDescriptionUnitOfWork(sessions) as uow:
            loaded = uow.job_descriptions.get_for_update(
                workspace_id=jd_workspace_id, job_description_id=jd_id
            )
            task = loaded.job_description.tasks[0]
            loaded.job_description.update_requirement(
                task_id=task.id, requirement_id=task.requirements[0].id, text="新要求"
            )
            second = uow.job_descriptions.save(loaded.job_description)
            after_content = loaded.job_description.model_dump()
            uow.commit()
    finally:
        event.remove(pg_engine, "before_cursor_execute", capture)
    assert (first, second) == (2, 3)
    assert {sql.split()[1] for sql in writes if sql.startswith("UPDATE ")} == {
        "job_descriptions",
        "task_requirements",
    }
    assert all(
        sql.startswith("UPDATE ")
        or sql.startswith("INSERT INTO job_description_snapshots ")
        for sql in writes
    )
    with SqlAlchemyJobDescriptionUnitOfWork(sessions) as uow:
        assert (
            uow.history.get(
                workspace_id=jd_workspace_id, job_description_id=jd_id, version=first
            ).job_description.model_dump()
            == before_content
        )
        assert (
            uow.history.get(
                workspace_id=jd_workspace_id, job_description_id=jd_id, version=second
            ).job_description.model_dump()
            == after_content
        )
        assert not uow.history.get(
            workspace_id=jd_workspace_id, job_description_id=jd_id, version=initial
        ).job_description.tasks
        loaded = uow.job_descriptions.get_for_update(
            workspace_id=jd_workspace_id, job_description_id=jd_id
        )
        assert uow.job_descriptions.save(loaded.job_description) == second
        uow.commit()
    with pg_engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT count(*) FROM job_description_snapshots"))
            == 3
        )


def test_repository_add_never_drops_a_complete_new_graph(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    root = JobDescription(id=uuid4(), workspace_id=jd_workspace_id)
    _populate(root)
    sessions = create_session_factory(pg_engine)
    with SqlAlchemyJobDescriptionUnitOfWork(sessions) as uow:
        saved = uow.job_descriptions.add(root)
        uow.commit()
    with SqlAlchemyJobDescriptionUnitOfWork(sessions) as uow:
        assert (
            uow.history.get(
                workspace_id=jd_workspace_id, job_description_id=root.id, version=saved
            ).job_description.model_dump()
            == root.model_dump()
        )


def test_history_reads_snapshot_without_reassembling_current_children(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    root = JobDescription(id=uuid4(), workspace_id=jd_workspace_id)
    _populate(root)
    sessions = create_session_factory(pg_engine)
    with SqlAlchemyJobDescriptionUnitOfWork(sessions) as uow:
        saved = uow.job_descriptions.add(root)
        uow.commit()
    statements: list[str] = []

    def capture(
        connection: Connection,
        cursor: object,
        statement: str,
        parameters: object,
        context: ExecutionContext,
        executemany: bool,
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT "):
            statements.append(statement)

    event.listen(pg_engine, "before_cursor_execute", capture)
    try:
        with SqlAlchemyJobDescriptionUnitOfWork(sessions) as uow:
            historic = uow.history.get(
                workspace_id=jd_workspace_id, job_description_id=root.id, version=saved
            )
            assert historic.job_description.model_dump() == root.model_dump()
    finally:
        event.remove(pg_engine, "before_cursor_execute", capture)
    assert any("job_description_snapshots" in sql for sql in statements)
    assert not any(
        "FROM job_tasks" in sql or "FROM knowledge" in sql for sql in statements
    )
    assert inspect(pg_engine).get_pk_constraint("job_description_snapshots")[
        "constrained_columns"
    ] == ["job_description_id", "version"]


def _stored_rows(engine: Engine) -> dict[str, tuple[str, ...]]:
    """獨立 SQL oracle 同時比較目前列與完整快照，含來源 metadata。"""
    with engine.connect() as connection:
        return {
            name: tuple(
                connection.scalars(
                    text(
                        f'SELECT to_jsonb(t)::text FROM "{name}" t '
                        "ORDER BY to_jsonb(t)::text"
                    )
                )
            )
            for name in inspect(connection).get_table_names()
            if name not in {"alembic_version", "workspaces"}
        }


@pytest.mark.parametrize("mode", ["edit", "restore", "same_content_restore"])
def test_flushed_edit_and_restores_rollback_content_version_and_snapshot(
    pg_engine: Engine, jd_workspace_id: UUID, mode: str
) -> None:
    root = JobDescription(id=uuid4(), workspace_id=jd_workspace_id)
    _populate(root)
    sessions = create_session_factory(pg_engine)
    with SqlAlchemyJobDescriptionUnitOfWork(sessions) as uow:
        original = uow.job_descriptions.add(root)
        uow.commit()
    with SqlAlchemyJobDescriptionUnitOfWork(sessions) as uow:
        current = uow.job_descriptions.get_for_update(
            workspace_id=jd_workspace_id, job_description_id=root.id
        )
        current.job_description.set_purpose(purpose="已保存的後續編修")
        latest = uow.job_descriptions.save(current.job_description)
        uow.commit()
    before = _stored_rows(pg_engine)
    with pytest.raises(RuntimeError, match="rollback probe"):
        with SqlAlchemyJobDescriptionUnitOfWork(sessions) as uow:
            loaded = uow.job_descriptions.get_for_update(
                workspace_id=jd_workspace_id, job_description_id=root.id
            )
            if mode == "edit":
                loaded.job_description.remove_task(
                    task_id=loaded.job_description.tasks[0].id
                )
                uow.job_descriptions.save(
                    loaded.job_description, correlation_id="failed-edit"
                )
            else:
                target = original if mode == "restore" else latest
                historical = uow.history.get(
                    workspace_id=jd_workspace_id,
                    job_description_id=root.id,
                    version=target,
                )
                assert (
                    uow.job_descriptions.save(
                        historical.job_description,
                        correlation_id="failed-restore",
                        restore=RestoreMetadata(
                            target_version=target, reverts_correlation_id="source"
                        ),
                    )
                    == latest + 1
                )
            raise RuntimeError("rollback probe")
    assert _stored_rows(pg_engine) == before


def test_real_constraint_failure_after_snapshot_flush_restores_every_row(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    root = JobDescription(id=uuid4(), workspace_id=jd_workspace_id)
    _populate(root)
    with SqlAlchemyJobDescriptionUnitOfWork(create_session_factory(pg_engine)) as uow:
        uow.job_descriptions.add(root)
        uow.commit()
    before = _stored_rows(pg_engine)
    session = Session(pg_engine)
    with pytest.raises(IntegrityError):
        with SqlAlchemyJobDescriptionUnitOfWork(lambda: session) as uow:
            loaded = uow.job_descriptions.get_for_update(
                workspace_id=jd_workspace_id, job_description_id=root.id
            )
            loaded.job_description.set_purpose(purpose="將回滾")
            uow.job_descriptions.save(loaded.job_description)
            session.execute(text("INSERT INTO duties SELECT * FROM duties LIMIT 1"))
    assert _stored_rows(pg_engine) == before


def test_same_root_waits_before_loading_and_other_root_is_independent(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    other_workspace = (
        WorkspaceService(lambda: SqlAlchemyWorkspaceUnitOfWork(sessions))
        .create(interviewee_name="另一份")
        .workspace_id
    )
    jd_id, _ = _create(pg_engine, jd_workspace_id)
    other_id, _ = _create(pg_engine, other_workspace)
    pids: Queue[int] = Queue()

    def make_waiting_session() -> Session:
        session = sessions()

        def after_begin(
            session: Session, transaction: object, connection: Connection
        ) -> None:
            pid = connection.scalar(text("SELECT pg_backend_pid()"))
            assert isinstance(pid, int)
            pids.put(pid)

        event.listen(session, "after_begin", after_begin)
        return session

    def waiting_writer() -> None:
        update_job_description(
            workspace_id=jd_workspace_id,
            input=UpdateJobDescriptionInput(
                job_description_id=jd_id, expected_version=1, purpose="過期要求不得寫入"
            ),
            uow_factory=lambda: SqlAlchemyJobDescriptionUnitOfWork(
                make_waiting_session
            ),
        )

    with ThreadPoolExecutor(max_workers=1) as pool:
        with SqlAlchemyJobDescriptionUnitOfWork(sessions) as first:
            loaded = first.job_descriptions.get_for_update(
                workspace_id=jd_workspace_id, job_description_id=jd_id
            )
            loaded.job_description.set_purpose(purpose="第一個提交")
            assert first.job_descriptions.save(loaded.job_description) == 2
            future = pool.submit(waiting_writer)
            waiting_pid = pids.get(timeout=3)
            deadline = monotonic() + 3
            blocked = False
            while monotonic() < deadline and not blocked:
                with pg_engine.connect() as observer:
                    blocked = bool(
                        observer.scalar(
                            text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"),
                            {"pid": waiting_pid},
                        )
                    )
                if not blocked:
                    Event().wait(0.01)
            assert blocked, "第二個 writer 必須真正在根鎖等待"
            with pg_engine.connect() as observer:
                assert (
                    observer.scalar(
                        text("SELECT count(*) FROM job_description_snapshots")
                    )
                    == 2
                )
            with SqlAlchemyJobDescriptionUnitOfWork(
                sessions, lock_timeout_ms=200
            ) as other:
                independent = other.job_descriptions.get_for_update(
                    workspace_id=other_workspace, job_description_id=other_id
                )
                independent.job_description.set_purpose(purpose="獨立提交")
                other.job_descriptions.save(independent.job_description)
                other.commit()
            first.commit()
        with pytest.raises(JobDescriptionConcurrencyError):
            future.result(timeout=3)
    with pg_engine.connect() as observer:
        assert (
            observer.scalar(
                text("SELECT purpose FROM job_descriptions WHERE id=:id"), {"id": jd_id}
            )
            == "第一個提交"
        )
        assert (
            observer.scalar(text("SELECT count(*) FROM job_description_snapshots")) == 4
        )


def test_root_lock_timeout_is_bounded_and_creates_no_snapshot(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    jd_id, _ = _create(pg_engine, jd_workspace_id)
    sessions = create_session_factory(pg_engine)
    before = _stored_rows(pg_engine)
    with SqlAlchemyJobDescriptionUnitOfWork(sessions) as first:
        assert (
            first.job_descriptions.get_for_update(
                workspace_id=jd_workspace_id, job_description_id=jd_id
            )
            is not None
        )
        with pytest.raises(JobDescriptionConcurrencyError):
            with SqlAlchemyJobDescriptionUnitOfWork(
                sessions, lock_timeout_ms=50
            ) as second:
                second.job_descriptions.get_for_update(
                    workspace_id=jd_workspace_id, job_description_id=jd_id
                )
    assert _stored_rows(pg_engine) == before


@pytest.mark.parametrize(
    "corruption", ["missing_definition", "duplicate_identity", "missing_task_content"]
)
def test_incomplete_snapshot_is_not_silently_projected(
    pg_engine: Engine, jd_workspace_id: UUID, corruption: str
) -> None:
    root = JobDescription(id=uuid4(), workspace_id=jd_workspace_id)
    _populate(root)
    sessions = create_session_factory(pg_engine)
    with SqlAlchemyJobDescriptionUnitOfWork(sessions) as uow:
        saved = uow.job_descriptions.add(root)
        uow.commit()
    with pg_engine.begin() as connection:
        changes = {
            "missing_definition": "jsonb_set(content, '{knowledge}', '[]'::jsonb)",
            "duplicate_identity": (
                "jsonb_set(content, '{knowledge}', "
                "(content->'knowledge') || (content->'knowledge'))"
            ),
            "missing_task_content": "content #- '{tasks,0,outcomes}'",
        }
        connection.execute(
            text(f"UPDATE job_description_snapshots SET content={changes[corruption]}")
        )
    with SqlAlchemyJobDescriptionUnitOfWork(sessions) as uow:
        with pytest.raises(JobDescriptionHistoryDataError):
            uow.history.get(
                workspace_id=jd_workspace_id, job_description_id=root.id, version=saved
            )


@pytest.mark.parametrize("first_operation", ["add", "edit", "noop"])
def test_uow_rejects_a_second_save_including_noop(
    pg_engine: Engine, jd_workspace_id: UUID, first_operation: str
) -> None:
    sessions = create_session_factory(pg_engine)
    jd_id = uuid4()
    if first_operation != "add":
        jd_id, _ = _create(pg_engine, jd_workspace_id)
    with SqlAlchemyJobDescriptionUnitOfWork(sessions) as uow:
        if first_operation == "add":
            root = JobDescription(id=jd_id, workspace_id=jd_workspace_id)
            first = uow.job_descriptions.add(root)
        else:
            loaded = uow.job_descriptions.get_for_update(
                workspace_id=jd_workspace_id, job_description_id=jd_id
            )
            root = loaded.job_description
            if first_operation == "edit":
                root.set_purpose(purpose="第一筆保存")
            first = uow.job_descriptions.save(root)
        with pytest.raises(RuntimeError, match="一次"):
            uow.job_descriptions.save(root)
        uow.commit()
    with SqlAlchemyJobDescriptionUnitOfWork(sessions) as uow:
        loaded = uow.job_descriptions.get_for_update(
            workspace_id=jd_workspace_id, job_description_id=jd_id
        )
        assert loaded.version == first
