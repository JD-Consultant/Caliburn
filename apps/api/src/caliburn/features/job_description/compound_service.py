"""JD 複合用例在呼叫者交易內只保存最終修訂；重播直接承接原結果。"""

from typing import cast
from uuid import UUID, uuid4

from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import (
    area_persistence,
    capability_persistence,
    collaborator_persistence,
    condition_persistence,
    persistence,
    revision_editing,
    source_persistence,
    task_persistence,
    work_queries,
)
from caliburn.features.job_description.areas import ResponsibilityArea
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.capabilities import Capability
from caliburn.features.job_description.collaborators import Collaborator
from caliburn.features.job_description.compound_changes import (
    apply_compound_changes,
    compound_effect,
)
from caliburn.features.job_description.compound_edits import (
    CompoundItem,
    CompoundJdEdit,
    CreateItemWithSources,
    CreateTaskWithSources,
    JdCompoundEditResult,
    JdEditEffect,
    ReviseProfileWithSources,
)
from caliburn.features.job_description.conditions import JobCondition
from caliburn.features.job_description.models import (
    JdProfileRevision,
    StaleJdRevisionError,
)
from caliburn.features.job_description.navigation import jd_read_ref, resolve_jd_read_ref
from caliburn.features.job_description.tasks import TaskDetail, WorkTask

_COMMAND: TypeAdapter[CompoundJdEdit] = TypeAdapter(CompoundJdEdit)


async def _insert_content(
    session: AsyncSession, job_file_id: UUID, item: CompoundItem | None
) -> None:
    match item:
        case ResponsibilityArea():
            await area_persistence.insert_area_content(session, job_file_id, item)
        case WorkTask():
            await task_persistence.insert_task_content(session, job_file_id, item)
        case Capability():
            await capability_persistence.insert_capability_content(session, job_file_id, item)
        case Collaborator():
            await collaborator_persistence.insert_collaborator_content(session, job_file_id, item)
        case JobCondition():
            await condition_persistence.insert_condition_content(session, job_file_id, item)


async def apply_compound_edit(
    session: AsyncSession,
    job_file_id: UUID,
    command: CompoundJdEdit,
    *,
    candidate: JdCandidateScope,
) -> JdCompoundEditResult:
    """呼叫者先鎖檔案、writer 與 open candidate；本函式不 commit。

    意圖衝突及過期版本沿既有領域錯誤；後段保存失敗交外層完整回滾。
    原結果查詢早於版本檢查，避免提交結果不明重播覆蓋後續候選。
    """
    match command:
        case ReviseProfileWithSources():
            kind = "profile"
        case CreateTaskWithSources():
            kind = "task"
        case CreateItemWithSources():
            kind = "item_creation"
        case _:
            kind = "item_revision"
    payload = {"version": 1, "kind": kind, "value": _COMMAND.dump_python(command, mode="json")}
    original = await revision_editing.read_edit_operation(
        session, job_file_id, command.command_id, candidate
    )
    if original is not None:
        revision_editing.require_matching_edit_intent(
            original,
            kind="compound_edit",
            expected_revision_id=command.expected_revision_id,
            request_payload=payload,
        )
        metadata = original.result_payload
        if not isinstance(metadata, dict) or metadata.get("effect") not in {
            "created",
            "updated",
            "aligned",
            "unchanged",
        }:
            raise RuntimeError("Stored compound JD result is invalid")
        effect = cast(JdEditEffect, metadata["effect"])
        if (effect == "created") != (metadata.get("created_ref") is not None):
            raise RuntimeError("Stored compound JD result has an inconsistent created identity")
        created = None
        if metadata.get("created_ref") is not None:
            if not isinstance(metadata["created_ref"], str):
                raise RuntimeError("Stored compound JD item reference is invalid")
            work = await work_queries.read_work_at(
                session, job_file_id, original.result_revision_id
            )
            item = resolve_jd_read_ref(work, metadata["created_ref"])
            if isinstance(item, TaskDetail):
                raise RuntimeError("Compound creation cannot return a standalone detail")
            created = item
        return JdCompoundEditResult(original.result_revision_id, effect, created)
    current = await revision_editing.read_edit_revision(session, job_file_id, candidate)
    if current != command.expected_revision_id:
        raise StaleJdRevisionError("Read the current JD before submitting a new edit")
    profile = await persistence.read_revision(session, job_file_id, current)
    work = await work_queries.read_work_at(session, job_file_id, current)
    references = await source_persistence.read_source_references(session, job_file_id, current)
    changes = apply_compound_changes(profile.profile, work, references, command)
    changed = (
        changes.profile != profile.profile
        or changes.work != work
        or changes.references != references
    )
    revision = current
    if changed:
        revision = uuid4()
        await _insert_content(session, job_file_id, changes.changed_content)
        await persistence.insert_revision(
            session,
            job_file_id,
            JdProfileRevision(revision, changes.profile),
            parent_revision_id=current,
            areas=changes.work.areas,
            tasks=changes.work.tasks,
            capabilities=changes.work.capabilities,
            task_links=changes.work.task_links,
            collaborators=changes.work.collaborators,
            conditions=changes.work.conditions,
        )
    effect = compound_effect(command, changed=changed)
    await revision_editing.record_edit(
        session,
        job_file_id,
        command_id=command.command_id,
        kind="compound_edit",
        expected_revision_id=current,
        result_revision_id=revision,
        request_payload=payload,
        candidate=candidate,
        source_references=changes.references,
        result_payload={
            "effect": effect,
            "created_ref": jd_read_ref(changes.created_item)
            if changes.created_item is not None
            else None,
        },
    )
    return JdCompoundEditResult(revision, effect, changes.created_item)
