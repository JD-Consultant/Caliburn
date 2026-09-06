"""Small application routing projection; message bodies live only in Saver.

No model calls or long transactions here. Single-process admission is owned by
AnalysisService, not claimed as a distributed queue or a second workflow engine.
"""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class DocumentRow(Base):
    __tablename__ = 'q019_document'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RunRow(Base):
    __tablename__ = 'q019_analysis_run'
    __table_args__ = (UniqueConstraint('document_id', 'request_key'),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey('q019_document.id'))
    request_key: Mapped[str] = mapped_column(String(128))
    input_digest: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(64))
    resume_count: Mapped[int] = mapped_column(Integer, default=0)
    usage_complete: Mapped[bool] = mapped_column(Boolean, default=True)
    outcome: Mapped[dict | None] = mapped_column(JSON)


def values(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


class Catalog:
    def __init__(self, engine):
        self.engine = engine
        self.sessions = sessionmaker(engine, expire_on_commit=False)

    def setup(self):
        Base.metadata.create_all(self.engine)

    def create_document(self, title):
        with self.sessions.begin() as session:
            row = DocumentRow(id=str(uuid4()), title=title, created_at=datetime.now(timezone.utc))
            session.add(row)
            session.flush()
            return values(row)

    def documents(self):
        with self.sessions() as session:
            return [values(row) for row in session.scalars(select(DocumentRow).order_by(DocumentRow.created_at))]

    def document(self, document):
        with self.sessions() as session:
            row = session.get(DocumentRow, document)
            if row is None:
                raise KeyError('Document not found')
            return values(row)

    def runs(self, document=None):
        query = select(RunRow).order_by(RunRow.created_at)
        if document is not None:
            query = query.where(RunRow.document_id == document)
        with self.sessions() as session:
            return [values(row) for row in session.scalars(query)]

    def run(self, document, run_id):
        with self.sessions() as session:
            row = session.get(RunRow, run_id)
            if row is None or row.document_id != document:
                raise KeyError('Run not found')
            return values(row)

    def create_run(self, document, key, digest):
        with self.sessions.begin() as session:
            row = RunRow(id=str(uuid4()), document_id=document, request_key=key,
                         input_digest=digest, created_at=datetime.now(timezone.utc), status='receiving')
            session.add(row)
            session.flush()
            return values(row)

    def update_run(self, run_id, **changes):
        with self.sessions.begin() as session:
            row = session.get(RunRow, run_id)
            if row is None:
                raise KeyError('Run not found')
            for key, value in changes.items():
                setattr(row, key, value)
            session.flush()
            return values(row)
