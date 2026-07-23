"""No-network tests for pure Job Authoring transitions (plan §6.1, §7)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4, uuid5

import pytest

from app.job_authoring import transitions
from app.job_authoring.canonical import canonical_hash
from app.job_authoring.commands import (
    CreateJobDocumentCommand,
    EmployeeTaskBundleCommand,
)
from app.job_authoring.contracts import (
    EditableOutputValue,
    JobDocumentRevision,
    TaskBundleEditValue,
)
from app.job_authoring.errors import AuthoringError

_UTC = datetime(2026, 7, 23, 12, 0, 0, tzinfo=UTC)


def _create_command(
    session_id: UUID | None = None,
    command_id: UUID | None = None,
    job_title: str = "門市補貨專員",
) -> CreateJobDocumentCommand:
    return CreateJobDocumentCommand(
        command_id=command_id or uuid4(),
        tenant_id=uuid4(),
        session_id=session_id or uuid4(),
        job_title=job_title,
        occurred_at=_UTC,
    )


def _initial_revision(command: CreateJobDocumentCommand) -> JobDocumentRevision:
    return transitions.create_initial_document(command)


def _add_command(
    head: JobDocumentRevision,
    *,
    statement: str = "彙整各門市缺貨明細並提出補貨建議",
    outputs: tuple[str, ...] = ("補貨建議表",),
    command_id: UUID | None = None,
) -> EmployeeTaskBundleCommand:
    return EmployeeTaskBundleCommand(
        command_id=command_id or uuid4(),
        tenant_id=uuid4(),
        document_id=head.document_id,
        expected_revision_id=head.revision_id,
        expected_revision_hash=head.snapshot_hash,
        action="add",
        target_task_id=None,
        expected_target_version=None,
        value=TaskBundleEditValue(
            statement=statement,
            outputs=tuple(
                EditableOutputValue(output_id=None, statement=text) for text in outputs
            ),
        ),
        occurred_at=_UTC,
    )


# --- create initial document (plan §7.1, §6.1) ------------------------------


def test_create_initial_document_is_deterministic() -> None:
    command = _create_command()
    revision = transitions.create_initial_document(command)

    assert revision.document_id == uuid5(command.session_id, "job-authoring/document")
    assert revision.revision_id == uuid5(command.command_id, "job-authoring/revision")
    assert revision.revision_number == 0
    assert revision.parent_revision_id is None
    assert revision.source_kind == "initial"
    assert revision.snapshot.tasks == ()
    assert revision.snapshot.job_title == "門市補貨專員"
    assert revision.snapshot_hash == canonical_hash(revision.snapshot)
    assert revision.occurred_at == _UTC


def test_create_initial_document_same_input_same_output() -> None:
    command = _create_command()
    first = transitions.create_initial_document(command)
    second = transitions.create_initial_document(command)
    assert first == second


# --- employee direct add (plan §7.2, §6.1) ----------------------------------


def test_direct_add_appends_task_with_derived_ids() -> None:
    create = _create_command()
    head = _initial_revision(create)
    command = _add_command(head, outputs=("補貨建議表", "缺貨統計"))

    revision = transitions.apply_direct_add(head, command)

    assert revision.revision_number == 1
    assert revision.parent_revision_id == head.revision_id
    assert revision.source_kind == "employee_direct_edit"
    assert revision.command_id == command.command_id
    assert len(revision.snapshot.tasks) == 1
    task = revision.snapshot.tasks[0]
    assert task.task_id == uuid5(command.command_id, "job-authoring/task")
    assert task.entity_version == 1
    assert task.provenance.source_kind == "employee_document_edit"
    assert task.provenance.source_id == command.command_id
    assert task.provenance.evidence_basis == ()
    assert tuple(o.output_id for o in task.outputs) == (
        uuid5(command.command_id, "job-authoring/output/0001"),
        uuid5(command.command_id, "job-authoring/output/0002"),
    )
    assert revision.snapshot_hash == canonical_hash(revision.snapshot)


def test_direct_add_rejects_revision_conflict() -> None:
    create = _create_command()
    head = _initial_revision(create)
    command = _add_command(head).model_copy(update={"expected_revision_hash": "sha256:" + "0" * 64})
    with pytest.raises(AuthoringError) as excinfo:
        transitions.apply_direct_add(head, command)
    assert excinfo.value.code == "authoring_revision_conflict"


def test_direct_add_capacity_exceeded_fails_closed() -> None:
    create = _create_command()
    head = _initial_revision(create)
    # Grow to 64 tasks by chaining adds.
    current = head
    for _ in range(64):
        current = transitions.apply_direct_add(current, _add_command(current))
    assert len(current.snapshot.tasks) == 64
    with pytest.raises(AuthoringError) as excinfo:
        transitions.apply_direct_add(current, _add_command(current))
    assert excinfo.value.code == "authoring_capacity_exceeded"


# --- employee direct replace (plan §7.3) ------------------------------------


def _head_with_one_task() -> JobDocumentRevision:
    create = _create_command()
    initial = _initial_revision(create)
    return transitions.apply_direct_add(
        initial, _add_command(initial, statement="舊任務", outputs=("舊產出",))
    )


def _replace_command(
    head: JobDocumentRevision,
    *,
    target: JobDocumentRevision,
    target_task_index: int = 0,
    statement: str,
    outputs: tuple[tuple[UUID | None, str], ...],
    command_id: UUID | None = None,
    expected_target_version: int | None = None,
) -> EmployeeTaskBundleCommand:
    task = target.snapshot.tasks[target_task_index]
    return EmployeeTaskBundleCommand(
        command_id=command_id or uuid4(),
        tenant_id=uuid4(),
        document_id=head.document_id,
        expected_revision_id=head.revision_id,
        expected_revision_hash=head.snapshot_hash,
        action="replace",
        target_task_id=task.task_id,
        expected_target_version=(
            expected_target_version
            if expected_target_version is not None
            else task.entity_version
        ),
        value=TaskBundleEditValue(
            statement=statement,
            outputs=tuple(
                EditableOutputValue(output_id=oid, statement=text)
                for oid, text in outputs
            ),
        ),
        occurred_at=_UTC,
    )


def test_replace_keeps_task_id_position_and_bumps_version() -> None:
    head = _head_with_one_task()
    original = head.snapshot.tasks[0]
    kept_output_id = original.outputs[0].output_id
    command = _replace_command(
        head,
        target=head,
        statement="新任務描述",
        outputs=((kept_output_id, "舊產出改寫"), (None, "新產出")),
    )
    revision = transitions.apply_direct_replace(head, command)

    task = revision.snapshot.tasks[0]
    assert task.task_id == original.task_id
    assert task.entity_version == original.entity_version + 1
    assert task.statement == "新任務描述"
    assert task.outputs[0].output_id == kept_output_id
    assert task.outputs[1].output_id == uuid5(
        command.command_id, "job-authoring/output/0002"
    )
    assert all(
        o.provenance.source_kind == "employee_document_edit" for o in task.outputs
    )
    assert task.provenance.source_id == command.command_id


def test_replace_rejects_stale_target_version() -> None:
    head = _head_with_one_task()
    command = _replace_command(
        head,
        target=head,
        statement="新任務",
        outputs=(),
        expected_target_version=99,
    )
    with pytest.raises(AuthoringError) as excinfo:
        transitions.apply_direct_replace(head, command)
    assert excinfo.value.code == "authoring_task_version_conflict"


def test_replace_rejects_missing_target() -> None:
    head = _head_with_one_task()
    command = _replace_command(
        head, target=head, statement="新任務", outputs=()
    ).model_copy(update={"target_task_id": uuid4()})
    with pytest.raises(AuthoringError) as excinfo:
        transitions.apply_direct_replace(head, command)
    assert excinfo.value.code == "authoring_task_not_found"


def test_replace_rejects_foreign_output_id() -> None:
    head = _head_with_one_task()
    command = _replace_command(
        head,
        target=head,
        statement="新任務",
        outputs=((uuid4(), "外來產出"),),
    )
    with pytest.raises(AuthoringError) as excinfo:
        transitions.apply_direct_replace(head, command)
    assert excinfo.value.code == "authoring_output_scope_invalid"


def test_replace_no_semantic_change_is_rejected() -> None:
    head = _head_with_one_task()
    original = head.snapshot.tasks[0]
    command = _replace_command(
        head,
        target=head,
        statement=original.statement,
        outputs=((original.outputs[0].output_id, original.outputs[0].statement),),
    )
    with pytest.raises(AuthoringError) as excinfo:
        transitions.apply_direct_replace(head, command)
    assert excinfo.value.code == "authoring_no_semantic_change"


def test_replace_preserves_position_among_tasks() -> None:
    head = _head_with_one_task()
    head = transitions.apply_direct_add(
        head, _add_command(head, statement="第二任務", outputs=())
    )
    second = head.snapshot.tasks[1]
    command = _replace_command(
        head,
        target=head,
        target_task_index=1,
        statement="第二任務改寫",
        outputs=(),
    )
    revision = transitions.apply_direct_replace(head, command)

    assert revision.snapshot.tasks[0].task_id == head.snapshot.tasks[0].task_id
    assert revision.snapshot.tasks[1].task_id == second.task_id
    assert revision.snapshot.tasks[1].statement == "第二任務改寫"
    assert revision.snapshot.tasks[1].entity_version == second.entity_version + 1


# --- proposal build + accept/edit/reject (plan §7.4-§7.7) -------------------

from app.job_authoring.commands import (  # noqa: E402
    CreateTaskProposalCommand,
    EmployeeProposalDecisionCommand,
)
from app.job_authoring.contracts import (  # noqa: E402
    EvidenceBasisRef,
    ProposalStaleReason,
    ProposedOutputDraft,
    TaskBundleProposalDraft,
)

_EV_ID = uuid4()
_EV_HASH = "sha256:" + "a" * 64
_ACTIVE_EVIDENCE = {_EV_ID: _EV_HASH}


def _basis() -> tuple[EvidenceBasisRef, ...]:
    return (EvidenceBasisRef(evidence_id=_EV_ID, evidence_hash=_EV_HASH),)


def _proposal_command(head: JobDocumentRevision) -> CreateTaskProposalCommand:
    return CreateTaskProposalCommand(
        proposal_id=uuid4(),
        tenant_id=uuid4(),
        session_id=head.snapshot.session_id,
        document_id=head.document_id,
        base_revision_id=head.revision_id,
        base_revision_hash=head.snapshot_hash,
        evidence_state_version=3,
        evidence_state_hash="sha256:" + "b" * 64,
        source_kind="scripted",
        source_id=uuid4(),
        draft=TaskBundleProposalDraft(
            statement="彙整各門市缺貨明細並提出補貨建議",
            evidence_basis=_basis(),
            outputs=(
                ProposedOutputDraft(statement="補貨建議表", evidence_basis=_basis()),
            ),
            plain_language_reason="員工描述其每日盤點缺貨並回報",
            limitations=(),
        ),
        created_at=_UTC,
    )


def _decision_command(
    head: JobDocumentRevision,
    proposal,
    *,
    action: str,
    edited_value: TaskBundleEditValue | None = None,
    command_id: UUID | None = None,
) -> EmployeeProposalDecisionCommand:
    return EmployeeProposalDecisionCommand(
        command_id=command_id or uuid4(),
        tenant_id=uuid4(),
        document_id=head.document_id,
        proposal_id=proposal.proposal_id,
        expected_revision_id=head.revision_id,
        expected_revision_hash=head.snapshot_hash,
        action=action,
        edited_value=edited_value,
        occurred_at=_UTC,
    )


def test_build_proposal_derives_ids_and_preserves_basis() -> None:
    head = _initial_revision(_create_command())
    command = _proposal_command(head)
    proposal = transitions.build_proposal(command, _ACTIVE_EVIDENCE)

    assert proposal.operation == "add_task"
    assert proposal.proposed_task.task_id == uuid5(
        command.proposal_id, "job-authoring/task"
    )
    assert proposal.proposed_task.outputs[0].output_id == uuid5(
        command.proposal_id, "job-authoring/output/0001"
    )
    assert proposal.proposed_task.evidence_basis == _basis()
    assert proposal.proposed_task.outputs[0].evidence_basis == _basis()
    assert proposal.base_revision_id == head.revision_id


def test_build_proposal_rejects_missing_evidence() -> None:
    head = _initial_revision(_create_command())
    command = _proposal_command(head)
    with pytest.raises(AuthoringError) as excinfo:
        transitions.build_proposal(command, {})
    assert excinfo.value.code == "authoring_evidence_invalid"


def test_build_proposal_rejects_wrong_evidence_hash() -> None:
    head = _initial_revision(_create_command())
    command = _proposal_command(head)
    with pytest.raises(AuthoringError) as excinfo:
        transitions.build_proposal(command, {_EV_ID: "sha256:" + "c" * 64})
    assert excinfo.value.code == "authoring_evidence_invalid"


def test_accept_materializes_proposed_task_with_accepted_provenance() -> None:
    head = _initial_revision(_create_command())
    proposal = transitions.build_proposal(_proposal_command(head), _ACTIVE_EVIDENCE)
    decision_command = _decision_command(head, proposal, action="accept")

    revision, decision = transitions.materialize_accept(
        head, proposal, decision_command, _ACTIVE_EVIDENCE
    )

    assert revision.revision_number == 1
    assert revision.source_kind == "ai_proposal_accept"
    task = revision.snapshot.tasks[0]
    assert task.task_id == proposal.proposed_task.task_id
    assert task.entity_version == 1
    assert task.statement == proposal.proposed_task.statement
    assert task.outputs[0].output_id == proposal.proposed_task.outputs[0].output_id
    assert task.provenance.source_kind == "accepted_ai_proposal"
    assert task.provenance.source_id == proposal.proposal_id
    assert task.provenance.evidence_basis == _basis()
    assert task.outputs[0].provenance.evidence_basis == _basis()
    assert decision.action == "accept"
    assert decision.result_revision_id == revision.revision_id
    assert decision.final_task == task


def test_accept_stale_when_base_revision_advanced() -> None:
    head = _initial_revision(_create_command())
    proposal = transitions.build_proposal(_proposal_command(head), _ACTIVE_EVIDENCE)
    advanced = transitions.apply_direct_add(head, _add_command(head))
    decision_command = _decision_command(advanced, proposal, action="accept")
    with pytest.raises(AuthoringError) as excinfo:
        transitions.materialize_accept(
            advanced, proposal, decision_command, _ACTIVE_EVIDENCE
        )
    assert excinfo.value.code == "authoring_proposal_stale"
    assert excinfo.value.details["stale_reason"] == (
        ProposalStaleReason.BASE_REVISION_CHANGED
    )


def test_accept_stale_when_evidence_changed() -> None:
    head = _initial_revision(_create_command())
    proposal = transitions.build_proposal(_proposal_command(head), _ACTIVE_EVIDENCE)
    decision_command = _decision_command(head, proposal, action="accept")
    with pytest.raises(AuthoringError) as excinfo:
        transitions.materialize_accept(head, proposal, decision_command, {})
    assert excinfo.value.code == "authoring_proposal_stale"
    assert excinfo.value.details["stale_reason"] == (
        ProposalStaleReason.EVIDENCE_BASIS_CHANGED
    )


def test_edit_then_accept_uses_employee_provenance_and_new_output_ids() -> None:
    head = _initial_revision(_create_command())
    proposal = transitions.build_proposal(_proposal_command(head), _ACTIVE_EVIDENCE)
    kept_output_id = proposal.proposed_task.outputs[0].output_id
    edited = TaskBundleEditValue(
        statement="員工改寫後的任務描述",
        outputs=(
            EditableOutputValue(output_id=kept_output_id, statement="改寫的補貨建議表"),
            EditableOutputValue(output_id=None, statement="員工新增產出"),
        ),
    )
    decision_command = _decision_command(
        head, proposal, action="edit", edited_value=edited
    )

    revision, decision = transitions.materialize_edit(
        head, proposal, decision_command, _ACTIVE_EVIDENCE
    )

    task = revision.snapshot.tasks[0]
    assert revision.source_kind == "employee_proposal_edit"
    assert task.task_id == proposal.proposed_task.task_id
    assert task.statement == "員工改寫後的任務描述"
    assert task.provenance.source_kind == "employee_proposal_edit"
    assert task.provenance.source_id == proposal.proposal_id
    # kept proposal output retains proposal basis; new output gets empty basis
    assert task.outputs[0].output_id == kept_output_id
    assert task.outputs[0].provenance.evidence_basis == _basis()
    assert task.outputs[1].output_id == uuid5(
        decision_command.command_id, "job-authoring/output/0002"
    )
    assert task.outputs[1].provenance.evidence_basis == ()
    assert decision.action == "edit"


def test_edit_equal_to_proposal_requires_accept() -> None:
    head = _initial_revision(_create_command())
    proposal = transitions.build_proposal(_proposal_command(head), _ACTIVE_EVIDENCE)
    identical = TaskBundleEditValue(
        statement=proposal.proposed_task.statement,
        outputs=(
            EditableOutputValue(
                output_id=proposal.proposed_task.outputs[0].output_id,
                statement=proposal.proposed_task.outputs[0].statement,
            ),
        ),
    )
    decision_command = _decision_command(
        head, proposal, action="edit", edited_value=identical
    )
    with pytest.raises(AuthoringError) as excinfo:
        transitions.materialize_edit(head, proposal, decision_command, _ACTIVE_EVIDENCE)
    assert excinfo.value.code == "authoring_no_semantic_change"
    assert excinfo.value.details["required_action"] == "accept"


def test_reject_produces_decision_without_revision() -> None:
    head = _initial_revision(_create_command())
    proposal = transitions.build_proposal(_proposal_command(head), _ACTIVE_EVIDENCE)
    decision_command = _decision_command(head, proposal, action="reject")

    decision = transitions.build_reject_decision(head, proposal, decision_command)

    assert decision.action == "reject"
    assert decision.final_task is None
    assert decision.result_revision_id is None
    assert decision.proposal_id == proposal.proposal_id
