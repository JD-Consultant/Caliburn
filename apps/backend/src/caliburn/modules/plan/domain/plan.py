"""每 Workspace 的最新正文與內容版本；所有變更從根進入。"""

from typing import Self
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from caliburn.modules.plan.domain.editing.body_edits import apply_body_diff
from caliburn.modules.plan.domain.errors import (
    InvalidPlanSnapshotError,
    PlanVersionExhaustedError,
)
from caliburn.modules.plan.domain.snapshot import MAX_PLAN_VERSION, PlanSnapshot
from caliburn.modules.plan.domain.text import validate_body
from caliburn.shared.domain.base_aggregate_root import BaseAggregateRoot


class Plan(BaseAggregateRoot[UUID]):
    model_config = ConfigDict(hide_input_in_errors=True)

    version: int = Field(default=1, ge=1, le=MAX_PLAN_VERSION, frozen=True)
    body: str | None = Field(default=None, frozen=True)

    @field_validator("body")
    @classmethod
    def _validate_body(cls, body: str | None) -> str | None:
        return validate_body(body)

    @classmethod
    def create(cls, *, workspace_id: UUID) -> Self:
        return cls(id=workspace_id)

    @property
    def workspace_id(self) -> UUID:
        return self.id

    def apply_patch(self, diff: str) -> bool:
        """完整套用才修改目前內容；沒有字元效果時保留 None。"""
        before = self.body if self.body is not None else ""
        after = apply_body_diff(before, diff)
        if after == before:
            return False
        return self._replace_body(after)

    def restore(self, snapshot: PlanSnapshot) -> bool:
        """採用快照正文為最新內容；版號不倒退、不移除既有歷史。"""
        if snapshot.workspace_id != self.workspace_id:
            raise InvalidPlanSnapshotError("Snapshot belongs to another workspace")
        return self._replace_body(snapshot.body)

    def _replace_body(self, body: str | None) -> bool:
        if self.body == body:
            return False
        if self.version == MAX_PLAN_VERSION:
            raise PlanVersionExhaustedError("Plan content version is exhausted")
        object.__setattr__(self, "body", body)
        object.__setattr__(self, "version", self.version + 1)
        return True
