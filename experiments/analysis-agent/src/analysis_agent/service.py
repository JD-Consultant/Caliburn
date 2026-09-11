"""Single-process API application service around the official synchronous graph.

The executor outlives HTTP requests. Stops are cooperative at public middleware
boundaries; no Future.cancel(), private graph state, or second message archive.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
import hashlib
from threading import Event, RLock, Condition
from contextlib import contextmanager

from langchain.agents.middleware import AgentMiddleware
from langchain_core.exceptions import ModelError
from analysis_agent.budget import RequestBudgetExceeded
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import START

from analysis_agent.conversation import build_conversation, close_turn, pending_memory_read
from analysis_agent.consolidation_request import REQUEST_TOOL_NAME
from analysis_agent.sources import ConversationReader
from analysis_agent.publication import PublicationUncertain, PublicationStore
from analysis_agent.memory import MemoryArtifacts
from analysis_agent.live_memory import MemorySession
from analysis_agent.memory_tools import readonly_file_tools
from analysis_agent.skills import SkillAssets, analysis_files, analysis_skills
from analysis_agent.provider import is_billing_error
from analysis_agent.jd_engine import JdNativeCalls


class ServiceConflict(Exception):
    pass


class StopRequested(Exception):
    pass


class CooperativeStop(AgentMiddleware):
    def __init__(self, signal):
        self.signal = signal

    def before_model(self, state, runtime):
        if self.signal.is_set():
            raise StopRequested('Stopped at a saved model boundary')

    def after_model(self, state, runtime):
        # after_model is a saved public node before ToolNode. The model response
        # is retained; close_turn knows the returned tool was not started.
        if self.signal.is_set():
            raise StopRequested('Stopped before tool execution')

    def wrap_model_call(self, request, handler):
        if self.signal.is_set():
            raise StopRequested('Stopped at model entry')
        return handler(request)

    def wrap_tool_call(self, request, handler):
        # Other hooks can run after after_model. Check again at the actual
        # public tool entry; this result is certain because handler is NOT run.
        if self.signal.is_set():
            return ToolMessage('Tool not executed: stop was requested before tool entry.',
                name=request.tool_call['name'], tool_call_id=request.tool_call['id'], status='error')
        return handler(request)


@dataclass
class DocumentRuntime:
    graph: object
    reader: ConversationReader
    stop: Event
    memory: MemorySession | None
    jd_session: object | None = None
    native_calls: object = field(default_factory=JdNativeCalls)
    active_entries: int = 0
    manual_active: bool = False
    generation: int = 0
    prior_execution: bool = False
    closing: bool = False
    close_entries: int = 0
    read_stop: Event = field(default_factory=Event)

    @property
    def config(self):
        return {'configurable': {'thread_id': self.reader.document_id}}


def current_values(snapshot):
    for task in snapshot.tasks:
        if (task.name == 'analysis' and hasattr(task.state, 'values')
                and task.state.values.get('messages')):
            return task.state.values
    return snapshot.values


def pending_input_id(snapshot):
    return next((m.id for m in reversed(snapshot.values.get('messages', []))
                 if isinstance(m, HumanMessage)), None)


def resumable_repair(state):
    """Only the known C workflow can replay an uncertain publication safely.

    Its checkpointed operation identity and existing CAS/receipt protocol own
    idempotency. This is NOT permission to rerun arbitrary unknown tools.
    """
    binding = state.get('memory_repair_binding')
    if not binding:
        return False
    for message in reversed(state.get('messages', [])):
        if isinstance(message, AIMessage) and message.id == binding['message_id']:
            return any(c['name'] == 'repair_memory' and c['id'] == binding['call_id']
                       for c in message.tool_calls) and not any(
                isinstance(m, ToolMessage) and m.tool_call_id == binding['call_id']
                for m in state['messages'])
    return False


class AnalysisService:
    def __init__(self, *, catalog, saver, model, instructions, store=None,
                 max_workers=2, max_model_steps=16, max_tool_calls=15, jd=None, lifecycle=None):
        self.catalog, self.saver, self.store = catalog, saver, store
        self.jd = jd
        self.lifecycle = lifecycle
        self.create_calls, self.create_stop = JdNativeCalls(), Event()
        self.create_active = 0
        self.model, self.instructions = model, instructions
        self.max_model_steps, self.max_tool_calls = max_model_steps, max_tool_calls
        self.lock = RLock()
        self.entries_changed = Condition(self.lock)
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='q019-analysis')
        self.contexts, self.futures = {}, {}
        self.background = None
        self.scheduler = None
        self.accepting = False

    def _context(self, document):
        from analysis_agent.scheduling import BackgroundAvailability
        self.catalog.document(document)
        if document not in self.contexts:
            stop = Event()
            common = dict(model=self.model, checkpointer=self.saver, instructions=self.instructions,
                          max_model_steps=self.max_model_steps, max_tool_calls=self.max_tool_calls)
            base = build_conversation(**common)
            reader = ConversationReader(base, document)
            assets = SkillAssets()
            memory = (MemorySession(PublicationStore(self.catalog.engine,
                       MemoryArtifacts(self.store, document, source=reader)), reader,
                       skill_assets=assets) if self.store is not None else None)
            from analysis_agent.jd_tools import JdToolSession
            native_calls = JdNativeCalls()
            jd_session = JdToolSession(self.jd, reader, cancel=stop, native_calls=native_calls, source_read_tools=memory.read_tools if memory else ()) if self.jd is not None else None
            graph = build_conversation(**common,
                tools=[*(memory.tools if memory else readonly_file_tools(analysis_files(assets))),
                       *(jd_session.tools if jd_session else ())],
                middleware=[analysis_skills(assets), *([jd_session] if jd_session else []), *([memory] if memory else []),
                            BackgroundAvailability(self, document), CooperativeStop(stop)])
            reader.graph = graph
            prior = graph.get_state({'configurable':{'thread_id':document}},subgraphs=True)
            self.contexts[document] = DocumentRuntime(graph, reader, stop, memory, jd_session,native_calls,
                prior_execution=bool(prior.values.get('jd_manual_pending') or
                    current_values(prior).get('jd_pending_operation') or
                    (current_values(prior).get('jd_binding') and not current_values(prior).get('jd_bindings')) or
                    any(not b.get('closed') for b in current_values(prior).get('jd_bindings',{}).values())))
        return self.contexts[document]

    def enable_background(self, *, max_recoveries, text_threshold=None, extraction_model=None,
                          consolidation_model=None):
        from analysis_agent.scheduling import BackgroundDispatcher
        with self.lock:
            if self.background is not None:
                raise ServiceConflict('Background dispatcher is already configured')
            self.background = BackgroundDispatcher(self, max_recoveries=max_recoveries,
                text_threshold=text_threshold, extraction_model=extraction_model,
                consolidation_model=consolidation_model)
            return self.background

    def start_background(self, *, poll_seconds):
        from datetime import datetime, timezone
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.executors.pool import ThreadPoolExecutor as SchedulerExecutor
        if not 0 < poll_seconds < float('inf'):
            raise ValueError('Background polling interval must be positive and finite')
        with self.lock:
            if not self.accepting or self.background is None or self.scheduler is not None:
                raise ServiceConflict('Background startup requires one configured, running service')
            scheduler = BackgroundScheduler(executors={'default': SchedulerExecutor(max_workers=1)}, timezone='UTC')
            # One reconstructible wake job, not one unlimited executor per JD.
            scheduler.add_job(self.background.tick, 'interval', seconds=poll_seconds,
                              id='q019-background-dispatch', coalesce=True, max_instances=1,
                              next_run_time=datetime.now(timezone.utc))
            self.scheduler = scheduler
            scheduler.start()

    def start(self):
        with self.lock:
            if self.lifecycle is not None:
                self.lifecycle.verify()
            for row in self.catalog.runs():
                if row['status'] in {'receiving', 'running', 'stopping', 'interrupted', 'uncertain'}:
                    try:
                        self._reconcile(row, startup=True)
                    except PublicationUncertain:
                        self.catalog.update_run(row['id'],status='uncertain',error_code='publication_uncertain')
            if self.jd is not None:
                for document in self.catalog.documents():
                    saved = self.saver.get_tuple({'configurable':{'thread_id':document['id']}})
                    if saved and saved.checkpoint['channel_values'].get('jd_manual_pending'):
                        context = self._context(document['id'])
                        try:
                            self._reconcile_manual(context)
                        except PublicationUncertain:
                            # Identity remains durable; explicit recovery can retry.
                            pass
            self.accepting = True

    def create_document(self, title, *, request_key=None):
        if not title.strip() or len(title) > 200:
            raise ValueError('Title must contain 1–200 characters')
        with self.lock:
            if not self.accepting:
                raise ServiceConflict('Service is stopping')
            options = {'request_key': request_key} if request_key is not None else {}
            self.create_active += 1
        try:
            return self.jd.create_document(title,cancel=self.create_stop,native_calls=self.create_calls,**options) if self.jd is not None else self.catalog.create_document(title, **options)
        finally:
            with self.entries_changed:
                self.create_active -= 1
                self.entries_changed.notify_all()

    def update_document(self, document, command):
        with self.lock:
            self.catalog.document(document)
            context = self._context(document)
            if not self.accepting or self._jd_busy(context) or self._running(document) or any(r['status'] in {'receiving','running','stopping','uncertain','interrupted'} for r in self.catalog.runs(document)):
                raise ServiceConflict('Close the foreground run before updating metadata')
            return self.catalog.update_document(document, command)

    def run_by_request(self, document, request_key):
        with self.lock:
            self.catalog.document(document)
            row = next((r for r in self.catalog.runs(document) if r['request_key'] == request_key), None)
            if row is None:
                return {'found': False}
            context = self._context(document)
            saved = context.graph.get_state(context.config)
            received = any(isinstance(m, HumanMessage) and m.id == row['id'] for m in saved.values.get('messages', []))
            return {'found': True, 'run': self.get_run(document, row['id']), 'input_received': received}

    def list_documents(self):
        with self.lock:
            return self.catalog.documents()

    def reader(self, document):
        with self.lock:
            return self._context(document).reader

    def _running(self, document):
        future = self.futures.get(document)
        return future is not None and not future.done()

    def _jd_busy(self, context):
        state = current_values(context.graph.get_state(context.config,subgraphs=True))
        return (context.closing or context.manual_active or context.active_entries or not context.native_calls.quiescent or
            context.graph.get_state(context.config).values.get('jd_manual_pending') is not None or
            bool(state.get('jd_pending_operation')) or
            any(not b.get('closed') for b in state.get('jd_bindings',{}).values()))

    def _write_blocked(self, context):
        document = context.reader.document_id
        return bool(not self.accepting or self.catalog.document(document)['archived'] or
            self._jd_busy(context) or self._running(document) or
            context.graph.get_state(context.config).next or
            any(r['status'] in {'receiving','running','stopping','uncertain','interrupted'}
                for r in self.catalog.runs(document)))

    def _manual_pending(self, context):
        from uuid import UUID
        import re
        from analysis_agent.jd_contract import manual_operation_id
        from analysis_agent.jd_types import JdScope
        pending = context.graph.get_state(context.config).values.get('jd_manual_pending')
        if pending is None:
            return None
        try:
            valid = (set(pending)=={'operation','base','digest','request_key','origin'} and
                pending['origin']=='manual' and re.fullmatch('[0-9a-f]{64}',pending['digest']) and
                str(UUID(pending['request_key']))==pending['request_key'] and
                str(UUID(pending['base']))==pending['base'] and
                str(manual_operation_id(JdScope(context.reader.document_id),pending['request_key']))==pending['operation'])
        except (TypeError,ValueError,KeyError):
            valid = False
        if not valid:
            raise PublicationUncertain('Manual admission identity cannot be confirmed')
        return pending

    def manual_recovery(self, document, request_key=None):
        """Pure projection of an original receipt and the same admission owner."""
        from analysis_agent.jd_contract import manual_operation_id
        from analysis_agent.jd_types import JdScope
        with self.lock:
            context = self._context(document)
            pending = self._manual_pending(context)
            key = request_key if request_key is not None else pending['request_key'] if pending else None
            original = self.jd.store.receipt(JdScope(document),manual_operation_id(JdScope(document),key)) if key else None
            matched = pending is not None and pending['request_key']==key
            can_recover = bool(self.accepting and matched and not context.manual_active and not context.closing and
                not context.active_entries and not self._running(document))
            result = {'status':'available' if original else 'unknown' if matched else 'no_pending',
                'request_key':key,'write_blocked':self._write_blocked(context),'can_recover':can_recover,
                'restart_required':bool(context.native_calls.blocked and not pending and
                    not context.active_entries and not context.manual_active and not context.closing and
                    not self._running(document) and not context.graph.get_state(context.config).next)}
            if original:
                if original.durability!='confirmed' or original.status=='operation_conflict':
                    raise PublicationUncertain('Original terminal receipt cannot be confirmed')
                result['result'] = original
            return result

    def recover_manual(self, document, request_key):
        """One explicit attempt on the exact original identity; never replay."""
        with self.lock:
            if not self.accepting:
                raise ServiceConflict('Service is stopping')
            initial = self.manual_recovery(document,request_key)
            context = self._context(document)
            pending = self._manual_pending(context)
            if not pending or pending['request_key']!=request_key:
                return initial
            if context.closing or context.manual_active or context.active_entries or self._running(document):
                if initial['status']=='available':
                    return initial
                raise ServiceConflict('Original manual publisher or recovery is active')
            context.closing = True
            context.close_entries += 1
            context.generation += 1
            generation = context.generation
        try:
            # This owner retains the original handles. No global lock while waiting.
            context.native_calls.cleanup()
            with self.lock:
                if context.generation!=generation or self._manual_pending(context)!=pending:
                    raise PublicationUncertain('Manual recovery admission changed')
            try:
                self._reconcile_manual(context)
            except PublicationUncertain:
                pass
        finally:
            with self.entries_changed:
                context.closing = False
                try:
                    # Project the released gate before another admission or
                    # shutdown can run; the drain count still owns this read.
                    result = self.manual_recovery(document,request_key)
                finally:
                    context.close_entries -= 1
                    self.entries_changed.notify_all()
        return result

    @contextmanager
    def jd_read_entry(self, document):
        with self.lock:
            if not self.accepting:
                raise ServiceConflict('Service is stopping')
            context = self._context(document)
            if context.closing:
                raise ServiceConflict('Document recovery is closing prior native work')
            context.active_entries += 1
        try:
            yield context
        finally:
            with self.entries_changed:
                context.active_entries -= 1
                self.entries_changed.notify_all()

    def save_manual(self, intent, request_key):
        from analysis_agent.conversation import save_manual_pending
        from analysis_agent.jd_contract import validate_intent_digest, manual_operation_id
        from analysis_agent.jd_references import source_refs
        validate_intent_digest(intent)
        if manual_operation_id(intent.scope,request_key)!=intent.operation_id:
            raise ValueError('Manual request identity differs')
        document = intent.scope.document_id
        with self.lock:
            context = self._context(document)
            pending = context.graph.get_state(context.config).values.get('jd_manual_pending')
            original = self.jd.store.receipt(intent.scope,intent.operation_id,intent.digest)
            if original:
                if (pending and pending['operation']==str(intent.operation_id) and original.status!='operation_conflict'
                        and not context.closing and not context.manual_active and not context.active_entries
                        and context.native_calls.quiescent and not self._running(document)):
                    try:
                        save_manual_pending(context.graph,context.config,None)
                    except Exception:
                        pass  # A terminal receipt remains readable; the descriptor keeps its gate.
                return original
            recover = pending and pending.get('request_key')==request_key
            if recover and pending.get('digest')!=intent.digest:
                raise ServiceConflict('Original manual payload differs')
        if recover:
            result = self.recover_manual(document,request_key)
            if result['status']=='available':
                return result['result']
            raise PublicationUncertain('Original manual result is still unknown')
        with self.lock:
            # Another request can have admitted while the receipt was read.
            if self._write_blocked(context):
                raise ServiceConflict('Close the admitted foreground/manual operation first')
            for reference in source_refs(intent.value):
                context.reader.read(reference)
            descriptor = {'operation':str(intent.operation_id),'base':str(intent.base_id),
                'digest':intent.digest,'request_key':request_key,'origin':'manual'}
            # No candidate or synthetic input is written into this root channel.
            save_manual_pending(context.graph,context.config,descriptor)
            context.stop.clear()
            context.manual_active = True
            context.active_entries += 1
            context.generation += 1
        try:
            result = self.jd.manual_save(intent,cancel=context.stop,native_calls=context.native_calls)
            with self.lock:
                if result.durability=='confirmed' and result.status!='operation_conflict' and context.native_calls.quiescent:
                    save_manual_pending(context.graph,context.config,None)
            return result
        finally:
            with self.entries_changed:
                context.manual_active = False
                context.active_entries -= 1
                self.entries_changed.notify_all()

    def _reconcile_manual(self, context):
        """Only the root's admitted identity; no candidate reconstruction."""
        from uuid import UUID
        import re
        from analysis_agent.conversation import save_manual_pending
        from analysis_agent.jd_types import JdScope
        from analysis_agent.jd_contract import manual_operation_id
        from analysis_agent.jd_reconcile import JdWriterStopped,JdAdmittedIdentity,reconcile_identity
        with self.lock:
            snapshot = context.graph.get_state(context.config)
            pending = self._manual_pending(context)
            generation = context.generation
        if pending is None:
            return None
        scope = JdScope(context.reader.document_id)
        if (snapshot.next or pending.get('origin')!='manual' or
                set(pending)!= {'operation','base','digest','request_key','origin'} or
                not re.fullmatch('[0-9a-f]{64}',pending.get('digest','')) or
                str(manual_operation_id(scope,pending['request_key']))!=pending['operation']):
            raise PublicationUncertain('Manual admission identity cannot be confirmed')
        proof = JdWriterStopped(scope,context.native_calls,
            lambda: not context.active_entries and not self._running(scope.document_id),
            self.lifecycle,context.prior_execution)
        identity = JdAdmittedIdentity(scope,UUID(pending['operation']),UUID(pending['base']),pending['digest'],'manual')
        result = reconcile_identity(self.jd.store,identity,proof)
        with self.lock:
            if context.generation!=generation or context.graph.get_state(context.config).values.get('jd_manual_pending')!=pending:
                raise PublicationUncertain('Manual admission changed during reconciliation')
            try:
                save_manual_pending(context.graph,context.config,None)
            except Exception as exc:
                raise PublicationUncertain('Original result is terminal but admission cleanup is unconfirmed') from exc
            context.prior_execution = False
        return result

    def _close_turn(self, context, *, reason='cancelled', worker_unwound=False):
        """Caller has reserved this document; no wait while holding admission."""
        from analysis_agent.jd_reconcile import JdWriterStopped
        document = context.reader.document_id
        idle = lambda: (not context.active_entries and
                        (worker_unwound or not self._running(document)))
        proof = JdWriterStopped(context.jd_session.scope if context.jd_session else None,
            context.native_calls,idle,self.lifecycle,context.prior_execution)
        if context.jd_session:
            proof.require(context.jd_session.scope)
            context.jd_session.stopped_proof = proof
        elif not idle():
            raise PublicationUncertain('Foreground execution has not stopped')
        try:
            return close_turn(context.graph,context.config,reason=reason,quiescent=True,
                memory_session=context.memory,jd_session=context.jd_session)
        finally:
            if context.jd_session:
                context.jd_session.stopped_proof = None

    def _reconcile(self, row, *, startup=False, observer=False):
        context = self._context(row['document_id'])
        snapshot = context.graph.get_state(context.config, subgraphs=True)
        if not any(m.id == row['id'] for m in snapshot.values.get('messages', [])):
            return self.catalog.update_run(row['id'], status='not_received', error_code=None)
        boundary = snapshot.values.get('closed_turns', {}).get(row['id'])
        if not boundary and snapshot.next:
            child = current_values(snapshot)
            if child.get('closed_turns', {}).get(row['id']):
                # The child finished but the root merge reply was lost. This
                # public closure copies the actual terminal result, no model.
                if not observer and not self._running(row['document_id']):
                    self._close_turn(context)
                    snapshot = context.graph.get_state(context.config)
                    boundary = snapshot.values.get('closed_turns', {}).get(row['id'])
        if boundary:
            state = current_values(snapshot)
            if state.get('jd_pending_operation') or any(not b.get('closed') for b in state.get('jd_bindings',{}).values()) or not context.native_calls.quiescent:
                return self.catalog.update_run(row['id'],status='uncertain',error_code='publication_uncertain')
            outcome = snapshot.values.get('turn_outcome')
            if not outcome or outcome['input_id'] != row['id']:
                outcome = row['outcome']
            return self.catalog.update_run(row['id'], status=boundary['status'], outcome=outcome)
        if startup:
            if not observer and row['status'] == 'stopping' and pending_input_id(snapshot) == row['id']:
                try:
                    self._close_turn(context)
                except PublicationUncertain:
                    return self.catalog.update_run(row['id'], status='uncertain', error_code='publication_uncertain')
                return self._reconcile(row)
            return self.catalog.update_run(row['id'], status=('uncertain' if row['error_code'] == 'publication_uncertain' else 'interrupted'),
                error_code=row['error_code'] or 'process_interrupted', usage_complete=False)
        return row

    def submit(self, document, request_key, text, *, abandon_pending=False, jd_selection=None):
        if not text.strip() or not request_key or len(request_key) > 128:
            raise ValueError('Non-empty text and a request key of at most 128 characters are required')
        import json
        from analysis_agent.jd_contract import validate, parse_ref
        from analysis_agent.jd_types import JdScope
        if jd_selection is not None:
            jd_selection=validate('JdSelectionCaptureClientInput',jd_selection)
        digest = hashlib.sha256(json.dumps({'text':text,'jd_selection':jd_selection,
            'abandon_pending':abandon_pending},sort_keys=True,ensure_ascii=False,separators=(',', ':')).encode()).hexdigest()
        closing_pending = False
        with self.lock:
            if not self.accepting:
                raise ServiceConflict('Service is stopping')
            context = self._context(document)
            existing = next((r for r in self.catalog.runs(document) if r['request_key'] == request_key), None)
            if existing:
                if existing['input_digest'] != digest:
                    raise ServiceConflict('Request key already belongs to different input')
                self.get_run(document, existing['id'])
                existing = self.catalog.run(document, existing['id'])
                saved = context.graph.get_state(context.config)
                if any(m.id == existing['id'] for m in saved.values.get('messages', [])):
                    return self.get_run(document, existing['id'])
                self.catalog.update_run(existing['id'], status='not_received', error_code=None)
            if self.catalog.document(document)['archived']:
                raise ServiceConflict('Document is archived')
            if self._running(document):
                raise ServiceConflict('This document is still running')
            if self._jd_busy(context):
                raise ServiceConflict('JD operation must be reconciled before new input')
            snapshot = context.graph.get_state(context.config)
            if snapshot.next:
                if not abandon_pending:
                    raise ServiceConflict('Resume or explicitly close the interrupted run first')
                closing_pending = context.closing = True
                context.close_entries += 1
            context.stop.clear()
            selection_context=None
            if jd_selection is not None and not closing_pending:
                if self.jd is None: raise ServiceConflict('JD selection is unavailable')
                scope=JdScope(document)
                try:
                    base,=parse_ref(jd_selection['base_revision_ref'],'revision',scope)
                except ValueError as exc:
                    raise ServiceConflict('JD selection belongs to an invalid saved document reference') from exc
                current=self.jd.store.current(scope)
                if current.id!=base: raise ServiceConflict('JD selection base is stale; select saved current content again')
                context.active_entries += 1
                context.generation += 1
                selection_generation = context.generation
        if closing_pending:
            try:
                self._close_turn(context)
                if context.graph.get_state(context.config).next:
                    raise PublicationUncertain('Interrupted input closure is unconfirmed')
                for old in self.catalog.runs(document):
                    if old['status'] in {'running','interrupted','uncertain','stopping'}:
                        self._reconcile(old)
            finally:
                with self.entries_changed:
                    context.closing = False
                    context.close_entries -= 1
                    self.entries_changed.notify_all()
            # The old input is now closed. Recheck admission of this original
            # request (including archive/stop), then prepare its selection.
            return self.submit(document,request_key,text,abandon_pending=abandon_pending,jd_selection=jd_selection)
        if jd_selection is not None:
            try:
                from analysis_agent.jd_engine import JdEngineFailure
                try:
                    native=self.jd.engine.selection(current.value,jd_selection['range'],cancel=context.stop,native_calls=context.native_calls)
                except JdEngineFailure as exc:
                    if exc.code in {'invalid_input','invalid_selection','invalid_span','target_missing','unsupported_content'}:
                        raise ServiceConflict('JD selection is unavailable; select supported saved content again') from exc
                    raise
                selection_context={'document':document,'revision':str(base),'target':native['target_id'],
                    'range':native['range'],'fragment':native['fragment']}
            except BaseException:
                with self.entries_changed:
                    context.active_entries -= 1
                    self.entries_changed.notify_all()
                raise
        with self.lock:
            if jd_selection is not None:
                context.active_entries -= 1
                self.entries_changed.notify_all()
            latest = next((r for r in self.catalog.runs(document) if r['request_key']==request_key),None)
            if latest:
                if latest['input_digest']!=digest:
                    raise ServiceConflict('Request key already belongs to different input')
                if any(m.id==latest['id'] for m in context.graph.get_state(context.config).values.get('messages',[])):
                    return self.get_run(document,latest['id'])
                existing = latest
            if self.catalog.document(document)['archived'] or context.graph.get_state(context.config).next:
                raise ServiceConflict('Document archive or pending input changed during admission')
            if not self.accepting or self._running(document) or self._jd_busy(context):
                raise ServiceConflict('Document admission changed while preparing input')
            if jd_selection is not None and (context.generation!=selection_generation or
                    context.stop.is_set() or self.jd.store.current(scope).id!=base):
                raise ServiceConflict('JD selection base or owner changed during admission')
            row = existing or self.catalog.create_run(document, request_key, digest)
            context.generation += 1
            if selection_context is not None: selection_context['input']=row['id']
            # as_node START writes the real root input and schedules analysis,
            # without running a model. It is a public update_state operation.
            context.graph.update_state(context.config, {'messages': [HumanMessage(text, id=row['id'])],
                                                        'turn_outcome': None, 'jd_selection': selection_context}, as_node=START)
            saved = context.graph.get_state(context.config)
            if not any(m.id == row['id'] for m in saved.values.get('messages', [])):
                raise RuntimeError('Input checkpoint was not confirmed')
            self._launch(context, row)
            return self.get_run(document, row['id'])

    def _launch(self, context, row):
        context.stop.clear()
        self.catalog.update_run(row['id'], status='running', error_code=None)
        self.futures[row['document_id']] = self.executor.submit(self._execute, context, row['id'])

    def _execute(self, context, run_id):
        try:
            context.graph.invoke(None, context.config, durability='sync')
        except StopRequested:
            try:
                self._close_turn(context, worker_unwound=True)
            except PublicationUncertain:
                self.catalog.update_run(run_id, status='uncertain', error_code='publication_uncertain')
                return
        except Exception as exc:
            if context.stop.is_set():
                # The model/tool has now unwound, even when it failed. Honor
                # the requested stop; do not offer an unwanted network resume.
                try:
                    self._close_turn(context, worker_unwound=True)
                except PublicationUncertain:
                    code, status = 'publication_uncertain', 'uncertain'
                else:
                    code, status = None, 'cancelled'
            elif isinstance(exc, PublicationUncertain):
                code, status = 'publication_uncertain', 'uncertain'
            elif isinstance(exc, ModelError):
                billing = is_billing_error(exc)
                retryable = exc.is_retryable and not billing
                code = ('context_budget_exceeded' if isinstance(exc, RequestBudgetExceeded) else
                        'billing_error' if billing else ('transport_error' if retryable else 'configuration_error'))
                status = 'interrupted'
                if not retryable:
                    try:
                        self._close_turn(context, reason='configuration_error', worker_unwound=True)
                        status = 'configuration_error'
                    except PublicationUncertain:
                        code, status = 'publication_uncertain', 'uncertain'
            else:
                code, status = 'runtime_error', 'interrupted'
            with self.lock:
                row = self.catalog.update_run(run_id, status=status, error_code=code, usage_complete=False)
            self._reconcile(row)
            return
        self._reconcile(self.catalog.run(context.reader.document_id, run_id))

    def get_run(self, document, run_id):
        with self.lock:
            row = self.catalog.run(document, run_id)
            if not self._running(document) and row['status'] in {'receiving', 'running', 'stopping'}:
                row = self._reconcile(row, startup=True, observer=True)
            context = self._context(document)
            snapshot = context.graph.get_state(context.config, subgraphs=True)
            state = current_values(snapshot)
            if not any(m.id == run_id for m in snapshot.values.get('messages', [])):
                row = self.catalog.update_run(run_id, status='not_received', error_code=None)
            repair_resume = row['error_code'] == 'publication_uncertain' and resumable_repair(state)
            read_call = pending_memory_read(snapshot, context.memory)
            read_resume = (row['error_code'] in {'runtime_error', 'process_interrupted'}
                and read_call is not None)
            at_tools = any(t.name == 'analysis' and hasattr(t.state, 'next')
                           and 'tools' in t.state.next for t in snapshot.tasks)
            last = state.get('messages', [])[-1] if state.get('messages') else None
            notification_pending = (isinstance(last, AIMessage) and not last.invalid_tool_calls
                and len(last.tool_calls) == 1 and last.tool_calls[0]['name'] == REQUEST_TOOL_NAME)
            # A process/transport label cannot certify an unknown tool effect.
            # Only bound reads, the reserved pure notification, and C's saved
            # receipt identity may re-enter a pending ToolNode.
            safe_tools = read_call is not None or notification_pending or resumable_repair(state)
            can_resume = (not self._running(document) and row['status'] in {'interrupted', 'uncertain'}
                and not context.manual_active and not context.closing and context.native_calls.quiescent
                and not state.get('jd_pending_operation')
                and not any(not b.get('closed') for b in state.get('jd_bindings',{}).values())
                and (row['error_code'] in {'transport_error', 'process_interrupted'} or repair_resume or read_resume)
                and (not at_tools or safe_tools)
                and bool(snapshot.next) and pending_input_id(snapshot) == run_id
                and (state.get('thread_model_call_count', 0) < self.max_model_steps or repair_resume or read_resume))
            # A pending trusted read can finish even at the model limit. Resume
            # uses the existing checkpoint; the next official model guard ends
            # at the saved quota without another provider call.
            # A completed tool at its exact quota does not prohibit a final
            # answer. Official middleware still guards additional calls; the
            # per-input counters are never reset by this API.
            usage, usage_complete, in_turn = None, row['usage_complete'], False
            for message in state.get('messages', []):
                if isinstance(message, HumanMessage):
                    if in_turn:
                        break
                    in_turn = message.id == run_id
                elif in_turn and isinstance(message, AIMessage) and message.response_metadata.get('status'):
                    if message.usage_metadata:
                        usage = usage or dict(input_tokens=0, output_tokens=0, total_tokens=0)
                        for name in usage:
                            usage[name] += message.usage_metadata.get(name, 0)
                    else:
                        usage_complete = False
            # An allow-list prevents checkpoints, encrypted reasoning, provider
            # bodies, request hashes and credentials crossing the API seam.
            return {k: row[k] for k in ('id', 'document_id', 'status', 'error_code',
                'resume_count', 'outcome')} | {'can_resume': can_resume, 'usage': usage,
                                              'usage_complete': usage_complete}

    def runs(self, document):
        with self.lock:
            self.catalog.document(document)
            return [self.get_run(document, r['id']) for r in self.catalog.runs(document)]

    def messages(self, document):
        with self.lock:
            context = self._context(document)
            state = current_values(context.graph.get_state(context.config, subgraphs=True))
            result = []
            for message in state.get('messages', []):
                if not isinstance(message, (HumanMessage, AIMessage)):
                    continue
                if message.additional_kwargs.get('analysis_agent_origin') == 'runtime_notice':
                    continue
                if isinstance(message.content, str):
                    text = message.content
                else:
                    text = ''.join(b.get('text', '') for b in message.content
                                   if isinstance(b, dict) and b.get('type') == 'text')
                if text:
                    result.append({'id': message.id, 'role': 'user' if isinstance(message, HumanMessage) else 'assistant', 'text': text})
            return result

    def resume(self, document, run_id):
        with self.lock:
            if not self.accepting or not self.get_run(document, run_id)['can_resume']:
                raise ServiceConflict('Run is not safely resumable')
            row = self.catalog.run(document, run_id)
            row = self.catalog.update_run(run_id, resume_count=row['resume_count'] + 1)
            self._launch(self._context(document), row)
            return self.get_run(document, run_id)

    def stop(self, document, run_id):
        with self.lock:
            if not self.accepting:
                raise ServiceConflict('Service is stopping')
            self.get_run(document, run_id)
            row = self.catalog.run(document, run_id)
            context = self._context(document)
            snapshot = context.graph.get_state(context.config)
            state = current_values(context.graph.get_state(context.config,subgraphs=True))
            pending_jd = state.get('jd_pending_operation') or any(not b.get('closed') for b in state.get('jd_bindings',{}).values())
            if (not snapshot.next and not pending_jd) or pending_input_id(snapshot) != run_id:
                return self.get_run(document, run_id)
            if self._running(document):
                context.stop.set()
                self.catalog.update_run(run_id, status='stopping')
                return self.get_run(document,run_id)
            if context.closing:
                return self.get_run(document,run_id)
            context.stop.set()
            context.closing = True
            context.close_entries += 1
            generation = context.generation
            self.catalog.update_run(run_id,status='stopping')
        # Same handles only, outside global admission. GET never reaches here.
        try:
            cleaned = context.native_calls.cleanup()
            with self.lock:
                if not cleaned or generation!=context.generation:
                    raise PublicationUncertain('JD cleanup/generation is unconfirmed')
            self._close_turn(context)
            self._reconcile(row)
        except PublicationUncertain:
            with self.lock:
                self.catalog.update_run(run_id,status='uncertain',error_code='publication_uncertain')
        finally:
            with self.entries_changed:
                context.closing = False
                try:
                    result = self.get_run(document,run_id)
                finally:
                    context.close_entries -= 1
                    self.entries_changed.notify_all()
        return result

    def join(self, document):
        """Wait for quiescence without holding admission lock (also used at shutdown)."""
        future = self.futures.get(document)
        if future:
            future.result()

    def close(self):
        with self.lock:
            self.accepting = False
            self.create_stop.set()
            for context in self.contexts.values():
                context.stop.set()
                context.read_stop.set()
        if self.scheduler is not None and self.scheduler.running:
            self.scheduler.shutdown(wait=True)
        if hasattr(self, 'background_lock'):
            # Also join an admitted direct dispatcher call (maintenance/tests),
            # not only work submitted by APScheduler. No lock held over A join.
            with self.background_lock:
                pass
        self.executor.shutdown(wait=True, cancel_futures=False)
        with self.entries_changed:
            drained = self.entries_changed.wait_for(lambda: not self.create_active and
                all(not context.active_entries and not context.close_entries for context in self.contexts.values()),timeout=10)
        if not drained:
            raise PublicationUncertain('App entry drain is not confirmed')
        owners = [self.create_calls,*(c.native_calls for c in self.contexts.values())]
        cleaned = [owner.cleanup() for owner in owners]
        if not all(cleaned):
            raise PublicationUncertain('Native cleanup is not confirmed')
        for context in list(self.contexts.values()):
                if self.jd is not None:
                    self._reconcile_manual(context)
                snapshot = context.graph.get_state(context.config)
                if snapshot.next and context.jd_session is not None:
                    try:
                        self._close_turn(context)
                    except PublicationUncertain:
                        # Keep saved unknown work; do not fabricate a result.
                        continue
                    for row in self.catalog.runs(context.reader.document_id):
                        if row['status'] in {'receiving','running','stopping','uncertain','interrupted'}:
                            self._reconcile(row)
