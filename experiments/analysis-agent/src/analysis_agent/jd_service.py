"""JD application composition; Node computation never owns a SQL transaction."""
from uuid import uuid4
from dataclasses import replace
from sqlalchemy.exc import DBAPIError
from analysis_agent.jd_contract import validate_intent_digest, engine_error_status
from analysis_agent.jd_engine import JdEngineFailure
from analysis_agent.jd_store import failure
from analysis_agent.jd_types import JdReadView, JdChangeView, JdMissing


class JdService:
    def __init__(self, store, engine, catalog):
        if store.engine is not catalog.engine:
            raise ValueError('JD and catalog must share one engine')
        self.store, self.engine, self.catalog = store, engine, catalog

    def create_document(self, title):
        value = self.engine.validate_value([{'type': 'p', 'id': str(uuid4()), 'children': [{'text': ''}]}]).value
        return self.store.create_document(self.catalog, title, value)

    def read(self, scope, query):
        try:
            revision = self.store.revision(scope, query.revision_id) if query.revision_id else self.store.current(scope)
            fragment = revision.value
            if query.target_id:
                def find(nodes):
                    for node in nodes:
                        if node.get('id') == query.target_id:
                            return node
                        if found := find(node.get('children', [])):
                            return found
                target = find(fragment)
                if target is None:
                    raise JdMissing('Target not found')
                fragment = [target]
            if query.selection:
                fragment = self.engine.selection(revision.value, query.selection)['fragment']
            return JdReadView(revision, fragment)
        except JdMissing:
            return JdReadView(status='target_missing')
        except (DBAPIError, TimeoutError):
            return JdReadView(status='read_failed')
        except JdEngineFailure as exc:
            # Read classifications differ from write validation: malformed
            # saved content cannot be repaired by changing selection arguments.
            if exc.code in {'invalid_input', 'invalid_selection', 'invalid_span'}:
                return JdReadView(status='invalid_input')
            if exc.code == 'target_missing':
                return JdReadView(status='target_missing')
            if exc.code in {'unsupported_content', 'noncanonical_value', 'duplicate_id',
                            'referenced_item', 'invalid_relation_kind'}:
                return JdReadView(status='unsupported_content')
            if exc.code in {'engine_failed', 'engine_timeout'}:
                return JdReadView(status='read_failed')
            # Cancellation and unclassified protocol/programming errors retain
            # their original exception for the runtime owner; no catch-all retry.
            raise

    def manual_save(self, intent):
        return self._write(intent, manual=True)

    def edit(self, intent):
        return self._write(intent, manual=False)

    def _write(self, intent, *, manual):
        validate_intent_digest(intent)
        try:
            existing = self.store.receipt(intent.scope, intent.operation_id, intent.digest)
            if existing:
                return existing
            # Confirm head exists without silently creating one for old catalog.
            self.store.current(intent.scope)
        except JdMissing:
            return replace(failure(intent, 'target_missing', confirmed=False),
                           operation_id=None, next_action='reread_current')
        except (DBAPIError, TimeoutError):
            return failure(intent, 'outcome_unknown', base_id=intent.base_id, confirmed=False)
        try:
            base = self.store.revision(intent.scope, intent.base_id)
        except JdMissing:
            return self.store.publish(intent, error=failure(intent, 'target_missing'))
        except (DBAPIError, TimeoutError):
            return failure(intent, 'save_failed', confirmed=False)
        try:
            candidate = self.engine.validate_value(intent.value) if manual else self.engine.transform(base.value, intent.commands)
        except JdEngineFailure as exc:
            code = engine_error_status(exc.code)
            error = failure(intent, code, base_id=base.id, code=exc.code, command_index=exc.command_index)
            if not exc.quiescent:
                return failure(intent, code, base_id=base.id, code=exc.code, confirmed=False)
            return self.store.publish(intent, error=error)
        return self.store.publish(intent, candidate)

    def change_read(self, scope, query):
        try:
            outcome = self.store.receipt(scope, query.operation_id) if query.operation_id else None
            if query.operation_id and (outcome is None or outcome.status not in {'committed', 'no_change'}):
                raise JdMissing('Change not found')
            before_id = outcome.base_id if outcome else query.before_id
            after_id = outcome.result_id if outcome else query.after_id
            if before_id is None or after_id is None:
                raise JdMissing('Revision pair required')
            return JdChangeView(self.store.revision(scope, before_id), self.store.revision(scope, after_id), outcome)
        except JdMissing:
            return JdChangeView(status='target_missing')
        except (DBAPIError, TimeoutError):
            return JdChangeView(status='read_failed')
