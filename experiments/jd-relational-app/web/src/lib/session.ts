import { ApiError, JdApi } from './api.ts';
import { openDraftStore, draftHandle } from './drafts.ts';
import type { DraftHandle, DraftRow, DraftStore, DraftSubmission, JsonValue, FieldDraft } from './drafts.ts';
import { projectView } from './view.ts';
import { settleItemForm } from './item-form.ts';
import type { JdView, FieldView } from './view.ts';
import type { ManualCommand, ManualDocumentState } from '../../../src/jd_relational/generated/jd-manual-http.ts';
import type { MutationResult } from '../../../src/jd_relational/generated/jd-result.ts';

export interface SessionSnapshot {
  view: JdView | null; values: Record<string, string>; form: JsonValue | null;
  row: DraftRow | null; loading: boolean; readOnly: boolean; submitting: boolean;
  needsReview: boolean; dirty: boolean; error: string; status: string;
  recoveryFields: Record<string, FieldDraft>;
}
export const emptySession: SessionSnapshot = { view: null, values: {}, form: null, row: null,
  loading: true, readOnly: true, submitting: false, needsReview: false, dirty: false, error: '', status: '讀取中', recoveryFields: {} };
const explain = (error: unknown) => error instanceof ApiError ? error.message :
  '本機暫存或操作未完成，內容仍保留在畫面中。請先查看狀態。';

/** One document's browser handoff. Business decisions are made by the common API. */
export class JdSession {
  private api: JdApi; private id: string; private notify: (snapshot: SessionSnapshot) => void;
  private view: JdView | null = null; private row: DraftRow | null = null;
  private store: DraftStore | null = null; private handle: DraftHandle | null = null;
  private writable = false; private disposed = false; private loading = true;
  private review = false; private error = ''; private composing = false; private seq = 0;
  private input = new Map<string, { field: FieldView; text: string; seq: number }>();
  private pendingForm: { value: JsonValue | null; seq: number } | null = null;
  private openStore: typeof openDraftStore; private locks: Pick<LockManager, 'request'> | undefined;
  private local: Promise<void> = Promise.resolve(); private flight: Promise<void> | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null; private release: (() => void) | null = null;
  private state: ManualDocumentState | null = null;
  constructor(api: JdApi, id: string, notify: (snapshot: SessionSnapshot) => void,
    options: { openStore?: typeof openDraftStore; locks?: Pick<LockManager, 'request'> } = {}) {
    this.api = api; this.id = id; this.notify = notify;
    this.openStore = options.openStore ?? openDraftStore; this.locks = options.locks ?? globalThis.navigator?.locks;
  }
  private emit() {
    if (this.disposed) return;
    const values: Record<string, string> = {};
    if (!this.review) for (const [key, field] of Object.entries(this.row?.fields ?? {})) values[key] = field.text ?? '';
    const recoveryFields = { ...this.row?.fields };
    for (const [key, candidate] of this.input) {
      if (!this.review) values[key] = candidate.text;
      const field = candidate.field;
      recoveryFields[key] = { itemId: field.itemId, fieldName: field.name, fieldRef: field.field_ref,
        baseValue: this.row?.fields[key]?.baseValue ?? field.value, text: candidate.text, seq: candidate.seq };
    }
    const dirty = !!this.input.size || !!this.pendingForm || !!this.row?.submission || !!Object.keys(this.row?.fields ?? {}).length
      || !!Object.keys(this.row?.forms ?? {}).length;
    this.notify({ view: this.view, values, recoveryFields, row: this.row, form: this.review && !this.pendingForm ? null :
      this.pendingForm ? this.pendingForm.value : this.row?.forms.editor?.value ?? null,
      loading: this.loading, readOnly: !this.writable || this.review || this.state?.write_blocked !== false,
      submitting: !!this.flight, needsReview: this.review, dirty,
      error: this.error, status: this.row?.submission ? (this.flight ? '保存中' : '保存結果待確認') :
        this.review ? '找回內容，待確認' : dirty ? '尚未保存' : !this.writable ? '唯讀' : '已保存' });
  }
  private async queue(work: () => Promise<void>): Promise<void> {
    const current = this.local.then(work);
    this.local = current.catch(error => { this.error = explain(error); this.review = true; this.emit(); });
    return current;
  }
  async start() {
    try {
      const [page, state] = await Promise.all([this.api.read(this.id), this.api.state(this.id)]);
      if (this.disposed) return;
      this.view = projectView(page); this.state = state;
      if (!this.locks) throw new ApiError('browser_unsupported', '此瀏覽器不支援編輯保護，請使用新版 Chrome 或 Edge。');
      // Holding a native lock has no expiry/stealing timer. Second tab is read-only.
      void this.locks.request(JSON.stringify(['jd-document', this.api.origin, this.api.datasetId, this.id]), { ifAvailable: true }, async lock => {
        if (this.disposed) return;
        if (!lock) { this.error = '另一個分頁正在編輯這份文件。關閉該分頁後可重新開啟此文件。'; this.loading = false; this.emit(); return; }
        try {
          const storageClosed = () => { this.writable = false; this.error = '瀏覽器暫存已中斷或正在更新，請保留畫面內容。'; this.emit(); };
          this.store = await this.openStore({ terminated: storageClosed, blocking: storageClosed });
          if (this.disposed) { this.store.close(); return; }
          this.row = await this.store.claim({ apiOrigin: this.api.origin, datasetId: this.api.datasetId!, documentId: this.id }, crypto.randomUUID());
          this.handle = draftHandle(this.row); this.seq = this.row.inputSeq;
          this.review = !!this.row.submission || !!Object.keys(this.row.fields).length || !!Object.keys(this.row.forms).length;
          this.writable = true; this.loading = false; this.emit();
          if (this.disposed) return;
          await new Promise<void>(resolve => { this.release = resolve; });
          await this.flight?.catch(() => undefined); await this.local;
        } catch (error) { this.error = explain(error); this.loading = false; this.writable = false; this.emit(); }
        finally { this.store?.close(); }
      }).catch(error => { this.error = explain(error); this.loading = false; this.emit(); });
    } catch (error) { this.error = explain(error); this.loading = false; this.emit(); }
  }
  async dispose() {
    this.disposed = true; if (this.timer) clearTimeout(this.timer);
    this.release?.();
  }
  composition(active: boolean) { this.composing = active; if (active && this.timer) clearTimeout(this.timer); if (!active) this.schedule(); }
  edit(field: FieldView, text: string) {
    if (!this.writable || this.review || this.disposed || this.state?.write_blocked !== false) return;
    const seq = ++this.seq; this.input.set(field.key, { field, text, seq }); this.emit();
    void this.queue(async () => {
      const current = this.row?.fields[field.key];
      const actual = this.view?.fields.find(item => item.key === field.key);
      if (!actual) throw new ApiError('target_missing', '這個欄位已變更，請先比較找回的內容。');
      this.row = await this.store!.persistField(this.handle!, { itemId: field.itemId, fieldName: field.name,
        fieldRef: current?.fieldRef ?? actual.field_ref, baseValue: current ? current.baseValue : actual.value, text, seq });
      if (this.input.get(field.key)?.seq === seq) this.input.delete(field.key);
      this.emit();
    }).then(() => this.schedule()).catch(() => undefined);
  }
  form(value: JsonValue | null) {
    if (!this.writable || this.review || this.flight || this.disposed || this.state?.write_blocked !== false) return;
    const seq = ++this.seq;
    this.pendingForm = { value, seq }; this.emit();
    void this.queue(async () => {
      if (value === null) {
        const prior = this.row?.forms.editor;
        if (prior) this.row = await this.store!.discardForm(this.handle!, 'editor', prior.seq);
      } else this.row = await this.store!.persistForm(this.handle!, { key: 'editor', value, seq });
      if (this.pendingForm?.seq === seq) this.pendingForm = null;
      this.emit();
    }).catch(() => undefined);
  }
  private schedule() {
    if (this.timer) clearTimeout(this.timer);
    if (this.disposed || this.composing || this.review || this.row?.submission || this.flight || !this.writable
      || this.state?.write_blocked !== false || (!this.input.size && !Object.keys(this.row?.fields ?? {}).length)) return;
    this.timer = setTimeout(() => { void this.flush().catch(() => undefined); }, 800);
  }
  private async fresh() { const [page, state] = await Promise.all([this.api.read(this.id), this.api.state(this.id)]); return { view: projectView(page), state }; }
  private async received(submission: DraftSubmission, result: MutationResult) {
    if (result.receipt_durability !== 'confirmed') {
      this.error = result.error?.message ?? '保存結果尚未確認。請使用原操作查回。'; this.review = true; this.emit(); return;
    }
    // Read first: losing this response leaves the original submission recoverable.
    const [next, saved] = await Promise.all([this.fresh(), result.result_revision_ref === null ? Promise.resolve(null) :
      this.api.read(this.id, { view: 'history', target_ref: result.result_revision_ref, cursor: null })]);
    await this.queue(async () => {
      this.row = await this.store!.acknowledgeSubmission(this.handle!, { operationId: submission.request.operation_id,
        submissionGeneration: submission.submissionGeneration, result }, (value, command) => {
          const settled = settleItemForm(value, command);
          // The one independent K/S insert cannot change the preserved task.
          // Advance only the form built against this original operation's base.
          if (settled !== value && settled && typeof settled === 'object' && !Array.isArray(settled)
              && settled.baseRevisionRef === submission.request.base_revision_ref && saved)
            return { ...settled, baseRevisionRef: saved.revision_ref };
          return settled;
        });
      this.seq = Math.max(this.seq, this.row.inputSeq);
      this.view = next.view; this.state = next.state;
      if (result.status !== 'committed' && result.status !== 'no_change') {
        this.review = true; this.error = result.error.message; this.emit(); return;
      }
      this.review = this.review && (!!Object.keys(this.row.fields).length || !!Object.keys(this.row.forms).length);
      this.error = '';
      if (next.state.write_blocked) { this.review = true; this.error = '服務目前暫停編輯，後續輸入已保留。請稍後重新查看狀態。'; }
      // Observation and history refs intentionally differ; the server normalizes
      // the issued saved-result ref by reading its immutable historical revision.
      if (next.view.revisionRef !== saved?.revision_ref) {
        this.review = true; this.error = '保存後文件又有改動，請比較尚未保存的內容。'; this.emit(); return;
      }
      // Only the just-confirmed own result can advance an unsent field automatically.
      for (const [key, field] of Object.entries(this.row.fields)) {
        const actual = next.view.fields.find(item => item.key === key);
        if (!actual || actual.value !== field.baseValue) { this.review = true; this.error = '欄位內容已變更，請比較後再繼續。'; break; }
        this.row = await this.store!.rebindField(this.handle!, { key, seq: field.seq, fieldRef: actual.field_ref, baseValue: actual.value });
      }
      this.emit();
    });
  }
  private async submit(command: ManualCommand, coveredFields: Record<string, number>, coveredForms: Record<string, number>) {
    let submission: DraftSubmission;
    await this.queue(async () => {
      this.row = await this.store!.prepareSubmission(this.handle!, { request: { operation_id: crypto.randomUUID(),
        base_revision_ref: this.view!.revisionRef, command }, coveredFields, coveredForms });
      submission = this.row.submission!; this.emit();
    });
    try { await this.received(submission!, await this.api.save(this.id, submission!.request)); }
    catch (error) { this.error = explain(error); this.review = true; }
  }
  async flush(): Promise<void> {
    if (this.flight) return this.flight;
    if (this.disposed || this.review || this.composing || !this.writable || this.state?.write_blocked !== false) return;
    const work = async () => {
      await this.local;
      while (!this.disposed && !this.review && !this.composing && !this.row?.submission && this.state?.write_blocked === false) {
        const first = Object.entries(this.row?.fields ?? {}).sort((a, b) => a[1].seq - b[1].seq)[0];
        if (!first) break;
        const [key, field] = first;
        await this.submit({ tool: 'jd_set_text', arguments: { target_field_ref: field.fieldRef, text: field.text, basis_refs: [] } }, { [key]: field.seq }, {});
      }
    };
    this.flight = work(); this.emit();
    try { await this.flight; } finally { this.flight = null; this.emit(); this.schedule(); }
  }
  async command(command: ManualCommand, options: { preserveForm?: boolean } = {}): Promise<void> {
    if (this.disposed || this.review || !this.writable || this.composing || this.state?.write_blocked !== false) throw new ApiError('not_ready', '請先處理尚未保存的內容。');
    if (this.flight || this.input.size || Object.keys(this.row?.fields ?? {}).length) throw new ApiError('not_ready', '文字正在保存，請保存完成後再操作。');
    await this.local;
    if (this.row?.submission || this.review || Object.keys(this.row?.fields ?? {}).length)
      throw new ApiError('not_ready', '請先確認文字保存結果，再完成這項操作。');
    // Commands in the open form refer to the displayed revision; never rewrite refs.
    const coveredForms: Record<string, number> = !options.preserveForm && this.row?.forms.editor ? { editor: this.row.forms.editor.seq } : {};
    this.flight = this.submit(command, {}, coveredForms); this.emit();
    try { await this.flight; } finally { this.flight = null; this.emit(); }
    if (this.review || this.row?.submission) throw new ApiError('not_completed', this.error || '請先確認這次操作的結果。');
  }
  async reconcile(retry = false) {
    if (this.flight || !this.row?.submission || !this.writable) return;
    const submission = this.row.submission;
    this.flight = (async () => {
      try {
        const observed = await this.api.operation(this.id, submission.request.operation_id);
        this.state = observed.write_state;
        if (observed.presence === 'observed') await this.received(submission, observed.result);
        else if (retry) {
          const result = observed.presence === 'pending'
            ? (await this.api.operation(this.id, submission.request.operation_id, true)).result
            : await this.api.save(this.id, submission.request);
          if (result) await this.received(submission, result);
        } else this.error = '原保存尚未取得確定結果，可繼續同一次操作。';
      } catch (error) { this.error = explain(error); }
    })(); this.emit();
    try { await this.flight; } finally { this.flight = null; this.emit(); }
  }
  async resume(discard: boolean) {
    if (!this.writable || this.flight || this.row?.submission) return;
    try {
      const next = await this.fresh();
      if (next.state.write_blocked && !discard) throw new ApiError('busy', '目前仍暫停編輯，請稍後再試；輸入繼續保留。');
      await this.queue(async () => {
        if (!discard) for (const [key, candidate] of this.input) {
          const actual = next.view.fields.find(item => item.key === key);
          if (!actual) throw new ApiError('target_missing', '原欄位已移除，請先複製保留輸入內容。');
          this.row = await this.store!.persistField(this.handle!, { itemId: actual.itemId, fieldName: actual.name,
            fieldRef: actual.field_ref, baseValue: actual.value, text: candidate.text, seq: candidate.seq });
          if (this.input.get(key)?.seq === candidate.seq) this.input.delete(key);
        }
        if (!discard && this.pendingForm?.value !== null && this.pendingForm) {
          const candidate = this.pendingForm;
          this.row = await this.store!.persistForm(this.handle!, { key: 'editor', value: candidate.value, seq: candidate.seq });
          if (this.pendingForm?.seq === candidate.seq) this.pendingForm = null;
        }
        for (const [key, field] of Object.entries(this.row!.fields)) {
          if (discard) this.row = await this.store!.discardField(this.handle!, key, field.seq);
          else {
            const actual = next.view.fields.find(item => item.key === key);
            if (!actual) throw new ApiError('target_missing', '原項目已不存在，請先複製保留需要的文字，再捨棄這份找回內容。');
            this.row = await this.store!.rebindField(this.handle!, { key, seq: field.seq, fieldRef: actual.field_ref, baseValue: actual.value });
          }
        }
        if (discard) for (const [key, form] of Object.entries(this.row!.forms)) this.row = await this.store!.discardForm(this.handle!, key, form.seq);
        this.input.clear(); this.pendingForm = null;
        this.view = next.view; this.state = next.state; this.review = false; this.error = ''; this.emit();
      });
      this.schedule();
    } catch (error) { this.error = explain(error); this.review = true; this.emit(); }
  }
  async refreshStatus() {
    if (this.flight || this.disposed) return;
    if (this.row?.submission) return this.reconcile();
    this.flight = (async () => { try {
      const next = await this.fresh(); this.state = next.state; this.view = next.view;
      if (this.input.size || Object.keys(this.row?.fields ?? {}).length || Object.keys(this.row?.forms ?? {}).length) this.review = true;
      this.error = next.state.write_blocked ? '服務目前暫停編輯，請稍後再查看；尚未保存的內容繼續保留。' : '';
      this.emit();
    } catch (error) { this.error = explain(error); this.emit(); } })();
    this.emit();
    try { await this.flight; } finally { this.flight = null; this.emit(); this.schedule(); }
  }
}
