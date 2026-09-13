import assert from 'node:assert/strict';
import test from 'node:test';
import {
  acknowledgeSubmissionRecord, claimDraftRecord, draftHandle, fieldKey,
  persistFieldRecord, persistFormRecord, prepareSubmissionRecord, validateDraftRecord, prepareCreationRecord,
  rebindFieldRecord,
} from '../src/lib/drafts.ts';
import type { DraftRow, FieldDraft } from '../src/lib/drafts.ts';
import type { ManualSaveInput } from '../../src/jd_relational/generated/jd-manual-http.ts';
import type { MutationResult } from '../../src/jd_relational/generated/jd-result.ts';

const uuid = (n: number) => `00000000-0000-0000-0000-${n.toString().padStart(12, '0')}`;
const scope = { apiOrigin: 'http://127.0.0.1:8002', datasetId: uuid(1), documentId: uuid(2) };
const key = fieldKey(uuid(3), 'description');
const field = (text = 'A', seq = 1): FieldDraft => ({ itemId: uuid(3), fieldName: 'description', fieldRef: 'field:original', baseValue: '原內容', text, seq });
const fresh = () => claimDraftRecord(null, scope, uuid(4), uuid(5));
const request = (): ManualSaveInput => ({ operation_id: uuid(6), base_revision_ref: 'revision:original',
  command: { tool: 'jd_set_text', arguments: { target_field_ref: 'field:original', text: 'A', basis_refs: [] } } });
const committed: MutationResult = { status: 'committed', effect: 'changed', receipt_durability: 'confirmed', operation_ref: 'op:opaque', result_revision_ref: 'revision:result', change_ref: 'change:result', error: null, next_action: 'continue' };
function prepared(row = persistFieldRecord(fresh(), draftHandle(fresh()), field())) {
  return prepareSubmissionRecord(row, draftHandle(row), { request: request(), coveredFields: { [key]: 1 }, coveredForms: {} });
}
function ack(row: DraftRow, result = committed) {
  return acknowledgeSubmissionRecord(row, draftHandle(row), { operationId: uuid(6), submissionGeneration: row.submission!.submissionGeneration, result });
}

test('confirmed A preserves later B and updates its original value without inventing a field ref', () => {
  const a = prepared(); const b = persistFieldRecord(a, draftHandle(a), field('B', 2));
  const saved = ack(b);
  assert.equal(saved.fields[key].text, 'B'); assert.equal(saved.fields[key].baseValue, 'A');
  assert.equal(saved.fields[key].fieldRef, 'field:original');
  assert.equal(saved.submission, null); assert.ok(saved.generation > b.generation);
});

test('A only removes the exact covered field and keeps another earlier unsent field', () => {
  let row = persistFieldRecord(fresh(), draftHandle(fresh()), { ...field('另外內容', 1), fieldName: 'name' });
  row = persistFieldRecord(row, draftHandle(row), field('A', 2));
  row = prepareSubmissionRecord(row, draftHandle(row), { request: request(), coveredFields: { [key]: 2 }, coveredForms: {} });
  const saved = ack(row);
  assert.equal(saved.fields[key], undefined);
  assert.equal(saved.fields[fieldKey(uuid(3), 'name')].text, '另外內容');
});

test('complete unfinished task form survives an unrelated confirmed text save', () => {
  let row = prepared();
  const value = { name: '每月報表', outcomes: [{ text: '交付結果', conditions: ['尚待訪談'] }], requirements: [], capabilityIds: [uuid(7)] };
  row = persistFormRecord(row, draftHandle(row), { key: 'new-task', seq: 2, value });
  assert.deepEqual(ack(row).forms['new-task'].value, value);
});

test('unknown result preserves original request and all input', () => {
  const row = prepared(); const before = structuredClone(row);
  assert.throws(() => ack(row, { status: 'outcome_unknown', effect: 'unknown', receipt_durability: 'unconfirmed', operation_ref: 'op:opaque', result_revision_ref: null, change_ref: null, error: { code: 'outcome_unknown', message: 'unknown', related_refs: [] }, next_action: 'reconcile_operation' }), /result_unconfirmed/);
  assert.deepEqual(row, before);
});

test('a new lock owner fences old callbacks while keeping the immutable original request', () => {
  const old = prepared(); const handle = draftHandle(old);
  const next = claimDraftRecord(old, scope, uuid(9), uuid(10));
  assert.deepEqual(next.submission, old.submission); assert.equal(next.draftId, old.draftId);
  assert.throws(() => persistFieldRecord(next, handle, field('舊頁', 2)), /owner_changed/);
});

test('old operation and submission generation cannot acknowledge a current row', () => {
  const row = prepared();
  assert.throws(() => acknowledgeSubmissionRecord(row, draftHandle(row), { operationId: uuid(77), submissionGeneration: row.submission!.submissionGeneration, result: committed }), /submission_changed/);
  assert.throws(() => acknowledgeSubmissionRecord(row, draftHandle(row), { operationId: uuid(6), submissionGeneration: row.submission!.submissionGeneration - 1, result: committed }), /submission_changed/);
});

test('prepare refuses replacing an unsettled original operation or stale coverage', () => {
  const row = prepared();
  assert.throws(() => prepareSubmissionRecord(row, draftHandle(row), { request: { ...request(), operation_id: uuid(8) }, coveredFields: { [key]: 1 }, coveredForms: {} }), /submission_pending/);
  const next = persistFieldRecord(fresh(), draftHandle(fresh()), field('B', 2));
  assert.throws(() => prepareSubmissionRecord(next, draftHandle(next), { request: request(), coveredFields: { [key]: 1 }, coveredForms: {} }), /input_changed/);
});

test('local format and generated HTTP contract are checked before accepting recovered rows', () => {
  const row = prepared(); assert.equal(validateDraftRecord(row).format, 1);
  assert.throws(() => validateDraftRecord({ ...row, format: 2 }), /invalid_draft/);
  assert.throws(() => validateDraftRecord({ ...row, submission: { ...row.submission, request: { ...request(), extra: true } } }), /invalid_draft/);
  assert.throws(() => claimDraftRecord(row, { ...scope, datasetId: uuid(66) }, uuid(9), uuid(10)), /scope_changed/);
});

test('local values are bounded plain JSON and caller mutation cannot alter original request', () => {
  const row = fresh(); const handle = draftHandle(row);
  assert.throws(() => persistFormRecord(row, handle, { key: 'task', seq: 1, value: { bad: undefined } as never }), /invalid_draft/);
  const original = request(); const typed = persistFieldRecord(row, handle, field());
  const next = prepareSubmissionRecord(typed, handle, { request: original, coveredFields: { [key]: 1 }, coveredForms: {} });
  original.base_revision_ref = 'mutated'; assert.equal(next.submission!.request.base_revision_ref, 'revision:original');
});

test('confirmed rejection clears only submission and retains candidates for correction', () => {
  const row = prepared();
  const saved = ack(row, { status: 'invalid_input', effect: 'unchanged', receipt_durability: 'confirmed', operation_ref: 'op:opaque', result_revision_ref: null, change_ref: null, error: { code: 'invalid_input', message: 'correct input', related_refs: [] }, next_action: 'correct_arguments' });
  assert.equal(saved.submission, null); assert.deepEqual(saved.fields, row.fields);
});

test('unbound rejection cannot erase an already prepared original operation', () => {
  const row = prepared();
  assert.throws(() => ack(row, { status: 'busy', effect: 'unchanged', receipt_durability: 'unconfirmed', operation_ref: null, result_revision_ref: null, change_ref: null, error: { code: 'busy', message: 'busy', related_refs: [] }, next_action: 'stop' }), /result_unconfirmed/);
  assert.ok(row.submission);
});

test('rebind is explicit, fenced by current input sequence, and unavailable during unknown submission', () => {
  const a = prepared(); const b = persistFieldRecord(a, draftHandle(a), field('B', 2));
  assert.throws(() => rebindFieldRecord(b, draftHandle(b), { key, seq: 2, fieldRef: 'new-ref', baseValue: 'A' }), /submission_pending/);
  const saved = ack(b);
  assert.throws(() => rebindFieldRecord(saved, draftHandle(saved), { key, seq: 1, fieldRef: 'new-ref', baseValue: 'A' }), /input_changed/);
  const rebound = rebindFieldRecord(saved, draftHandle(saved), { key, seq: 2, fieldRef: 'new-ref', baseValue: 'A' });
  assert.equal(rebound.fields[key].text, 'B'); assert.equal(rebound.fields[key].fieldRef, 'new-ref');
});

test('one-field submission cannot claim other unsent fields or forms', () => {
  let row = persistFieldRecord(fresh(), draftHandle(fresh()), field());
  row = persistFieldRecord(row, draftHandle(row), { ...field('name', 2), fieldName: 'name' });
  assert.throws(() => prepareSubmissionRecord(row, draftHandle(row), { request: request(), coveredFields: { [key]: 1, [fieldKey(uuid(3), 'name')]: 2 }, coveredForms: {} }), /invalid_coverage/);
});

test('late input persistence cannot overwrite a later sequence of the same field', () => {
  const row = persistFieldRecord(fresh(), draftHandle(fresh()), field('C', 3));
  assert.throws(() => persistFieldRecord(row, draftHandle(row), field('B', 2)), /input_changed/);
  assert.equal(row.fields[key].text, 'C');
});

test('unsafe values, oversized candidate and unsafe counters leave original row unchanged', () => {
  const row = fresh(); const handle = draftHandle(row);
  assert.throws(() => persistFormRecord(row, handle, { key: 'task', seq: 1, value: { value: Number.NaN } }), /invalid_draft/);
  assert.throws(() => persistFieldRecord(row, handle, field('x'.repeat(4 * 1024 * 1024), 1)), /draft_too_large/);
  assert.throws(() => persistFieldRecord(row, handle, field('A', Number.MAX_SAFE_INTEGER + 1)), /invalid_draft/);
  assert.deepEqual(row.fields, {});
});

test('creation keeps exact original identity and rejects another pending intent', () => {
  const original = { request_key: uuid(80), dataset_id: scope.datasetId, title: '完整工作' };
  const next = prepareCreationRecord(null, original); original.title = 'external mutation';
  assert.equal(next.title, '完整工作');
  assert.deepEqual(prepareCreationRecord(next, { ...next }), next);
  assert.throws(() => prepareCreationRecord(next, { ...next, title: 'changed intent' }), /creation_pending/);
  assert.throws(() => prepareCreationRecord(next, { ...next, request_key: uuid(81) }), /creation_pending/);
  assert.throws(() => prepareCreationRecord(next, { ...next, dataset_id: uuid(82) }), /scope_changed/);
  assert.throws(() => prepareCreationRecord(null, { ...next, title: '   ' }), /invalid_draft/);
});

test('later typing cannot replace a baseline already advanced by confirmed A', () => {
  const a = prepared(); const b = persistFieldRecord(a, draftHandle(a), field('B', 2));
  const saved = ack(b);
  const c = persistFieldRecord(saved, draftHandle(saved), field('C', 3));
  assert.equal(c.fields[key].baseValue, 'A');
});

test('recovered coverage cannot claim a different field or a vanished candidate', () => {
  const row = prepared();
  assert.throws(() => validateDraftRecord({ ...row, fields: {} }), /invalid_draft/);
  const wrong = structuredClone(row); wrong.submission!.request.command = {
    tool: 'jd_set_text', arguments: { target_field_ref: 'unrelated-field', text: 'A', basis_refs: [] },
  };
  assert.throws(() => validateDraftRecord(wrong), /invalid_draft/);
});
