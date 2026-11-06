"""一個 Workspace 一個 Plan 根，版本完整保存並依根級聯刪除。"""

from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.shared.infrastructure.persistence.orm_base import OrmBase


class PlanRow(OrmBase):
    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint(
            "version BETWEEN 1 AND 9007199254740991", name="ck_plans_version"
        ),
        CheckConstraint("char_length(body) <= 16000", name="ck_plans_body_length"),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", name="fk_plans_workspace_id", ondelete="CASCADE"),
        primary_key=True,
    )
    version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)


class PlanVersionRow(OrmBase):
    __tablename__ = "plan_versions"
    __table_args__ = (
        CheckConstraint(
            "version BETWEEN 1 AND 9007199254740991", name="ck_plan_versions_version"
        ),
        CheckConstraint(
            "char_length(body) <= 16000", name="ck_plan_versions_body_length"
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "plans.workspace_id",
            name="fk_plan_versions_workspace_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    version: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
