import assert from 'node:assert/strict';
import test from 'node:test';
import { JdSession } from '../src/lib/session.ts';
import type { SessionSnapshot } from '../src/lib/session.ts';
import { ApiError } from '../src/lib/api.ts';
import type { JdApi } from '../src/lib/api.ts';
import { acknowledgeSubmissionRecord, claimDraftRecord, fieldKey, persistChatRecord, persistFieldRecord,
  prepareSubmissionRecord, rebindFieldRecord } from '../src/lib/drafts.ts';
import type { ChatDraft, DraftHandle, DraftRow, DraftScope, DraftStore, FieldDraft, PrepareSubmission,
  RebindField, SubmissionAcknowledgment } from '../src/lib/drafts.ts';
import type { ChatRunState } from '../../src/jd_relational/generated/jd-chat-http.ts';
import type { ReadInput, ReadPage, ReadRecord } from '../../src/jd_relational/generated/jd-read.ts';
import type { ManualDocumentState, ManualSaveInput } from '../../src/jd_relational/generated/jd-manual-http.ts';
import type { MutationResult } from '../../src/jd_relational/generated/jd-result.ts';

const uuid = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const scope = { apiOrigin: 'http://127.0.0.1:9000', datasetId: uuid(1), documentId: uuid(2) };
const writable: ManualDocumentState = { ready: true, archived: false, write_blocked: false, running: false, operation_id: null, error: null };
const field = fieldKey(null, 'job_title');
function page(revision = 0, value = '原內容'): ReadPage {
  const records: ReadRecord[] = [
    ...(['profile', 'purpose', 'duties_tasks', 'knowledge', 'skills', 'conditions'] as const).map(section_key => ({ type: 'section' as const, section_key, section_ref: `${revision}:${section_key}`, title: section_key })),
    { type: 'field', field_ref: `${revision}:field`, section_ref: `${revision}:profile`, item_ref: null, name: 'job_title', value },
  ];
  return { format_version: 2, view: 'current', access: 'current', revision_ref: `${revision}:revision`, records,
    start_index: 0, total_records: records.length, has_more: false, next_cursor: null, oversized_unit: false };
}
function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (error: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
async function until(check: () => boolean) {
  for (let n = 0; n < 100; n++) { if (check()) return; await new Promise<void>(resolve => setImmediate(resolve)); }
  assert.ok(check(), 'bounded expected state');
}
// Independent record/lock port doubles: these do not claim native IndexedDB or browser execution.
class Store {
  row: DraftRow | null = null; failChatOnce = false;
  async claim(value: DraftScope, owner: string) { return this.row = claimDraftRecord(this.row, value, owner, uuid(3)); }
  close() {}
  async persistChat(handle: DraftHandle, input: ChatDraft) {
    if (this.failChatOnce) { this.failChatOnce = false; throw new Error('synthetic storage failure'); }
    return this.row = persistChatRecord(this.row!, handle, input);
  }
  async persistField(handle: DraftHandle, input: FieldDraft) { return this.row = persistFieldRecord(this.row!, handle, input); }
  async prepareSubmission(handle: DraftHandle, input: PrepareSubmission) { return this.row = prepareSubmissionRecord(this.row!, handle, input); }
  async acknowledgeSubmission(handle: DraftHandle, input: SubmissionAcknowledgment) { return this.row = acknowledgeSubmissionRecord(this.row!, handle, input); }
  async rebindField(handle: DraftHandle, input: RebindField) { return this.row = rebindFieldRecord(this.row!, handle, input); }
}
async function setup() {
  const store = new Store(), snapshots: SessionSnapshot[] = [], saves: ManualSaveInput[] = [];
  const replies: ReturnType<typeof deferred<MutationResult>>[] = [];
  let current = page(), held = false;
  const history = new Map<string, ReadPage>([['0:observation', page()]]);
  const api = { origin: scope.apiOrigin, datasetId: scope.datasetId,
    read: async (_id?: string, input?: ReadInput): Promise<ReadPage> => {
      if (input?.view === 'history') {
        const original = history.get(input.target_ref!); assert.ok(original);
        return { ...structuredClone(original), view: 'history', access: 'history' };
      }
      return structuredClone(current);
    }, state: async () => structuredClone(writable),
    save: async (_id: string, request: ManualSaveInput) => {
      saves.push(request); const reply = deferred<MutationResult>(); replies.push(reply); return reply.promise;
    },
  };
  const request = (async (_name: string, _options: unknown, callback: (lock: Lock) => Promise<unknown>) => {
    assert.equal(held, false); held = true;
    try { return await callback({ name: 'review-document-lock', mode: 'exclusive' }); } finally { held = false; }
  }) as LockManager['request'];
  const session = new JdSession(api as unknown as JdApi, scope.documentId, value => snapshots.push(value), {
    openStore: async () => store as unknown as DraftStore, locks: { request },
  });
  await session.start(); await until(() => snapshots.at(-1)?.loading === false);
  return { session, api, store, saves, get last() { return snapshots.at(-1)!; },
    commit() {
      current = page(1, '較新的人工保存'); history.set('1:observation', structuredClone(current));
      replies[0].resolve({ status: 'committed', effect: 'changed', receipt_durability: 'confirmed', operation_ref: 'original-op',
        result_revision_ref: '1:observation', change_ref: 'original-change', error: null, next_action: 'continue' });
    },
    async stop() { for (const reply of replies) reply.reject(new ApiError('response_unknown')); await session.dispose(); await until(() => !held); },
  };
}
const terminal: ChatRunState = { dataset_id: scope.datasetId, document_id: scope.documentId, run_id: uuid(40),
  run_status: 'completed', input_state: 'saved', response_message_id: 'old-reply', stop_requested: null,
  write_state: writable, jd_effects: { state: 'settled', results: [] } };

test('review: delayed old-run chat observation cannot replace a newer confirmed manual revision', async () => {
  const h = await setup(), delayed = deferred<ReadPage>();
  let readStarted = false;
  try {
    const nativeRead = h.api.read;
    h.api.read = async (id, input) => {
      if (!readStarted && input?.view !== 'history') { readStarted = true; return delayed.promise; }
      return nativeRead(id, input);
    };
    const observe = h.session.chatObserve(terminal); await until(() => readStarted);
    h.session.edit(h.last.view!.fields[0], '較新的人工保存'); let flush = h.session.flush();
    // A correct serialized observation may block the write, so release it before committing.
    for (let n = 0; n < 20 && !h.saves.length; n++) await new Promise<void>(resolve => setImmediate(resolve));
    if (!h.saves.length) {
      delayed.resolve(page()); await observe; await flush;
      if (h.last.needsReview) await h.session.resume(false);
      flush = h.session.flush();
    }
    await until(() => h.saves.length === 1); h.commit(); await flush;
    assert.equal(h.store.row!.fields[field], undefined);
    delayed.resolve(page()); await observe;
    assert.equal(h.last.view!.revisionRef, '1:revision');
    assert.equal(h.last.view!.fields[0].value, '較新的人工保存');
  } finally { delayed.resolve(page()); await h.stop(); }
});

test('review: explicit recovery retries RAM-only chat candidate after a one-time storage failure', async () => {
  const h = await setup();
  try {
    h.store.failChatOnce = true; h.session.chatEdit('不能遺失的原話');
    await until(() => h.last.needsReview);
    assert.equal(h.last.chatText, '不能遺失的原話'); assert.equal(h.store.row!.chatDraft, null);
    await h.session.resume(false);
    const restored = structuredClone<DraftRow>(h.store.row!);
    assert.equal(restored.chatDraft?.text, '不能遺失的原話');
    assert.equal(h.last.chatSaving, false); assert.equal(h.last.needsReview, false);
  } finally { await h.stop(); }
});
