"""受訪者姓名：不可全空白，合法值保留原文。"""

from pydantic import field_validator

from caliburn.shared.domain.base_domain_primitive import BaseDomainPrimitive


class IntervieweeName(BaseDomainPrimitive[str]):
    @field_validator("value")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value or value.isspace():
            raise ValueError("受訪者姓名不可為空字串或全空白")

        return value
