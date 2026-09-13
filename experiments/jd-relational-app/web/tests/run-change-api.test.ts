import assert from 'node:assert/strict';
import { test } from 'node:test';
import { ApiError, JdApi } from '../src/lib/api.ts';

const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const DOC = id(1), DATASET = id(2), RUN = id(3), OTHER = id(4);
const origin = 'http://127.0.0.1:9000';
const path = `/api/documents/${DOC}/chat/runs/${RUN}/changes`;
const header = (index = 0) => ({ type: 'change', change_index: index, kind: 'update', entity_kind: 'profile',
  before_exists: true, after_exists: true, changed_fields: ['purpose'] });
const field = (side = 'after', index = 0) => ({ type: 'value', change_index: index, side,
  record: { type: 'field', item_ref: null, section_ref: `${side}-section`, field_ref: `${side}-field`, name: 'purpose', value: '繁中\n完整原文😀' } });
const page = (overrides: object = {}) => ({ format_version: 1, view: 'run_change', access: 'history',
  dataset_id: DATASET, document_id: DOC, run_id: RUN, capture_ref: 'fixed-capture-offset-zero',
  effects_state: 'unconfirmed', continuity: 'continuous', captured_operation_count: 2,
  base_revision_ref: 'S', result_revision_ref: 'E', records: [header(), field('before'), field()],
  start_index: 0, total_records: 3, total_changes: 1, has_more: false, next_cursor: null, oversized_unit: false, ...overrides });
const json = (value: unknown, status = 200, media = 'application/json') => new Response(JSON.stringify(value), {
  status, headers: { 'Content-Type': media } });
function client(...responses: (Response | Error | (() => Response))[]) {
  const calls: { url: string; init: RequestInit }[] = [];
  const api = new JdApi(origin, async function (this: unknown, url, init) {
    assert.equal(this, undefined);
    calls.push({ url: String(url), init: init ?? {} });
    const next = responses.shift();
    if (!next || next instanceof Error) throw next ?? new Error('unexpected request');
    return typeof next === 'function' ? next() : next;
  });
  api.datasetId = DATASET;
  return { api, calls };
}
const invalid = (error: unknown) => error instanceof ApiError && error.code === 'invalid_response';

test('run changes assemble a fixed captured range across pages using only GET', async () => {
  const before = page({ records: [header()], has_more: true, next_cursor: 'cursor.1' });
  const after = page({ records: [field('before'), field()], start_index: 1 });
  const { api, calls } = client(json(before), json(after));
  assert.deepEqual(await api.runChanges(DOC, RUN), page());
  assert.equal(calls.length, 2);
  assert.equal(calls[0].url, origin + path);
  assert.equal(calls[1].url, origin + path + '?cursor=cursor.1');
  for (const { init } of calls) {
    assert.equal(init.method, 'GET'); assert.equal(init.body, undefined);
    assert.equal(new Headers(init.headers).get('X-JD-Dataset'), DATASET);
    assert.equal(init.cache, 'no-store'); assert.equal(init.credentials, 'omit');
  }
});

for (const continuity of ['none', 'continuous', 'discontinuous'])
  test(`empty ${continuity} projection retains distinct captured event semantics`, async () => {
    const value = page({ continuity, captured_operation_count: continuity === 'none' ? 0 : 2,
      base_revision_ref: continuity === 'continuous' ? 'S' : null, result_revision_ref: continuity === 'continuous' ? 'E' : null,
      records: [], total_records: 0, total_changes: 0 });
    assert.deepEqual(await client(json(value)).api.runChanges(DOC, RUN), value);
  });

for (const [fieldName, value] of Object.entries({ dataset_id: OTHER, document_id: OTHER, run_id: OTHER,
  format_version: 2, capture_ref: 'new-capture', effects_state: 'settled', continuity: 'discontinuous',
  captured_operation_count: 3, base_revision_ref: 'different-S', result_revision_ref: 'different-E', total_records: 4, total_changes: 2 }))
  test(`continued run page cannot change ${fieldName}`, async () => {
    const first = page({ records: [header()], has_more: true, next_cursor: 'cursor.1' });
    const second = page({ records: [field('before'), field()], start_index: 1, [fieldName]: value });
    await assert.rejects(client(json(first), json(second)).api.runChanges(DOC, RUN), invalid);
  });

for (const overrides of [{ start_index: 1 }, { dataset_id: OTHER }, { document_id: OTHER }, { run_id: OTHER },
  { has_more: true }, { next_cursor: 'orphan' }, { oversized_unit: true },
  { records: [], has_more: true, next_cursor: 'empty' }, { total_records: 4 }, { total_records: 2 },
  { continuity: 'none' }, { captured_operation_count: 0 }, { base_revision_ref: null },
  { continuity: 'discontinuous', base_revision_ref: null, result_revision_ref: null }])
  test('invalid initial framing or contradictory source-schema values fail closed', async () => {
    await assert.rejects(client(json(page(overrides))).api.runChanges(DOC, RUN), invalid);
  });

test('cursor and offset must advance and never loop', async () => {
  const first = page({ records: [header()], has_more: true, next_cursor: 'cursor.1' });
  for (const second of [page({ records: [field('before'), field()], start_index: 0 }),
    page({ records: [field('before')], start_index: 1, has_more: true, next_cursor: 'cursor.1' })]) {
    const { api, calls } = client(json(first), json(second));
    await assert.rejects(api.runChanges(DOC, RUN), invalid);
    assert.equal(calls.length, 2);
  }
});

for (const [records, total_changes] of [
  [[field()], 1], [[header(1), field('after', 1)], 1], [[header(), header()], 1],
  [[header(), field('after', 1)], 1], [[header()], 2], [[header(), field(), header(2)], 3],
] as const)
  test('complete transport must contain every declared change group once in sequence', async () => {
    await assert.rejects(client(json(page({ records, total_records: records.length, total_changes }))).api.runChanges(DOC, RUN), invalid);
  });

test('oversized atomic historical record stays intact while assembling the complete page', async () => {
  const large = field(); large.record.value = '原文\n'.repeat(20000);
  const first = page({ records: [header()], total_records: 2, has_more: true, next_cursor: 'next' });
  const second = page({ records: [large], start_index: 1, total_records: 2, oversized_unit: true });
  const result = await client(json(first), json(second)).api.runChanges(DOC, RUN);
  assert.deepEqual(result.records, [header(), large]);
});

test('known dataset and canonical route identities are required before any request', async () => {
  const { api, calls } = client();
  api.datasetId = null;
  await assert.rejects(api.runChanges(DOC, RUN), (error: unknown) => error instanceof ApiError && error.code === 'dataset_required');
  api.datasetId = DATASET;
  for (const [doc, run] of [['wrong', RUN], [DOC, 'wrong']]) await assert.rejects(api.runChanges(doc, run));
  assert.equal(calls.length, 0);
});

test('dataset replacement during the request invalidates the late page', async () => {
  const { api } = client(() => { api.datasetId = OTHER; return json(page()); });
  await assert.rejects(api.runChanges(DOC, RUN), (error: unknown) => error instanceof ApiError && error.code === 'dataset_changed');
});

test('lost read response remains unknown and never retries, cancels or replays a model', async () => {
  const { api, calls } = client(new Error('SyntheticPrivateDriverData'));
  await assert.rejects(api.runChanges(DOC, RUN), (error: unknown) =>
    error instanceof ApiError && error.code === 'response_unknown' && !error.message.includes('SyntheticPrivate'));
  assert.equal(calls.length, 1); assert.equal(calls[0].init.method, 'GET');
});

test('read endpoint preserves a known safe chat Problem and rejects unknown error content', async () => {
  const value = { type: 'about:blank', title: 'Service Unavailable', status: 503, detail: '請重新查看原回合。',
    instance: `urn:uuid:${RUN}`, code: 'service_unavailable', next_action: 'lookup_run' };
  await assert.rejects(client(json(value, 503, 'application/problem+json')).api.runChanges(DOC, RUN),
    (error: unknown) => error instanceof ApiError && error.code === 'service_unavailable' && error.message === value.detail);
  await assert.rejects(client(json({ ...value, secret: 'SyntheticPrivate' }, 503, 'application/problem+json')).api.runChanges(DOC, RUN), invalid);
  await assert.rejects(client(json(page(), 202)).api.runChanges(DOC, RUN), invalid);
});
