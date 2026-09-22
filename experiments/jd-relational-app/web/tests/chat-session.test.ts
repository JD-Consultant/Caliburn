import assert from 'node:assert/strict';
import { test } from 'node:test';
import { ChatController } from '../src/lib/chat-session.ts';
import type { ChatPort, ChatApi } from '../src/lib/chat-session.ts';
import { ApiError } from '../src/lib/api.ts';
import type { ChatSubmission } from '../src/lib/drafts.ts';
import type { ChatHistoryPage, ChatRunState, ChatMessage } from '../../src/jd_relational/generated/jd-chat-http.ts';

const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const DOC = id(1), DATASET = id(2), RUN = id(3), OLD = id(4);
const original: ChatSubmission = { request: { run_id: RUN, text: '原話\r\n  整理工作😀', expected_jd_revision_ref: 'original-revision' },
  submissionGeneration: 7, coveredSeq: 4 };
const user = (run = RUN): ChatMessage => ({ message_id: run, run_id: run, role: 'user', text: '原話' });
const reply = (run = RUN): ChatMessage => ({ message_id: `reply-${run}`, run_id: run, role: 'assistant', text: '回覆' });
function state(status = 'running', run = RUN): ChatRunState {
  const pending = ['running', 'closing', 'recovery_required'].includes(status);
  return { dataset_id: DATASET, document_id: DOC, run_id: run, run_status: status,
    input_state: status === 'not_found' ? 'unconfirmed' : 'saved', response_message_id: status === 'completed' ? reply(run).message_id : null,
    stop_requested: status === 'running' ? false : null, jd_effects: { state: pending || status === 'not_found' ? 'unconfirmed' : 'settled', results: [] },
    write_state: { ready: true, archived: false, write_blocked: pending, running: false, operation_id: null, error: null } } as ChatRunState;
}
function page(messages: ChatMessage[] = [user(), reply()], anchor = 'anchor', run = RUN, cursor: string | null = null): ChatHistoryPage {
  return { dataset_id: DATASET, document_id: DOC, anchor, anchor_run_id: run, messages, next_cursor: cursor };
}
function deferred<T>() { let resolve!: (value: T) => void, reject!: (error: unknown) => void;
  const promise = new Promise<T>((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; }
async function microtasks() { for (let i = 0; i < 30; i++) await Promise.resolve(); }
function fixture(pending: ChatSubmission | null = null) {
  const calls: { method: string; input: unknown }[] = [], observed: ChatRunState[] = [];
  let currentOriginal = pending, finished = 0, unavailable = 0, restored = 0;
  let latest: ChatHistoryPage = page();
  const answers: Record<string, () => Promise<unknown>> = {};
  async function call(method: string, input: unknown, fallback: unknown) {
    calls.push({ method, input: structuredClone(input) }); return answers[method] ? answers[method]() : fallback;
  }
  const api = {
    datasetId: DATASET,
    chatMessages: (_doc: string, options?: unknown) => call('history', options ?? {}, latest),
    chatStatus: (_doc: string, run: string) => call('status', run, state('completed', run)),
    chatStart: (_doc: string, body: unknown) => call('post', body, state()),
    chatCancel: (_doc: string, run: string) => call('cancel', run, state('running', run)),
    chatRecover: (_doc: string, run: string) => call('recover', run, state('cancelled', run)),
  } as ChatApi;
  const port: ChatPort = {
    async chatPrepare() { currentOriginal = structuredClone(original); return currentOriginal; },
    chatOriginal() { return currentOriginal; },
    async chatObserve(value) { observed.push(structuredClone(value)); },
    async chatUnavailable(value) { assert.deepEqual(value, original); unavailable++; currentOriginal = null; },
    chatRequestFinished() { finished++; },
    async chatRestore(value) { assert.equal(value.input_state, 'not_saved'); restored++; currentOriginal = null; },
  };
  const controller = new ChatController(api, DOC, port, () => {});
  return { api, port, controller, calls, answers, observed, setOriginal: (v: ChatSubmission | null) => { currentOriginal = v; },
    setPage: (v: ChatHistoryPage) => { latest = v; }, counts: () => ({ finished, unavailable, restored }) };
}

test('startup reads one latest page and looks up the durable pending run before the anchor run', async t => {
  const f = fixture(original); t.after(() => f.controller.dispose());
  f.setPage(page([user(OLD)], 'other-anchor', OLD));
  await f.controller.start();
  assert.deepEqual(f.calls.map(c => c.method), ['history', 'status', 'history']);
  assert.equal(f.calls[1].input, RUN);
  assert.equal(f.controller.snapshot().run?.run_id, RUN);
  assert.equal(f.observed.length, 1);
});

test('an unrecorded local run is not invented from the first visible message', async t => {
  const f = fixture(); t.after(() => f.controller.dispose());
  f.setPage(page([reply(OLD), user()], 'latest-anchor', RUN));
  await f.controller.start();
  assert.equal(f.calls.find(c => c.method === 'status')?.input, RUN);
  assert.equal(f.calls.filter(c => c.method === 'post').length, 0);
});

test('empty history does not create, query or invent a run', async t => {
  const f = fixture(); t.after(() => f.controller.dispose());
  f.setPage({ dataset_id: DATASET, document_id: DOC, anchor: null, anchor_run_id: null, messages: [], next_cursor: null });
  await f.controller.start();
  assert.deepEqual(f.calls.map(c => c.method), ['history']);
  assert.equal(f.controller.snapshot().run, null);
});

test('explicit refresh recovers an initial history failure with no local pending run', async t => {
  const f = fixture(); t.after(() => f.controller.dispose());
  f.answers.history = async () => { throw new ApiError('response_unknown'); };
  await f.controller.start();
  assert.equal(f.controller.snapshot().error?.code, 'response_unknown');
  delete f.answers.history;
  await f.controller.refresh();
  assert.deepEqual(f.calls.map(c => c.method), ['history', 'history', 'status']);
  assert.equal(f.controller.snapshot().run?.run_id, RUN);
  assert.deepEqual(f.controller.snapshot().messages, [user(), reply()]);
  assert.equal(f.controller.snapshot().error, null);
});

test('one transient active-run status 503 is re-read without replaying the run', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const f = fixture(); t.after(() => f.controller.dispose());
  await f.controller.send();
  let reads = 0;
  f.answers.status = async () => {
    if (++reads === 1) throw new ApiError('service_unavailable');
    return state('completed');
  };
  t.mock.timers.tick(2000); await microtasks();
  assert.equal(reads, 1);
  assert.equal(f.controller.snapshot().error?.code, 'service_unavailable');
  t.mock.timers.tick(2000); await microtasks();
  assert.equal(reads, 2);
  assert.equal(f.controller.snapshot().run?.run_status, 'completed');
  assert.equal(f.controller.snapshot().error, null);
  assert.equal(f.calls.filter(call => call.method === 'post').length, 1);
});

test('repeated active-run status 503 stops after one extra read', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const f = fixture(); t.after(() => f.controller.dispose());
  await f.controller.send();
  f.answers.status = async () => { throw new ApiError('service_unavailable'); };
  t.mock.timers.tick(2000); await microtasks();
  t.mock.timers.tick(2000); await microtasks();
  t.mock.timers.tick(4000); await microtasks();
  assert.equal(f.calls.filter(call => call.method === 'status').length, 2);
  assert.equal(f.controller.snapshot().error?.code, 'service_unavailable');
  assert.equal(f.calls.filter(call => call.method === 'post').length, 1);
});

test('explicit refresh discovers a later run and replaces the old terminal window', async t => {
  const f = fixture(); t.after(() => f.controller.dispose());
  f.setPage(page([user(OLD), reply(OLD)], 'old-anchor', OLD));
  await f.controller.start();
  assert.equal(f.controller.snapshot().run?.run_id, OLD);
  f.setPage(page([user(), reply()], 'new-anchor', RUN, 'new-older-cursor'));
  await f.controller.refresh();
  assert.deepEqual(f.calls.filter(c => c.method === 'status').map(c => c.input), [OLD, RUN]);
  assert.deepEqual(f.controller.snapshot().messages, [user(), reply()]);
  assert.equal(f.controller.snapshot().page?.anchor, 'new-anchor');
  assert.equal(f.controller.snapshot().page?.next_cursor, 'new-older-cursor');
});

test('a new anchor whose status lookup fails cannot display the old run as its result', async t => {
  const f = fixture(); t.after(() => f.controller.dispose());
  f.setPage(page([user(OLD), reply(OLD)], 'old-anchor', OLD)); await f.controller.start();
  f.setPage(page([user()], 'new-anchor'));
  f.answers.status = async () => { throw new ApiError('response_unknown'); };
  await f.controller.refresh();
  assert.equal(f.controller.snapshot().runId, RUN);
  assert.equal(f.controller.snapshot().run, null);
  assert.equal(f.controller.snapshot().error?.code, 'response_unknown');
});

test('explicit refresh still prefers the original pending run over a new page anchor', async t => {
  const f = fixture(original); t.after(() => f.controller.dispose());
  f.setPage(page([user(OLD), reply(OLD)], 'new-anchor', OLD));
  await f.controller.refresh();
  assert.equal(f.calls[0].method, 'history');
  assert.equal(f.calls.find(c => c.method === 'status')?.input, RUN);
  assert.equal(f.calls.some(c => c.method === 'post'), false);
});

test('prepare and exact original POST share one flight; its completion releases the handoff', async t => {
  const f = fixture(); t.after(() => f.controller.dispose());
  const flight = deferred<ChatRunState>(); f.answers.post = () => flight.promise;
  const sending = f.controller.send(); await microtasks();
  await f.controller.send(); await f.controller.refresh(); await f.controller.cancel();
  assert.equal(f.controller.snapshot().busy, true);
  assert.deepEqual(f.calls, [{ method: 'post', input: original.request }]);
  flight.resolve(state('completed')); await sending;
  assert.equal(f.counts().finished, 1);
  assert.equal(f.observed[0].run_status, 'completed');
  assert.equal(f.controller.snapshot().busy, false);
});

test('unknown start retains original input, never cancels/replays, and exposes only fixed error', async t => {
  const f = fixture(); t.after(() => f.controller.dispose());
  f.answers.post = async () => { throw new Error('private-marker'); };
  await f.controller.send();
  assert.deepEqual(f.port.chatOriginal(), original);
  assert.equal(f.controller.snapshot().canRetry, true);
  assert.ok(!f.controller.snapshot().error?.message.includes('private-marker'));
  assert.equal(f.calls.length, 1); assert.equal(f.counts().finished, 1);
});

test('new original B clears completed A before POST and keeps B unknown after reply loss', async t => {
  const f = fixture(); t.after(() => f.controller.dispose());
  f.setPage(page([user(OLD), reply(OLD)], 'anchor-A', OLD)); await f.controller.start();
  const flight = deferred<ChatRunState>(); f.answers.post = () => flight.promise;
  const sending = f.controller.send(); await microtasks();
  try {
    assert.equal(f.controller.snapshot().runId, RUN);
    assert.equal(f.controller.snapshot().run, null);
  } finally { flight.reject(new ApiError('response_unknown')); await sending; }
  assert.equal(f.controller.snapshot().run, null);
  assert.equal(f.controller.snapshot().runId, RUN);
  assert.equal(f.controller.snapshot().error?.code, 'response_unknown');
  assert.deepEqual(f.port.chatOriginal(), original);
});

test('retrying a different durable original clears old terminal status even when GET fails', async t => {
  const f = fixture(); t.after(() => f.controller.dispose());
  f.setPage(page([user(OLD), reply(OLD)], 'anchor-A', OLD)); await f.controller.start();
  f.setOriginal(structuredClone(original));
  f.answers.status = async () => { throw new ApiError('response_unknown'); };
  await f.controller.retry();
  assert.equal(f.controller.snapshot().runId, RUN); assert.equal(f.controller.snapshot().run, null);
  assert.equal(f.calls.some(c => c.method === 'post'), false);
});

for (const method of ['cancel', 'recover'] as const) test(`${method} binds the selected original target before its reply`, async t => {
  const f = fixture(); t.after(() => f.controller.dispose());
  f.setPage(page([user(OLD), reply(OLD)], 'anchor-A', OLD)); await f.controller.start();
  f.setOriginal(structuredClone(original));
  f.answers[method] = async () => { throw new ApiError('response_unknown'); };
  await f.controller[method]();
  assert.equal(f.calls.at(-1)?.input, RUN);
  assert.equal(f.controller.snapshot().runId, RUN); assert.equal(f.controller.snapshot().run, null);
  assert.equal(f.calls.some(c => c.method === 'post'), false);
});

test('only the original start ai_unavailable restores the original draft', async t => {
  const f = fixture(original); t.after(() => f.controller.dispose());
  f.answers.status = async () => { throw new ApiError('ai_unavailable', '尚未啟用'); };
  await f.controller.refresh(); assert.equal(f.counts().unavailable, 0);
  f.answers.post = f.answers.status;
  await f.controller.send(); assert.equal(f.counts().unavailable, 1);
  assert.equal(f.controller.snapshot().error?.code, 'ai_unavailable');
});

test('ai_unavailable from a later observer/history read is not an original POST rejection', async t => {
  const f = fixture(); t.after(() => f.controller.dispose());
  f.port.chatObserve = async () => { throw new ApiError('ai_unavailable', '後續讀取未完成'); };
  await f.controller.send();
  assert.equal(f.counts().unavailable, 0);
  assert.deepEqual(f.port.chatOriginal(), original);
  assert.equal(f.controller.snapshot().run?.run_status, 'running');
});

test('retry first GETs; only not_found posts the unchanged original body', async t => {
  const f = fixture(original); t.after(() => f.controller.dispose());
  f.answers.status = async () => state('not_found');
  f.answers.post = async () => state('completed');
  await f.controller.retry();
  assert.deepEqual(f.calls.slice(0, 2), [{ method: 'status', input: RUN }, { method: 'post', input: original.request }]);
  assert.equal(f.counts().finished, 1);
});

test('retry recovery_required uses recover and never resubmits the model input', async t => {
  const f = fixture(original); t.after(() => f.controller.dispose());
  f.answers.status = async () => state('recovery_required');
  await f.controller.retry();
  assert.deepEqual(f.calls.filter(c => c.method !== 'history').map(c => c.method), ['status', 'recover']);
  assert.equal(f.controller.snapshot().run?.run_status, 'cancelled');
});

test('retry observed committed/failed state never submits again or conflates its JD effects', async t => {
  const f = fixture(original); t.after(() => f.controller.dispose());
  const value = { ...state('failed'), jd_effects: { state: 'settled', results: [{ status: 'committed', effect: 'changed', receipt_durability: 'confirmed',
    operation_ref: 'operation', result_revision_ref: 'revision', change_ref: 'change', error: null, next_action: 'continue' }] } } as ChatRunState;
  f.answers.status = async () => value;
  await f.controller.retry();
  assert.equal(f.calls.some(c => c.method === 'post'), false);
  assert.deepEqual(f.controller.snapshot().run, value);
});

test('a changed original during lookup is not sent under the previous captured request', async t => {
  const f = fixture(original); t.after(() => f.controller.dispose());
  f.answers.status = async () => { f.setOriginal({ ...original, request: { ...original.request, text: '另一段' } }); return state('not_found'); };
  await f.controller.retry();
  assert.equal(f.calls.some(c => c.method === 'post'), false);
  assert.equal(f.controller.snapshot().error?.code, 'request_changed');
});

test('older pages prepend one fixed scope and anchor; refresh replaces rather than merges anchors', async t => {
  const f = fixture(); t.after(() => f.controller.dispose());
  f.setPage(page([user(), reply()], 'anchor-A', RUN, 'older-1'));
  await f.controller.start();
  f.setPage(page([user(OLD), reply(OLD)], 'anchor-A', RUN));
  await f.controller.more();
  assert.deepEqual(f.controller.snapshot().messages.map(m => m.message_id), [OLD, reply(OLD).message_id, RUN, reply().message_id]);
  assert.deepEqual(f.controller.snapshot().page?.messages, [user(OLD), reply(OLD)]);
  assert.deepEqual(f.calls.at(-1)?.input, { cursor: 'older-1', anchor: 'anchor-A', anchorRunId: RUN });
  f.setPage(page([user()], 'anchor-B'));
  await f.controller.start();
  assert.equal(f.controller.snapshot().page?.anchor, 'anchor-B');
  assert.ok(!f.controller.snapshot().messages.some(m => m.run_id === OLD));
});

for (const bad of [page([user(OLD)], 'wrong-anchor'), page([user()], 'anchor'),
  { ...page([user(OLD)]), document_id: OLD }, { ...page([user(OLD)]), dataset_id: OLD }])
  test('older pages reject mixed anchors/scopes/duplicate IDs without corrupting visible history', async t => {
    const f = fixture(); t.after(() => f.controller.dispose()); f.setPage(page([user(), reply()], 'anchor', RUN, 'older'));
    await f.controller.start(); const before = f.controller.snapshot().messages;
    f.setPage(bad); await f.controller.more();
    assert.deepEqual(f.controller.snapshot().messages, before);
    assert.equal(f.controller.snapshot().error?.code, 'invalid_response');
  });

test('dispose ignores late status and history, does not observe or cancel the server, and releases request handoff', async () => {
  const f = fixture(); const flight = deferred<ChatRunState>(); f.answers.post = () => flight.promise;
  const sending = f.controller.send(); await microtasks(); f.controller.dispose();
  flight.resolve(state('completed')); await sending;
  assert.equal(f.observed.length, 0); assert.equal(f.calls.length, 1); assert.equal(f.counts().finished, 1);
});

test('a changed dataset while a flight awaits cannot publish or acknowledge old data', async t => {
  const f = fixture(original); t.after(() => f.controller.dispose());
  const flight = deferred<ChatRunState>(); f.answers.status = () => flight.promise;
  const reading = f.controller.refresh(); await microtasks(); f.api.datasetId = OLD;
  flight.resolve(state('completed')); await reading;
  assert.equal(f.observed.length, 0); assert.equal(f.controller.snapshot().error?.code, 'dataset_changed');
});

test('polling is single-flight every two seconds; closing continues, first error stops, dispose never cancels', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const f = fixture(original); t.after(() => f.controller.dispose());
  f.answers.status = async () => state('closing');
  await f.controller.refresh();
  t.mock.timers.tick(1999); await microtasks(); assert.equal(f.calls.filter(c => c.method === 'status').length, 1);
  const flight = deferred<ChatRunState>(); f.answers.status = () => flight.promise;
  t.mock.timers.tick(1); await microtasks();
  t.mock.timers.tick(10000); await microtasks(); assert.equal(f.calls.filter(c => c.method === 'status').length, 2);
  assert.equal(f.calls.filter(c => c.method === 'history').length, 1);
  flight.reject(new ApiError('response_unknown')); await microtasks();
  t.mock.timers.tick(10000); await microtasks(); assert.equal(f.calls.filter(c => c.method === 'status').length, 2);
  assert.equal(f.calls.some(c => c.method === 'cancel'), false);
});

test('poll keeps expanded history until a newly saved reply needs its new latest window', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const f = fixture(original); t.after(() => f.controller.dispose());
  f.setPage(page([user()], 'old-anchor', RUN, 'older'));
  f.answers.status = async () => state('closing');
  await f.controller.start();
  f.setPage(page([user(OLD), reply(OLD)], 'old-anchor'));
  await f.controller.more();
  t.mock.timers.tick(2000); await microtasks();
  assert.equal(f.calls.filter(c => c.method === 'history').length, 2);
  assert.deepEqual(f.controller.snapshot().messages, [user(OLD), reply(OLD), user()]);
  f.setPage(page([user(), reply()], 'reply-anchor'));
  f.answers.status = async () => state('completed');
  t.mock.timers.tick(2000); await microtasks();
  assert.equal(f.calls.filter(c => c.method === 'history').length, 3);
  assert.deepEqual(f.controller.snapshot().messages, [user(), reply()]);
  assert.equal(f.controller.snapshot().page?.anchor, 'reply-anchor');
  assert.equal(f.controller.snapshot().run?.run_status, 'completed');
});

test('dispose during explicit latest refresh cannot start a late run lookup', async () => {
  const f = fixture(); const history = deferred<ChatHistoryPage>(); f.answers.history = () => history.promise;
  const reading = f.controller.refresh(); await microtasks(); f.controller.dispose();
  history.resolve(page()); await reading;
  assert.deepEqual(f.calls.map(c => c.method), ['history']);
  assert.equal(f.observed.length, 0);
  assert.equal(f.controller.snapshot().page, null);
});

test('confirmed not_saved can explicitly restore; ordinary failure cannot', async t => {
  const f = fixture(original); t.after(() => f.controller.dispose());
  f.answers.status = async () => state('failed'); await f.controller.refresh(); await f.controller.restore();
  assert.equal(f.counts().restored, 0);
  f.answers.status = async () => ({ ...state('failed'), input_state: 'not_saved' });
  await f.controller.refresh(); await f.controller.restore(); assert.equal(f.counts().restored, 1);
});

for (const status of ['not_found', 'recovery_required']) test(`${status} stops automatic status observation without a POST`, async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const f = fixture(original); t.after(() => f.controller.dispose());
  f.answers.status = async () => state(status);
  await f.controller.refresh(); t.mock.timers.tick(20000); await microtasks();
  assert.deepEqual(f.calls.filter(c => c.method !== 'history').map(c => c.method), ['status']);
});

test('failed prepare releases the local handoff and never calls HTTP', async t => {
  const f = fixture(); t.after(() => f.controller.dispose());
  f.port.chatPrepare = async () => { throw new Error('private-save-detail'); };
  await f.controller.send();
  assert.equal(f.calls.length, 0); assert.equal(f.counts().finished, 1);
  assert.ok(!f.controller.snapshot().error?.message.includes('private-save-detail'));
});
