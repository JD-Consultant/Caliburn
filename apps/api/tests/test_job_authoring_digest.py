"""No-network tests for the deterministic bounded JobStateDigest (plan §5.8)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.job_authoring.canonical import canonical_hash
from app.job_authoring.contracts import (
    JobDocumentDraft,
    JobDocumentRevision,
    JobFieldProvenance,
    JobOutput,
    JobStateDigest,
    JobTask,
)
from app.job_authoring.digest import build_job_state_digest

_UTC = datetime(2026, 7, 23, 12, 0, 0, tzinfo=UTC)


def _prov() -> JobFieldProvenance:
    return JobFieldProvenance(
        source_kind="employee_document_edit", source_id=uuid4(), evidence_basis=()
    )


def _task(statement: str = "任務", output_statements: tuple[str, ...] = ()) -> JobTask:
    return JobTask(
        task_id=uuid4(),
        entity_version=1,
        statement=statement,
        outputs=tuple(
            JobOutput(output_id=uuid4(), statement=text, provenance=_prov())
            for text in output_statements
        ),
        provenance=_prov(),
    )


def _revision(tasks: tuple[JobTask, ...]) -> JobDocumentRevision:
    snapshot = JobDocumentDraft(
        document_id=uuid4(),
        session_id=uuid4(),
        job_title="門市補貨專員",
        tasks=tasks,
    )
    return JobDocumentRevision(
        revision_id=uuid4(),
        document_id=snapshot.document_id,
        revision_number=1,
        parent_revision_id=uuid4(),
        snapshot=snapshot,
        snapshot_hash=canonical_hash(snapshot),
        source_kind="employee_direct_edit",
        command_id=uuid4(),
        occurred_at=_UTC,
    )


def test_digest_carries_revision_metadata_and_self_hash() -> None:
    revision = _revision((_task(),))
    digest = build_job_state_digest(revision, pending_proposals=(), pending_proposal_count=0, stale_proposal_count=0)

    assert isinstance(digest, JobStateDigest)
    assert digest.document_id == revision.document_id
    assert digest.session_id == revision.snapshot.session_id
    assert digest.revision_id == revision.revision_id
    assert digest.revision_number == revision.revision_number
    assert digest.revision_hash == revision.snapshot_hash
    assert digest.job_title == "門市補貨專員"


def test_digest_orders_tasks_and_assigns_ordinals() -> None:
    revision = _revision((_task("第一"), _task("第二"), _task("第三")))
    digest = build_job_state_digest(revision, pending_proposals=(), pending_proposal_count=0, stale_proposal_count=0)
    assert tuple(t.ordinal for t in digest.tasks) == ("T01", "T02", "T03")
    assert tuple(t.task_id for t in digest.tasks) == tuple(
        t.task_id for t in revision.snapshot.tasks
    )


def test_digest_caps_tasks_at_32() -> None:
    revision = _revision(tuple(_task(f"任務{i}") for i in range(33)))
    digest = build_job_state_digest(revision, pending_proposals=(), pending_proposal_count=0, stale_proposal_count=0)
    assert len(digest.tasks) == 32
    assert digest.omitted_task_count == 1
    assert digest.tasks[-1].ordinal == "T32"


def test_digest_caps_outputs_at_4() -> None:
    revision = _revision((_task("任務", tuple(f"產出{i}" for i in range(5))),))
    digest = build_job_state_digest(revision, pending_proposals=(), pending_proposal_count=0, stale_proposal_count=0)
    assert len(digest.tasks[0].output_excerpts) == 4
    assert digest.tasks[0].omitted_output_count == 1


def test_digest_truncates_excerpt_to_240_code_points() -> None:
    revision = _revision((_task("任" * 300),))
    digest = build_job_state_digest(revision, pending_proposals=(), pending_proposal_count=0, stale_proposal_count=0)
    excerpt = digest.tasks[0].statement_excerpt
    assert len(excerpt) == 240
    assert excerpt.endswith("…")
    assert excerpt[:239] == "任" * 239


def test_digest_truncation_does_not_split_emoji() -> None:
    revision = _revision((_task("😀" * 300),))
    digest = build_job_state_digest(revision, pending_proposals=(), pending_proposal_count=0, stale_proposal_count=0)
    excerpt = digest.tasks[0].statement_excerpt
    assert len(excerpt) == 240
    assert excerpt[:239] == "😀" * 239


def test_digest_short_statement_is_not_truncated() -> None:
    revision = _revision((_task("短任務"),))
    digest = build_job_state_digest(revision, pending_proposals=(), pending_proposal_count=0, stale_proposal_count=0)
    assert digest.tasks[0].statement_excerpt == "短任務"


def test_digest_pending_ids_sorted_and_capped_at_16() -> None:
    revision = _revision((_task(),))
    pending = tuple(
        (_UTC + timedelta(seconds=i), UUID(int=i)) for i in range(17, 0, -1)
    )
    digest = build_job_state_digest(
        revision,
        pending_proposals=pending,
        pending_proposal_count=17,
        stale_proposal_count=2,
    )
    expected = [pid for _, pid in sorted(pending)][:16]
    assert list(digest.pending_proposal_ids) == expected
    assert digest.pending_proposal_count == 17
    assert digest.stale_proposal_count == 2


def test_digest_is_deterministic_for_same_input() -> None:
    revision = _revision((_task("任務", ("產出",)),))
    pending = ((_UTC, UUID(int=5)),)
    first = build_job_state_digest(
        revision, pending_proposals=pending, pending_proposal_count=1, stale_proposal_count=1
    )
    second = build_job_state_digest(
        revision, pending_proposals=pending, pending_proposal_count=1, stale_proposal_count=1
    )
    assert first == second
    assert first.digest_hash == second.digest_hash
    assert first.digest_hash == canonical_hash(
        first.model_dump(mode="json", exclude={"digest_hash"})
    )


def test_digest_excludes_full_reason_and_evidence_text() -> None:
    revision = _revision((_task("任務", ("產出",)),))
    payload = build_job_state_digest(
        revision, pending_proposals=(), pending_proposal_count=0, stale_proposal_count=0
    ).model_dump(mode="json")
    keys = set(payload)
    assert "plain_language_reason" not in keys
    assert "evidence_basis" not in keys
    assert "limitations" not in keys
