"""Provider-outside-transaction 的 durable OPKS Proposal generation。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.core.domain import (
    CurrentJdOpks,
    OpenIssue,
    OpenIssueKind,
    OpksProposal,
    SourceAnchor,
    Task,
    TaskState,
)
from app.job_analysis.providers import OpenRouterAdapter

from app.core.authority import commit_authority_change
from app.core.journal import (
    OPKS_GENERATION_SCHEMA_ID,
    JournalEntry,
    OpksGenerationOutcome,
    OpksGenerationPayload,
)
from app.core.model_outcome import OperationOutcome
from app.core.persistence import (
    DocumentRecord,
    JobAnalysisUnitOfWork,
    JobAnalysisUnitOfWorkFactory,
)
from app.core.state import JobAnalysisState

from .durable_turn import StaleAuthoritySnapshot
from .errors import DocumentNotFound, IdempotencyConflict, JdTaskNotFound
from .opks_context import (
    OpksContextPacket,
    OpksGroundingUnavailable,
    build_opks_context_packet,
)
from .opks_digest import compute_analysis_input_digest
from .opks_operation import OpksOperationResult, run_opks_operation
from .opks_verifier import OpksGap


@dataclass(frozen=True)
class OpksGenerationSnapshot:
    document_id: UUID
    authority_generation: int
    selected_task_id: str
    analysis_input_digest: str
    state: JobAnalysisState
    packet: OpksContextPacket


class OpksGenerationResult(OpksGenerationPayload):
    """回 API 的 typed result；沿用 receipt 的可重播內容。"""


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def _load_state(
    uow: JobAnalysisUnitOfWork,
    record: DocumentRecord,
) -> JobAnalysisState:
    return JobAnalysisState(
        jd_header=record.jd_header,
        current_duties=await uow.duties.list(record.document_id),
        work_model=record.work_model,
        current_jd=await uow.tasks.list(record.document_id),
        proposals=await uow.proposals.list(record.document_id),
        current_opks=CurrentJdOpks(
            items=await uow.opks.list(record.document_id)
        ),
        opks_proposals=await uow.opks_proposals.list(record.document_id),
    )


def _selected_task(state: JobAnalysisState, task_id: str) -> Task:
    if task_id not in state.current_jd_task_ids:
        raise JdTaskNotFound(f"Current JD task {task_id!r} was not found")
    task = state.work_model.task_by_id(task_id)
    if task is None:
        raise OpksGroundingUnavailable(
            "selected Current JD task has not been reconciled into the Work Model"
        )
    if task.state is not TaskState.ACTIVE:
        raise OpksGroundingUnavailable(
            "selected task is not stable enough for OPKS generation"
        )
    return task


def _packet_for(state: JobAnalysisState, task_id: str) -> OpksContextPacket:
    return build_opks_context_packet(
        selected_task=_selected_task(state, task_id),
        current_opks=state.current_opks,
        proposals=state.opks_proposals,
        open_issues=state.work_model.open_issues,
    )


def _result(payload: OpksGenerationPayload) -> OpksGenerationResult:
    return OpksGenerationResult.model_validate(payload.model_dump())


def _require_generation_replay(
    entry: JournalEntry,
    *,
    operation_id: str,
    task_id: str,
) -> OpksGenerationResult:
    if entry.kind != "opks_generation" or not isinstance(
        entry.payload, OpksGenerationPayload
    ):
        raise IdempotencyConflict(
            f"entry {operation_id!r} already belongs to another operation"
        )
    if (
        entry.payload.operation_id != operation_id
        or entry.payload.selected_task_id != task_id
    ):
        raise IdempotencyConflict(
            f"operation {operation_id!r} was replayed for another Task"
        )
    return _result(entry.payload)


async def _committed_replay(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
    operation_id: str,
    task_id: str,
) -> OpksGenerationResult | None:
    async with uow_factory() as uow:
        existing = await uow.journal.get(document_id, operation_id)
        if existing is None:
            return None
        return _require_generation_replay(
            existing,
            operation_id=operation_id,
            task_id=task_id,
        )


async def prepare_opks_generation(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
    task_id: str,
    expected_digest: str,
) -> OpksGenerationSnapshot:
    """讀一份不可變 snapshot,並確認它就是被排定的那份輸入。

    `expected_digest` 是主回合凍結進 receipt 的那一個(決定 7–8)。**不比對就會付兩次
    錢**:主回合 commit 之後、這裡開始之前員工仍可能直接編輯該 Task,child 於是用新
    輸入分析、卻把 receipt 寫在舊 digest 推導出來的 operation ID 上;下一輪 scheduler
    算出新 digest、`journal.get()` 找不到,同一份輸入再分析一次。

    對不上就 **abandon**(決定 10):raise `StaleAuthoritySnapshot`、不寫任何 receipt,
    由更新的那一輪排定自己的 child。這一步刻意在 provider 呼叫之前——漂移這時已經看得
    出來,沒有理由先付錢再丟掉。
    """

    async with uow_factory() as uow:
        record = await uow.documents.get(document_id)
        if record is None:
            raise DocumentNotFound(f"document {document_id} was not found")
        state = await _load_state(uow, record)
        # grounding 檢查排在 digest 比對之前:「這個 Task 沒有員工依據」是它自己的
        # 狀態,不是漂移,兩者的呼叫端處置不同,不能被後者蓋掉。
        packet = _packet_for(state, task_id)
        # 用 packet 投影出的那一份 Task 算,digest 與 specialist 真正看到的輸入同源。
        digest = compute_analysis_input_digest(packet.selected_task.task)
        if digest != expected_digest:
            raise StaleAuthoritySnapshot(
                f"task {task_id!r} changed after this OPKS child was scheduled"
            )
        return OpksGenerationSnapshot(
            document_id=document_id,
            authority_generation=record.authority_generation,
            selected_task_id=task_id,
            analysis_input_digest=digest,
            state=state,
            packet=packet,
        )


def _gap_issues(
    gaps: tuple[OpksGap, ...],
    *,
    packet: OpksContextPacket,
    selected_task_id: str,
    operation_id: str,
) -> tuple[OpenIssue, ...]:
    """把 specialist 的缺口落成可持久、可追問、可終結的 `OpenIssue`(決定 19)。

    ID 決定性(`{operation_id}-gap{source_index}`),沿用本 repo 既有的
    「ID 由 operation_id ＋ 位置決定」慣例,**不用 `uuid4()`**:同一個 operation
    重跑必須產生同一批 ID,否則 replay 會留下兩份缺口。

    anchors 用該 Task 目前投影給 specialist 的員工依據——`OpenIssue` 要求至少一筆,
    而缺口正是「就這些依據還看不出這一軸」的意思。
    """

    if not gaps:
        return ()
    anchors = tuple(
        SourceAnchor(
            source_ref=view.support_link.source_ref,
            quote=view.support_link.quote,
            question_turn_id=view.support_link.question_turn_id,
        )
        for view in packet.evidence
    )
    return tuple(
        OpenIssue(
            id=f"{operation_id}-gap{gap.source_index}",
            kind=OpenIssueKind.INSUFFICIENT_EVIDENCE,
            summary=gap.summary,
            source_anchors=anchors,
            subject_task_id=selected_task_id,
            opks_axis=gap.axis,
        )
        for gap in gaps
    )


def _is_terminal_failure(operation_result: OpksOperationResult) -> bool:
    """provider error／invalid output／refused／verifier rejected 都是終端失敗。

    第一版**不做 backoff、attempt counter、circuit breaker**(決定 29)。失敗寫一筆
    `failed` receipt,作用是解除 head-of-line blocking——否則同一個 Task 每輪都會被
    重新排定、每輪都再燒一次錢。

    誠實代價已載明於 ADR 後果段:偶發 provider 抖動會**永久**壓住那個確切 digest,
    直到出現新 Evidence 使 digest 改變。只在「該 Task 之後再也沒被提到」時才真的損失。
    """

    return (
        operation_result.outcome is not OperationOutcome.VERIFIED
        or operation_result.report is None
        or not operation_result.report.is_valid
    )


async def _commit_failed_receipt(
    uow: JobAnalysisUnitOfWork,
    *,
    record: DocumentRecord,
    state: JobAnalysisState,
    snapshot: OpksGenerationSnapshot,
    operation_id: str,
    now: datetime,
) -> OpksGenerationResult:
    """寫一筆 `failed` 終端 receipt,不改 Current JD 的任何內容。

    四種 outcome **在阻擋效果上等價**(決定 29):差別只在呈現與診斷。
    """

    payload = OpksGenerationPayload(
        operation_id=operation_id,
        selected_task_id=snapshot.selected_task_id,
        analysis_input_digest=snapshot.analysis_input_digest,
        outcome=OpksGenerationOutcome.FAILED,
    )
    await commit_authority_change(
        uow,
        record=record,
        state=state,
        updated_at=now,
        journal_entries=(
            JournalEntry(
                document_id=snapshot.document_id,
                entry_id=operation_id,
                kind="opks_generation",
                payload_schema_id=OPKS_GENERATION_SCHEMA_ID,
                payload=payload,
                created_at=now,
            ),
        ),
    )
    return _result(payload)


async def commit_opks_generation(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    snapshot: OpksGenerationSnapshot,
    operation_id: str,
    operation_result: OpksOperationResult,
) -> OpksGenerationResult:
    async with uow_factory() as uow:
        record = await uow.documents.get(snapshot.document_id, for_update=True)
        if record is None:
            raise DocumentNotFound(f"document {snapshot.document_id} was not found")
        state = await _load_state(uow, record)

        existing = await uow.journal.get(snapshot.document_id, operation_id)
        if existing is not None:
            return _require_generation_replay(
                existing,
                operation_id=operation_id,
                task_id=snapshot.selected_task_id,
            )

        try:
            current_packet = _packet_for(state, snapshot.selected_task_id)
        except (JdTaskNotFound, OpksGroundingUnavailable) as error:
            raise StaleAuthoritySnapshot(
                "selected Task changed while OPKS generation was running"
            ) from error
        if (
            record.authority_generation != snapshot.authority_generation
            or current_packet.read_set != snapshot.packet.read_set
        ):
            # abandon(決定 10):**不寫任何 receipt,因此不阻擋**。漂移代表已有更新的
            # 回合,由該回合排定自己的 child。用一次偶發競態永久壓住一個 digest 是錯的。
            # 這一段刻意排在失敗處理之前:輸入已經不是當初那一份,為它留下終端 receipt
            # 只會封鎖一個沒有人會再要求的 digest。
            raise StaleAuthoritySnapshot(
                "the document changed after OPKS generation was prepared"
            )

        now = _utcnow()
        if _is_terminal_failure(operation_result):
            return await _commit_failed_receipt(
                uow,
                record=record,
                state=state,
                snapshot=snapshot,
                operation_id=operation_id,
                now=now,
            )
        assert operation_result.report is not None
        additions = tuple(
            OpksProposal(
                proposal_id=f"{operation_id}-op{change.source_index}",
                operation_id=operation_id,
                entity_id=change.entity_id,
                entity_kind=change.entity_kind,
                action=change.action,
                before=change.before,
                after=change.after,
                base_authority_generation=record.authority_generation,
                created_at=now,
            )
            for change in operation_result.report.changes
        )
        proposal_ids = tuple(proposal.proposal_id for proposal in additions)
        gap_issues = _gap_issues(
            operation_result.report.gaps,
            packet=current_packet,
            selected_task_id=snapshot.selected_task_id,
            operation_id=operation_id,
        )
        gap_issue_ids = tuple(issue.id for issue in gap_issues)
        # 決定 28:有 gap 即 needs_clarification,`proposal_ids` 仍可非空。
        if gap_issue_ids:
            outcome = OpksGenerationOutcome.NEEDS_CLARIFICATION
        elif proposal_ids:
            outcome = OpksGenerationOutcome.PROPOSED
        else:
            outcome = OpksGenerationOutcome.NO_CHANGE
        payload = OpksGenerationPayload(
            operation_id=operation_id,
            selected_task_id=snapshot.selected_task_id,
            analysis_input_digest=snapshot.analysis_input_digest,
            outcome=outcome,
            proposal_ids=proposal_ids,
            gap_issue_ids=gap_issue_ids,
        )
        # 決定 30:Proposal、OpenIssue 與 receipt 在同一個 commit_authority_change()
        # 交易寫入。open_issues 住 work_model,順著同一份 state 更新即可。
        next_state = state.model_copy(
            update={
                "work_model": state.work_model.model_copy(
                    update={
                        "open_issues": (
                            *state.work_model.open_issues,
                            *gap_issues,
                        )
                    }
                ),
                "opks_proposals": (*state.opks_proposals, *additions),
            }
        )
        await commit_authority_change(
            uow,
            record=record,
            state=next_state,
            updated_at=now,
            journal_entries=(
                JournalEntry(
                    document_id=snapshot.document_id,
                    entry_id=operation_id,
                    kind="opks_generation",
                    payload_schema_id=OPKS_GENERATION_SCHEMA_ID,
                    payload=payload,
                    created_at=now,
                ),
            ),
        )
        return _result(payload)


async def generate_opks_proposals(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    adapter: OpenRouterAdapter,
    document_id: UUID,
    task_id: str,
    operation_id: str,
    expected_digest: str,
) -> OpksGenerationResult:
    """`expected_digest` 是必填的:少了它,漏比對就是靜默的雙重付費。

    `operation_id` 由 `(task_id, expected_digest)` 推導(決定 7),所以這三個值必須是
    同一筆 `ScheduledOpks` 來的;呼叫端拿不到凍結的 digest 就不該啟動 child。
    """

    replay = await _committed_replay(
        uow_factory,
        document_id=document_id,
        operation_id=operation_id,
        task_id=task_id,
    )
    if replay is not None:
        return replay
    snapshot = await prepare_opks_generation(
        uow_factory,
        document_id=document_id,
        task_id=task_id,
        expected_digest=expected_digest,
    )
    operation_result = await run_opks_operation(
        packet=snapshot.packet,
        adapter=adapter,
        operation_id=operation_id,
    )
    return await commit_opks_generation(
        uow_factory,
        snapshot=snapshot,
        operation_id=operation_id,
        operation_result=operation_result,
    )
