import assert from 'node:assert/strict';
import test from 'node:test';
import { ChatController } from '../src/lib/chat-session.ts';
import type { ChatApi, ChatPort } from '../src/lib/chat-session.ts';
import { ApiError } from '../src/lib/api.ts';
import type { ChatHistoryPage, ChatMessage, ChatRunState } from '../../src/jd_relational/generated/jd-chat-http.ts';

const uuid = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const DATASET = uuid(1), DOC = uuid(2), A = uuid(3), B = uuid(4);
const user = (run: string): ChatMessage => ({ message_id: run, run_id: run, role: 'user', text: '原話' });
const reply = (run: string): ChatMessage => ({ message_id: `reply-${run}`, run_id: run, role: 'assistant', text: '公開回覆' });
const page = (run: string, anchor: string, messages = [user(run), reply(run)], next_cursor: string | null = null): ChatHistoryPage =>
  ({ dataset_id: DATASET, document_id: DOC, anchor, anchor_run_id: run, messages, next_cursor });
function state(run: string, running = false): ChatRunState {
  return { dataset_id: DATASET, document_id: DOC, run_id: run, run_status: running ? 'running' : 'completed',
    input_state: 'saved', response_message_id: running ? null : reply(run).message_id, stop_requested: running ? false : null,
    write_state: { ready: true, archived: false, write_blocked: running, running, operation_id: null, error: null },
    jd_effects: { state: running ? 'unconfirmed' : 'settled', results: [] } } as ChatRunState;
}
function fixture() {
  let current = page(A, 'anchor-A'), failHistory = false, running = false;
  const calls: { method: string; run?: string }[] = [];
  const api: ChatApi = {
    datasetId: DATASET,
    chatMessages: async () => { calls.push({ method: 'history' }); if (failHistory) { failHistory = false; throw new ApiError('response_unknown'); } return current; },
    chatStatus: async (_doc, run) => { calls.push({ method: 'status', run }); return state(run, running); },
    chatStart: async () => { throw new Error('unexpected POST'); },
    chatCancel: async () => { throw new Error('unexpected cancel'); },
    chatRecover: async () => { throw new Error('unexpected recover'); },
  };
  const port: ChatPort = {
    chatPrepare: async () => { throw new Error('unexpected prepare'); }, chatOriginal: () => null,
    chatObserve: async () => {}, chatUnavailable: async () => { throw new Error('unexpected restore'); },
    chatRequestFinished: () => {}, chatRestore: async () => { throw new Error('unexpected restore'); },
  };
  const controller = new ChatController(api, DOC, port, () => {});
  return { controller, calls, setPage: (value: ChatHistoryPage) => { current = value; },
    failHistory: () => { failHistory = true; }, setRunning: (value: boolean) => { running = value; } };
}

test('review: explicit refresh recovers an initial history failure instead of clearing error with no read', async t => {
  const f = fixture(); t.after(() => f.controller.dispose());
  f.failHistory(); await f.controller.start();
  assert.equal(f.controller.snapshot().error?.code, 'response_unknown'); assert.equal(f.controller.snapshot().page, null);
  await f.controller.refresh();
  assert.equal(f.calls.filter(value => value.method === 'history').length, 2);
  assert.equal(f.controller.snapshot().page?.anchor, 'anchor-A');
  assert.equal(f.controller.snapshot().run?.run_id, A);
});

test('review: explicit refresh rediscovers the current native anchor rather than permanently pinning prior terminal A', async t => {
  const f = fixture(); t.after(() => f.controller.dispose());
  await f.controller.start(); assert.equal(f.controller.snapshot().run?.run_id, A);
  f.setPage(page(B, 'anchor-B'));
  await f.controller.refresh();
  assert.equal(f.controller.snapshot().page?.anchor, 'anchor-B');
  assert.equal(f.controller.snapshot().run?.run_id, B);
  assert.ok(f.calls.some(value => value.method === 'status' && value.run === B));
});

test('review: a new complete reply replaces loaded older windows without mixing signed anchors', async t => {
  const f = fixture(); t.after(() => f.controller.dispose());
  f.setRunning(true); f.setPage(page(B, 'before-reply', [user(B)], 'older'));
  await f.controller.start();
  f.setPage(page(B, 'before-reply', [user(A), reply(A)])); await f.controller.more();
  assert.deepEqual(f.controller.snapshot().messages.map(value => value.message_id), [A, reply(A).message_id, B]);
  f.setRunning(false); f.setPage(page(B, 'after-reply'));
  await f.controller.refresh();
  assert.equal(f.controller.snapshot().page?.anchor, 'after-reply');
  assert.deepEqual(f.controller.snapshot().messages, [user(B), reply(B)]);
});
