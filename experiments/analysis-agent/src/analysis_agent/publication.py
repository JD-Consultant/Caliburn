"""Runtime-only publication metadata. Content stays in the official Store.

Only short ORM transactions touch the head. No model calls, automatic retries,
semantic merge, SQL bulk writes or process-local lock as a correctness boundary.
"""

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import JSON, Integer, String, Text, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.orm.exc import StaleDataError

from analysis_agent.memory import MemoryArtifacts, MemoryVersion
from analysis_agent.sources import parse_reference


class Base(DeclarativeBase):
    pass


class HeadRow(Base):
    __tablename__ = "q019_document_memory_head"
    document_id: Mapped[str] = mapped_column(String, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    memory_version: Mapped[str] = mapped_column(String, nullable=False)
    processed_source: Mapped[str | None] = mapped_column(Text)
    last_operation_id: Mapped[str] = mapped_column(String, nullable=False)
    __mapper_args__ = {"version_id_col": revision}


class ReceiptRow(Base):
    __tablename__ = "q019_memory_publication_receipt"
    document_id: Mapped[str] = mapped_column(String, primary_key=True)
    operation_id: Mapped[str] = mapped_column(String, primary_key=True)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    base_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    result_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    memory_version: Mapped[str] = mapped_column(String, nullable=False)
    processed_source: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    repair_sources: Mapped[list[str]] = mapped_column(JSON, nullable=False)


@dataclass(frozen=True)
class PublishedHead:
    revision: int
    memory: MemoryVersion
    processed_source: str | None


@dataclass(frozen=True)
class PublishRequest:
    operation_id: str
    memory: MemoryVersion
    expected_revision: int
    kind: Literal["consolidation", "repair"]
    artifact_digest: str
    processed_source: str | None = None
    repair_sources: tuple[str, ...] = ()

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@dataclass(frozen=True)
class Receipt:
    operation_id: str
    base_revision: int
    result: PublishedHead
    kind: str
    repair_sources: tuple[str, ...]
    request_digest: str


class StalePublication(Exception):
    def __init__(self, current: PublishedHead | None):
        super().__init__("Memory changed; reload and reconsider content, not just its version")
        self.current = current


class PublicationUncertain(Exception):
    """Do not infer failure or allocate a new operation. Reconcile/retry same request."""


class PublicationStore:
    def __init__(self, engine: Engine, artifacts: MemoryArtifacts):
        self.engine, self.artifacts = engine, artifacts
        self.document_id = artifacts.document_id
        self.sessions = sessionmaker(engine, expire_on_commit=False)

    def setup(self):
        """Explicit isolated schema initialization, never performed inside a run."""
        Base.metadata.create_all(self.engine)

    def _head(self, row) -> PublishedHead:
        revision = row.revision if isinstance(row, HeadRow) else row.result_revision
        return PublishedHead(revision, MemoryVersion(row.document_id, row.memory_version), row.processed_source)

    def _receipt(self, row: ReceiptRow) -> Receipt:
        return Receipt(row.operation_id, row.base_revision, self._head(row), row.kind, tuple(row.repair_sources), row.request_digest)

    def current(self) -> PublishedHead | None:
        with self.sessions() as session:
            row = session.get(HeadRow, self.document_id)
            return self._head(row) if row else None

    def receipt(self, operation_id: str) -> Receipt | None:
        with self.sessions() as session:
            row = session.get(ReceiptRow, (self.document_id, operation_id))
            return self._receipt(row) if row else None

    def _validate(self, request: PublishRequest):
        if request.memory.document_id != self.document_id:
            raise ValueError("Publication belongs to another document")
        UUID(request.operation_id)
        if type(request.expected_revision) is not int or request.expected_revision < 0:
            raise ValueError("Expected non-negative base revision")
        if request.kind not in ("consolidation", "repair"):
            raise ValueError("Unknown publication kind")
        if request.kind == "consolidation" and not request.processed_source:
            raise ValueError("Consolidation requires its completed source window")
        if request.kind == "repair" and request.processed_source is not None:
            raise ValueError("Repair must not advance the background source cursor")
        references = (*request.repair_sources, *((request.processed_source,) if request.processed_source else ()))
        for reference in references:
            parse_reference(reference, self.document_id)

    def prepare(self, memory: MemoryVersion, *, expected_revision: int, kind: str,
                processed_source: str | None = None, repair_sources: tuple[str, ...] = ()) -> PublishRequest:
        request = PublishRequest(str(uuid4()), memory, expected_revision, kind,
                                 self.artifacts.verify_version(memory), processed_source, tuple(repair_sources))
        self._validate(request)
        return request

    @staticmethod
    def _match(receipt: Receipt | None, request: PublishRequest) -> PublishedHead | None:
        if receipt is None:
            return None
        if receipt.request_digest != request.digest():
            raise ValueError("Same operation ID cannot carry a different publication")
        return receipt.result

    def publish(self, request: PublishRequest) -> PublishedHead:
        self._validate(request)
        try:
            return self._publish(request)
        except IntegrityError:
            raise  # known unrelated constraint failure, not a lost commit reply
        except DBAPIError as error:
            # Includes both initial reconciliation and queries after rollback.
            # Neither query failure proves an earlier attempt did not commit.
            raise PublicationUncertain("Database result not confirmed; reconcile or retry the same request") from error

    def _publish(self, request: PublishRequest) -> PublishedHead:
        # Receipt first: a known successful historical operation stays successful
        # even after later heads; returning it does not reselect that old head.
        if result := self._match(self.receipt(request.operation_id), request):
            return result
        if self.artifacts.verify_version(request.memory) != request.artifact_digest:
            raise ValueError("Prepared Memory content changed; publication rejected")
        try:
            with self.sessions.begin() as session:
                prior = session.get(ReceiptRow, (self.document_id, request.operation_id))
                if prior is not None:
                    return self._match(self._receipt(prior), request)
                row = session.get(HeadRow, self.document_id)
                if (row.revision if row else 0) != request.expected_revision:
                    raise StalePublication(self._head(row) if row else None)
                if row is None:
                    row = HeadRow(document_id=self.document_id, memory_version=request.memory.version_id,
                                  last_operation_id=request.operation_id)
                    session.add(row)
                row.memory_version = request.memory.version_id
                row.last_operation_id = request.operation_id  # forces CAS even for content no-op
                if request.kind == "consolidation":
                    row.processed_source = request.processed_source
                session.flush()  # official version_id_col validates/increments revision
                result = self._head(row)
                session.add(ReceiptRow(document_id=self.document_id, operation_id=request.operation_id,
                    request_digest=request.digest(), base_revision=request.expected_revision,
                    result_revision=result.revision, memory_version=result.memory.version_id,
                    processed_source=result.processed_source, kind=request.kind,
                    repair_sources=list(request.repair_sources)))
            return result
        except (StalePublication, StaleDataError, IntegrityError) as error:
            # Context has rolled back. A new Session sees a concurrent winner's
            # receipt; never continue/commit the failed transaction.
            if result := self._match(self.receipt(request.operation_id), request):
                return result
            if isinstance(error, IntegrityError) and getattr(error.orig, "sqlstate", None) != "23505":
                raise
            raise StalePublication(self.current()) from error

    def repair_receipts(self, *, after_revision: int, through_revision: int, limit: int = 20) -> list[Receipt]:
        if not 1 <= limit <= 100 or not 0 <= after_revision <= through_revision:
            raise ValueError("Invalid receipt page bounds")
        with self.sessions() as session:
            rows = session.scalars(select(ReceiptRow).where(
                ReceiptRow.document_id == self.document_id, ReceiptRow.kind == "repair",
                ReceiptRow.result_revision > after_revision, ReceiptRow.result_revision <= through_revision,
            ).order_by(ReceiptRow.result_revision).limit(limit))
            return [self._receipt(row) for row in rows]
