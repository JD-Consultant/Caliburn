"""Chat App adapter: native conversation, original effects and shared write gate.

No provider construction, second conversation table, implicit retry or model
replay. Browser request IDs are not passed to the LLM as authored parameters.
"""
import json
from uuid import UUID

from .ai_runtime import AiRuntime
from .generated.chat_http import ChatStartInput, ChatRunState, ChatHistoryPage
from .manual_service import ManualService
from .observation_projection import project_observation
from .transport import REQUEST_LIMIT


class ChatError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


_ERROR_MAP = {
    'invalid_input': 'invalid_input', 'invalid_ref': 'invalid_ref',
    'document_missing': 'document_missing', 'target_missing': 'document_missing',
    'stale_view': 'stale_view', 'operation_conflict': 'run_conflict',
    'document_busy': 'busy', 'document_archived': 'busy',
    'run_recovery_pending': 'busy', 'writer_not_stopped': 'busy',
    'run_recovery_required': 'recovery_required',
    'invalid_cursor': 'invalid_ref',
    'execution_disabled': 'ai_unavailable',
}


def _failure(error):
    if isinstance(error, ChatError):
        return error
    code = getattr(error, 'code', None)
    return ChatError(_ERROR_MAP.get(code, 'service_unavailable') if type(code) is str else 'service_unavailable')


def parse_chat_input(value, *, empty=False):
    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError()
            result[key] = item
        return result
    def reject(_):
        raise ValueError()
    try:
        raw = value if type(value) is str else json.dumps(value, ensure_ascii=False, allow_nan=False)
        if len(raw.encode('utf-8')) > REQUEST_LIMIT:
            raise ValueError()
        parsed = json.loads(raw, object_pairs_hook=unique, parse_constant=reject)
        if empty:
            if type(parsed) is not dict or parsed:
                raise ValueError()
            return {}
        result = ChatStartInput.model_validate(parsed, strict=True).model_dump(mode='json')
        if len(result['text'].encode('utf-8')) > 128 * 1024:
            raise ValueError()
        return result
    except Exception:
        raise ChatError('invalid_input') from None


def _state(value):
    flags = value['write_state']
    if (any(type(flags[key]) is not bool for key in ('ready','archived','write_blocked','running'))
            or value['stop_requested'] is not None and type(value['stop_requested']) is not bool):
        raise ChatError('service_unavailable')
    return ChatRunState.model_validate(value, strict=True).model_dump(mode='json')


class ChatService:
    def __init__(self, runtime: AiRuntime, manual: ManualService, history):
        if not isinstance(runtime, AiRuntime) or not isinstance(manual, ManualService) or manual.runtime is not runtime.owner:
            raise ValueError('invalid_chat_service')
        self.runtime, self.manual, self.history = runtime, manual, history

    def start(self, document_id, value):
        envelope = parse_chat_input(value)
        try:
            base = self.runtime.codec.resolve(envelope['expected_jd_revision_ref'],
                document_id=document_id, roles={'revision'}, purposes={'history','observation'})
            self.runtime.start(document_id, envelope['run_id'], envelope['text'],
                               expected_revision_id=UUID(base.revision_id))
            return self.status(document_id, envelope['run_id'])
        except Exception as error:
            raise _failure(error) from None

    def status(self, document_id, run_id):
        def read():
            # A run can close between native observation and the current gate.
            # One bounded reread avoids reporting a stale busy snapshot beside
            # a now-writable document. It never restarts or repairs the run.
            for _ in range(2):
                state = self.runtime.inspect_run(document_id, run_id)
                write = self.manual.status(document_id)
                if state.run_status in {'running','closing','recovery_required'} and not write['write_blocked']:
                    continue
                return _state({'dataset_id': self.runtime.codec.dataset_id,
                    'document_id': document_id, 'run_id': run_id,
                    'run_status': state.run_status, 'input_state': state.input_state,
                    'response_message_id': state.response_message_id,
                    'stop_requested': state.stop_requested, 'write_state': write,
                    'jd_effects': {'state': 'settled' if state.effects_settled else 'unconfirmed',
                        'results': [project_observation(item, self.runtime.codec) for item in state.receipts]}})
            raise ChatError('service_unavailable')
        try:
            return self.runtime.owner.inspect_document(document_id, read)
        except Exception as error:
            raise _failure(error) from None

    def cancel(self, document_id, run_id):
        try:
            self.runtime.request_stop(document_id, run_id)
            return self.status(document_id, run_id)
        except Exception as error:
            raise _failure(error) from None

    def recover(self, document_id, run_id):
        try:
            self.runtime.recover_run(document_id, run_id)
            return self.status(document_id, run_id)
        except Exception as error:
            raise _failure(error) from None

    def messages(self, document_id, *, cursor=None, limit=50):
        def read():
            # Saved conversation does not itself establish the JD still exists.
            self.runtime.owner.storage.read_current(document_id)
            result = self.history.read(document_id, cursor=cursor, limit=limit)
            return ChatHistoryPage.model_validate(result, strict=True).model_dump(mode='json')
        try:
            return self.runtime.owner.inspect_document(document_id, read)
        except Exception as error:
            raise _failure(error) from None
