"""Context assembler:`TaskAnalysisContext.v1` 的動態 packet(§11)。

純函式、決定性——相同輸入產生逐字相同的 packet。第一版直接送**完整 transcript 與
全部 Work Model Tasks**,不做 embedding、retrieval、compaction 或 recent-window
(§11.2;長對話出現退化才啟用 ADR 0041 決定 8)。

**ordinal 只住在這裡**(§11.2、§9.3):每輪重新編號、在 packet 中明示,mapping 存在
該輪呼叫紀錄側,不進 domain——domain 的 Task 只認 `task_id`。

**retired 接在 active 之後編號**(active `1..N`、retired `N+1..N+M`):§11.4 要求
`retired_tasks[]` 不進 active 的 namespace,而 verifier 只有在兩組整數不相交時才判斷
得出「這個 target 指的是已撤回的工作」;共用整數則永遠先命中 active,規則等於不存在。
ordinal 本來就每輪重編,不需要固定號段基準,也就沒有上限。

**packet 只用 ordinal 說話**:transcript 回合、被引用的依據、最近提問一律以 ordinal
呈現,內部的 turn_id／task_id／issue_id 不進 rendering(§11.2)。

`Static Instructions` 與 `Output Schema` 不在這裡——前者是固定 prompt(§11.2:
Task policies 不混進動態產品現況),後者是 `llm/` 已凍結的 provider schema。
"""

from __future__ import annotations

from pydantic import model_validator

from app.core.domain import (
    CurrentWorkModel,
    DomainModel,
    ExcludedSignal,
    Identifier,
    JdTask,
    NonEmptyText,
    OpenIssue,
    OpenIssueKind,
    OpenIssueTerminalResolutionKind,
    Proposal,
    ProposalStatus,
    SourceKind,
    Task,
    TaskId,
    jd_map,
)
from .verifier import (
    PacketOpenIssue,
    PacketRetiredTask,
    PacketSupportLink,
    PacketTask,
    PacketTurn,
    TurnSpeaker,
    VerificationContext,
)


# ── 輸入(conversation 尚未凍結,§9 前言把它留給後續垂直切片)──────────────


class ConversationTurn(DomainModel):
    turn_id: Identifier
    speaker: TurnSpeaker
    text: NonEmptyText


class ActiveQuestion(DomainModel):
    """產生 `support_links.question_turn_id` 的來源(§11.4);缺它短答無法解讀。"""

    turn_id: Identifier
    text: NonEmptyText


# ── packet 投影 ─────────────────────────────────────────────────────────────


class PacketTurnView(DomainModel):
    ordinal: int
    turn: ConversationTurn


class PacketTaskView(DomainModel):
    """整個 Task 帶著走,不另抄一份語意欄位;packet 只多加 ordinal 與 JD 現況。"""

    ordinal: int
    task: Task
    jd_task: JdTask | None = None

    @property
    def in_jd(self) -> bool:
        return self.jd_task is not None

    @property
    def support_ordinals(self) -> tuple[int, ...]:
        return tuple(range(1, len(self.task.support_links) + 1))


class PacketRetiredTaskView(DomainModel):
    """§11.4 的精簡形式:ordinal、statement、retirement.kind/reason。"""

    ordinal: int
    task: Task


class PacketOpenIssueView(DomainModel):
    ordinal: int
    issue: OpenIssue
    jd_task: JdTask | None = None


class PacketProposalView(DomainModel):
    """§11.2:Proposal 只引用 Task ordinal,不重複整份 Task 內容。

    `task_ordinals` 對得上號的才有;staged 的新 ID 還不是 Work Model Task,標成
    `None`(rendering 寫「新項目」)。
    """

    proposal: Proposal
    task_ordinals: tuple[int | None, ...]


class ConversationContext(DomainModel):
    transcript: tuple[PacketTurnView, ...] = ()
    active_question: ActiveQuestion | None = None


class CurrentAuthorities(DomainModel):
    tasks: tuple[PacketTaskView, ...] = ()
    retired_tasks: tuple[PacketRetiredTaskView, ...] = ()
    open_issues: tuple[PacketOpenIssueView, ...] = ()
    settled_issues: tuple[OpenIssue, ...] = ()
    """已終結、只作「已問過、勿重問」記憶的 issue(ADR 0054 決定 20)。

    **刻意沒有 ordinal。** ordinal 是模型唯一的指認手段;不配發,模型就結構性地
    無法再次「解決」一個員工已經回答不出來的缺口——不必靠 prompt 約束。
    """

    excluded_signals: tuple[ExcludedSignal, ...] = ()


class ProposalContext(DomainModel):
    pending: tuple[PacketProposalView, ...] = ()
    open_revision_requests: tuple[PacketProposalView, ...] = ()
    constraining_rejections: tuple[PacketProposalView, ...] = ()


class TaskAnalysisPacket(DomainModel):
    conversation_context: ConversationContext
    current_authorities: CurrentAuthorities
    proposal_context: ProposalContext
    current_turn_ordinal: int
    employee_written_overview: NonEmptyText | None = None

    @model_validator(mode="after")
    def transcript_turn_ids_are_unique(self):
        """ordinal↔turn_id 必須是雙射,否則 anchor 解析會指到任意一個同名回合。"""
        turn_ids = [view.turn.turn_id for view in self.conversation_context.transcript]
        if len(set(turn_ids)) != len(turn_ids):
            raise ValueError("duplicate transcript turn id")
        return self

    @model_validator(mode="after")
    def current_turn_is_an_employee_turn(self):
        view = self.turn_view(self.current_turn_ordinal)
        if view is None or view.turn.speaker is not TurnSpeaker.EMPLOYEE:
            raise ValueError("current turn must be an employee turn in the packet")
        return self

    @model_validator(mode="after")
    def active_question_is_an_earlier_consultant_turn(self):
        """`active_question` 是 `support_links.question_turn_id` 的來源(§11.4)。

        指錯回合的代價很具體:員工的短答(「對」「大概兩小時」)會被接到另一個問題上,
        整條依據鏈從此指向錯的提問。所以它必須真的是 transcript 裡**較早的顧問回合**,
        而且文字一致——文字不同表示送進 packet 的問題已經不是實際問出口的那句。
        """
        question = self.conversation_context.active_question
        if question is None:
            return self
        view = next(
            (
                candidate
                for candidate in self.conversation_context.transcript
                if candidate.turn.turn_id == question.turn_id
            ),
            None,
        )
        if view is None:
            raise ValueError("active question must reference a transcript turn")
        if view.turn.speaker is not TurnSpeaker.CONSULTANT:
            raise ValueError("active question must reference a consultant turn")
        if view.ordinal >= self.current_turn_ordinal:
            raise ValueError("active question must be earlier than the current turn")
        if view.turn.text != question.text:
            raise ValueError("active question text must match its transcript turn")
        return self

    def turn_view(self, ordinal: int) -> PacketTurnView | None:
        for view in self.conversation_context.transcript:
            if view.ordinal == ordinal:
                return view
        return None

    @property
    def turn_ordinal_by_id(self) -> dict[str, int]:
        """rendering 用的解析表;ordinal↔ID mapping 只住 application(§9.3)。"""
        return {
            view.turn.turn_id: view.ordinal
            for view in self.conversation_context.transcript
        }

    def task_view(self, ordinal: int) -> PacketTaskView | None:
        for view in self.current_authorities.tasks:
            if view.ordinal == ordinal:
                return view
        return None

    @property
    def read_set(
        self,
    ) -> tuple[CurrentAuthorities, ProposalContext, NonEmptyText | None]:
        """§11.3:read-set ＝ 本輪送出的所有可變 authority 資料(保守計入)。

        不另建 framework、也不從模型輸出反推它「真正讀了什麼」:當輪投影本身就是
        read-set,寫入前比對這批值是否已變(§10.9)。怎麼比(generation、before-value)
        留給 persistence 決定。
        """
        return (
            self.current_authorities,
            self.proposal_context,
            self.employee_written_overview,
        )

    def verification_context(self) -> VerificationContext:
        """交給 T3 verifier 的 ordinal 檢視;兩者的號段必然一致,因為都出自這裡。"""
        return VerificationContext(
            turns=tuple(
                PacketTurn(
                    ordinal=view.ordinal,
                    speaker=view.turn.speaker,
                    turn_id=view.turn.turn_id,
                    text=view.turn.text,
                )
                for view in self.conversation_context.transcript
            ),
            current_turn_ordinal=self.current_turn_ordinal,
            tasks=tuple(
                PacketTask(
                    ordinal=view.ordinal,
                    task_id=view.task.task_id,
                    support_links=tuple(
                        PacketSupportLink(ordinal=ordinal, is_effective=link.is_effective)
                        for ordinal, link in zip(
                            view.support_ordinals, view.task.support_links
                        )
                    ),
                )
                for view in self.current_authorities.tasks
            ),
            retired_tasks=tuple(
                PacketRetiredTask(ordinal=view.ordinal, task_id=view.task.task_id)
                for view in self.current_authorities.retired_tasks
            ),
            open_issues=tuple(
                PacketOpenIssue(
                    ordinal=view.ordinal,
                    issue_id=view.issue.id,
                    reconciliation_task_id=view.issue.reconciliation_task_id,
                    subject_task_id=view.issue.subject_task_id,
                )
                for view in self.current_authorities.open_issues
            ),
        )


# ── 組裝 ────────────────────────────────────────────────────────────────────


_AGENDA_RANK_BY_KIND = {
    OpenIssueKind.UNRESOLVED_CONTRADICTION: 0,
    OpenIssueKind.TASK_BOUNDARY_UNCERTAIN: 0,
    OpenIssueKind.RESPONSIBILITY_UNCLEAR: 0,
    OpenIssueKind.INSUFFICIENT_EVIDENCE: 1,
}


def _agenda_rank(issue: OpenIssue) -> int:
    """決定 21 的 agenda 位置。

    Task 邊界矛盾／責任問題最前——它們動搖的是「這件工作是什麼、是不是他的」,
    在那之前先問 OPKS 缺口等於在還沒確定的東西上追細節。OPKS gap 最後,因為它
    只在 Task 已經站穩之後才有意義(這與 pre-gate 的「無指向此 Task 的 active
    issue」是同一條規則的兩端)。
    """

    if issue.opks_axis is not None:
        return 2
    return _AGENDA_RANK_BY_KIND[issue.kind]


def build_context_packet(
    *,
    transcript: tuple[ConversationTurn, ...],
    current_turn_id: str,
    work_model: CurrentWorkModel,
    current_jd: tuple[JdTask, ...] = (),
    active_question: ActiveQuestion | None = None,
    proposals: tuple[Proposal, ...] = (),
    employee_written_overview: str | None = None,
) -> TaskAnalysisPacket:
    """把當前現況投影成一份 packet。順序完全跟隨輸入,因此同輸入同輸出。"""

    turn_views = tuple(
        PacketTurnView(ordinal=ordinal, turn=turn)
        for ordinal, turn in enumerate(transcript, start=1)
    )
    current_turn_ordinal = next(
        (view.ordinal for view in turn_views if view.turn.turn_id == current_turn_id),
        None,
    )
    if current_turn_ordinal is None:
        raise ValueError(f"current turn {current_turn_id!r} is not in the transcript")

    jd_tasks = {task.task_id: task for task in current_jd}
    active_tasks = tuple(task for task in work_model.tasks if task.retirement is None)
    retired_tasks = tuple(task for task in work_model.tasks if task.retirement is not None)

    task_views = tuple(
        PacketTaskView(
            ordinal=ordinal, task=task, jd_task=jd_tasks.get(task.task_id)
        )
        for ordinal, task in enumerate(active_tasks, start=1)
    )
    # active 1..N、retired N+1..N+M:不相交(verifier 才判斷得出 target 指到已撤回的
    # 工作),決定性,而且不需要任何固定號段基準或上限。
    retired_views = tuple(
        PacketRetiredTaskView(ordinal=ordinal, task=task)
        for ordinal, task in enumerate(retired_tasks, start=len(active_tasks) + 1)
    )
    # 決定 20–21:只有 active issue 進 open_issues 並取得 ordinal,並依 agenda 順序
    # 排列(Task 邊界矛盾／責任問題 → 一般 open issue → OPKS gap)。員工可隨時結束
    # 訪談,先問哪一類**會**影響最終覆蓋。
    active_issues = sorted(
        (issue for issue in work_model.open_issues if issue.is_active),
        key=_agenda_rank,
    )
    issue_views = tuple(
        PacketOpenIssueView(
            ordinal=ordinal,
            issue=issue,
            jd_task=(
                jd_tasks.get(issue.reconciliation_task_id)
                if issue.reconciliation_task_id is not None
                else None
            ),
        )
        for ordinal, issue in enumerate(active_issues, start=1)
    )
    settled_issues = tuple(
        issue for issue in work_model.open_issues if not issue.is_active
    )

    ordinal_by_task_id = {view.task.task_id: view.ordinal for view in task_views}
    ordinal_by_task_id.update(
        {view.task.task_id: view.ordinal for view in retired_views}
    )

    def proposal_view(proposal: Proposal) -> PacketProposalView:
        return PacketProposalView(
            proposal=proposal,
            task_ordinals=tuple(
                ordinal_by_task_id.get(task_id) for task_id in proposal.affected_task_ids
            ),
        )

    def touches_packet(proposal: Proposal) -> bool:
        return any(
            task_id in ordinal_by_task_id for task_id in proposal.affected_task_ids
        )

    pending = tuple(
        proposal_view(proposal)
        for proposal in proposals
        if proposal.status in {ProposalStatus.PENDING, ProposalStatus.DEFERRED}
    )
    open_revision_requests = tuple(
        proposal_view(proposal)
        for proposal in proposals
        if proposal.status is ProposalStatus.REVISION_REQUESTED
        and _revision_is_unresolved(proposal)
    )
    # §9.6 已知例外:被拒絕的 topology 必須持久保存,並在再次分析相關 Task 時帶入,
    # 否則員工直接刪掉 JD 條目後,同一個判斷會以「純 Work Model 整理」之姿再回來。
    constraining_rejections = tuple(
        proposal_view(proposal)
        for proposal in proposals
        if proposal.status is ProposalStatus.REJECTED and touches_packet(proposal)
    )

    return TaskAnalysisPacket(
        conversation_context=ConversationContext(
            transcript=turn_views, active_question=active_question
        ),
        current_authorities=CurrentAuthorities(
            tasks=task_views,
            retired_tasks=retired_views,
            open_issues=issue_views,
            settled_issues=settled_issues,
            excluded_signals=work_model.excluded_signals,
        ),
        proposal_context=ProposalContext(
            pending=pending,
            open_revision_requests=open_revision_requests,
            constraining_rejections=constraining_rejections,
        ),
        current_turn_ordinal=current_turn_ordinal,
        employee_written_overview=employee_written_overview,
    )


def _revision_is_unresolved(proposal: Proposal) -> bool:
    resolution = proposal.revision_resolution
    return resolution is None or (
        resolution.replacement_proposal_id is None
        and resolution.closed_without_replacement_reason is None
    )


# ── rendering(送進 Static Instructions 之後的動態區段)──────────────────────

_SPEAKER_LABEL = {TurnSpeaker.CONSULTANT: "顧問", TurnSpeaker.EMPLOYEE: "員工"}
_PENDING_BANNER = "尚未成立,不得當作現況事實"
_RETIRED_BANNER = "接在 active 之後編號;唯讀,不得出現在任何 target"
_EMPLOYEE_OVERVIEW_RULE = (
    "「員工填寫的整體描述」是背景不是做過的事；其中提到但訪談沒談過的責任，先追問怎麼做。"
)


def _render_turn_ref(turn_id: str | None, turn_ordinals: dict[str, int]) -> str | None:
    """把內部 turn_id 換成 ordinal;不在本輪 transcript 的一律不印 ID(§11.2)。"""
    if turn_id is None:
        return None
    ordinal = turn_ordinals.get(turn_id)
    return f"[{ordinal}]" if ordinal is not None else "(不在本輪 transcript)"


def _render_anchor(anchor, turn_ordinals: dict[str, int]) -> str:
    """一筆依據:來源回合 ordinal ＋ 逐字引用 ＋ 它回應的提問。

    非 employee_turn 的來源(員工直接編輯、提案決策)不在 transcript 裡,只印種類——
    ID 對模型沒有用途,而且契約裡沒有任何欄位可以讓它回填 ID。
    """
    source = anchor.source_ref
    where = (
        _render_turn_ref(source.id, turn_ordinals)
        if source.kind is SourceKind.EMPLOYEE_TURN
        else f"({source.kind.value})"
    )
    quote = f"「{anchor.quote}」" if anchor.quote else "(無引用)"
    asked = _render_turn_ref(anchor.question_turn_id, turn_ordinals)
    return f"{where} {quote}" + (f" 回應提問 {asked}" if asked else "")


def render_context_packet(packet: TaskAnalysisPacket) -> str:
    """決定性 rendering:相同 packet 逐字相同。

    區段對應 §11.1 的三個權威來源;分區是為了讓「員工已確認的事」、「AI 暫時的理解」
    與「尚未核准的提案」不混在一起,不是要模型照步驟推理。
    """

    turn_ordinals = packet.turn_ordinal_by_id
    lines: list[str] = ["# Dynamic Context Packet", "", "## conversation_context", ""]
    lines.append("### transcript")
    for view in packet.conversation_context.transcript:
        marker = " ← 本次要分析的回合" if view.ordinal == packet.current_turn_ordinal else ""
        lines.append(
            f"[{view.ordinal}] {_SPEAKER_LABEL[view.turn.speaker]}: "
            f"{view.turn.text}{marker}"
        )
    lines.append("")
    lines.append("### active_question")
    question = packet.conversation_context.active_question
    lines.append(
        f"{_render_turn_ref(question.turn_id, turn_ordinals)} {question.text}"
        if question
        else "(無)"
    )
    lines.append("")

    if packet.employee_written_overview is not None:
        lines.append("## 員工填寫的整體描述")
        lines.append("")
        lines.append(packet.employee_written_overview)
        lines.append(_EMPLOYEE_OVERVIEW_RULE)
        lines.append("")

    authorities = packet.current_authorities
    lines.append("## current_authorities")
    lines.append("")
    lines.append("### tasks")
    if not authorities.tasks:
        lines.append("(無)")
    for view in authorities.tasks:
        task = view.task
        lines.append(f"[{view.ordinal}] {task.statement}")
        lines.append(f"    action/object: {task.action} / {task.object}")
        for label, value in (
            ("purpose_result", task.purpose_result),
            ("context", task.context),
        ):
            if value is not None:
                lines.append(f"    {label}: {value}")
        if task.enablers:
            enablers = ", ".join(
                f"{enabler.kind.value}:{enabler.name}" for enabler in task.enablers
            )
            lines.append(f"    enablers: {enablers}")
        if view.jd_task is None:
            lines.append("    jd_presence: 不在 Current JD")
        else:
            lines.append(f"    jd_presence: 在 Current JD——{view.jd_task.statement}")
            for label, value in (
                ("purpose_result", view.jd_task.purpose_result),
                ("context", view.jd_task.context),
                ("frequency", view.jd_task.frequency_text),
            ):
                if value is not None:
                    lines.append(f"    jd_{label}: {value}")
            if view.jd_task.responsibility_role is not None:
                lines.append(
                    "    jd_responsibility_role: "
                    f"{view.jd_task.responsibility_role.value}"
                )
            if view.jd_task.enablers:
                jd_enablers = ", ".join(
                    f"{enabler.kind.value}:{enabler.name}"
                    for enabler in view.jd_task.enablers
                )
                lines.append(f"    jd_enablers: {jd_enablers}")
        if task.pending_reconciliation is not None:
            lines.append("    狀態: 待與 Current JD 重新對齊(pending reconciliation)")
        lines.append("    support_links:")
        for ordinal, link in zip(view.support_ordinals, task.support_links):
            state = "有效" if link.is_effective else "已被取代"
            lines.append(
                f"      ({ordinal}) [{state}] {_render_anchor(link, turn_ordinals)}"
            )
    lines.append("")

    lines.append(f"### retired_tasks({_RETIRED_BANNER})")
    if not authorities.retired_tasks:
        lines.append("(無)")
    for view in authorities.retired_tasks:
        retirement = view.task.retirement
        reason = f"/{retirement.reason.value}" if retirement.reason else ""
        lines.append(
            f"[{view.ordinal}] {view.task.statement} — {retirement.kind.value}{reason}"
        )
    lines.append("")

    lines.append("### open_issues")
    if not authorities.open_issues:
        lines.append("(無)")
    for view in authorities.open_issues:
        lines.append(f"[{view.ordinal}] {view.issue.kind.value}: {view.issue.summary}")
        if view.issue.reconciliation_task_id is not None:
            if view.jd_task is None:
                lines.append("    Current JD Task: (已不存在)")
            else:
                lines.append(f"    Current JD Task: {view.jd_task.statement}")
                missing = [
                    label
                    for label, value in (
                        ("purpose_result", view.jd_task.purpose_result),
                        ("context", view.jd_task.context),
                        ("frequency", view.jd_task.frequency_text),
                        ("responsibility_role", view.jd_task.responsibility_role),
                        ("enablers", view.jd_task.enablers or None),
                    )
                    if value is None
                ]
                lines.append(
                    "    待分析欄位: "
                    + (", ".join(missing) if missing else "(目前均有值)")
                )
            waiting_actions = sorted(
                {
                    proposal_view.proposal.action.value
                    for proposal_view in packet.proposal_context.pending
                    if view.issue.reconciliation_task_id
                    in proposal_view.proposal.affected_task_ids
                }
            )
            if waiting_actions:
                lines.append(
                    "    狀態: 等待員工決定 "
                    + "／".join(waiting_actions)
                    + " 提案"
                )
        # 缺了 anchors,模型看不出矛盾在哪兩句之間;缺了 last_asked,它會把剛問過的
        # 缺口當成沒問過再問一次——那正是 Context 要解決的跨回合記憶。
        for anchor in view.issue.source_anchors:
            lines.append(f"    依據: {_render_anchor(anchor, turn_ordinals)}")
        asked = _render_turn_ref(view.issue.last_asked_turn_id, turn_ordinals)
        lines.append(f"    最近提問: {asked}" if asked else "    最近提問: (尚未問過)")
    lines.append("")

    # 決定 20:已終結的缺口只作記憶,**不配發 ordinal**,因此不可能被再次「解決」。
    lines.append("### settled_issues(已問過，勿重問)")
    if not authorities.settled_issues:
        lines.append("(無)")
    for issue in authorities.settled_issues:
        resolution = issue.terminal_resolution
        assert resolution is not None
        answer = {
            OpenIssueTerminalResolutionKind.EMPLOYEE_UNKNOWN: "員工表示不知道",
            OpenIssueTerminalResolutionKind.NOT_APPLICABLE: "員工表示不適用",
        }[resolution.kind]
        lines.append(f"- {issue.summary} — {answer}")
    lines.append("")

    lines.append("### excluded_signals")
    if not authorities.excluded_signals:
        lines.append("(無)")
    for signal in authorities.excluded_signals:
        lines.append(f"- {signal.reason.value}: {signal.summary}")
        for anchor in signal.source_anchors:
            lines.append(f"    依據: {_render_anchor(anchor, turn_ordinals)}")
    lines.append("")

    proposals = packet.proposal_context
    lines.append("## proposal_context")
    lines.append("")
    for heading, views in (
        (f"### pending／deferred proposals({_PENDING_BANNER})", proposals.pending),
        ("### 尚未完成的 revision requests", proposals.open_revision_requests),
        ("### 會約束後續判斷的 rejection", proposals.constraining_rejections),
    ):
        lines.append(heading)
        if not views:
            lines.append("(無)")
        for view in views:
            lines.extend(_render_proposal(view))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render_proposal(view: PacketProposalView) -> list[str]:
    targets = ", ".join(
        f"[{ordinal}]" if ordinal is not None else "(新項目)"
        for ordinal in view.task_ordinals
    )
    proposal = view.proposal
    lines = [
        f"- {proposal.action.value} → {targets}({proposal.status.value})"
    ]
    for task_id, task in jd_map(proposal.jd_after).items():
        ordinal = _ordinal_for(view, task_id)
        after = task.statement if task is not None else "(自 JD 移除)"
        lines.append(f"    {ordinal} jd_after: {after}")
    if proposal.rejection_reason is not None:
        lines.append(f"    拒絕理由: {proposal.rejection_reason}")
    if proposal.excluded_member_task_ids or proposal.excluded_child_refs:
        excluded = ", ".join(
            _ordinal_for(view, task_id)
            for task_id in (
                *proposal.excluded_member_task_ids,
                *proposal.excluded_child_refs,
            )
        )
        lines.append(f"    員工要求排除: {excluded}")
    return lines


def _ordinal_for(view: PacketProposalView, task_id: TaskId) -> str:
    for affected, ordinal in zip(view.proposal.affected_task_ids, view.task_ordinals):
        if affected == task_id and ordinal is not None:
            return f"[{ordinal}]"
    return "(新項目)"
