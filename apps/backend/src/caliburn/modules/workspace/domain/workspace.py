"""Workspace 聚合根：固定身分與有效的受訪者姓名。"""

from uuid import UUID, uuid7

from pydantic import Field

from caliburn.modules.workspace.domain.interviewee_name import IntervieweeName
from caliburn.shared.domain.base_aggregate_root import BaseAggregateRoot


class Workspace(BaseAggregateRoot[UUID]):
    interviewee_name: IntervieweeName = Field(frozen=True)

    @classmethod
    def create(cls, *, interviewee_name: str) -> Workspace:
        name = IntervieweeName(value=interviewee_name)
        return cls(id=uuid7(), interviewee_name=name)

    def rename(self, *, interviewee_name: IntervieweeName) -> Workspace:
        """保留身分，回傳通過驗證的新快照。"""
        return Workspace(id=self.id, interviewee_name=interviewee_name)
