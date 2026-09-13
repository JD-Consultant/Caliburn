import { ApiError } from './api.ts';
import type { JdApi } from './api.ts';
import type { ChatSubmission } from './drafts.ts';
import type { ChatHistoryPage, ChatMessage, ChatRunState } from '../../../src/jd_relational/generated/jd-chat-http.ts';

export type ChatApi = Pick<JdApi, 'datasetId' | 'chatMessages' | 'chatStatus' | 'chatStart' | 'chatCancel' | 'chatRecover'>;
export interface ChatPort {
  chatPrepare(): Promise<ChatSubmission>;
  chatOriginal(): ChatSubmission | null;
  chatObserve(state: ChatRunState): Promise<void>;
  chatUnavailable(submission: ChatSubmission): Promise<void>;
  chatRequestFinished(): void;
  chatRestore(state: ChatRunState): Promise<void>;
}
export interface ChatSnapshot {
  messages: ChatMessage[];
  page: ChatHistoryPage | null;
  run: ChatRunState | null;
  runId: string | null;
  loading: boolean;
  busy: boolean;
  error: ApiError | null;
  canRetry: boolean;
}

const active = (value: ChatRunState | null) => value?.run_status === 'running' || value?.run_status === 'closing';
const invalid = () => new ApiError('invalid_response');

/** One document's read observer and explicit controls; persistence belongs to ChatPort. */
export class ChatController {
  private readonly api: ChatApi;
  private readonly id: string;
  private readonly port: ChatPort;
  private readonly notify: (value: ChatSnapshot) => void;
  private readonly dataset: string | null;
  private disposed = false;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private busy = false;
  private loading = false;
  private error: ApiError | null = null;
  private page: ChatHistoryPage | null = null;
  private messages: ChatMessage[] = [];
  private run: ChatRunState | null = null;
  private runId: string | null = null;

  constructor(api: ChatApi, id: string, port: ChatPort, notify: (value: ChatSnapshot) => void) {
    this.api = api; this.id = id; this.port = port; this.notify = notify; this.dataset = api.datasetId;
  }
  snapshot(): ChatSnapshot {
    return { messages: structuredClone(this.messages), page: structuredClone(this.page), run: structuredClone(this.run),
      runId: this.runId, loading: this.loading, busy: this.busy, error: this.error,
      canRetry: !this.busy && this.port.chatOriginal() !== null && this.run?.run_status !== 'recovery_required'
        && (this.error !== null || this.run?.run_status === 'not_found') };
  }
  private emit() { if (!this.disposed) this.notify(this.snapshot()); }
  private scope() {
    if (this.dataset === null) throw new ApiError('dataset_required', '請先讀取文件列表。');
    if (this.api.datasetId !== this.dataset) throw new ApiError('dataset_changed', '資料集已變更，請保留原輸入並重新開啟文件。');
  }
  private stopTimer() { if (this.timer !== null) clearTimeout(this.timer); this.timer = null; }
  private schedule() {
    this.stopTimer();
    if (this.disposed || this.busy || this.error || !active(this.run)) return;
    // An explicit active response permits another observation, never a replay.
    this.timer = setTimeout(() => { this.timer = null; void this.poll(); }, 2000);
  }
  private async flight(work: () => Promise<void>, loading = false) {
    if (this.disposed || this.busy) return;
    this.stopTimer(); this.busy = true; this.loading = loading; this.error = null; this.emit();
    try { this.scope(); await work(); }
    catch (error) {
      if (!this.disposed) this.error = error instanceof ApiError ? error
        : new ApiError('response_unknown', '目前無法確認這次操作，請保留原輸入並查看原回合。');
    } finally {
      this.busy = false; this.loading = false; this.emit(); this.schedule();
    }
  }
  private checkedPage(page: ChatHistoryPage) {
    this.scope();
    if (page.dataset_id !== this.dataset || page.document_id !== this.id) throw invalid();
    const ids = new Set<string>();
    for (const message of page.messages) {
      if (ids.has(message.message_id)) throw invalid();
      ids.add(message.message_id);
    }
  }
  private async latest() {
    const page = await this.api.chatMessages(this.id);
    if (this.disposed) return;
    this.checkedPage(page);
    // New root means a new window. Previously loaded old pages are not mixed in.
    this.page = structuredClone(page); this.messages = structuredClone(page.messages); this.emit();
  }
  private target(): string | null {
    return this.port.chatOriginal()?.request.run_id ?? this.runId ?? this.page?.anchor_run_id ?? null;
  }
  private selectRun(runId: string | null) {
    if (this.run?.run_id !== runId) this.run = null;
    this.runId = runId; this.emit();
  }
  private async observe(value: ChatRunState, runId: string) {
    if (this.disposed) return;
    this.scope();
    if (value.dataset_id !== this.dataset || value.document_id !== this.id || value.run_id !== runId) throw invalid();
    this.run = structuredClone(value); this.runId = runId; this.emit();
    await this.port.chatObserve(value);
    if (this.disposed) return;
    this.scope();
    // Fetch public text only when the known saved input/response is not visible.
    // A partial page need not contain every item of an older inspected run.
    if (value.input_state === 'saved' && !this.messages.some(m => m.role === 'user' && m.run_id === runId)
        || value.response_message_id !== null && !this.messages.some(m => m.message_id === value.response_message_id))
      await this.latest();
  }
  private async status(runId: string) {
    this.selectRun(runId);
    const state = await this.api.chatStatus(this.id, runId);
    if (!this.disposed) await this.observe(state, runId);
    return state;
  }
  private async post(submission: ChatSubmission) {
    let state: ChatRunState;
    try {
      state = await this.api.chatStart(this.id, submission.request);
    } catch (error) {
      if (!this.disposed && error instanceof ApiError && error.code === 'ai_unavailable') {
        this.scope(); await this.port.chatUnavailable(submission);
      }
      throw error;
    }
    if (!this.disposed) await this.observe(state, submission.request.run_id);
  }

  private async latestRun() {
    await this.latest(); if (this.disposed) return;
    // The durable local request wins even when the newest page belongs elsewhere.
    const runId = this.port.chatOriginal()?.request.run_id ?? this.page?.anchor_run_id ?? null;
    this.selectRun(runId);
    if (runId !== null) await this.status(runId);
    else this.run = null;
  }
  async start() {
    await this.flight(() => this.latestRun(), true);
  }
  async send() {
    await this.flight(async () => {
      if (active(this.run) || this.run?.run_status === 'recovery_required')
        throw new ApiError('document_busy', '請先等待原回合完成或確認收尾。');
      try {
        const submission = await this.port.chatPrepare();
        if (this.disposed) return;
        this.scope(); this.selectRun(submission.request.run_id);
        await this.post(submission);
      } finally { this.port.chatRequestFinished(); }
    });
  }
  async refresh() {
    await this.flight(() => this.latestRun());
  }
  private async poll() {
    await this.flight(async () => { if (this.runId !== null) await this.status(this.runId); });
  }
  async retry() {
    await this.flight(async () => {
      const original = this.port.chatOriginal();
      if (original === null) return;
      const captured = structuredClone(original);
      const state = await this.status(captured.request.run_id);
      if (this.disposed) return;
      if (state.run_status === 'recovery_required') {
        await this.observe(await this.api.chatRecover(this.id, captured.request.run_id), captured.request.run_id);
      } else if (state.run_status === 'not_found') {
        if (JSON.stringify(this.port.chatOriginal()) !== JSON.stringify(captured))
          throw new ApiError('request_changed', '原輸入已改變，請保留內容並重新查看原回合。');
        try { await this.post(captured); }
        finally { this.port.chatRequestFinished(); }
      }
    });
  }
  async cancel() {
    await this.flight(async () => {
      const runId = this.target();
      if (runId !== null) { this.selectRun(runId); await this.observe(await this.api.chatCancel(this.id, runId), runId); }
    });
  }
  async recover() {
    await this.flight(async () => {
      const runId = this.target();
      if (runId !== null) { this.selectRun(runId); await this.observe(await this.api.chatRecover(this.id, runId), runId); }
    });
  }
  async restore() {
    await this.flight(async () => {
      if (this.run?.run_status === 'failed' && this.run.input_state === 'not_saved') await this.port.chatRestore(this.run);
    });
  }
  async more() {
    await this.flight(async () => {
      const before = this.page;
      if (!before || before.anchor === null || before.next_cursor === null) return;
      const page = await this.api.chatMessages(this.id, { cursor: before.next_cursor, anchor: before.anchor, anchorRunId: before.anchor_run_id });
      if (this.disposed) return;
      this.checkedPage(page);
      if (page.anchor !== before.anchor || page.anchor_run_id !== before.anchor_run_id || !page.messages.length
          || page.next_cursor === before.next_cursor) throw invalid();
      const ids = new Set(this.messages.map(m => m.message_id));
      if (page.messages.some(m => ids.has(m.message_id))) throw invalid();
      this.messages = [...structuredClone(page.messages), ...this.messages];
      this.page = structuredClone(page); this.emit();
    });
  }
  dispose() { this.disposed = true; this.stopTimer(); }
}
