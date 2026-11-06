"""Workspace 資料列；領域模型不依賴 ORM 狀態。"""

from uuid import UUID

from sqlalchemy import CheckConstraint, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.shared.infrastructure.persistence.orm_base import OrmBase


class WorkspaceRow(OrmBase):
    __tablename__ = "workspaces"
    __table_args__ = (
        CheckConstraint(
            # 固定 Python 3.14 str.isspace 完整集合，避免依資料庫 locale 漂移。
            "length(btrim(interviewee_name, U&'"
            "\\0009\\000A\\000B\\000C\\000D\\001C\\001D\\001E\\001F\\0020"
            "\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006"
            "\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000')) > 0",
            name="ck_workspaces_interviewee_name_not_blank",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    interviewee_name: Mapped[str] = mapped_column(Text, nullable=False)
