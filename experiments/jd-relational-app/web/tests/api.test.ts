import assert from 'node:assert/strict';
import { test } from 'node:test';
import { ApiError, JdApi, decode, validateManualRequest } from '../src/lib/api.ts';
import type { ManualSaveInput } from '../../src/jd_relational/generated/jd-manual-http';

const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const DOC = id(1), DATASET = id(2), OP = id(3), KEY = id(4);
const request: ManualSaveInput = { operation_id: OP, base_revision_ref: 'original-revision', command: {
  tool: 'jd_set_text', arguments: { target_field_ref: 'current-field', text: '繁中\n修正', basis_refs: [] } } };
const committed = { status: 'committed', effect: 'changed', receipt_durability: 'confirmed',
  operation_ref: 'original-operation', result_revision_ref: 'original-result', change_ref: 'original-change', error: null, next_action: 'continue' };
const stale = { status: 'stale_view', effect: 'unchanged', receipt_durability: 'confirmed',
  operation_ref: 'original-operation', result_revision_ref: null, change_ref: null,
  error: { code: 'stale_view', message: '請讀取目前稿。', related_refs: [] }, next_action: 'reread_current' };
const unknown = { status: 'outcome_unknown', effect: 'unknown', receipt_durability: 'unconfirmed',
  operation_ref: 'original-operation', result_revision_ref: null, change_ref: null,
  error: { code: 'outcome_unknown', message: '請查回原結果。', related_refs: [] }, next_action: 'reconcile_operation' };
const writable = { ready: true, archived: false, write_blocked: false, running: false, operation_id: null, error: null };
const document = { document_id: DOC, title: '自己的工作', archived: false, metadata_version: 1,
  created_at: '2026-09-13T00:00:00Z', updated_at: '2026-09-13T00:00:00Z' };
const section = (key: 'profile' | 'purpose' = 'profile') => ({ type: 'section', section_ref: `opaque-${key}`, section_key: key, title: key });
const page = (overrides: object = {}) => ({ format_version: 2, view: 'current', access: 'current', revision_ref: 'revision',
  records: [section()], start_index: 0, total_records: 1, has_more: false, next_cursor: null, oversized_unit: false, ...overrides });
const change = (overrides: object = {}) => ({ format_version: 2, view: 'change', access: 'history', change_ref: 'change',
  operation_ref: 'operation', base_revision_ref: 'before', result_revision_ref: 'after', origin: 'manual',
  records: [{ type: 'change', change_index: 0, kind: 'update', entity_kind: 'profile', before_exists: true, after_exists: true, changed_fields: ['purpose'] }],
  start_index: 0, total_records: 1, total_changes: 1, has_more: false, next_cursor: null, oversized_unit: false, ...overrides });
const json = (value: unknown, status = 200, headers: Record<string, string> = {}) => new Response(JSON.stringify(value), {
  status, headers: { 'Content-Type': 'application/json', ...headers } });
const problem = (result = stale) => ({ type: 'about:blank', title: 'Conflict', status: 409,
  detail: '請重新查看。', instance: `urn:uuid:${OP}`, jd_result: result });
function client(...responses: (Response | Error)[]) {
  const calls: { url: string; init: RequestInit }[] = [];
  const fetcher: typeof fetch = async (input, init) => {
    calls.push({ url: String(input), init: init ?? {} });
    const next = responses.shift();
    if (!next || next instanceof Error) throw next ?? new Error('unexpected extra request');
    return next;
  };
  const api = new JdApi('http://127.0.0.1:9000', fetcher); api.datasetId = DATASET;
  return { api, calls };
}
const invalid = (error: unknown) => error instanceof ApiError && error.code === 'invalid_response';

test('fetch is called without binding the JdApi instance as its receiver', async () => {
  let observedReceiver: unknown = 'not called';
  const calls: { url: string; method: string | undefined }[] = [];
  // A normal function observes the receiver; an arrow would conceal this regression.
  const fetcher: typeof fetch = async function (this: unknown, input, init) {
    observedReceiver = this;
    calls.push({ url: String(input), method: init?.method });
    return json({ dataset_id: DATASET, documents: [], next_after: null });
  };
  const api = new JdApi('http://127.0.0.1:9000', fetcher);
  assert.deepEqual(await api.list(), { dataset_id: DATASET, documents: [], next_after: null });
  assert.equal(observedReceiver, undefined, 'native browser fetch must not be invoked as a JdApi method');
  assert.deepEqual(calls, [{ url: 'http://127.0.0.1:9000/api/documents?archived=false', method: 'GET' }]);
});

test('AJV validates authoritative command schema without coercion or injected identities', () => {
  validateManualRequest(request);
  assert.throws(() => validateManualRequest({ ...request, operation_id: 3 }), invalid);
  assert.throws(() => validateManualRequest({ ...request, item_id: DOC }), invalid);
  assert.throws(() => decode('read', 'ReadPage', page({ format_version: 1 })), invalid);
});

test('save receives exact original confirmed failure through the root HTTP Problem schema', async () => {
  const { api, calls } = client(json(problem(), 409, { 'Content-Type': 'application/problem+json' }));
  assert.deepEqual(await api.save(DOC, request), stale);
  assert.equal(calls.length, 1);
});

test('query root Problem preserves stale_view instead of undefined or unknown errors', async () => {
  const { api } = client(json({ type: 'about:blank', title: 'Conflict', status: 409, detail: '請讀取目前稿。',
    instance: `urn:uuid:${OP}`, jd_read_error: { type: 'read_error', code: 'stale_view', message: '請讀取目前稿。', next_action: 'reread_current' } },
  409, { 'Content-Type': 'application/problem+json' }));
  await assert.rejects(api.read(DOC), (error: unknown) => error instanceof ApiError && error.code === 'stale_view');
});

test('wire status must match the validated HTTP Problem status', async () => {
  const { api } = client(json(problem(), 500, { 'Content-Type': 'application/problem+json' }));
  await assert.rejects(api.save(DOC, request), invalid);
});

for (const [name, response] of [
  ['non-JSON media', () => json(committed, 200, { 'Content-Type': 'text/plain' })],
  ['unknown observation reported as HTTP 200', () => json(unknown, 200)],
  ['confirmed write reported as HTTP 202', () => json(committed, 202)],
] as const) test(`save rejects ${name}`, async () => {
  await assert.rejects(client(response()).api.save(DOC, request), invalid);
});

test('unknown original observation is retained and never replayed by the API client', async () => {
  const { api, calls } = client(json(unknown, 202), json({ operation_id: OP, presence: 'pending', result: unknown,
    write_state: { ready: true, archived: false, write_blocked: true, running: true, operation_id: OP, error: 'busy' } }));
  assert.deepEqual(await api.save(DOC, request), unknown);
  assert.equal((await api.operation(DOC, OP)).presence, 'pending');
  assert.equal(calls.length, 2);
  assert.equal(calls[1].init.method, 'GET');
  assert.deepEqual(JSON.parse(String(calls[0].init.body)), request);
});

test('network abort does not trigger new operation submission or claim rollback', async () => {
  const { api, calls } = client(new Error('private transport failure'));
  await assert.rejects(api.save(DOC, request), (error: unknown) => error instanceof ApiError
    && error.code === 'response_unknown' && !error.message.includes('private'));
  assert.equal(calls.length, 1);
});

for (const [name, response] of [
  ['has_more without cursor', page({ has_more: true })],
  ['wrong requested view', page({ view: 'history', access: 'history' })],
  ['wrong current access', page({ access: 'history' })],
  ['oversized page with two records', page({ records: [section(), section('purpose')], total_records: 2, oversized_unit: true })],
] as const) test(`read rejects ${name}`, async () => {
  await assert.rejects(client(json(response)).api.read(DOC), invalid);
});

test('read joins full same-version records and preserves complete Unicode text', async () => {
  const text = '繁中🙂\n重複文字；重複文字'.repeat(1000);
  const { api, calls } = client(json(page({ total_records: 2, has_more: true, next_cursor: 'opaque-cursor' })),
    json(page({ start_index: 1, records: [{ type: 'field', field_ref: 'f', section_ref: 'opaque-profile', item_ref: null,
      name: 'job_title', value: text }], total_records: 2 })));
  const received = await api.read(DOC);
  assert.equal(received.records.length, 2);
  assert.equal(received.records[1].type === 'field' && received.records[1].value, text);
  assert.deepEqual(JSON.parse(String(calls[1].init.body)), { view: 'current', target_ref: null, cursor: 'opaque-cursor' });
});

test('read cannot revise expected total count halfway through a paginated response', async () => {
  const { api } = client(json(page({ total_records: 7, has_more: true, next_cursor: 'c' })),
    json(page({ records: [section('purpose')], start_index: 1, total_records: 2 })));
  await assert.rejects(api.read(DOC), invalid);
});

for (const [key, changed] of [['base_revision_ref', 'different-base'], ['result_revision_ref', 'different-result'], ['origin', 'ai'], ['total_changes', 2]] as const)
  test(`change pagination fixes original ${key}`, async () => {
    const { api } = client(json(change({ total_records: 2, has_more: true, next_cursor: 'c' })),
      json(change({ [key]: changed, records: [{ type: 'value', change_index: 0, side: 'before', record: section() }], start_index: 1, total_records: 2 })));
    await assert.rejects(api.changes(DOC, 'change'), invalid);
  });

test('change first page cannot start after omitted records', async () => {
  await assert.rejects(client(json(change({ start_index: 5 }))).api.changes(DOC, 'change'), invalid);
});

test('creation lookup verifies original key and dataset, including not_found', async () => {
  const input = { request_key: KEY, dataset_id: DATASET, title: '原始名稱' };
  for (const wrong of [{ request_key: id(8) }, { dataset_id: id(9) }]) {
    const { api } = client(json({ state: 'not_found', request_key: KEY, dataset_id: DATASET, document_id: null, ...wrong }));
    await assert.rejects(api.lookupCreation(input), invalid);
  }
});

test('creation input from another dataset fails before fetch, without replacing its key', async () => {
  const input = { request_key: KEY, dataset_id: id(9), title: '原始名稱' };
  const { api, calls } = client(json({ request_key: KEY, dataset_id: id(9), document_id: DOC }));
  await assert.rejects(api.create(input), (error: unknown) => error instanceof ApiError && error.code === 'dataset_changed');
  assert.equal(calls.length, 0);
});

test('metadata update validates returned document identity and requires a strong opaque ETag', async () => {
  for (const [value, etag] of [[{ ...document, document_id: id(8) }, '"opaque"'], [document, 'W/"weak"'], [document, '']] as const) {
    const { api } = client(json(value, 200, { ETag: etag }));
    await assert.rejects(api.updateMetadata(DOC, { title: '新名稱' }, '"old"'), invalid);
  }
});

test('metadata uses conditional merge-patch and retains server document semantics', async () => {
  const { api, calls } = client(json(document, 200, { ETag: '"returned-opaque"' }));
  assert.deepEqual(await api.updateMetadata(DOC, { archived: true }, '"original-opaque"'), document);
  const headers = new Headers(calls[0].init.headers);
  assert.equal(headers.get('If-Match'), '"original-opaque"');
  assert.equal(headers.get('Content-Type'), 'application/merge-patch+json');
  assert.equal(headers.get('X-JD-Dataset'), DATASET);
});

test('operation lookup preserves original result and rejects another operation identity', async () => {
  const { api } = client(json({ operation_id: OP, presence: 'observed', result: stale, write_state: writable }));
  assert.deepEqual((await api.operation(DOC, OP)).result, stale);
  await assert.rejects(client(json({ operation_id: id(9), presence: 'observed', result: stale, write_state: writable })).api.operation(DOC, OP), invalid);
});

test('catalog cursor cannot advance without any document or cycle indefinitely', async () => {
  const { api, calls } = client(json({ dataset_id: DATASET, documents: [], next_after: id(8) }),
    json({ dataset_id: DATASET, documents: [], next_after: id(9) }));
  await assert.rejects(api.list(), invalid);
  assert.equal(calls.length, 1);
});

for (const [name, overrides] of [
  ['record outside declared change count', { total_changes: 0 }],
  ['missing first header', { records: [{ type: 'value', change_index: 0, side: 'before', record: section() }] }],
  ['omitted earlier change', { records: [{ ...change().records[0], change_index: 1 }], total_changes: 2 }],
] as const) test(`change groups reject ${name}`, async () => {
  await assert.rejects(client(json(change(overrides))).api.changes(DOC, 'change'), invalid);
});

test('change pagination may split one change while preserving exact historical values', async () => {
  const { api } = client(json(change({ total_records: 2, has_more: true, next_cursor: 'cursor' })),
    json(change({ start_index: 1, total_records: 2, records: [{ type: 'value', change_index: 0, side: 'after', record: section() }] })));
  const result = await api.changes(DOC, 'change');
  assert.equal(result.records.length, 2);
  assert.equal(result.base_revision_ref, 'before');
  assert.equal(result.result_revision_ref, 'after');
});

test('empty unchanged operation has a complete empty change page', async () => {
  const result = await client(json(change({ records: [], total_records: 0, total_changes: 0 }))).api.changes(DOC, 'change');
  assert.deepEqual(result.records, []);
});

test('history and historical item reads keep read-only access without decoding refs', async () => {
  for (const view of ['history', 'item'] as const) {
    const { api } = client(json(page({ view, access: 'history' })));
    const result = await api.read(DOC, { view, target_ref: 'history-opaque-ref', cursor: null });
    assert.equal(result.access, 'history');
  }
});

test('current page from a changed revision never combines with the previous page', async () => {
  const { api } = client(json(page({ total_records: 2, has_more: true, next_cursor: 'c' })),
    json(page({ revision_ref: 'new-head', start_index: 1, total_records: 2 })));
  await assert.rejects(api.read(DOC), (error: unknown) => error instanceof ApiError && error.code === 'stale_view');
});

test('catalog paginates with stable dataset and original IDs; changed dataset is retained as error', async () => {
  const { api, calls } = client(json({ dataset_id: DATASET, documents: [document], next_after: DOC }),
    json({ dataset_id: DATASET, documents: [{ ...document, document_id: id(5) }], next_after: null }));
  assert.equal((await api.list()).documents.length, 2);
  assert.match(calls[1].url, new RegExp(`after=${DOC}`));
  const changed = client(json({ dataset_id: id(9), documents: [], next_after: null })).api;
  await assert.rejects(changed.list(), (error: unknown) => error instanceof ApiError && error.code === 'dataset_changed');
  assert.equal(changed.datasetId, DATASET);
});

test('creation sends and looks up unchanged original payload without deriving a new key', async () => {
  const input = { request_key: KEY, dataset_id: DATASET, title: '原始名稱' };
  const created = { request_key: KEY, dataset_id: DATASET, document_id: DOC };
  const { api, calls } = client(json(created), json({ ...created, state: 'found' }));
  assert.deepEqual(await api.create(input), created);
  assert.equal((await api.lookupCreation(input)).document_id, DOC);
  assert.deepEqual(calls.map(call => JSON.parse(String(call.init.body))), [input, input]);
});

test('explicit recovery sends only empty body to the original operation and preserves not_found', async () => {
  const { api, calls } = client(json({ operation_id: OP, presence: 'not_found', result: null, write_state: writable }));
  const result = await api.operation(DOC, OP, true);
  assert.equal(result.presence, 'not_found');
  assert.equal(result.result, null);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].init.body, '{}');
  assert.ok(calls[0].url.endsWith(`/operations/${OP}/recover`));
});

test('safe manual and configured dataset Problems preserve their generated error codes', async () => {
  for (const [status, code, next_action] of [[403, 'origin_not_allowed', 'stop'], [409, 'dataset_changed', 'reread']] as const) {
    const { api } = client(json({ type: 'about:blank', title: 'Request blocked', status, code, next_action,
      detail: '請重新查看。', instance: `urn:uuid:${OP}` }, status, { 'Content-Type': 'application/problem+json' }));
    await assert.rejects(api.save(DOC, request), (error: unknown) => error instanceof ApiError && error.code === code);
  }
});

const preview = (overrides: object = {}) => ({ format_version: 2, view: 'restore_preview', access: 'current',
  base_revision_ref: 'head-now', target_revision_ref: 'older',
  records: [{ type: 'change', change_index: 0, kind: 'delete', entity_kind: 'duty', before_exists: true, after_exists: false, changed_fields: [] }],
  start_index: 0, total_records: 1, total_changes: 1, has_more: false, next_cursor: null, oversized_unit: false, ...overrides });

test('a restore preview reads only, and says which head it compared against', async () => {
  const { api, calls } = client(json(preview()));
  const page = await api.restorePreview(DOC, 'older');
  assert.equal(page.view, 'restore_preview');
  assert.equal(page.base_revision_ref, 'head-now');
  assert.equal(page.total_changes, 1);
  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/jd\/restore\/preview$/);
  assert.deepEqual(JSON.parse(String(calls[0].init.body)), { target_revision_ref: 'older', cursor: null });
});

test('a preview page that answers about another revision is refused', async () => {
  const { api } = client(json(preview({ target_revision_ref: 'someone-else' })));
  await assert.rejects(() => api.restorePreview(DOC, 'older'), (error: ApiError) => error.code === 'invalid_response');
});

test('a preview whose declared total does not match what arrived is refused', async () => {
  const { api } = client(json(preview({ total_records: 2 })));
  await assert.rejects(() => api.restorePreview(DOC, 'older'), (error: ApiError) => error.code === 'invalid_response');
});

const sourcePage = (overrides: object = {}) => ({ format_version: 2, view: 'source_read', access: 'history',
  source_ref: 'opaque-source', messages: [{ message_id: 'm1', role: 'user', text: '我每週巡檢設備。' }], ...overrides });

test('a marker reads back its own interview and nothing else', async () => {
  const { api, calls } = client(json(sourcePage()));
  const page = await api.sourceRead(DOC, 'opaque-source');
  assert.equal(page.view, 'source_read');
  assert.deepEqual(page.messages.map(m => [m.role, m.text]), [['user', '我每週巡檢設備。']]);
  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/jd\/sources\/read$/);
  assert.deepEqual(JSON.parse(String(calls[0].init.body)), { source_ref: 'opaque-source' });
});

test('an answer about another source is refused rather than shown', async () => {
  const { api } = client(json(sourcePage({ source_ref: 'someone-elses-source' })));
  await assert.rejects(() => api.sourceRead(DOC, 'opaque-source'),
    (error: ApiError) => error.code === 'invalid_response');
});

test('an interview with no messages is refused, because that is not an answer', async () => {
  const { api } = client(json(sourcePage({ messages: [] })));
  await assert.rejects(() => api.sourceRead(DOC, 'opaque-source'),
    (error: ApiError) => error.code === 'invalid_response');
});
