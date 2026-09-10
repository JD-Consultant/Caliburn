"""Browser adapters over the same JD ports; no fabricated model/tool identity."""
import base64
import json
from uuid import UUID
from typing import Literal

from fastapi import APIRouter, Request, HTTPException
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool
from jd_editor_contract import models
from jsonschema import ValidationError
from analysis_agent.jd_contract import (validate, revision_ref, parse_ref, outcome_to_wire,
    manual_intent, manual_operation_id, read_failure_to_wire)
from analysis_agent.jd_references import elements, source_refs
from analysis_agent.jd_types import JdScope, JdReadQuery, JdChangeQuery, JdReadView
from analysis_agent.service import ServiceConflict

class ManualSaveRejection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    admission: Literal['not_admitted'] = 'not_admitted'
    request_key: str
    message: str


def rejected_manual(request, document, key, message, status=422):
    # Never infer zero-write from HTTP status or a failed receipt lookup.
    service, scope = scoped(request, document)
    if not isinstance(key, str) or not key:
        raise HTTPException(422, 'Manual submission identity is unavailable')
    try:
        canonical_key = str(UUID(key))
    except ValueError as exc:
        raise HTTPException(422, 'Manual submission identity is invalid') from exc
    with service.lock:
        try:
            original = service.jd.store.receipt(scope, manual_operation_id(scope, canonical_key))
        except Exception as exc:
            raise HTTPException(503, 'Manual receipt is unavailable') from exc
        if original:
            raise HTTPException(409, 'Existing identity requires its exact original payload')
        return JSONResponse(status_code=status, content=ManualSaveRejection(
            request_key=key, message=message).model_dump(mode='json'))


class ManualValidationRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def handle(request):
            try:
                return await handler(request)
            except RequestValidationError as exc:
                if self.path != '/documents/{document}/jd/manual-save':
                    raise
                body = exc.body if isinstance(exc.body, dict) else {}
                return await run_in_threadpool(rejected_manual, request, request.path_params['document'],
                    body.get('request_key'), 'Invalid manual submission')
        return handle


router = APIRouter(route_class=ManualValidationRoute)


def locator(scope, kind, **fields):
    return 'jd-browser:' + base64.urlsafe_b64encode(json.dumps(
        {'document': scope.document_id, 'kind': kind, **fields}, ensure_ascii=False,
        separators=(',', ':')).encode()).decode()


def resolve_locator(scope, ref, kind):
    try:
        if not ref.startswith('jd-browser:') or len(ref) > 16000:
            raise ValueError('Invalid browser locator')
        result = json.loads(base64.b64decode(ref[11:], altchars=b'-_', validate=True))
        if result['document'] != scope.document_id or result['kind'] != kind:
            raise ValueError('Wrong document or read kind')
        return result
    except (ValueError, KeyError, TypeError) as exc:
        raise ServiceConflict('Invalid document read reference') from exc


def read_document(service, scope, args):
    validate('JdReadModelInput', args)
    query, kind, offset = JdReadQuery(), 'current', 0
    if 'revision_ref' in args:
        query = JdReadQuery(parse_ref(args['revision_ref'], 'revision', scope)[0])
        kind = 'history'
    elif 'target_ref' in args:
        record = resolve_locator(scope, args['target_ref'], 'target')
        query = JdReadQuery(UUID(record['revision']), record['target'])
        kind = 'target'
    elif 'selection_ref' in args:
        record = resolve_locator(scope, args['selection_ref'], 'selection')
        query = JdReadQuery(UUID(record['revision']), selection=record['range'])
        kind = 'selection'
    elif 'continuation_ref' in args:
        record = resolve_locator(scope, args['continuation_ref'], 'read_page')
        query = JdReadQuery(UUID(record['revision']), record['target'], record['range'])
        kind, offset = record['read_kind'], record['offset']
        if not isinstance(offset, int) or offset < 0:
            raise ServiceConflict('Invalid read page')
    view = service.jd.read(scope, query)
    if view.status != 'ok':
        return read_failure_to_wire(view)
    revision = view.revision
    fragment = view.fragment[offset:offset+64]
    def target(node):
        return locator(scope, 'target', revision=str(revision.id), target=node['id'])
    nodes = list(elements(revision.value))
    index = {node['id']: node for node in nodes}
    targets = []
    for node in elements(fragment):
        item = {'target_ref': target(node), 'element': node, 'access': 'read_only'}
        if node['type'] == 'jd_task':
            for field in ('knowledge', 'skill'):
                item[field+'_refs'] = [target(index[id]) for id in node.get(field+'_ids', [])]
        if node['type'] in ('jd_knowledge', 'jd_skill'):
            field = 'knowledge_ids' if node['type'] == 'jd_knowledge' else 'skill_ids'
            item['used_by_task_refs'] = [target(n) for n in nodes if n['type'] == 'jd_task' and node['id'] in n.get(field, [])]
        targets.append(item)
    producer = service.jd.store.producer(scope, revision.id)
    continuation = locator(scope, 'read_page', revision=str(revision.id), target=query.target_id,
        range=query.selection, read_kind=kind, offset=offset+64) if offset+64 < len(view.fragment) else None
    return validate('JdReadSuccess', {'status':'ok', 'read_kind':kind,
        'revision_ref':revision_ref(scope, revision.id), 'access':'read_only', 'fragment':fragment,
        'targets':targets, 'selection':None, 'source_refs':source_refs(fragment),
        'change_refs':[outcome_to_wire(producer)['change_ref']] if producer else [], 'continuation_ref':continuation})


def read_changes(service, scope, args):
    validate('JdChangeReadModelInput', args)
    offset = 0
    if 'continuation_ref' in args:
        record = resolve_locator(scope, args['continuation_ref'], 'change_page')
        args, offset = record['args'], record['offset']
        if not isinstance(offset, int) or offset < 0:
            raise ServiceConflict('Invalid change page')
        validate('JdChangeReadModelInput', args)
    if 'change_ref' in args:
        operation, before, after = parse_ref(args['change_ref'], 'change', scope, 3)
        query = JdChangeQuery(operation_id=operation)
    else:
        before = parse_ref(args['before_revision_ref'], 'revision', scope)[0]
        after = parse_ref(args['after_revision_ref'], 'revision', scope)[0]
        query = JdChangeQuery(before_id=before, after_id=after)
    view = service.jd.change_read(scope, query)
    if view.status != 'ok':
        return read_failure_to_wire(JdReadView(status=view.status))
    if view.before.id != before or view.after.id != after:
        raise ServiceConflict('Change endpoints do not match receipt')
    before_value, after_value = view.before.value, view.after.value
    continuation = locator(scope, 'change_page', args=args, offset=offset+64) if offset+64 < max(len(before_value), len(after_value)) else None
    return validate('JdChangeReadSuccess', {'status':'ok', 'mode':'change' if view.outcome else 'revision_comparison',
        'change_ref':outcome_to_wire(view.outcome)['change_ref'] if view.outcome else None,
        'origin':view.outcome.origin if view.outcome else None,
        'before_revision_ref':revision_ref(scope, before), 'after_revision_ref':revision_ref(scope, after),
        'before_fragment':before_value[offset:offset+64], 'after_fragment':after_value[offset:offset+64],
        'native_operations':view.outcome.operations if view.outcome else None,
        'source_refs':source_refs([*before_value[offset:offset+64], *after_value[offset:offset+64]]),
        'presentation_limitations':['部分格式或關係差異未高亮，可查看兩版完整內容。'] if not view.outcome or view.outcome.operations is None else [],
        'continuation_ref':continuation})


def scoped(request, document):
    service = request.app.state.service
    service.catalog.document(document)
    if service.jd is None:
        raise HTTPException(503, 'JD service is unavailable')
    return service, JdScope(document)


@router.get('/documents/{document}/jd', response_model=models.JdReadResult, response_model_exclude_unset=True)
def current(document: str, request: Request):
    service, scope = scoped(request, document)
    return read_document(service, scope, {})


@router.post('/documents/{document}/jd/read', response_model=models.JdReadResult, response_model_exclude_unset=True)
def read(document: str, request: Request, data: models.JdReadModelInput):
    service, scope = scoped(request, document)
    try:
        return read_document(service, scope, data.model_dump(mode='json', exclude_unset=True))
    except (ValueError, ValidationError) as exc:
        raise HTTPException(422, 'Invalid scoped JD read') from exc


@router.post('/documents/{document}/jd/changes/read', response_model=models.JdChangeReadResult, response_model_exclude_unset=True)
def changes(document: str, request: Request, data: models.JdChangeReadModelInput):
    service, scope = scoped(request, document)
    try:
        return read_changes(service, scope, data.model_dump(mode='json', exclude_unset=True))
    except (ValueError, ValidationError) as exc:
        raise HTTPException(422, 'Invalid scoped JD change read') from exc


@router.post('/documents/{document}/jd/manual-save', response_model=models.JdManualSaveResult, response_model_exclude_unset=True,
    responses={409: {'model': ManualSaveRejection}, 422: {'model': ManualSaveRejection}})
def manual_save(document: str, request: Request, data: models.JdManualSaveClientInput):
    service, scope = scoped(request, document)
    try:
        intent = manual_intent(scope, data.model_dump(mode='json', exclude_unset=True))
    except (ValueError, ValidationError):
        return rejected_manual(request, document, str(data.request_key), 'Invalid scoped manual submission')
    with service.lock:
        original = service.jd.store.receipt(scope, intent.operation_id, intent.digest)
        if original:
            return outcome_to_wire(original)
        if service.catalog.document(document)['archived']:
            return rejected_manual(request, document, str(data.request_key), 'Document is archived', 409)
        if service._running(document) or any(r['status'] in {'receiving','running','stopping','uncertain','interrupted'} for r in service.catalog.runs(document)):
            return rejected_manual(request, document, str(data.request_key), 'Foreground run must close before manual save', 409)
        # Sources remain locators in the existing conversation owner.
        reader = service.reader(document)
        for reference in source_refs(intent.value):
            try:
                reader.read(reference)
            except ValueError:
                return rejected_manual(request, document, str(data.request_key), 'Source is unavailable in this document')
        return outcome_to_wire(service.jd.manual_save(intent))
