"""Deterministic bounded projection to JobStateDigest (plan §5.8).

Pure function over one immutable revision plus the pending/stale proposal
summary. No table, no LLM summary, and pending proposals are never treated as
accepted truth. Bounds are fixed: 32 tasks, 4 outputs per task, 240 code-point
excerpts, 16 pending ids.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from .canonical import canonical_hash_excluding
from .contracts import (
    JobDocumentRevision,
    JobStateDigest,
    JobStateDigestTask,
    JobTask,
)

MAX_DIGEST_TASKS = 32
MAX_DIGEST_OUTPUTS = 4
MAX_EXCERPT_CODE_POINTS = 240
MAX_PENDING_IDS = 16

_PLACEHOLDER_HASH = "sha256:" + "0" * 64


def _excerpt(text: str) -> str:
    if len(text) <= MAX_EXCERPT_CODE_POINTS:
        return text
    return text[: MAX_EXCERPT_CODE_POINTS - 1] + "…"


def _digest_task(ordinal: str, task: JobTask) -> JobStateDigestTask:
    return JobStateDigestTask(
        ordinal=ordinal,
        task_id=task.task_id,
        entity_version=task.entity_version,
        statement_excerpt=_excerpt(task.statement),
        output_excerpts=tuple(
            _excerpt(output.statement)
            for output in task.outputs[:MAX_DIGEST_OUTPUTS]
        ),
        omitted_output_count=max(0, len(task.outputs) - MAX_DIGEST_OUTPUTS),
    )


def build_job_state_digest(
    revision: JobDocumentRevision,
    pending_proposals: Sequence[tuple[datetime, UUID]],
    stale_proposal_count: int,
) -> JobStateDigest:
    tasks = revision.snapshot.tasks
    digest_tasks = tuple(
        _digest_task(f"T{index:02d}", task)
        for index, task in enumerate(tasks[:MAX_DIGEST_TASKS], start=1)
    )
    sorted_pending = sorted(pending_proposals, key=lambda pair: (pair[0], pair[1]))
    pending_ids = tuple(proposal_id for _, proposal_id in sorted_pending[:MAX_PENDING_IDS])

    body = dict(
        document_id=revision.document_id,
        session_id=revision.snapshot.session_id,
        revision_id=revision.revision_id,
        revision_number=revision.revision_number,
        revision_hash=revision.snapshot_hash,
        job_title=revision.snapshot.job_title,
        tasks=digest_tasks,
        omitted_task_count=max(0, len(tasks) - MAX_DIGEST_TASKS),
        pending_proposal_ids=pending_ids,
        pending_proposal_count=len(pending_proposals),
        stale_proposal_count=stale_proposal_count,
    )
    provisional = JobStateDigest.model_construct(**body, digest_hash=_PLACEHOLDER_HASH)
    digest_hash = canonical_hash_excluding(provisional, exclude="digest_hash")
    return JobStateDigest(**body, digest_hash=digest_hash)
