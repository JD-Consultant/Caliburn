"""職能級別的值域；不判斷級別是否符合任務正文。"""

from pydantic import field_validator

from caliburn.modules.job_description.domain.errors import InvalidCompetencyLevelError
from caliburn.shared.domain.base_domain_primitive import BaseDomainPrimitive


class CompetencyLevel(BaseDomainPrimitive[int]):
    @field_validator("value")
    @classmethod
    def _require_valid_level(cls, value: int) -> int:
        if not 1 <= value <= 6:
            raise InvalidCompetencyLevelError("職能級別須為 1–6 的整數")
        return value
