"""OPKS first slice 的無網路 PostgreSQL scripted vertical。

這支 driver 使用真 application use cases、真 UoW／repositories／serialization 與
authority commit seam；只有 provider 回應是事先寫好的。它驗證管線與交易，不驗證模型品質。

用法（working directory: ``apps/api``）：

``uv run python scripts/job_analysis_opks_smoke.py``
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

# 直接執行 scripts/ 下檔案時，apps/api 尚未在 sys.path。
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.job_analysis.application import (  # noqa: E402
    JobAnalysisState,
    OpksGroundingUnavailable,
    add_jd_task,
    add_opks_item,
    compute_analysis_input_digest,
    create_document,
    decide_opks_proposal,
    delete_jd_task,
    delete_opks_item,
    edit_opks_item,
    generate_opks_proposals,
    load_document,
)
from app.job_analysis.application.authority_commit import (  # noqa: E402
    commit_authority_change,
)
from app.job_analysis.application.persistence import (  # noqa: E402
    JobAnalysisUnitOfWorkFactory,
)
from app.job_analysis.domain import (  # noqa: E402
    CurrentWorkModel,
    JdTask,
    JdTaskFields,
    OpksEntityKind,
    OpksProposalStatus,
    SourceKind,
    SourceRef,
    SupportLink,
    Task,
)
from app.job_analysis.llm import (  # noqa: E402
    OpksDecision,
    OpksResultWire,
    OpksWireItem,
)
from app.job_analysis.providers import (  # noqa: E402
    OpenRouterAdapter,
    OpenRouterConfig,
    TransportResponse,
)


CONFIG = OpenRouterConfig(
    model="anthropic/claude-opus-5",
    provider_order=("anthropic",),
    max_output_tokens=1024,
    timeout_seconds=90,
)


async def _analysis_digest(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    document_id,
    task_id: str,
) -> str:
    """該 Task 目前的分析輸入指紋。

    child 只跑被排定的那一份輸入(ADR 0054 決定 10),所以每個呼叫端都得指名它預期的
    digest;production 的來源是主回合凍結進 receipt 的 `ScheduledOpks`。
    """

    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    task = loaded.state.work_model.task_by_id(task_id)
    assert task is not None
    return compute_analysis_input_digest(task)


@dataclass(frozen=True)
class ScenarioMetrics:
    name: str
    proposal_count: int
    current_opks_count: int
    journal_count: int
    provider_calls: int
    note: str


@dataclass(frozen=True)
class OpksSmokeReport:
    scenarios: tuple[ScenarioMetrics, ...]
    generation_replay_equal: bool
    decision_statuses: tuple[OpksProposalStatus, ...]
    reused_entity_id: str
    reused_task_refs: tuple[str, ...]
    isolation_unchanged: bool
    ungrounded_state_unchanged: bool

    @property
    def provider_calls(self) -> int:
        return self.scenarios[-1].provider_calls

    @property
    def scenario_names(self) -> tuple[str, ...]:
        return tuple(scenario.name for scenario in self.scenarios)

    def render(self) -> str:
        lines = [
            f"{len(self.scenarios)}/{len(self.scenarios)} scripted scenarios passed",
            f"provider calls: {self.provider_calls}",
        ]
        for scenario in self.scenarios:
            lines.append(
                f"- {scenario.name}: proposals={scenario.proposal_count}, "
                f"current_opks={scenario.current_opks_count}, "
                f"journal={scenario.journal_count}, "
                f"provider_calls={scenario.provider_calls}; {scenario.note}"
            )
        lines.append("no model-quality claim: scripted provider, no network")
        return "\n".join(lines)


class ScriptedTransport:
    """逐次回傳 compact wire，並記錄唯一可發生的模型呼叫數。"""

    def __init__(self, responses: tuple[OpksResultWire, ...]) -> None:
        self._responses = responses
        self.calls = 0

    async def __call__(self, *, url, headers, body, timeout) -> TransportResponse:
        del url, headers, body, timeout
        if self.calls >= len(self._responses):
            raise AssertionError("scripted OPKS provider received an unexpected call")
        wire = self._responses[self.calls]
        self.calls += 1
        return TransportResponse(
            status_code=200,
            body={
                "model": CONFIG.model,
                "choices": [
                    {
                        "message": {
                            "content": wire.model_dump_json(),
                            "refusal": None,
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
        )


def _task(task_id: str, statement: str, source_id: str) -> Task:
    return Task(
        task_id=task_id,
        statement=statement,
        action="彙整",
        object="營運資料",
        support_links=(
            SupportLink(
                source_ref=SourceRef(
                    kind=SourceKind.EMPLOYEE_TURN,
                    id=source_id,
                ),
                quote=statement,
            ),
        ),
    )


async def _seed_grounded_document(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
) -> None:
    await create_document(
        uow_factory,
        document_id=document_id,
        title="門市營運專員 [scripted OPKS smoke]",
    )
    tasks = (
        _task("task-1", "我每週彙整營運週報", "employee-turn-1"),
        _task("task-2", "我每月整理排班資料", "employee-turn-2"),
    )
    async with uow_factory() as uow:
        record = await uow.documents.get(document_id, for_update=True)
        assert record is not None
        await commit_authority_change(
            uow,
            record=record,
            state=JobAnalysisState(
                work_model=CurrentWorkModel(tasks=tasks),
                current_jd=(
                    JdTask(
                        task_id="task-1",
                        statement="彙整營運週報",
                        display_order=0,
                    ),
                    JdTask(
                        task_id="task-2",
                        statement="整理排班資料",
                        display_order=1,
                    ),
                ),
            ),
            updated_at=datetime.now(UTC),
        )


def _initial_generation() -> OpksResultWire:
    return OpksResultWire(
        items=tuple(
            OpksWireItem(
                entity_kind=kind,
                decision=OpksDecision.ADD_NEW,
                target_ordinal=0,
                text=text,
            )
            for kind, text in (
                (OpksEntityKind.OUTPUT, "營運週報"),
                (OpksEntityKind.INDICATOR, "依排程完成週報並核對異常"),
                (OpksEntityKind.KNOWLEDGE, "營運指標定義"),
                (OpksEntityKind.SKILL, "營運資料彙整"),
            )
        )
    )


def _reuse_knowledge() -> OpksResultWire:
    return OpksResultWire(
        items=(
            OpksWireItem(
                entity_kind=OpksEntityKind.KNOWLEDGE,
                decision=OpksDecision.REUSE_EXISTING,
                target_ordinal=1,
                text="",
            ),
        )
    )


def _pending_output_revision() -> OpksResultWire:
    return OpksResultWire(
        items=(
            OpksWireItem(
                entity_kind=OpksEntityKind.OUTPUT,
                decision=OpksDecision.REVISE_EXISTING,
                target_ordinal=1,
                text="每週營運異常分析報告",
            ),
        )
    )


async def _known_journal_count(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    document_id: UUID,
    entry_ids: tuple[str, ...],
) -> int:
    async with uow_factory() as uow:
        count = 0
        for entry_id in entry_ids:
            if await uow.journal.get(document_id, entry_id) is not None:
                count += 1
        return count


async def _metrics(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
    transport: ScriptedTransport,
    journal_ids: tuple[str, ...],
    name: str,
    note: str,
) -> ScenarioMetrics:
    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    return ScenarioMetrics(
        name=name,
        proposal_count=len(loaded.state.opks_proposals),
        current_opks_count=len(loaded.state.current_opks.items),
        journal_count=await _known_journal_count(
            uow_factory, document_id, journal_ids
        ),
        provider_calls=transport.calls,
        note=note,
    )


async def run_scripted_opks_smoke(
    *,
    uow_factory: JobAnalysisUnitOfWorkFactory,
    document_id: UUID,
    isolation_document_id: UUID,
) -> OpksSmokeReport:
    """執行七個 frozen scripted scenarios；不讀 API key，也沒有網路路徑。"""

    await _seed_grounded_document(uow_factory, document_id=document_id)
    await create_document(
        uow_factory,
        document_id=isolation_document_id,
        title="隔離文件 [scripted OPKS smoke]",
    )
    await add_opks_item(
        uow_factory,
        document_id=isolation_document_id,
        entry_id="isolation-attitude",
        entity_kind=OpksEntityKind.ATTITUDE,
        text="主動釐清異常",
    )

    transport = ScriptedTransport(
        (_initial_generation(), _reuse_knowledge(), _pending_output_revision())
    )
    adapter = OpenRouterAdapter(
        config=CONFIG,
        api_key="sk-scripted-no-network",
        transport=transport,
    )
    journal_ids: list[str] = []
    scenarios: list[ScenarioMetrics] = []

    task_1_digest = await _analysis_digest(uow_factory, document_id, "task-1")
    generated = await generate_opks_proposals(
        uow_factory,
        adapter=adapter,
        document_id=document_id,
        task_id="task-1",
        expected_digest=task_1_digest,
        operation_id="opks-generate",
    )
    assert generated.proposal_ids == tuple(
        f"opks-generate-op{index}" for index in range(4)
    )
    generated_state = await load_document(uow_factory, document_id)
    assert generated_state is not None
    assert {
        proposal.entity_kind for proposal in generated_state.state.opks_proposals
    } == {
        OpksEntityKind.OUTPUT,
        OpksEntityKind.INDICATOR,
        OpksEntityKind.KNOWLEDGE,
        OpksEntityKind.SKILL,
    }
    assert all(
        proposal.entity_kind is not OpksEntityKind.ATTITUDE
        for proposal in generated_state.state.opks_proposals
    )
    journal_ids.append("opks-generate")
    scenarios.append(
        await _metrics(
            uow_factory,
            document_id=document_id,
            transport=transport,
            journal_ids=tuple(journal_ids),
            name="generate_proposals",
            note="O/P/K/S proposals created; A remains manual-only",
        )
    )

    replay = await generate_opks_proposals(
        uow_factory,
        adapter=adapter,
        document_id=document_id,
        task_id="task-1",
        expected_digest=task_1_digest,
        operation_id="opks-generate",
    )
    assert replay == generated
    assert transport.calls == 1
    scenarios.append(
        await _metrics(
            uow_factory,
            document_id=document_id,
            transport=transport,
            journal_ids=tuple(journal_ids),
            name="idempotent_replay",
            note="same receipt and proposal IDs; provider still called once",
        )
    )

    decision_specs = (
        ("opks-generate-op0", "accept-output", "accepted", None, None),
        (
            "opks-generate-op1",
            "edit-indicator",
            "edited",
            "員工修改後：依排程完成週報並核對異常",
            None,
        ),
        (
            "opks-generate-op2",
            "reject-knowledge",
            "rejected",
            None,
            "這項知識描述不準確",
        ),
        ("opks-generate-op3", "defer-skill", "deferred", None, None),
    )
    decided = []
    for proposal_id, decision_id, decision, edited_text, reason in decision_specs:
        decided.append(
            await decide_opks_proposal(
                uow_factory,
                document_id=document_id,
                proposal_id=proposal_id,
                decision_id=decision_id,
                decision=decision,
                edited_text=edited_text,
                reason=reason,
            )
        )
        journal_ids.append(decision_id)
        if decision == "edited":
            journal_ids.append(f"{decision_id}-direct-edit")
    decided_state = await load_document(uow_factory, document_id)
    assert decided_state is not None
    by_proposal_id = {
        proposal.proposal_id: proposal
        for proposal in decided_state.state.opks_proposals
    }
    assert by_proposal_id["opks-generate-op2"].rejection_reason == (
        "這項知識描述不準確"
    )
    edited_indicator = decided_state.state.current_opks.item_by_id(
        "opks-generate-p1"
    )
    assert edited_indicator is not None
    assert any(
        link.source_ref.kind is SourceKind.DIRECT_EDIT
        for link in edited_indicator.evidence_links
    )
    scenarios.append(
        await _metrics(
            uow_factory,
            document_id=document_id,
            transport=transport,
            journal_ids=tuple(journal_ids),
            name="employee_decisions",
            note="accept/edit/reject/defer survive reload with scoped payloads",
        )
    )

    attitude = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="attitude-add",
        entity_kind=OpksEntityKind.ATTITUDE,
        text="主動回報異常",
    )
    journal_ids.append("attitude-add")
    await edit_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="attitude-edit",
        entity_id=attitude.entity_id,
        entity_kind=OpksEntityKind.ATTITUDE,
        text="主動釐清並回報異常",
    )
    journal_ids.append("attitude-edit")
    await delete_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="attitude-delete",
        entity_id=attitude.entity_id,
    )
    journal_ids.append("attitude-delete")
    after_attitude = await load_document(uow_factory, document_id)
    assert after_attitude is not None
    assert all(
        item.entity_kind is not OpksEntityKind.ATTITUDE
        for item in after_attitude.state.current_opks.items
    )
    assert transport.calls == 1
    scenarios.append(
        await _metrics(
            uow_factory,
            document_id=document_id,
            transport=transport,
            journal_ids=tuple(journal_ids),
            name="manual_attitude",
            note="add/edit/delete committed with zero extra provider calls",
        )
    )

    knowledge = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="manual-knowledge",
        entity_kind=OpksEntityKind.KNOWLEDGE,
        text="排班規則與人力配置原則",
        task_refs=("task-1",),
    )
    journal_ids.append("manual-knowledge")
    reuse = await generate_opks_proposals(
        uow_factory,
        adapter=adapter,
        document_id=document_id,
        task_id="task-2",
        expected_digest=await _analysis_digest(uow_factory, document_id, "task-2"),
        operation_id="opks-reuse",
    )
    journal_ids.append("opks-reuse")
    assert reuse.proposal_ids == ("opks-reuse-op0",)
    await decide_opks_proposal(
        uow_factory,
        document_id=document_id,
        proposal_id="opks-reuse-op0",
        decision_id="accept-reuse",
        decision="accepted",
    )
    journal_ids.append("accept-reuse")
    reused_state = await load_document(uow_factory, document_id)
    assert reused_state is not None
    reused = reused_state.state.current_opks.item_by_id(knowledge.entity_id)
    assert reused is not None
    scenarios.append(
        await _metrics(
            uow_factory,
            document_id=document_id,
            transport=transport,
            journal_ids=tuple(journal_ids),
            name="reuse_knowledge",
            note="same entity, 2 Task refs; no text-similarity identity",
        )
    )

    pending = await generate_opks_proposals(
        uow_factory,
        adapter=adapter,
        document_id=document_id,
        task_id="task-1",
        expected_digest=await _analysis_digest(uow_factory, document_id, "task-1"),
        operation_id="opks-pending",
    )
    journal_ids.append("opks-pending")
    assert pending.proposal_ids == ("opks-pending-op0",)
    isolation_before = await load_document(uow_factory, isolation_document_id)
    await delete_jd_task(
        uow_factory,
        document_id=document_id,
        entry_id="delete-task-1",
        task_id="task-1",
    )
    journal_ids.append("delete-task-1")
    isolation_after = await load_document(uow_factory, isolation_document_id)
    scenarios.append(
        await _metrics(
            uow_factory,
            document_id=document_id,
            transport=transport,
            journal_ids=tuple(journal_ids),
            name="task_delete",
            note="O/P cascade, shared K ref pruned, pending proposal stale",
        )
    )

    await add_jd_task(
        uow_factory,
        document_id=document_id,
        entry_id="no-ground-task",
        fields=JdTaskFields(statement="員工只填了任務名稱"),
    )
    journal_ids.append("no-ground-task")
    before_ungrounded = await load_document(uow_factory, document_id)
    calls_before = transport.calls
    journal_before = await _known_journal_count(
        uow_factory, document_id, tuple(journal_ids)
    )
    try:
        await generate_opks_proposals(
            uow_factory,
            adapter=adapter,
            document_id=document_id,
            task_id="direct-no-ground-task",
            # 沒有員工依據是這個 Task 自己的狀態,不是漂移:grounding 在 digest 比對
            # 之前就擋下來,所以這裡的值到不了比對那一步。
            expected_digest="unreachable-grounding-fails-first",
            operation_id="opks-no-ground",
        )
    except OpksGroundingUnavailable:
        pass
    else:  # pragma: no cover - the smoke must stop before provider
        raise AssertionError("ungrounded Task unexpectedly reached the provider")
    after_ungrounded = await load_document(uow_factory, document_id)
    journal_after = await _known_journal_count(
        uow_factory, document_id, (*journal_ids, "opks-no-ground")
    )
    scenarios.append(
        await _metrics(
            uow_factory,
            document_id=document_id,
            transport=transport,
            journal_ids=tuple(journal_ids),
            name="ungrounded_stop",
            note="provider call 0; Current JD, proposals and Journal unchanged",
        )
    )

    return OpksSmokeReport(
        scenarios=tuple(scenarios),
        generation_replay_equal=generated == replay,
        decision_statuses=tuple(proposal.status for proposal in decided),
        reused_entity_id=reused.entity_id,
        reused_task_refs=reused.task_refs,
        isolation_unchanged=isolation_before == isolation_after,
        ungrounded_state_unchanged=(
            calls_before == transport.calls
            and before_ungrounded == after_ungrounded
            and journal_before == journal_after
        ),
    )


async def _run() -> OpksSmokeReport:
    from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork
    from app.database import AsyncSessionLocal

    return await run_scripted_opks_smoke(
        uow_factory=lambda: SqlAlchemyJobAnalysisUnitOfWork(AsyncSessionLocal),
        document_id=uuid4(),
        isolation_document_id=uuid4(),
    )


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    report = asyncio.run(_run())
    print(report.render())
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
