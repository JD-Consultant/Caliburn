"""唯讀回復舊 checkpoint 的確定性子操作；不能以回復缺口建立新結果。"""

from uuid import UUID, uuid5

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import persistence, revision_editing, work_queries
from caliburn.features.job_description.areas import (
    CreateArea,
    EditJdAreas,
    ReviseArea,
    area_change_payload,
)
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.capabilities import (
    CreateCapability,
    EditJdCapabilities,
    ReviseCapability,
    SetTaskCapability,
)
from caliburn.features.job_description.capability_changes import capability_change_payload
from caliburn.features.job_description.collaborators import (
    CreateCollaborator,
    EditJdCollaborators,
    ReviseCollaborator,
    collaborator_change_payload,
)
from caliburn.features.job_description.compound_changes import (
    added_detail_sources,
    compound_effect,
    item_source_target,
    task_source_groups,
)
from caliburn.features.job_description.compound_edits import (
    BoundItemSources,
    CompoundItem,
    CompoundJdEdit,
    CreateItemWithSources,
    CreateTaskWithSources,
    ItemContentRevision,
    ItemCreation,
    JdCompoundEditResult,
    ReviseProfileWithSources,
)
from caliburn.features.job_description.conditions import EditJdConditions, condition_change_payload
from caliburn.features.job_description.models import (
    JdCommandConflictError,
    ProfileField,
    ReviseJdProfile,
    profile_change_payload,
)
from caliburn.features.job_description.navigation import jd_read_ref
from caliburn.features.job_description.source_changes import source_change_payload
from caliburn.features.job_description.sources import (
    AddJdSource,
    JdSourceTarget,
    ReviseJdSources,
    SourceTargetKind,
)
from caliburn.features.job_description.task_changes import task_edit_payload
from caliburn.features.job_description.tasks import EditJdTasks, ReviseTask, WorkTask
from caliburn.features.job_description.work_queries import JdWorkRevision

type LegacyEdit = (
    ReviseJdProfile
    | EditJdAreas
    | EditJdTasks
    | EditJdCapabilities
    | EditJdCollaborators
    | EditJdConditions
    | ReviseJdSources
)


def content_command(
    command_id: UUID, revision: UUID, content: ItemCreation | ItemContentRevision
) -> LegacyEdit:
    match content:
        case CreateArea() | ReviseArea():
            return EditJdAreas(command_id, revision, content)
        case ReviseTask():
            return EditJdTasks(command_id, revision, content)
        case CreateCapability() | ReviseCapability():
            return EditJdCapabilities(command_id, revision, content)
        case CreateCollaborator() | ReviseCollaborator():
            return EditJdCollaborators(command_id, revision, content)
        case _:
            return EditJdConditions(command_id, revision, content)


def _intent(command: LegacyEdit) -> tuple[str, object]:
    if isinstance(command, ReviseJdProfile):
        return "revise_profile", profile_change_payload(command.changes)
    if isinstance(command, ReviseJdSources):
        return "edit_sources", source_change_payload(command)
    if isinstance(command, EditJdAreas):
        return "edit_areas", area_change_payload(command.change)
    if isinstance(command, EditJdTasks):
        return "edit_tasks", task_edit_payload(command.change)
    if isinstance(command, EditJdCapabilities):
        return "edit_capabilities", capability_change_payload(command.change)
    if isinstance(command, EditJdCollaborators):
        return "edit_collaborators", collaborator_change_payload(command.change)
    return "edit_conditions", condition_change_payload(command.change)


def _first_step(command: CompoundJdEdit) -> str:
    if isinstance(command, CreateTaskWithSources):
        return "task"
    if isinstance(command, CreateItemWithSources):
        return "item"
    if isinstance(command, ReviseProfileWithSources):
        return "profile_text" if command.changes else f"profile_source:{command.sources[0].field}"
    if command.content is not None:
        return "content"
    return "capability:0" if command.capabilities else "source:0"


async def _read_named_steps(
    session: AsyncSession,
    job_file_id: UUID,
    command_id: UUID,
    candidate: JdCandidateScope,
    names: tuple[str, ...],
) -> set[UUID]:
    originals = await persistence.read_operations(
        session, job_file_id, tuple(uuid5(command_id, name) for name in names)
    )
    for original in originals:
        # 同一 Session 已載入這批列；沿既有規則核 scope，不另造資格判斷。
        await revision_editing.read_edit_operation(
            session, job_file_id, original.command_id, candidate
        )
    return {original.command_id for original in originals}


def _created(before: JdWorkRevision, after: JdWorkRevision) -> CompoundItem:
    def items(work: JdWorkRevision) -> tuple[CompoundItem, ...]:
        return (*work.areas, *work.tasks, *work.capabilities, *work.collaborators, *work.conditions)

    previous = {jd_read_ref(item) for item in items(before)}
    created = [item for item in items(after) if jd_read_ref(item) not in previous]
    if len(created) != 1:
        raise RuntimeError("Original legacy operation must identify exactly one created item")
    return created[0]


async def recover_legacy_compound(
    session: AsyncSession,
    job_file_id: UUID,
    command: CompoundJdEdit,
    *,
    candidate: JdCandidateScope,
) -> JdCompoundEditResult | None:
    """完整核對原子操作鏈；存在首筆即必須取得全部原結果，絕不補寫或倒轉 head。"""
    known = await _read_named_steps(
        session,
        job_file_id,
        command.command_id,
        candidate,
        (
            "profile_text",
            *(f"profile_source:{field}" for field in ProfileField),
            "task",
            "item",
            "sources",
            "content",
            "capability:0",
            "source:0",
        ),
    )
    if not known:
        return None
    if uuid5(command.command_id, _first_step(command)) not in known:
        raise JdCommandConflictError("command_id belongs to a different legacy JD intent")
    revision = command.expected_revision_id
    covered: set[UUID] = set()

    async def read_step(edit: LegacyEdit) -> UUID:
        original = await revision_editing.read_edit_operation(
            session, job_file_id, edit.command_id, candidate
        )
        if original is None:
            raise RuntimeError("An atomic legacy JD operation has missing suboperations")
        kind, payload = _intent(edit)
        if (
            original.kind != kind
            or original.expected_revision_id != edit.expected_revision_id
            or original.request_payload != payload
        ):
            raise JdCommandConflictError("command_id was used with different legacy JD intent")
        covered.add(original.command_id)
        return original.result_revision_id

    created = None
    if isinstance(command, ReviseProfileWithSources):
        if command.changes:
            revision = await read_step(
                ReviseJdProfile(
                    uuid5(command.command_id, "profile_text"), revision, command.changes
                )
            )
        for profile_group in command.sources:
            revision = await read_step(
                ReviseJdSources(
                    uuid5(command.command_id, f"profile_source:{profile_group.field}"),
                    revision,
                    JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=profile_group.field),
                    profile_group.changes,
                )
            )
    elif isinstance(command, CreateTaskWithSources | CreateItemWithSources):
        before = await work_queries.read_work_at(session, job_file_id, revision)
        edit = (
            EditJdTasks(uuid5(command.command_id, "task"), revision, command.task)
            if isinstance(command, CreateTaskWithSources)
            else content_command(uuid5(command.command_id, "item"), revision, command.item)
        )
        revision = await read_step(edit)
        after = await work_queries.read_work_at(session, job_file_id, revision)
        created = _created(before, after)
        if isinstance(command, CreateTaskWithSources):
            if not isinstance(created, WorkTask):
                raise RuntimeError("Legacy task creation did not create a task")
            for capability in command.capabilities:
                revision = await read_step(
                    EditJdCapabilities(
                        uuid5(command.command_id, f"link:{capability.capability_id}"),
                        revision,
                        SetTaskCapability(created.task_id, capability.capability_id, True),
                    )
                )
            for index, group in enumerate(task_source_groups(created, command)):
                if group.changes:
                    revision = await read_step(
                        ReviseJdSources(
                            uuid5(command.command_id, f"source:{index}"),
                            revision,
                            group.target,
                            group.changes,
                        )
                    )
            # 建立任務的來源索引會跳過空來源，不能只查下一個 index。
            # 原 task 修訂及原可合法連結的能力，界定全部衍生 link/source 的有限範圍。
            original_links = await _read_named_steps(
                session,
                job_file_id,
                command.command_id,
                candidate,
                tuple(f"link:{item.capability_id}" for item in before.capabilities),
            )
            known.update(original_links)
            known.update(
                await _read_named_steps(
                    session,
                    job_file_id,
                    command.command_id,
                    candidate,
                    tuple(
                        f"source:{index}"
                        for index in range(1 + len(created.details) + len(original_links))
                    ),
                )
            )
        elif command.sources:
            revision = await read_step(
                ReviseJdSources(
                    uuid5(command.command_id, "sources"),
                    revision,
                    item_source_target(created),
                    tuple(AddJdSource(s) for s in command.sources),
                )
            )
        if isinstance(command, CreateItemWithSources):
            known.update(
                await _read_named_steps(
                    session, job_file_id, command.command_id, candidate, ("sources",)
                )
            )
    else:
        if command.content is not None:
            revision = await read_step(
                content_command(uuid5(command.command_id, "content"), revision, command.content)
            )
        details: tuple[BoundItemSources, ...] = ()
        if command.added_details:
            before = await work_queries.read_work_at(
                session, job_file_id, command.expected_revision_id
            )
            after = await work_queries.read_work_at(session, job_file_id, revision)
            details = added_detail_sources(before, after, command)
        for index, change in enumerate(command.capabilities):
            revision = await read_step(
                EditJdCapabilities(
                    uuid5(command.command_id, f"capability:{index}"), revision, change
                )
            )
        for index, group in enumerate((*command.sources, *details)):
            revision = await read_step(
                ReviseJdSources(
                    uuid5(command.command_id, f"source:{index}"),
                    revision,
                    group.target,
                    group.changes,
                )
            )
        # 舊修訂的 capability/source loop 連續編號，no-op 也保存 operation。
        # 已核前綴之外仍有下一筆，即代表此次意圖省略原尾段；不能回傳中間稿。
        known.update(
            await _read_named_steps(
                session,
                job_file_id,
                command.command_id,
                candidate,
                (
                    f"capability:{len(command.capabilities)}",
                    f"source:{len(command.sources) + len(details)}",
                ),
            )
        )
    if known - covered:
        raise JdCommandConflictError("The legacy JD intent omits original suboperations")
    return JdCompoundEditResult(
        revision,
        compound_effect(command, changed=revision != command.expected_revision_id),
        created,
    )
