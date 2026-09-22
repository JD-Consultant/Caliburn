import { openDB } from 'idb';
import type { DBSchema, IDBPDatabase } from 'idb';
import { decode, validateChatRequest, validateManualRequest, validateOrigin } from './api.ts';
import type { ManualSaveInput, ManualCommand } from '../../../src/jd_relational/generated/jd-manual-http.ts';
import type { MutationResult } from '../../../src/jd_relational/generated/jd-result.ts';
import type { CatalogCreateInput } from '../../../src/jd_relational/generated/jd-catalog-http.ts';
import type { ChatStartInput, ChatRunState } from '../../../src/jd_relational/generated/jd-chat-http.ts';

export interface DraftScope { apiOrigin: string; datasetId: string; documentId: string }
export interface DraftHandle { scope: DraftScope; draftId: string; ownerEpoch: string }
export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };
export interface FieldDraft {
  itemId: string | null; fieldName: string; fieldRef: string;
  baseValue: string | null; text: string | null; seq: number;
}
export interface FormDraft { key: string; value: JsonValue; seq: number }
export interface DraftSubmission {
  request: ManualSaveInput; submissionGeneration: number;
  coveredFields: Record<string, number>; coveredForms: Record<string, number>;
}
interface DraftBase {
  scope: DraftScope; draftId: string; ownerEpoch: string;
  generation: number; inputSeq: number;
  fields: Record<string, FieldDraft>; forms: Record<string, FormDraft>;
  submission: DraftSubmission | null;
}
export interface LegacyDraftRow extends DraftBase { format: 1 }
export interface ChatDraft { text: string; seq: number }
export interface ChatSubmission { request: ChatStartInput; submissionGeneration: number; coveredSeq: number }
export interface DraftRow extends DraftBase {
  format: 2; chatDraft: ChatDraft | null; chatSubmission: ChatSubmission | null;
}
export type StoredDraftRow = LegacyDraftRow | DraftRow;
export interface PrepareChat { request: ChatStartInput; coveredSeq: number }
export interface ChatSubmissionIdentity { runId: string; submissionGeneration: number }
export interface ChatAcknowledgment extends ChatSubmissionIdentity { state: ChatRunState }
export interface PrepareSubmission {
  request: ManualSaveInput; coveredFields: Record<string, number>; coveredForms: Record<string, number>;
}
export interface SubmissionAcknowledgment {
  operationId: string; submissionGeneration: number; result: MutationResult;
}
export interface RebindField { key: string; seq: number; fieldRef: string; baseValue: string | null }
export class DraftError extends Error {
  readonly code: string;
  constructor(code: string) { super(code); this.name = 'DraftError'; this.code = code; }
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const MAX_BYTES = 4 * 1024 * 1024;
const own = (object: object, key: string) => Object.hasOwn(object, key);
function demand(condition: unknown, code = 'invalid_draft'): asserts condition {
  if (!condition) throw new DraftError(code);
}
function plain(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null);
}
function exact(value: unknown, keys: string[]): asserts value is Record<string, unknown> {
  demand(plain(value) && Object.keys(value).length === keys.length && keys.every(k => own(value, k)));
}
const integer = (value: unknown, min = 0): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= min;
const uuid = (value: unknown): value is string => typeof value === 'string' && UUID.test(value);
const ref = (value: unknown): value is string => typeof value === 'string' && value.length > 0 && value.length <= 4096;
const text = (value: unknown): value is string | null => value === null || typeof value === 'string';
function checkScope(scope: unknown): asserts scope is DraftScope {
  exact(scope, ['apiOrigin', 'datasetId', 'documentId']);
  demand(typeof scope.apiOrigin === 'string' && uuid(scope.datasetId) && uuid(scope.documentId));
  try { validateOrigin(scope.apiOrigin); } catch { throw new DraftError('invalid_draft'); }
}
function checkJson(value: unknown): void {
  let nodes = 0;
  const path = new Set<object>();
  function visit(item: unknown, depth: number): void {
    demand(++nodes <= 10000 && depth <= 24);
    if (item === null || typeof item === 'boolean' || typeof item === 'string') return;
    if (typeof item === 'number') { demand(Number.isFinite(item)); return; }
    demand(Array.isArray(item) || plain(item));
    demand(!path.has(item)); path.add(item);
    demand(Object.getOwnPropertySymbols(item).length === 0);
    if (Array.isArray(item)) {
      demand(Object.keys(item).length === item.length);
      for (const child of item) visit(child, depth + 1);
    } else {
      for (const descriptor of Object.values(Object.getOwnPropertyDescriptors(item))) {
        demand(own(descriptor, 'value') && descriptor.enumerable); visit(descriptor.value, depth + 1);
      }
    }
    path.delete(item);
  }
  visit(value, 0);
  demand(new TextEncoder().encode(JSON.stringify(value)).byteLength <= MAX_BYTES, 'draft_too_large');
}
function checkField(field: unknown): asserts field is FieldDraft {
  exact(field, ['itemId', 'fieldName', 'fieldRef', 'baseValue', 'text', 'seq']);
  demand((field.itemId === null || uuid(field.itemId)) && typeof field.fieldName === 'string'
    && field.fieldName.length > 0 && field.fieldName.length <= 128 && !field.fieldName.includes('\0')
    && ref(field.fieldRef) && text(field.baseValue) && text(field.text) && integer(field.seq, 1));
}
function checkForm(form: unknown): asserts form is FormDraft {
  exact(form, ['key', 'value', 'seq']);
  demand(typeof form.key === 'string' && form.key.length > 0 && form.key.length <= 200
    && !['__proto__', 'prototype', 'constructor'].includes(form.key) && integer(form.seq, 1));
  checkJson(form.value);
}
function checkCoverage(value: unknown): asserts value is Record<string, number> {
  demand(plain(value));
  for (const seq of Object.values(value)) demand(integer(seq, 1));
}
export function fieldKey(itemId: string | null, fieldName: string): string { return JSON.stringify([itemId, fieldName]); }
function sameScope(a: DraftScope, b: DraftScope) {
  return a.apiOrigin === b.apiOrigin && a.datasetId === b.datasetId && a.documentId === b.documentId;
}
export function draftHandle(row: StoredDraftRow): DraftHandle {
  return { scope: { ...row.scope }, draftId: row.draftId, ownerEpoch: row.ownerEpoch };
}
export function validateStoredDraftRecord(value: unknown): StoredDraftRow {
  checkJson(value);
  demand(plain(value));
  const keys = ['format', 'scope', 'draftId', 'ownerEpoch', 'generation', 'inputSeq', 'fields', 'forms', 'submission'];
  exact(value, value.format === 2 ? [...keys, 'chatDraft', 'chatSubmission'] : keys);
  demand((value.format === 1 || value.format === 2) && uuid(value.draftId) && uuid(value.ownerEpoch)
    && integer(value.generation, 1) && integer(value.inputSeq) && plain(value.fields) && plain(value.forms));
  checkScope(value.scope);
  const inputSeq = value.inputSeq;
  for (const [key, field] of Object.entries(value.fields)) {
    checkField(field); demand(key === fieldKey(field.itemId, field.fieldName) && field.seq <= value.inputSeq);
  }
  for (const [key, form] of Object.entries(value.forms)) {
    checkForm(form); demand(key === form.key && form.seq <= value.inputSeq);
  }
  if (value.submission !== null) {
    const s = value.submission;
    exact(s, ['request', 'submissionGeneration', 'coveredFields', 'coveredForms']);
    demand(integer(s.submissionGeneration, 1) && s.submissionGeneration <= value.generation);
    checkCoverage(s.coveredFields); checkCoverage(s.coveredForms);
    demand([...Object.values(s.coveredFields), ...Object.values(s.coveredForms)].every(seq => seq <= inputSeq));
    try { validateManualRequest(s.request); } catch { throw new DraftError('invalid_draft'); }
    demand(new TextEncoder().encode(JSON.stringify(s.request)).byteLength <= 1024 * 1024, 'draft_too_large');
    for (const [key, seq] of Object.entries(s.coveredFields)) {
      demand(own(value.fields, key)); const field = value.fields[key] as FieldDraft;
      demand(field.seq >= seq);
    }
    for (const [key, seq] of Object.entries(s.coveredForms)) {
      demand(own(value.forms, key)); const form = value.forms[key] as FormDraft;
      demand(form.seq >= seq);
    }
    if (s.request.command.tool === 'jd_set_text') {
      const keys = Object.keys(s.coveredFields);
      demand(keys.length === 1 && Object.keys(s.coveredForms).length === 0);
      const field = value.fields[keys[0]] as FieldDraft;
      demand(field.fieldRef === s.request.command.arguments.target_field_ref);
      if (field.seq === s.coveredFields[keys[0]]) demand(field.text === s.request.command.arguments.text);
    }
  }
  if (value.format === 2) {
    if (value.chatDraft !== null) {
      checkChatDraft(value.chatDraft); demand(value.chatDraft.seq <= inputSeq);
    }
    if (value.chatSubmission !== null) {
      const s = value.chatSubmission;
      exact(s, ['request', 'submissionGeneration', 'coveredSeq']);
      demand(integer(s.submissionGeneration, 1) && s.submissionGeneration <= value.generation
        && integer(s.coveredSeq, 1) && s.coveredSeq <= inputSeq);
      checkChatRequest(s.request);
      demand(value.submission === null && Object.keys(value.fields).length === 0 && Object.keys(value.forms).length === 0);
      demand(value.chatDraft === null || value.chatDraft.seq > s.coveredSeq);
    }
  }
  return value as unknown as StoredDraftRow;
}
export function validateDraftRecord(value: unknown): DraftRow {
  const row = validateStoredDraftRecord(value); demand(row.format === 2); return row;
}
function checkChatDraft(value: unknown): asserts value is ChatDraft {
  exact(value, ['text', 'seq']); demand(typeof value.text === 'string' && integer(value.seq, 1));
}
function checkChatRequest(value: unknown): asserts value is ChatStartInput {
  try { validateChatRequest(value); } catch { throw new DraftError('invalid_draft'); }
  demand(new TextEncoder().encode(JSON.stringify(value)).byteLength <= 1024 * 1024, 'draft_too_large');
}
function owned(row: DraftRow, handle: DraftHandle): void {
  validateDraftRecord(row); checkScope(handle.scope);
  demand(sameScope(row.scope, handle.scope), 'scope_changed');
  demand(row.draftId === handle.draftId && row.ownerEpoch === handle.ownerEpoch, 'owner_changed');
}
function changed(row: DraftRow): DraftRow {
  row.generation += 1; validateDraftRecord(row); return row;
}

// Bounded immutable transitions are also tested without claiming a mock is a browser.
export function claimDraftRecord(previous: StoredDraftRow | null, scope: DraftScope, ownerEpoch: string, newDraftId: string): DraftRow {
  checkScope(scope); demand(uuid(ownerEpoch) && uuid(newDraftId));
  if (previous !== null) {
    validateStoredDraftRecord(previous); demand(sameScope(previous.scope, scope), 'scope_changed');
    // Only claim under the document Web Lock upgrades one validated row; reads do not rewrite legacy data.
    const next: DraftRow = previous.format === 1
      ? { ...structuredClone(previous), format: 2, chatDraft: null, chatSubmission: null, ownerEpoch }
      : { ...structuredClone(previous), ownerEpoch };
    return changed(next);
  }
  return validateDraftRecord({ format: 2, scope: { ...scope }, draftId: newDraftId, ownerEpoch,
    generation: 1, inputSeq: 0, fields: {}, forms: {}, submission: null, chatDraft: null, chatSubmission: null });
}
export function persistFieldRecord(row: DraftRow, handle: DraftHandle, field: FieldDraft): DraftRow {
  owned(row, handle); checkField(field);
  demand(row.chatSubmission === null, 'chat_submission_pending');
  const key = fieldKey(field.itemId, field.fieldName);
  demand(!own(row.fields, key) || field.seq > row.fields[key].seq, 'input_changed');
  const next = structuredClone(row); next.fields[key] = structuredClone(field);
  if (own(row.fields, key)) {
    next.fields[key].baseValue = row.fields[key].baseValue;
    next.fields[key].fieldRef = row.fields[key].fieldRef;
  }
  next.inputSeq = Math.max(next.inputSeq, field.seq); return changed(next);
}
export function persistFormRecord(row: DraftRow, handle: DraftHandle, form: FormDraft): DraftRow {
  owned(row, handle); checkForm(form);
  demand(row.chatSubmission === null, 'chat_submission_pending');
  demand(!own(row.forms, form.key) || form.seq > row.forms[form.key].seq, 'input_changed');
  const next = structuredClone(row); next.forms[form.key] = structuredClone(form);
  next.inputSeq = Math.max(next.inputSeq, form.seq); return changed(next);
}
export function prepareSubmissionRecord(row: DraftRow, handle: DraftHandle, input: PrepareSubmission): DraftRow {
  owned(row, handle); demand(row.submission === null, 'submission_pending');
  demand(row.chatSubmission === null, 'chat_submission_pending');
  checkCoverage(input.coveredFields); checkCoverage(input.coveredForms);
  try { validateManualRequest(input.request); } catch { throw new DraftError('invalid_draft'); }
  for (const [key, seq] of Object.entries(input.coveredFields)) demand(own(row.fields, key) && row.fields[key].seq === seq, 'input_changed');
  for (const [key, seq] of Object.entries(input.coveredForms)) demand(own(row.forms, key) && row.forms[key].seq === seq, 'input_changed');
  // An ordinary one-field write cannot claim other fields or forms were submitted.
  if (input.request.command.tool === 'jd_set_text') {
    const entries = Object.keys(input.coveredFields);
    demand(entries.length === 1 && Object.keys(input.coveredForms).length === 0, 'invalid_coverage');
    const field = row.fields[entries[0]], args = input.request.command.arguments;
    demand(field.fieldRef === args.target_field_ref && field.text === args.text, 'invalid_coverage');
  }
  const next = structuredClone(row);
  next.submission = { ...structuredClone(input), submissionGeneration: next.generation + 1 };
  return changed(next);
}
export function acknowledgeSubmissionRecord(row: DraftRow, handle: DraftHandle, input: SubmissionAcknowledgment): DraftRow {
  owned(row, handle);
  const submission = row.submission;
  demand(submission && submission.request.operation_id === input.operationId
    && submission.submissionGeneration === input.submissionGeneration, 'submission_changed');
  const result = decode<MutationResult>('result', 'MutationResult', input.result);
  demand(result.receipt_durability === 'confirmed', 'result_unconfirmed');
  const next = structuredClone(row);
  if (result.status === 'committed' || result.status === 'no_change') {
    for (const [key, seq] of Object.entries(submission.coveredFields)) {
      if (!own(next.fields, key)) continue;
      if (next.fields[key].seq <= seq) delete next.fields[key];
      else if (submission.request.command.tool === 'jd_set_text') {
        next.fields[key].baseValue = submission.request.command.arguments.text;
      }
    }
    for (const [key, seq] of Object.entries(submission.coveredForms)) {
      if (own(next.forms, key) && next.forms[key].seq <= seq) delete next.forms[key];
    }
  }
  // Confirmed rejection retains candidates; caller follows the receipt's next_action.
  next.submission = null; return changed(next);
}
export function rebindFieldRecord(row: DraftRow, handle: DraftHandle, input: RebindField): DraftRow {
  owned(row, handle); demand(row.submission === null, 'submission_pending');
  demand(own(row.fields, input.key) && row.fields[input.key].seq === input.seq, 'input_changed');
  demand(ref(input.fieldRef) && text(input.baseValue));
  const next = structuredClone(row);
  next.fields[input.key].fieldRef = input.fieldRef; next.fields[input.key].baseValue = input.baseValue;
  return changed(next);
}

export function persistChatRecord(row: DraftRow, handle: DraftHandle, input: ChatDraft): DraftRow {
  owned(row, handle); checkChatDraft(input);
  demand(input.seq > row.inputSeq, 'input_changed');
  const next = structuredClone(row); next.chatDraft = structuredClone(input); next.inputSeq = input.seq;
  return changed(next);
}
export function prepareChatRecord(row: DraftRow, handle: DraftHandle, input: PrepareChat): DraftRow {
  owned(row, handle); exact(input, ['request', 'coveredSeq']); checkChatRequest(input.request);
  demand(row.chatSubmission === null, 'chat_submission_pending');
  demand(row.submission === null && Object.keys(row.fields).length === 0 && Object.keys(row.forms).length === 0, 'manual_pending');
  demand(integer(input.coveredSeq, 1) && row.chatDraft !== null && row.chatDraft.seq === input.coveredSeq
    && row.chatDraft.text === input.request.text, 'input_changed');
  const next = structuredClone(row);
  next.chatSubmission = { ...structuredClone(input), submissionGeneration: next.generation + 1 };
  // The complete original text is now held by the immutable request, before any POST.
  next.chatDraft = null; return changed(next);
}
function matchingChat(row: DraftRow, handle: DraftHandle, input: ChatSubmissionIdentity): void {
  owned(row, handle);
  demand(uuid(input.runId) && integer(input.submissionGeneration, 1));
  demand(row.chatSubmission !== null && row.chatSubmission.request.run_id === input.runId
    && row.chatSubmission.submissionGeneration === input.submissionGeneration, 'submission_changed');
}
function chatAcknowledgment(row: DraftRow, handle: DraftHandle, input: ChatAcknowledgment): ChatRunState {
  exact(input, ['runId', 'submissionGeneration', 'state']); matchingChat(row, handle, input);
  let state: ChatRunState;
  try { state = decode<ChatRunState>('chat-http', 'ChatRunState', input.state); }
  catch { throw new DraftError('invalid_draft'); }
  demand(state.dataset_id === row.scope.datasetId && state.document_id === row.scope.documentId
    && state.run_id === input.runId, 'scope_changed');
  demand(['completed', 'failed', 'cancelled'].includes(state.run_status) && state.jd_effects.state === 'settled', 'result_unconfirmed');
  return state;
}
export function acknowledgeChatRecord(row: DraftRow, handle: DraftHandle, input: ChatAcknowledgment): DraftRow {
  const state = chatAcknowledgment(row, handle, input);
  demand(state.input_state === 'saved', 'result_unconfirmed');
  const next = structuredClone(row); next.chatSubmission = null; return changed(next);
}
export function restoreChatRecord(row: DraftRow, handle: DraftHandle, input: ChatAcknowledgment): DraftRow {
  // Explicit controller action, with the original App's known-not-saved result. Unknown/timeout is never proof.
  const state = chatAcknowledgment(row, handle, input);
  demand(state.input_state === 'not_saved', 'result_unconfirmed');
  return takeOriginalChatBack(row);
}
function takeOriginalChatBack(row: DraftRow): DraftRow {
  demand(row.chatDraft === null || row.chatDraft.text === '', 'input_changed');
  const next = structuredClone(row); next.inputSeq += 1;
  next.chatDraft = { text: row.chatSubmission!.request.text, seq: next.inputSeq };
  next.chatSubmission = null; return changed(next);
}
export function rejectUnavailableChatRecord(row: DraftRow, handle: DraftHandle, input: ChatSubmissionIdentity): DraftRow {
  // ONLY the original start POST's validated ai_unavailable response proves this pre-admission rejection.
  // The controller must never use this for GET not_found, timeout, or other errors; no run state is fabricated.
  exact(input, ['runId', 'submissionGeneration']); matchingChat(row, handle, input);
  return takeOriginalChatBack(row);
}

interface DraftDatabase extends DBSchema {
  drafts: { key: [string, string, string]; value: StoredDraftRow; indexes: { document: [string, string] } };
  creations: { key: string; value: CatalogCreateInput };
}
const dbKey = (scope: DraftScope): [string, string, string] => [scope.apiOrigin, scope.datasetId, scope.documentId];
export interface DraftStoreOptions {
  name?: string; blocked?: () => void; blocking?: () => void; terminated?: () => void;
}
export class DraftStore {
  private readonly db: IDBPDatabase<DraftDatabase>;
  constructor(db: IDBPDatabase<DraftDatabase>) { this.db = db; }
  close(): void { this.db.close(); }
  async read(scope: DraftScope): Promise<StoredDraftRow | null> {
    checkScope(scope);
    try { const row = await this.db.get('drafts', dbKey(scope)); return row === undefined ? null : validateStoredDraftRecord(row); }
    catch (error) { if (error instanceof DraftError) throw error; throw new DraftError('storage_unavailable'); }
  }
  async listForDocument(apiOrigin: string, documentId: string): Promise<StoredDraftRow[]> {
    validateOrigin(apiOrigin); demand(uuid(documentId));
    try { return (await this.db.getAllFromIndex('drafts', 'document', [apiOrigin, documentId])).map(validateStoredDraftRecord); }
    catch (error) { if (error instanceof DraftError) throw error; throw new DraftError('storage_unavailable'); }
  }
  private async update(scope: DraftScope, transform: (row: StoredDraftRow | null) => DraftRow): Promise<DraftRow> {
    checkScope(scope);
    const tx = this.db.transaction('drafts', 'readwrite', { durability: 'strict' });
    try {
      const old = await tx.store.get(dbKey(scope));
      const next = transform(old === undefined ? null : validateStoredDraftRecord(old));
      await Promise.all([tx.store.put(next, dbKey(scope)), tx.done]);
      return next;
    } catch (error) {
      try { tx.abort(); } catch { /* already completed or aborted */ }
      await tx.done.catch(() => undefined);
      if (error instanceof DraftError) throw error;
      throw new DraftError('storage_unavailable');
    }
  }
  // Caller must already hold the matching native Web Lock until all its work drains.
  claim(scope: DraftScope, ownerEpoch: string): Promise<DraftRow> {
    const newDraftId = crypto.randomUUID();
    return this.update(scope, row => claimDraftRecord(row, scope, ownerEpoch, newDraftId));
  }
  private current(row: StoredDraftRow | null): DraftRow { demand(row?.format === 2, 'owner_changed'); return row; }
  persistField(handle: DraftHandle, field: FieldDraft): Promise<DraftRow> {
    return this.update(handle.scope, row => persistFieldRecord(this.current(row), handle, field));
  }
  persistForm(handle: DraftHandle, form: FormDraft): Promise<DraftRow> {
    return this.update(handle.scope, row => persistFormRecord(this.current(row), handle, form));
  }
  persistChat(handle: DraftHandle, input: ChatDraft): Promise<DraftRow> {
    return this.update(handle.scope, row => persistChatRecord(this.current(row), handle, input));
  }
  prepareChat(handle: DraftHandle, input: PrepareChat): Promise<DraftRow> {
    return this.update(handle.scope, row => prepareChatRecord(this.current(row), handle, input));
  }
  acknowledgeChat(handle: DraftHandle, input: ChatAcknowledgment): Promise<DraftRow> {
    return this.update(handle.scope, row => acknowledgeChatRecord(this.current(row), handle, input));
  }
  restoreChat(handle: DraftHandle, input: ChatAcknowledgment): Promise<DraftRow> {
    return this.update(handle.scope, row => restoreChatRecord(this.current(row), handle, input));
  }
  rejectUnavailableChat(handle: DraftHandle, input: ChatSubmissionIdentity): Promise<DraftRow> {
    return this.update(handle.scope, row => rejectUnavailableChatRecord(this.current(row), handle, input));
  }
  prepareSubmission(handle: DraftHandle, input: PrepareSubmission): Promise<DraftRow> {
    return this.update(handle.scope, row => prepareSubmissionRecord(this.current(row), handle, input));
  }
  acknowledgeSubmission(handle: DraftHandle, input: SubmissionAcknowledgment,
    settleEditorForm?: (value: JsonValue, command: ManualCommand) => JsonValue): Promise<DraftRow> {
    return this.update(handle.scope, row => {
      const original = this.current(row);
      const next = acknowledgeSubmissionRecord(original, handle, input);
      if (settleEditorForm && (input.result.status === 'committed' || input.result.status === 'no_change')
          && next.forms.editor && !own(original.submission!.coveredForms, 'editor')) {
        const value = settleEditorForm(next.forms.editor.value, original.submission!.request.command);
        if (JSON.stringify(value) !== JSON.stringify(next.forms.editor.value)) {
          next.inputSeq += 1; next.forms.editor = { key: 'editor', value, seq: next.inputSeq };
          validateDraftRecord(next);
        }
      }
      return next;
    });
  }
  rebindField(handle: DraftHandle, input: RebindField): Promise<DraftRow> {
    return this.update(handle.scope, row => rebindFieldRecord(this.current(row), handle, input));
  }
  discardField(handle: DraftHandle, key: string, seq: number): Promise<DraftRow> {
    return this.update(handle.scope, row => {
      row = this.current(row); owned(row, handle); demand(row.submission === null, 'submission_pending');
      demand(own(row.fields, key) && row.fields[key].seq === seq, 'input_changed');
      const next = structuredClone(row); delete next.fields[key]; return changed(next);
    });
  }
  discardForm(handle: DraftHandle, key: string, seq: number): Promise<DraftRow> {
    return this.update(handle.scope, row => {
      row = this.current(row); owned(row, handle); demand(row.submission === null, 'submission_pending');
      demand(own(row.forms, key) && row.forms[key].seq === seq, 'input_changed');
      const next = structuredClone(row); delete next.forms[key]; return changed(next);
    });
  }
  async readCreation(apiOrigin: string, datasetId: string): Promise<CatalogCreateInput | null> {
    const key = creationKey(apiOrigin, datasetId);
    try {
      const old = await this.db.get('creations', key);
      return old ? validateCreation(old, datasetId) : null;
    } catch (error) { if (error instanceof DraftError) throw error; throw new DraftError('storage_unavailable'); }
  }
  async storeCreation(apiOrigin: string, input: CatalogCreateInput): Promise<CatalogCreateInput> {
    const candidate = validateCreation(input, input.dataset_id);
    const key = creationKey(apiOrigin, candidate.dataset_id);
    const tx = this.db.transaction('creations', 'readwrite', { durability: 'strict' });
    try {
      const old = await tx.store.get(key);
      const next = prepareCreationRecord(old ?? null, candidate);
      await Promise.all([tx.store.put(next, key), tx.done]); return next;
    } catch (error) {
      try { tx.abort(); } catch { /* already completed or aborted */ }
      await tx.done.catch(() => undefined);
      if (error instanceof DraftError) throw error;
      throw new DraftError('storage_unavailable');
    }
  }
  async clearCreation(apiOrigin: string, datasetId: string, requestKey: string): Promise<boolean> {
    const key = creationKey(apiOrigin, datasetId); demand(uuid(requestKey));
    const tx = this.db.transaction('creations', 'readwrite', { durability: 'strict' });
    try {
      const old = await tx.store.get(key);
      const matches = old !== undefined && validateCreation(old, datasetId).request_key === requestKey;
      if (matches) await tx.store.delete(key);
      await tx.done; return matches;
    } catch (error) {
      try { tx.abort(); } catch { /* already completed or aborted */ }
      await tx.done.catch(() => undefined);
      if (error instanceof DraftError) throw error;
      throw new DraftError('storage_unavailable');
    }
  }
}
function creationKey(apiOrigin: string, datasetId: string): string {
  validateOrigin(apiOrigin); demand(uuid(datasetId)); return JSON.stringify([apiOrigin, datasetId]);
}
function validateCreation(input: unknown, datasetId: string): CatalogCreateInput {
  checkJson(input);
  let value: CatalogCreateInput;
  try { value = decode<CatalogCreateInput>('catalog-http', 'CatalogCreateInput', input); }
  catch { throw new DraftError('invalid_draft'); }
  demand(value.dataset_id === datasetId, 'scope_changed');
  demand(new TextEncoder().encode(JSON.stringify(value)).byteLength <= 1024 * 1024, 'draft_too_large');
  return structuredClone(value);
}
export function prepareCreationRecord(previous: CatalogCreateInput | null, input: CatalogCreateInput): CatalogCreateInput {
  const next = validateCreation(input, input.dataset_id);
  if (previous) {
    const old = validateCreation(previous, next.dataset_id);
    demand(old.request_key === next.request_key && old.title === next.title, 'creation_pending');
    return old;
  }
  return next;
}
export const readCreation = (store: DraftStore, apiOrigin: string, datasetId: string) => store.readCreation(apiOrigin, datasetId);
export const storeCreation = (store: DraftStore, apiOrigin: string, input: CatalogCreateInput) => store.storeCreation(apiOrigin, input);
export const clearCreation = (store: DraftStore, apiOrigin: string, datasetId: string, requestKey: string) => store.clearCreation(apiOrigin, datasetId, requestKey);
export async function openDraftStore(options: DraftStoreOptions = {}): Promise<DraftStore> {
  try {
    const db = await openDB<DraftDatabase>(options.name ?? 'caliburn-jd-browser-drafts', 2, {
      upgrade(database, oldVersion) {
        if (oldVersion < 1) {
          const store = database.createObjectStore('drafts'); store.createIndex('document', ['scope.apiOrigin', 'scope.documentId']);
          database.createObjectStore('creations');
        }
        // Version 2 fences old connections; rows are validated/upgraded only by claim, never cleared in bulk.
      },
      blocked() { options.blocked?.(); },
      blocking() { db.close(); options.blocking?.(); },
      terminated() { options.terminated?.(); },
    });
    return new DraftStore(db);
  } catch { throw new DraftError('storage_unavailable'); }
}
