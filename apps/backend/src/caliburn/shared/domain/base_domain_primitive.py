"""不可變的單值 Domain Primitive；有效值規則由具體型別定義。"""

from caliburn.shared.domain.base_value_object import BaseValueObject


class BaseDomainPrimitive[ValueT](BaseValueObject):
    value: ValueT
