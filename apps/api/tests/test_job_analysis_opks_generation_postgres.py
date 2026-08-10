"""Durable OPKS generation：provider 在交易外，commit 前重驗 authority。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork
from app.documents import load_document
from app.documents.authoring import create_document
from app.job_analysis.application import (
    OpksGenerationOutcome,
    OpksGenerationPayload,
    ScheduledOpks,
    StaleAuthoritySnapshot,
    add_opks_item,
    compute_analysis_input_digest,
    generate_opks_proposals,
    scheduled_opks_operation_id,
    select_scheduled_opks,
)
from app.job_analysis.application.errors import IdempotencyConflict
from app.core.domain import (
    CurrentWorkModel,
    JdHeader,
    JdTask,
    OpksEntityKind,
    OpksEvidenceLink,
    OpksGapAxis,
    OpksItem,
    SourceKind,
    SourceRef,
    SupportLink,
    Task,
)
from app.job_analysis.llm import (
    OpksDecision,
    OpksResultWire,
    OpksWireItem,
)
from app.job_analysis.providers import (
    OpenRouterAdapter,
    OpenRouterConfig,
    TransportResponse,
)


pytestmark = pytest.mark.asyncio
CONFIG = OpenRouterConfig(
    model="anthropic/claude-opus-5",
    provider_order=("anthropic",),
    max_output_tokens=1024,
    timeout_seconds=90,
)


def factory(session_factory):
    return lambda: SqlAlchemyJobAnalysisUnitOfWork(session_factory)


def source(source_id: str = "turn-1") -> SourceRef:
    return SourceRef(kind=SourceKind.EMPLOYEE_TURN, id=source_id)


SEEDED_STATEMENTS = {
    "task-1": "我每週彙整營運週報",
    "task-2": "我每月整理排班資料",
}


def digest_of(task_id: str = "task-1") -> str:
    """`seed()` 種下的那個 Task 的分析輸入指紋。

    child 只跑被排定的那一份輸入(ADR 0054 決定 10),所以每個呼叫端都得指名它預期的
    digest;拿不到凍結值的呼叫端本來就不該啟動 child。
    """

    return compute_analysis_input_digest(
        work_task(task_id, SEEDED_STATEMENTS[task_id])
    )


def work_task(task_id: str, statement: str) -> Task:
    return Task(
        task_id=task_id,
        statement=statement,
        action="彙整",
        object="營運資料",
        support_links=(
            SupportLink(
                source_ref=source(f"source-{task_id}"),
                quote=statement,
            ),
        ),
    )


def current_knowledge() -> OpksItem:
    return OpksItem(
        entity_id="knowledge-existing",
        entity_kind=OpksEntityKind.KNOWLEDGE,
        text="營運指標定義",
        evidence_links=(
            OpksEvidenceLink(
                source_ref=source("source-existing"),
                quote="我會先確認營運指標定義",
            ),
        ),
    )


async def seed(
    session_factory,
    document_id,
    *,
    include_second_task: bool = False,
    items: tuple[OpksItem, ...] = (),
    jd_header: JdHeader | None = None,
):
    uow_factory = factory(session_factory)
    await create_document(
        uow_factory,
        document_id=document_id,
        title="門市營運專員",
    )
    tasks = [work_task("task-1", SEEDED_STATEMENTS["task-1"])]
    jd = [JdTask(task_id="task-1", statement="彙整營運週報", display_order=0)]
    if include_second_task:
        tasks.append(work_task("task-2", SEEDED_STATEMENTS["task-2"]))
        jd.append(JdTask(task_id="task-2", statement="整理排班資料", display_order=1))
    async with uow_factory() as uow:
        record = await uow.documents.get(document_id, for_update=True)
        assert record is not None
        await uow.tasks.replace(document_id, tuple(jd))
        await uow.opks.replace(document_id, items)
        updated = await uow.documents.update_authority(
            document_id,
            expected_generation=record.authority_generation,
            jd_header=jd_header if jd_header is not None else record.jd_header,
            work_model=CurrentWorkModel(tasks=tuple(tasks)),
            active_question=record.active_question,
            updated_at=record.updated_at + timedelta(seconds=1),
        )
        assert updated
        await uow.commit()
    return uow_factory


def provider_response(wire: OpksResultWire) -> TransportResponse:
    return TransportResponse(
        status_code=200,
        body={
            "model": CONFIG.model,
            "choices": [
                {
                    "message": {"content": wire.model_dump_json(), "refusal": None},
                    "finish_reason": "stop",
                }
            ],
        },
    )


class RecordingTransport:
    def __init__(self, wire: OpksResultWire, before_return=None):
        self.response = provider_response(wire)
        self.before_return = before_return
        self.calls = 0

    async def __call__(self, *, url, headers, body, timeout):
        self.calls += 1
        if self.before_return is not None:
            await self.before_return()
        return self.response


def adapter(transport) -> OpenRouterAdapter:
    return OpenRouterAdapter(
        config=CONFIG,
        api_key="sk-test",
        transport=transport,
    )


def add_output_wire() -> OpksResultWire:
    return OpksResultWire(
        items=(
            OpksWireItem(
                entity_kind=OpksEntityKind.OUTPUT,
                decision=OpksDecision.ADD_NEW,
                target_ordinal=0,
                text="營運週報",
            ),
        )
    )


async def test_generation_persists_one_proposal_and_receipt_then_replays_without_call(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    header = JdHeader(
        competency_name="門市營運管理",
        work_description="負責門市日常營運與週報彙整。",
    )
    uow_factory = await seed(
        postgres_session_factory,
        document_id,
        jd_header=header,
    )
    transport = RecordingTransport(add_output_wire())

    first = await generate_opks_proposals(
        uow_factory,
        adapter=adapter(transport),
        document_id=document_id,
        task_id="task-1",
        expected_digest=digest_of(),
        operation_id="generate-1",
    )
    replay = await generate_opks_proposals(
        uow_factory,
        adapter=adapter(transport),
        document_id=document_id,
        task_id="task-1",
        expected_digest=digest_of(),
        operation_id="generate-1",
    )
    loaded = await load_document(uow_factory, document_id)

    assert first == replay
    assert first.outcome is OpksGenerationOutcome.PROPOSED
    assert first.proposal_ids == ("generate-1-op0",)
    assert transport.calls == 1
    assert loaded is not None
    assert loaded.document.authority_generation == 2
    assert loaded.state.jd_header == header
    proposal = loaded.state.opks_proposals[0]
    assert proposal.proposal_id == "generate-1-op0"
    assert proposal.entity_id == "generate-1-o0"
    assert proposal.after is not None
    assert proposal.after.task_refs == ("task-1",)
    assert loaded.state.current_opks.items == ()

    async with uow_factory() as uow:
        receipt = await uow.journal.get(document_id, "generate-1")
    assert receipt is not None
    assert isinstance(receipt.payload, OpksGenerationPayload)
    assert receipt.payload.selected_task_id == "task-1"
    assert receipt.payload.proposal_ids == ("generate-1-op0",)


async def test_same_key_for_another_task_is_an_idempotency_conflict_before_provider(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = await seed(
        postgres_session_factory,
        document_id,
        include_second_task=True,
    )
    transport = RecordingTransport(add_output_wire())
    model = adapter(transport)
    await generate_opks_proposals(
        uow_factory,
        adapter=model,
        document_id=document_id,
        task_id="task-1",
        expected_digest=digest_of(),
        operation_id="generate-same-key",
    )

    with pytest.raises(IdempotencyConflict):
        await generate_opks_proposals(
            uow_factory,
            adapter=model,
            document_id=document_id,
            task_id="task-2",
            expected_digest=digest_of("task-2"),
            operation_id="generate-same-key",
        )

    assert transport.calls == 1


async def test_empty_verified_result_commits_a_no_candidate_receipt(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = await seed(postgres_session_factory, document_id)
    transport = RecordingTransport(OpksResultWire(items=()))

    outcome = await generate_opks_proposals(
        uow_factory,
        adapter=adapter(transport),
        document_id=document_id,
        task_id="task-1",
        expected_digest=digest_of(),
        operation_id="generate-empty",
    )

    assert outcome.outcome is OpksGenerationOutcome.NO_CHANGE
    assert outcome.proposal_ids == ()
    assert transport.calls == 1
    async with uow_factory() as uow:
        receipt = await uow.journal.get(document_id, "generate-empty")
        proposals = await uow.opks_proposals.list(document_id)
    assert receipt is not None
    assert proposals == ()


async def test_reuse_existing_resolves_ordinal_to_stable_entity_id(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = await seed(
        postgres_session_factory,
        document_id,
        items=(current_knowledge(),),
    )
    transport = RecordingTransport(
        OpksResultWire(
            items=(
                OpksWireItem(
                    entity_kind=OpksEntityKind.KNOWLEDGE,
                    decision=OpksDecision.REUSE_EXISTING,
                    target_ordinal=1,
                    text="",
                ),
            )
        )
    )

    outcome = await generate_opks_proposals(
        uow_factory,
        adapter=adapter(transport),
        document_id=document_id,
        task_id="task-1",
        expected_digest=digest_of(),
        operation_id="generate-reuse",
    )
    loaded = await load_document(uow_factory, document_id)

    assert outcome.proposal_ids == ("generate-reuse-op0",)
    assert loaded is not None
    proposal = loaded.state.opks_proposals[0]
    assert proposal.entity_id == "knowledge-existing"
    assert proposal.before == current_knowledge()
    assert proposal.after is not None
    assert proposal.after.task_refs == ("task-1",)


async def test_reuse_that_adds_nothing_is_recorded_without_an_empty_proposal(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    already_linked = OpksItem(
        entity_id="knowledge-linked",
        entity_kind=OpksEntityKind.KNOWLEDGE,
        text="營運指標定義",
        task_refs=("task-1",),
        evidence_links=(
            OpksEvidenceLink(
                source_ref=source("source-task-1"),
                quote="我每週彙整營運週報",
            ),
        ),
    )
    uow_factory = await seed(
        postgres_session_factory,
        document_id,
        items=(already_linked,),
    )
    transport = RecordingTransport(
        OpksResultWire(
            items=(
                OpksWireItem(
                    entity_kind=OpksEntityKind.KNOWLEDGE,
                    decision=OpksDecision.REUSE_EXISTING,
                    target_ordinal=1,
                    text="",
                ),
            )
        )
    )

    outcome = await generate_opks_proposals(
        uow_factory,
        adapter=adapter(transport),
        document_id=document_id,
        task_id="task-1",
        expected_digest=digest_of(),
        operation_id="generate-noop-reuse",
    )
    loaded = await load_document(uow_factory, document_id)

    assert outcome.outcome is OpksGenerationOutcome.NO_CHANGE
    assert loaded is not None
    assert loaded.state.opks_proposals == ()
    assert loaded.state.current_opks.items == (already_linked,)


async def test_authority_change_during_provider_call_discards_result_and_receipt(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = await seed(postgres_session_factory, document_id)

    async def mutate_authority():
        await add_opks_item(
            uow_factory,
            document_id=document_id,
            entry_id="edit-during-provider",
            entity_kind=OpksEntityKind.ATTITUDE,
            text="主動釐清異常",
        )

    transport = RecordingTransport(add_output_wire(), before_return=mutate_authority)

    with pytest.raises(StaleAuthoritySnapshot):
        await generate_opks_proposals(
            uow_factory,
            adapter=adapter(transport),
            document_id=document_id,
            task_id="task-1",
            expected_digest=digest_of(),
            operation_id="generate-stale",
        )

    assert transport.calls == 1
    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    assert loaded.state.opks_proposals == ()
    async with uow_factory() as uow:
        assert await uow.journal.get(document_id, "generate-stale") is None


async def test_an_input_that_drifted_before_the_child_started_abandons_before_paying(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    """ADR 0054 決定 10、研究稿 §4.12 步驟 4a:**prepare 就比對 digest**。

    主回合把 `(task_id, D1)` 凍結進 receipt 之後、child 真的開始之前,員工仍可能直接
    編輯那個 Task(crash 後重開、replay 之間都會)。少了這道比對,child 會拿 D2 的輸入
    分析,卻把 receipt 寫在 D1 那個 key 上——下一輪 scheduler 算出 D2、`journal.get()`
    找不到,**同一份輸入再付一次錢**,而那筆 receipt 的 payload digest 也與自己的 key
    對不起來。

    比對放在 prepare 而不是 commit:漂移在呼叫 provider **之前**就看得出來,沒有理由
    先付錢再丟掉。
    """

    document_id = cleanup_job_analysis_rows
    uow_factory = await seed(postgres_session_factory, document_id)
    transport = RecordingTransport(add_output_wire())
    frozen = ScheduledOpks(
        task_id="task-1",
        analysis_input_digest=compute_analysis_input_digest(
            work_task("task-1", "這是主回合凍結當下的舊敘述")
        ),
    )

    with pytest.raises(StaleAuthoritySnapshot):
        await generate_opks_proposals(
            uow_factory,
            adapter=adapter(transport),
            document_id=document_id,
            task_id=frozen.task_id,
            operation_id=scheduled_opks_operation_id(frozen),
            expected_digest=frozen.analysis_input_digest,
        )

    assert transport.calls == 0, "漂移在 prepare 就看得出來,不該先付錢"
    async with uow_factory() as uow:
        receipt = await uow.journal.get(
            document_id, scheduled_opks_operation_id(frozen)
        )
    assert receipt is None, "abandon 不寫 receipt(決定 10),否則一次競態就永久壓住它"


# ── gap 落地成 OpenIssue 與 needs_clarification receipt(ADR 0054 決定 19、28、30)──


def gap_wire(*, with_proposal: bool = False) -> OpksResultWire:
    items = []
    if with_proposal:
        items.append(
            OpksWireItem(
                entity_kind=OpksEntityKind.OUTPUT,
                decision=OpksDecision.ADD_NEW,
                target_ordinal=0,
                text="營運週報",
            )
        )
    items.append(
        OpksWireItem(
            entity_kind=OpksEntityKind.SKILL,
            decision=OpksDecision.UNCERTAIN,
            target_ordinal=0,
            text="還看不出完成這件事需要哪些具體操作",
        )
    )
    return OpksResultWire(items=tuple(items))


async def test_a_gap_becomes_a_persisted_open_issue_with_its_task_and_axis(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = await seed(postgres_session_factory, document_id)

    result = await generate_opks_proposals(
        uow_factory,
        adapter=adapter(RecordingTransport(gap_wire())),
        document_id=document_id,
        task_id="task-1",
        expected_digest=digest_of(),
        operation_id="generate-gap",
    )
    loaded = await load_document(uow_factory, document_id)

    assert result.outcome is OpksGenerationOutcome.NEEDS_CLARIFICATION
    assert result.gap_issue_ids == ("generate-gap-gap0",)
    assert result.proposal_ids == ()
    assert result.analysis_input_digest
    assert loaded is not None
    (issue,) = loaded.state.work_model.open_issues
    assert issue.id == "generate-gap-gap0"
    assert issue.subject_task_id == "task-1"
    assert issue.opks_axis is OpksGapAxis.SKILL
    assert issue.summary == "還看不出完成這件事需要哪些具體操作"
    assert issue.is_active is True
    assert issue.source_anchors


async def test_proposals_and_gaps_are_published_together_in_one_transaction(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    """決定 18／28／30:效力單位是 item,三者同一交易寫入。"""

    document_id = cleanup_job_analysis_rows
    uow_factory = await seed(postgres_session_factory, document_id)

    result = await generate_opks_proposals(
        uow_factory,
        adapter=adapter(RecordingTransport(gap_wire(with_proposal=True))),
        document_id=document_id,
        task_id="task-1",
        expected_digest=digest_of(),
        operation_id="generate-both",
    )
    loaded = await load_document(uow_factory, document_id)

    assert result.outcome is OpksGenerationOutcome.NEEDS_CLARIFICATION
    assert result.proposal_ids == ("generate-both-op0",)
    assert result.gap_issue_ids == ("generate-both-gap1",)
    assert loaded is not None
    assert len(loaded.state.opks_proposals) == 1
    assert len(loaded.state.work_model.open_issues) == 1
    async with uow_factory() as uow:
        receipt = await uow.journal.get(document_id, "generate-both")
    assert receipt is not None
    assert receipt.payload.gap_issue_ids == ("generate-both-gap1",)


async def test_a_replayed_generation_does_not_duplicate_the_gap_issue(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    """ID 決定性:同一個 operation 重跑必須產生同一批 ID,否則留下兩份缺口。"""

    document_id = cleanup_job_analysis_rows
    uow_factory = await seed(postgres_session_factory, document_id)
    transport = RecordingTransport(gap_wire())

    first = await generate_opks_proposals(
        uow_factory,
        adapter=adapter(transport),
        document_id=document_id,
        task_id="task-1",
        expected_digest=digest_of(),
        operation_id="generate-gap",
    )
    replay = await generate_opks_proposals(
        uow_factory,
        adapter=adapter(transport),
        document_id=document_id,
        task_id="task-1",
        expected_digest=digest_of(),
        operation_id="generate-gap",
    )
    loaded = await load_document(uow_factory, document_id)

    assert first == replay
    assert transport.calls == 1
    assert loaded is not None
    assert len(loaded.state.work_model.open_issues) == 1


# ── 終端失敗與 abandon 必須分開(ADR 0054 決定 10、29)────────────────────────


class FailingTransport:
    """provider 回非 200:terminal 失敗的其中一種。"""

    def __init__(self):
        self.calls = 0

    async def __call__(self, *, url, headers, body, timeout):
        self.calls += 1
        return TransportResponse(status_code=503, body={"error": "upstream down"})


def refusal_wire_response() -> TransportResponse:
    return TransportResponse(
        status_code=200,
        body={
            "model": CONFIG.model,
            "choices": [
                {
                    "message": {"content": None, "refusal": "我無法協助這個請求"},
                    "finish_reason": "stop",
                }
            ],
        },
    )


class RefusingTransport:
    def __init__(self):
        self.calls = 0

    async def __call__(self, *, url, headers, body, timeout):
        self.calls += 1
        return refusal_wire_response()


class MalformedTransport:
    """回 200 但不是合法的 opks_result_v1:invalid_output。"""

    def __init__(self):
        self.calls = 0

    async def __call__(self, *, url, headers, body, timeout):
        self.calls += 1
        return TransportResponse(
            status_code=200,
            body={
                "model": CONFIG.model,
                "choices": [
                    {
                        "message": {"content": '{"items": "not a list"}', "refusal": None},
                        "finish_reason": "stop",
                    }
                ],
            },
        )


def rejected_wire() -> OpksResultWire:
    """target ordinal 不存在:verifier rejected。"""

    return OpksResultWire(
        items=(
            OpksWireItem(
                entity_kind=OpksEntityKind.KNOWLEDGE,
                decision=OpksDecision.REUSE_EXISTING,
                target_ordinal=99,
                text="",
            ),
        )
    )


@pytest.mark.parametrize(
    "transport_factory",
    [
        FailingTransport,
        RefusingTransport,
        MalformedTransport,
        lambda: RecordingTransport(rejected_wire()),
    ],
    ids=["provider_error", "refused", "invalid_output", "verifier_rejected"],
)
async def test_every_terminal_failure_writes_a_failed_receipt(
    postgres_session_factory,
    cleanup_job_analysis_rows,
    transport_factory,
):
    """決定 29:四種 outcome 在阻擋效果上等價,差別只在呈現與診斷。

    `failed` 的作用是解除 head-of-line blocking——否則同一個 Task 每輪都會被重新
    排定、每輪都再燒一次錢。
    """

    document_id = cleanup_job_analysis_rows
    uow_factory = await seed(postgres_session_factory, document_id)

    result = await generate_opks_proposals(
        uow_factory,
        adapter=adapter(transport_factory()),
        document_id=document_id,
        task_id="task-1",
        expected_digest=digest_of(),
        operation_id="generate-failed",
    )
    loaded = await load_document(uow_factory, document_id)

    assert result.outcome is OpksGenerationOutcome.FAILED
    assert result.proposal_ids == ()
    assert result.gap_issue_ids == ()
    assert result.analysis_input_digest
    assert loaded is not None
    assert loaded.state.opks_proposals == ()
    assert loaded.state.work_model.open_issues == ()
    async with uow_factory() as uow:
        receipt = await uow.journal.get(document_id, "generate-failed")
    assert receipt is not None
    assert receipt.payload.outcome is OpksGenerationOutcome.FAILED


async def test_a_failed_receipt_stops_the_same_input_from_being_rescheduled(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = await seed(postgres_session_factory, document_id)
    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    async with uow_factory() as uow:
        before = await select_scheduled_opks(
            uow,
            document_id=document_id,
            state=loaded.state,
        )
    assert before is not None

    await generate_opks_proposals(
        uow_factory,
        adapter=adapter(FailingTransport()),
        document_id=document_id,
        task_id=before.task_id,
        expected_digest=before.analysis_input_digest,
        operation_id=scheduled_opks_operation_id(before),
    )

    async with uow_factory() as uow:
        after = await select_scheduled_opks(
            uow,
            document_id=document_id,
            state=loaded.state,
        )

    assert after is None


async def test_digest_drift_abandons_without_writing_any_receipt(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    """決定 10:abandon 與 failed 必須分開。

    漂移代表已有更新的回合,由該回合排定自己的 child。用一次偶發競態永久壓住一個
    digest 是錯的——所以這條路徑**不寫 receipt**,同一個輸入之後仍排得到。
    """

    document_id = cleanup_job_analysis_rows
    uow_factory = await seed(postgres_session_factory, document_id)

    async def drift():
        await add_opks_item(
            uow_factory,
            document_id=document_id,
            entry_id="employee-edit-during-call",
            entity_kind=OpksEntityKind.OUTPUT,
            text="員工自己補的產出",
            task_refs=("task-1",),
        )

    transport = RecordingTransport(add_output_wire(), before_return=drift)

    with pytest.raises(StaleAuthoritySnapshot):
        await generate_opks_proposals(
            uow_factory,
            adapter=adapter(transport),
            document_id=document_id,
            task_id="task-1",
            expected_digest=digest_of(),
            operation_id="generate-abandoned",
        )

    async with uow_factory() as uow:
        receipt = await uow.journal.get(document_id, "generate-abandoned")

    assert receipt is None
