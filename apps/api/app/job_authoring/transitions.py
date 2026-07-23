"""Pure document transitions for the Job Authoring Core (plan §6.1, §7).

Every function takes already-hydrated immutable values and returns new
immutable values or raises ``AuthoringError``. No locking, persistence,
network, or staling of other rows happens here — that orchestration lives in
the service. The application owns all identity: models never supply UUIDs, and
these helpers derive them deterministically with UUIDv5 over locked literal
names.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import UUID, uuid5

from .canonical import canonical_hash
from .commands import (
    CreateJobDocumentCommand,
    CreateTaskProposalCommand,
    EmployeeProposalDecisionCommand,
    EmployeeTaskBundleCommand,
)
from .contracts import (
    MAX_TASKS_PER_DRAFT,
    AiTaskBundleProposal,
    EvidenceBasisRef,
    EmployeeProposalDecision,
    JobDocumentDraft,
    JobDocumentRevision,
    JobFieldProvenance,
    JobOutput,
    JobTask,
    ProposalStaleReason,
    ProposedJobOutput,
    ProposedJobTask,
    TaskBundleEditValue,
)
from .errors import AuthoringError, AuthoringErrorCode

# Identity literals (plan §6.1). Locked by test; never copied inline elsewhere.
DOCUMENT_NAME = "job-authoring/document"
REVISION_NAME = "job-authoring/revision"
TASK_NAME = "job-authoring/task"
OUTPUT_NAME_TEMPLATE = "job-authoring/output/{index:04d}"


def derive_document_id(session_id: UUID) -> UUID:
    return uuid5(session_id, DOCUMENT_NAME)


def derive_revision_id(command_id: UUID) -> UUID:
    return uuid5(command_id, REVISION_NAME)


def derive_task_id(source_id: UUID) -> UUID:
    return uuid5(source_id, TASK_NAME)


def derive_output_id(source_id: UUID, index: int) -> UUID:
    return uuid5(source_id, OUTPUT_NAME_TEMPLATE.format(index=index))


# --- create initial document (plan §7.1) ------------------------------------


def create_initial_document(command: CreateJobDocumentCommand) -> JobDocumentRevision:
    document_id = derive_document_id(command.session_id)
    snapshot = JobDocumentDraft(
        document_id=document_id,
        session_id=command.session_id,
        job_title=command.job_title,
        tasks=(),
    )
    return JobDocumentRevision(
        revision_id=derive_revision_id(command.command_id),
        document_id=document_id,
        revision_number=0,
        parent_revision_id=None,
        snapshot=snapshot,
        snapshot_hash=canonical_hash(snapshot),
        source_kind="initial",
        command_id=command.command_id,
        occurred_at=command.occurred_at,
    )


# --- employee direct add (plan §7.2) ----------------------------------------


def apply_direct_add(
    head: JobDocumentRevision, command: EmployeeTaskBundleCommand
) -> JobDocumentRevision:
    _assert_head_matches(head, command)
    if len(head.snapshot.tasks) >= MAX_TASKS_PER_DRAFT:
        raise AuthoringError(AuthoringErrorCode.CAPACITY_EXCEEDED)
    task = _materialize_employee_task(
        command.command_id, command.value, entity_version=1
    )
    return _succeed_revision(
        head,
        command.command_id,
        head.snapshot.tasks + (task,),
        source_kind="employee_direct_edit",
        occurred_at=command.occurred_at,
    )


# --- employee direct replace (plan §7.3) ------------------------------------


def apply_direct_replace(
    head: JobDocumentRevision, command: EmployeeTaskBundleCommand
) -> JobDocumentRevision:
    _assert_head_matches(head, command)
    tasks = head.snapshot.tasks
    index = _find_task_index(tasks, command.target_task_id)
    target = tasks[index]
    if target.entity_version != command.expected_target_version:
        raise AuthoringError(AuthoringErrorCode.TASK_VERSION_CONFLICT)

    existing_output_ids = {output.output_id for output in target.outputs}
    for item in command.value.outputs:
        if item.output_id is not None and item.output_id not in existing_output_ids:
            raise AuthoringError(AuthoringErrorCode.OUTPUT_SCOPE_INVALID)

    provenance = JobFieldProvenance(
        source_kind="employee_document_edit",
        source_id=command.command_id,
        evidence_basis=(),
    )
    new_outputs = tuple(
        JobOutput(
            output_id=(
                item.output_id
                if item.output_id is not None
                else derive_output_id(command.command_id, index_)
            ),
            statement=item.statement,
            provenance=provenance,
        )
        for index_, item in enumerate(command.value.outputs, start=1)
    )

    if command.value.statement == target.statement and _same_output_content(
        new_outputs, target.outputs
    ):
        raise AuthoringError(AuthoringErrorCode.NO_SEMANTIC_CHANGE)

    new_task = JobTask(
        task_id=target.task_id,
        entity_version=target.entity_version + 1,
        statement=command.value.statement,
        outputs=new_outputs,
        provenance=provenance,
    )
    new_tasks = tasks[:index] + (new_task,) + tasks[index + 1 :]
    return _succeed_revision(
        head,
        command.command_id,
        new_tasks,
        source_kind="employee_direct_edit",
        occurred_at=command.occurred_at,
    )


# --- shared helpers ---------------------------------------------------------


def _find_task_index(tasks: tuple[JobTask, ...], task_id: UUID) -> int:
    for index, task in enumerate(tasks):
        if task.task_id == task_id:
            return index
    raise AuthoringError(AuthoringErrorCode.TASK_NOT_FOUND)


def _same_output_content(
    left: tuple[JobOutput, ...], right: tuple[JobOutput, ...]
) -> bool:
    return [(o.output_id, o.statement) for o in left] == [
        (o.output_id, o.statement) for o in right
    ]


# --- proposal build (plan §7.4) ---------------------------------------------


def build_proposal(
    command: CreateTaskProposalCommand, active_evidence: Mapping[UUID, str]
) -> AiTaskBundleProposal:
    draft = command.draft
    refs = list(draft.evidence_basis)
    for output in draft.outputs:
        refs.extend(output.evidence_basis)
    if not _evidence_live(refs, active_evidence):
        raise AuthoringError(AuthoringErrorCode.EVIDENCE_INVALID)

    proposed_outputs = tuple(
        ProposedJobOutput(
            output_id=derive_output_id(command.proposal_id, index),
            statement=output.statement,
            evidence_basis=output.evidence_basis,
        )
        for index, output in enumerate(draft.outputs, start=1)
    )
    proposed_task = ProposedJobTask(
        task_id=derive_task_id(command.proposal_id),
        statement=draft.statement,
        outputs=proposed_outputs,
        evidence_basis=draft.evidence_basis,
    )
    return AiTaskBundleProposal(
        proposal_id=command.proposal_id,
        session_id=command.session_id,
        document_id=command.document_id,
        base_revision_id=command.base_revision_id,
        base_revision_hash=command.base_revision_hash,
        evidence_state_version=command.evidence_state_version,
        evidence_state_hash=command.evidence_state_hash,
        operation="add_task",
        proposed_task=proposed_task,
        plain_language_reason=draft.plain_language_reason,
        limitations=draft.limitations,
        source_kind=command.source_kind,
        source_id=command.source_id,
        created_at=command.created_at,
    )


# --- accept / edit / reject (plan §7.5-§7.7) --------------------------------


def materialize_accept(
    head: JobDocumentRevision,
    proposal: AiTaskBundleProposal,
    decision_command: EmployeeProposalDecisionCommand,
    active_evidence: Mapping[UUID, str],
) -> tuple[JobDocumentRevision, EmployeeProposalDecision]:
    _assert_decision_head(head, decision_command)
    _assert_proposal_fresh(head, proposal, active_evidence)
    if len(head.snapshot.tasks) >= MAX_TASKS_PER_DRAFT:
        raise AuthoringError(AuthoringErrorCode.CAPACITY_EXCEEDED)

    task = _materialize_accepted_task(proposal)
    revision = _succeed_revision(
        head,
        decision_command.command_id,
        head.snapshot.tasks + (task,),
        source_kind="ai_proposal_accept",
        occurred_at=decision_command.occurred_at,
    )
    decision = _decide(
        decision_command,
        proposal,
        head,
        action="accept",
        final_task=task,
        result_revision_id=revision.revision_id,
    )
    return revision, decision


def materialize_edit(
    head: JobDocumentRevision,
    proposal: AiTaskBundleProposal,
    decision_command: EmployeeProposalDecisionCommand,
    active_evidence: Mapping[UUID, str],
) -> tuple[JobDocumentRevision, EmployeeProposalDecision]:
    _assert_decision_head(head, decision_command)
    _assert_proposal_fresh(head, proposal, active_evidence)
    edited = decision_command.edited_value
    if edited is None:  # command validator guarantees this; fail closed anyway
        raise AuthoringError(AuthoringErrorCode.OUTPUT_SCOPE_INVALID)

    proposed_by_id = {
        output.output_id: output for output in proposal.proposed_task.outputs
    }
    for item in edited.outputs:
        if item.output_id is not None and item.output_id not in proposed_by_id:
            raise AuthoringError(AuthoringErrorCode.OUTPUT_SCOPE_INVALID)

    task_provenance = JobFieldProvenance(
        source_kind="employee_proposal_edit",
        source_id=proposal.proposal_id,
        evidence_basis=proposal.proposed_task.evidence_basis,
    )
    new_outputs = tuple(
        JobOutput(
            output_id=(
                item.output_id
                if item.output_id is not None
                else derive_output_id(decision_command.command_id, index)
            ),
            statement=item.statement,
            provenance=JobFieldProvenance(
                source_kind="employee_proposal_edit",
                source_id=proposal.proposal_id,
                evidence_basis=(
                    proposed_by_id[item.output_id].evidence_basis
                    if item.output_id is not None
                    else ()
                ),
            ),
        )
        for index, item in enumerate(edited.outputs, start=1)
    )

    if edited.statement == proposal.proposed_task.statement and [
        (o.output_id, o.statement) for o in new_outputs
    ] == [(o.output_id, o.statement) for o in proposal.proposed_task.outputs]:
        raise AuthoringError(AuthoringErrorCode.NO_SEMANTIC_CHANGE)

    if len(head.snapshot.tasks) >= MAX_TASKS_PER_DRAFT:
        raise AuthoringError(AuthoringErrorCode.CAPACITY_EXCEEDED)

    final_task = JobTask(
        task_id=proposal.proposed_task.task_id,
        entity_version=1,
        statement=edited.statement,
        outputs=new_outputs,
        provenance=task_provenance,
    )
    revision = _succeed_revision(
        head,
        decision_command.command_id,
        head.snapshot.tasks + (final_task,),
        source_kind="employee_proposal_edit",
        occurred_at=decision_command.occurred_at,
    )
    decision = _decide(
        decision_command,
        proposal,
        head,
        action="edit",
        final_task=final_task,
        result_revision_id=revision.revision_id,
    )
    return revision, decision


def build_reject_decision(
    head: JobDocumentRevision,
    proposal: AiTaskBundleProposal,
    decision_command: EmployeeProposalDecisionCommand,
) -> EmployeeProposalDecision:
    _assert_decision_head(head, decision_command)
    return _decide(
        decision_command,
        proposal,
        head,
        action="reject",
        final_task=None,
        result_revision_id=None,
    )


# --- proposal helpers -------------------------------------------------------


def _evidence_live(
    basis: Sequence[EvidenceBasisRef], active_evidence: Mapping[UUID, str]
) -> bool:
    return all(
        active_evidence.get(ref.evidence_id) == ref.evidence_hash for ref in basis
    )


def _all_proposal_basis(proposal: AiTaskBundleProposal) -> list[EvidenceBasisRef]:
    refs = list(proposal.proposed_task.evidence_basis)
    for output in proposal.proposed_task.outputs:
        refs.extend(output.evidence_basis)
    return refs


def _assert_decision_head(
    head: JobDocumentRevision, decision_command: EmployeeProposalDecisionCommand
) -> None:
    if (
        decision_command.expected_revision_id != head.revision_id
        or decision_command.expected_revision_hash != head.snapshot_hash
    ):
        raise AuthoringError(AuthoringErrorCode.REVISION_CONFLICT)


def _assert_proposal_fresh(
    head: JobDocumentRevision,
    proposal: AiTaskBundleProposal,
    active_evidence: Mapping[UUID, str],
) -> None:
    if (
        proposal.base_revision_id != head.revision_id
        or proposal.base_revision_hash != head.snapshot_hash
    ):
        raise AuthoringError(
            AuthoringErrorCode.PROPOSAL_STALE,
            stale_reason=ProposalStaleReason.BASE_REVISION_CHANGED,
        )
    if not _evidence_live(_all_proposal_basis(proposal), active_evidence):
        raise AuthoringError(
            AuthoringErrorCode.PROPOSAL_STALE,
            stale_reason=ProposalStaleReason.EVIDENCE_BASIS_CHANGED,
        )


def _materialize_accepted_task(proposal: AiTaskBundleProposal) -> JobTask:
    task_provenance = JobFieldProvenance(
        source_kind="accepted_ai_proposal",
        source_id=proposal.proposal_id,
        evidence_basis=proposal.proposed_task.evidence_basis,
    )
    outputs = tuple(
        JobOutput(
            output_id=output.output_id,
            statement=output.statement,
            provenance=JobFieldProvenance(
                source_kind="accepted_ai_proposal",
                source_id=proposal.proposal_id,
                evidence_basis=output.evidence_basis,
            ),
        )
        for output in proposal.proposed_task.outputs
    )
    return JobTask(
        task_id=proposal.proposed_task.task_id,
        entity_version=1,
        statement=proposal.proposed_task.statement,
        outputs=outputs,
        provenance=task_provenance,
    )


def _decide(
    decision_command: EmployeeProposalDecisionCommand,
    proposal: AiTaskBundleProposal,
    head: JobDocumentRevision,
    *,
    action: str,
    final_task: JobTask | None,
    result_revision_id: UUID | None,
) -> EmployeeProposalDecision:
    return EmployeeProposalDecision(
        command_id=decision_command.command_id,
        proposal_id=proposal.proposal_id,
        action=action,
        base_revision_id=head.revision_id,
        base_revision_hash=head.snapshot_hash,
        final_task=final_task,
        result_revision_id=result_revision_id,
        decided_at=decision_command.occurred_at,
    )


def _assert_head_matches(
    head: JobDocumentRevision, command: EmployeeTaskBundleCommand
) -> None:
    if (
        command.expected_revision_id != head.revision_id
        or command.expected_revision_hash != head.snapshot_hash
    ):
        raise AuthoringError(AuthoringErrorCode.REVISION_CONFLICT)


def _materialize_employee_task(
    source_id: UUID, value: TaskBundleEditValue, *, entity_version: int
) -> JobTask:
    provenance = JobFieldProvenance(
        source_kind="employee_document_edit",
        source_id=source_id,
        evidence_basis=(),
    )
    outputs = tuple(
        JobOutput(
            output_id=derive_output_id(source_id, index),
            statement=item.statement,
            provenance=provenance,
        )
        for index, item in enumerate(value.outputs, start=1)
    )
    return JobTask(
        task_id=derive_task_id(source_id),
        entity_version=entity_version,
        statement=value.statement,
        outputs=outputs,
        provenance=provenance,
    )


def _succeed_revision(
    head: JobDocumentRevision,
    command_id: UUID,
    tasks: tuple[JobTask, ...],
    *,
    source_kind: str,
    occurred_at,
) -> JobDocumentRevision:
    snapshot = JobDocumentDraft(
        document_id=head.snapshot.document_id,
        session_id=head.snapshot.session_id,
        job_title=head.snapshot.job_title,
        tasks=tasks,
    )
    return JobDocumentRevision(
        revision_id=derive_revision_id(command_id),
        document_id=head.document_id,
        revision_number=head.revision_number + 1,
        parent_revision_id=head.revision_id,
        snapshot=snapshot,
        snapshot_hash=canonical_hash(snapshot),
        source_kind=source_kind,
        command_id=command_id,
        occurred_at=occurred_at,
    )
