"""指定內容版本的不可變快照；只供同根恢復。"""

from dataclasses import dataclass
from uuid import UUID

from caliburn.modules.plan.domain.errors import InvalidPlanSnapshotError
from caliburn.modules.plan.domain.text import validate_body

MAX_PLAN_VERSION = 9_007_199_254_740_991


@dataclass(frozen=True, slots=True)
class PlanSnapshot:
    workspace_id: UUID
    version: int
    body: str | None

    def __post_init__(self) -> None:
        if type(self.version) is not int or not 1 <= self.version <= MAX_PLAN_VERSION:
            raise InvalidPlanSnapshotError("Snapshot content version is invalid")
        validate_body(self.body)
