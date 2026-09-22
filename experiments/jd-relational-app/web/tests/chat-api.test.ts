import assert from 'node:assert/strict';
import { test } from 'node:test';
import { ApiError, JdApi, validateChatRequest } from '../src/lib/api.ts';
import type { ChatStartInput } from '../../src/jd_relational/generated/jd-chat-http';

const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const DOC = id(1), DATASET = id(2), RUN = id(3), OTHER = id(4);
const origin = 'http://127.0.0.1:9000';
const runPath = `/api/documents/${DOC}/chat/runs/${RUN}`;
const request: ChatStartInput = { run_id: RUN, text: '原話\r\n  每月處理異常。😀', expected_jd_revision_ref: 'original-signed-revision' };
const writable = { ready: true, archived: false, write_blocked: false, running: false, operation_id: null, error: null };
const committed = { status: 'committed', effect: 'changed', receipt_durability: 'confirmed', operation_ref: 'original-operation',
  result_revision_ref: 'original-revision', change_ref: 'original-change', error: null, next_action: 'continue' };
const unknown = { status: 'outcome_unknown', effect: 'unknown', receipt_durability: 'unconfirmed', operation_ref: 'original-operation',
  result_revision_ref: null, change_ref: null, error: { code: 'outcome_unknown', message: '請查回。', related_refs: [] }, next_action: 'reconcile_operation' };
const state = (run_status = 'running', overrides: object = {}) => {
  const pending = ['running', 'closing', 'recovery_required'].includes(run_status);
  return { dataset_id: DATASET, document_id: DOC, run_id: RUN, run_status,
    input_state: pending || run_status === 'not_found' ? 'unconfirmed' : 'saved',
    write_state: { ...writable, write_blocked: pending }, response_message_id: null,
    stop_requested: run_status === 'running' ? false : null,
    jd_effects: { state: pending || run_status === 'not_found' ? 'unconfirmed' : 'settled', results: [] }, ...overrides };
};
const message = (message_id = RUN, role = 'user', run_id = RUN) => ({ message_id, run_id, role, text: '逐字\r\n  原稿😀' });
const page = (overrides: object = {}) => ({ dataset_id: DATASET, document_id: DOC, anchor: 'original-anchor', anchor_run_id: RUN,
  messages: [message()], next_cursor: null, ...overrides });
const json = (value: unknown, status = 200, headers: Record<string, string> = {}) => new Response(JSON.stringify(value), {
  status, headers: { 'Content-Type': 'application/json', ...headers } });
const control = (value = state(), status = 202, location = runPath) => json(value, status, { Location: location });
const problem = (code = 'ai_unavailable', status = 503, next_action = 'stop') => ({
  type: 'about:blank', title: 'Service Unavailable', status, code, next_action,
  detail: 'AI 訪談尚未啟用；請保留輸入。目前仍可查看原有對話及編輯 JD。', instance: `urn:uuid:${RUN}`,
});
function client(...responses: (Response | Error)[]) {
  const calls: { url: string; init: RequestInit }[] = [];
  const fetcher: typeof fetch = async function (this: unknown, input, init) {
    assert.equal(this, undefined, 'native fetch cannot receive JdApi as receiver');
    calls.push({ url: String(input), init: init ?? {} });
    const response = responses.shift();
    if (!response || response instanceof Error) throw response ?? new Error('unexpected extra request');
    return response;
  };
  const api = new JdApi(origin, fetcher); api.datasetId = DATASET;
  return { api, calls };
}
const invalid = (error: unknown) => error instanceof ApiError && error.code === 'invalid_response';

test('chat start sends the unchanged original request once and verifies its scoped pending result', async () => {
  validateChatRequest(request);
  const { api, calls } = client(control());
  assert.deepEqual(await api.chatStart(DOC, request), state());
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, `${origin}/api/documents/${DOC}/chat/runs`);
  assert.equal(calls[0].init.method, 'POST');
  assert.deepEqual(JSON.parse(String(calls[0].init.body)), request);
  const headers = new Headers(calls[0].init.headers);
  assert.equal(headers.get('X-JD-Dataset'), DATASET);
  assert.equal(headers.get('Content-Type'), 'application/json');
  assert.equal(calls[0].init.credentials, 'omit');
  assert.equal(calls[0].init.cache, 'no-store');
  assert.equal(calls[0].init.redirect, 'error');
});

for (const method of ['chatStatus', 'chatCancel', 'chatRecover'] as const)
  test(`${method} addresses only the original run and never repeats start`, async () => {
    const { api, calls } = client(method === 'chatStatus' ? json(state()) : control());
    assert.deepEqual(await api[method](DOC, RUN), state());
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, origin + runPath + (method === 'chatStatus' ? '' : method === 'chatCancel' ? '/cancel' : '/recover'));
    assert.equal(calls[0].init.method, method === 'chatStatus' ? 'GET' : 'POST');
    assert.equal(calls[0].init.body, method === 'chatStatus' ? undefined : '{}');
    assert.equal(new Headers(calls[0].init.headers).get('X-JD-Dataset'), DATASET);
  });

test('completed failed run can retain committed JD while an unknown run does not claim unsaved input', async () => {
  const failed = state('failed', { jd_effects: { state: 'settled', results: [committed] } });
  const missing = state('not_found');
  const { api } = client(control(failed, 200), json(missing));
  assert.deepEqual(await api.chatStart(DOC, request), failed);
  assert.deepEqual(await api.chatStatus(DOC, RUN), missing);
});

for (const method of ['chatStart', 'chatStatus', 'chatCancel', 'chatRecover', 'chatMessages'] as const)
  test(`${method} requires the known dataset before any request`, async () => {
    const { api, calls } = client(); api.datasetId = null;
    await assert.rejects(method === 'chatStart' ? api.chatStart(DOC, request)
      : method === 'chatMessages' ? api.chatMessages(DOC) : api[method](DOC, RUN),
    (error: unknown) => error instanceof ApiError && error.code === 'dataset_required');
    assert.equal(calls.length, 0);
  });

for (const field of ['dataset_id', 'document_id', 'run_id'] as const)
  test(`chat replies reject a different ${field}`, async () => {
    for (const method of ['chatStart', 'chatStatus', 'chatCancel', 'chatRecover'] as const) {
      const value = state('failed', { [field]: OTHER });
      const { api } = client(method === 'chatStatus' ? json(value) : control(value, 200));
      await assert.rejects(method === 'chatStart' ? api.chatStart(DOC, request) : api[method](DOC, RUN), invalid);
      assert.equal(api.datasetId, DATASET);
    }
  });

test('chat requests reject invalid original body and route IDs without sending', async () => {
  const { api, calls } = client();
  for (const value of [{ ...request, run_id: 5 }, { ...request, text: ' \n' },
    { ...request, text: '工\0作' }, { ...request, extra: true }, { run_id: RUN, text: '工作' }])
    await assert.rejects(api.chatStart(DOC, value as unknown as ChatStartInput));
  for (const value of ['other-document', DOC.toUpperCase().replace('00000000', 'abcdefAB'), DOC + '/elsewhere']) {
    await assert.rejects(api.chatStatus(value, RUN));
    await assert.rejects(api.chatStatus(DOC, value));
  }
  assert.equal(calls.length, 0);
});

for (const [value, status] of [[state(), 200], [state('completed'), 202], [state('not_found'), 202]] as const)
  test(`control HTTP ${status} must agree with run state ${value.run_status}`, async () => {
    await assert.rejects(client(control(value, status)).api.chatStart(DOC, request), invalid);
  });

test('GET status may report active or terminal state but never returns HTTP 202', async () => {
  for (const value of [state(), state('closing'), state('failed'), state('not_found')])
    assert.deepEqual(await client(json(value)).api.chatStatus(DOC, RUN), value);
  await assert.rejects(client(control()).api.chatStatus(DOC, RUN), invalid);
});

for (const location of ['', 'http://elsewhere.invalid' + runPath, runPath + '/cancel', runPath + '?wrong=1',
  runPath + '#wrong', runPath.replace(RUN, OTHER)])
  test(`control rejects mismatched Location ${location}`, async () => {
    await assert.rejects(client(control(state(), 202, location)).api.chatStart(DOC, request), invalid);
  });

test('Location may be same-origin absolute or relative and is never followed automatically', async () => {
  for (const location of [runPath, origin + runPath]) {
    const { api, calls } = client(control(state(), 202, location));
    await api.chatStart(DOC, request);
    assert.equal(calls.length, 1);
  }
});

test('unavailable AI is a fixed stop Problem and preserves original input without retries', async () => {
  const value = problem();
  const { api, calls } = client(json(value, 503, { 'Content-Type': 'application/problem+json' }));
  const before = structuredClone(request);
  await assert.rejects(api.chatStart(DOC, request), (error: unknown) =>
    error instanceof ApiError && error.code === 'ai_unavailable' && error.message === value.detail);
  assert.deepEqual(request, before);
  assert.equal(calls.length, 1);
});

for (const fault of [
  () => json(problem(), 500, { 'Content-Type': 'application/problem+json' }),
  () => json({ ...problem(), raw_error: 'private' }, 503, { 'Content-Type': 'application/problem+json' }),
  () => json({ ...problem('selection_not_available', 422), next_action: 'stop' }, 422, { 'Content-Type': 'application/problem+json' }),
  () => json({ type: 'about:blank', title: 'Conflict', status: 409, detail: 'private', instance: `urn:uuid:${RUN}`, jd_result: committed }, 409, { 'Content-Type': 'application/problem+json' }),
  () => json(state(), 202, { 'Content-Type': 'text/plain', Location: runPath }),
  () => new Response('private-non-json', { status: 200, headers: { 'Content-Type': 'application/json' } }),
]) test('unknown chat response shape never exposes private content as a recognized result', async () => {
  const { api, calls } = client(fault());
  await assert.rejects(api.chatStart(DOC, request), (error: unknown) => invalid(error) && !(error as Error).message.includes('private'));
  assert.equal(calls.length, 1);
});

test('network failure preserves uncertainty and does not request cancellation or replay', async () => {
  const { api, calls } = client(new Error('private connection detail'));
  await assert.rejects(api.chatStart(DOC, request), (error: unknown) =>
    error instanceof ApiError && error.code === 'response_unknown' && !error.message.includes('private'));
  assert.equal(calls.length, 1);
  assert.deepEqual(JSON.parse(String(calls[0].init.body)), request);
});

for (const value of [
  state('completed', { jd_effects: { state: 'settled', results: [unknown] } }),
  state('running', { write_state: writable }),
  state('running', { write_state: { ...writable, write_blocked: 1 } }),
  state('not_found', { input_state: 'not_saved' }),
  state('failed', { input_state: 'not_saved', jd_effects: { state: 'settled', results: [committed] } }),
]) test('chat response validation retains the committed source-schema truth constraints', async () => {
  await assert.rejects(client(json(value)).api.chatStatus(DOC, RUN), invalid);
});

test('messages return exactly one scoped page and preserve original text', async () => {
  const value = page({ next_cursor: 'opaque-cursor.1' });
  const { api, calls } = client(json(value));
  assert.deepEqual(await api.chatMessages(DOC), value);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].init.method, 'GET');
  assert.equal(calls[0].init.body, undefined);
  assert.equal(new Headers(calls[0].init.headers).get('X-JD-Dataset'), DATASET);
  assert.equal(new URL(calls[0].url).pathname, `/api/documents/${DOC}/chat/messages`);
});

test('a continued page sends only its cursor and limit and requires the original anchor', async () => {
  const value = page({ messages: [message('assistant-id', 'assistant')] });
  const { api, calls } = client(json(value));
  assert.deepEqual(await api.chatMessages(DOC, { cursor: 'opaque-cursor.1', anchor: 'original-anchor', anchorRunId: RUN, limit: 10 }), value);
  const url = new URL(calls[0].url);
  assert.equal(url.searchParams.get('cursor'), 'opaque-cursor.1');
  assert.equal(url.searchParams.get('limit'), '10');
  assert.equal(url.searchParams.get('anchor'), null);
  assert.equal(calls.length, 1);
});

for (const overrides of [{ dataset_id: OTHER }, { document_id: OTHER }, { messages: [message(), message()] },
  { messages: [{ ...message(), role: 'tool' }] }, { messages: [{ ...message(), thinking: 'private' }] },
  { messages: Array.from({ length: 51 }, (_, index) => message(String(index), 'assistant')) },
  { messages: [], next_cursor: 'opaque-next' }])
  test('messages reject foreign, duplicate, private or impossible page framing', async () => {
    await assert.rejects(client(json(page(overrides))).api.chatMessages(DOC), invalid);
  });

for (const overrides of [{ anchor: 'changed-anchor' }, { anchor_run_id: OTHER }, { next_cursor: 'opaque-cursor.1' },
  { anchor: null, anchor_run_id: null, messages: [], next_cursor: null }, { messages: [] }])
  test('continued page never mixes anchors or accepts an empty/cycling suffix', async () => {
    await assert.rejects(client(json(page(overrides))).api.chatMessages(DOC,
      { cursor: 'opaque-cursor.1', anchor: 'original-anchor', anchorRunId: RUN }), invalid);
  });

test('empty first history is valid and does not invent a reply or issue another request', async () => {
  const value = page({ anchor: null, anchor_run_id: null, messages: [] });
  const { api, calls } = client(json(value));
  assert.deepEqual(await api.chatMessages(DOC), value);
  assert.equal(calls.length, 1);
});

test('invalid history options fail before HTTP and a suffix must include its anchor', async () => {
  const { api, calls } = client();
  for (const options of [{ cursor: 'c' }, { cursor: '', anchor: 'a' }, { cursor: 'c', anchor: '' },
    { cursor: 'c', anchor: 'a'.repeat(4097) }, { limit: 0 }, { limit: 51 }, { limit: true },
    { limit: 1.5 }, { limit: null }, { cursor: null, anchor: 'ignored' }, { cursor: null, unknown: true },
    { cursor: 'c', anchor: 'a' }, { cursor: 'c', anchor: 'a', anchorRunId: 'not-a-run' },
    { cursor: null, anchorRunId: RUN }])
    await assert.rejects(api.chatMessages(DOC, options as never));
  assert.equal(calls.length, 0);
});

test('a client dataset changed during an awaited response cannot publish the old scoped result', async () => {
  let release!: (response: Response) => void;
  const fetcher: typeof fetch = () => new Promise(resolve => { release = resolve; });
  const api = new JdApi(origin, fetcher); api.datasetId = DATASET;
  const pending = api.chatStatus(DOC, RUN);
  api.datasetId = OTHER;
  release(json(state()));
  await assert.rejects(pending, (error: unknown) => error instanceof ApiError && error.code === 'dataset_changed');
  assert.equal(api.datasetId, OTHER);
});

test('original UTF-8 boundary and unpaired surrogates are rejected without normalizing the input', () => {
  const exact = { ...request, text: '工'.repeat(43690) + 'ab' };
  assert.equal(new TextEncoder().encode(exact.text).length, 128 * 1024);
  validateChatRequest(exact);
  for (const text of [exact.text + 'c', '\ud800', '\udfff'])
    assert.throws(() => validateChatRequest({ ...request, text }), (error: unknown) =>
      error instanceof ApiError && error.code === 'invalid_input');
  assert.equal(exact.text, '工'.repeat(43690) + 'ab');
});

test('messages associate every Human with its original run and reject a run change without another Human', async () => {
  for (const messages of [
    [message('wrong-human-id')],
    [message(), message('reply', 'assistant', OTHER)],
    [message('first-reply', 'assistant'), message('next-reply', 'assistant', OTHER)],
  ]) await assert.rejects(client(json(page({ messages }))).api.chatMessages(DOC), invalid);
  const messages = [message(), message('first-reply', 'assistant'), message(OTHER, 'user', OTHER),
    message('next-reply', 'assistant', OTHER)];
  assert.deepEqual((await client(json(page({ messages, anchor_run_id: OTHER }))).api.chatMessages(DOC)).messages, messages);
});

test('a response cannot exceed the requested message count even when below the schema maximum', async () => {
  await assert.rejects(client(json(page({ messages: [message(), message('reply', 'assistant')] }))).api.chatMessages(DOC, { limit: 1 }), invalid);
});

// Compiled but never called: the options type prevents losing a suffix anchor.
function staticHistoryOptions(api: JdApi) {
  void api.chatMessages(DOC);
  void api.chatMessages(DOC, { cursor: null, limit: 50 });
  void api.chatMessages(DOC, { cursor: 'cursor', anchor: 'anchor', anchorRunId: RUN, limit: 10 });
  // @ts-expect-error A continued page always carries its original anchor.
  void api.chatMessages(DOC, { cursor: 'cursor' });
  // @ts-expect-error An initial page cannot carry a silently ignored anchor.
  void api.chatMessages(DOC, { cursor: null, anchor: 'anchor' });
  // @ts-expect-error A continued page retains the run at its original anchor.
  void api.chatMessages(DOC, { cursor: 'cursor', anchor: 'anchor' });
}
void staticHistoryOptions;

test('initial history exposes the anchored latest run while an older page may belong to earlier runs', async () => {
  const latest = page({ anchor_run_id: OTHER, messages: [message(), message(OTHER, 'user', OTHER)], next_cursor: 'older' });
  const older = page({ anchor_run_id: OTHER, messages: [message('old-reply', 'assistant')] });
  const { api } = client(json(latest), json(older));
  assert.equal((await api.chatMessages(DOC)).anchor_run_id, OTHER);
  assert.deepEqual(await api.chatMessages(DOC, { cursor: 'older', anchor: 'original-anchor', anchorRunId: OTHER }), older);
});

test('initial latest page cannot claim a different anchor run or omit its identity', async () => {
  for (const value of [page({ anchor_run_id: OTHER }), page({ anchor_run_id: null }),
    page({ anchor: null, anchor_run_id: RUN, messages: [] })])
    await assert.rejects(client(json(value)).api.chatMessages(DOC), invalid);
  const missing = page() as Record<string, unknown>;
  delete missing.anchor_run_id;
  await assert.rejects(client(json(missing)).api.chatMessages(DOC), invalid);
});
