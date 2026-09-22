import assert from 'node:assert/strict';
import test from 'node:test';
import { JdSession } from '../src/lib/session.ts';
import type { SessionSnapshot } from '../src/lib/session.ts';
import { ApiError } from '../src/lib/api.ts';
import type { JdApi } from '../src/lib/api.ts';
import { acknowledgeSubmissionRecord, claimDraftRecord, draftHandle, fieldKey, persistFieldRecord,
  persistFormRecord, prepareSubmissionRecord, rebindFieldRecord, persistChatRecord, prepareChatRecord,
  acknowledgeChatRecord, restoreChatRecord, rejectUnavailableChatRecord } from '../src/lib/drafts.ts';
import type { DraftHandle, DraftRow, DraftScope, DraftStore, FieldDraft, FormDraft, PrepareSubmission,
  RebindField, SubmissionAcknowledgment, ChatDraft, PrepareChat, ChatAcknowledgment } from '../src/lib/drafts.ts';
import type { ChatRunState } from '../../src/jd_relational/generated/jd-chat-http.ts';
import type { ReadInput, ReadPage, ReadRecord } from '../../src/jd_relational/generated/jd-read.ts';
import type { ManualDocumentState, ManualSaveInput } from '../../src/jd_relational/generated/jd-manual-http.ts';
import type { MutationResult } from '../../src/jd_relational/generated/jd-result.ts';

const uuid = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const scope = { apiOrigin: 'http://127.0.0.1:9000', datasetId: uuid(1), documentId: uuid(2) };
const key = fieldKey(null, 'job_title');
const writable: ManualDocumentState = { ready: true, archived: false, write_blocked: false, running: false, operation_id: null, error: null };
function page(revision = 0, value = '原內容'): ReadPage {
  const records: ReadRecord[] = [
    ...(['profile', 'purpose', 'duties_tasks', 'knowledge', 'skills', 'conditions'] as const).map(section_key => ({ type: 'section' as const, section_ref: `${revision}:${section_key}`, section_key, title: section_key })),
    { type: 'field', field_ref: `${revision}:field`, section_ref: `${revision}:profile`, item_ref: null, name: 'job_title', value },
    { type: 'field', field_ref: `${revision}:purpose-field`, section_ref: `${revision}:purpose`, item_ref: null, name: 'purpose', value: '另一欄原內容' },
  ];
  return { format_version: 2, view: 'current', access: 'current', revision_ref: `${revision}:revision`, records,
    start_index: 0, total_records: records.length, has_more: false, next_cursor: null, oversized_unit: false };
}
function deferred<T>() {
  let resolve!: (value: T) => void; let reject!: (error: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
async function until(check: () => boolean, reason = 'expected state'): Promise<void> {
  for (let n = 0; n < 50; n++) { if (check()) return; await new Promise<void>(resolve => setImmediate(resolve)); }
  assert.ok(check(), reason);
}

// A pure record test double, explicitly not evidence of native IndexedDB transactions.
class RecordStore {
  row: DraftRow | null = null; failField = false; failForm = false; closed = 0;
  fieldCalls = 0; failFieldCalls = new Set<number>();
  gate: ReturnType<typeof deferred<void>> | null = null;
  close() { this.closed++; }
  async claim(value: DraftScope, owner: string) { return this.row = claimDraftRecord(this.row, value, owner, uuid(9)); }
  async read() { return this.row; }
  async persistField(handle: DraftHandle, field: FieldDraft) {
    this.fieldCalls++;
    if (this.gate) await this.gate.promise;
    if (this.failField || this.failFieldCalls.has(this.fieldCalls)) { this.failField = false; throw new Error('simulated IDB failure'); }
    return this.row = persistFieldRecord(this.row!, handle, field);
  }
  async persistForm(handle: DraftHandle, form: FormDraft) {
    if (this.failForm) { this.failForm = false; throw new Error('simulated IDB failure'); }
    return this.row = persistFormRecord(this.row!, handle, form);
  }
  async persistChat(handle: DraftHandle, input: ChatDraft) {
    if (this.gate) await this.gate.promise;
    return this.row = persistChatRecord(this.row!, handle, input);
  }
  async prepareChat(handle: DraftHandle, input: PrepareChat) { return this.row = prepareChatRecord(this.row!, handle, input); }
  async acknowledgeChat(handle: DraftHandle, input: ChatAcknowledgment) { return this.row = acknowledgeChatRecord(this.row!, handle, input); }
  async restoreChat(handle: DraftHandle, input: ChatAcknowledgment) { return this.row = restoreChatRecord(this.row!, handle, input); }
  async rejectUnavailableChat(handle: DraftHandle, input: { runId: string; submissionGeneration: number }) {
    return this.row = rejectUnavailableChatRecord(this.row!, handle, input);
  }
  async prepareSubmission(handle: DraftHandle, input: PrepareSubmission) { return this.row = prepareSubmissionRecord(this.row!, handle, input); }
  async acknowledgeSubmission(handle: DraftHandle, input: SubmissionAcknowledgment) { return this.row = acknowledgeSubmissionRecord(this.row!, handle, input); }
  async rebindField(handle: DraftHandle, input: RebindField) { return this.row = rebindFieldRecord(this.row!, handle, input); }
  async discardField(_handle: DraftHandle, field: string, seq: number) {
    assert.equal(this.row!.fields[field].seq, seq); assert.equal(this.row!.submission, null);
    const next = structuredClone(this.row!); delete next.fields[field]; next.generation++; return this.row = next;
  }
  async discardForm(_handle: DraftHandle, name: string, seq: number) {
    assert.equal(this.row!.forms[name].seq, seq); assert.equal(this.row!.submission, null);
    const next = structuredClone(this.row!); delete next.forms[name]; next.generation++; return this.row = next;
  }
}
async function setup(existing?: DraftRow) {
  const store = new RecordStore(); store.row = existing ?? null;
  const snapshots: SessionSnapshot[] = []; const saves: ManualSaveInput[] = [];
  const replies: ReturnType<typeof deferred<MutationResult>>[] = [];
  let current = page(), state = writable, held = false;
  const history = new Map<string, ReadPage>([['0:observation', structuredClone(current)], [current.revision_ref, structuredClone(current)]]);
  const api = { origin: scope.apiOrigin, datasetId: scope.datasetId,
    read: async (_id?: string, input?: ReadInput): Promise<ReadPage> => {
      if (input?.view === 'history' && input.target_ref) {
        const saved = history.get(input.target_ref); assert.ok(saved, 'must resolve the exact immutable target');
        return { ...structuredClone(saved), view: 'history', access: 'history' };
      }
      return structuredClone(current);
    }, state: async () => structuredClone(state),
    save: async (_id: string, request: ManualSaveInput) => {
      saves.push(structuredClone(request)); const reply = deferred<MutationResult>(); replies.push(reply); return reply.promise;
    },
    operation: async (_id: string, operationId: string) => ({ operation_id: operationId, presence: 'not_found', result: null, write_state: state }),
  };
  const requestLock = (async (_name: string, _options: unknown, callback: (lock: Lock | null) => Promise<unknown>) => {
    assert.equal(held, false); held = true;
    try { return await callback({ name: 'test-held-lock', mode: 'exclusive' } as Lock); } finally { held = false; }
  }) as LockManager['request'];
  const session = new JdSession(api as unknown as JdApi, scope.documentId, snapshot => snapshots.push(snapshot), {
    openStore: async () => store as unknown as DraftStore, locks: { request: requestLock },
  });
  await session.start(); await until(() => snapshots.at(-1)?.loading === false, 'session became ready');
  return { session, store, saves, replies, snapshots, api,
    get last() { return snapshots.at(-1)!; }, get held() { return held; },
    commit(index: number, value: string, nextState = writable) {
      current = page(index + 1, value); state = nextState;
      history.set(`${index + 1}:observation`, structuredClone(current)); history.set(current.revision_ref, structuredClone(current));
      replies[index].resolve({ status: 'committed', effect: 'changed', receipt_durability: 'confirmed', operation_ref: `op:${index}`, result_revision_ref: `${index + 1}:observation`, change_ref: `change:${index}`, error: null, next_action: 'continue' });
    },
    async stop() {
      for (const reply of replies) reply.reject(new ApiError('response_unknown'));
      store.gate?.resolve(); await session.dispose(); await until(() => !held, 'lock drained before release');
    },
  };
}

test('A response preserves later B and sends B against the confirmed new field ref', async () => {
  const h = await setup();
  try {
    const field = h.last.view!.fields[0]; h.session.edit(field, 'A');
    const flush = h.session.flush(); await until(() => h.saves.length === 1);
    h.session.edit(field, 'B'); await until(() => h.store.row?.fields[key]?.text === 'B');
    h.commit(0, 'A'); await until(() => h.saves.length === 2);
    assert.equal(h.saves[0].command.tool, 'jd_set_text');
    assert.equal(h.saves[1].base_revision_ref, '1:revision');
    assert.deepEqual(h.saves[1].command, { tool: 'jd_set_text', arguments: { target_field_ref: '1:field', text: 'B', basis_refs: [] } });
    assert.equal(h.last.values[key], 'B'); h.commit(1, 'B'); await flush;
    assert.equal(h.last.dirty, false); assert.equal(h.last.view!.fields[0].value, 'B');
  } finally { await h.stop(); }
});

function terminalChat(runId: string): ChatRunState {
  return { dataset_id: scope.datasetId, document_id: scope.documentId, run_id: runId,
    run_status: 'completed', input_state: 'saved', response_message_id: 'reply', stop_requested: null,
    write_state: writable, jd_effects: { state: 'settled', results: [] } };
}
test('chat handoff waits for real manual save and binds the new saved revision', async () => {
  const h = await setup();
  try {
    h.session.edit(h.last.view!.fields[0], '先手動更正'); h.session.chatEdit('原話\n下一行');
    const preparing = h.session.chatPrepare(); await until(() => h.saves.length === 1);
    assert.equal(h.session.chatOriginal(), null); assert.equal(h.last.readOnly, true);
    h.session.edit(h.last.view!.fields[0], '不應插入'); h.session.chatEdit('不應蓋掉交接中的原話');
    h.commit(0, '先手動更正'); const original = await preparing;
    assert.equal(original.request.expected_jd_revision_ref, '1:revision');
    assert.equal(original.request.text, '原話\n下一行'); assert.equal(h.saves.length, 1);
    assert.deepEqual(h.store.row?.chatSubmission, original); assert.equal(h.last.chatText, '');
    h.session.chatRequestFinished(); assert.equal(h.last.readOnly, true, 'pending original still fences JD');
  } finally { await h.stop(); }
});
test('an unfinished JD form is preserved and blocks chat instead of being silently saved', async () => {
  const h = await setup();
  try {
    h.session.form({ name: '尚未完成的任務' }); h.session.chatEdit('想補充工作');
    await assert.rejects(h.session.chatPrepare(), { code: 'not_ready' });
    assert.equal(h.session.chatOriginal(), null); assert.equal(h.last.chatText, '想補充工作');
    assert.equal(h.store.row?.forms.editor.value && (h.store.row.forms.editor.value as {name:string}).name, '尚未完成的任務');
    assert.equal(h.saves.length, 0);
  } finally { await h.stop(); }
});
test('chat does not treat a failed manual flush as permission to send', async () => {
  const h = await setup();
  try {
    h.session.edit(h.last.view!.fields[0], '仍待保存'); h.session.chatEdit('原話');
    const preparing = h.session.chatPrepare(); await until(() => h.saves.length === 1);
    h.replies[0].reject(new ApiError('response_unknown'));
    await assert.rejects(preparing, { code: 'not_ready' });
    assert.equal(h.session.chatOriginal(), null); assert.ok(h.store.row?.submission);
    assert.equal(h.last.chatText, '原話');
  } finally { await h.stop(); }
});
test('both JD and chat composition block handoff without generating a request', async () => {
  const h = await setup();
  try {
    h.session.chatEdit('輸入法尚未選字'); h.session.chatComposition(true);
    await assert.rejects(h.session.chatPrepare(), { code: 'not_ready' });
    h.session.chatComposition(false); h.session.composition(true);
    await assert.rejects(h.session.chatPrepare(), { code: 'not_ready' });
    assert.equal(h.session.chatOriginal(), null);
  } finally { await h.stop(); }
});
test('saved terminal A acknowledges only A and preserves the next chat draft B', async () => {
  const h = await setup();
  try {
    h.session.chatEdit('A'); const original = await h.session.chatPrepare(); h.session.chatRequestFinished();
    h.session.chatEdit('B'); await until(() => h.store.row?.chatDraft?.text === 'B');
    await h.session.chatObserve(terminalChat(original.request.run_id));
    assert.equal(h.session.chatOriginal(), null); assert.equal(h.last.chatText, 'B');
    assert.equal(h.last.readOnly, false); assert.equal(h.last.chatReady, true);
  } finally { await h.stop(); }
});
test('an unavailable exact start restores A for editing without inventing a saved run', async () => {
  const h = await setup();
  try {
    h.session.chatEdit('  原話\n'); const original = await h.session.chatPrepare();
    await h.session.chatUnavailable(original); h.session.chatRequestFinished();
    assert.equal(h.session.chatOriginal(), null); assert.equal(h.last.chatText, '  原話\n');
    assert.equal(h.last.readOnly, false); assert.equal(h.saves.length, 0);
  } finally { await h.stop(); }
});
test('unknown original survives reopen and is not mistaken for a manual draft review', async () => {
  const h = await setup(); let saved: DraftRow;
  try {
    h.session.chatEdit('已送出但結果不明'); await h.session.chatPrepare(); h.session.chatRequestFinished();
    saved = structuredClone(h.store.row!);
  } finally { await h.stop(); }
  const next = await setup(saved!);
  try {
    assert.deepEqual(next.session.chatOriginal(), saved!.chatSubmission);
    assert.equal(next.last.needsReview, false); assert.equal(next.last.readOnly, true);
    assert.equal(next.saves.length, 0); assert.equal(next.last.chatReady, false);
  } finally { await next.stop(); }
});

test('A confirmed but writer still blocked must not dispatch B', async () => {
  const h = await setup();
  try {
    const field = h.last.view!.fields[0]; h.session.edit(field, 'A');
    const flush = h.session.flush(); await until(() => h.saves.length === 1);
    h.session.edit(field, 'B'); await until(() => h.store.row?.fields[key]?.text === 'B');
    h.commit(0, 'A', { ready: true, archived: false, write_blocked: true, running: false, operation_id: h.saves[0].operation_id, error: 'recovery_required' });
    await until(() => h.last.readOnly || h.saves.length > 1);
    await new Promise<void>(resolve => setImmediate(resolve));
    assert.equal(h.saves.length, 1, 'B waits while server still reports blocked');
    await flush; assert.equal(h.store.row!.fields[key].text, 'B');
  } finally { await h.stop(); }
});

test('new form is immediately dirty and its full RAM value survives local storage failure', async () => {
  const h = await setup();
  try {
    h.store.failForm = true;
    const form = { format: 1, task: { title: '不可遺失的新任務', outcomes: ['完整內容'] } };
    h.session.form(form);
    assert.equal(h.last.dirty, true, 'must protect navigation before IndexedDB resolves');
    await until(() => h.last.needsReview);
    assert.ok(JSON.stringify(h.last).includes('不可遺失的新任務'), 'the failed candidate remains observable for recovery');
  } finally { await h.stop(); }
});

test('explicit discard also removes the RAM-only field whose persistence failed', async () => {
  const h = await setup();
  try {
    h.store.failField = true; h.session.edit(h.last.view!.fields[0], '未持久內容');
    await until(() => h.last.needsReview);
    assert.equal(h.last.recoveryFields[key].text, '未持久內容');
    assert.equal(h.last.values[key], undefined, 'review must not overwrite the saved body with RAM-only text');
    assert.equal(h.last.view!.fields[0].value, '原內容');
    await h.session.resume(true);
    assert.equal(h.last.dirty, false); assert.equal(h.last.values[key], undefined);
  } finally { await h.stop(); }
});

test('explicit resume retries a RAM-only candidate instead of leaving it permanently unsaved', async () => {
  const h = await setup();
  try {
    h.store.failField = true; h.session.edit(h.last.view!.fields[0], '可重試內容');
    await until(() => h.last.needsReview); await h.session.resume(false);
    const flush = h.session.flush(); await until(() => h.saves.length === 1, 'RAM-only input is persisted before retry');
    h.commit(0, '可重試內容'); await flush; assert.equal(h.last.dirty, false);
  } finally { await h.stop(); }
});

test('dispose holds ownership until a pending local persistence finishes and emits no late update', async () => {
  const h = await setup();
  try {
    h.store.gate = deferred<void>(); h.session.edit(h.last.view!.fields[0], '離頁前輸入');
    await h.session.dispose(); await new Promise<void>(resolve => setImmediate(resolve));
    assert.equal(h.held, true); const count = h.snapshots.length;
    h.store.gate.resolve(); await until(() => !h.held);
    assert.equal(h.store.row!.fields[key].text, '離頁前輸入'); assert.equal(h.snapshots.length, count);
    assert.equal(h.saves.length, 0);
  } finally { await h.stop(); }
});

test('composition blocks send until the complete IME text is ready', async () => {
  const h = await setup();
  try {
    h.session.composition(true); h.session.edit(h.last.view!.fields[0], '完整繁中'); await h.session.flush();
    assert.equal(h.saves.length, 0); h.session.composition(false);
    const flush = h.session.flush(); await until(() => h.saves.length === 1);
    h.commit(0, '完整繁中'); await flush;
  } finally { await h.stop(); }
});

test('reopening a persisted original submission never automatically resends it', async () => {
  const store = new RecordStore(); const base = await store.claim(scope, uuid(80));
  const candidate = await store.persistField(draftHandle(base), { itemId: null, fieldName: 'job_title', fieldRef: '0:field', baseValue: '原內容', text: '原請求', seq: 1 });
  await store.prepareSubmission(draftHandle(candidate), { request: { operation_id: uuid(81), base_revision_ref: '0:revision', command: { tool: 'jd_set_text', arguments: { target_field_ref: '0:field', text: '原請求', basis_refs: [] } } }, coveredFields: { [key]: 1 }, coveredForms: {} });
  const h = await setup(store.row!);
  try {
    assert.equal(h.last.needsReview, true); await h.session.flush(); await h.session.reconcile(false);
    assert.equal(h.saves.length, 0); assert.equal(h.store.row!.submission!.request.operation_id, uuid(81));
  } finally { await h.stop(); }
});

test('a partially successful local retry can retry remaining input without looping on an already persisted sequence', async () => {
  const h = await setup();
  try {
    h.session.composition(true); h.store.failFieldCalls = new Set([1, 2, 4]);
    h.session.edit(h.last.view!.fields[0], '候選A'); h.session.edit(h.last.view!.fields[1], '候選B');
    await until(() => h.store.fieldCalls === 2 && h.last.needsReview);
    await h.session.resume(false);
    assert.equal(h.store.row!.fields[key].text, '候選A'); assert.equal(h.last.needsReview, true);
    await h.session.resume(false);
    assert.equal(h.store.row!.fields[fieldKey(null, 'purpose')]?.text, '候選B');
    assert.equal(h.last.needsReview, false);
  } finally { await h.stop(); }
});

test('A confirmed while current is later C keeps B for comparison and displays C', async () => {
  const h = await setup();
  try {
    const field = h.last.view!.fields[0]; h.session.edit(field, 'A');
    const flush = h.session.flush(); await until(() => h.saves.length === 1);
    h.session.edit(field, 'B'); await until(() => h.store.row?.fields[key]?.text === 'B');
    const originalRead = h.api.read;
    h.api.read = async (id, input) => input?.view === 'history' ? originalRead(id, input) : page(99, 'C');
    h.commit(0, 'A'); await flush;
    assert.equal(h.last.view!.fields[0].value, 'C'); assert.equal(h.last.needsReview, true);
    assert.equal(h.store.row!.fields[key].text, 'B'); assert.equal(h.store.row!.fields[key].baseValue, 'A');
    assert.equal(h.saves.length, 1);
  } finally { await h.stop(); }
});

test('explicit retry after missing lookup sends exactly the same original request', async () => {
  const h = await setup();
  try {
    h.session.edit(h.last.view!.fields[0], '原意圖');
    const first = h.session.flush(); await until(() => h.saves.length === 1);
    h.replies[0].reject(new ApiError('response_unknown')); await first;
    assert.ok(h.store.row!.submission); assert.equal(h.last.needsReview, true);
    await h.session.reconcile(false); assert.equal(h.saves.length, 1);
    const retry = h.session.reconcile(true); await until(() => h.saves.length === 2);
    assert.deepEqual(h.saves[1], h.saves[0]); h.commit(1, '原意圖'); await retry;
    assert.equal(h.store.row!.submission, null); assert.equal(h.last.dirty, false);
  } finally { await h.stop(); }
});

test('blocked A result keeps B in review until refreshed state is writable and the user resumes', async () => {
  const h = await setup();
  try {
    const field = h.last.view!.fields[0]; h.session.edit(field, 'A');
    const first = h.session.flush(); await until(() => h.saves.length === 1);
    h.session.edit(field, 'B'); await until(() => h.store.row?.fields[key]?.text === 'B');
    h.commit(0, 'A', { ready: true, archived: false, write_blocked: true, running: false, operation_id: h.saves[0].operation_id, error: 'recovery_required' });
    await first;
    assert.equal(h.last.needsReview, true); assert.equal(h.last.values[key], undefined);
    assert.equal(h.last.recoveryFields[key].text, 'B'); assert.ok(h.last.error);
    await h.session.resume(false); assert.equal(h.last.needsReview, true); assert.equal(h.saves.length, 1);
    h.api.state = async () => writable; await h.session.refreshStatus();
    assert.equal(h.last.needsReview, true, 'refresh does not automatically publish B');
    await h.session.resume(false); const second = h.session.flush(); await until(() => h.saves.length === 2);
    h.commit(1, 'B'); await second; assert.equal(h.last.dirty, false);
  } finally { await h.stop(); }
});

test('a delayed status read cannot replace a newer confirmed body', async () => {
  const h = await setup(); const delayed = deferred<ReadPage>();
  try {
    const originalRead = h.api.read; let reads = 0;
    h.api.read = async (id, input) => ++reads === 1 ? delayed.promise : originalRead(id, input);
    const refresh = h.session.refreshStatus();
    h.session.edit(h.last.view!.fields[0], '新的已保存內容');
    let flush = h.session.flush();
    for (let i = 0; i < 20 && h.saves.length === 0; i++) await new Promise<void>(resolve => setImmediate(resolve));
    if (h.saves.length === 0) {
      // A serialized status read is also valid; finish it before allowing the write.
      delayed.resolve(page()); await refresh; await flush;
      if (h.last.needsReview) await h.session.resume(false);
      flush = h.session.flush();
    }
    await until(() => h.saves.length === 1); h.commit(0, '新的已保存內容'); await flush;
    delayed.resolve(page()); await refresh;
    assert.equal(h.last.view!.fields[0].value, '新的已保存內容');
    assert.equal(h.last.view!.revisionRef, '1:revision');
  } finally { delayed.resolve(page()); await h.stop(); }
});
