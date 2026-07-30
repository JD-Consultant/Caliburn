"""Pure transition service:把通過 verifier 的結果轉成 Work Model 變更與 Proposal(T6)。

規則來源:§12.2 的 mapping、§9.6 的 identity gate、§9.5 的原子性三出口、
§10 的 Proposal 建立與 stale disposition。

**state 全在記憶體**(`JobAnalysisState`),不碰 DB。交易、CAS、reload、authority
snapshot 的持久化保護留給 persistence plan。

**寫入權威**(§9.4):模型只提出候選,application 驗證後才寫入。Proposal 只 gate
Current JD——所以這個函式**永遠不動 `current_jd`**;JD 只在員工決定提案時才改。

**全有或全無**:任何一條不變量在最後 revalidate 時不成立,整筆拒絕、state 原封不動
(§9.5 的原子性)。中途用 `model_copy(update=...)` 疊改是刻意的:它不觸發驗證,所以
「最後一條有效依據被取代、又沒走三個出口之一」這種中間狀態能被建構出來、被最後那道
檢查抓到並整筆拒絕,而不是在半途炸掉、留下改了一半的 state。
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import ValidationError, model_validator

from app.job_analysis.domain import (
    CurrentWorkModel,
    DomainModel,
    ExcludedSignal,
    Identifier,
    JdEntry,
    JdTask,
    MergeTarget,
    NonEmptyText,
    OpenIssue,
    Proposal,
    ProposalAction,
    ProposalStatus,
    Retirement,
    RetirementKind,
    RetirementReason,
    SingleTaskTarget,
    SourceAnchor,
    SourceKind,
    SourceRef,
    SplitTarget,
    StagedTask,
    StagedTaskLineage,
    StagedWorkModelDelta,
    SupportLink,
    Task,
    TaskFields,
    TaskId,
    withdraw_delta_matches_target_state,
)
from app.job_analysis.llm import (
    NextQuestion,
    NextQuestionTargetKind,
    SignalDisposition,
    TaskAnalysisResult,
    TaskChangeKind,
    WorkSignal,
)

from .context import TaskAnalysisPacket
from .verifier import verify_task_analysis_result


class JobAnalysisState(DomainModel):
    """一名員工、一份職務說明書的目前狀態(§9.4 的兩層)。"""

    work_model: CurrentWorkModel = CurrentWorkModel()
    current_jd: tuple[JdTask, ...] = ()
    proposals: tuple[Proposal, ...] = ()

    @model_validator(mode="after")
    def ids_are_unique_and_jd_is_canonical(self):
        jd_ids = [entry.task_id for entry in self.current_jd]
        if len(set(jd_ids)) != len(jd_ids):
            raise ValueError("duplicate current JD task ids")
        expected = sorted(
            self.current_jd, key=lambda task: (task.display_order, task.task_id)
        )
        if list(self.current_jd) != expected:
            raise ValueError("current JD must be sorted by display order and task id")
        display_orders = [task.display_order for task in self.current_jd]
        if len(set(display_orders)) != len(display_orders):
            raise ValueError("current JD task display orders must be unique")
        proposal_ids = [proposal.proposal_id for proposal in self.proposals]
        if len(set(proposal_ids)) != len(proposal_ids):
            raise ValueError("duplicate proposal ids")
        return self

    @property
    def current_jd_task_ids(self) -> frozenset[TaskId]:
        return frozenset(task.task_id for task in self.current_jd)


class TransitionOutcome(StrEnum):
    APPLIED = "applied"
    REJECTED = "rejected"


class TransitionResult(DomainModel):
    outcome: TransitionOutcome
    state: JobAnalysisState
    immediate_task_ids: tuple[TaskId, ...] = ()
    created_proposal_ids: tuple[Identifier, ...] = ()
    staled_proposal_ids: tuple[Identifier, ...] = ()
    detail: NonEmptyText | None = None

    @property
    def is_applied(self) -> bool:
        return self.outcome is TransitionOutcome.APPLIED


def apply_task_analysis_result(
    *,
    state: JobAnalysisState,
    packet: TaskAnalysisPacket,
    result: TaskAnalysisResult,
    operation_id: str,
) -> TransitionResult:
    """套用一輪分析結果。

    `operation_id` 讓 ID 配發**決定性**:同一份結果對同一份起始 state,產生的
    Task／Proposal ID 完全相同。

    **這不等於 replay 冪等。** 真的把同一份結果對「已套用過的 state」再送一次,
    support link 會被追加第二次,open issue 會因為 ID 重複而整筆被拒。§5 要求的
    exactly-once(同一份已保存結果不得建立第二個 Task ID)需要 operation ledger,
    第一版不做,留給 persistence plan。
    """

    report = verify_task_analysis_result(result, packet.verification_context())
    if not report.is_valid:
        return _rejected(state, f"result did not pass the verifier: {report.codes[0]}")

    writer = _Writer(state=state, packet=packet, operation_id=operation_id)
    try:
        for index, signal in enumerate(result.work_signals):
            writer.apply_signal(index, signal)
        writer.record_next_question(result.next_question)
        return writer.finish()
    except (_TransitionRejected, ValidationError) as rejection:
        return _rejected(state, str(rejection))


def _rejected(state: JobAnalysisState, detail: str) -> TransitionResult:
    return TransitionResult(
        outcome=TransitionOutcome.REJECTED, state=state, detail=detail
    )


class _TransitionRejected(Exception):
    """整筆拒絕。state 不會被改動——呼叫端拿回原本那一份。"""


class _Writer:
    def __init__(
        self, *, state: JobAnalysisState, packet: TaskAnalysisPacket, operation_id: str
    ) -> None:
        self._state = state
        self._packet = packet
        self._operation_id = operation_id
        self._tasks: dict[TaskId, Task] = {
            task.task_id: task for task in state.work_model.tasks
        }
        self._open_issues = list(state.work_model.open_issues)
        self._excluded = list(state.work_model.excluded_signals)
        self._proposals = {proposal.proposal_id: proposal for proposal in state.proposals}
        self._jd = {task.task_id: task for task in state.current_jd}
        self._immediate: list[TaskId] = []
        self._created: list[Identifier] = []
        self._staled: list[Identifier] = []
        self._touched: set[TaskId] = set()
        self._materially_reanalysed: set[TaskId] = set()

    # ── 解析 ────────────────────────────────────────────────────────────────

    @property
    def _current_turn_id(self) -> str:
        return self._packet.turn_view(self._packet.current_turn_ordinal).turn.turn_id

    def _task_id(self, ordinal: int) -> TaskId:
        return self._packet.task_view(ordinal).task.task_id

    def _anchors(self, signal: WorkSignal) -> tuple[SourceAnchor, ...]:
        """模型只給 anchors;`SourceRef` 與 `question_turn_id` 由 application 解析(§12.2)。"""
        active_question = self._packet.conversation_context.active_question
        anchors: list[SourceAnchor] = []
        for anchor in signal.anchors:
            turn_id = self._packet.turn_view(anchor.turn_ordinal).turn.turn_id
            anchors.append(
                SourceAnchor(
                    source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id=turn_id),
                    quote=anchor.quote,
                    # 只有本次回合是在回答 active question;更早的回合各自回答的是
                    # 別的問題,掛上這一題會讓依據鏈指向錯的提問。
                    question_turn_id=(
                        active_question.turn_id
                        if active_question is not None and turn_id == self._current_turn_id
                        else None
                    ),
                )
            )
        return tuple(anchors)

    def _support_links(self, signal: WorkSignal) -> tuple[SupportLink, ...]:
        return tuple(
            SupportLink(**anchor.model_dump()) for anchor in self._anchors(signal)
        )

    def _retirement_source(self, signal: WorkSignal) -> SourceRef:
        """選模型實際引用的最新員工回合，不把無關 current turn 寫成來源。"""
        anchor = max(signal.anchors, key=lambda candidate: candidate.turn_ordinal)
        turn_id = self._packet.turn_view(anchor.turn_ordinal).turn.turn_id
        return SourceRef(kind=SourceKind.EMPLOYEE_TURN, id=turn_id)

    @staticmethod
    def _unique_support_links(
        *groups: tuple[SupportLink, ...],
    ) -> tuple[SupportLink, ...]:
        """保留首次出現順序的 exact dedupe；不做語意相似度猜測。"""
        unique: list[SupportLink] = []
        for group in groups:
            for link in group:
                if link not in unique:
                    unique.append(link)
        return tuple(unique)

    def _merge_support_links(
        self, members: list[TaskId], signal: WorkSignal
    ) -> tuple[SupportLink, ...]:
        return self._unique_support_links(
            *(self._tasks[member].effective_support_links for member in members),
            self._support_links(signal),
        )

    def _split_support_links(
        self, parent_id: TaskId, inherited_ordinals: tuple[int, ...], signal: WorkSignal
    ) -> tuple[SupportLink, ...]:
        parent = self._tasks[parent_id]
        inherited = tuple(
            parent.support_links[ordinal - 1] for ordinal in inherited_ordinals
        )
        return self._unique_support_links(inherited, self._support_links(signal))

    # ── 逐筆訊號 ────────────────────────────────────────────────────────────

    def apply_signal(self, index: int, signal: WorkSignal) -> None:
        self._apply_supersessions(signal)
        if signal.resolves_open_issue_ordinal is not None:
            self._resolve_reconciliation_issue(index, signal)
            return
        if signal.disposition is SignalDisposition.SUPPORT_ONLY:
            for ordinal in signal.identity.target_task_ordinals:
                self._append_support(self._task_id(ordinal), signal)
            return
        if signal.disposition is SignalDisposition.EXCLUDE:
            self._excluded.append(
                ExcludedSignal(
                    id=f"{self._operation_id}-x{index}",
                    reason=signal.exclude.reason,
                    summary=signal.exclude.summary,
                    source_anchors=self._anchors(signal),
                )
            )
            return
        if signal.disposition is SignalDisposition.OPEN_ISSUE:
            self._open_issues.append(
                OpenIssue(
                    id=f"{self._operation_id}-i{index}",
                    kind=signal.open_issue.kind,
                    summary=signal.open_issue.summary,
                    source_anchors=self._anchors(signal),
                )
            )
            return
        self._apply_task_change(index, signal)

    def _reconciliation_issue(
        self, ordinal: int
    ) -> tuple[OpenIssue, TaskId]:
        view = next(
            (
                candidate
                for candidate in self._packet.current_authorities.open_issues
                if candidate.ordinal == ordinal
            ),
            None,
        )
        if view is None or view.issue.reconciliation_task_id is None:
            raise _TransitionRejected(
                f"open issue ordinal {ordinal} is not a reconciliation issue"
            )
        local = next(
            (issue for issue in self._open_issues if issue.id == view.issue.id),
            None,
        )
        if local is None or local != view.issue:
            raise _TransitionRejected(
                f"open issue ordinal {ordinal} changed after the packet was built"
            )
        task_id = local.reconciliation_task_id
        jd_task = self._jd.get(task_id)
        if jd_task is None or jd_task != view.jd_task:
            raise _TransitionRejected(
                f"JD task for open issue ordinal {ordinal} changed or disappeared"
            )
        if task_id in self._tasks:
            raise _TransitionRejected(
                f"reconciliation task id {task_id!r} already exists in the Work Model"
            )
        return local, task_id

    def _resolve_reconciliation_issue(
        self, index: int, signal: WorkSignal
    ) -> None:
        issue, task_id = self._reconciliation_issue(
            signal.resolves_open_issue_ordinal
        )
        if signal.disposition is SignalDisposition.TASK_CHANGE:
            self._materialize_reconciliation_task(index, issue, task_id, signal)
            return
        if signal.disposition is SignalDisposition.EXCLUDE:
            self._exclude_reconciliation_task(index, issue, task_id, signal)
            return
        raise _TransitionRejected(
            "a reconciliation issue may only resolve through add or exclude"
        )

    def _materialize_reconciliation_task(
        self,
        index: int,
        issue: OpenIssue,
        task_id: TaskId,
        signal: WorkSignal,
    ) -> None:
        fields = signal.task_change.task_fields
        issue_support = tuple(
            SupportLink(**anchor.model_dump()) for anchor in issue.source_anchors
        )
        self._insert(
            Task(
                task_id=task_id,
                **dict(fields),
                support_links=self._unique_support_links(
                    issue_support,
                    self._support_links(signal),
                ),
            )
        )
        self._open_issues.remove(issue)
        self._immediate.append(task_id)
        self._materially_reanalysed.add(task_id)

        current_jd = self._jd[task_id]
        proposed_jd = self._jd_task_from_fields(
            task_id=task_id,
            fields=fields,
            existing=current_jd,
        )
        if proposed_jd != current_jd:
            self._create_proposal(
                index,
                SingleTaskTarget(action=ProposalAction.REVISE, task_id=task_id),
                jd_after={task_id: proposed_jd},
            )

    def _exclude_reconciliation_task(
        self,
        index: int,
        issue: OpenIssue,
        task_id: TaskId,
        signal: WorkSignal,
    ) -> None:
        self._excluded.append(
            ExcludedSignal(
                id=f"{self._operation_id}-x{index}",
                reason=signal.exclude.reason,
                summary=signal.exclude.summary,
                source_anchors=self._anchors(signal),
            )
        )
        if not withdraw_delta_matches_target_state(
            target_has_non_retired_task=False,
            staged_work_model_delta=None,
        ):
            raise _TransitionRejected("JD-only withdraw delta state is inconsistent")
        self._create_proposal(
            index,
            SingleTaskTarget(action=ProposalAction.WITHDRAW, task_id=task_id),
            jd_after={task_id: None},
        )

    def record_next_question(self, question: NextQuestion) -> None:
        target = question.target
        if (
            target is None
            or target.kind is not NextQuestionTargetKind.EXISTING_OPEN_ISSUE
        ):
            return
        view = next(
            (
                candidate
                for candidate in self._packet.current_authorities.open_issues
                if candidate.ordinal == target.ordinal
            ),
            None,
        )
        if view is None:
            raise _TransitionRejected(
                f"next question references unknown open issue ordinal {target.ordinal}"
            )
        for position, issue in enumerate(self._open_issues):
            if issue.id == view.issue.id:
                self._open_issues[position] = issue.model_copy(
                    update={
                        "last_asked_turn_id": f"{self._operation_id}-consultant"
                    }
                )
                return
        raise _TransitionRejected(
            "next question targets an open issue already resolved by this result"
        )

    def _apply_supersessions(self, signal: WorkSignal) -> None:
        """§12.3 末段:被取代的依據一律指向本次正在處理的 employee turn。"""
        if not signal.supersedes_support_ordinals:
            return
        superseded_by = SourceRef(
            kind=SourceKind.EMPLOYEE_TURN, id=self._current_turn_id
        )
        for reference in signal.supersedes_support_ordinals:
            task_id = self._task_id(reference.task_ordinal)
            task = self._tasks[task_id]
            links = list(task.support_links)
            position = reference.support_ordinal - 1
            links[position] = links[position].model_copy(
                update={"superseded_by": superseded_by}
            )
            self._replace(task.model_copy(update={"support_links": tuple(links)}))

    def _append_support(self, task_id: TaskId, signal: WorkSignal) -> None:
        task = self._tasks[task_id]
        self._replace(
            task.model_copy(
                update={
                    "support_links": (*task.support_links, *self._support_links(signal))
                }
            )
        )

    def _apply_task_change(self, index: int, signal: WorkSignal) -> None:
        change = signal.task_change
        targets = [
            self._task_id(ordinal) for ordinal in change.target_task_ordinals
        ]
        match change.change:
            case TaskChangeKind.ADD:
                self._add(index, signal)
            case TaskChangeKind.REVISE:
                self._revise(index, signal, targets[0])
            case TaskChangeKind.WITHDRAW:
                self._withdraw(index, signal, targets[0])
            case TaskChangeKind.MERGE:
                self._merge(index, signal, targets)
            case TaskChangeKind.SPLIT:
                self._split(index, signal, targets[0])

    # ── §9.6 identity gate ─────────────────────────────────────────────────

    def _gate_is_open(self, topology_affected: list[TaskId]) -> bool:
        """交集為空 → 純 Work Model 整理,立即套用,不打擾員工(§9.6)。"""
        return not (set(topology_affected) & self._state.current_jd_task_ids)

    def _add(self, index: int, signal: WorkSignal) -> None:
        """`add` 立即建立候選；同輪 Proposal 讓員工決定是否進 JD。"""
        task_id = f"{self._operation_id}-t{index}"
        fields = signal.task_change.task_fields
        inserted = self._insert(
            Task(
                task_id=task_id,
                **dict(fields),
                support_links=self._support_links(signal),
            )
        )
        if inserted:
            self._immediate.append(task_id)
            self._create_proposal(
                index,
                SingleTaskTarget(action=ProposalAction.ADD, task_id=task_id),
                jd_after={
                    task_id: self._jd_task_from_fields(
                        task_id=task_id,
                        fields=fields,
                        display_order=self._next_jd_order(),
                    )
                },
            )

    def _revise(self, index: int, signal: WorkSignal, task_id: TaskId) -> None:
        """同 ID revise:Work Model 立即更新(topology delta 為空);JD 文字要跟著改才提案。"""
        task = self._tasks[task_id]
        fields = signal.task_change.task_fields
        self._replace(
            task.model_copy(
                update={
                    **dict(fields),
                    "support_links": (
                        *task.support_links,
                        *self._support_links(signal),
                    ),
                }
            )
        )
        self._materially_reanalysed.add(task_id)
        self._immediate.append(task_id)
        jd_task = self._jd.get(task_id)
        revised_jd = (
            self._jd_task_from_fields(
                task_id=task_id,
                fields=fields,
                existing=jd_task,
            )
            if jd_task is not None
            else None
        )
        if jd_task is not None and jd_task != revised_jd:
            self._create_proposal(
                index,
                SingleTaskTarget(action=ProposalAction.REVISE, task_id=task_id),
                jd_after={task_id: revised_jd},
            )

    def _withdraw(self, index: int, signal: WorkSignal, task_id: TaskId) -> None:
        retirement = Retirement(
            kind=RetirementKind.WITHDRAWN,
            # 理由由模型指認(verifier 保證 withdraw 一定帶):同一個既有 Task 可能因為
            # 「其實是同事做的」「那是去年的事」「只代班過一次」而被推翻,寫死一種就是
            # 把撤回理由寫成假的。source_ref 記下是哪一個回合說的。
            reason=signal.task_change.withdraw_reason,
            source_ref=self._retirement_source(signal),
        )
        if self._gate_is_open([task_id]):
            self._replace(
                self._tasks[task_id].model_copy(update={"retirement": retirement})
            )
            self._immediate.append(task_id)
            return
        # JD 內:暫不 retire,設 pending_reconciliation 並建立提案(§9.6)。
        self._replace(
            self._tasks[task_id].model_copy(
                update={"pending_reconciliation": retirement.source_ref}
            )
        )
        self._create_proposal(
            index,
            SingleTaskTarget(action=ProposalAction.WITHDRAW, task_id=task_id),
            jd_after={task_id: None},
            delta=StagedWorkModelDelta(
                lineage_changes=(
                    StagedTaskLineage(task_id=task_id, retirement=retirement),
                )
            ),
        )

    def _merge(self, index: int, signal: WorkSignal, members: list[TaskId]) -> None:
        new_task_id = f"{self._operation_id}-m{index}"
        fields = signal.task_change.task_fields
        support_links = self._merge_support_links(members, signal)
        retirement = Retirement(
            kind=RetirementKind.MERGED,
            source_ref=self._retirement_source(signal),
        )
        if self._gate_is_open(members):
            self._insert(
                Task(
                    task_id=new_task_id,
                    **dict(fields),
                    support_links=support_links,
                )
            )
            for member in members:
                self._replace(
                    self._tasks[member].model_copy(
                        update={"retirement": retirement, "merged_into": new_task_id}
                    )
                )
            self._immediate.extend([new_task_id, *members])
            return
        self._create_proposal(
            index,
            MergeTarget(new_task_id=new_task_id, member_task_ids=tuple(members)),
            jd_after={
                new_task_id: self._jd_task_from_fields(
                    task_id=new_task_id,
                    fields=fields,
                    display_order=self._next_jd_order(),
                ),
                **{member: None for member in members},
            },
            delta=StagedWorkModelDelta(
                lineage_changes=tuple(
                    StagedTaskLineage(
                        task_id=member, retirement=retirement, merged_into=new_task_id
                    )
                    for member in members
                ),
                new_tasks=(
                    StagedTask(
                        task_id=new_task_id,
                        fields=fields,
                        support_links=support_links,
                    ),
                ),
            ),
        )

    def _split(self, index: int, signal: WorkSignal, parent_id: TaskId) -> None:
        children = signal.task_change.split_children
        child_ids = [f"{self._operation_id}-s{index}-{n}" for n in range(len(children))]
        retirement = Retirement(
            kind=RetirementKind.SPLIT,
            source_ref=self._retirement_source(signal),
        )
        if self._gate_is_open([parent_id]):
            for child_id, child in zip(child_ids, children):
                support_links = self._split_support_links(
                    parent_id, child.inherited_support_ordinals, signal
                )
                self._insert(
                    Task(
                        task_id=child_id,
                        **dict(child.task_fields),
                        support_links=support_links,
                        split_from=parent_id,
                    )
                )
            self._replace(
                self._tasks[parent_id].model_copy(update={"retirement": retirement})
            )
            self._immediate.extend([parent_id, *child_ids])
            return
        self._create_proposal(
            index,
            SplitTarget(parent_task_id=parent_id, child_task_ids=tuple(child_ids)),
            jd_after={
                parent_id: None,
                **{
                    child_id: self._jd_task_from_fields(
                        task_id=child_id,
                        fields=child.task_fields,
                        display_order=self._next_jd_order() + offset,
                    )
                    for offset, (child_id, child) in enumerate(
                        zip(child_ids, children)
                    )
                },
            },
            delta=StagedWorkModelDelta(
                lineage_changes=(
                    StagedTaskLineage(task_id=parent_id, retirement=retirement),
                    *(
                        StagedTaskLineage(task_id=child_id, split_from=parent_id)
                        for child_id in child_ids
                    ),
                ),
                new_tasks=tuple(
                    StagedTask(
                        task_id=child_id,
                        fields=child.task_fields,
                        support_links=self._split_support_links(
                            parent_id, child.inherited_support_ordinals, signal
                        ),
                    )
                    for child_id, child in zip(child_ids, children)
                ),
            ),
        )

    # ── Proposal ───────────────────────────────────────────────────────────

    def _create_proposal(
        self,
        index: int,
        target,
        *,
        jd_after: dict[TaskId, JdTask | None],
        delta: StagedWorkModelDelta | None = None,
    ) -> None:
        affected = sorted(target.affected_task_ids)
        proposal = Proposal(
            proposal_id=f"{self._operation_id}-p{index}",
            target=target,
            jd_before=tuple(
                JdEntry(task_id=task_id, value=self._jd.get(task_id))
                for task_id in affected
            ),
            jd_after=tuple(
                JdEntry(task_id=task_id, value=jd_after.get(task_id))
                for task_id in affected
            ),
            staged_work_model_delta=delta,
        )
        if not self._insert_proposal(proposal):
            return
        self._created.append(proposal.proposal_id)
        self._stale_superseded_proposals(proposal)

    def _next_jd_order(self) -> int:
        return max((task.display_order for task in self._jd.values()), default=-1) + 1

    def _jd_task_from_fields(
        self,
        *,
        task_id: TaskId,
        fields: TaskFields,
        existing: JdTask | None = None,
        display_order: int | None = None,
    ) -> JdTask:
        return JdTask(
            task_id=task_id,
            statement=fields.statement,
            purpose_result=fields.purpose_result,
            context=fields.context,
            frequency_text=(
                existing.frequency_text if existing is not None else None
            ),
            responsibility_role=(
                existing.responsibility_role if existing is not None else None
            ),
            enablers=fields.enablers,
            display_order=(
                existing.display_order
                if existing is not None
                else (
                    display_order
                    if display_order is not None
                    else self._next_jd_order()
                )
            ),
        )

    def _stale_superseded_proposals(self, replacement: Proposal) -> None:
        """§10.8:新提案與待決提案的 `affected_task_ids` 有交集 → 舊的 stale。

        理由必須是員工看得到的文字;只寫進資料庫等同無聲消失(§10.8)。
        """
        affected = set(replacement.affected_task_ids)
        for proposal_id, proposal in list(self._proposals.items()):
            if proposal_id == replacement.proposal_id:
                continue
            if proposal.status not in {ProposalStatus.PENDING, ProposalStatus.DEFERRED}:
                continue
            if not affected & set(proposal.affected_task_ids):
                continue
            self._proposals[proposal_id] = proposal.model_copy(
                update={
                    "status": ProposalStatus.STALE,
                    "stale_reason": "同一批工作已由較新的分析重新提案,這份提案不再適用。",
                }
            )
            self._staled.append(proposal_id)

    def _stale_proposals_for_unstable_tasks(self) -> None:
        """§10.8:affected Task 進入 pending_reconciliation 或 retirement → 舊提案失效。

        沒有對應的新提案時走 visible closure,不硬塞一份 replacement——那等於把已經
        被否決的內容換個形式再推一次(§10.7)。
        """
        unstable = {
            task_id
            for task_id, task in self._tasks.items()
            if task.retirement is not None or task.pending_reconciliation is not None
        }
        for proposal_id, proposal in list(self._proposals.items()):
            if proposal_id in self._created:
                continue
            if proposal.status not in {ProposalStatus.PENDING, ProposalStatus.DEFERRED}:
                continue
            if not unstable & set(proposal.affected_task_ids):
                continue
            self._proposals[proposal_id] = proposal.model_copy(
                update={
                    "status": ProposalStatus.STALE,
                    "stale_reason": "這份提案涉及的工作已被撤回或正在重新對齊,提案不再適用。",
                }
            )
            self._staled.append(proposal_id)

    def _stale_proposals_for_reanalysed_tasks(self) -> None:
        """最新分析已確認 Task 內容、但沒產生 replacement 時仍要關閉舊提案。"""
        if not self._materially_reanalysed:
            return
        for proposal_id, proposal in list(self._proposals.items()):
            if proposal_id in self._created:
                continue
            if proposal.status not in {ProposalStatus.PENDING, ProposalStatus.DEFERRED}:
                continue
            if not self._materially_reanalysed & set(proposal.affected_task_ids):
                continue
            self._proposals[proposal_id] = proposal.model_copy(
                update={
                    "status": ProposalStatus.STALE,
                    "stale_reason": "這項工作已由較新的分析確認為目前內容,舊提案不再適用。",
                }
            )
            self._staled.append(proposal_id)

    # ── 收尾 ────────────────────────────────────────────────────────────────

    def _replace(self, task: Task) -> None:
        self._tasks[task.task_id] = task
        self._touched.add(task.task_id)

    def _insert(self, task: Task) -> bool:
        existing = self._tasks.get(task.task_id)
        if existing is None:
            self._tasks[task.task_id] = task
            self._touched.add(task.task_id)
            return True
        if existing != task:
            raise _TransitionRejected(
                f"task id collision for {task.task_id!r}; existing content differs"
            )
        return False

    def _insert_proposal(self, proposal: Proposal) -> bool:
        existing = self._proposals.get(proposal.proposal_id)
        if existing is None:
            self._proposals[proposal.proposal_id] = proposal
            return True
        if existing != proposal:
            raise _TransitionRejected(
                f"proposal id collision for {proposal.proposal_id!r}; "
                "existing content differs"
            )
        return False

    def finish(self) -> TransitionResult:
        self._stale_proposals_for_unstable_tasks()
        self._stale_proposals_for_reanalysed_tasks()
        try:
            # model_copy 疊改不驗證,所以這裡逐筆 revalidate:§9.5 的「active Task 至少
            # 一條有效 SupportLink」在此執行,三個出口之一沒被走到就會整筆拒絕。
            tasks = tuple(
                Task.model_validate(task.model_dump()) for task in self._tasks.values()
            )
            work_model = CurrentWorkModel(
                tasks=tasks,
                open_issues=tuple(self._open_issues),
                excluded_signals=tuple(self._excluded),
            )
        except ValidationError as error:
            raise _TransitionRejected(
                f"write would break a work model invariant: {error.errors()[0]['msg']}"
            ) from error

        return TransitionResult(
            outcome=TransitionOutcome.APPLIED,
            state=JobAnalysisState(
                work_model=work_model,
                current_jd=self._state.current_jd,
                proposals=tuple(self._proposals.values()),
            ),
            immediate_task_ids=tuple(self._immediate),
            created_proposal_ids=tuple(self._created),
            staled_proposal_ids=tuple(self._staled),
        )
