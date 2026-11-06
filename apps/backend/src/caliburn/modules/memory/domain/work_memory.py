"""同一 Workspace 的 Memory 聚合根。"""

from datetime import datetime
from typing import Self
from uuid import UUID, uuid7

from pydantic import ConfigDict, Field, model_validator

from caliburn.modules.memory.domain.analysis import (
    MemoryAnalysis,
    MemoryFailure,
    MemoryFailureReason,
    MemoryPhase,
    MemorySourceWindow,
)
from caliburn.modules.memory.domain.content import MemoryContent
from caliburn.modules.memory.domain.errors import (
    InvalidMemoryPhaseError,
    InvalidMemorySnapshotError,
    InvalidMemorySourceError,
    MemoryAnalysisConflictError,
    MemoryItemNotFoundError,
    MemoryVersionExhaustedError,
)
from caliburn.modules.memory.domain.items import (
    MemoryItem,
    WorkSituation,
    WorkUnderstanding,
    same_memory_item,
    validate_memory_items,
)
from caliburn.modules.memory.domain.snapshot import MAX_MEMORY_VERSION, MemorySnapshot
from caliburn.shared.domain.base_aggregate_root import BaseAggregateRoot


class WorkMemory(BaseAggregateRoot[UUID]):
    """建構子供復水。修改經根操作，持久層在交易內管理寫入資格。"""

    model_config = ConfigDict(hide_input_in_errors=True)

    version: int = Field(default=0, frozen=True, ge=0, le=MAX_MEMORY_VERSION)
    published_version: int | None = Field(default=None, frozen=True, gt=0)
    items: tuple[MemoryItem, ...] = Field(default=(), frozen=True)
    analysis: MemoryAnalysis | None = Field(default=None, frozen=True)
    failure: MemoryFailure | None = Field(default=None, frozen=True)

    @model_validator(mode="after")
    def _validate_saved_memory(self) -> Self:
        if self.published_version is not None and self.published_version > self.version:
            raise InvalidMemorySnapshotError("Memory published version is out of range")
        if self.analysis is not None:
            if (
                self.analysis.base_published_version != self.published_version
                or self.version <= (self.published_version or 0)
            ):
                raise MemoryAnalysisConflictError(
                    "Saved Memory analysis base is invalid"
                )
            self._require_local_window(self.analysis.source_window)
        validate_memory_items(
            workspace_id=self.workspace_id, version=self.version, items=self.items
        )
        return self

    @classmethod
    def create(cls, *, workspace_id: UUID) -> Self:
        return cls(id=workspace_id)

    @property
    def workspace_id(self) -> UUID:
        return self.id

    @property
    def situations(self) -> tuple[WorkSituation, ...]:
        return tuple(item for item in self.items if isinstance(item, WorkSituation))

    @property
    def understandings(self) -> tuple[WorkUnderstanding, ...]:
        return tuple(item for item in self.items if isinstance(item, WorkUnderstanding))

    def get_situation(self, *, item_id: UUID) -> WorkSituation:
        return self._get_item(item_id, WorkSituation)

    def get_understanding(self, *, item_id: UUID) -> WorkUnderstanding:
        return self._get_item(item_id, WorkUnderstanding)

    def create_situation(
        self, *, content: MemoryContent, interview_message_ids: tuple[UUID, ...] = ()
    ) -> UUID:
        version = self._next_version()
        situation = WorkSituation(
            id=uuid7(),
            workspace_id=self.workspace_id,
            content=content,
            interview_message_ids=interview_message_ids,
            changed_version=version,
        )
        self._save_items((*self.items, situation), version)
        return situation.id

    def create_understanding(
        self, *, content: MemoryContent, situation_ids: tuple[UUID, ...] = ()
    ) -> UUID:
        version = self._next_version()
        understanding = WorkUnderstanding(
            id=uuid7(),
            workspace_id=self.workspace_id,
            content=content,
            situation_ids=situation_ids,
            changed_version=version,
        )
        self._save_items((*self.items, understanding), version)
        return understanding.id

    def revise_situation(
        self,
        *,
        item_id: UUID,
        content: MemoryContent,
        interview_message_ids: tuple[UUID, ...],
    ) -> bool:
        situation = self.get_situation(item_id=item_id)
        candidate = WorkSituation(
            id=item_id,
            workspace_id=self.workspace_id,
            content=content,
            interview_message_ids=interview_message_ids,
            changed_version=situation.changed_version,
        )
        if same_memory_item(situation, candidate):
            return False
        version = self._next_version()
        revised = candidate.model_copy(update={"changed_version": version})
        self._update_situation(item_id, revised, version)
        return True

    def revise_understanding(
        self, *, item_id: UUID, content: MemoryContent, situation_ids: tuple[UUID, ...]
    ) -> bool:
        understanding = self.get_understanding(item_id=item_id)
        candidate = WorkUnderstanding(
            id=item_id,
            workspace_id=self.workspace_id,
            content=content,
            situation_ids=situation_ids,
            changed_version=understanding.changed_version,
        )
        if same_memory_item(understanding, candidate):
            return False
        version = self._next_version()
        revised = candidate.model_copy(update={"changed_version": version})
        items = tuple(revised if item.id == item_id else item for item in self.items)
        self._save_items(items, version)
        return True

    def remove_situation(self, *, item_id: UUID) -> None:
        self.get_situation(item_id=item_id)
        self._update_situation(item_id, None, self._next_version())

    def remove_understanding(self, *, item_id: UUID) -> None:
        self.get_understanding(item_id=item_id)
        self._save_items(
            tuple(item for item in self.items if item.id != item_id),
            self._next_version(),
        )

    def publish(
        self, *, covered_through_message_id: UUID, published_at: datetime
    ) -> MemorySnapshot:
        """發布完整圖，並結束同一窗口已交接的整理。"""
        analysis = self.analysis
        if analysis is not None:
            if analysis.phase != "understanding":
                raise InvalidMemoryPhaseError("Memory analysis has not handed off")
            if covered_through_message_id != analysis.source_window.through_message_id:
                raise InvalidMemorySourceError("Memory publication upper bound differs")
        version = self._next_version()
        snapshot = MemorySnapshot(
            workspace_id=self.workspace_id,
            version=version,
            covered_through_message_id=covered_through_message_id,
            published_at=published_at,
            items=self.items,
        )
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "published_version", version)
        object.__setattr__(self, "analysis", None)
        object.__setattr__(self, "failure", None)
        return snapshot

    def reset_to_published(self, snapshot: MemorySnapshot | None) -> bool:
        """還原目前發布基準的完整項目與 stamp。"""
        items = self._published_items(snapshot)
        published_by_id = {item.id: item for item in items}
        if len(self.items) == len(items) and all(
            item.id in published_by_id
            and same_memory_item(item, published_by_id[item.id])
            for item in self.items
        ):
            return False
        self._save_items(items, self._next_version())
        return True

    def begin_analysis(
        self,
        *,
        analysis_id: UUID,
        source_window: MemorySourceWindow,
        baseline: MemorySnapshot | None,
    ) -> None:
        """回到發布基準並建立新的情境整理資格，根版只增加一次。"""
        if self.analysis is not None:
            raise MemoryAnalysisConflictError("Memory analysis is already active")
        self._require_local_window(source_window)
        items = self._published_items(baseline)
        analysis = MemoryAnalysis(
            analysis_id=analysis_id,
            phase="situation",
            base_published_version=self.published_version,
            source_window=source_window,
        )
        self._save_items(items, self._next_version())
        object.__setattr__(self, "analysis", analysis)

    def require_analysis(
        self, *, analysis_id: UUID, phase: MemoryPhase | None = None
    ) -> MemoryAnalysis:
        analysis = self.analysis
        if analysis is None or analysis.analysis_id != analysis_id:
            raise MemoryAnalysisConflictError("Memory analysis is no longer active")
        if phase is not None and analysis.phase != phase:
            raise InvalidMemoryPhaseError("Memory analysis phase does not match")
        return analysis

    def handoff(self, *, analysis_id: UUID) -> None:
        """關閉情境階段的寫入資格並開啟理解階段。"""
        analysis = self.require_analysis(analysis_id=analysis_id, phase="situation")
        version = self._next_version()
        object.__setattr__(
            self, "analysis", analysis.model_copy(update={"phase": "understanding"})
        )
        object.__setattr__(self, "version", version)

    def discard_analysis(
        self,
        *,
        analysis_id: UUID,
        baseline: MemorySnapshot | None,
        reason: MemoryFailureReason | None = None,
        formal_message_ids: tuple[UUID, ...] = (),
    ) -> None:
        """撤去整理資格並恢復基準的內容及 stamp。"""
        self.require_analysis(analysis_id=analysis_id)
        items = self._published_items(baseline)
        failure = (
            MemoryFailure(
                analysis_id=analysis_id,
                reason=reason,
                formal_message_ids=formal_message_ids,
            )
            if reason is not None
            else self.failure
        )
        self._save_items(items, self._next_version())
        object.__setattr__(self, "analysis", None)
        object.__setattr__(self, "failure", failure)

    def _require_local_window(self, source_window: MemorySourceWindow) -> None:
        if source_window.workspace_id != self.workspace_id:
            raise InvalidMemorySourceError(
                "Memory source window belongs to another workspace"
            )

    def _published_items(
        self, snapshot: MemorySnapshot | None
    ) -> tuple[MemoryItem, ...]:
        if snapshot is None:
            if self.published_version is not None:
                raise InvalidMemorySnapshotError(
                    "The published Memory baseline is missing"
                )
            return ()
        if (
            snapshot.workspace_id != self.workspace_id
            or snapshot.version != self.published_version
        ):
            raise InvalidMemorySnapshotError(
                "Snapshot is not the published Memory baseline"
            )
        return snapshot.items

    def _get_item[ItemT: MemoryItem](
        self, item_id: UUID, item_type: type[ItemT]
    ) -> ItemT:
        for item in self.items:
            if item.id == item_id and isinstance(item, item_type):
                return item
        raise MemoryItemNotFoundError("Memory item was not found in this layer")

    def _update_situation(
        self, item_id: UUID, revised: WorkSituation | None, version: int
    ) -> None:
        items: list[MemoryItem] = []
        for item in self.items:
            if item.id == item_id:
                if revised is not None:
                    items.append(revised)
                continue
            if isinstance(item, WorkUnderstanding) and item_id in item.situation_ids:
                sources = item.situation_ids
                if revised is None:
                    sources = tuple(source for source in sources if source != item_id)
                item = item.model_copy(
                    update={"situation_ids": sources, "changed_version": version}
                )
            items.append(item)
        self._save_items(tuple(items), version)

    def _next_version(self) -> int:
        if self.version == MAX_MEMORY_VERSION:
            raise MemoryVersionExhaustedError("Memory version is exhausted")
        return self.version + 1

    def _save_items(self, items: tuple[MemoryItem, ...], version: int) -> None:
        validate_memory_items(
            workspace_id=self.workspace_id, version=version, items=items
        )
        object.__setattr__(self, "items", items)
        object.__setattr__(self, "version", version)
