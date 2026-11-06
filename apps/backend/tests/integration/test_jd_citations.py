"""沿公開用例驗證來源資格、原子編修、歷史與撤回交錯。"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from threading import Event
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, text

from caliburn.modules.interview.application.recording import record_turn_input
from caliburn.modules.interview.application.withdrawal import withdraw_turn
from caliburn.modules.interview.infrastructure.persistence.unit_of_work import (
    SqlAlchemyInterviewUnitOfWork,
)
from caliburn.modules.job_description.application.citation_inputs import (
    AddCitationInput,
    ConfirmCitationInput,
    RemoveCitationInput,
)
from caliburn.modules.job_description.application.citations import (
    ChangeCitationsInput,
    change_citations,
    get_citation,
)
from caliburn.modules.job_description.application.errors import (
    CitationSourceDataError,
    InvalidCitationSourceError,
)
from caliburn.modules.job_description.application.history.operations import (
    RestoreJobDescriptionInput,
    restore,
)
from caliburn.modules.job_description.application.job_descriptions import (
    UpdateJobDescriptionInput,
    update_job_description,
)
from caliburn.modules.job_description.application.tasks.inputs import (
    AddTaskInput,
    TaskPlacementInput,
    UpdateTaskInput,
)
from caliburn.modules.job_description.application.tasks.lifecycle import (
    add_task,
    delete_task,
    update_task,
)
from caliburn.modules.job_description.domain.models.citation import (
    CitationTargetKind,
    InterviewReference,
    MemoryReference,
)
from caliburn.modules.job_description.infrastructure.persistence import citation_sources
from caliburn.modules.job_description.infrastructure.persistence.queries import (
    SqlAlchemyJobDescriptionQueries,
)
from caliburn.modules.memory.application.inputs import MemoryWriteContext
from caliburn.modules.memory.application.service import MemoryService
from caliburn.modules.memory.domain.content import MemoryContent
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
from tests.integration.content_scenarios import C1, D1, JD, K1, Q1, S1, T1
from tests.integration.content_support import factory, read_current, seed_root


def source_message(
    engine: Engine, workspace_id: UUID
) -> tuple[UUID, InterviewReference]:
    turn_id = uuid4()
    message = record_turn_input(
        workspace_id=workspace_id,
        turn_id=turn_id,
        text="合成來源原話",
        uow_factory=partial(
            SqlAlchemyInterviewUnitOfWork, create_session_factory(engine)
        ),
    )
    return turn_id, InterviewReference(
        workspace_id=workspace_id, message_id=message.message_id
    )


def test_citation_attaches_reads_deletes_and_restores_with_original_id(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    seed_root(pg_engine, jd_workspace_id)
    _, source = source_message(pg_engine, jd_workspace_id)
    attached = update_task(
        workspace_id=jd_workspace_id,
        input=UpdateTaskInput(
            job_description_id=JD,
            expected_version=1,
            task_id=T1,
            citations=(AddCitationInput(source=source),),
        ),
        uow_factory=factory(pg_engine),
    )
    citation = attached.citations[0]
    result = get_citation(
        workspace_id=jd_workspace_id,
        job_description_id=JD,
        citation_id=citation.id,
        queries=SqlAlchemyJobDescriptionQueries(pg_engine),
        sources=citation_sources.SqlAlchemyCitationSourceQueries(pg_engine),
    )
    assert result.source.text == "合成來源原話"
    removed = delete_task(
        workspace_id=jd_workspace_id,
        job_description_id=JD,
        expected_version=2,
        task_id=T1,
        uow_factory=factory(pg_engine),
    )
    assert removed.citations == ()
    restored = restore(
        workspace_id=jd_workspace_id,
        input=RestoreJobDescriptionInput(
            job_description_id=JD, expected_version=3, target_version=2
        ),
        uow_factory=factory(pg_engine),
    )
    assert restored.citations == (citation,)
    assert read_current(pg_engine, workspace_id=jd_workspace_id).citations == (
        citation,
    )
    removed_source = change_citations(
        workspace_id=jd_workspace_id,
        input=ChangeCitationsInput(
            job_description_id=JD,
            expected_version=4,
            target_kind="task",
            target_id=T1,
            changes=(RemoveCitationInput(citation_id=citation.id),),
        ),
        uow_factory=factory(pg_engine),
    )
    assert removed_source.citations == ()
    assert removed_source.version == 5


def test_invalid_source_rolls_back_new_task_and_cross_workspace_is_rejected(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    seed_root(pg_engine, jd_workspace_id)
    sessions = create_session_factory(pg_engine)
    foreign = (
        WorkspaceService(partial(SqlAlchemyWorkspaceUnitOfWork, sessions))
        .create(interviewee_name="其他合成工作區")
        .workspace_id
    )
    _, source = source_message(pg_engine, foreign)
    for candidate in (
        source,
        InterviewReference(workspace_id=jd_workspace_id, message_id=source.message_id),
    ):
        with pytest.raises(InvalidCitationSourceError):
            add_task(
                workspace_id=jd_workspace_id,
                input=AddTaskInput(
                    job_description_id=JD,
                    expected_version=1,
                    name="不可留下的任務",
                    citations=(AddCitationInput(source=candidate),),
                ),
                uow_factory=factory(pg_engine),
            )
    current = read_current(pg_engine, workspace_id=jd_workspace_id)
    assert current.version == 1
    assert all(task.name != "不可留下的任務" for task in current.tasks)


def test_withdrawn_source_retains_locator_without_text_and_allows_unrelated_edit(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    seed_root(pg_engine, jd_workspace_id)
    turn_id, source = source_message(pg_engine, jd_workspace_id)
    attached = update_task(
        workspace_id=jd_workspace_id,
        input=UpdateTaskInput(
            job_description_id=JD,
            expected_version=1,
            task_id=T1,
            citations=(AddCitationInput(source=source),),
        ),
        uow_factory=factory(pg_engine),
    )
    withdraw_turn(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        uow_factory=partial(
            SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine)
        ),
    )
    updated = update_job_description(
        workspace_id=jd_workspace_id,
        input=UpdateJobDescriptionInput(
            job_description_id=JD, expected_version=2, purpose="無關修改"
        ),
        uow_factory=factory(pg_engine),
    )
    assert updated.citations == attached.citations
    view = get_citation(
        workspace_id=jd_workspace_id,
        job_description_id=JD,
        citation_id=attached.citations[0].id,
        queries=SqlAlchemyJobDescriptionQueries(pg_engine),
        sources=citation_sources.SqlAlchemyCitationSourceQueries(pg_engine),
    )
    assert view.source.availability == "unavailable"
    assert view.source.text is None
    with pytest.raises(InvalidCitationSourceError):
        change_citations(
            workspace_id=jd_workspace_id,
            input=ChangeCitationsInput(
                job_description_id=JD,
                expected_version=3,
                target_kind="job_description",
                target_id=JD,
                changes=(AddCitationInput(source=source),),
            ),
            uow_factory=factory(pg_engine),
        )


def test_review_is_sticky_for_human_but_move_and_read_do_not_change_it(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    seed_root(pg_engine, jd_workspace_id)
    _, source = source_message(pg_engine, jd_workspace_id)
    attached = update_task(
        workspace_id=jd_workspace_id,
        input=UpdateTaskInput(
            job_description_id=JD,
            expected_version=1,
            task_id=T1,
            citations=(AddCitationInput(source=source),),
        ),
        uow_factory=factory(pg_engine),
    )
    changed = update_task(
        workspace_id=jd_workspace_id,
        input=UpdateTaskInput(
            job_description_id=JD, expected_version=2, task_id=T1, competency_level=2
        ),
        uow_factory=factory(pg_engine),
    )
    assert changed.citations[0].jd_changed
    reverted = update_task(
        workspace_id=jd_workspace_id,
        input=UpdateTaskInput(
            job_description_id=JD, expected_version=3, task_id=T1, competency_level=None
        ),
        uow_factory=factory(pg_engine),
    )
    assert reverted.citations[0].jd_changed
    moved = update_task(
        workspace_id=jd_workspace_id,
        input=UpdateTaskInput(
            job_description_id=JD,
            expected_version=4,
            task_id=T1,
            placement=TaskPlacementInput(destination_duty_id=None),
        ),
        actor="consultant",
        uow_factory=factory(pg_engine),
    )
    assert moved.citations[0].jd_changed
    confirmed = change_citations(
        workspace_id=jd_workspace_id,
        input=ChangeCitationsInput(
            job_description_id=JD,
            expected_version=5,
            target_kind="task",
            target_id=T1,
            changes=(ConfirmCitationInput(citation_id=attached.citations[0].id),),
        ),
        uow_factory=factory(pg_engine),
    )
    assert not confirmed.citations[0].jd_changed


def test_source_turn_lock_prevents_withdrawal_between_validation_and_commit(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    seed_root(pg_engine, jd_workspace_id)
    turn_id, source = source_message(pg_engine, jd_workspace_id)
    started, finished = Event(), Event()

    def withdraw() -> None:
        started.set()
        withdraw_turn(
            workspace_id=jd_workspace_id,
            turn_id=turn_id,
            uow_factory=partial(
                SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine)
            ),
        )
        finished.set()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with factory(pg_engine)() as uow:
            loaded = uow.job_descriptions.get_for_update(
                workspace_id=jd_workspace_id, job_description_id=JD
            )
            uow.citation_sources.require_available(source=source)
            future = pool.submit(withdraw)
            assert started.wait(3)
            assert not finished.wait(0.15)
            loaded.job_description.add_citation(
                target_kind="task", target_id=T1, source=source
            )
            uow.job_descriptions.save(loaded.job_description)
            uow.commit()
        future.result(timeout=5)
    assert finished.is_set()
    current = read_current(pg_engine, workspace_id=jd_workspace_id)
    assert current.version == 2
    assert current.citations[0].source == source


@pytest.mark.parametrize(
    ("kind", "target"),
    (
        ("job_description", JD),
        ("duty", D1),
        ("task", T1),
        ("knowledge", K1),
        ("skill", S1),
        ("collaboration", C1),
        ("condition", Q1),
    ),
)
def test_all_seven_citation_targets_persist(
    pg_engine: Engine, jd_workspace_id: UUID, kind: CitationTargetKind, target: UUID
) -> None:
    seed_root(pg_engine, jd_workspace_id)
    _, source = source_message(pg_engine, jd_workspace_id)
    attached = change_citations(
        workspace_id=jd_workspace_id,
        input=ChangeCitationsInput(
            job_description_id=JD,
            expected_version=1,
            target_kind=kind,
            target_id=target,
            changes=(AddCitationInput(source=source),),
        ),
        uow_factory=factory(pg_engine),
    )
    citation = read_current(pg_engine, workspace_id=jd_workspace_id).citations[0]
    assert (citation.target_kind, citation.target_id) == (kind, target)
    assert citation == attached.citations[0]


@dataclass
class CompletedTurns:
    ids: frozenset[UUID]

    def completed_turn_ids(self, *, workspace_id: UUID) -> frozenset[UUID]:
        return self.ids


def test_memory_citation_stays_fixed_until_explicit_confirmation(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    seed_root(pg_engine, jd_workspace_id)
    turn, interview = source_message(pg_engine, jd_workspace_id)
    turns = CompletedTurns(frozenset((turn,)))
    service = MemoryService(
        partial(SqlAlchemyMemoryUnitOfWork, create_session_factory(pg_engine)),
        completed_turns=turns,
    )
    analysis = uuid4()

    def context(version: int) -> MemoryWriteContext:
        return MemoryWriteContext(
            workspace_id=jd_workspace_id, expected_version=version, analysis_id=analysis
        )

    service.start(context(0), through_message_id=interview.message_id)
    created = service.create_situation(
        context(1),
        content=MemoryContent(
            title="固定情境", description="情境說明", body="原發布正文"
        ),
        interview_message_ids=(interview.message_id,),
    )
    assert created.item_id is not None
    service.handoff(context(2))
    service.publish(context(3))
    fixed = MemoryReference(
        workspace_id=jd_workspace_id, published_version=4, item_id=created.item_id
    )
    attached = change_citations(
        workspace_id=jd_workspace_id,
        input=ChangeCitationsInput(
            job_description_id=JD,
            expected_version=1,
            target_kind="task",
            target_id=T1,
            changes=(AddCitationInput(source=fixed),),
        ),
        uow_factory=factory(pg_engine),
    )
    turn2, interview2 = source_message(pg_engine, jd_workspace_id)
    turns.ids |= {turn2}
    analysis = uuid4()
    service.start(context(4), through_message_id=interview2.message_id)
    service.revise_situation(
        context(5),
        item_id=created.item_id,
        content=MemoryContent(
            title="改名情境", description="新說明", body="新發布正文"
        ),
        interview_message_ids=(interview2.message_id,),
    )
    service.handoff(context(6))
    service.publish(context(7))
    citation = attached.citations[0]
    view = get_citation(
        workspace_id=jd_workspace_id,
        job_description_id=JD,
        citation_id=citation.id,
        queries=SqlAlchemyJobDescriptionQueries(pg_engine),
        sources=citation_sources.SqlAlchemyCitationSourceQueries(pg_engine),
        published_version=8,
        memory_queries=SqlAlchemyMemoryQueries(pg_engine),
    )
    assert view.source.text == "原發布正文"
    assert view.source.item_kind == "situation"
    assert view.source_changed is True
    assert view.needs_recheck is True
    assert (
        read_current(pg_engine, workspace_id=jd_workspace_id).citations
        == attached.citations
    )
    confirmed = change_citations(
        workspace_id=jd_workspace_id,
        input=ChangeCitationsInput(
            job_description_id=JD,
            expected_version=2,
            target_kind="task",
            target_id=T1,
            changes=(
                ConfirmCitationInput(citation_id=citation.id, published_version=8),
            ),
        ),
        uow_factory=factory(pg_engine),
    )
    assert confirmed.citations[0].id == citation.id
    assert confirmed.citations[0].source == MemoryReference(
        workspace_id=jd_workspace_id, published_version=8, item_id=created.item_id
    )
    restored = restore(
        workspace_id=jd_workspace_id,
        input=RestoreJobDescriptionInput(
            job_description_id=JD, expected_version=3, target_version=2
        ),
        uow_factory=factory(pg_engine),
    )
    assert restored.citations == attached.citations


def test_restore_allows_withdrawn_but_rejects_missing_fixed_source(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    seed_root(pg_engine, jd_workspace_id)
    turn_id, source = source_message(pg_engine, jd_workspace_id)
    attached = change_citations(
        workspace_id=jd_workspace_id,
        input=ChangeCitationsInput(
            job_description_id=JD,
            expected_version=1,
            target_kind="task",
            target_id=T1,
            changes=(AddCitationInput(source=source),),
        ),
        uow_factory=factory(pg_engine),
    )
    withdraw_turn(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        uow_factory=partial(
            SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine)
        ),
    )
    restored = restore(
        workspace_id=jd_workspace_id,
        input=RestoreJobDescriptionInput(
            job_description_id=JD, expected_version=2, target_version=2
        ),
        uow_factory=factory(pg_engine),
    )
    assert restored.citations == attached.citations
    with pg_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE job_description_snapshots SET content = "
                "jsonb_set(content, '{citations,0,source,message_id}', "
                "to_jsonb(CAST(:missing AS text))) "
                "WHERE job_description_id=:jd AND version=2"
            ),
            {"missing": str(uuid4()), "jd": JD},
        )
    with pytest.raises(CitationSourceDataError):
        restore(
            workspace_id=jd_workspace_id,
            input=RestoreJobDescriptionInput(
                job_description_id=JD, expected_version=3, target_version=2
            ),
            uow_factory=factory(pg_engine),
        )
    assert read_current(pg_engine, workspace_id=jd_workspace_id).version == 3
