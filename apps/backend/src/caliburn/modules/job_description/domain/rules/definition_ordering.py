"""JD 內部職責及 K/S 總覽的相對排列規則。"""

from uuid import UUID

from caliburn.modules.job_description.domain.errors import InvalidDefinitionOrderError
from caliburn.modules.job_description.domain.rules.collection_ordering import (
    move_before,
)


def move_definition_before(
    *, definition_id: UUID, ordered_ids: tuple[UUID, ...], before_id: UUID | None
) -> tuple[UUID, ...]:
    """以同 JD 同類條目的身分順序計算排列；其他相對順序不變。"""
    try:
        return move_before(
            identity=definition_id, ordered_ids=ordered_ids, before_id=before_id
        )
    except ValueError as error:
        raise InvalidDefinitionOrderError(
            "排序目標與錨點須為同 JD 同類的不同條目"
        ) from error
