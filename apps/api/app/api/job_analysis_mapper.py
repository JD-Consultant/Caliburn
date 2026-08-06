"""Explicit mapping between job-analysis domain records and wire DTOs."""

from job_analysis_contract import (
    ActiveQuestionView,
    ConsultationView,
    ConversationTurnView,
    DocumentMetadataView,
    DocumentReadinessView,
    DocumentSummary as WireDocumentSummary,
    DocumentView,
    DutyView,
    JdHeaderView,
    JdHeaderWrite,
    JdTaskWrite,
    JdTaskView,
    OpksGenerationView,
    OpksItemView,
    OpksItemWrite,
    OpksProposalDecisionWrite,
    OpksProposalView,
    ProposalJdEntryView,
    ProposalDecisionWrite,
    ProposalView,
    ReadinessIssueView,
)

from app.job_analysis.application import (
    DocumentReadiness,
    DocumentRecord,
    DocumentSummary,
    LoadedDocument,
    OpksGenerationResult,
    assess_readiness,
)
from app.job_analysis.domain import (
    Duty,
    Enabler,
    EnablerKind,
    JdHeader,
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
        duty_id=_optional_text(body.duty_id),
        competency_level=body.competency_level,
    )


def to_duty_view(duty: Duty) -> DutyView:
    return DutyView(
        duty_id=duty.duty_id,
        statement=duty.statement,
        display_order=duty.display_order,
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


def to_opks_generation_view(result: OpksGenerationResult) -> OpksGenerationView:
    return OpksGenerationView(
        outcome=result.outcome.value,
        proposal_ids=list(result.proposal_ids),
    )


def to_jd_header(body: JdHeaderWrite) -> JdHeader:
    return JdHeader(
        competency_name=_optional_text(body.competency_name),
        occupation_category_name=_optional_text(body.occupation_category_name),
        occupation_name=_optional_text(body.occupation_name),
        occupation_code=_optional_text(body.occupation_code),
        industry_name=_optional_text(body.industry_name),
        industry_code=_optional_text(body.industry_code),
        work_description=_optional_text(body.work_description),
        competency_level=body.competency_level,
        notes=_optional_text(body.notes),
    )


def to_jd_header_view(header: JdHeader) -> JdHeaderView:
    return JdHeaderView(
        competency_name=header.competency_name,
        occupation_category_name=header.occupation_category_name,
        occupation_name=header.occupation_name,
        occupation_code=header.occupation_code,
        industry_name=header.industry_name,
        industry_code=header.industry_code,
        work_description=header.work_description,
        competency_level=header.competency_level,
        notes=header.notes,
    )


def to_document_readiness_view(
    readiness: DocumentReadiness,
) -> DocumentReadinessView:
    return DocumentReadinessView(
        issues=[
            ReadinessIssueView(code=issue.code.value, field=issue.field)
            for issue in readiness.issues
        ]
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
            "duty_id": task.duty_id,
            "competency_level": task.competency_level,
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


def to_document_view(loaded: LoadedDocument) -> DocumentView:
    return DocumentView(
        document_id=loaded.document.document_id,
        title=loaded.document.title,
        updated_at=loaded.document.updated_at,
        jd_header=to_jd_header_view(loaded.state.jd_header),
        readiness=to_document_readiness_view(
            assess_readiness(
                header=loaded.state.jd_header,
                duties=loaded.state.current_duties,
                tasks=loaded.state.current_jd,
            )
        ),
        duties=[to_duty_view(duty) for duty in loaded.state.current_duties],
        tasks=[to_jd_task_view(task) for task in loaded.state.current_jd],
        opks_items=[
            to_opks_item_view(item) for item in loaded.state.current_opks.items
        ],
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
        duties=[to_duty_view(duty) for duty in loaded.state.current_duties],
        tasks=[to_jd_task_view(task) for task in loaded.state.current_jd],
        opks_items=[
            to_opks_item_view(item) for item in loaded.state.current_opks.items
        ],
    )
