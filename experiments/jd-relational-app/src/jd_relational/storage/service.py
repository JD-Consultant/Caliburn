"""JD-specific transaction service over Core, with caller-owned writer authority.

No HTTP/LLM calls, source I/O, ref issuance, automatic migration or write retry.
The runtime must supply trusted admission and stopped-writer checks. SQL row
locks do not replace that lifecycle ownership or prove a worker has stopped.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
from time import perf_counter
from typing import Protocol
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from jd_relational.application import prepare_edit
from jd_relational.domain import DomainError
from jd_relational.intents import BoundEdit
from jd_relational.snapshots import empty_domain, snapshot_from_domain, domain_from_snapshot, snapshot_digest
from . import schema as db
from .receipts import SavedOperation, WriteObservation, body_for
from .rows import read_domain, write_candidate


LOG = logging.getLogger("caliburn.jd.storage")


class StorageError(ValueError):
    """Fixed safe code only; raw driver parameters/exception chains stay private."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class WriterAuthority(Protocol):
    def require_bound(self, intent: BoundEdit) -> None:
        """Local nonblocking ownership check; raise if this admitted writer is invalid."""

    def require_stopped(self, intent: BoundEdit) -> None:
        """Require authoritative proof the original writer cannot submit more SQL."""


@dataclass(frozen=True)
class CurrentDocument:
    document_id: str
    title: str
    archived: bool
    metadata_version: int
    revision_id: UUID
    revision_number: int
    snapshot: dict

    @property
    def domain(self) -> dict:
        return domain_from_snapshot(self.snapshot, str(self.revision_id))


def _now():
    return datetime.now(timezone.utc)


def _catalog_digest(title):
    if not isinstance(title, str) or not title.strip() or "\x00" in title:
        raise StorageError("invalid_title")
    title = title.replace("\r\n", "\n").replace("\r", "\n")
    try:
        encoded = json.dumps({"title": title}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except UnicodeError:
        raise StorageError("invalid_title") from None
    if len(encoded) > 64 * 1024:
        raise StorageError("invalid_title")
    return title, hashlib.sha256(encoded).hexdigest()


class JdStorage:
    def __init__(self, engine: sa.Engine, authority: WriterAuthority):
        if engine.dialect.name != "postgresql" or engine.dialect.driver != "psycopg":
            raise ValueError("PostgreSQL with Psycopg is required for this tested adapter.")
        self.engine = engine
        self.authority = authority

    def _connection(self, *, readonly=False):
        # Configure before the first SQL/autobegin. Separate readers from writers.
        return self.engine.connect().execution_options(
            isolation_level="REPEATABLE READ" if readonly else "READ COMMITTED",
            postgresql_readonly=readonly)

    @staticmethod
    def _operation(conn, document_id, operation_id):
        row = conn.execute(sa.select(db.jd_operation).where(db.jd_operation.c.document_id == document_id,
            db.jd_operation.c.operation_id == operation_id)).mappings().one_or_none()
        return SavedOperation.from_row(row) if row else None

    @staticmethod
    def _check_original(receipt, intent):
        if receipt.request_digest != intent.request_digest:
            raise StorageError("operation_conflict")
        return WriteObservation(intent.document_id, intent.operation_id, receipt)

    @staticmethod
    def _lock_head(conn, document_id):
        document = conn.execute(sa.select(db.jd_document).where(db.jd_document.c.id == document_id)
                                .with_for_update()).mappings().one_or_none()
        if document is None:
            raise StorageError("document_missing")
        head = conn.execute(sa.select(db.jd_head).where(db.jd_head.c.document_id == document_id)
                            .with_for_update()).mappings().one_or_none()
        if head is None:
            raise StorageError("head_missing")
        return document, head

    @staticmethod
    def _verified_current(conn, document, head):
        revision = conn.execute(sa.select(db.jd_revision).where(
            db.jd_revision.c.document_id == document["id"],
            db.jd_revision.c.revision_id == head["current_revision_id"])).mappings().one()
        current = read_domain(conn, document["id"], str(head["current_revision_id"]))
        snapshot = snapshot_from_domain(current)
        if (revision["revision_number"] != head["revision_number"] or revision["format_version"] != 3
                or revision["engine_profile"] != "jd-relational-v1"
                or snapshot_digest(snapshot) != revision["content_digest"]
                or snapshot != revision["snapshot"]):
            raise StorageError("stored_content_mismatch")
        return CurrentDocument(document["id"], document["title"], document["archived"], document["metadata_version"],
                               head["current_revision_id"], head["revision_number"], snapshot)

    def read_current(self, document_id: str) -> CurrentDocument:
        try:
            with self._connection(readonly=True) as conn, conn.begin():
                doc = conn.execute(sa.select(db.jd_document).where(db.jd_document.c.id == document_id)).mappings().one_or_none()
                head = conn.execute(sa.select(db.jd_head).where(db.jd_head.c.document_id == document_id)).mappings().one_or_none()
                if doc is None or head is None:
                    raise StorageError("document_missing")
                return self._verified_current(conn, doc, head)
        except StorageError:
            raise
        except Exception:
            raise StorageError("read_failed") from None

    def create_document(self, request_key: UUID, title: str) -> str:
        """Commit a fresh empty JD once; a lost response is looked up by this key."""
        if not isinstance(request_key, UUID):
            raise StorageError("invalid_create_key")
        title, digest = _catalog_digest(title)
        try:
            with self._connection() as conn, conn.begin():
                identity = str(uuid4())
                now = _now()
                created = conn.execute(insert(db.jd_document).values(id=identity, title=title,
                    metadata_version=1, create_request_key=str(request_key), create_payload_digest=digest,
                    created_at=now, updated_at=now).on_conflict_do_nothing(
                        index_elements=[db.jd_document.c.create_request_key]).returning(db.jd_document.c.id)).scalar_one_or_none()
                if created is None:
                    row = conn.execute(sa.select(db.jd_document).where(
                        db.jd_document.c.create_request_key == str(request_key))).mappings().one()
                    if row["create_payload_digest"] != digest:
                        raise StorageError("operation_conflict")
                    identity = row["id"]
                else:
                    initial = uuid4()
                    conn.execute(db.jd_profile.insert().values(document_id=identity))
                    snapshot = snapshot_from_domain(empty_domain(identity, str(initial)))
                    conn.execute(db.jd_revision.insert().values(document_id=identity, revision_id=initial,
                        revision_number=1, parent_revision_id=None, origin="initial", format_version=3,
                        engine_profile="jd-relational-v1", snapshot=snapshot,
                        content_digest=snapshot_digest(snapshot), created_at=now))
                    conn.execute(db.jd_head.insert().values(document_id=identity, current_revision_id=initial,
                                                            revision_number=1, updated_at=now))
            return identity  # Only after outer transaction context exit confirmed COMMIT.
        except StorageError:
            raise
        except Exception:
            raise StorageError("create_unconfirmed") from None

    def lookup_creation(self, request_key: UUID, title: str) -> str | None:
        if not isinstance(request_key, UUID):
            raise StorageError("invalid_create_key")
        _, digest = _catalog_digest(title)
        try:
            with self._connection(readonly=True) as conn, conn.begin():
                row = conn.execute(sa.select(db.jd_document).where(
                    db.jd_document.c.create_request_key == str(request_key))).mappings().one_or_none()
                if row and row["create_payload_digest"] != digest:
                    raise StorageError("operation_conflict")
                return row["id"] if row else None
        except StorageError:
            raise
        except Exception:
            raise StorageError("read_failed") from None

    def get_operation(self, document_id: str, operation_id: UUID) -> SavedOperation | None:
        try:
            with self._connection(readonly=True) as conn, conn.begin():
                return self._operation(conn, document_id, operation_id)
        except Exception:
            raise StorageError("read_failed") from None

    @staticmethod
    def _base_if_known(conn, intent):
        return conn.execute(sa.select(db.jd_revision.c.revision_id).where(
            db.jd_revision.c.document_id == intent.document_id,
            db.jd_revision.c.revision_id == intent.base_revision_id)).scalar_one_or_none()

    @staticmethod
    def _insert_receipt(conn, intent, base, result, status):
        body = body_for(intent.command["tool"], status)
        conn.execute(db.jd_operation.insert().values(document_id=intent.document_id,
            operation_id=intent.operation_id, request_digest=intent.request_digest,
            origin=intent.origin, ai_run_id=intent.ai_run_id,
            base_revision_id=base, result_revision_id=result, status=status,
            receipt=body.model_dump(mode="json"), created_at=_now()))
        return JdStorage._operation(conn, intent.document_id, intent.operation_id)

    def _edit_locked(self, conn, intent, document, head):
        base = self._base_if_known(conn, intent)
        try:
            self.authority.require_bound(intent)
            if document["archived"]:
                raise StorageError("writer_not_valid")
        except Exception:
            return self._insert_receipt(conn, intent, base, None, "save_failed")
        if head["current_revision_id"] != intent.base_revision_id:
            return self._insert_receipt(conn, intent, base, None, "stale_view")
        current = self._verified_current(conn, document, head)
        savepoint = conn.begin_nested()
        try:
            candidate = prepare_edit(current.domain, intent.command, intent.context,
                                     request_id=intent.operation_id)
            wanted = snapshot_from_domain(candidate)
            write_candidate(conn, current.domain, candidate)
            actual = snapshot_from_domain(read_domain(conn, intent.document_id, str(intent.base_revision_id)))
            if actual != wanted:
                raise StorageError("candidate_storage_mismatch")
            digest = snapshot_digest(actual)
            if digest == snapshot_digest(current.snapshot):
                savepoint.rollback()
                return self._insert_receipt(conn, intent, base, base, "no_change")
            result = uuid4()
            conn.execute(db.jd_revision.insert().values(document_id=intent.document_id, revision_id=result,
                revision_number=head["revision_number"] + 1, parent_revision_id=base,
                origin=intent.origin, format_version=3, engine_profile="jd-relational-v1",
                snapshot=actual, content_digest=digest, created_at=_now()))
            receipt = self._insert_receipt(conn, intent, base, result, "committed")
            conn.execute(db.jd_head.update().where(db.jd_head.c.document_id == intent.document_id).values(
                current_revision_id=result, revision_number=head["revision_number"] + 1, updated_at=_now()))
            savepoint.commit()
            return receipt
        except DomainError as error:
            savepoint.rollback()
            return self._insert_receipt(conn, intent, base, None, error.code)
        except IntegrityError as error:
            # Only this explicitly mapped dependency is a known user-facing constraint.
            if (getattr(error.orig, "sqlstate", None) == "23001"
                    and getattr(getattr(error.orig, "diag", None), "constraint_name", None) == "fk_jd_task_capability_capability"):
                savepoint.rollback()
                return self._insert_receipt(conn, intent, base, None, "dependent_items")
            raise

    def execute(self, intent: BoundEdit) -> WriteObservation:
        """One admitted command, never an automatic retry or admission mechanism."""
        return self._transaction(intent, recovering=False)

    def reconcile_stopped(self, intent: BoundEdit) -> WriteObservation:
        """Failure-only closure, requiring caller-owned stopped-writer proof first."""
        try:
            self.authority.require_stopped(intent)
        except Exception:
            raise StorageError("writer_not_stopped") from None
        return self._transaction(intent, recovering=True)

    def _transaction(self, intent, *, recovering):
        started = perf_counter()
        phase = "connecting"
        conn = tx = None
        observed = None
        absence_proven = False
        unchanged_candidate = False
        conflict = False
        try:
            conn = self._connection()
            tx = conn.begin()
            phase = "working"
            receipt = self._operation(conn, intent.document_id, intent.operation_id)
            if receipt:
                observed = self._check_original(receipt, intent)
                return observed
            if not recovering:
                self.authority.require_bound(intent)
            conn.execute(sa.text("SET LOCAL lock_timeout = '5s'"))
            document, head = self._lock_head(conn, intent.document_id)
            # A fresh READ COMMITTED statement after waiting for the same row locks.
            receipt = self._operation(conn, intent.document_id, intent.operation_id)
            if receipt:
                observed = self._check_original(receipt, intent)
                return observed
            absence_proven = True  # No terminal after this operation's document/head barrier.
            if recovering:
                self.authority.require_stopped(intent)
                receipt = self._insert_receipt(conn, intent, self._base_if_known(conn, intent), None, "save_failed")
            else:
                receipt = self._edit_locked(conn, intent, document, head)
            unchanged_candidate = receipt.status != "committed"
            phase = "committing"
            tx.commit()
            phase = "committed"
            observed = WriteObservation(intent.document_id, intent.operation_id, receipt)
            return observed
        except StorageError as error:
            if error.code == "operation_conflict":
                conflict = True
                raise StorageError("operation_conflict") from None
            observed = self._unresolved(intent, phase, tx, absence_proven, unchanged_candidate)
            return observed
        except Exception:
            observed = self._unresolved(intent, phase, tx, absence_proven, unchanged_candidate)
            return observed
        finally:
            # Cleanup errors cannot erase a receipt already observed or a COMMIT
            # uncertainty. Closing performs no write replay or extra connection.
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            try:
                LOG.log(logging.INFO if observed and observed.confirmed else logging.WARNING,
                    "JD storage observation", extra={"event_name": "jd.storage.observe",
                        "document_id": intent.document_id, "operation_id": str(intent.operation_id),
                        "phase": phase, "recovery": recovering,
                        "outcome": observed.status if observed else "operation_conflict" if conflict else "not_observed",
                        "receipt_confirmed": bool(observed and observed.confirmed),
                        "duration_ms": round((perf_counter() - started) * 1000, 3)})
            except Exception:
                pass  # Broken diagnostics cannot replace a save/reconciliation result.

    @staticmethod
    def _unresolved(intent, phase, tx, absence_proven, unchanged_candidate):
        if not absence_proven:
            # A failed lookup/connection says nothing about an earlier attempt
            # with this identity; it may already have committed.
            effect = "unknown"
        elif phase in {"committing", "committed"}:
            effect = "unchanged" if unchanged_candidate else "unknown"
        else:
            try:
                tx.rollback()
                effect = "unchanged"
            except Exception:
                effect = "unknown"
        return WriteObservation(intent.document_id, intent.operation_id, None, effect)
