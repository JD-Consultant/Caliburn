"""Durable employee authoring use cases for one local Current JD."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.job_analysis.domain import (
    CurrentWorkModel,
    JdTask,
    JdTaskFields,
    OpenIssue,
    OpenIssueKind,
    Proposal,
    ProposalStatus,
    SourceAnchor,
    SourceKind,
    SourceRef,
    Task,
    TaskId,
)

from .persistence import (
    DIRECT_EDIT_SCHEMA_ID,
    DirectEditPayload,
    DocumentRecord,
    DocumentSummary,
    JobAnalysisUnitOfWork,
    JobAnalysisUnitOfWorkFactory,
    JournalEntry,
    LoadedDocument,
)
from .transition import JobAnalysisState


class JobAnalysisApplicationError(RuntimeError):
    pass


class DocumentNotFound(JobAnalysisApplicationError):
    pass


class JdTaskNotFound(JobAnalysisApplicationError):
    pass


class IdempotencyConflict(JobAnalysisApplicationError):
    pass


class ConcurrentAuthorityChange(JobAnalysisApplicationError):
    pass


class InvalidJdTaskOrder(JobAnalysisApplicationError):
    pass


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _task_fields(task: JdTask) -> JdTaskFields:
    return JdTaskFields.model_validate(
        task.model_dump(include=set(JdTaskFields.model_fields))
    )


def _direct_task_id(entry_id: str) -> TaskId:
    return f"direct-{entry_id}"


def _direct_source(entry_id: str) -> SourceRef:
    return SourceRef(kind=SourceKind.DIRECT_EDIT, id=entry_id)


def _require_direct_edit(
    entry: JournalEntry,
    *,
    edit_kind: str,
) -> DirectEditPayload:
    if entry.kind != "direct_edit" or not isinstance(
        entry.payload,
        DirectEditPayload,
    ):
        raise IdempotencyConflict(
            f"entry {entry.entry_id!r} already belongs to another operation"
        )
    if entry.payload.edit_kind != edit_kind:
        raise IdempotencyConflict(
            f"entry {entry.entry_id!r} already records "
            f"{entry.payload.edit_kind!r}"
        )
    return entry.payload


def _reconciled_work_model(
    work_model: CurrentWorkModel,
    *,
    task_id: TaskId,
    entry_id: str,
    summary: str,
    keep_missing_task_issue: bool = True,
) -> CurrentWorkModel:
    source = _direct_source(entry_id)
    issue_id = f"direct-task-{task_id}"
    remaining_issues = tuple(
        issue
        for issue in work_model.open_issues
        if issue.id != issue_id and issue.reconciliation_task_id != task_id
    )
    tasks: list[Task] = []
    matched_active = False
    for task in work_model.tasks:
        if task.task_id == task_id and task.retirement is None:
            tasks.append(
                Task.model_validate(
                    {
                        **task.model_dump(),
                        "pending_reconciliation": source.model_dump(),
                    }
                )
            )
            matched_active = True
        else:
            tasks.append(task)
    if matched_active:
        return CurrentWorkModel(
            tasks=tuple(tasks),
            open_issues=remaining_issues,
            excluded_signals=work_model.excluded_signals,
        )

    if not keep_missing_task_issue:
        return CurrentWorkModel(
            tasks=tuple(tasks),
            open_issues=remaining_issues,
            excluded_signals=work_model.excluded_signals,
        )
    issue = OpenIssue(
        id=issue_id,
        kind=OpenIssueKind.INSUFFICIENT_EVIDENCE,
        summary=summary,
        source_anchors=(SourceAnchor(source_ref=source),),
        reconciliation_task_id=task_id,
    )
    return CurrentWorkModel(
        tasks=tuple(tasks),
        open_issues=(*remaining_issues, issue),
        excluded_signals=work_model.excluded_signals,
    )


def _stale_related_proposals(
    proposals: tuple[Proposal, ...],
    *,
    affected_task_ids: frozenset[TaskId],
) -> tuple[Proposal, ...]:
    result: list[Proposal] = []
    for proposal in proposals:
        should_stale = (
            proposal.status
            in {
                ProposalStatus.PENDING,
                ProposalStatus.DEFERRED,
            }
            and bool(affected_task_ids & set(proposal.affected_task_ids))
        )
        if not should_stale:
            result.append(proposal)
            continue
        result.append(
            Proposal.model_validate(
                {
                    **proposal.model_dump(),
                    "status": ProposalStatus.STALE,
                    "stale_reason": "Current JD 已由員工直接修改，舊提案不再適用。",
                }
            )
        )
    return tuple(result)


async def _locked_document(
    uow: JobAnalysisUnitOfWork,
    document_id: UUID,
) -> DocumentRecord:
    record = await uow.documents.get(document_id, for_update=True)
    if record is None:
        raise DocumentNotFound(f"document {document_id} was not found")
    return record


async def _commit_direct_edit(
    uow: JobAnalysisUnitOfWork,
    *,
    record: DocumentRecord,
    tasks: tuple[JdTask, ...],
    proposals: tuple[Proposal, ...],
    work_model: CurrentWorkModel,
    entry_id: str,
    payload: DirectEditPayload,
) -> None:
    now = _utcnow()
    await uow.tasks.replace(record.document_id, tasks)
    await uow.proposals.replace(record.document_id, proposals)
    await uow.journal.add(
        JournalEntry(
            document_id=record.document_id,
            entry_id=entry_id,
            kind="direct_edit",
            payload_schema_id=DIRECT_EDIT_SCHEMA_ID,
            payload=payload,
            created_at=now,
        )
    )
    updated = await uow.documents.update_authority(
        record.document_id,
        expected_generation=record.authority_generation,
        work_model=work_model,
        active_question=record.active_question,
        updated_at=now,
    )
    if not updated:
        raise ConcurrentAuthorityChange(
            f"document {record.document_id} authority changed concurrently"
        )
    await uow.commit()


async def create_document(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
    title: str,
) -> DocumentRecord:
    async with uow_factory() as uow:
        existing = await uow.documents.get(document_id, for_update=True)
        if existing is not None:
            if existing.title != title:
                raise IdempotencyConflict(
                    f"document {document_id} already exists with another title"
                )
            return existing
        now = _utcnow()
        record = DocumentRecord(
            document_id=document_id,
            title=title,
            work_model=CurrentWorkModel(),
            active_question=None,
            authority_generation=0,
            created_at=now,
            updated_at=now,
        )
        await uow.documents.create(record)
        await uow.commit()
        return record


async def list_documents(
    uow_factory: JobAnalysisUnitOfWorkFactory,
) -> tuple[DocumentSummary, ...]:
    async with uow_factory() as uow:
        return await uow.documents.list()


async def load_document(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    document_id: UUID,
) -> LoadedDocument | None:
    async with uow_factory() as uow:
        record = await uow.documents.get(document_id)
        if record is None:
            return None
        tasks = await uow.tasks.list(document_id)
        proposals = await uow.proposals.list(document_id)
        turns = await uow.journal.list_recent_turns(document_id, limit=None)
        return LoadedDocument(
            document=record,
            state=JobAnalysisState(
                work_model=record.work_model,
                current_jd=tasks,
                proposals=proposals,
            ),
            recent_turns=turns,
        )


async def add_jd_task(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
    entry_id: str,
    fields: JdTaskFields,
) -> JdTask:
    task_id = _direct_task_id(entry_id)
    async with uow_factory() as uow:
        record = await _locked_document(uow, document_id)
        existing_entry = await uow.journal.get(document_id, entry_id)
        if existing_entry is not None:
            payload = _require_direct_edit(existing_entry, edit_kind="add")
            if (
                payload.task_id != task_id
                or payload.after is None
                or _task_fields(payload.after) != fields
            ):
                raise IdempotencyConflict(
                    f"entry {entry_id!r} was replayed with another add payload"
                )
            return payload.after

        tasks = await uow.tasks.list(document_id)
        if any(task.task_id == task_id for task in tasks):
            raise IdempotencyConflict(f"generated task id {task_id!r} already exists")
        created = JdTask(
            **fields.model_dump(),
            task_id=task_id,
            display_order=max(
                (task.display_order for task in tasks),
                default=-1,
            )
            + 1,
        )
        proposals = await uow.proposals.list(document_id)
        work_model = _reconciled_work_model(
            record.work_model,
            task_id=task_id,
            entry_id=entry_id,
            summary=created.statement,
        )
        await _commit_direct_edit(
            uow,
            record=record,
            tasks=(*tasks, created),
            proposals=_stale_related_proposals(
                proposals,
                affected_task_ids=frozenset({task_id}),
            ),
            work_model=work_model,
            entry_id=entry_id,
            payload=DirectEditPayload(
                edit_kind="add",
                task_id=task_id,
                after=created,
            ),
        )
        return created


async def edit_jd_task(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
    entry_id: str,
    task_id: TaskId,
    fields: JdTaskFields,
) -> JdTask:
    async with uow_factory() as uow:
        record = await _locked_document(uow, document_id)
        existing_entry = await uow.journal.get(document_id, entry_id)
        if existing_entry is not None:
            payload = _require_direct_edit(existing_entry, edit_kind="edit")
            if (
                payload.task_id != task_id
                or payload.after is None
                or _task_fields(payload.after) != fields
            ):
                raise IdempotencyConflict(
                    f"entry {entry_id!r} was replayed with another edit payload"
                )
            return payload.after

        tasks = await uow.tasks.list(document_id)
        existing = next((task for task in tasks if task.task_id == task_id), None)
        if existing is None:
            raise JdTaskNotFound(f"JD task {task_id!r} was not found")
        edited = JdTask(
            **fields.model_dump(),
            task_id=task_id,
            display_order=existing.display_order,
        )
        next_tasks = tuple(
            edited if task.task_id == task_id else task
            for task in tasks
        )
        proposals = await uow.proposals.list(document_id)
        work_model = _reconciled_work_model(
            record.work_model,
            task_id=task_id,
            entry_id=entry_id,
            summary=edited.statement,
        )
        await _commit_direct_edit(
            uow,
            record=record,
            tasks=next_tasks,
            proposals=_stale_related_proposals(
                proposals,
                affected_task_ids=frozenset({task_id}),
            ),
            work_model=work_model,
            entry_id=entry_id,
            payload=DirectEditPayload(
                edit_kind="edit",
                task_id=task_id,
                after=edited,
            ),
        )
        return edited


async def delete_jd_task(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
    entry_id: str,
    task_id: TaskId,
) -> None:
    async with uow_factory() as uow:
        record = await _locked_document(uow, document_id)
        existing_entry = await uow.journal.get(document_id, entry_id)
        if existing_entry is not None:
            payload = _require_direct_edit(existing_entry, edit_kind="delete")
            if payload.task_id != task_id:
                raise IdempotencyConflict(
                    f"entry {entry_id!r} was replayed for another task"
                )
            return

        tasks = await uow.tasks.list(document_id)
        existing = next((task for task in tasks if task.task_id == task_id), None)
        if existing is None:
            raise JdTaskNotFound(f"JD task {task_id!r} was not found")
        proposals = await uow.proposals.list(document_id)
        work_model = _reconciled_work_model(
            record.work_model,
            task_id=task_id,
            entry_id=entry_id,
            summary=existing.statement,
            keep_missing_task_issue=False,
        )
        await _commit_direct_edit(
            uow,
            record=record,
            tasks=tuple(task for task in tasks if task.task_id != task_id),
            proposals=_stale_related_proposals(
                proposals,
                affected_task_ids=frozenset({task_id}),
            ),
            work_model=work_model,
            entry_id=entry_id,
            payload=DirectEditPayload(
                edit_kind="delete",
                task_id=task_id,
                after=None,
            ),
        )


async def reorder_jd_tasks(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
    entry_id: str,
    ordered_task_ids: tuple[TaskId, ...],
) -> tuple[JdTask, ...]:
    async with uow_factory() as uow:
        record = await _locked_document(uow, document_id)
        existing_entry = await uow.journal.get(document_id, entry_id)
        tasks = await uow.tasks.list(document_id)
        by_id = {task.task_id: task for task in tasks}
        if existing_entry is not None:
            payload = _require_direct_edit(existing_entry, edit_kind="reorder")
            if payload.ordered_task_ids != ordered_task_ids:
                raise IdempotencyConflict(
                    f"entry {entry_id!r} was replayed with another order"
                )
            if set(ordered_task_ids) != set(by_id):
                raise IdempotencyConflict(
                    "the reordered Task set changed after the original request"
                )
            return tuple(
                JdTask.model_validate(
                    {
                        **by_id[task_id].model_dump(),
                        "display_order": index,
                    }
                )
                for index, task_id in enumerate(ordered_task_ids)
            )

        if len(set(ordered_task_ids)) != len(ordered_task_ids):
            raise InvalidJdTaskOrder("ordered_task_ids must be distinct")
        if set(ordered_task_ids) != set(by_id):
            raise InvalidJdTaskOrder(
                "ordered_task_ids must cover exactly the Current JD Tasks"
            )
        reordered = tuple(
            JdTask.model_validate(
                {
                    **by_id[task_id].model_dump(),
                    "display_order": index,
                }
            )
            for index, task_id in enumerate(ordered_task_ids)
        )
        proposals = await uow.proposals.list(document_id)
        await _commit_direct_edit(
            uow,
            record=record,
            tasks=reordered,
            proposals=_stale_related_proposals(
                proposals,
                affected_task_ids=frozenset(ordered_task_ids),
            ),
            work_model=record.work_model,
            entry_id=entry_id,
            payload=DirectEditPayload(
                edit_kind="reorder",
                task_id=None,
                after=None,
                ordered_task_ids=ordered_task_ids,
            ),
        )
        return reordered
