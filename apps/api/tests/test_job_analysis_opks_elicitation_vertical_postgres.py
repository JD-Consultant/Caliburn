"""OPKS 漸進式蒐集的真 PostgreSQL 端到端 vertical(ADR 0054)。

走完驗收流程一次,中途重載一次:

    員工訪談 → Task 進入 Current JD → 自動排定 OPKS
    → 有依據的部分產生 Proposal、缺資料的部分形成 gap
    → 主顧問追問 → 員工回答 → 自動重新分析
    → 員工決定 OPKS → reload 後狀態一致

另外釘住三條付費邊界:同一回合只付一次、同一 digest 只付一次、
**拒絕 Proposal 不觸發重分析**(決定 14——REJECTED 強制帶 reason,若進 digest
就會形成付費 reject loop)。
"""

from __future__ import annotations

import pytest

from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork
from app.job_analysis.application import (
    create_document,
    decide_opks_proposal,
    decide_proposal,
    load_document,
    submit_employee_turn,
)
from app.job_analysis.domain import OpksEntityKind, OpksGapAxis
from app.job_analysis.llm import (
    IdentityRelation,
    IssueResolutionKind,
    OpksDecision,
    OpksResultWire,
    OpksWireItem,
    SignalDisposition,
    TaskAnalysisWire,
    WireAnchor,
    WireIssueResolution,
    WireNextQuestion,
    WireSignal,
    WireTaskChange,
    WireTaskFields,
)
from app.job_analysis.providers import ProviderText


pytestmark = pytest.mark.asyncio

OPKS_SCHEMA = "opks_result_v1"
FIRST_ANSWER = "我每週彙整營運週報"
SECOND_ANSWER = "週報會交給店長跟區經理，讓他們決定補貨"
THIRD_ANSWER = "我要先把 POS 匯出的資料對過帳才會做，對不起來就得回頭查單據"


def turn_add() -> ProviderText:
    """第一輪:顧問找到一件工作,建立候選與待決提案。"""

    wire = TaskAnalysisWire(
        work_signals=(
            WireSignal(
                anchors=(WireAnchor(turn_ordinal=2, quote=FIRST_ANSWER),),
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
        next_question=WireNextQuestion(text="這份週報主要交給誰？"),
    )
    return ProviderText(text=wire.model_dump_json())


def turn_support(
    quote: str,
    turn_ordinal: int,
    *,
    resolves_gap: bool = False,
) -> ProviderText:
    """後續回合:只補依據(必要時同時關掉一個缺口)。

    `answered` 的機械前提就是這一筆 `support_only`——沒有它,digest 不變、OPKS 不會
    再分析,缺口會被假關閉(決定 23)。
    """

    wire = TaskAnalysisWire(
        work_signals=(
            WireSignal(
                anchors=(WireAnchor(turn_ordinal=turn_ordinal, quote=quote),),
                relation=IdentityRelation.DUPLICATE,
                target_task_ordinals=(1,),
                disposition=SignalDisposition.SUPPORT_ONLY,
                task=WireTaskFields(statement="", action="", object=""),
            ),
        ),
        issue_resolutions=(
            (
                WireIssueResolution(
                    open_issue_ordinal=1,
                    resolution=IssueResolutionKind.ANSWERED,
                ),
            )
            if resolves_gap
            else ()
        ),
        next_question=WireNextQuestion(text="還有其他每週固定要做的事嗎？"),
    )
    return ProviderText(text=wire.model_dump_json())


def opks_output_and_gap() -> ProviderText:
    """第一次分析:產出有依據,技能還看不出來。決定 18 的 item-level 部分發布。"""

    wire = OpksResultWire(
        items=(
            OpksWireItem(
                entity_kind=OpksEntityKind.OUTPUT,
                decision=OpksDecision.ADD_NEW,
                target_ordinal=0,
                text="每週營運週報",
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


def turn_without_signals() -> ProviderText:
    """沒有任何工作訊號的一輪:員工講了與 Task 無關的話。

    測「拒絕不觸發重分析」必須用這種回合——只要補了一筆依據,digest 本來就該改變,
    那時的重分析是**正確行為**,會把要驗的東西蓋掉。
    """

    wire = TaskAnalysisWire(
        work_signals=(),
        next_question=WireNextQuestion(text="還有其他每週固定要做的事嗎？"),
    )
    return ProviderText(text=wire.model_dump_json())


def opks_skill() -> ProviderText:
    """員工回答之後的再分析:技能這次有依據了。"""

    wire = OpksResultWire(
        items=(
            OpksWireItem(
                entity_kind=OpksEntityKind.SKILL,
                decision=OpksDecision.ADD_NEW,
                target_ordinal=0,
                text="核對 POS 匯出資料與單據並排查差異",
            ),
        )
    )
    return ProviderText(text=wire.model_dump_json())


class ScriptedAdapter:
    """依 schema 分流的排隊 adapter;用完就 raise,漏掉的呼叫不會靜默通過。"""

    def __init__(self, *, turns: list[ProviderText], opks: list[ProviderText]):
        self.turns = list(turns)
        self.opks = list(opks)
        self.turn_calls = 0
        self.opks_calls = 0

    @property
    def calls(self) -> int:
        return self.turn_calls + self.opks_calls

    async def complete(self, **kwargs):
        if kwargs["schema_name"] == OPKS_SCHEMA:
            self.opks_calls += 1
            assert self.opks, "OPKS specialist 被呼叫的次數超過劇本"
            return self.opks.pop(0)
        self.turn_calls += 1
        assert self.turns, "主顧問被呼叫的次數超過劇本"
        return self.turns.pop(0)


async def test_the_full_progressive_elicitation_loop_is_durable_and_paid_once(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = lambda: SqlAlchemyJobAnalysisUnitOfWork(  # noqa: E731
        postgres_session_factory
    )
    adapter = ScriptedAdapter(
        turns=[
            # transcript 每輪多兩句(員工＋顧問),所以當輪員工回合的 ordinal 是 2、4、6、8。
            turn_add(),
            turn_support(SECOND_ANSWER, 4),
            turn_support(THIRD_ANSWER, 6, resolves_gap=True),
            turn_without_signals(),
        ],
        opks=[opks_output_and_gap(), opks_skill()],
    )
    await create_document(uow_factory, document_id=document_id, title="門市營運專員")

    # ── 1. 訪談找到一件工作;它還不在 Current JD,所以還不會排定分析 ──────────
    await submit_employee_turn(
        uow_factory,
        adapter=adapter,
        document_id=document_id,
        operation_id="turn-1",
        text=FIRST_ANSWER,
    )
    after_first = await load_document(uow_factory, document_id)
    assert after_first is not None
    assert (adapter.turn_calls, adapter.opks_calls) == (1, 0)
    task_proposal = after_first.state.proposals[0]

    # ── 2. 員工接受 → 工作進入 Current JD ────────────────────────────────────
    await decide_proposal(
        uow_factory,
        document_id=document_id,
        proposal_id=task_proposal.proposal_id,
        decision_id="accept-task",
        decision="accepted",
    )
    accepted = await load_document(uow_factory, document_id)
    assert accepted is not None
    task_id = accepted.state.current_jd[0].task_id

    # ── 3. 下一輪對話自動排定 OPKS:有依據的出提案、缺的留缺口 ────────────────
    await submit_employee_turn(
        uow_factory,
        adapter=adapter,
        document_id=document_id,
        operation_id="turn-2",
        text=SECOND_ANSWER,
    )
    analysed = await load_document(uow_factory, document_id)

    assert (adapter.turn_calls, adapter.opks_calls) == (2, 1)
    assert analysed is not None
    assert [proposal.after.text for proposal in analysed.state.opks_proposals] == [
        "每週營運週報"
    ]
    gaps = [
        issue
        for issue in analysed.state.work_model.open_issues
        if issue.opks_axis is not None
    ]
    assert len(gaps) == 1
    assert gaps[0].opks_axis is OpksGapAxis.SKILL
    assert gaps[0].subject_task_id == task_id
    assert gaps[0].is_active

    # 付費邊界一:同一回合重播不重打任何一次。
    await submit_employee_turn(
        uow_factory,
        adapter=adapter,
        document_id=document_id,
        operation_id="turn-2",
        text=SECOND_ANSWER,
    )
    assert (adapter.turn_calls, adapter.opks_calls) == (2, 1)

    # ── 4. 中途重載:狀態全部來自 PostgreSQL ─────────────────────────────────
    reloaded = await load_document(uow_factory, document_id)
    assert reloaded is not None
    assert reloaded.state.work_model.open_issues == analysed.state.work_model.open_issues
    assert reloaded.state.opks_proposals == analysed.state.opks_proposals

    # ── 5. 員工接受工作產出提案 ─────────────────────────────────────────────
    await decide_opks_proposal(
        uow_factory,
        document_id=document_id,
        proposal_id=analysed.state.opks_proposals[0].proposal_id,
        decision_id="accept-output",
        decision="accepted",
    )
    with_output = await load_document(uow_factory, document_id)
    assert with_output is not None
    assert [item.text for item in with_output.state.current_opks.items] == [
        "每週營運週報"
    ]

    # 付費邊界二:接受提案不改 digest,所以不會因此重跑一次分析(決定 13)。
    assert (adapter.turn_calls, adapter.opks_calls) == (2, 1)

    # ── 6. 員工回答缺口 → 缺口關閉、新證據使 digest 改變 → 自動重新分析 ───────
    await submit_employee_turn(
        uow_factory,
        adapter=adapter,
        document_id=document_id,
        operation_id="turn-3",
        text=THIRD_ANSWER,
    )
    answered = await load_document(uow_factory, document_id)

    assert (adapter.turn_calls, adapter.opks_calls) == (3, 2)
    assert answered is not None
    assert [
        issue for issue in answered.state.work_model.open_issues
        if issue.opks_axis is not None
    ] == []
    skill_proposals = [
        proposal
        for proposal in answered.state.opks_proposals
        if proposal.entity_kind is OpksEntityKind.SKILL
    ]
    assert [proposal.after.text for proposal in skill_proposals] == [
        "核對 POS 匯出資料與單據並排查差異"
    ]

    # ── 7. 員工拒絕技能提案 ─────────────────────────────────────────────────
    await decide_opks_proposal(
        uow_factory,
        document_id=document_id,
        proposal_id=skill_proposals[0].proposal_id,
        decision_id="reject-skill",
        decision="rejected",
        reason="那是資訊室在做的，我只負責看結果",
    )

    # 付費邊界三:拒絕**不**觸發重分析(決定 14)。REJECTED 強制帶 reason,
    # 若把 reason 放進 digest,每次拒絕都會產生新 digest ＝ 付費 reject loop。
    await submit_employee_turn(
        uow_factory,
        adapter=adapter,
        document_id=document_id,
        operation_id="turn-4",
        text="其他就是一些臨時交辦的事",
    )
    final = await load_document(uow_factory, document_id)

    assert adapter.opks_calls == 2, "相同 analysis input 不得再付一次"
    assert adapter.turn_calls == 4
    assert final is not None
    assert [item.text for item in final.state.current_opks.items] == ["每週營運週報"]
    assert final.state.work_model.open_issues == ()
