"""Single-process API application service around the official synchronous graph.

The executor outlives HTTP requests. Stops are cooperative at public middleware
boundaries; no Future.cancel(), private graph state, or second message archive.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import hashlib
from threading import Event, RLock

from langchain.agents.middleware import AgentMiddleware
from langchain_core.exceptions import ModelError
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import START

from analysis_agent.conversation import build_conversation, close_turn
from analysis_agent.sources import ConversationReader
from analysis_agent.publication import PublicationUncertain, PublicationStore
from analysis_agent.memory import MemoryArtifacts
from analysis_agent.live_memory import MemorySession
from analysis_agent.provider import is_billing_error


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
                 max_workers=2, max_model_steps=9, max_tool_calls=8):
        self.catalog, self.saver, self.store = catalog, saver, store
        self.model, self.instructions = model, instructions
        self.max_model_steps, self.max_tool_calls = max_model_steps, max_tool_calls
        self.lock = RLock()
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='q019-analysis')
        self.contexts, self.futures = {}, {}
        self.accepting = False

    def _context(self, document):
        self.catalog.document(document)
        if document not in self.contexts:
            stop = Event()
            common = dict(model=self.model, checkpointer=self.saver, instructions=self.instructions,
                          max_model_steps=self.max_model_steps, max_tool_calls=self.max_tool_calls)
            base = build_conversation(**common)
            reader = ConversationReader(base, document)
            memory = (MemorySession(PublicationStore(self.catalog.engine,
                       MemoryArtifacts(self.store, document)), reader) if self.store is not None else None)
            graph = build_conversation(**common, tools=memory.tools if memory else (),
                                       middleware=[*([memory] if memory else []), CooperativeStop(stop)])
            reader.graph = graph
            self.contexts[document] = DocumentRuntime(graph, reader, stop, memory)
        return self.contexts[document]

    def start(self):
        with self.lock:
            for row in self.catalog.runs():
                if row['status'] in {'receiving', 'running', 'stopping', 'interrupted', 'uncertain'}:
                    self._reconcile(row, startup=True)
            self.accepting = True

    def create_document(self, title):
        if not title.strip() or len(title) > 200:
            raise ValueError('Title must contain 1–200 characters')
        with self.lock:
            return self.catalog.create_document(title)

    def list_documents(self):
        with self.lock:
            return self.catalog.documents()

    def reader(self, document):
        with self.lock:
            return self._context(document).reader

    def _running(self, document):
        future = self.futures.get(document)
        return future is not None and not future.done()

    def _reconcile(self, row, *, startup=False):
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
                if not self._running(row['document_id']):
                    close_turn(context.graph, context.config,
                        reason='cancelled', quiescent=True, memory_session=context.memory)
                    snapshot = context.graph.get_state(context.config)
                    boundary = snapshot.values.get('closed_turns', {}).get(row['id'])
        if boundary:
            outcome = snapshot.values.get('turn_outcome')
            if not outcome or outcome['input_id'] != row['id']:
                outcome = row['outcome']
            return self.catalog.update_run(row['id'], status=boundary['status'], outcome=outcome)
        if startup:
            if row['status'] == 'stopping' and pending_input_id(snapshot) == row['id']:
                try:
                    close_turn(context.graph, context.config, reason='cancelled', quiescent=True,
                               memory_session=context.memory)
                except PublicationUncertain:
                    return self.catalog.update_run(row['id'], status='uncertain', error_code='publication_uncertain')
                return self._reconcile(row)
            return self.catalog.update_run(row['id'], status=('uncertain' if row['error_code'] == 'publication_uncertain' else 'interrupted'),
                error_code=row['error_code'] or 'process_interrupted', usage_complete=False)
        return row

    def submit(self, document, request_key, text, *, abandon_pending=False):
        if not text.strip() or not request_key or len(request_key) > 128:
            raise ValueError('Non-empty text and a request key of at most 128 characters are required')
        digest = hashlib.sha256(text.encode()).hexdigest()
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
            if self._running(document):
                raise ServiceConflict('This document is still running')
            snapshot = context.graph.get_state(context.config)
            if snapshot.next:
                if not abandon_pending:
                    raise ServiceConflict('Resume or explicitly close the interrupted run first')
                close_turn(context.graph, context.config, reason='cancelled', quiescent=True,
                           memory_session=context.memory)
                for old in self.catalog.runs(document):
                    if old['status'] in {'running', 'interrupted', 'uncertain', 'stopping'}:
                        self._reconcile(old)
            row = existing or self.catalog.create_run(document, request_key, digest)
            # as_node START writes the real root input and schedules analysis,
            # without running a model. It is a public update_state operation.
            context.graph.update_state(context.config, {'messages': [HumanMessage(text, id=row['id'])],
                                                        'turn_outcome': None}, as_node=START)
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
                close_turn(context.graph, context.config, reason='cancelled', quiescent=True,
                           memory_session=context.memory)
            except PublicationUncertain:
                self.catalog.update_run(run_id, status='uncertain', error_code='publication_uncertain')
                return
        except Exception as exc:
            if context.stop.is_set():
                # The model/tool has now unwound, even when it failed. Honor
                # the requested stop; do not offer an unwanted network resume.
                try:
                    close_turn(context.graph, context.config, reason='cancelled', quiescent=True,
                               memory_session=context.memory)
                except PublicationUncertain:
                    code, status = 'publication_uncertain', 'uncertain'
                else:
                    code, status = None, 'cancelled'
            elif isinstance(exc, PublicationUncertain):
                code, status = 'publication_uncertain', 'uncertain'
            elif isinstance(exc, ModelError):
                billing = is_billing_error(exc)
                retryable = exc.is_retryable and not billing
                code = 'billing_error' if billing else ('transport_error' if retryable else 'configuration_error')
                status = 'interrupted'
                if not retryable:
                    try:
                        close_turn(context.graph, context.config, reason='configuration_error',
                                   quiescent=True, memory_session=context.memory)
                        status = 'configuration_error'
                    except PublicationUncertain:
                        code, status = 'publication_uncertain', 'uncertain'
            else:
                code, status = 'runtime_error', 'interrupted'
            with self.lock:
                row = self.catalog.update_run(run_id, status=status, error_code=code, usage_complete=False)
                self._reconcile(row)
            return
        with self.lock:
            self._reconcile(self.catalog.run(context.reader.document_id, run_id))

    def get_run(self, document, run_id):
        with self.lock:
            row = self.catalog.run(document, run_id)
            if not self._running(document) and row['status'] in {'receiving', 'running', 'stopping'}:
                row = self._reconcile(row, startup=True)
            context = self._context(document)
            snapshot = context.graph.get_state(context.config, subgraphs=True)
            state = current_values(snapshot)
            if not any(m.id == run_id for m in snapshot.values.get('messages', [])):
                row = self.catalog.update_run(run_id, status='not_received', error_code=None)
            repair_resume = row['error_code'] == 'publication_uncertain' and resumable_repair(state)
            can_resume = (not self._running(document) and row['status'] in {'interrupted', 'uncertain'}
                and (row['error_code'] in {'transport_error', 'process_interrupted'} or repair_resume)
                and bool(snapshot.next) and pending_input_id(snapshot) == run_id
                and (state.get('thread_model_call_count', 0) < self.max_model_steps or repair_resume))
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
            self.get_run(document, run_id)
            row = self.catalog.run(document, run_id)
            context = self._context(document)
            snapshot = context.graph.get_state(context.config)
            if not snapshot.next or pending_input_id(snapshot) != run_id:
                return self.get_run(document, run_id)
            if row['status'] in {'running', 'stopping'} and self._running(document):
                context.stop.set()
                self.catalog.update_run(run_id, status='stopping')
            elif not self._running(document) and row['status'] in {'interrupted', 'uncertain', 'receiving'}:
                close_turn(context.graph, context.config, reason='cancelled', quiescent=True,
                           memory_session=context.memory)
                self._reconcile(row)
            return self.get_run(document, run_id)

    def join(self, document):
        """Wait for quiescence without holding admission lock (also used at shutdown)."""
        future = self.futures.get(document)
        if future:
            future.result()

    def close(self):
        with self.lock:
            self.accepting = False
            for context in self.contexts.values():
                context.stop.set()
        self.executor.shutdown(wait=True, cancel_futures=False)
