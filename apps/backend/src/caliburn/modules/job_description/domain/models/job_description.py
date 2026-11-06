"""JD 唯一聚合根維護全部內容、分類、引用及順序。"""

from collections.abc import Container
from typing import Self
from uuid import UUID, uuid7

from pydantic import (
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
    validate_call,
)

from caliburn.modules.job_description.domain.errors import (
    CitationNotFoundError,
    CitationTargetNotFoundError,
    CollaborationNotFoundError,
    DuplicateIdentityError,
    DutyNotFoundError,
    InvalidCitationError,
    InvalidJobDescriptionOwnershipError,
    InvalidJobDescriptionRecordOrderError,
    InvalidTaskReferenceError,
    JobConditionNotFoundError,
    KnowledgeNotFoundError,
    SkillNotFoundError,
    TaskNotFoundError,
)
from caliburn.modules.job_description.domain.models.citation import (
    Citation,
    CitationTargetKind,
    MemoryReference,
    SourceReference,
)
from caliburn.modules.job_description.domain.models.collaboration_entry import (
    CollaborationEntry,
)
from caliburn.modules.job_description.domain.models.competency_level import (
    CompetencyLevel,
)
from caliburn.modules.job_description.domain.models.condition_kind import ConditionKind
from caliburn.modules.job_description.domain.models.duty import Duty
from caliburn.modules.job_description.domain.models.entry_name import (
    EntryName,
    require_distinct_names,
)
from caliburn.modules.job_description.domain.models.job_condition import JobCondition
from caliburn.modules.job_description.domain.models.job_task import JobTask
from caliburn.modules.job_description.domain.models.knowledge import Knowledge
from caliburn.modules.job_description.domain.models.skill import Skill
from caliburn.modules.job_description.domain.models.task_outcome import TaskOutcome
from caliburn.modules.job_description.domain.models.task_requirement import (
    TaskRequirement,
)
from caliburn.modules.job_description.domain.rules.collection_ordering import (
    move_before,
)
from caliburn.modules.job_description.domain.rules.definition_ordering import (
    move_definition_before,
)
from caliburn.modules.job_description.domain.rules.task_placement import (
    plan_task_placement,
)
from caliburn.shared.domain.base_aggregate_root import BaseAggregateRoot

_UUID_ADAPTER = TypeAdapter(UUID)
_OPTIONAL_UUID_ADAPTER = TypeAdapter(UUID | None)
type DefinitionSelection = UUID | tuple[str, str | None]

_DEFINITION_SELECTIONS_ADAPTER = TypeAdapter(tuple[DefinitionSelection, ...])
_TASK_TEXTS_ADAPTER = TypeAdapter(tuple[str, ...])


class JobDescription(BaseAggregateRoot[UUID]):
    """新增經領域方法；建構子供復水，接收本次獨立建立的成員。"""

    workspace_id: UUID = Field(frozen=True)
    job_title: str | None = Field(default=None, frozen=True)
    organization_unit: str | None = Field(default=None, frozen=True)
    reports_to: str | None = Field(default=None, frozen=True)
    purpose: str | None = Field(default=None, frozen=True)
    baseline_competency_level: CompetencyLevel | None = Field(default=None, frozen=True)
    collaborations: tuple[CollaborationEntry, ...] = Field(default=(), frozen=True)
    conditions: tuple[JobCondition, ...] = Field(default=(), frozen=True)
    duties: tuple[Duty, ...] = Field(default=(), frozen=True)
    tasks: tuple[JobTask, ...] = Field(default=(), frozen=True)
    knowledge: tuple[Knowledge, ...] = Field(default=(), frozen=True)
    skills: tuple[Skill, ...] = Field(default=(), frozen=True)
    citations: tuple[Citation, ...] = Field(default=(), frozen=True)

    @classmethod
    def create(cls, *, workspace_id: UUID) -> Self:
        """建立新的空 JD；復水使用建構子保留原 ID。"""
        return cls(id=uuid7(), workspace_id=workspace_id)

    @field_validator("conditions")
    @classmethod
    def _group_conditions(
        cls, values: tuple[JobCondition, ...]
    ) -> tuple[JobCondition, ...]:
        return _group_conditions(values)

    @model_validator(mode="after")
    def _validate_structure(self) -> JobDescription:
        for members in (self.duties, self.tasks, self.knowledge, self.skills):
            for member in members:
                self._require_ownership(member)
        for entries in (
            self.collaborations,
            self.conditions,
            self.duties,
            self.tasks,
            self.knowledge,
            self.skills,
        ):
            identities = tuple(item.id for item in entries)
            if len(identities) != len(set(identities)):
                raise DuplicateIdentityError("同類 JD 內部記載的 ID 不可重複")
        for named_entries in (self.duties, self.tasks, self.knowledge, self.skills):
            require_distinct_names(item.name for item in named_entries)
        # O/P 身分由整份 JD 管理，避免同一記載同時屬於不同任務。
        for identities in (
            tuple(item.id for task in self.tasks for item in task.outcomes),
            tuple(item.id for task in self.tasks for item in task.requirements),
        ):
            if len(identities) != len(set(identities)):
                raise DuplicateIdentityError("同類任務記載不可由多個任務共用身分")
        for task in self.tasks:
            self._require_task_references(
                task, knowledge=self.knowledge, skills=self.skills
            )
        object.__setattr__(self, "tasks", self._group_tasks(self.tasks))
        citation_ids: set[UUID] = set()
        citation_relations: set[tuple[CitationTargetKind, UUID, SourceReference]] = (
            set()
        )
        for citation in self.citations:
            self.require_citation_target(
                target_kind=citation.target_kind, target_id=citation.target_id
            )
            if citation.source.workspace_id != self.workspace_id:
                raise InvalidCitationError("引用來源必須屬於此 Workspace")
            relation = (citation.target_kind, citation.target_id, citation.source)
            if citation.id in citation_ids or relation in citation_relations:
                raise InvalidCitationError("引用身分或來源關係不可重複")
            citation_ids.add(citation.id)
            citation_relations.add(relation)
        return self

    def require_citation_target(
        self, *, target_kind: CitationTargetKind, target_id: UUID
    ) -> None:
        targets: dict[CitationTargetKind, set[UUID]] = {
            "job_description": {self.id},
            "duty": {item.id for item in self.duties},
            "task": {item.id for item in self.tasks},
            "knowledge": {item.id for item in self.knowledge},
            "skill": {item.id for item in self.skills},
            "collaboration": {item.id for item in self.collaborations},
            "condition": {item.id for item in self.conditions},
        }
        if target_id not in targets.get(target_kind, set()):
            raise CitationTargetNotFoundError("引用目標不存在於此 JD 的指定種類")

    def add_citation(
        self,
        *,
        target_kind: CitationTargetKind,
        target_id: UUID,
        source: SourceReference,
    ) -> UUID:
        self.require_citation_target(target_kind=target_kind, target_id=target_id)
        citation = Citation(
            id=uuid7(), target_kind=target_kind, target_id=target_id, source=source
        )
        if citation.source.workspace_id != self.workspace_id:
            raise InvalidCitationError("引用來源必須屬於此 Workspace")
        for existing in self.citations:
            if existing.id == citation.id:
                raise InvalidCitationError("引用身分不可重複")
            if (existing.target_kind, existing.target_id, existing.source) == (
                target_kind,
                target_id,
                source,
            ):
                return existing.id
        object.__setattr__(self, "citations", (*self.citations, citation))
        return citation.id

    def get_citation(self, *, citation_id: UUID) -> Citation:
        for citation in self.citations:
            if citation.id == citation_id:
                return citation
        raise CitationNotFoundError("引用不存在於此 JD")

    def remove_citation(self, *, citation_id: UUID) -> None:
        self.get_citation(citation_id=citation_id)
        object.__setattr__(
            self, "citations", tuple(x for x in self.citations if x.id != citation_id)
        )

    def set_citation_review(self, *, citation_id: UUID, jd_changed: bool) -> None:
        citation = self.get_citation(citation_id=citation_id)
        updated = Citation(
            id=citation.id,
            target_kind=citation.target_kind,
            target_id=citation.target_id,
            source=citation.source,
            jd_changed=jd_changed,
        )
        object.__setattr__(
            self,
            "citations",
            tuple(updated if x.id == citation_id else x for x in self.citations),
        )

    def confirm_citation(self, *, citation_id: UUID, source: SourceReference) -> None:
        citation = self.get_citation(citation_id=citation_id)
        original = citation.source
        if isinstance(original, MemoryReference) and isinstance(
            source, MemoryReference
        ):
            same_identity = (original.workspace_id, original.item_id) == (
                source.workspace_id,
                source.item_id,
            )
        else:
            same_identity = original == source
        if not same_identity:
            raise InvalidCitationError("核對不得改指另一來源")
        updated = Citation(
            id=citation.id,
            target_kind=citation.target_kind,
            target_id=citation.target_id,
            source=source,
            jd_changed=False,
        )
        if any(
            other.id != citation.id
            and (other.target_kind, other.target_id, other.source)
            == (updated.target_kind, updated.target_id, updated.source)
            for other in self.citations
        ):
            raise InvalidCitationError("核對後引用與既有來源重複")
        object.__setattr__(
            self,
            "citations",
            tuple(updated if x.id == citation.id else x for x in self.citations),
        )

    def _remove_target_citations(
        self, kind: CitationTargetKind, identity: UUID
    ) -> None:
        object.__setattr__(
            self,
            "citations",
            tuple(
                x
                for x in self.citations
                if (x.target_kind, x.target_id) != (kind, identity)
            ),
        )

    def _group_tasks(self, tasks: tuple[JobTask, ...]) -> tuple[JobTask, ...]:
        groups = (None, *(duty.id for duty in self.duties))
        return tuple(
            task for duty_id in groups for task in tasks if task.duty_id == duty_id
        )

    def _require_ownership(self, member: Duty | JobTask | Knowledge | Skill) -> None:
        if member.job_description_id != self.id:
            raise InvalidJobDescriptionOwnershipError("內部成員必須屬於此 JD")

    def _require_task_references(
        self,
        task: JobTask,
        *,
        knowledge: tuple[Knowledge, ...],
        skills: tuple[Skill, ...],
    ) -> None:
        if task.duty_id is not None and task.duty_id not in {x.id for x in self.duties}:
            raise InvalidTaskReferenceError("任務分類不存在於此 JD")
        if not set(task.knowledge_ids) <= {x.id for x in knowledge}:
            raise InvalidTaskReferenceError("任務知識引用不存在於此 JD")
        if not set(task.skill_ids) <= {x.id for x in skills}:
            raise InvalidTaskReferenceError("任務技能引用不存在於此 JD")

    def get_duty(self, *, duty_id: UUID) -> Duty:
        identity = _UUID_ADAPTER.validate_python(duty_id, strict=True)
        for duty in self.duties:
            if duty.id == identity:
                return duty
        raise DutyNotFoundError("指定職責不存在於此 JD")

    def get_task(self, *, task_id: UUID) -> JobTask:
        identity = _UUID_ADAPTER.validate_python(task_id, strict=True)
        for task in self.tasks:
            if task.id == identity:
                return task
        raise TaskNotFoundError("指定任務不存在於此 JD")

    def get_knowledge(self, *, knowledge_id: UUID) -> Knowledge:
        identity = _UUID_ADAPTER.validate_python(knowledge_id, strict=True)
        for knowledge in self.knowledge:
            if knowledge.id == identity:
                return knowledge
        raise KnowledgeNotFoundError("指定知識不存在於此 JD")

    def get_skill(self, *, skill_id: UUID) -> Skill:
        identity = _UUID_ADAPTER.validate_python(skill_id, strict=True)
        for skill in self.skills:
            if skill.id == identity:
                return skill
        raise SkillNotFoundError("指定技能不存在於此 JD")

    def add_duty(self, *, name: str, scope: str | None = None) -> UUID:
        candidate = Duty.create(
            id=uuid7(), job_description_id=self.id, name=name, scope=scope
        )
        _require_new_id(candidate.id, tuple(duty.id for duty in self.duties))
        require_distinct_names((*[duty.name for duty in self.duties], candidate.name))
        object.__setattr__(self, "duties", (*self.duties, candidate))
        return candidate.id

    def add_knowledge(self, *, name: str, description: str | None = None) -> UUID:
        candidate = Knowledge.create(
            id=uuid7(),
            job_description_id=self.id,
            name=name,
            description=description,
        )
        _require_new_id(
            candidate.id, tuple(knowledge.id for knowledge in self.knowledge)
        )
        require_distinct_names(
            (*[knowledge.name for knowledge in self.knowledge], candidate.name)
        )
        object.__setattr__(self, "knowledge", (*self.knowledge, candidate))
        return candidate.id

    def add_skill(self, *, name: str, description: str | None = None) -> UUID:
        candidate = Skill.create(
            id=uuid7(), job_description_id=self.id, name=name, description=description
        )
        _require_new_id(candidate.id, tuple(skill.id for skill in self.skills))
        require_distinct_names((*[skill.name for skill in self.skills], candidate.name))
        object.__setattr__(self, "skills", (*self.skills, candidate))
        return candidate.id

    def add_task(
        self,
        *,
        name: str,
        description: str | None = None,
        duty_id: UUID | None = None,
        competency_level: int | None = None,
        outcomes: tuple[str, ...] = (),
        requirements: tuple[str, ...] = (),
        knowledge: tuple[DefinitionSelection, ...] = (),
        skills: tuple[DefinitionSelection, ...] = (),
    ) -> UUID:
        """K/S 按序引用 UUID 或新建 (name, description)；完整驗證後納入。"""
        knowledge_ids: list[UUID] = []
        knowledge_candidates: list[Knowledge] = []
        for selection in _DEFINITION_SELECTIONS_ADAPTER.validate_python(
            knowledge, strict=True
        ):
            if isinstance(selection, UUID):
                knowledge_ids.append(selection)
            else:
                knowledge_name, knowledge_description = selection
                knowledge_candidate = Knowledge.create(
                    id=uuid7(),
                    job_description_id=self.id,
                    name=knowledge_name,
                    description=knowledge_description,
                )
                knowledge_candidates.append(knowledge_candidate)
                knowledge_ids.append(knowledge_candidate.id)
        require_distinct_names(knowledge.name for knowledge in knowledge_candidates)
        skill_ids: list[UUID] = []
        skill_candidates: list[Skill] = []
        for selection in _DEFINITION_SELECTIONS_ADAPTER.validate_python(
            skills, strict=True
        ):
            if isinstance(selection, UUID):
                skill_ids.append(selection)
            else:
                skill_name, skill_description = selection
                skill_candidate = Skill.create(
                    id=uuid7(),
                    job_description_id=self.id,
                    name=skill_name,
                    description=skill_description,
                )
                skill_candidates.append(skill_candidate)
                skill_ids.append(skill_candidate.id)
        require_distinct_names(skill.name for skill in skill_candidates)
        candidate_task = JobTask.create(
            id=uuid7(),
            job_description_id=self.id,
            name=name,
            description=description,
            duty_id=duty_id,
            competency_level=competency_level,
            outcomes=tuple(
                TaskOutcome(id=uuid7(), text=text)
                for text in _TASK_TEXTS_ADAPTER.validate_python(outcomes, strict=True)
            ),
            requirements=tuple(
                TaskRequirement(id=uuid7(), text=text)
                for text in _TASK_TEXTS_ADAPTER.validate_python(
                    requirements, strict=True
                )
            ),
            knowledge_ids=tuple(knowledge_ids),
            skill_ids=tuple(skill_ids),
        )
        require_distinct_names(
            (*[task.name for task in self.tasks], candidate_task.name)
        )
        all_knowledge = (*self.knowledge, *knowledge_candidates)
        all_skills = (*self.skills, *skill_candidates)
        require_distinct_names(knowledge.name for knowledge in all_knowledge)
        require_distinct_names(skill.name for skill in all_skills)
        for entries in (all_knowledge, all_skills, (*self.tasks, candidate_task)):
            identities = tuple(entry.id for entry in entries)
            if len(identities) != len(set(identities)):
                raise DuplicateIdentityError("同類 JD 內部條目的 ID 不可重複")
        self._require_task_references(
            candidate_task, knowledge=all_knowledge, skills=all_skills
        )
        existing_outcome_ids = {
            outcome.id for task in self.tasks for outcome in task.outcomes
        }
        for outcome in candidate_task.outcomes:
            _require_new_id(outcome.id, existing_outcome_ids)
        existing_requirement_ids = {
            requirement.id for task in self.tasks for requirement in task.requirements
        }
        for requirement in candidate_task.requirements:
            _require_new_id(requirement.id, existing_requirement_ids)
        object.__setattr__(self, "knowledge", all_knowledge)
        object.__setattr__(self, "skills", all_skills)
        object.__setattr__(
            self, "tasks", self._group_tasks((*self.tasks, candidate_task))
        )
        return candidate_task.id

    def update_duty(self, *, duty_id: UUID, name: str, scope: str | None) -> bool:
        duty = self.get_duty(duty_id=duty_id)
        candidate_name = EntryName(value=name)
        require_distinct_names(
            (*[x.name for x in self.duties if x.id != duty_id], candidate_name)
        )
        return duty._update_details(name=candidate_name, scope=scope)

    def update_knowledge(
        self, *, knowledge_id: UUID, name: str, description: str | None
    ) -> bool:
        knowledge = self.get_knowledge(knowledge_id=knowledge_id)
        candidate_name = EntryName(value=name)
        require_distinct_names(
            (*[x.name for x in self.knowledge if x.id != knowledge_id], candidate_name)
        )
        return knowledge._update_details(name=candidate_name, description=description)

    def update_skill(
        self, *, skill_id: UUID, name: str, description: str | None
    ) -> bool:
        skill = self.get_skill(skill_id=skill_id)
        candidate_name = EntryName(value=name)
        require_distinct_names(
            (*[x.name for x in self.skills if x.id != skill_id], candidate_name)
        )
        return skill._update_details(name=candidate_name, description=description)

    def update_task(
        self,
        *,
        task_id: UUID,
        name: str,
        description: str | None,
        competency_level: int | None,
    ) -> bool:
        task = self.get_task(task_id=task_id)
        candidate_name = EntryName(value=name)
        require_distinct_names(
            (*[x.name for x in self.tasks if x.id != task_id], candidate_name)
        )
        return task._update_details(
            name=candidate_name,
            description=description,
            competency_level=CompetencyLevel(value=competency_level)
            if competency_level is not None
            else None,
        )

    def add_outcome(self, *, task_id: UUID, text: str) -> UUID:
        task = self.get_task(task_id=task_id)
        candidate = TaskOutcome(id=uuid7(), text=text)
        _require_new_id(
            candidate.id,
            tuple(item.id for existing in self.tasks for item in existing.outcomes),
        )
        task._add_outcome(outcome=candidate)
        return candidate.id

    def add_requirement(self, *, task_id: UUID, text: str) -> UUID:
        task = self.get_task(task_id=task_id)
        candidate = TaskRequirement(id=uuid7(), text=text)
        _require_new_id(
            candidate.id,
            tuple(item.id for existing in self.tasks for item in existing.requirements),
        )
        task._add_requirement(requirement=candidate)
        return candidate.id

    def update_outcome(self, *, task_id: UUID, outcome_id: UUID, text: str) -> bool:
        return self.get_task(task_id=task_id)._update_outcome(
            outcome_id=outcome_id, text=text
        )

    def update_requirement(
        self, *, task_id: UUID, requirement_id: UUID, text: str
    ) -> bool:
        return self.get_task(task_id=task_id)._update_requirement(
            requirement_id=requirement_id, text=text
        )

    def remove_duty(self, *, duty_id: UUID) -> None:
        duty = self.get_duty(duty_id=duty_id)
        self._remove_target_citations("duty", duty.id)
        affected = tuple(task for task in self.tasks if task.duty_id == duty.id)
        remaining = tuple(task for task in self.tasks if task.duty_id != duty.id)
        for task in affected:
            task._reclassify(duty_id=None)
        object.__setattr__(
            self,
            "duties",
            tuple(
                existing_duty
                for existing_duty in self.duties
                if existing_duty.id != duty.id
            ),
        )
        object.__setattr__(self, "tasks", self._group_tasks((*remaining, *affected)))

    def remove_task(self, *, task_id: UUID) -> None:
        task = self.get_task(task_id=task_id)
        self._remove_target_citations("task", task.id)
        object.__setattr__(
            self,
            "tasks",
            tuple(
                existing_task
                for existing_task in self.tasks
                if existing_task.id != task.id
            ),
        )

    def remove_knowledge(self, *, knowledge_id: UUID) -> None:
        knowledge = self.get_knowledge(knowledge_id=knowledge_id)
        self._remove_target_citations("knowledge", knowledge.id)
        for task in self.tasks:
            task._unlink_knowledge(knowledge_id=knowledge.id)
        object.__setattr__(
            self,
            "knowledge",
            tuple(
                existing_knowledge
                for existing_knowledge in self.knowledge
                if existing_knowledge.id != knowledge.id
            ),
        )

    def remove_skill(self, *, skill_id: UUID) -> None:
        skill = self.get_skill(skill_id=skill_id)
        self._remove_target_citations("skill", skill.id)
        for task in self.tasks:
            task._unlink_skill(skill_id=skill.id)
        object.__setattr__(
            self,
            "skills",
            tuple(
                existing_skill
                for existing_skill in self.skills
                if existing_skill.id != skill.id
            ),
        )

    def remove_outcome(self, *, task_id: UUID, outcome_id: UUID) -> None:
        self.get_task(task_id=task_id)._remove_outcome(outcome_id=outcome_id)

    def remove_requirement(self, *, task_id: UUID, requirement_id: UUID) -> None:
        self.get_task(task_id=task_id)._remove_requirement(
            requirement_id=requirement_id
        )

    def link_knowledge(self, *, task_id: UUID, knowledge_id: UUID) -> bool:
        task = self.get_task(task_id=task_id)
        knowledge = self._get_referenced_knowledge(knowledge_id=knowledge_id)
        return task._link_knowledge(knowledge_id=knowledge.id)

    def link_skill(self, *, task_id: UUID, skill_id: UUID) -> bool:
        task = self.get_task(task_id=task_id)
        skill = self._get_referenced_skill(skill_id=skill_id)
        return task._link_skill(skill_id=skill.id)

    def unlink_knowledge(self, *, task_id: UUID, knowledge_id: UUID) -> bool:
        task = self.get_task(task_id=task_id)
        knowledge = self._get_referenced_knowledge(knowledge_id=knowledge_id)
        return task._unlink_knowledge(knowledge_id=knowledge.id)

    def unlink_skill(self, *, task_id: UUID, skill_id: UUID) -> bool:
        task = self.get_task(task_id=task_id)
        skill = self._get_referenced_skill(skill_id=skill_id)
        return task._unlink_skill(skill_id=skill.id)

    def _get_referenced_knowledge(self, *, knowledge_id: UUID) -> Knowledge:
        """Task 關係要求有效定義；與直接查詢定義的不存在語意分開。"""
        try:
            return self.get_knowledge(knowledge_id=knowledge_id)
        except KnowledgeNotFoundError as error:
            raise InvalidTaskReferenceError("任務知識引用不存在於此 JD") from error

    def _get_referenced_skill(self, *, skill_id: UUID) -> Skill:
        try:
            return self.get_skill(skill_id=skill_id)
        except SkillNotFoundError as error:
            raise InvalidTaskReferenceError("任務技能引用不存在於此 JD") from error

    def move_duty(self, *, duty_id: UUID, before_id: UUID | None) -> bool:
        self.get_duty(duty_id=duty_id)
        before = _OPTIONAL_UUID_ADAPTER.validate_python(before_id, strict=True)
        identities = tuple(existing_duty.id for existing_duty in self.duties)
        ordered = move_definition_before(
            definition_id=duty_id, ordered_ids=identities, before_id=before
        )
        if ordered == identities:
            return False
        entries = {existing_duty.id: existing_duty for existing_duty in self.duties}
        object.__setattr__(
            self, "duties", tuple(entries[identity] for identity in ordered)
        )
        object.__setattr__(self, "tasks", self._group_tasks(self.tasks))
        return True

    def move_knowledge(self, *, knowledge_id: UUID, before_id: UUID | None) -> bool:
        self.get_knowledge(knowledge_id=knowledge_id)
        before = _OPTIONAL_UUID_ADAPTER.validate_python(before_id, strict=True)
        identities = tuple(
            existing_knowledge.id for existing_knowledge in self.knowledge
        )
        ordered = move_definition_before(
            definition_id=knowledge_id, ordered_ids=identities, before_id=before
        )
        if ordered == identities:
            return False
        entries = {
            existing_knowledge.id: existing_knowledge
            for existing_knowledge in self.knowledge
        }
        object.__setattr__(
            self, "knowledge", tuple(entries[identity] for identity in ordered)
        )
        return True

    def move_skill(self, *, skill_id: UUID, before_id: UUID | None) -> bool:
        self.get_skill(skill_id=skill_id)
        before = _OPTIONAL_UUID_ADAPTER.validate_python(before_id, strict=True)
        identities = tuple(existing_skill.id for existing_skill in self.skills)
        ordered = move_definition_before(
            definition_id=skill_id, ordered_ids=identities, before_id=before
        )
        if ordered == identities:
            return False
        entries = {existing_skill.id: existing_skill for existing_skill in self.skills}
        object.__setattr__(
            self, "skills", tuple(entries[identity] for identity in ordered)
        )
        return True

    def move_task(
        self,
        *,
        task_id: UUID,
        destination_duty_id: UUID | None,
        before_id: UUID | None = None,
    ) -> bool:
        task = self.get_task(task_id=task_id)
        destination = _OPTIONAL_UUID_ADAPTER.validate_python(
            destination_duty_id, strict=True
        )
        if destination is not None:
            try:
                self.get_duty(duty_id=destination)
            except DutyNotFoundError as error:
                raise InvalidTaskReferenceError("任務分類不存在於此 JD") from error
        group = tuple(
            existing_task.id
            for existing_task in self.tasks
            if existing_task.duty_id == destination
        )
        placement = plan_task_placement(
            task_id=task.id, destination_task_ids=group, before_id=before_id
        )
        if task.duty_id == destination and not placement.changed:
            return False
        entries = {existing_task.id: existing_task for existing_task in self.tasks}
        other_groups = tuple(
            existing_task
            for existing_task in self.tasks
            if existing_task.duty_id != destination and existing_task.id != task.id
        )
        task._reclassify(duty_id=destination)
        object.__setattr__(
            self,
            "tasks",
            self._group_tasks(
                (*other_groups, *(entries[identity] for identity in placement.task_ids))
            ),
        )
        return True

    def move_outcome(
        self, *, task_id: UUID, outcome_id: UUID, before_id: UUID | None
    ) -> bool:
        return self.get_task(task_id=task_id)._move_outcome(
            outcome_id=outcome_id, before_id=before_id
        )

    def move_requirement(
        self, *, task_id: UUID, requirement_id: UUID, before_id: UUID | None
    ) -> bool:
        return self.get_task(task_id=task_id)._move_requirement(
            requirement_id=requirement_id, before_id=before_id
        )

    def move_knowledge_reference(
        self, *, task_id: UUID, knowledge_id: UUID, before_id: UUID | None
    ) -> bool:
        task = self.get_task(task_id=task_id)
        knowledge = self._get_referenced_knowledge(knowledge_id=knowledge_id)
        return task._move_knowledge_reference(
            knowledge_id=knowledge.id, before_id=before_id
        )

    def move_skill_reference(
        self, *, task_id: UUID, skill_id: UUID, before_id: UUID | None
    ) -> bool:
        task = self.get_task(task_id=task_id)
        skill = self._get_referenced_skill(skill_id=skill_id)
        return task._move_skill_reference(skill_id=skill.id, before_id=before_id)

    def add_collaboration(
        self,
        *,
        collaborator_name: str,
        scope: str | None = None,
    ) -> UUID:
        candidate = CollaborationEntry(
            id=uuid7(), collaborator_name=collaborator_name, scope=scope
        )
        if any(
            collaboration.id == candidate.id for collaboration in self.collaborations
        ):
            raise DuplicateIdentityError("協作 ID 不可重複")
        object.__setattr__(self, "collaborations", (*self.collaborations, candidate))
        return candidate.id

    def get_collaboration(self, *, collaboration_id: UUID) -> CollaborationEntry:
        identity = _UUID_ADAPTER.validate_python(collaboration_id, strict=True)
        for collaboration in self.collaborations:
            if collaboration.id == identity:
                return collaboration
        raise CollaborationNotFoundError("指定協作不存在於此 JD")

    def update_collaboration(
        self,
        *,
        collaboration_id: UUID,
        collaborator_name: str,
        scope: str | None,
    ) -> bool:
        return self.get_collaboration(collaboration_id=collaboration_id)._update(
            collaborator_name=collaborator_name, scope=scope
        )

    def remove_collaboration(self, *, collaboration_id: UUID) -> None:
        existing_collaboration = self.get_collaboration(
            collaboration_id=collaboration_id
        )
        self._remove_target_citations("collaboration", existing_collaboration.id)
        object.__setattr__(
            self,
            "collaborations",
            tuple(x for x in self.collaborations if x.id != existing_collaboration.id),
        )

    def move_collaboration(
        self, *, collaboration_id: UUID, before_id: UUID | None
    ) -> bool:
        self.get_collaboration(collaboration_id=collaboration_id)
        identities = tuple(
            existing_collaboration.id for existing_collaboration in self.collaborations
        )
        ordered = _move_before(identities, collaboration_id, before_id)
        if ordered == identities:
            return False
        entries = {
            existing_collaboration.id: existing_collaboration
            for existing_collaboration in self.collaborations
        }
        object.__setattr__(
            self, "collaborations", tuple(entries[key] for key in ordered)
        )
        return True

    def add_condition(self, *, kind: ConditionKind, text: str) -> UUID:
        candidate = JobCondition(id=uuid7(), kind=kind, text=text)
        if any(condition.id == candidate.id for condition in self.conditions):
            raise DuplicateIdentityError("條件 ID 不可重複")
        object.__setattr__(
            self, "conditions", _group_conditions((*self.conditions, candidate))
        )
        return candidate.id

    def get_condition(self, *, condition_id: UUID) -> JobCondition:
        identity = _UUID_ADAPTER.validate_python(condition_id, strict=True)
        for condition in self.conditions:
            if condition.id == identity:
                return condition
        raise JobConditionNotFoundError("指定條件不存在於此 JD")

    def update_condition(self, *, condition_id: UUID, text: str) -> bool:
        return self.get_condition(condition_id=condition_id)._update_text(text=text)

    def remove_condition(self, *, condition_id: UUID) -> None:
        existing_condition = self.get_condition(condition_id=condition_id)
        self._remove_target_citations("condition", existing_condition.id)
        object.__setattr__(
            self,
            "conditions",
            tuple(x for x in self.conditions if x.id != existing_condition.id),
        )

    def reclassify_condition(self, *, condition_id: UUID, kind: ConditionKind) -> bool:
        condition = self.get_condition(condition_id=condition_id)
        if not condition._reclassify(kind=kind):
            return False
        remaining = tuple(x for x in self.conditions if x.id != condition.id)
        object.__setattr__(
            self, "conditions", _group_conditions((*remaining, condition))
        )
        return True

    def move_condition(self, *, condition_id: UUID, before_id: UUID | None) -> bool:
        existing_condition = self.get_condition(condition_id=condition_id)
        group = tuple(x for x in self.conditions if x.kind == existing_condition.kind)
        identities = tuple(x.id for x in group)
        ordered = _move_before(identities, condition_id, before_id)
        if ordered == identities:
            return False
        entries = {x.id: x for x in group}
        other_groups = tuple(
            x for x in self.conditions if x.kind != existing_condition.kind
        )
        object.__setattr__(
            self,
            "conditions",
            _group_conditions((*other_groups, *(entries[key] for key in ordered))),
        )
        return True

    @validate_call(config=ConfigDict(strict=True))
    def update_details(
        self,
        *,
        job_title: str | None,
        organization_unit: str | None,
        reports_to: str | None,
        purpose: str | None,
        baseline_competency_level: int | None,
    ) -> bool:
        """完整候選驗證成功後原地套用；回傳是否有實際變更。"""
        validated_level = (
            CompetencyLevel(value=baseline_competency_level)
            if baseline_competency_level is not None
            else None
        )
        if (
            self.job_title,
            self.organization_unit,
            self.reports_to,
            self.purpose,
            self.baseline_competency_level,
        ) == (
            job_title,
            organization_unit,
            reports_to,
            purpose,
            validated_level,
        ):
            return False
        object.__setattr__(self, "job_title", job_title)
        object.__setattr__(self, "organization_unit", organization_unit)
        object.__setattr__(self, "reports_to", reports_to)
        object.__setattr__(self, "purpose", purpose)
        object.__setattr__(self, "baseline_competency_level", validated_level)

        return True

    @validate_call(config=ConfigDict(strict=True))
    def set_job_title(self, *, job_title: str | None) -> None:
        object.__setattr__(self, "job_title", job_title)

    @validate_call(config=ConfigDict(strict=True))
    def set_organization_unit(self, *, organization_unit: str | None) -> None:
        object.__setattr__(self, "organization_unit", organization_unit)

    @validate_call(config=ConfigDict(strict=True))
    def set_reports_to(self, *, reports_to: str | None) -> None:
        object.__setattr__(self, "reports_to", reports_to)

    @validate_call(config=ConfigDict(strict=True))
    def set_purpose(self, *, purpose: str | None) -> None:
        object.__setattr__(self, "purpose", purpose)

    @validate_call(config=ConfigDict(strict=True))
    def set_baseline_competency_level(self, *, competency_level: int | None) -> None:
        validated_level = (
            CompetencyLevel(value=competency_level)
            if competency_level is not None
            else None
        )
        object.__setattr__(self, "baseline_competency_level", validated_level)


def _require_new_id(identity: UUID, existing: Container[UUID]) -> None:
    if identity in existing:
        raise DuplicateIdentityError("同類 JD 內部條目的 ID 不可重複")


def _group_conditions(values: tuple[JobCondition, ...]) -> tuple[JobCondition, ...]:
    return tuple(item for kind in ConditionKind for item in values if item.kind == kind)


def _move_before(
    identities: tuple[UUID, ...], identity: UUID, before_id: UUID | None
) -> tuple[UUID, ...]:
    candidate = _OPTIONAL_UUID_ADAPTER.validate_python(before_id, strict=True)
    try:
        return move_before(
            identity=identity, ordered_ids=identities, before_id=candidate
        )
    except ValueError as error:
        raise InvalidJobDescriptionRecordOrderError(
            "排序錨點須為同集合的其他項目"
        ) from error
