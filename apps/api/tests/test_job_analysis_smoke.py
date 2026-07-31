"""T7:scripted vertical smoke——員工回覆 → packet → 模型 → verifier → Work Model →
Proposal → 下一題,整條路走一遍。

provider 是 scripted 的(不打真 API、不付費),所以**這裡證明的是管線接得起來,不是
模型品質**。依 ADR 0042 決定 3,R1 exit gate 的判準未被否決,只是暫停阻擋效力:
這五個案例全綠**不代表** Task Discovery 已通過,任何文件都不得這樣寫。

每個案例最後都印出一份人看得懂的摘要(`pytest -s` 可見),並對摘要斷言——「輸出可讀」
要是沒有東西驗,它就會在第一次重構時悄悄消失。
"""

from __future__ import annotations

from app.job_analysis.application import (
    ActiveQuestion,
    ConversationTurn,
    JobAnalysisState,
    OperationOutcome,
    TransitionResult,
    TurnSpeaker,
    apply_task_analysis_result,
    build_context_packet,
    render_context_packet,
    run_task_analysis_operation,
)
from app.job_analysis.domain import (
    CurrentWorkModel,
    Enabler,
    EnablerKind,
    ExclusionReason,
    OpenIssueKind,
    RetirementReason,
    SourceKind,
    SourceRef,
    SupportLink,
    Task,
    TaskFields,
    TaskState,
    JdEntry,
    JdTask,
    Proposal,
    ProposalAction,
    SingleTaskTarget,
)
from app.job_analysis.llm import (
    IdentityRelation,
    SignalDisposition,
    TaskAnalysisWire,
    WireAnchor,
    WireEnabler,
    WireNextQuestion,
    WireRejectionCode,
    WireSignal,
    WireSupersession,
    WireTaskChange,
    WireTaskFields,
    WireWithdrawReason,
)
from app.job_analysis.providers import (
    OpenRouterAdapter,
    OpenRouterConfig,
    TransportResponse,
)


CONFIG = OpenRouterConfig(
    model="anthropic/claude-opus-5",
    provider_order=("anthropic",),
    max_output_tokens=8192,
    timeout_seconds=90.0,
)


class ScriptedProvider:
    """照劇本回一份 wire 輸出;形狀與真的 OpenRouter 回應一致。

    劇本寫的是**模型送出來的東西**(`task_analysis_result.v2`),不是 domain 形狀——
    否則這條 smoke 就會跳過 mapper,不再是端到端。
    """

    def __init__(self, result: TaskAnalysisWire) -> None:
        self._result = result
        self.calls = 0

    async def __call__(self, *, url, headers, body, timeout) -> TransportResponse:
        self.calls += 1
        return TransportResponse(
            status_code=200,
            body={
                "model": CONFIG.model,
                "choices": [
                    {
                        "message": {
                            "content": self._result.model_dump_json(),
                            "refusal": None,
                        },
                        "finish_reason": "stop",
                    }
                ]
            },
        )


async def run_round(
    *,
    transcript: tuple[ConversationTurn, ...],
    current_turn_id: str,
    scripted: TaskAnalysisWire,
    state: JobAnalysisState | None = None,
    active_question: ActiveQuestion | None = None,
    operation_id: str = "op-1",
) -> tuple[TransitionResult, str, str]:
    state = state or JobAnalysisState()
    packet = build_context_packet(
        transcript=transcript,
        current_turn_id=current_turn_id,
        work_model=state.work_model,
        current_jd=state.current_jd,
        active_question=active_question,
        proposals=state.proposals,
    )
    provider = ScriptedProvider(scripted)
    adapter = OpenRouterAdapter(config=CONFIG, api_key="sk-test", transport=provider)

    operation = await run_task_analysis_operation(packet=packet, adapter=adapter)
    assert operation.outcome is OperationOutcome.VERIFIED, operation.detail
    assert provider.calls == 1

    transition = apply_task_analysis_result(
        state=state, packet=packet, result=operation.result, operation_id=operation_id
    )
    assert transition.is_applied, transition.detail
    return transition, summarize(transition, operation.result), render_context_packet(packet)


def summarize(transition: TransitionResult, result: TaskAnalysisWire) -> str:
    """人看得懂的一輪成果:產生了什麼工作、排除了什麼、還缺什麼、下一題問什麼。"""
    work_model = transition.state.work_model
    lines: list[str] = ["## 目前成立的工作"]
    active = [task for task in work_model.tasks if task.state is TaskState.ACTIVE]
    if active:
        lines.extend(
            f"- {task.statement}"
            + (
                f"(使用:{', '.join(enabler.name for enabler in task.enablers)})"
                if task.enablers
                else ""
            )
            for task in active
        )
    else:
        lines.append("- (還沒有成立的工作)")

    retired = [task for task in work_model.tasks if task.state is TaskState.RETIRED]
    if retired:
        lines.append("## 已撤回")
        lines.extend(
            f"- {task.statement} — {task.retirement.kind.value}"
            + (f"/{task.retirement.reason.value}" if task.retirement.reason else "")
            for task in retired
        )
    if work_model.excluded_signals:
        lines.append("## 不算這位員工的工作")
        lines.extend(
            f"- {signal.summary}({signal.reason.value})"
            for signal in work_model.excluded_signals
        )
    if work_model.open_issues:
        lines.append("## 還沒問清楚")
        lines.extend(
            f"- {issue.summary}({issue.kind.value})" for issue in work_model.open_issues
        )
    if transition.created_proposal_ids:
        lines.append("## 等員工決定的提案")
        lines.extend(
            f"- {proposal.action.value}:{proposal.proposal_id}"
            for proposal in transition.state.proposals
            if proposal.proposal_id in transition.created_proposal_ids
        )
    lines.append("## 下一題")
    lines.append(f"- {result.next_question.text}")
    return "\n".join(lines)


def consultant(turn_id: str, text: str) -> ConversationTurn:
    return ConversationTurn(turn_id=turn_id, speaker=TurnSpeaker.CONSULTANT, text=text)


def employee(turn_id: str, text: str) -> ConversationTurn:
    return ConversationTurn(turn_id=turn_id, speaker=TurnSpeaker.EMPLOYEE, text=text)


#: `change` 是 `"none"` 的訊號必須送中性的 task,否則 mapper 會判定夾帶。
NEUTRAL_TASK = WireTaskFields(statement="", action="", object="", purpose_result="")


def question(text: str, intent: str) -> WireNextQuestion:
    """`intent` 只是這個場景在說明「為什麼是這一題」。

    `NextQuestion.purpose` 已移除——全 repo 沒有消費者,每回合向模型索取一次再丟掉。
    """

    del intent
    return WireNextQuestion(text=text)


# ── 1. 工具不成 Task(`TI-R1-01` 語意)──────────────────────────────────────


async def test_a_tool_alone_never_becomes_a_task():
    text = "我整天都在用 Excel,幾乎沒離開過它"
    scripted = TaskAnalysisWire(
        work_signals=(
            WireSignal(
                anchors=(WireAnchor(turn_ordinal=2, quote="我整天都在用 Excel"),),
                relation=IdentityRelation.NO_MATCH,
                disposition=SignalDisposition.EXCLUDE,
                task=NEUTRAL_TASK,
                rejection_code=WireRejectionCode.ENABLER_OR_STEP,
                rejection_summary="Excel 是工具本身,沒有說出用它完成什麼工作",
            ),
        ),
        next_question=question("你用 Excel 主要在做出什麼東西?", "把工具轉成產出"),
    )
    transition, summary, _ = await run_round(
        transcript=(consultant("turn-1", "說說你的一週?"), employee("turn-2", text)),
        current_turn_id="turn-2",
        scripted=scripted,
    )

    assert transition.state.work_model.tasks == ()
    assert transition.state.work_model.excluded_signals[0].reason is (
        ExclusionReason.ENABLER_OR_STEP
    )
    assert "Excel 是工具本身" in summary
    assert "- (還沒有成立的工作)" in summary
    assert "你用 Excel 主要在做出什麼東西?" in summary
    print("\n" + summary)


# ── 2. 含工具的工作成立(`TI-R1-02` 語意)──────────────────────────────────


async def test_work_done_with_a_tool_still_becomes_a_task():
    text = "我每週用 Excel 整理產能報表給生產主管看"
    scripted = TaskAnalysisWire(
        work_signals=(
            WireSignal(
                anchors=(
                    WireAnchor(
                        turn_ordinal=2, quote="每週用 Excel 整理產能報表給生產主管看"
                    ),
                ),
                relation=IdentityRelation.NO_MATCH,
                disposition=SignalDisposition.TASK_CHANGE,
                change=WireTaskChange.ADD,
                task=WireTaskFields(
                    statement="每週整理產能報表供生產主管掌握產線狀況",
                    action="整理",
                    object="產能報表",
                    purpose_result="讓生產主管掌握產線狀況",
                    enablers=(WireEnabler(kind=EnablerKind.TOOL_SYSTEM, name="Excel"),),
                ),
            ),
        ),
        next_question=question("這份報表如果晚交,會影響到什麼?", "找出成功判準"),
    )
    transition, summary, _ = await run_round(
        transcript=(consultant("turn-1", "說說你的一週?"), employee("turn-2", text)),
        current_turn_id="turn-2",
        scripted=scripted,
    )

    task = transition.state.work_model.tasks[0]
    assert task.action == "整理" and task.object == "產能報表"
    assert [enabler.name for enabler in task.enablers] == ["Excel"]
    assert "每週整理產能報表" in summary and "使用:Excel" in summary
    assert "(還沒有成立的工作)" not in summary
    print("\n" + summary)


# ── 3. 一段話多個工作訊號 ───────────────────────────────────────────────────


async def test_one_answer_can_carry_several_work_signals():
    text = "早上我要盤點庫存,下午跑生產排程,有時候還要幫忙接客訴電話,不過那個不一定"
    scripted = TaskAnalysisWire(
        work_signals=(
            WireSignal(
                anchors=(WireAnchor(turn_ordinal=2, quote="早上我要盤點庫存"),),
                relation=IdentityRelation.NO_MATCH,
                disposition=SignalDisposition.TASK_CHANGE,
                change=WireTaskChange.ADD,
                task=WireTaskFields(
                    statement="每日盤點庫存以維持帳料一致",
                    action="盤點",
                    object="庫存",
                ),
            ),
            WireSignal(
                anchors=(WireAnchor(turn_ordinal=2, quote="下午跑生產排程"),),
                relation=IdentityRelation.NO_MATCH,
                disposition=SignalDisposition.TASK_CHANGE,
                change=WireTaskChange.ADD,
                task=WireTaskFields(
                    statement="每日排定生產排程", action="排定", object="生產排程"
                ),
            ),
            WireSignal(
                anchors=(
                    WireAnchor(turn_ordinal=2, quote="有時候還要幫忙接客訴電話"),
                ),
                relation=IdentityRelation.UNCERTAIN,
                disposition=SignalDisposition.OPEN_ISSUE,
                task=NEUTRAL_TASK,
                rejection_code=WireRejectionCode.RESPONSIBILITY_UNCLEAR,
                rejection_summary="接客訴電話是不是這位員工的責任還不確定",
            ),
        ),
        next_question=question("接客訴電話是誰的職責?", "釐清責任邊界"),
    )
    transition, summary, _ = await run_round(
        transcript=(consultant("turn-1", "說說你的一天?"), employee("turn-2", text)),
        current_turn_id="turn-2",
        scripted=scripted,
    )

    assert [task.statement for task in transition.state.work_model.tasks] == [
        "每日盤點庫存以維持帳料一致",
        "每日排定生產排程",
    ]
    assert len(transition.state.work_model.open_issues) == 1
    assert "還沒問清楚" in summary
    print("\n" + summary)


# ── 4. 員工更正導致既有 Task 撤回(`TI-R1-08` 語意)────────────────────────


async def test_a_correction_withdraws_an_existing_task_and_supersedes_its_evidence():
    existing = Task(
        task_id="task-1",
        statement="每月結帳並核對總帳",
        action="結帳",
        object="總帳",
        support_links=(
            SupportLink(
                source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id="turn-2"),
                quote="月底結帳的時候我也會看一下",
            ),
        ),
    )
    correction = "其實結帳是會計在做,我只是去年他請產假時代班過那一次"
    scripted = TaskAnalysisWire(
        work_signals=(
            WireSignal(
                anchors=(
                    WireAnchor(
                        turn_ordinal=4, quote="結帳是會計在做,我只是去年他請產假時代班過那一次"
                    ),
                ),
                relation=IdentityRelation.DUPLICATE,
                target_task_ordinals=(1,),
                supersedes=(WireSupersession(task_ordinal=1, support_ordinal=1),),
                disposition=SignalDisposition.TASK_CHANGE,
                change=WireTaskChange.WITHDRAW,
                withdraw_reason=WireWithdrawReason.ONE_OFF,
                task=NEUTRAL_TASK,
            ),
        ),
        next_question=question("那月底那幾天你實際在忙什麼?", "補回被撤掉的時段"),
    )
    transition, summary, _ = await run_round(
        transcript=(
            consultant("turn-1", "說說你的一個月?"),
            employee("turn-2", "月底結帳的時候我也會看一下"),
            consultant("turn-3", "結帳這件事是你負責嗎?"),
            employee("turn-4", correction),
        ),
        current_turn_id="turn-4",
        scripted=scripted,
        state=JobAnalysisState(work_model=CurrentWorkModel(tasks=(existing,))),
    )

    withdrawn = transition.state.work_model.task_by_id("task-1")
    assert withdrawn.state is TaskState.RETIRED
    # 理由是模型讀出來的,不是 application 猜的:代班一次是 one_off,不是員工否認。
    assert withdrawn.retirement.reason is RetirementReason.ONE_OFF
    assert withdrawn.support_links[0].superseded_by.id == "turn-4"
    assert "已撤回" in summary and "withdrawn/one_off" in summary
    print("\n" + summary)


# ── 5. 短答必須連回 question_turn_id 才可解讀 ───────────────────────────────


async def test_a_short_answer_is_only_interpretable_through_the_active_question():
    existing = Task(
        task_id="task-1",
        statement="整理產能報表供生產主管掌握產線狀況",
        action="整理",
        object="產能報表",
        support_links=(
            SupportLink(
                source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id="turn-2"),
                quote="我會整理產能報表給主管",
            ),
        ),
    )
    asked = "這份產能報表多久整理一次?"
    scripted = TaskAnalysisWire(
        work_signals=(
            WireSignal(
                # 「每週」單獨看沒有意義:要靠 active_question 才知道它在回答頻率。
                anchors=(WireAnchor(turn_ordinal=4, quote="每週"),),
                relation=IdentityRelation.DUPLICATE,
                target_task_ordinals=(1,),
                disposition=SignalDisposition.SUPPORT_ONLY,
                task=NEUTRAL_TASK,
            ),
        ),
        next_question=question("報表整理好之後交給誰?", "釐清產出對象"),
    )
    transition, summary, rendered = await run_round(
        transcript=(
            consultant("turn-1", "說說你的一週?"),
            employee("turn-2", "我會整理產能報表給主管"),
            consultant("turn-3", asked),
            employee("turn-4", "每週"),
        ),
        current_turn_id="turn-4",
        scripted=scripted,
        active_question=ActiveQuestion(turn_id="turn-3", text=asked),
        state=JobAnalysisState(work_model=CurrentWorkModel(tasks=(existing,))),
    )

    # packet 明確告訴模型現在這一題是什麼,新依據也記下它回答的是哪一題。
    assert f"### active_question\n[3] {asked}" in rendered
    new_link = transition.state.work_model.task_by_id("task-1").support_links[-1]
    assert new_link.quote == "每週"
    assert new_link.question_turn_id == "turn-3"
    assert "整理產能報表" in summary
    print("\n" + summary)


# ── 6. 待決提案不會凍結訪談，故事結束後回到工作週期 ──────────────────────


async def test_a_pending_proposal_does_not_block_the_next_coverage_question():
    existing = Task(
        task_id="task-1",
        statement="處理客戶退貨",
        action="處理",
        object="客戶退貨",
        support_links=(
            SupportLink(
                source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id="turn-2"),
                quote="昨天我處理了一筆客戶退貨",
            ),
        ),
    )
    proposal = Proposal(
        proposal_id="proposal-1",
        target=SingleTaskTarget(action=ProposalAction.ADD, task_id="task-1"),
        jd_before=(JdEntry(task_id="task-1"),),
        jd_after=(
            JdEntry(
                task_id="task-1",
                value=JdTask(
                    task_id="task-1",
                    statement="處理客戶退貨",
                    display_order=0,
                ),
            ),
        ),
    )
    scripted = TaskAnalysisWire(
        work_signals=(),
        next_question=question(
            "除了這次退貨，還有哪些每週固定或偶爾發生、但仍由你負責的工作？",
            "故事結束後掃描尚未覆蓋的工作週期",
        ),
    )

    transition, summary, rendered = await run_round(
        transcript=(
            consultant("turn-1", "說一個最近處理客戶問題的例子。"),
            employee("turn-2", "昨天我處理了一筆客戶退貨"),
        ),
        current_turn_id="turn-2",
        scripted=scripted,
        state=JobAnalysisState(
            work_model=CurrentWorkModel(tasks=(existing,)),
            proposals=(proposal,),
        ),
    )

    assert transition.state.proposals[0].status.value == "pending"
    assert "尚未成立,不得當作現況事實" in rendered
    assert "每週固定或偶爾發生" in summary
