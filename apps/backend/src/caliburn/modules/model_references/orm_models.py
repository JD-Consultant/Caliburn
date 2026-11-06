"""模型定位唯一資料表；只有 Workspace 外鍵，不連多型業務表。"""

from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Identity,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.modules.model_references.contracts import ResourceKind
from caliburn.shared.infrastructure.persistence.orm_base import OrmBase


class ModelReferenceRow(OrmBase):
    __tablename__ = "model_references"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "resource_kind",
            "resource_id",
            name="uq_model_references_target",
        ),
        CheckConstraint(
            "resource_kind IN ('message', 'duty', 'task', 'outcome', 'requirement', "
            "'knowledge', 'skill', 'collaboration', 'condition', 'occupation', "
            "'citation')",
            name="ck_model_references_kind",
        ),
    )

    reference_number: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "workspaces.id", name="fk_model_references_workspace", ondelete="CASCADE"
        ),
        nullable=False,
    )
    resource_kind: Mapped[ResourceKind] = mapped_column(Text, nullable=False)
    resource_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
