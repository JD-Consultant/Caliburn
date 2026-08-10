"""Domain/wire mapping for the OPKS transport seam."""

from job_analysis_contract import (
    OpksItemView,
    OpksItemWrite,
    OpksProposalDecisionWrite,
    OpksProposalView,
    OpksTaskStatusView,
)

from app.core.domain import OpksEntityKind, OpksItem, OpksProposal
from app.core.state import JobAnalysisState
from app.opks import opks_task_status


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def to_opks_write(
    body: OpksItemWrite,
) -> tuple[OpksEntityKind, str, tuple[str, ...], tuple[str, ...]]:
    return (
        OpksEntityKind(body.entity_kind.value),
        body.text.strip(),
        tuple(body.task_refs),
        tuple(body.indicator_refs),
    )


def to_opks_item_view(item: OpksItem) -> OpksItemView:
    quotes: list[str] = []
    for link in item.evidence_links:
        if link.quote is not None and link.quote not in quotes:
            quotes.append(link.quote)
    return OpksItemView(
        entity_id=item.entity_id,
        entity_kind=item.entity_kind.value,
        text=item.text,
        task_refs=list(item.task_refs),
        indicator_refs=list(item.indicator_refs),
        evidence_quotes=quotes,
        display_order=item.display_order,
    )


def to_opks_proposal_decision(
    body: OpksProposalDecisionWrite,
) -> tuple[str, str | None, str | None]:
    return (
        body.decision.value,
        _optional_text(body.edited_text),
        _optional_text(body.reason),
    )


def to_opks_proposal_view(proposal: OpksProposal) -> OpksProposalView:
    return OpksProposalView(
        proposal_id=proposal.proposal_id,
        operation_id=proposal.operation_id,
        entity_id=proposal.entity_id,
        entity_kind=proposal.entity_kind.value,
        action=proposal.action.value,
        status=proposal.status.value,
        before=(
            to_opks_item_view(proposal.before)
            if proposal.before is not None
            else None
        ),
        after=(
            to_opks_item_view(proposal.after)
            if proposal.after is not None
            else None
        ),
        edited_after=(
            to_opks_item_view(proposal.edited_after)
            if proposal.edited_after is not None
            else None
        ),
        rejection_reason=proposal.rejection_reason,
        stale_reason=proposal.stale_reason,
    )


def to_opks_task_status(state: JobAnalysisState) -> list[OpksTaskStatusView]:
    """ADR 0052 決定 1–3:規則是 domain 純函式,contract 只承載結果,Web 不重算。

    只列**有狀態**的 Task。判不出來就不出現在這個陣列裡——0052 決定 6
    「無法確定的一律不提示」因此是結構事實,不是呼叫端要記得的約定。
    """

    result = []
    for task in state.current_jd:
        status = opks_task_status(state, task.task_id)
        if status is not None:
            result.append(
                OpksTaskStatusView(task_id=task.task_id, status=status.value)
            )
    return result
