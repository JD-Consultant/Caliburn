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
from typing import Callable, Protocol
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from jd_relational.application import prepare_edit, prepare_restore
from jd_relational.domain import DomainError
from jd_relational.transport import MANUAL_MODELS
from jd_relational.intents import AdmittedIdentity, BoundEdit, IntentValidationError
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

    def require_stopped(self, identity: AdmittedIdentity) -> None:
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


@dataclass(frozen=True)
class CatalogRecord:
    document_id: str
    title: str
    archived: bool
    metadata_version: int
    created_at: datetime
    updated_at: datetime


def _catalog_record(row):
    return CatalogRecord(row["id"], row["title"], row["archived"],
                         row["metadata_version"], row["created_at"], row["updated_at"])


def _catalog_id(value):
    try:
        if type(value) is not str or str(UUID(value)) != value:
            raise ValueError()
    except (TypeError, ValueError, AttributeError):
        raise StorageError("invalid_input") from None


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


class JdReader:
    """Current-document SQL reader; no writer authority or mutation methods."""

    def __init__(self, engine: sa.Engine):
        if engine.dialect.name != "postgresql" or engine.dialect.driver != "psycopg":
            raise ValueError("PostgreSQL with Psycopg is required for this tested adapter.")
        self.engine = engine

    def _connection(self, *, readonly=True):
        # Configure before the first SQL/autobegin. Separate readers from writers.
        return self.engine.connect().execution_options(
            isolation_level="REPEATABLE READ" if readonly else "READ COMMITTED",
            postgresql_readonly=readonly)

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

    def catalog_document(self, document_id: str) -> CatalogRecord:
        _catalog_id(document_id)
        try:
            with self._connection(readonly=True) as conn, conn.begin():
                row = conn.execute(sa.select(db.jd_document).where(
                    db.jd_document.c.id == document_id)).mappings().one_or_none()
                if row is None:
                    raise StorageError("document_missing")
                return _catalog_record(row)
        except StorageError:
            raise
        except Exception:
            raise StorageError("read_failed") from None

    def list_catalog(self, *, archived: bool | None = False, after: str | None = None,
                     limit: int = 100) -> tuple[CatalogRecord, ...]:
        if (type(limit) is not int or not 1 <= limit <= 101
                or archived is not None and type(archived) is not bool):
            raise StorageError("invalid_input")
        if after is not None:
            _catalog_id(after)
        statement = sa.select(db.jd_document).order_by(db.jd_document.c.id).limit(limit)
        if after is not None:
            statement = statement.where(db.jd_document.c.id > after)
        if archived is not None:
            statement = statement.where(db.jd_document.c.archived == archived)
        try:
            with self._connection(readonly=True) as conn, conn.begin():
                return tuple(_catalog_record(row) for row in conn.execute(statement).mappings())
        except Exception:
            raise StorageError("read_failed") from None

    def document_ids(self, *, after: str | None = None, limit: int = 100) -> tuple[str, ...]:
        """List all catalog IDs, including archived documents, without a writer.

        Each page is one short read-only transaction. A startup scan must keep
        catalog changes/new admission excluded until it has consumed every page;
        these keyset pages do not retain a database snapshot across calls.
        An empty page is not evidence about any document's pending operation.
        """
        try:
            if type(limit) is not int or not 1 <= limit <= 500:
                raise ValueError()
            if after is not None and (type(after) is not str or str(UUID(after)) != after):
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise StorageError("invalid_input") from None
        try:
            statement = sa.select(db.jd_document.c.id).order_by(db.jd_document.c.id).limit(limit)
            if after is not None:
                statement = statement.where(db.jd_document.c.id > after)
            with self._connection(readonly=True) as conn, conn.begin():
                result = tuple(conn.execute(statement).scalars())
                if any(type(value) is not str or str(UUID(value)) != value for value in result):
                    raise ValueError("invalid_stored_document_id")
                return result
        except Exception:
            raise StorageError("read_failed") from None


class JdStorage(JdReader):
    def __init__(self, engine: sa.Engine, authority: WriterAuthority):
        if not all(callable(getattr(authority, name, None))
                   for name in ("require_bound", "require_stopped")):
            raise ValueError("WriterAuthority is required for this write adapter.")
        super().__init__(engine)
        self.authority = authority

    def _connection(self, *, readonly=False):
        return super()._connection(readonly=readonly)

    @staticmethod
    def _operation(conn, document_id, operation_id):
        row = conn.execute(sa.select(db.jd_operation).where(db.jd_operation.c.document_id == document_id,
            db.jd_operation.c.operation_id == operation_id)).mappings().one_or_none()
        return SavedOperation.from_row(row) if row else None

    @staticmethod
    def _check_original(receipt, identity):
        if (receipt.document_id != identity.document_id or receipt.operation_id != identity.operation_id
                or receipt.request_digest != identity.request_digest or receipt.origin != identity.origin
                or receipt.ai_run_id != identity.ai_run_id or receipt.body.command_kind != identity.command_kind
                or (receipt.base_revision_id is not None and receipt.base_revision_id != identity.base_revision_id)):
            raise StorageError("operation_conflict")
        return WriteObservation(identity.document_id, identity.operation_id, receipt)

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

    def create_document(self, request_key: UUID, title: str, *,
                        catalog_guard: Callable[[], None] | None = None) -> str:
        """Internal primitive; App callers must use the owned runtime gate.

        The optional guard retains fixture/bootstrap compatibility. Public App
        composition never exposes this unguarded primitive as a service.
        """
        if not isinstance(request_key, UUID):
            raise StorageError("invalid_create_key")
        if catalog_guard is not None and not callable(catalog_guard):
            raise StorageError("invalid_input")
        title, digest = _catalog_digest(title)
        try:
            if catalog_guard is not None:
                catalog_guard()
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
                if catalog_guard is not None:
                    catalog_guard()
            return identity  # Only after outer transaction context exit confirmed COMMIT.
        except StorageError:
            raise
        except Exception:
            raise StorageError("create_unconfirmed") from None

    def update_catalog(self, document_id: str, metadata_version: int, *,
                       title: str | None = None, archived: bool | None = None,
                       catalog_guard: Callable[[], None]) -> CatalogRecord:
        """One explicit metadata intent, guarded CAS; never changes JD history.

        A stale version always fails, even if the value currently matches. A
        caller can reread actual state after uncertainty, but cannot attribute
        it to this request or silently update its precondition and retry.
        """
        _catalog_id(document_id)
        if (not callable(catalog_guard) or type(metadata_version) is not int
                or not 1 <= metadata_version <= 9007199254740991
                or (title is None) == (archived is None)
                or archived is not None and type(archived) is not bool):
            raise StorageError("invalid_input")
        if title is not None:
            try:
                title, _ = _catalog_digest(title)
            except StorageError:
                raise StorageError("invalid_input") from None
        try:
            catalog_guard()
            with self._connection() as conn, conn.begin():
                row, _ = self._lock_head(conn, document_id)
                catalog_guard()  # Ownership checked again after blocking SQL locks.
                if row["metadata_version"] != metadata_version:
                    raise StorageError("metadata_changed")
                desired = {"title": title} if title is not None else {"archived": archived}
                if any(row[key] != value for key, value in desired.items()):
                    if metadata_version == 9007199254740991:
                        raise StorageError("catalog_version_limit")
                    row = conn.execute(db.jd_document.update().where(
                        db.jd_document.c.id == document_id,
                        db.jd_document.c.metadata_version == metadata_version).values(
                            **desired, metadata_version=metadata_version + 1, updated_at=_now())
                        .returning(db.jd_document)).mappings().one()
                result = _catalog_record(row)
            return result  # COMMIT acknowledgement, not merely UPDATE RETURNING.
        except StorageError:
            raise
        except Exception:
            raise StorageError("catalog_unconfirmed") from None

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

    def lookup(self, identity: AdmittedIdentity) -> WriteObservation | None:
        """Read the original terminal before admission, without writer checks.

        None means an existing catalog document had no visible receipt in this
        short read-only transaction. A missing document cannot acquire pending
        metadata outside the catalog that startup recovery enumerates.
        It proves neither writer death nor absence after a write barrier, and
        cannot authorize recovery or replay. New execution still requires a
        durable descriptor and the real document owner.
        """
        try:
            if type(identity) is not AdmittedIdentity:
                raise IntentValidationError()
            identity.validate()
        except (IntentValidationError, TypeError, ValueError, AttributeError):
            raise StorageError("invalid_input") from None
        try:
            with self._connection(readonly=True) as conn, conn.begin():
                receipt = self._operation(conn, identity.document_id, identity.operation_id)
                if receipt is not None:
                    return self._check_original(receipt, identity)
                present = conn.execute(sa.select(db.jd_document.c.id).where(
                    db.jd_document.c.id == identity.document_id)).scalar_one_or_none()
                if present is None:
                    raise StorageError("document_missing")
                return None
        except StorageError as error:
            raise StorageError(error.code if error.code in {"operation_conflict", "document_missing"} else "read_failed") from None
        except Exception:
            raise StorageError("read_failed") from None

    @staticmethod
    def _base_if_known(conn, intent):
        return conn.execute(sa.select(db.jd_revision.c.revision_id).where(
            db.jd_revision.c.document_id == intent.document_id,
            db.jd_revision.c.revision_id == intent.base_revision_id)).scalar_one_or_none()

    @staticmethod
    def _insert_receipt(conn, identity: AdmittedIdentity, base, result, status, reinstated=None):
        body = body_for(identity.command_kind, status, reinstated)
        conn.execute(db.jd_operation.insert().values(document_id=identity.document_id,
            operation_id=identity.operation_id, request_digest=identity.request_digest,
            origin=identity.origin, ai_run_id=identity.ai_run_id,
            base_revision_id=base, result_revision_id=result, status=status,
            receipt=body.model_dump(mode="json"), created_at=_now()))
        return JdStorage._operation(conn, identity.document_id, identity.operation_id)

    
    @staticmethod
    def _undo_target(conn, intent, head):
        """The JD this document had before one AI turn wrote to it.

        The range is that turn's own committed operations, proven to be one
        unbroken chain that still ends exactly where the App said it did and
        where the document still is. A turn that wrote nothing, a chain broken
        by somebody else's edit, or a head that has moved all refuse: taking a
        turn back may never quietly discard what happened afterwards, and the
        range is never guessed from timestamps or from origin alone.
        """
        arguments = intent.command["arguments"]
        rows = conn.execute(sa.select(
            db.jd_operation.c.base_revision_id, db.jd_operation.c.result_revision_id).where(
            db.jd_operation.c.document_id == intent.document_id,
            db.jd_operation.c.ai_run_id == arguments["ai_run_id"],
            db.jd_operation.c.status == "committed")).mappings().all()
        rows = [row for row in rows if row["base_revision_id"] and row["result_revision_id"]]
        if not rows:
            raise DomainError("target_missing", "這一輪沒有對 JD 的已保存修改可以撤回。")
        broken = DomainError("stale_view", "這一輪的修改不連續或已不是目前版本，無法整輪撤回。")
        links = {row["base_revision_id"]: row["result_revision_id"] for row in rows}
        results = set(links.values())
        starts = [base for base in links if base not in results]
        if len(links) != len(rows) or len(starts) != 1:
            raise broken
        chain, node = [], starts[0]
        while node in links:
            node = links[node]
            chain.append(node)
        try:
            expected = UUID(arguments["expected_result_revision_id"])
        except (TypeError, ValueError):
            raise DomainError("invalid_input", "撤回目標不是一個版本識別。") from None
        if len(chain) != len(rows) or chain[-1] != expected or head["current_revision_id"] != expected:
            raise broken
        stored = conn.execute(sa.select(db.jd_revision.c.snapshot).where(
            db.jd_revision.c.document_id == intent.document_id,
            db.jd_revision.c.revision_id == starts[0])).scalar_one_or_none()
        if stored is None:
            raise DomainError("target_missing", "這一輪之前的版本已無法取得。")
        return stored, {"reinstated_revision_id": str(starts[0]),
                        "undone_ai_run_id": arguments["ai_run_id"]}

    @staticmethod
    def _restore_target(conn, intent):
        """This document's own saved revision, read from its immutable history.

        A revision identity means nothing outside the document that owns it, so
        one from anywhere else is simply not a target that exists here.
        """
        try:
            target = UUID(intent.command["arguments"]["target_revision_id"])
        except (KeyError, TypeError, ValueError):
            raise DomainError("target_missing", "還原目標不是這份文件的版本。") from None
        stored = conn.execute(sa.select(db.jd_revision.c.snapshot).where(
            db.jd_revision.c.document_id == intent.document_id,
            db.jd_revision.c.revision_id == target)).scalar_one_or_none()
        if stored is None:
            raise DomainError("target_missing", "還原目標不是這份文件的版本。")
        return stored, {"reinstated_revision_id": str(target)}

    def _edit_locked(self, conn, intent, document, head):
        base = self._base_if_known(conn, intent)
        try:
            self.authority.require_bound(intent)
            if document["archived"]:
                raise StorageError("writer_not_valid")
        except Exception:
            return self._insert_receipt(conn, intent.identity, base, None, "save_failed")
        if head["current_revision_id"] != intent.base_revision_id:
            return self._insert_receipt(conn, intent.identity, base, None, "stale_view")
        current = self._verified_current(conn, document, head)
        savepoint = conn.begin_nested()
        try:
            kind = intent.identity.command_kind
            # Restoring and undoing differ only in how the target revision is
            # proven; both then rebuild through the one restore service, and
            # both record which revision they proved so history can say so.
            reinstated = None
            if kind in {"restore_revision", "undo_ai_turn"}:
                stored, reinstated = (self._restore_target(conn, intent) if kind == "restore_revision"
                                      else self._undo_target(conn, intent, head))
                candidate = prepare_restore(current.domain, stored)
            else:
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
                # Nothing was put back, so nothing may claim it was.
                return self._insert_receipt(conn, intent.identity, base, base, "no_change")
            result = uuid4()
            conn.execute(db.jd_revision.insert().values(document_id=intent.document_id, revision_id=result,
                revision_number=head["revision_number"] + 1, parent_revision_id=base,
                origin=intent.origin, format_version=3, engine_profile="jd-relational-v1",
                snapshot=actual, content_digest=digest, created_at=_now()))
            receipt = self._insert_receipt(conn, intent.identity, base, result, "committed",
                                           reinstated)
            conn.execute(db.jd_head.update().where(db.jd_head.c.document_id == intent.document_id).values(
                current_revision_id=result, revision_number=head["revision_number"] + 1, updated_at=_now()))
            savepoint.commit()
            return receipt
        except DomainError as error:
            savepoint.rollback()
            return self._insert_receipt(conn, intent.identity, base, None, error.code)
        except IntegrityError as error:
            # Only this explicitly mapped dependency is a known user-facing constraint.
            if (getattr(error.orig, "sqlstate", None) == "23001"
                    and getattr(getattr(error.orig, "diag", None), "constraint_name", None) == "fk_jd_task_capability_capability"):
                savepoint.rollback()
                return self._insert_receipt(conn, intent.identity, base, None, "dependent_items")
            raise

    def execute(self, intent: BoundEdit) -> WriteObservation:
        """One admitted command, never an automatic retry or admission mechanism."""
        return self._transaction(intent, recovering=False)

    def reconcile_stopped(self, identity: AdmittedIdentity) -> WriteObservation:
        """Failure-only closure, requiring caller-owned stopped-writer proof first."""
        try:
            if type(identity) is not AdmittedIdentity:
                raise IntentValidationError()
            identity.validate()
        except (IntentValidationError, TypeError, ValueError, AttributeError):
            raise StorageError("invalid_input") from None
        try:
            self.authority.require_stopped(identity)
        except Exception:
            raise StorageError("writer_not_stopped") from None
        return self._transaction(identity, recovering=True)

    def _transaction(self, intent, *, recovering):
        identity = intent if recovering else intent.identity
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
                observed = self._check_original(receipt, identity)
                return observed
            if not recovering:
                self.authority.require_bound(intent)
            conn.execute(sa.text("SET LOCAL lock_timeout = '5s'"))
            document, head = self._lock_head(conn, intent.document_id)
            # A fresh READ COMMITTED statement after waiting for the same row locks.
            receipt = self._operation(conn, intent.document_id, intent.operation_id)
            if receipt:
                observed = self._check_original(receipt, identity)
                return observed
            absence_proven = True  # No terminal after this operation's document/head barrier.
            if recovering:
                self.authority.require_stopped(identity)
                receipt = self._insert_receipt(conn, identity, self._base_if_known(conn, identity), None, "save_failed")
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
