"""Minimal durable consultation use case; no network."""

from __future__ import annotations

import app.consultation as consultation
import pytest

from app.adapters.postgres import SqlAlchemyJobAnalysisUnitOfWork
from app.consultation import UncommittableOperationResult
from app.core.errors import IdempotencyConflict
from app.documents import load_document
from app.documents.authoring import create_document
from app.task_analysis.llm import (
    IdentityRelation,
    SignalDisposition,
    TaskAnalysisWire,
    WireAnchor,
    WireNextQuestion,
    WireSignal,
    WireTaskChange,
    WireTaskFields,
)
from app.adapters.openrouter import (
    ProviderFailure,
    ProviderFailureKind,
    ProviderText,
)


pytestmark = pytest.mark.asyncio


def factory(session_factory):
    return lambda: SqlAlchemyJobAnalysisUnitOfWork(session_factory)


def verified_text() -> ProviderText:
    result = TaskAnalysisWire(
        work_signals=(
            WireSignal(
                anchors=(
                    WireAnchor(
                        turn_ordinal=2,
                        quote="我每週會彙整營運週報",
                    ),
                ),
                relation=IdentityRelation.NO_MATCH,
                disposition=SignalDisposition.TASK_CHANGE,
                change=WireTaskChange.ADD,
                task=WireTaskFields(
                    statement="每週彙整營運週報",
                    action="彙整",
                    object="營運週報",
                    purpose_result="讓主管掌握營運狀況",
                ),
            ),
        ),
        next_question=WireNextQuestion(
            text="這份週報主要提供給誰？",
        ),
    )
    return ProviderText(text=result.model_dump_json())


class StaticAdapter:
    def __init__(self, outcome) -> None:
        self.outcome = outcome
        self.calls = 0

    async def complete(self, **kwargs):
        self.calls += 1
        return self.outcome


async def test_committed_turn_replay_skips_the_provider_before_prepare(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    submit = getattr(consultation, "submit_employee_turn", None)
    assert submit is not None
    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    adapter = StaticAdapter(verified_text())
    await create_document(uow_factory, document_id=document_id, title="營運專員")

    await submit(
        uow_factory,
        task_analysis_adapter=adapter,
        opks_adapter=adapter,
        document_id=document_id,
        operation_id="turn-1",
        text="我每週會彙整營運週報",
    )
    await submit(
        uow_factory,
        task_analysis_adapter=adapter,
        opks_adapter=adapter,
        document_id=document_id,
        operation_id="turn-1",
        text="我每週會彙整營運週報",
    )
    loaded = await load_document(uow_factory, document_id)

    assert adapter.calls == 1
    assert loaded is not None
    assert [turn.speaker.value for turn in loaded.conversation_turns] == [
        "consultant",
        "employee",
        "consultant",
    ]
    assert loaded.document.authority_generation == 1

    with pytest.raises(IdempotencyConflict):
        await submit(
            uow_factory,
            task_analysis_adapter=adapter,
            opks_adapter=adapter,
            document_id=document_id,
            operation_id="turn-1",
            text="其實我每月才做一次",
        )
    assert adapter.calls == 1


async def test_provider_failure_leaves_only_the_opening(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    submit = getattr(consultation, "submit_employee_turn", None)
    assert submit is not None
    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    adapter = StaticAdapter(
        ProviderFailure(kind=ProviderFailureKind.TIMEOUT, detail="timed out")
    )
    await create_document(uow_factory, document_id=document_id, title="營運專員")

    with pytest.raises(UncommittableOperationResult):
        await submit(
            uow_factory,
            task_analysis_adapter=adapter,
            opks_adapter=adapter,
            document_id=document_id,
            operation_id="turn-failed",
            text="我每週會彙整營運週報",
        )

    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    assert adapter.calls == 1
    assert len(loaded.conversation_turns) == 1
    assert loaded.document.authority_generation == 0


# ── 一次 /turns 最多主顧問 ＋ 一個 OPKS child(ADR 0054 決定 9、32、34)────────


OPKS_SCHEMA = "opks_result_v1"


def support_only_text() -> ProviderText:
    """只補依據、不動 Task 的一輪:讓已在 JD 的 Task 維持 eligible。"""

    result = TaskAnalysisWire(
        work_signals=(
            WireSignal(
                anchors=(WireAnchor(turn_ordinal=2, quote="我每週會彙整營運週報"),),
                relation=IdentityRelation.DUPLICATE,
                target_task_ordinals=(1,),
                disposition=SignalDisposition.SUPPORT_ONLY,
                task=WireTaskFields(statement="", action="", object=""),
            ),
        ),
        next_question=WireNextQuestion(text="這份週報主要提供給誰？"),
    )
    return ProviderText(text=result.model_dump_json())


def opks_text() -> ProviderText:
    from app.core.domain import OpksEntityKind
    from app.opks.llm import OpksDecision, OpksResultWire, OpksWireItem

    wire = OpksResultWire(
        items=(
            OpksWireItem(
                entity_kind=OpksEntityKind.OUTPUT,
                decision=OpksDecision.ADD_NEW,
                target_ordinal=0,
                text="營運週報",
            ),
            OpksWireItem(
                entity_kind=OpksEntityKind.SKILL,
                decision=OpksDecision.UNCERTAIN,
                target_ordinal=0,
                text="還看不出完成這件事需要哪些具體操作",
            ),
        )
    )
    return ProviderText(text=wire.model_dump_json())


class ScriptedAdapter:
    """依 `schema_name` 分流,並記下每種 operation 被呼叫幾次。"""

    def __init__(self, *, opks=None, opks_raises=None) -> None:
        self.opks = opks if opks is not None else opks_text()
        self.opks_raises = opks_raises
        self.turn_calls = 0
        self.opks_calls = 0

    async def complete(self, **kwargs):
        if kwargs["schema_name"] == OPKS_SCHEMA:
            self.opks_calls += 1
            if self.opks_raises is not None:
                raise self.opks_raises
            return self.opks
        self.turn_calls += 1
        return support_only_text()


async def seed_task_in_jd(uow_factory, document_id):
    from datetime import timedelta

    from app.core.domain import (
        CurrentWorkModel,
        JdTask,
        SourceKind,
        SourceRef,
        SupportLink,
        Task,
    )

    analysed = Task(
        task_id="task-existing",
        statement="每週彙整營運週報",
        action="彙整",
        object="營運週報",
        support_links=(
            SupportLink(
                source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id="old-turn"),
                quote="我每週會整理營運週報",
            ),
        ),
    )
    async with uow_factory() as uow:
        record = await uow.documents.get(document_id, for_update=True)
        assert record is not None
        assert await uow.documents.update_authority(
            document_id,
            expected_generation=record.authority_generation,
            jd_header=record.jd_header,
            work_model=CurrentWorkModel(tasks=(analysed,)),
            active_question=None,
            updated_at=record.updated_at + timedelta(seconds=1),
        )
        await uow.tasks.replace(
            document_id,
            (
                JdTask(
                    task_id="task-existing",
                    statement="每週彙整營運週報",
                    display_order=0,
                ),
            ),
        )
        await uow.commit()


async def submit(uow_factory, adapter, document_id, operation_id="turn-1"):
    return await consultation.submit_employee_turn(
        uow_factory,
        task_analysis_adapter=adapter,
        opks_adapter=adapter,
        document_id=document_id,
        operation_id=operation_id,
        text="我每週會彙整營運週報",
    )


async def test_one_turn_runs_the_consultant_then_its_scheduled_opks_child(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    await create_document(uow_factory, document_id=document_id, title="營運專員")
    await seed_task_in_jd(uow_factory, document_id)
    adapter = ScriptedAdapter()

    await submit(uow_factory, adapter, document_id)
    loaded = await load_document(uow_factory, document_id)

    assert (adapter.turn_calls, adapter.opks_calls) == (1, 1)
    assert loaded is not None
    assert len(loaded.state.opks_proposals) == 1
    gaps = [
        issue
        for issue in loaded.state.work_model.open_issues
        if issue.opks_axis is not None
    ]
    assert len(gaps) == 1
    assert gaps[0].subject_task_id == "task-existing"


async def test_a_failing_child_never_turns_the_committed_turn_into_an_error(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    """決定 32:主回合已經寫進資料庫,員工的話已經留下。"""

    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    await create_document(uow_factory, document_id=document_id, title="營運專員")
    await seed_task_in_jd(uow_factory, document_id)
    adapter = ScriptedAdapter(
        opks=ProviderFailure(
            kind=ProviderFailureKind.CONNECTION,
            detail="upstream down",
        )
    )

    await submit(uow_factory, adapter, document_id)
    loaded = await load_document(uow_factory, document_id)

    assert loaded is not None
    assert loaded.state.opks_proposals == ()
    assert loaded.conversation_turns[-1].speaker.value == "consultant"
    assert loaded.document.authority_generation >= 1


async def test_replaying_the_same_turn_pays_for_neither_call_twice(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    await create_document(uow_factory, document_id=document_id, title="營運專員")
    await seed_task_in_jd(uow_factory, document_id)
    adapter = ScriptedAdapter()

    await submit(uow_factory, adapter, document_id)
    await submit(uow_factory, adapter, document_id)

    assert (adapter.turn_calls, adapter.opks_calls) == (1, 1)


async def test_a_crash_before_the_child_ran_is_resumed_by_the_same_replay(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    """決定 9:主回合 commit 後、child 執行前崩潰,replay 恢復**同一個** child。

    **沒有 background worker**,所以單純 reload 不會補跑;恢復只發生在這一條路徑,
    或後續回合的 scheduler 再次選到同一個 child ID。
    """

    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    await create_document(uow_factory, document_id=document_id, title="營運專員")
    await seed_task_in_jd(uow_factory, document_id)
    crashing = ScriptedAdapter(opks_raises=RuntimeError("process died"))

    with pytest.raises(RuntimeError):
        await submit(uow_factory, crashing, document_id)

    after_crash = await load_document(uow_factory, document_id)
    assert after_crash is not None
    assert after_crash.state.opks_proposals == ()
    assert crashing.turn_calls == 1

    healthy = ScriptedAdapter()
    await submit(uow_factory, healthy, document_id)
    resumed = await load_document(uow_factory, document_id)

    assert healthy.turn_calls == 0, "主回合已提交,不得重付"
    assert healthy.opks_calls == 1
    assert resumed is not None
    assert len(resumed.state.opks_proposals) == 1


async def test_reloading_the_document_does_not_run_the_missing_child(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    """誠實邊界:沒有 background worker,單純 reload／GET 不會自行補跑。

    這一筆存在是為了擋住日後有人「順手」在讀取路徑加一個隱性 worker。
    """

    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    await create_document(uow_factory, document_id=document_id, title="營運專員")
    await seed_task_in_jd(uow_factory, document_id)
    crashing = ScriptedAdapter(opks_raises=RuntimeError("process died"))
    with pytest.raises(RuntimeError):
        await submit(uow_factory, crashing, document_id)

    for _ in range(3):
        await load_document(uow_factory, document_id)
    loaded = await load_document(uow_factory, document_id)

    assert loaded is not None
    assert loaded.state.opks_proposals == ()
    assert loaded.state.work_model.open_issues == ()
