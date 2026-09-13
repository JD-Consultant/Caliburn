import assert from 'node:assert/strict';
import test from 'node:test';
import { acknowledgeChatRecord, acknowledgeSubmissionRecord, claimDraftRecord, draftHandle, DraftError, DraftStore,
  persistChatRecord, persistFieldRecord, persistFormRecord, prepareChatRecord, prepareSubmissionRecord,
  rejectUnavailableChatRecord, restoreChatRecord, validateDraftRecord, validateStoredDraftRecord } from '../src/lib/drafts.ts';
import type { ChatAcknowledgment, DraftRow, StoredDraftRow } from '../src/lib/drafts.ts';
import type { ChatRunState, ChatStartInput } from '../../src/jd_relational/generated/jd-chat-http.ts';

const uuid = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const scope = { apiOrigin: 'http://127.0.0.1:9000', datasetId: uuid(1), documentId: uuid(2) };
const key = JSON.stringify([null, 'job_title']);
function legacy() {
  return { format: 1 as const, scope, draftId: uuid(3), ownerEpoch: uuid(4), generation: 8, inputSeq: 4,
    fields: { [key]: { itemId: null, fieldName: 'job_title', fieldRef: 'original-field', baseValue: '原職稱', text: '工程專員', seq: 4 } },
    forms: { editor: { key: 'editor', value: { title: '尚未完成任務', outcomes: ['完整保留'] }, seq: 3 } },
    submission: { request: { operation_id: uuid(5), base_revision_ref: 'original-revision', command: {
      tool: 'jd_set_text' as const, arguments: { target_field_ref: 'original-field', text: '工程專員', basis_refs: [] } } },
    submissionGeneration: 8, coveredFields: { [key]: 4 }, coveredForms: {} } };
}
const fresh = () => claimDraftRecord(null, scope, uuid(4), uuid(3));
const original: ChatStartInput = { run_id: uuid(8), text: '原話\r\n  每月檢查😀', expected_jd_revision_ref: 'original-revision' };
const writable = { ready: true as const, archived: false as const, write_blocked: false as const, running: false as const, operation_id: null, error: null };
const state = (overrides: object = {}): ChatRunState => ({ dataset_id: scope.datasetId, document_id: scope.documentId,
  run_id: original.run_id, write_state: writable, run_status: 'completed', input_state: 'saved',
  response_message_id: 'native-response', stop_requested: null, jd_effects: { state: 'settled', results: [] }, ...overrides } as ChatRunState);
function prepared() {
  const row = fresh(), typed = persistChatRecord(row, draftHandle(row), { text: original.text, seq: 1 });
  return prepareChatRecord(typed, draftHandle(typed), { request: original, coveredSeq: 1 });
}
const identity = (row: DraftRow) => ({ runId: row.chatSubmission!.request.run_id, submissionGeneration: row.chatSubmission!.submissionGeneration });
const ack = (row: DraftRow, result = state()): ChatAcknowledgment => ({ ...identity(row), state: result });
const knownNotSaved = () => state({ run_status: 'failed', input_state: 'not_saved', response_message_id: null });
function unchanged(row: DraftRow, act: () => unknown, code: string) {
  const before = structuredClone(row);
  assert.throws(act, (error: unknown) => error instanceof DraftError && error.code === code);
  assert.deepEqual(row, before);
}

test('claim alone upgrades exact v1 manual pending data to v2 without changing its request or candidates', () => {
  const old = legacy(), before = structuredClone(old);
  const next = claimDraftRecord(old, scope, uuid(6), uuid(7));
  assert.equal(next.format, 2);
  assert.deepEqual(old, before);
  assert.equal(next.draftId, old.draftId);
  assert.equal(next.ownerEpoch, uuid(6));
  assert.equal(next.generation, old.generation + 1);
  assert.equal(next.inputSeq, old.inputSeq);
  assert.deepEqual(next.fields, old.fields);
  assert.deepEqual(next.forms, old.forms);
  assert.deepEqual(next.submission, old.submission);
  assert.equal(next.chatDraft, null);
  assert.equal(next.chatSubmission, null);
});

test('readonly legacy validation preserves its version and rejects corrupt or unknown formats', () => {
  const old = legacy(); assert.equal(validateStoredDraftRecord(old), old); assert.equal(old.format, 1);
  assert.throws(() => validateDraftRecord(old), /invalid_draft/);
  for (const bad of [{ ...old, format: 3 }, { ...old, chatDraft: null }, { ...old, fields: {} },
    { ...old, submission: { ...old.submission, request: { ...old.submission.request, extra: true } } }]) {
    const before = structuredClone(bad);
    assert.throws(() => claimDraftRecord(bad as never, scope, uuid(6), uuid(7)), /invalid_draft/);
    assert.deepEqual(bad, before);
  }
});

test('prepare stores the exact original A before clearing only A composer and freezes caller mutation', () => {
  const a = fresh(), text = persistChatRecord(a, draftHandle(a), { text: original.text, seq: 1 });
  const request = structuredClone(original), before = structuredClone(text);
  const row = prepareChatRecord(text, draftHandle(text), { request, coveredSeq: 1 });
  assert.deepEqual(text, before); assert.equal(row.chatDraft, null);
  assert.deepEqual(row.chatSubmission!.request, original);
  request.text = 'later request mutation'; request.expected_jd_revision_ref = 'changed-ref';
  assert.deepEqual(row.chatSubmission!.request, original);
  assert.equal(row.chatSubmission!.submissionGeneration, row.generation);
});

for (const status of ['completed', 'failed', 'cancelled']) test(`terminal saved ${status} A preserves typed B on exact ACK`, () => {
  const a = prepared(), b = persistChatRecord(a, draftHandle(a), { text: '下一段 B\n尚未送出', seq: 2 });
  const next = acknowledgeChatRecord(b, draftHandle(b), ack(b, state({ run_status: status })));
  assert.equal(next.chatSubmission, null); assert.deepEqual(next.chatDraft, b.chatDraft);
  assert.equal(b.chatSubmission!.request.text, original.text); assert.equal(next.inputSeq, 2);
});

test('a saved terminal A can be cleared while another run blocks current JD editing', () => {
  const row = prepared(), result = state({ write_state: { ...writable, write_blocked: true, running: true, error: 'busy' } });
  assert.equal(acknowledgeChatRecord(row, draftHandle(row), ack(row, result)).chatSubmission, null);
});

test('new owner fences old chat typing, ACK, restore, and pre-admission callbacks', () => {
  const row = prepared(), old = draftHandle(row), next = claimDraftRecord(row, scope, uuid(55), uuid(56));
  assert.deepEqual(next.chatSubmission, row.chatSubmission);
  for (const act of [() => persistChatRecord(next, old, { text: '舊頁', seq: 2 }),
    () => acknowledgeChatRecord(next, old, ack(next)),
    () => restoreChatRecord(next, old, ack(next, knownNotSaved())),
    () => rejectUnavailableChatRecord(next, old, identity(next))]) unchanged(next, act, 'owner_changed');
});

test('old run or submission generation cannot acknowledge a current original request', () => {
  const row = prepared();
  for (const input of [{ ...ack(row), runId: uuid(99) }, { ...ack(row), submissionGeneration: 1 }])
    unchanged(row, () => acknowledgeChatRecord(row, draftHandle(row), input), 'submission_changed');
});

for (const name of ['dataset_id', 'document_id', 'run_id']) test(`terminal ACK rejects another ${name}`, () => {
  const row = prepared();
  unchanged(row, () => acknowledgeChatRecord(row, draftHandle(row), ack(row, state({ [name]: uuid(99) }))), 'scope_changed');
});

for (const run_status of ['not_found', 'running', 'closing', 'recovery_required'])
  test(`${run_status} cannot clear or restore original A`, () => {
    const row = prepared();
    const result = state({ run_status, input_state: 'unconfirmed', response_message_id: null,
      stop_requested: run_status === 'running' ? false : null,
      write_state: run_status === 'not_found' ? writable : { ...writable, write_blocked: true },
      jd_effects: { state: 'unconfirmed', results: [] } });
    unchanged(row, () => acknowledgeChatRecord(row, draftHandle(row), ack(row, result)), 'result_unconfirmed');
    unchanged(row, () => restoreChatRecord(row, draftHandle(row), ack(row, result)), 'result_unconfirmed');
  });

test('known not-saved needs explicit restore and cannot overwrite later B', () => {
  const a = prepared(); unchanged(a, () => acknowledgeChatRecord(a, draftHandle(a), ack(a, knownNotSaved())), 'result_unconfirmed');
  const b = persistChatRecord(a, draftHandle(a), { text: 'B', seq: 2 });
  unchanged(b, () => restoreChatRecord(b, draftHandle(b), ack(b, knownNotSaved())), 'input_changed');
  const next = restoreChatRecord(a, draftHandle(a), ack(a, knownNotSaved()));
  assert.deepEqual(next.chatDraft, { text: original.text, seq: 2 }); assert.equal(next.chatSubmission, null);
});

test('explicit restore into empty composer advances shared sequence and rejects saved input', () => {
  const a = prepared(), blank = persistChatRecord(a, draftHandle(a), { text: '', seq: 8 });
  const next = restoreChatRecord(blank, draftHandle(blank), ack(blank, knownNotSaved()));
  assert.deepEqual(next.chatDraft, { text: original.text, seq: 9 }); assert.equal(next.inputSeq, 9);
  unchanged(a, () => restoreChatRecord(a, draftHandle(a), ack(a)), 'result_unconfirmed');
});

test('only explicit original ai_unavailable branch restores A without fabricating run state', () => {
  const a = prepared(), next = rejectUnavailableChatRecord(a, draftHandle(a), identity(a));
  assert.deepEqual(next.chatDraft, { text: original.text, seq: 2 }); assert.equal(next.chatSubmission, null);
  const b = persistChatRecord(a, draftHandle(a), { text: 'B', seq: 2 });
  unchanged(b, () => rejectUnavailableChatRecord(b, draftHandle(b), identity(b)), 'input_changed');
  unchanged(a, () => rejectUnavailableChatRecord(a, draftHandle(a), { ...identity(a), state: state() } as never), 'invalid_draft');
});

test('manual fields, unfinished forms, and unknown manual submission prevent chat handoff', () => {
  const base = fresh();
  const field = legacy().fields[key];
  for (const manual of [persistFieldRecord(base, draftHandle(base), field),
    persistFormRecord(base, draftHandle(base), legacy().forms.editor),
    claimDraftRecord(legacy(), scope, uuid(6), uuid(7))]) {
    const typed = persistChatRecord(manual, draftHandle(manual), { text: original.text, seq: manual.inputSeq + 1 });
    unchanged(typed, () => prepareChatRecord(typed, draftHandle(typed), { request: original, coveredSeq: typed.chatDraft!.seq }), 'manual_pending');
  }
});

test('pending chat disallows manual writes but keeps pure chat B typing available', () => {
  const a = prepared();
  for (const act of [() => persistFieldRecord(a, draftHandle(a), legacy().fields[key]),
    () => persistFormRecord(a, draftHandle(a), legacy().forms.editor),
    () => prepareSubmissionRecord(a, draftHandle(a), { request: legacy().submission.request, coveredFields: {}, coveredForms: {} })])
    unchanged(a, act, 'chat_submission_pending');
  const b = persistChatRecord(a, draftHandle(a), { text: 'B', seq: 2 });
  unchanged(b, () => prepareChatRecord(b, draftHandle(b), { request: { ...original, run_id: uuid(99), text: 'B' }, coveredSeq: 2 }), 'chat_submission_pending');
});

test('manual receipt updates keep independent unsent chat text intact', () => {
  const row = claimDraftRecord(legacy(), scope, uuid(6), uuid(7));
  const typed = persistChatRecord(row, draftHandle(row), { text: '尚未送出的聊天', seq: 5 });
  const result = { status: 'committed', effect: 'changed', receipt_durability: 'confirmed', operation_ref: 'op',
    result_revision_ref: 'revision', change_ref: 'change', error: null, next_action: 'continue' } as const;
  const next = acknowledgeSubmissionRecord(typed, draftHandle(typed), { operationId: uuid(5), submissionGeneration: 8, result });
  assert.deepEqual(next.chatDraft, typed.chatDraft); assert.deepEqual(next.forms, typed.forms);
});

test('stale text/coverage, duplicate sequences and late typing after prepare cannot replace A', () => {
  const a = fresh(), typed = persistChatRecord(a, draftHandle(a), { text: original.text, seq: 3 });
  for (const input of [{ request: original, coveredSeq: 2 }, { request: { ...original, text: 'different' }, coveredSeq: 3 }])
    unchanged(typed, () => prepareChatRecord(typed, draftHandle(typed), input), 'input_changed');
  const row = prepareChatRecord(typed, draftHandle(typed), { request: original, coveredSeq: 3 });
  for (const seq of [1, 3]) unchanged(row, () => persistChatRecord(row, draftHandle(row), { text: 'late', seq }), 'input_changed');
});

test('candidate preserves blank original values but request cannot submit blank or oversized text', () => {
  const base = fresh(), blank = persistChatRecord(base, draftHandle(base), { text: ' \r\n ', seq: 1 });
  assert.equal(blank.chatDraft!.text, ' \r\n ');
  unchanged(blank, () => prepareChatRecord(blank, draftHandle(blank), { request: { ...original, text: blank.chatDraft!.text }, coveredSeq: 1 }), 'invalid_draft');
  const large = persistChatRecord(base, draftHandle(base), { text: '文'.repeat(45000), seq: 1 });
  unchanged(large, () => prepareChatRecord(large, draftHandle(large), { request: { ...original, text: large.chatDraft!.text }, coveredSeq: 1 }), 'invalid_draft');
  unchanged(base, () => persistChatRecord(base, draftHandle(base), { text: 'x'.repeat(4 * 1024 * 1024), seq: 1 }), 'draft_too_large');
});

test('bad request/state schemas and unsafe counters preserve original row', () => {
  const base = fresh(), a = prepared();
  for (const draft of [{ text: 'A', seq: true }, { text: null, seq: 1 }, { text: 'A', seq: Number.MAX_SAFE_INTEGER + 1 }, { text: 'A', seq: 1, extra: true }])
    unchanged(base, () => persistChatRecord(base, draftHandle(base), draft as never), 'invalid_draft');
  for (const result of [state({ extra: 'private' }), state({ input_state: 'unconfirmed' }),
    state({ write_state: { ...writable, ready: 1 } }), state({ run_status: 'failed', input_state: 'not_saved', response_message_id: 'impossible' })])
    unchanged(a, () => acknowledgeChatRecord(a, draftHandle(a), ack(a, result)), 'invalid_draft');
  for (const bad of [{ ...a, chatSubmission: { ...a.chatSubmission, request: { ...original, extra: true } } },
    { ...a, chatSubmission: { ...a.chatSubmission, coveredSeq: true } }, { ...a, chatDraft: { text: 'stale', seq: 1 } },
    { ...a, fields: legacy().fields }]) assert.throws(() => validateDraftRecord(bad), /invalid_draft/);
});

// These are transaction-port doubles, not evidence of native IndexedDB/versionchange or browser persistence.
function port(initial: StoredDraftRow | null) {
  let stored = structuredClone(initial), resolve!: () => void, reject!: (error: Error) => void;
  const done = new Promise<void>((yes, no) => { resolve = yes; reject = no; });
  let candidate: StoredDraftRow | null = null, puts = 0, reads = 0, transactions = 0;
  const db = { get: async () => { reads++; return structuredClone(stored); },
    getAllFromIndex: async () => stored ? [structuredClone(stored)] : [],
    transaction: (_store: string, mode: string, options: object) => {
      transactions++; assert.equal(mode, 'readwrite'); assert.deepEqual(options, { durability: 'strict' });
      return { store: { get: async () => structuredClone(stored), put: async (value: StoredDraftRow) => { puts++; candidate = structuredClone(value); } },
        done, abort: () => reject(new Error('aborted')) };
    }, close() {} };
  return { store: new DraftStore(db as never), commit() { stored = candidate; resolve(); },
    fail() { reject(new Error('synthetic commit failure')); }, get stored() { return stored; }, get puts() { return puts; },
    get transactions() { return transactions; }, get reads() { return reads; } };
}
test('readonly store does not migrate v1; claim waits for transaction commit and preserves original data', async () => {
  const old = legacy(), p = port(old);
  assert.deepEqual(await p.store.read(scope), old); assert.deepEqual(await p.store.listForDocument(scope.apiOrigin, scope.documentId), [old]);
  assert.equal(p.puts, 0); assert.equal(p.transactions, 0);
  let completed = false; const pending = p.store.claim(scope, uuid(66)).then(row => { completed = true; return row; });
  await new Promise<void>(resolve => setImmediate(resolve)); assert.equal(p.puts, 1); assert.equal(completed, false);
  assert.deepEqual(p.stored, old); p.commit(); const next = await pending;
  assert.equal(next.format, 2); assert.deepEqual(next.submission, old.submission);
});

test('prepare persistence does not finish until commit; commit failure leaves durable original unchanged', async () => {
  const base = fresh(), row = persistChatRecord(base, draftHandle(base), { text: original.text, seq: 1 }), p = port(row);
  const pending = p.store.prepareChat(draftHandle(row), { request: original, coveredSeq: 1 });
  await new Promise<void>(resolve => setImmediate(resolve)); assert.equal(p.puts, 1);
  p.fail(); await assert.rejects(pending, /storage_unavailable/); assert.deepEqual(p.stored, row);
});

test('unclaimed v1 cannot be overwritten by a new mutation method', async () => {
  const old = legacy(), p = port(old);
  await assert.rejects(p.store.persistChat(draftHandle(old), { text: 'A', seq: 5 }), /owner_changed/);
  assert.equal(p.puts, 0); assert.deepEqual(p.stored, old);
});

test('falsy corrupt stored rows are not mistaken for an absent record or overwritten by claim', async () => {
  for (const value of [false, 0, '', null]) {
    const p = port(value as never);
    await assert.rejects(p.store.read(scope), /invalid_draft/);
    await assert.rejects(p.store.claim(scope, uuid(66)), /invalid_draft/);
    assert.equal(p.puts, 0); assert.equal(p.stored, value);
  }
});
