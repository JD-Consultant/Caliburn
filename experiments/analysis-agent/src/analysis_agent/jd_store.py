"""The sole JD SQL owner. Immutable revisions/receipts, one catalog engine."""
from contextlib import contextmanager
from dataclasses import replace
import math
from threading import Timer
import time
from uuid import uuid4

from sqlalchemy import (MetaData, Table, Column, String, Text, Integer, DateTime, CheckConstraint,
                        ForeignKeyConstraint, Index, select, text, bindparam, func)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from analysis_agent.catalog import DocumentRow
from analysis_agent.jd_contract import outcome_to_wire, outcome_from_row
from analysis_agent.jd_types import JdScope, JdRevision, JdWriteOutcome, JdMissing, JdHistory

metadata = MetaData()
catalog_table = DocumentRow.__table__.to_metadata(metadata)
revision = Table('jd_revision', metadata,
    Column('document_id', String, primary_key=True), Column('revision_id', UUID(as_uuid=True), primary_key=True),
    Column('parent_revision_id', UUID(as_uuid=True)), Column('origin', Text, nullable=False),
    Column('format_version', Integer, nullable=False), Column('engine_profile', Text, nullable=False),
    Column('value', JSONB, nullable=False), Column('created_at', DateTime(timezone=True), nullable=False, server_default=func.now()),
    ForeignKeyConstraint(['document_id'], ['q019_document.id']),
    ForeignKeyConstraint(['document_id', 'parent_revision_id'], ['jd_revision.document_id', 'jd_revision.revision_id']),
    CheckConstraint("origin IN ('initial','ai','manual')"),
    CheckConstraint("(origin='initial') = (parent_revision_id IS NULL)"),
    CheckConstraint('parent_revision_id IS NULL OR parent_revision_id <> revision_id'),
    CheckConstraint("format_version=2 AND engine_profile='jd-plate-clean-v2'"),
    CheckConstraint("(jsonb_typeof(value)='array' AND jsonb_array_length(value)>0) IS TRUE"))
Index('jd_one_initial', revision.c.document_id, unique=True, postgresql_where=revision.c.origin == 'initial')
Index('jd_one_successor', revision.c.document_id, revision.c.parent_revision_id, unique=True,
      postgresql_where=revision.c.parent_revision_id.is_not(None))

head = Table('jd_head', metadata,
    Column('document_id', String, primary_key=True), Column('current_revision_id', UUID(as_uuid=True), nullable=False),
    ForeignKeyConstraint(['document_id'], ['q019_document.id']),
    ForeignKeyConstraint(['document_id', 'current_revision_id'], ['jd_revision.document_id', 'jd_revision.revision_id']))

operation = Table('jd_operation', metadata,
    Column('document_id', String, primary_key=True), Column('operation_id', UUID(as_uuid=True), primary_key=True),
    Column('request_digest', Text, nullable=False), Column('origin', Text, nullable=False),
    Column('base_revision_id', UUID(as_uuid=True)), Column('result_revision_id', UUID(as_uuid=True)),
    Column('status', Text, nullable=False), Column('receipt', JSONB, nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False, server_default=func.now()),
    ForeignKeyConstraint(['document_id'], ['q019_document.id']),
    ForeignKeyConstraint(['document_id', 'base_revision_id'], ['jd_revision.document_id', 'jd_revision.revision_id']),
    ForeignKeyConstraint(['document_id', 'result_revision_id'], ['jd_revision.document_id', 'jd_revision.revision_id']),
    CheckConstraint("origin IN ('ai','manual')"),
    CheckConstraint("request_digest ~ '^[0-9a-f]{64}$'"),
    CheckConstraint("status IN ('committed','no_change','invalid_input','unsupported_content','target_missing','stale_base','engine_failed','save_failed')"),
    CheckConstraint("""(jsonb_typeof(receipt)='object'
      AND receipt->>'status'=status AND receipt->>'receipt_durability'='confirmed'
      AND jsonb_typeof(receipt->'operation_ref')='string' AND length(receipt->>'operation_ref')>0
      AND CASE WHEN status IN ('committed','no_change') THEN
        base_revision_id IS NOT NULL AND result_revision_id IS NOT NULL
        AND jsonb_typeof(receipt->'base_revision_ref')='string' AND length(receipt->>'base_revision_ref')>0
        AND jsonb_typeof(receipt->'result_revision_ref')='string' AND length(receipt->>'result_revision_ref')>0
        AND jsonb_typeof(receipt->'change_ref')='string' AND length(receipt->>'change_ref')>0
        AND receipt->'error'='null'::jsonb AND jsonb_typeof(receipt->'actual_changes')='object'
        AND receipt->'actual_changes'->>'origin'=origin
        AND receipt->'actual_changes'->>'before_revision_ref'=receipt->>'base_revision_ref'
        AND receipt->'actual_changes'->>'after_revision_ref'=receipt->>'result_revision_ref'
        AND CASE WHEN status='committed' THEN result_revision_id<>base_revision_id
          AND receipt->>'document_effect'='committed'
        ELSE result_revision_id=base_revision_id AND receipt->>'document_effect'='unchanged'
          AND receipt->>'base_revision_ref'=receipt->>'result_revision_ref'
          AND receipt->'actual_changes'->'affected_element_ids'='[]'::jsonb
          AND receipt->'actual_changes'->'native_operations'='null'::jsonb END
      ELSE result_revision_id IS NULL AND receipt->>'document_effect'='unchanged'
        AND receipt->'result_revision_ref'='null'::jsonb AND receipt->'change_ref'='null'::jsonb
        AND receipt->'actual_changes'='null'::jsonb AND jsonb_typeof(receipt->'error')='object'
        AND CASE WHEN base_revision_id IS NULL THEN receipt->'base_revision_ref'='null'::jsonb
          ELSE jsonb_typeof(receipt->'base_revision_ref')='string' AND length(receipt->>'base_revision_ref')>0 END
      END) IS TRUE""", name='jd_receipt_columns'))
Index('jd_one_producer', operation.c.document_id, operation.c.result_revision_id, unique=True,
      postgresql_where=operation.c.status == 'committed')


def failure(intent, status, *, base_id=None, confirmed=True, code=None, command_index=None):
    action = {'invalid_input': 'correct_arguments', 'unsupported_content': 'correct_arguments',
              'target_missing': 'reread_current', 'stale_base': 'reread_current'}.get(status, 'stop')
    return JdWriteOutcome(intent.scope, intent.operation_id, base_id, None, status, intent.origin,
        durability='confirmed' if confirmed else 'unconfirmed', error_code=code or status,
        error_message='JD operation did not complete.', command_index=command_index,
        next_action=action if confirmed else 'reconcile_operation')


class JdStore:
    def __init__(self, engine, *, timeout=30):
        if engine.dialect.name != 'postgresql':
            raise ValueError('JD authority requires the catalog PostgreSQL engine')
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('SQL budget must be positive and finite')
        self.engine, self.timeout = engine, timeout

    def setup(self):
        metadata.create_all(self.engine, tables=[revision, head, operation])

    @contextmanager
    def _connection(self):
        deadline = time.monotonic() + self.timeout
        with self.engine.connect() as conn:
            if time.monotonic() >= deadline:
                raise TimeoutError('JD SQL connection budget exhausted')
            # A single supervisor cancels the current driver operation. Statement
            # limits below are also reduced before every statement, not reset.
            driver = conn.connection.driver_connection
            timer = Timer(max(.001, deadline - time.monotonic()), driver.cancel)
            timer.daemon = True
            timer.start()
            try:
                yield conn, deadline
            finally:
                timer.cancel()
                timer.join()

    def _execute(self, conn, deadline, statement, params=None):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('JD SQL attempt budget exhausted')
        milliseconds = max(1, int(remaining * 1000))
        conn.execute(text("SELECT set_config('statement_timeout', :s, true), set_config('lock_timeout', :l, true)"),
                     {'s': str(min(10000, milliseconds)), 'l': str(min(5000, milliseconds))})
        if time.monotonic() >= deadline:
            raise TimeoutError('JD SQL attempt budget exhausted')
        return conn.execute(statement, params or {})

    def _scope(self, conn, deadline, scope):
        if self._execute(conn, deadline, select(catalog_table.c.id).where(catalog_table.c.id == scope.document_id)).first() is None:
            raise JdMissing('Document not found')

    def _revision(self, conn, deadline, scope, revision_id):
        row = self._execute(conn, deadline, select(revision).where(
            revision.c.document_id == scope.document_id, revision.c.revision_id == revision_id)).mappings().first()
        if row is None:
            raise JdMissing('Revision not found')
        return JdRevision(scope, row['revision_id'], row['parent_revision_id'], row['origin'], row['value'])

    def current(self, scope):
        with self._connection() as (conn, deadline):
            self._scope(conn, deadline, scope)
            row = self._execute(conn, deadline, select(revision).join(head,
                (head.c.document_id == revision.c.document_id) & (head.c.current_revision_id == revision.c.revision_id))
                .where(head.c.document_id == scope.document_id)).mappings().first()
            if row is None:
                raise JdMissing('JD head not found')
            return JdRevision(scope, row['revision_id'], row['parent_revision_id'], row['origin'], row['value'])

    def revision(self, scope, revision_id):
        with self._connection() as (conn, deadline):
            self._scope(conn, deadline, scope)
            return self._revision(conn, deadline, scope, revision_id)

    def _receipt(self, conn, deadline, scope, operation_id, digest=None):
        row = self._execute(conn, deadline, select(operation).where(operation.c.document_id == scope.document_id,
                             operation.c.operation_id == operation_id)).mappings().first()
        if row is None:
            return None
        result = outcome_from_row(scope, row)
        if digest is not None and row['request_digest'] != digest:
            return replace(result, status='operation_conflict', result_id=None, operations=None,
                           affected_ids=[], error_code='operation_conflict', error_message='Operation payload differs.', next_action='stop')
        return result

    def receipt(self, scope, operation_id, digest=None):
        with self._connection() as (conn, deadline):
            self._scope(conn, deadline, scope)
            return self._receipt(conn, deadline, scope, operation_id, digest)

    def create_document(self, catalog, title, value):
        if catalog.engine is not self.engine:
            raise ValueError('Catalog engine mismatch')
        with self._connection() as (conn, deadline), conn.begin():
            # Configure the remaining statement budget before the one catalog
            # INSERT; subsequent JD writes each lower it again.
            self._execute(conn, deadline, text('SELECT 1'))
            with Session(bind=conn) as session:
                document = catalog.create_document(title, session=session)
            scope, initial = JdScope(document['id']), uuid4()
            self._execute(conn, deadline, revision.insert().values(document_id=scope.document_id, revision_id=initial,
                parent_revision_id=None, origin='initial', format_version=2, engine_profile='jd-plate-clean-v2', value=value))
            self._execute(conn, deadline, head.insert().values(document_id=scope.document_id, current_revision_id=initial))
            if time.monotonic() >= deadline:
                raise TimeoutError('JD initial commit budget exhausted')
        return document

    @contextmanager
    def _publication_transaction(self, conn, state):
        transaction = conn.begin()
        try:
            yield
        except BaseException:
            try:
                transaction.rollback()
                state['rollback_confirmed'] = True
            except DBAPIError:
                state['rollback_confirmed'] = False
                conn.invalidate()
                raise
            raise
        else:
            if transaction.is_active:
                transaction.commit()

    def publish(self, intent, candidate=None, *, error=None):
        """No computation/replay here; commit uncertainty never becomes failure."""
        commit_sent = False
        outcome = None
        state = {'rollback_confirmed': False}
        try:
            with self._connection() as (conn, deadline):
                with self._publication_transaction(conn, state):
                    self._scope(conn, deadline, intent.scope)
                    current_id = self._execute(conn, deadline, select(head.c.current_revision_id)
                        .where(head.c.document_id == intent.scope.document_id).with_for_update()).scalar_one_or_none()
                    if current_id is None:
                        raise JdMissing('JD head not found')
                    existing = self._receipt(conn, deadline, intent.scope, intent.operation_id, intent.digest)
                    if existing:
                        conn.rollback()
                        return existing
                    try:
                        base = self._revision(conn, deadline, intent.scope, intent.base_id)
                    except JdMissing:
                        base = None
                    if base is None:
                        outcome = failure(intent, 'target_missing')
                    elif current_id != base.id:
                        outcome = failure(intent, 'stale_base', base_id=base.id)
                    elif error is not None:
                        outcome = replace(error, base_id=base.id)
                    else:
                        same = self._execute(conn, deadline, select(revision.c.value == bindparam('candidate', type_=JSONB))
                            .where(revision.c.document_id == intent.scope.document_id, revision.c.revision_id == base.id),
                            {'candidate': candidate.value}).scalar_one()
                        result_id = base.id if same else uuid4()
                        if not same:
                            self._execute(conn, deadline, revision.insert().values(document_id=intent.scope.document_id,
                                revision_id=result_id, parent_revision_id=base.id, origin=intent.origin,
                                format_version=2, engine_profile='jd-plate-clean-v2', value=candidate.value))
                        outcome = JdWriteOutcome(intent.scope, intent.operation_id, base.id, result_id,
                            'no_change' if same else 'committed', intent.origin,
                            operations=None if same or intent.origin == 'manual' else candidate.operations,
                            affected_ids=[] if same or intent.origin == 'manual' else candidate.affected_ids)
                    wire = outcome_to_wire(outcome)
                    row = dict(document_id=intent.scope.document_id, operation_id=intent.operation_id,
                        request_digest=intent.digest, origin=intent.origin, base_revision_id=outcome.base_id,
                        result_revision_id=outcome.result_id, status=outcome.status, receipt=wire)
                    outcome_from_row(intent.scope, row)
                    self._execute(conn, deadline, operation.insert().values(**row))
                    if outcome.status == 'committed':
                        self._execute(conn, deadline, head.update().where(head.c.document_id == intent.scope.document_id)
                                      .values(current_revision_id=outcome.result_id))
                    if time.monotonic() >= deadline:
                        raise TimeoutError('JD SQL commit budget exhausted')
                    commit_sent = True
                return outcome
        except (DBAPIError, TimeoutError):
            if commit_sent:
                if outcome is not None and outcome.status not in {'committed', 'no_change'}:
                    return replace(outcome, durability='unconfirmed', next_action='reconcile_operation')
                return failure(intent, 'outcome_unknown', base_id=intent.base_id, confirmed=False)
            if error is not None:
                return replace(error, durability='unconfirmed', next_action='reconcile_operation')
            if not state['rollback_confirmed']:
                return failure(intent, 'save_failed', base_id=intent.base_id, confirmed=False)
            # The connection context has completed rollback/cleanup before this
            # separate terminal recording attempt. It never republishes content.
            return self.publish(intent, error=failure(intent, 'save_failed', base_id=intent.base_id))

    def producer(self, scope, revision_id):
        with self._connection() as (conn, deadline):
            self._scope(conn, deadline, scope)
            self._revision(conn, deadline, scope, revision_id)
            row = self._execute(conn, deadline, select(operation).where(operation.c.document_id == scope.document_id,
                operation.c.result_revision_id == revision_id, operation.c.status == 'committed')).mappings().first()
            return outcome_from_row(scope, row) if row else None

    def history(self, scope, ancestor_id, descendant_id):
        """Only direct-parent ancestry; counts and the latest four creating events."""
        with self._connection() as (conn, deadline):
            self._scope(conn, deadline, scope)
            self._revision(conn, deadline, scope, ancestor_id)
            current, events, seen = descendant_id, [], set()
            ai = manual = 0
            while current != ancestor_id:
                if current is None or current in seen:
                    raise JdMissing('Requested revision is not an ancestor')
                seen.add(current)
                rev = self._revision(conn, deadline, scope, current)
                row = self._execute(conn, deadline, select(operation).where(operation.c.document_id == scope.document_id,
                    operation.c.result_revision_id == current, operation.c.status == 'committed')).mappings().first()
                if row is None:
                    raise JdMissing('Requested revision is not an ancestor')
                event = outcome_from_row(scope, row)
                if event.base_id != rev.parent_id or event.origin != rev.origin:
                    raise ValueError('Revision producer mismatch')
                ai += event.origin == 'ai'
                manual += event.origin == 'manual'
                if len(events) < 4:
                    events.append(event)
                current = rev.parent_id
            return JdHistory(ai + manual, ai, manual, tuple(events))
