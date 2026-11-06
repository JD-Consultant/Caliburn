"""已發生的領域事實；事件身分與發生時間由呼叫端提供。"""

from collections.abc import Hashable

from pydantic import AwareDatetime, BaseModel, ConfigDict


class BaseDomainEvent[IdT: Hashable](BaseModel):
    """具體事件宣告不可變資料；此基底不負責派送或持久化。"""

    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
    )

    event_id: IdT
    occurred_at: AwareDatetime
