"""Only wire boundary: generated DTOs plus authoritative JSON Schema validation."""
from base64 import urlsafe_b64decode, urlsafe_b64encode
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from uuid import UUID, uuid5, NAMESPACE_URL

from jsonschema import Draft202012Validator
from jd_editor_contract import models
from analysis_agent.jd_types import JdScope, JdManualIntent, JdWriteOutcome

PROFILE = {'format_version': 2, 'engine_profile': 'jd-plate-clean-v2'}
SCHEMA_PATH = Path(__file__).resolve().parents[3] / 'jd-editor/contract/generated/jd-editor-v2.schema.json'


@lru_cache
def _validator(name):
    schema = json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))
    return Draft202012Validator({'$ref': '#/$defs/' + name, '$defs': schema['$defs']},
                               format_checker=Draft202012Validator.FORMAT_CHECKER)


def validate(name, value):
    _validator(name).validate(value)
    return getattr(models, name).model_validate(value).model_dump(mode='json', exclude_unset=True)


def _ref(kind, scope, *ids):
    content = json.dumps([kind, scope.document_id, *map(str, ids)], separators=(',', ':'))
    return urlsafe_b64encode(content.encode()).decode().rstrip('=')


def parse_ref(ref, kind, scope, count=1):
    try:
        decoded = json.loads(urlsafe_b64decode(ref + '=' * (-len(ref) % 4)))
        if not isinstance(decoded, list) or len(decoded) != 2 + count or decoded[:2] != [kind, scope.document_id]:
            raise ValueError('Reference does not belong to this document')
        return tuple(UUID(item) for item in decoded[2:])
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ValueError('Invalid scoped JD reference') from exc


def revision_ref(scope, revision):
    return _ref('revision', scope, revision)


def operation_ref(scope, operation):
    return _ref('operation', scope, operation)


def request_digest(scope, base_id, payload, origin):
    value = {'document': scope.document_id, 'base': str(base_id), 'profile': PROFILE,
             'origin': origin, 'payload': payload}
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate_intent_digest(intent):
    payload = intent.value if intent.origin == 'manual' else intent.commands
    if intent.digest != request_digest(intent.scope, intent.base_id, payload, intent.origin):
        raise ValueError('JD intent digest does not match its exact payload')


def engine_error_status(code):
    if code in {'duplicate_id', 'invalid_span', 'referenced_item', 'invalid_relation_kind'}:
        return 'invalid_input'
    return code if code in {'invalid_input', 'unsupported_content', 'target_missing'} else 'engine_failed'


def read_failure_to_wire(view):
    action = {'invalid_input': 'correct_arguments', 'target_missing': 'reread_current', 'busy': 'wait'}.get(view.status, 'stop')
    return validate('JdReadFailure', {'status': view.status, 'document_effect': 'unchanged',
        'receipt_durability': 'unconfirmed', 'error': {'code': view.status,
        'message': 'Requested JD content could not be read.', 'command_index': None}, 'next_action': action})


def manual_intent(scope, body):
    body = validate('JdManualSaveClientInput', body)
    base, = parse_ref(body['base_revision_ref'], 'revision', scope)
    operation = uuid5(NAMESPACE_URL, json.dumps([scope.document_id, body['request_key']]))
    digest = request_digest(scope, base, body['value'], 'manual')
    request = {'document_ref': _ref('document', scope), 'submission_ref': operation_ref(scope, operation),
               'request_digest': digest, 'base_revision_ref': body['base_revision_ref'],
               'profile': PROFILE, 'value': body['value'], 'origin': 'manual'}
    validate('JdManualSaveRequest', request)
    return JdManualIntent(scope, operation, base, digest, deepcopy(body['value']))


def outcome_to_wire(outcome):
    o = outcome
    success = o.status in {'committed', 'no_change'}
    base = revision_ref(o.scope, o.base_id) if o.base_id else None
    result = revision_ref(o.scope, o.result_id) if o.result_id else None
    wire = {'status': o.status,
            'operation_ref': operation_ref(o.scope, o.operation_id) if o.operation_id else None,
            'base_revision_ref': base, 'result_revision_ref': result,
            'change_ref': _ref('change', o.scope, o.operation_id, o.base_id, o.result_id) if success else None,
            'document_effect': 'committed' if o.status == 'committed' else 'unknown' if o.status == 'outcome_unknown' else 'unchanged',
            'receipt_durability': o.durability,
            'actual_changes': {'origin': o.origin, 'before_revision_ref': base, 'after_revision_ref': result,
                               'native_operations': o.operations, 'affected_element_ids': o.affected_ids} if success else None,
            'error': None if success else {'code': o.error_code or o.status,
                      'message': o.error_message or 'JD operation did not complete.', 'command_index': o.command_index},
            'next_action': o.next_action}
    return validate('JdWriteResult', wire)


def outcome_from_row(scope, row):
    wire = validate('JdWriteResult', row['receipt'])
    if wire['status'] != row['status'] or wire['receipt_durability'] != 'confirmed':
        raise ValueError('Receipt column mismatch')
    for field, kind, expected in [('operation_ref', 'operation', row['operation_id']),
                                  ('base_revision_ref', 'revision', row['base_revision_id']),
                                  ('result_revision_ref', 'revision', row['result_revision_id'])]:
        actual = parse_ref(wire[field], kind, scope)[0] if wire[field] else None
        if actual != expected:
            raise ValueError('Receipt identity mismatch')
    changes, error = wire['actual_changes'], wire['error']
    if changes:
        if changes['origin'] != row['origin'] or changes['before_revision_ref'] != wire['base_revision_ref'] or changes['after_revision_ref'] != wire['result_revision_ref']:
            raise ValueError('Receipt change mismatch')
        if parse_ref(wire['change_ref'], 'change', scope, 3) != (row['operation_id'], row['base_revision_id'], row['result_revision_id']):
            raise ValueError('Receipt change identity mismatch')
    return JdWriteOutcome(scope, row['operation_id'], row['base_revision_id'], row['result_revision_id'],
        row['status'], row['origin'], operations=changes['native_operations'] if changes else None,
        affected_ids=changes['affected_element_ids'] if changes else [], error_code=error['code'] if error else None,
        error_message=error['message'] if error else None, command_index=error['command_index'] if error else None,
        next_action=wire['next_action'])
