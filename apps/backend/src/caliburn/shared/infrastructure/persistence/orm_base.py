"""所有持久化模型共用的 SQLAlchemy metadata。"""

from sqlalchemy.orm import DeclarativeBase


class OrmBase(DeclarativeBase):
    pass
