"""Explicit mapping between job-analysis domain records and wire DTOs."""

from job_analysis_contract import (
    ActiveQuestionView,
    ConsultationView,
    ConversationTurnView,
    DocumentMetadataView,
    DocumentSummary as WireDocumentSummary,
    DocumentView,
    JdTaskWrite,
    JdTaskView,
    OpksItemView,
    OpksTaskStatusView,
    OpksItemWrite,
    OpksProposalDecisionWrite,
    OpksProposalView,
    ProposalJdEntryView,
    ProposalDecisionWrite,
    ProposalView,
)

from app.job_analysis.application import (
    DocumentRecord,
    DocumentSummary,
    JobAnalysisState,
    LoadedDocument,
    opks_task_status,
)
from app.job_analysis.domain import (
    Enabler,
    EnablerKind,
    JdTask,
    JdTaskFields,
    JdEntry,
    OpksEntityKind,
    OpksItem,
    OpksProposal,
    Proposal,
    ResponsibilityRole,
    SourceKind,
    Task,
)


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def to_jd_task_fields(body: JdTaskWrite) -> JdTaskFields:
    role_value = (
        body.responsibility_role.value
        if body.responsibility_role is not None
        else None
    )
    return JdTaskFields(
        statement=body.statement.strip(),
        purpose_result=_optional_text(body.purpose_result),
        context=_optional_text(body.context),
        frequency_text=_optional_text(body.frequency_text),
        responsibility_role=(
            ResponsibilityRole(role_value) if role_value else None
        ),
        enablers=tuple(
            Enabler(
                kind=EnablerKind(item.kind.value),
                name=item.name.strip(),
            )
            for item in body.enablers
        ),
    )


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


def to_document_metadata_view(record: DocumentRecord) -> DocumentMetadataView:
    return DocumentMetadataView(
        document_id=record.document_id,
        title=record.title,
        updated_at=record.updated_at,
    )


def to_document_summary(summary: DocumentSummary) -> WireDocumentSummary:
    return WireDocumentSummary(
        document_id=summary.document_id,
        title=summary.title,
        task_count=summary.task_count,
        updated_at=summary.updated_at,
    )


def to_jd_task_view(task: JdTask) -> JdTaskView:
    return JdTaskView.model_validate(
        {
            "task_id": task.task_id,
            "statement": task.statement,
            "purpose_result": task.purpose_result,
            "context": task.context,
            "frequency_text": task.frequency_text,
            "responsibility_role": (
                task.responsibility_role.value
                if task.responsibility_role is not None
                else None
            ),
            "enablers": [
                {"kind": enabler.kind.value, "name": enabler.name}
                for enabler in task.enablers
            ],
            "display_order": task.display_order,
        }
    )


def _to_domain_jd_task(task: JdTaskView) -> JdTask:
    return JdTask(
        task_id=task.task_id,
        statement=task.statement.strip(),
        purpose_result=_optional_text(task.purpose_result),
        context=_optional_text(task.context),
        frequency_text=_optional_text(task.frequency_text),
        responsibility_role=(
            ResponsibilityRole(task.responsibility_role.value)
            if task.responsibility_role is not None
            else None
        ),
        enablers=tuple(
            Enabler(kind=EnablerKind(item.kind.value), name=item.name.strip())
            for item in task.enablers
        ),
        display_order=task.display_order,
    )


def to_proposal_decision(
    body: ProposalDecisionWrite,
) -> tuple[str, tuple[JdEntry, ...] | None, str | None]:
    entries = (
        tuple(
            JdEntry(
                task_id=entry.task_id,
                value=(
                    _to_domain_jd_task(entry.value)
                    if entry.value is not None
                    else None
                ),
            )
            for entry in body.edited_jd_after
        )
        if body.edited_jd_after is not None
        else None
    )
    return body.decision.value, entries, _optional_text(body.reason)


def _to_opks_task_status(state: JobAnalysisState) -> list[OpksTaskStatusView]:
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


def to_document_view(loaded: LoadedDocument) -> DocumentView:
    return DocumentView(
        document_id=loaded.document.document_id,
        title=loaded.document.title,
        updated_at=loaded.document.updated_at,
        tasks=[to_jd_task_view(task) for task in loaded.state.current_jd],
        opks_items=[
            to_opks_item_view(item) for item in loaded.state.current_opks.items
        ],
        opks_task_status=_to_opks_task_status(loaded.state),
    )


def _to_proposal_entry(entry: JdEntry) -> ProposalJdEntryView:
    return ProposalJdEntryView(
        task_id=entry.task_id,
        value=to_jd_task_view(entry.value) if entry.value is not None else None,
    )


def _evidence_quotes(proposal: Proposal, tasks: tuple[Task, ...]) -> list[str]:
    affected = set(proposal.affected_task_ids)
    links = [
        link
        for task in tasks
        if task.task_id in affected
        for link in task.support_links
    ]
    if proposal.staged_work_model_delta is not None:
        links.extend(
            link
            for task in proposal.staged_work_model_delta.new_tasks
            for link in task.support_links
        )
    quotes: list[str] = []
    for link in links:
        if (
            link.is_effective
            and link.source_ref.kind is SourceKind.EMPLOYEE_TURN
            and link.quote is not None
            and link.quote not in quotes
        ):
            quotes.append(link.quote)
    return quotes


def _to_proposal_view(
    proposal: Proposal,
    *,
    tasks: tuple[Task, ...],
) -> ProposalView:
    return ProposalView(
        proposal_id=proposal.proposal_id,
        action=proposal.action.value,
        status=proposal.status.value,
        jd_before=[_to_proposal_entry(entry) for entry in proposal.jd_before],
        jd_after=[_to_proposal_entry(entry) for entry in proposal.jd_after],
        edited_jd_after=(
            [_to_proposal_entry(entry) for entry in proposal.edited_jd_after]
            if proposal.edited_jd_after is not None
            else None
        ),
        rejection_reason=proposal.rejection_reason,
        stale_reason=proposal.stale_reason,
        evidence_quotes=_evidence_quotes(proposal, tasks),
    )


def to_consultation_view(loaded: LoadedDocument) -> ConsultationView:
    work_tasks = loaded.state.work_model.tasks
    question = loaded.document.active_question
    return ConsultationView(
        document=to_document_metadata_view(loaded.document),
        conversation=[
            ConversationTurnView(
                turn_id=turn.turn_id,
                speaker=turn.speaker.value,
                text=turn.text,
            )
            for turn in loaded.conversation_turns
        ],
        active_question=(
            ActiveQuestionView(turn_id=question.turn_id, text=question.text)
            if question is not None
            else None
        ),
        proposals=[
            _to_proposal_view(proposal, tasks=work_tasks)
            for proposal in loaded.state.proposals
        ],
        opks_proposals=[
            to_opks_proposal_view(proposal)
            for proposal in loaded.state.opks_proposals
        ],
        tasks=[to_jd_task_view(task) for task in loaded.state.current_jd],
        opks_items=[
            to_opks_item_view(item) for item in loaded.state.current_opks.items
        ],
        opks_task_status=_to_opks_task_status(loaded.state),
    )
