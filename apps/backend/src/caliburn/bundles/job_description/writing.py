"""將有界模型意圖交給一次 JD Application 用例，不在 Bundle 實作交易。"""

from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, TypedDict, assert_never
from uuid import UUID

from pydantic import BaseModel

from caliburn.bundles.job_description import write_inputs as wire
from caliburn.bundles.job_description.projection import reference_targets
from caliburn.modules.job_description.application import (
    collaborations,
    conditions,
    duties,
    job_descriptions,
    knowledge,
    skills,
)
from caliburn.modules.job_description.application.citation_inputs import (
    AddCitationInput,
    CitationChange,
    ConfirmCitationInput,
    EditingActor,
    RemoveCitationInput,
)
from caliburn.modules.job_description.application.content import TaskResult
from caliburn.modules.job_description.application.errors import (
    InvalidCitationSourceError,
    InvalidJobDescriptionInputError,
    InvalidTaskReferenceError,
    JobDescriptionConcurrencyError,
    JobDescriptionNotFoundError,
)
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.application.persistence import (
    JobDescriptionUnitOfWork,
)
from caliburn.modules.job_description.application.queries import JobDescriptionQueries
from caliburn.modules.job_description.application.tasks import inputs as task_input
from caliburn.modules.job_description.application.tasks.lifecycle import (
    add_task,
    delete_task,
    update_task,
)
from caliburn.modules.job_description.domain.models.citation import (
    InterviewReference,
    MemoryReference,
    SourceReference,
)
from caliburn.modules.job_description.domain.models.condition_kind import ConditionKind
from caliburn.modules.memory.application.persistence import MemoryQueries
from caliburn.modules.model_references.contracts import (
    ModelReferences,
    ReferenceTarget,
    ResourceKind,
)

_DUTY_KINDS: tuple[ResourceKind, ...] = ("duty",)


class RevisionFieldError(ValueError):
    """Bundle 已知欄位規則的拒絕位置，不保存或轉述輸入正文。"""

    def __init__(
        self,
        *,
        location: str,
        field: str,
        reason: Literal["unsupported_field", "duplicate_field"],
        allowed_fields: tuple[str, ...] = (),
    ) -> None:
        self.location = location
        self.field = field
        self.reason = reason
        self.allowed_fields = allowed_fields
        super().__init__("JD 工具欄位修改遭拒絕")


class ReferenceKindError(ValueError):
    """保留已解析短碼與此操作接受的種類，供工具沿原參數定位。"""

    def __init__(self, reference: str, allowed_kinds: Collection[ResourceKind]) -> None:
        self.reference = reference
        self.allowed_kinds = tuple(allowed_kinds)
        super().__init__("定位種類不適用此操作")


class WriteParameters(TypedDict):
    workspace_id: UUID
    job_description_id: UUID
    expected_version: int
    correlation_id: str
    uow_factory: Callable[[], JobDescriptionUnitOfWork]
    actor: EditingActor


@dataclass(frozen=True)
class WriteContext:
    """單次工具的 scoped 觀察；Application 再鎖根核同一原版本。"""

    snapshot: JobDescriptionResult
    resolved: Mapping[str, ReferenceTarget]
    parameters: WriteParameters
    memory_queries: MemoryQueries | None = None
    memory_published_version: int | None = None

    def target(self, ref: str, kinds: Collection[ResourceKind]) -> ReferenceTarget:
        target = self.resolved[ref]
        if target.resource_kind not in kinds:
            raise ReferenceKindError(ref, kinds)
        if target not in reference_targets(self.snapshot):
            raise InvalidTaskReferenceError("定位不在目前 JD")
        return target

    def task(self, target: ReferenceTarget) -> TaskResult:
        for task in self.snapshot.tasks:
            if task.id == target.resource_id:
                return task
        raise InvalidTaskReferenceError("找不到任務")

    def detail_owner(self, target: ReferenceTarget) -> TaskResult:
        for task in self.snapshot.tasks:
            details = (
                task.outcomes
                if target.resource_kind == "outcome"
                else task.requirements
            )
            if any(detail.id == target.resource_id for detail in details):
                return task
        raise InvalidTaskReferenceError("找不到明細所屬任務")

    def input_fields(self) -> dict[str, object]:
        return {
            "job_description_id": self.snapshot.job_description_id,
            "expected_version": self.parameters["expected_version"],
            "correlation_id": self.parameters["correlation_id"],
        }


def load_write_context(
    *,
    workspace_id: UUID,
    job_description_id: UUID,
    expected_version: int,
    turn_id: UUID,
    queries: JobDescriptionQueries,
    references: ModelReferences,
    uow_factory: Callable[[], JobDescriptionUnitOfWork],
    refs: Collection[str],
    memory_queries: MemoryQueries | None = None,
    memory_published_version: int | None = None,
) -> WriteContext:
    snapshot = queries.get_job_description(
        workspace_id=workspace_id, job_description_id=job_description_id
    )
    if snapshot is None:
        raise JobDescriptionNotFoundError("JD 不存在")
    if (
        snapshot.workspace_id != workspace_id
        or snapshot.job_description_id != job_description_id
    ):
        raise JobDescriptionNotFoundError("JD 不屬於此範圍")
    if snapshot.version != expected_version:
        raise JobDescriptionConcurrencyError("模型已見版本已過期")
    return WriteContext(
        snapshot=snapshot,
        resolved=references.resolve_refs(workspace_id, refs),
        parameters={
            "workspace_id": workspace_id,
            "job_description_id": job_description_id,
            "expected_version": expected_version,
            "correlation_id": str(turn_id),
            "uow_factory": uow_factory,
            "actor": "consultant",
        },
        memory_queries=memory_queries,
        memory_published_version=memory_published_version,
    )


def collect_reference_paths(
    **values: str | BaseModel | Sequence[BaseModel] | None,
) -> dict[str, tuple[str, ...]]:
    """收集已定義定位欄位的所有位置；正文內形似短碼的文字維持原樣。"""
    selected: dict[str, list[str]] = {}

    def collect(value: str | BaseModel | Sequence[BaseModel] | None, path: str) -> None:
        if value is None:
            return
        if isinstance(value, str):
            selected.setdefault(value, []).append(path)
            return
        if not isinstance(value, BaseModel):
            for index, item in enumerate(value):
                collect(item, f"{path}[{index}]")
            return
        for field in (
            "parent_read_ref",
            "capability_read_ref",
            "detail_read_ref",
            "before_read_ref",
            "message_ref",
            "citation_ref",
            "duty_read_ref",
        ):
            ref = getattr(value, field, None)
            if isinstance(ref, str):
                selected.setdefault(ref, []).append(f"{path}.{field}")
        if isinstance(value, wire.AddSource):
            collect(value.source, f"{path}.source")
        elif isinstance(value, wire.SourceInput):
            collect(value.supporting_sources, f"{path}.supporting_sources")

    for path, value in values.items():
        collect(value, path)
    return {ref: tuple(paths) for ref, paths in selected.items()}


def needs_memory(values: Sequence[BaseModel]) -> bool:
    for value in values:
        if isinstance(value, wire.MemorySource):
            return True
        if isinstance(value, wire.AddSource) and isinstance(
            value.source, wire.MemorySource
        ):
            return True
        if isinstance(value, wire.SourceInput) and needs_memory(
            value.supporting_sources
        ):
            return True
    return False


def _source(context: WriteContext, source: wire.Source) -> SourceReference:
    workspace_id = context.parameters["workspace_id"]
    if isinstance(source, wire.InterviewSource):
        target = context.resolved[source.message_ref]
        if target.resource_kind != "message":
            raise InvalidCitationSourceError("訪談來源種類錯誤")
        return InterviewReference(
            workspace_id=workspace_id, message_id=target.resource_id
        )
    version = context.memory_published_version
    if version is None or context.memory_queries is None:
        raise InvalidCitationSourceError("本輪沒有固定 Memory 發布版")
    snapshot = context.memory_queries.get_published(
        workspace_id=workspace_id, published_version=version
    )
    if (
        snapshot is None
        or snapshot.workspace_id != workspace_id
        or snapshot.version != version
    ):
        raise InvalidCitationSourceError("固定 Memory 發布版不存在")
    kind = "situation" if source.kind == "work_situation" else "understanding"
    item = next(
        (
            item
            for item in snapshot.items
            if item.kind == kind and item.content.title == source.target_title
        ),
        None,
    )
    if item is None:
        raise InvalidCitationSourceError("固定發布版沒有此完整標題")
    return MemoryReference(
        workspace_id=workspace_id, published_version=version, item_id=item.id
    )


def _citations(
    context: WriteContext, changes: Sequence[wire.SourceChange]
) -> tuple[CitationChange, ...]:
    results: list[CitationChange] = []
    selected: set[SourceReference | UUID] = set()
    for change in changes:
        if isinstance(change, wire.AddSource):
            source = _source(context, change.source)
            if source in selected:
                raise InvalidJobDescriptionInputError("同一來源不可重複新增")
            selected.add(source)
            results.append(AddCitationInput(source=source))
        else:
            target = context.resolved[change.citation_ref]
            if target.resource_kind != "citation" or not any(
                item.id == target.resource_id for item in context.snapshot.citations
            ):
                raise InvalidTaskReferenceError("引用不屬於目前 JD")
            if target.resource_id in selected:
                raise InvalidJobDescriptionInputError("同一引用不可重複或矛盾修改")
            selected.add(target.resource_id)
            version = None
            if isinstance(change, wire.ConfirmSource):
                citation = next(
                    item
                    for item in context.snapshot.citations
                    if item.id == target.resource_id
                )
                if isinstance(citation.source, MemoryReference):
                    version = context.memory_published_version
                    if version is None:
                        raise InvalidCitationSourceError("本輪沒有固定 Memory 發布版")
            results.append(
                RemoveCitationInput(citation_id=target.resource_id)
                if isinstance(change, wire.RemoveSource)
                else ConfirmCitationInput(
                    citation_id=target.resource_id, published_version=version
                )
            )
    return tuple(results)


def _new_citations(
    context: WriteContext, sources: Sequence[wire.Source]
) -> tuple[CitationChange, ...]:
    return _citations(
        context,
        [wire.AddSource(action="add_source", source=source) for source in sources],
    )


def create_task(
    context: WriteContext,
    *,
    name: str,
    description: str | None,
    parent_read_ref: str | None,
    competency_level: int | None,
    outcomes: Sequence[wire.TaskDetail],
    requirements: Sequence[wire.TaskDetail],
    required_knowledge: Sequence[wire.Capability],
    required_skills: Sequence[wire.Capability],
    supporting_sources: Sequence[wire.Source] = (),
) -> JobDescriptionResult:
    def definitions(
        values: Sequence[wire.Capability], kind: ResourceKind
    ) -> tuple[task_input.ExistingDefinitionInput | task_input.NewDefinitionInput, ...]:
        return tuple(
            task_input.ExistingDefinitionInput(
                id=context.target(value.capability_read_ref, (kind,)).resource_id
            )
            if isinstance(value, wire.ExistingCapability)
            else task_input.NewDefinitionInput(
                name=value.name, description=value.description
            )
            for value in values
        )

    fields = context.input_fields()
    return add_task(
        workspace_id=context.parameters["workspace_id"],
        input=task_input.AddTaskInput.model_validate(
            {
                **fields,
                "name": name,
                "description": description,
                "duty_id": context.target(parent_read_ref, _DUTY_KINDS).resource_id
                if parent_read_ref is not None
                else None,
                "competency_level": competency_level,
                "outcomes": tuple(item.text for item in outcomes),
                "requirements": tuple(item.text for item in requirements),
                "knowledge": definitions(required_knowledge, "knowledge"),
                "skills": definitions(required_skills, "skill"),
                "citations": _new_citations(context, supporting_sources),
            }
        ),
        uow_factory=context.parameters["uow_factory"],
        actor=context.parameters["actor"],
    )


def create_item(context: WriteContext, item: wire.NewItem) -> JobDescriptionResult:
    citations = _new_citations(context, item.supporting_sources)
    match item:
        case wire.DutyItem():
            return duties.add_duty(
                **context.parameters,
                name=item.name,
                scope=item.scope,
                citations=citations,
            )
        case wire.CapabilityItem(kind="knowledge"):
            return knowledge.add_knowledge(
                **context.parameters,
                name=item.name,
                description=item.description,
                citations=citations,
            )
        case wire.CapabilityItem():
            return skills.add_skill(
                **context.parameters,
                name=item.name,
                description=item.description,
                citations=citations,
            )
        case wire.CollaborationItem():
            return collaborations.add_collaboration(
                **context.parameters,
                collaborator_name=item.collaborator_name,
                scope=item.scope,
                citations=citations,
            )
        case wire.ConditionItem():
            return conditions.add_condition(
                **context.parameters,
                kind=ConditionKind(item.condition_kind),
                text=item.text,
                citations=citations,
            )
        case _:
            assert_never(item)


def _set_field(
    fields: dict[str, object], field: str, value: object, *, location: str
) -> None:
    if field in fields:
        raise RevisionFieldError(
            location=location, field=field, reason="duplicate_field"
        )
    fields[field] = value


def revise_profile(
    context: WriteContext, changes: Sequence[wire.ProfileChange]
) -> JobDescriptionResult:
    fields = context.input_fields()
    citation_changes: list[wire.SourceChange] = []
    for index, change in enumerate(changes):
        if isinstance(change, (wire.AddSource, wire.RemoveSource, wire.ConfirmSource)):
            citation_changes.append(change)
        elif isinstance(change, wire.SetBaselineLevel):
            _set_field(
                fields,
                "baseline_competency_level",
                change.value,
                location=f"changes[{index}].value",
            )
        else:
            _set_field(
                fields,
                change.field,
                change.value if isinstance(change, wire.SetProfileField) else None,
                location=f"changes[{index}].field",
            )
    if citation_changes:
        fields["citations"] = _citations(context, citation_changes)
    return job_descriptions.update_job_description(
        workspace_id=context.parameters["workspace_id"],
        input=job_descriptions.UpdateJobDescriptionInput.model_validate(fields),
        uow_factory=context.parameters["uow_factory"],
        actor=context.parameters["actor"],
    )


_FIELDS: dict[ResourceKind, tuple[str, ...]] = {
    "task": ("name", "description"),
    "duty": ("name", "scope"),
    "knowledge": ("name", "description"),
    "skill": ("name", "description"),
    "collaboration": ("collaborator_name", "scope"),
    "condition": ("text",),
    "outcome": ("text",),
    "requirement": ("text",),
}
_ITEM_KINDS: tuple[ResourceKind, ...] = tuple(_FIELDS)


def _task_change(
    context: WriteContext, task: TaskResult, change: wire.ItemChange
) -> task_input.TaskChange:
    match change:
        case wire.AddDetail(kind="outcome"):
            return task_input.AddOutcomeInput(text=change.text)
        case wire.AddDetail():
            return task_input.AddRequirementInput(text=change.text)
        case wire.ReviseDetail() | wire.RemoveDetail():
            target = context.target(change.detail_read_ref, ("outcome", "requirement"))
            if context.detail_owner(target).id != task.id:
                raise InvalidTaskReferenceError("明細不屬於目標任務")
            if isinstance(change, wire.ReviseDetail):
                return (
                    task_input.UpdateOutcomeInput(
                        id=target.resource_id, text=change.text
                    )
                    if target.resource_kind == "outcome"
                    else task_input.UpdateRequirementInput(
                        id=target.resource_id, text=change.text
                    )
                )
            return (
                task_input.DeleteOutcomeInput(id=target.resource_id)
                if target.resource_kind == "outcome"
                else task_input.DeleteRequirementInput(id=target.resource_id)
            )
        case wire.SetCapability():
            target = context.target(change.capability_read_ref, ("knowledge", "skill"))
            if target.resource_kind == "knowledge":
                return (
                    task_input.LinkKnowledgeInput(id=target.resource_id)
                    if change.relationship == "link"
                    else task_input.UnlinkKnowledgeInput(id=target.resource_id)
                )
            return (
                task_input.LinkSkillInput(id=target.resource_id)
                if change.relationship == "link"
                else task_input.UnlinkSkillInput(id=target.resource_id)
            )
        case wire.CreateCapability(kind="knowledge"):
            return task_input.CreateAndLinkKnowledgeInput(
                name=change.name, description=change.description
            )
        case wire.CreateCapability():
            return task_input.CreateAndLinkSkillInput(
                name=change.name, description=change.description
            )
        case wire.ReorderCapability():
            target = context.target(change.capability_read_ref, ("knowledge", "skill"))
            before = (
                context.target(
                    change.before_read_ref, (target.resource_kind,)
                ).resource_id
                if change.before_read_ref is not None
                else None
            )
            return (
                task_input.MoveKnowledgeReferenceInput(
                    id=target.resource_id, before_id=before
                )
                if target.resource_kind == "knowledge"
                else task_input.MoveSkillReferenceInput(
                    id=target.resource_id, before_id=before
                )
            )
        case _:
            raise InvalidJobDescriptionInputError("此修改動作不適用任務內容")


def _revision_fields(
    context: WriteContext,
    target: ReferenceTarget,
    changes: Iterable[tuple[str, wire.ItemChange]],
) -> dict[str, object]:
    fields = context.input_fields()
    task_changes: list[task_input.TaskChange] = []
    citation_changes: list[wire.SourceChange] = []
    for location, change in changes:
        if isinstance(change, (wire.AddSource, wire.RemoveSource, wire.ConfirmSource)):
            if target.resource_kind in ("outcome", "requirement"):
                raise InvalidJobDescriptionInputError("O/P 來源由所屬 Task 管理")
            citation_changes.append(change)
        elif isinstance(change, (wire.SetField, wire.ClearField)):
            if change.field not in _FIELDS[target.resource_kind]:
                raise RevisionFieldError(
                    location=f"{location}.field",
                    field=change.field,
                    reason="unsupported_field",
                    allowed_fields=_FIELDS[target.resource_kind],
                )
            _set_field(
                fields,
                change.field,
                change.value if isinstance(change, wire.SetField) else None,
                location=f"{location}.field",
            )
        elif (
            isinstance(change, wire.SetCompetencyLevel)
            and target.resource_kind == "task"
        ):
            _set_field(
                fields, "competency_level", change.value, location=f"{location}.value"
            )
        elif (
            isinstance(change, wire.SetConditionKind)
            and target.resource_kind == "condition"
        ):
            _set_field(
                fields,
                "kind",
                ConditionKind(change.value),
                location=f"{location}.value",
            )
        elif target.resource_kind == "task":
            task_changes.append(_task_change(context, context.task(target), change))
        else:
            raise InvalidJobDescriptionInputError("修改動作不適用此目標")
    if task_changes:
        fields["changes"] = tuple(task_changes)
    if citation_changes:
        fields["citations"] = _citations(context, citation_changes)
    return fields


def _update_item(
    context: WriteContext, target: ReferenceTarget, fields: dict[str, object]
) -> JobDescriptionResult:
    workspace_id = context.parameters["workspace_id"]
    factory = context.parameters["uow_factory"]
    fields[f"{target.resource_kind}_id"] = target.resource_id
    match target.resource_kind:
        case "task":
            return update_task(
                workspace_id=workspace_id,
                input=task_input.UpdateTaskInput.model_validate(fields),
                uow_factory=factory,
                actor=context.parameters["actor"],
            )
        case "duty":
            return duties.update_duty(
                workspace_id=workspace_id,
                input=duties.UpdateDutyInput.model_validate(fields),
                uow_factory=factory,
                actor=context.parameters["actor"],
            )
        case "knowledge":
            return knowledge.update_knowledge(
                workspace_id=workspace_id,
                input=knowledge.UpdateKnowledgeInput.model_validate(fields),
                uow_factory=factory,
                actor=context.parameters["actor"],
            )
        case "skill":
            return skills.update_skill(
                workspace_id=workspace_id,
                input=skills.UpdateSkillInput.model_validate(fields),
                uow_factory=factory,
                actor=context.parameters["actor"],
            )
        case "collaboration":
            return collaborations.update_collaboration(
                workspace_id=workspace_id,
                input=collaborations.UpdateCollaborationInput.model_validate(fields),
                uow_factory=factory,
                actor=context.parameters["actor"],
            )
        case "condition":
            return conditions.update_condition(
                workspace_id=workspace_id,
                input=conditions.UpdateConditionInput.model_validate(fields),
                uow_factory=factory,
                actor=context.parameters["actor"],
            )
        case _:
            raise InvalidJobDescriptionInputError("此目標須由所屬任務修改")


def revise_item(
    context: WriteContext, read_ref: str, changes: Sequence[wire.ItemChange]
) -> JobDescriptionResult:
    target = context.target(read_ref, _ITEM_KINDS)
    fields = _revision_fields(
        context,
        target,
        ((f"changes[{index}]", change) for index, change in enumerate(changes)),
    )
    if target.resource_kind in ("outcome", "requirement"):
        # 一筆明細仍經 Task PATCH，不能建立第二套明細交易入口。
        owner = context.detail_owner(target)
        detail = wire.ReviseDetail(
            action="revise_detail", detail_read_ref=read_ref, text=str(fields["text"])
        )
        fields = context.input_fields()
        fields["changes"] = (_task_change(context, owner, detail),)
        target = ReferenceTarget("task", owner.id)
    return _update_item(context, target, fields)


def move_item(
    context: WriteContext,
    read_ref: str,
    destination: wire.Destination,
    before_read_ref: str | None,
    changes: Sequence[wire.MovementChange],
) -> JobDescriptionResult:
    target = context.target(read_ref, _ITEM_KINDS)
    before = (
        context.target(before_read_ref, (target.resource_kind,)).resource_id
        if before_read_ref is not None
        else None
    )
    if isinstance(destination, wire.TaskParent) and target.resource_kind != "task":
        raise InvalidTaskReferenceError("只有任務可更換職責")
    fields = _revision_fields(
        context,
        target,
        (
            (f"content_changes[{index}]", change)
            for index, change in enumerate(changes)
            if not isinstance(change, wire.SetDutyScope)
        ),
    )
    duty_scopes = tuple(
        task_input.DutyScopeChange(
            duty_id=context.target(change.duty_read_ref, _DUTY_KINDS).resource_id,
            scope=change.scope,
        )
        for change in changes
        if isinstance(change, wire.SetDutyScope)
    )
    if duty_scopes:
        fields["duty_scopes"] = duty_scopes
    if target.resource_kind == "task":
        task = context.task(target)
        duty_id = task.duty_id
        if isinstance(destination, wire.TaskParent):
            duty_id = (
                context.target(destination.parent_read_ref, _DUTY_KINDS).resource_id
                if destination.parent_read_ref is not None
                else None
            )
        if changes and duty_id == task.duty_id:
            raise InvalidJobDescriptionInputError("伴隨修改僅適用任務更換職責")
        fields["placement"] = {"destination_duty_id": duty_id, "before_id": before}
    elif changes:
        raise InvalidJobDescriptionInputError("伴隨修改僅適用任務更換職責")
    elif target.resource_kind in ("outcome", "requirement"):
        owner = context.detail_owner(target)
        change = (
            task_input.MoveOutcomeInput(id=target.resource_id, before_id=before)
            if target.resource_kind == "outcome"
            else task_input.MoveRequirementInput(
                id=target.resource_id, before_id=before
            )
        )
        fields["changes"] = (change,)
        target = ReferenceTarget("task", owner.id)
    else:
        fields["placement"] = {"before_id": before}
    return _update_item(context, target, fields)


def delete_item(context: WriteContext, read_ref: str) -> JobDescriptionResult:
    target = context.target(read_ref, _ITEM_KINDS)
    match target.resource_kind:
        case "task":
            return delete_task(**context.parameters, task_id=target.resource_id)
        case "duty":
            return duties.delete_duty(**context.parameters, duty_id=target.resource_id)
        case "knowledge":
            return knowledge.delete_knowledge(
                **context.parameters, knowledge_id=target.resource_id
            )
        case "skill":
            return skills.delete_skill(
                **context.parameters, skill_id=target.resource_id
            )
        case "collaboration":
            return collaborations.delete_collaboration(
                **context.parameters, collaboration_id=target.resource_id
            )
        case "condition":
            return conditions.delete_condition(
                **context.parameters, condition_id=target.resource_id
            )
        case _:
            raise InvalidJobDescriptionInputError(
                "刪除成果／要求請選所屬任務及 remove_detail"
            )
