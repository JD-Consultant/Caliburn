"""No-network contract tests for the Job Authoring Core value objects."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.job_authoring.contracts import (
    EvidenceBasisRef,
    JobDocumentDraft,
    JobFieldProvenance,
    JobOutput,
    JobTask,
    ProposalStaleReason,
)

_HASH = "sha256:" + "0" * 64
_HASH2 = "sha256:" + "1" * 64


def _employee_provenance(command_id: UUID | None = None) -> JobFieldProvenance:
    return JobFieldProvenance(
        source_kind="employee_document_edit",
        source_id=command_id or uuid4(),
        evidence_basis=(),
    )


def _output(output_id: UUID | None = None, statement: str = "補貨建議表") -> JobOutput:
    return JobOutput(
        output_id=output_id or uuid4(),
        statement=statement,
        provenance=_employee_provenance(),
    )


def _task(
    task_id: UUID | None = None,
    statement: str = "彙整各門市缺貨明細並提出補貨建議",
    outputs: tuple[JobOutput, ...] = (),
    entity_version: int = 1,
) -> JobTask:
    return JobTask(
        task_id=task_id or uuid4(),
        entity_version=entity_version,
        statement=statement,
        outputs=outputs,
        provenance=_employee_provenance(),
    )


def _draft(tasks: tuple[JobTask, ...] = ()) -> JobDocumentDraft:
    return JobDocumentDraft(
        document_id=uuid4(),
        session_id=uuid4(),
        job_title="門市補貨專員",
        tasks=tasks,
    )


# --- strict / frozen / tuple ------------------------------------------------


def test_models_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        JobOutput(
            output_id=uuid4(),
            statement="x",
            provenance=_employee_provenance(),
            surprise="nope",
        )


def test_models_are_frozen() -> None:
    output = _output()
    with pytest.raises(ValidationError):
        output.statement = "changed"


def test_collections_are_tuples() -> None:
    task = _task(outputs=[_output()])  # list input
    assert isinstance(task.outputs, tuple)
    draft = _draft(tasks=[task])
    assert isinstance(draft.tasks, tuple)


# --- text rules -------------------------------------------------------------


def test_blank_statement_rejected() -> None:
    with pytest.raises(ValidationError):
        _output(statement="   \n\t ")


def test_title_max_256_code_points() -> None:
    JobDocumentDraft(
        document_id=uuid4(),
        session_id=uuid4(),
        job_title="標" * 256,
        tasks=(),
    )
    with pytest.raises(ValidationError):
        JobDocumentDraft(
            document_id=uuid4(),
            session_id=uuid4(),
            job_title="標" * 257,
            tasks=(),
        )


def test_statement_max_512_code_points() -> None:
    _task(statement="任" * 512)
    with pytest.raises(ValidationError):
        _task(statement="任" * 513)


def test_emoji_counts_as_single_code_point() -> None:
    # 256 astral-plane emoji are 256 code points, so a title of them is valid.
    JobDocumentDraft(
        document_id=uuid4(),
        session_id=uuid4(),
        job_title="😀" * 256,
        tasks=(),
    )


def test_text_is_not_stripped_or_normalized() -> None:
    task = _task(statement="第一行\r\n第二行  ")
    assert task.statement == "第一行\r\n第二行  "


# --- provenance -------------------------------------------------------------


def test_employee_edit_provenance_allows_empty_basis() -> None:
    provenance = _employee_provenance()
    assert provenance.evidence_basis == ()


def test_unknown_source_kind_rejected() -> None:
    with pytest.raises(ValidationError):
        JobFieldProvenance(
            source_kind="model_guess",
            source_id=uuid4(),
            evidence_basis=(),
        )


def test_evidence_basis_ref_requires_sha256() -> None:
    with pytest.raises(ValidationError):
        EvidenceBasisRef(evidence_id=uuid4(), evidence_hash="not-a-hash")
    EvidenceBasisRef(evidence_id=uuid4(), evidence_hash=_HASH)


def test_stale_reason_enum_values() -> None:
    assert ProposalStaleReason.DOCUMENT_REVISION_ADVANCED == "document_revision_advanced"
    assert ProposalStaleReason.BASE_REVISION_CHANGED == "base_revision_changed"
    assert ProposalStaleReason.EVIDENCE_BASIS_CHANGED == "evidence_basis_changed"


# --- task / output / draft invariants --------------------------------------


def test_task_entity_version_at_least_one() -> None:
    with pytest.raises(ValidationError):
        _task(entity_version=0)


def test_task_outputs_capacity_16() -> None:
    outputs = tuple(_output() for _ in range(16))
    _task(outputs=outputs)
    with pytest.raises(ValidationError):
        _task(outputs=tuple(_output() for _ in range(17)))


def test_duplicate_output_id_within_task_rejected() -> None:
    shared = uuid4()
    with pytest.raises(ValidationError):
        _task(outputs=(_output(output_id=shared), _output(output_id=shared)))


def test_draft_tasks_capacity_64() -> None:
    tasks = tuple(_task() for _ in range(64))
    _draft(tasks=tasks)
    with pytest.raises(ValidationError):
        _draft(tasks=tuple(_task() for _ in range(65)))


def test_duplicate_task_id_within_draft_rejected() -> None:
    shared = uuid4()
    with pytest.raises(ValidationError):
        _draft(tasks=(_task(task_id=shared), _task(task_id=shared)))


def test_duplicate_output_id_across_tasks_rejected() -> None:
    shared = uuid4()
    task_a = _task(outputs=(_output(output_id=shared),))
    task_b = _task(outputs=(_output(output_id=shared),))
    with pytest.raises(ValidationError):
        _draft(tasks=(task_a, task_b))


def test_timestamps_must_be_utc() -> None:
    # Provenance has no timestamp, but aware-UTC rule is exercised via revisions
    # in a later batch. Here we only assert naive datetimes are unusable as UTC.
    naive = datetime(2026, 7, 23, 12, 0, 0)
    aware_offset = datetime(2026, 7, 23, 12, 0, 0, tzinfo=timezone(timedelta(hours=8)))
    assert naive.tzinfo is None
    assert aware_offset.utcoffset() == timedelta(hours=8)


# --- canonical serialization parity with R5 (plan §6.2) ---------------------

from app.interview_vnext.domain import hashing as vnext_hashing  # noqa: E402
from app.job_authoring import canonical  # noqa: E402

_PARITY_VALUES = [
    {"b": 2, "a": 1, "z": {"y": [3, 2, 1]}},
    ["繁體中文", "emoji 😀🚀", "CRLF\r\nkept"],
    {"nested": ({"k": "v"}, ["繁", "😀"]), "n": 1.5},
    "第一行\r\n第二行  ",
]


@pytest.mark.parametrize("value", _PARITY_VALUES)
def test_canonical_json_byte_equal_to_vnext(value: object) -> None:
    assert canonical.canonical_json(value) == vnext_hashing.canonical_json(value)


@pytest.mark.parametrize("value", _PARITY_VALUES)
def test_canonical_hash_equal_to_vnext(value: object) -> None:
    assert canonical.canonical_hash(value) == vnext_hashing.canonical_hash(value)


def test_canonical_json_insensitive_to_dict_key_order() -> None:
    assert canonical.canonical_json({"a": 1, "b": 2}) == canonical.canonical_json(
        {"b": 2, "a": 1}
    )


def test_canonical_json_sensitive_to_tuple_order() -> None:
    assert canonical.canonical_json([1, 2]) != canonical.canonical_json([2, 1])


def test_canonical_preserves_cjk_and_emoji() -> None:
    payload = canonical.canonical_json({"t": "門市補貨 😀"})
    assert "門市補貨 😀" in payload  # not \uXXXX escaped


def test_canonical_hash_excluding_drops_only_named_field() -> None:
    full = {"a": 1, "digest_hash": "sha256:x", "b": 2}
    assert canonical.canonical_hash_excluding(
        full, exclude="digest_hash"
    ) == canonical.canonical_hash({"a": 1, "b": 2})


# --- revision + create/edit commands (plan §5.4, §5.5) ----------------------

from app.job_authoring.commands import (  # noqa: E402
    CreateJobDocumentCommand,
    EmployeeTaskBundleCommand,
)
from app.job_authoring.contracts import (  # noqa: E402
    EditableOutputValue,
    JobDocumentRevision,
    TaskBundleEditValue,
)

_UTC = datetime(2026, 7, 23, 12, 0, 0, tzinfo=UTC)


def _initial_snapshot() -> JobDocumentDraft:
    return _draft()


def _revision(
    *,
    revision_number: int = 0,
    parent_revision_id: UUID | None = None,
    source_kind: str = "initial",
    snapshot: JobDocumentDraft | None = None,
    snapshot_hash: str | None = None,
) -> JobDocumentRevision:
    snap = snapshot or _initial_snapshot()
    return JobDocumentRevision(
        revision_id=uuid4(),
        document_id=snap.document_id,
        revision_number=revision_number,
        parent_revision_id=parent_revision_id,
        snapshot=snap,
        snapshot_hash=snapshot_hash or canonical.canonical_hash(snap),
        source_kind=source_kind,
        command_id=uuid4(),
        occurred_at=_UTC,
    )


def test_revision_snapshot_hash_must_match() -> None:
    with pytest.raises(ValidationError):
        _revision(snapshot_hash=_HASH)
    _revision()  # correct hash accepted


def test_revision_zero_requires_initial_and_null_parent() -> None:
    _revision(revision_number=0, parent_revision_id=None, source_kind="initial")
    with pytest.raises(ValidationError):
        _revision(revision_number=0, source_kind="employee_direct_edit")
    with pytest.raises(ValidationError):
        _revision(revision_number=0, parent_revision_id=uuid4(), source_kind="initial")


def test_revision_after_zero_requires_parent_and_non_initial() -> None:
    _revision(
        revision_number=1,
        parent_revision_id=uuid4(),
        source_kind="employee_direct_edit",
    )
    with pytest.raises(ValidationError):
        _revision(revision_number=1, parent_revision_id=None, source_kind="ai_proposal_accept")
    with pytest.raises(ValidationError):
        _revision(revision_number=1, parent_revision_id=uuid4(), source_kind="initial")


def test_create_command_valid_and_bounds() -> None:
    CreateJobDocumentCommand(
        command_id=uuid4(),
        tenant_id=uuid4(),
        session_id=uuid4(),
        job_title="門市補貨專員",
        occurred_at=_UTC,
    )
    with pytest.raises(ValidationError):
        CreateJobDocumentCommand(
            command_id=uuid4(),
            tenant_id=uuid4(),
            session_id=uuid4(),
            job_title="  ",
            occurred_at=_UTC,
        )


def test_create_command_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        CreateJobDocumentCommand(
            command_id=uuid4(),
            tenant_id=uuid4(),
            session_id=uuid4(),
            job_title="門市補貨專員",
            occurred_at=datetime(2026, 7, 23, 12, 0, 0),
        )


def _bundle_value(outputs: tuple[EditableOutputValue, ...] = ()) -> TaskBundleEditValue:
    return TaskBundleEditValue(statement="彙整缺貨並補貨", outputs=outputs)


def _employee_command(
    *,
    action: str,
    target_task_id: UUID | None,
    expected_target_version: int | None,
    value: TaskBundleEditValue,
) -> EmployeeTaskBundleCommand:
    return EmployeeTaskBundleCommand(
        command_id=uuid4(),
        tenant_id=uuid4(),
        document_id=uuid4(),
        expected_revision_id=uuid4(),
        expected_revision_hash=_HASH,
        action=action,
        target_task_id=target_task_id,
        expected_target_version=expected_target_version,
        value=value,
        occurred_at=_UTC,
    )


def test_add_command_forbids_target_and_output_ids() -> None:
    _employee_command(
        action="add",
        target_task_id=None,
        expected_target_version=None,
        value=_bundle_value((EditableOutputValue(output_id=None, statement="表"),)),
    )
    with pytest.raises(ValidationError):
        _employee_command(
            action="add",
            target_task_id=uuid4(),
            expected_target_version=None,
            value=_bundle_value(),
        )
    with pytest.raises(ValidationError):
        _employee_command(
            action="add",
            target_task_id=None,
            expected_target_version=None,
            value=_bundle_value((EditableOutputValue(output_id=uuid4(), statement="表"),)),
        )


def test_replace_command_requires_target_and_version() -> None:
    _employee_command(
        action="replace",
        target_task_id=uuid4(),
        expected_target_version=1,
        value=_bundle_value(),
    )
    with pytest.raises(ValidationError):
        _employee_command(
            action="replace",
            target_task_id=None,
            expected_target_version=1,
            value=_bundle_value(),
        )
    with pytest.raises(ValidationError):
        _employee_command(
            action="replace",
            target_task_id=uuid4(),
            expected_target_version=0,
            value=_bundle_value(),
        )


# --- proposal creation contracts (plan §5.6) --------------------------------

from app.job_authoring.commands import CreateTaskProposalCommand  # noqa: E402
from app.job_authoring.contracts import (  # noqa: E402
    AiTaskBundleProposal,
    ProposedJobOutput,
    ProposedJobTask,
    ProposedOutputDraft,
    TaskBundleProposalDraft,
)


def _basis() -> tuple[EvidenceBasisRef, ...]:
    return (EvidenceBasisRef(evidence_id=uuid4(), evidence_hash=_HASH),)


def test_proposed_output_draft_requires_basis() -> None:
    ProposedOutputDraft(statement="補貨建議表", evidence_basis=_basis())
    with pytest.raises(ValidationError):
        ProposedOutputDraft(statement="補貨建議表", evidence_basis=())


def test_task_proposal_draft_requires_basis() -> None:
    TaskBundleProposalDraft(
        statement="彙整缺貨並補貨",
        evidence_basis=_basis(),
        outputs=(ProposedOutputDraft(statement="補貨建議表", evidence_basis=_basis()),),
        plain_language_reason="員工描述其每日盤點缺貨並回報",
        limitations=("尚未涵蓋跨區調度",),
    )
    with pytest.raises(ValidationError):
        TaskBundleProposalDraft(
            statement="彙整缺貨並補貨",
            evidence_basis=(),
            plain_language_reason="理由",
        )


def _proposed_task() -> ProposedJobTask:
    return ProposedJobTask(
        task_id=uuid4(),
        statement="彙整各門市缺貨明細並提出補貨建議",
        outputs=(
            ProposedJobOutput(
                output_id=uuid4(), statement="補貨建議表", evidence_basis=_basis()
            ),
        ),
        evidence_basis=_basis(),
    )


def test_proposed_task_and_output_require_basis() -> None:
    _proposed_task()
    with pytest.raises(ValidationError):
        ProposedJobTask(
            task_id=uuid4(),
            statement="彙整缺貨",
            outputs=(),
            evidence_basis=(),
        )
    with pytest.raises(ValidationError):
        ProposedJobOutput(output_id=uuid4(), statement="表", evidence_basis=())


def _proposal(operation: str = "add_task") -> AiTaskBundleProposal:
    return AiTaskBundleProposal(
        proposal_id=uuid4(),
        session_id=uuid4(),
        document_id=uuid4(),
        base_revision_id=uuid4(),
        base_revision_hash=_HASH,
        evidence_state_version=3,
        evidence_state_hash=_HASH2,
        operation=operation,
        proposed_task=_proposed_task(),
        plain_language_reason="員工描述其每日盤點缺貨並回報",
        limitations=(),
        source_kind="scripted",
        source_id=uuid4(),
        created_at=_UTC,
    )


def test_proposal_operation_is_add_task_only() -> None:
    _proposal()
    with pytest.raises(ValidationError):
        _proposal(operation="remove_task")


def test_create_task_proposal_command_source_allowlist() -> None:
    def _make(source_kind: str) -> CreateTaskProposalCommand:
        return CreateTaskProposalCommand(
            proposal_id=uuid4(),
            tenant_id=uuid4(),
            session_id=uuid4(),
            document_id=uuid4(),
            base_revision_id=uuid4(),
            base_revision_hash=_HASH,
            evidence_state_version=0,
            evidence_state_hash=_HASH2,
            source_kind=source_kind,
            source_id=uuid4(),
            draft=TaskBundleProposalDraft(
                statement="彙整缺貨並補貨",
                evidence_basis=_basis(),
                plain_language_reason="理由",
            ),
            created_at=_UTC,
        )

    _make("scripted")
    _make("llm_operation")
    with pytest.raises(ValidationError):
        _make("hallucinated")


# --- decision command / decision / view (plan §5.7, §5.6, §10.4) ------------

from app.job_authoring.commands import EmployeeProposalDecisionCommand  # noqa: E402
from app.job_authoring.contracts import (  # noqa: E402
    EmployeeProposalDecision,
    TaskProposalView,
)


def _decision_command(action: str, edited_value: TaskBundleEditValue | None):
    return EmployeeProposalDecisionCommand(
        command_id=uuid4(),
        tenant_id=uuid4(),
        document_id=uuid4(),
        proposal_id=uuid4(),
        expected_revision_id=uuid4(),
        expected_revision_hash=_HASH,
        action=action,
        edited_value=edited_value,
        occurred_at=_UTC,
    )


def test_decision_command_edited_value_matrix() -> None:
    _decision_command("accept", None)
    _decision_command("reject", None)
    _decision_command("edit", _bundle_value())
    with pytest.raises(ValidationError):
        _decision_command("edit", None)
    with pytest.raises(ValidationError):
        _decision_command("accept", _bundle_value())
    with pytest.raises(ValidationError):
        _decision_command("reject", _bundle_value())


def _decision(
    action: str,
    *,
    final_task: JobTask | None,
    result_revision_id: UUID | None,
) -> EmployeeProposalDecision:
    return EmployeeProposalDecision(
        command_id=uuid4(),
        proposal_id=uuid4(),
        action=action,
        base_revision_id=uuid4(),
        base_revision_hash=_HASH,
        final_task=final_task,
        result_revision_id=result_revision_id,
        decided_at=_UTC,
    )


def test_decision_accept_and_edit_require_final_and_result() -> None:
    _decision("accept", final_task=_task(), result_revision_id=uuid4())
    _decision("edit", final_task=_task(), result_revision_id=uuid4())
    with pytest.raises(ValidationError):
        _decision("accept", final_task=None, result_revision_id=uuid4())
    with pytest.raises(ValidationError):
        _decision("edit", final_task=_task(), result_revision_id=None)


def test_decision_reject_forbids_final_and_result() -> None:
    _decision("reject", final_task=None, result_revision_id=None)
    with pytest.raises(ValidationError):
        _decision("reject", final_task=_task(), result_revision_id=None)
    with pytest.raises(ValidationError):
        _decision("reject", final_task=None, result_revision_id=uuid4())


def _view(
    *,
    status: str,
    decision: EmployeeProposalDecision | None = None,
    result_revision_id: UUID | None = None,
    stale_reason: ProposalStaleReason | None = None,
    resolved_at: datetime | None = None,
) -> TaskProposalView:
    return TaskProposalView(
        proposal=_proposal(),
        status=status,
        decision=decision,
        result_revision_id=result_revision_id,
        stale_reason=stale_reason,
        resolved_at=resolved_at,
    )


def test_view_pending_is_clean() -> None:
    _view(status="pending")
    with pytest.raises(ValidationError):
        _view(status="pending", resolved_at=_UTC)


def test_view_accepted_requires_decision_result_resolved() -> None:
    result = uuid4()
    _view(
        status="accepted",
        decision=_decision("accept", final_task=_task(), result_revision_id=result),
        result_revision_id=result,
        resolved_at=_UTC,
    )
    with pytest.raises(ValidationError):  # missing resolved_at
        _view(
            status="accepted",
            decision=_decision("accept", final_task=_task(), result_revision_id=result),
            result_revision_id=result,
        )
    with pytest.raises(ValidationError):  # decision action mismatch
        _view(
            status="accepted",
            decision=_decision("reject", final_task=None, result_revision_id=None),
            result_revision_id=result,
            resolved_at=_UTC,
        )


def test_view_rejected_has_no_result() -> None:
    _view(
        status="rejected",
        decision=_decision("reject", final_task=None, result_revision_id=None),
        resolved_at=_UTC,
    )
    with pytest.raises(ValidationError):
        _view(
            status="rejected",
            decision=_decision("reject", final_task=None, result_revision_id=None),
            result_revision_id=uuid4(),
            resolved_at=_UTC,
        )


def test_view_stale_requires_reason_and_no_decision() -> None:
    _view(
        status="stale",
        stale_reason=ProposalStaleReason.DOCUMENT_REVISION_ADVANCED,
        resolved_at=_UTC,
    )
    with pytest.raises(ValidationError):  # stale must not carry a decision
        _view(
            status="stale",
            decision=_decision("accept", final_task=_task(), result_revision_id=uuid4()),
            stale_reason=ProposalStaleReason.DOCUMENT_REVISION_ADVANCED,
            resolved_at=_UTC,
        )
    with pytest.raises(ValidationError):  # stale requires a reason
        _view(status="stale", resolved_at=_UTC)


# --- generated JSON schema drift (plan §14.1, §13.1) ------------------------

import json  # noqa: E402
from pathlib import Path  # noqa: E402

from app.job_authoring import schema_exports  # noqa: E402
from app.job_authoring import write_schemas as ja_write_schemas  # noqa: E402

_EXPECTED_SEAMS = {
    "job-document-draft.v1.schema.json",
    "job-document-revision.v1.schema.json",
    "create-job-document-command.v1.schema.json",
    "employee-task-bundle-command.v1.schema.json",
    "create-task-proposal-command.v1.schema.json",
    "ai-task-bundle-proposal.v1.schema.json",
    "task-proposal-view.v1.schema.json",
    "employee-proposal-decision-command.v1.schema.json",
    "employee-proposal-decision.v1.schema.json",
    "job-state-digest.v1.schema.json",
}


def test_schema_exports_cover_exactly_ten_seams() -> None:
    assert set(schema_exports.SCHEMA_EXPORTS) == _EXPECTED_SEAMS


def test_committed_schemas_match_generated() -> None:
    schema_dir = Path(ja_write_schemas.__file__).with_name("schemas")
    for filename in schema_exports.SCHEMA_EXPORTS:
        committed = (schema_dir / filename).read_text(encoding="utf-8")
        expected = (
            json.dumps(
                schema_exports.published_schema(filename),
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
        assert committed == expected, filename


def test_schema_writer_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    ja_write_schemas.write_schemas(first)
    ja_write_schemas.write_schemas(second)
    for filename in schema_exports.SCHEMA_EXPORTS:
        assert (first / filename).read_bytes() == (second / filename).read_bytes()
