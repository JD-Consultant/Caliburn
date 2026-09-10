"""Small application routing projection; message bodies live only in Saver.

No model calls or long transactions here. Single-process admission is owned by
AnalysisService, not claimed as a distributed queue or a second workflow engine.
"""
from datetime import datetime, timezone
from uuid import uuid4
import hashlib

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class DocumentRow(Base):
    __tablename__ = 'q019_document'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')
    metadata_version: Mapped[int] = mapped_column(Integer, default=1, server_default='1')
    create_request_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    create_payload_digest: Mapped[str | None] = mapped_column(String(64))


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
    result = {column.name: getattr(row, column.name) for column in row.__table__.columns}
    # SQLite fixed-transport tests lose timezone metadata; all writes are UTC.
    if isinstance(result.get('created_at'), datetime) and result['created_at'].tzinfo is None:
        result['created_at'] = result['created_at'].replace(tzinfo=timezone.utc)
    return result


class Catalog:
    def __init__(self, engine):
        self.engine = engine
        self.sessions = sessionmaker(engine, expire_on_commit=False)

    def setup(self):
        Base.metadata.create_all(self.engine)

    def upgrade_document_metadata(self):
        """Explicit additive isolated PG setup; preserves existing catalog rows."""
        if self.engine.dialect.name != 'postgresql':
            raise ValueError('Metadata upgrade is PostgreSQL only')
        with self.engine.begin() as conn:
            for column in ('archived BOOLEAN NOT NULL DEFAULT false',
                           'metadata_version INTEGER NOT NULL DEFAULT 1',
                           'create_request_key VARCHAR(128)', 'create_payload_digest VARCHAR(64)'):
                conn.execute(text('ALTER TABLE q019_document ADD COLUMN IF NOT EXISTS '+column))
            conn.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS q019_document_create_key ON q019_document(create_request_key)'))

    def created_by_request(self, request_key, title, *, session=None):
        if request_key is None:
            return None
        if session is None:
            with self.sessions() as owned:
                return self.created_by_request(request_key, title, session=owned)
        row = session.scalar(select(DocumentRow).where(DocumentRow.create_request_key == request_key))
        if row is None:
            return None
        if row.create_payload_digest != hashlib.sha256(title.encode()).hexdigest():
            from analysis_agent.service import ServiceConflict
            raise ServiceConflict('Create request key belongs to different input')
        return values(row)

    def create_document(self, title, *, session=None, request_key=None):
        if session is None:
            with self.sessions.begin() as owned_session:
                return self.create_document(title, session=owned_session, request_key=request_key)
        existing = self.created_by_request(request_key, title, session=session)
        if existing:
            return existing
        row = DocumentRow(id=str(uuid4()), title=title, created_at=datetime.now(timezone.utc),
            create_request_key=request_key, create_payload_digest=hashlib.sha256(title.encode()).hexdigest() if request_key else None)
        session.add(row)
        session.flush()
        return values(row)

    def update_document(self, document, command):
        from analysis_agent.service import ServiceConflict
        with self.sessions.begin() as session:
            row = session.scalar(select(DocumentRow).where(DocumentRow.id == document).with_for_update())
            if row is None:
                raise KeyError('Document not found')
            if row.metadata_version != command['expected_metadata_version']:
                raise ServiceConflict('Document metadata changed; reread current metadata')
            field = 'title' if command['command'] == 'rename' else 'archived'
            if getattr(row, field) != command[field]:
                setattr(row, field, command[field])
                row.metadata_version += 1
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
