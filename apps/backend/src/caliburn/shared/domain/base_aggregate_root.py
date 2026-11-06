"""聚合根的身分契約；一致性規則由具體聚合維護。"""

from collections.abc import Hashable

from caliburn.shared.domain.base_entity import BaseEntity


class BaseAggregateRoot[IdT: Hashable](BaseEntity[IdT]):
    """標示聚合的變更入口，不負責交易或事件派送。"""
