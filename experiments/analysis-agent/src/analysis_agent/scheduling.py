"""One local background executor. Scheduler wakes; Saver owns B1/B2 progress.

The catalog row is admission/error metadata only, not a transcript, Memory copy,
or substitute for the existing checkpoint/receipt protocol. All model transport
retries remain inside the SDK; a caught failure is blocked, never retried per tick.
"""
from threading import Lock

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.exceptions import ModelError
from langchain_core.messages import SystemMessage
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from analysis_agent.catalog import Base, values
from analysis_agent.budget import RequestBudgetExceeded
from analysis_agent.consolidation import ConsolidationWorkflow
from analysis_agent.extraction import ExtractionWorkflow
from analysis_agent.provider import is_billing_error
from analysis_agent.publication import PublicationUncertain


class BackgroundRow(Base):
    __tablename__ = 'q019_background_admission'
    document_id: Mapped[str] = mapped_column(ForeignKey('q019_document.id'), primary_key=True)
    status: Mapped[str] = mapped_column(String(32))
    target_reference: Mapped[str | None] = mapped_column(String)
    source_reference: Mapped[str | None] = mapped_column(String)
    error_code: Mapped[str | None] = mapped_column(String(64))
    recovery_count: Mapped[int] = mapped_column(Integer, default=0)


class BackgroundDispatcher:
    def __init__(self, service, *, max_recoveries, text_threshold=None, max_windows=16):
        if type(max_recoveries) is not int or max_recoveries < 0:
            raise ValueError('An explicit nonnegative automatic recovery limit is required')
        if text_threshold is not None and (type(text_threshold) is not int or text_threshold < 1):
            raise ValueError('Text fallback threshold must be positive when enabled')
        if type(max_windows) is not int or not 1 <= max_windows <= 100:
            raise ValueError('Invalid extraction batch limit')
        if service.store is None:
            raise ValueError('Background memory requires the official Store')
        self.service, self.catalog = service, service.catalog
        self.max_recoveries, self.text_threshold, self.max_windows = max_recoveries, text_threshold, max_windows
        # Shared by every dispatcher entry in this single-process application.
        with service.lock:
            if not hasattr(service, 'background_lock'):
                service.background_lock = Lock()
        self.lock = service.background_lock
        self.workflows, self.last_document = {}, None
        self.catalog.setup()

    def _workflows(self, document):
        if document not in self.workflows:
            reader = self.service.reader(document)
            publication = self.service._context(document).memory.publication
            b1 = ExtractionWorkflow(reader, publication.artifacts, self.service.model,
                                    self.service.saver, max_windows=self.max_windows)
            # Deployment sets one per-response budget on the model. B2 has a
            # standalone default, which must not replace that explicit budget.
            output_limit = self.service.model.max_tokens
            limits = {'max_output_tokens': output_limit} if output_limit is not None else {}
            b2 = ConsolidationWorkflow(b1, publication, self.service.model, self.service.saver, **limits)
            self.workflows[document] = b1, b2
        return self.workflows[document]

    def _row(self, document):
        with self.catalog.sessions() as session:
            row = session.get(BackgroundRow, document)
            return values(row) if row else None

    def _update(self, document, **changes):
        with self.catalog.sessions.begin() as session:
            row = session.get(BackgroundRow, document)
            if row is None:
                row = BackgroundRow(document_id=document, status='idle', recovery_count=0)
                session.add(row)
            for name, value in changes.items():
                setattr(row, name, value)
            session.flush()
            return values(row)

    def status(self, document):
        self.catalog.document(document)
        row = self._row(document)
        return ({'status': row['status'], 'error_code': row['error_code'], 'recovery_count': row['recovery_count']}
                if row else {'status': 'idle', 'error_code': None, 'recovery_count': 0})

    def tick(self):
        if not self.lock.acquire(blocking=False):
            return False
        try:
            with self.service.lock:
                if not self.service.accepting:
                    return False
            docs = [d['id'] for d in self.service.list_documents()]
            if self.last_document in docs:
                index = docs.index(self.last_document) + 1
                docs = docs[index:] + docs[:index]
            for document in docs:
                try:
                    worked = self._step(document)
                except Exception as exc:
                    code = ('publication_uncertain' if isinstance(exc, PublicationUncertain) else
                            'context_budget_exceeded' if isinstance(exc, RequestBudgetExceeded) else
                            'billing_error' if isinstance(exc, ModelError) and is_billing_error(exc) else
                            'transport_error' if isinstance(exc, ModelError) and exc.is_retryable else
                            'configuration_error' if isinstance(exc, ModelError) else 'background_error')
                    self._update(document, status='blocked', error_code=code)
                    worked = True
                if worked:
                    self.last_document = document
                    return True
            return False
        finally:
            self.lock.release()

    def _step(self, document):
        row = self._row(document)
        b1, b2 = self._workflows(document)
        reader, publication = b1.reader, b2.publication
        head = publication.current()
        cursor = head.processed_source if head else None
        if row and row['source_reference'] and reader.source_covered(row['source_reference'], cursor):
            # Commit may have succeeded while the caller did not see its reply.
            # Finish the saved B2 publish node through its existing receipt path.
            pending = b2.graph.get_state(b2.config)
            if pending.next:
                if pending.next != ('publish',) or not pending.values.get('request'):
                    raise ValueError('Covered source has an unexpected pending B2 step')
                b2.resume()
            self._complete(document, row, reader, cursor)
            return True
        if row and row['status'] == 'blocked':
            return False
        if row and row['status'] == 'running':
            if row['recovery_count'] >= self.max_recoveries:
                self._update(document, status='blocked', error_code='recovery_limit')
                return True
            row = self._update(document, recovery_count=row['recovery_count'] + 1)
        if not row or row['status'] == 'idle':
            pending2, pending1 = b2.graph.get_state(b2.config), b1.graph.get_state(b1.config)
            old = (pending2.values if pending2.next else
                   pending1.values if pending1.values and
                   not reader.source_covered(pending1.values['source_reference'], cursor) else None)
            if old:
                if old.get('replaces_summary'):
                    raise ValueError('Explicit maintenance job requires its original recovery route')
                reference = old['source_reference']
                row = self._update(document, status='queued', target_reference=reference,
                                   source_reference=reference, error_code=None, recovery_count=0)
            else:
                source = reader.unprocessed_source(cursor)
                if not source:
                    return False
                if not reader.pending_consolidation_turns(cursor) and not (
                        self.text_threshold is not None and source['visible_chars'] >= self.text_threshold):
                    return False
                row = self._update(document, status='queued', target_reference=source['reference'],
                                   source_reference=None, error_code=None, recovery_count=0)
        if not row['source_reference']:
            source = reader.unprocessed_source(cursor, through_reference=row['target_reference'])
            if source is None:
                self._complete(document, row, reader, cursor)
                return True
            reference = reader.extraction_batch(source['reference'], max_chars=b1.max_chars,
                        context_chars=b1.context_chars, max_windows=b1.max_windows)
            row = self._update(document, source_reference=reference)
        self._update(document, status='running', error_code=None)
        pending2 = b2.graph.get_state(b2.config)
        if pending2.next:
            b2.resume()
        else:
            pending1 = b1.graph.get_state(b1.config)
            if pending1.next:
                if pending1.values['source_reference'] != row['source_reference']:
                    raise ValueError('Pending extraction must not be replaced by new input')
                b1.resume()
            else:
                b1.start(row['source_reference'])
            b2.start()
        head = publication.current()
        cursor = head.processed_source if head else None
        if not reader.source_covered(row['source_reference'], cursor):
            raise ValueError('Consolidation returned without publishing its source')
        self._complete(document, row, reader, cursor)
        return True

    def _complete(self, document, row, reader, cursor):
        covered = reader.source_covered(row['target_reference'], cursor)
        self._update(document, status='idle' if covered else 'queued',
                     target_reference=None if covered else row['target_reference'],
                     source_reference=None, error_code=None, recovery_count=0)

    def notice(self, document):
        """Read current availability only; never run/resume B from A's context."""
        row = self._row(document)
        if not row or row['status'] != 'blocked':
            return ''
        b1, b2 = self._workflows(document)
        head = b2.publication.current()
        if row['target_reference'] and head and b1.reader.source_covered(row['target_reference'], head.processed_source):
            return ''
        return ('最近一段訪談尚未成功整理進長期記憶；原始問答仍保存。'
                '不要假定記憶已包含這段資料，必要時回查訪談。'
                '這是程式的記憶可用性提示，不是員工工作事實；不要要求員工修理技術設定。'
                + ('\n本次尚未完整整理的訪談範圍：' + row['target_reference'] if row['target_reference'] else ''))


class BackgroundContextState(AgentState):
    background_notice: str
    background_turn_id: str


class BackgroundAvailability(AgentMiddleware):
    state_schema = BackgroundContextState

    def __init__(self, service, document):
        self.service, self.document = service, document

    def before_agent(self, state, runtime):
        from langchain_core.messages import HumanMessage
        current = next(m.id for m in reversed(state['messages']) if isinstance(m, HumanMessage))
        if state.get('background_turn_id') == current:
            return None
        dispatcher = self.service.background
        return {'background_turn_id': current,
                'background_notice': dispatcher.notice(self.document) if dispatcher else ''}

    def wrap_model_call(self, request, handler):
        notice = request.state.get('background_notice')
        if not notice:
            return handler(request)
        base = request.system_message.content if request.system_message else ''
        blocks = [{'type': 'text', 'text': base}] if isinstance(base, str) else list(base)
        blocks.append({'type': 'text', 'text': '<background_memory_availability>\n' + notice + '\n</background_memory_availability>'})
        return handler(request.override(system_message=SystemMessage(content=blocks)))
