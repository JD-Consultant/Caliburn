"use client";
import { useEffect, useState } from "react";
import same from "fast-deep-equal";
import type {
  JdDocumentValue,
  JdReadSuccess,
  JdSelectionCaptureClientInput,
  JdChangeReadSuccess,
} from "@caliburn/jd-editor-contract";
import type {
  DocumentOutput,
  MessageInput,
  MessageOutput,
  RunOutput,
} from "../generated/analysis-api";
import { api, ApiError, type JdApi } from "./api";
import { submissionCache, type Disk, type Submission } from "./submissionCache";
import { requestRecoveryCache } from "./requestRecoveryCache";
const active = new Set([
  "receiving",
  "running",
  "stopping",
  "uncertain",
  "interrupted",
]);
export class JdSession {
  head: JdReadSuccess | null = null;
  value = [] as unknown as JdDocumentValue;
  dirty = false;
  text = "";
  metadata: DocumentOutput | null = null;
  messages: MessageOutput[] = [];
  run: RunOutput | null = null;
  busy = false;
  saving = false;
  loading = true;
  readUnavailable = false;
  manualUnknown = false;
  serverWriteBlocked = true;
  restartRequired = false;
  recovery: Awaited<ReturnType<JdApi['readRecovery']>> | null = null;
  candidateRecovery: Awaited<ReturnType<JdApi['readRecovery']>> | null = null;
  recoverySequence = 0;
  error = "";
  notice = "";
  candidate: Submission | null = null;
  pendingRun: MessageInput | null = null;
  change: JdChangeReadSuccess | null = null;
  generation = 0;
  disposed = false;
  onChange = () => {};
  /** The editor applies a confirmed batch only against its exact clean baseline. */
  onHead:
    ((head: JdReadSuccess, change: JdChangeReadSuccess | null) => void) | null =
    null;
  constructor(
    public document: string,
    public port: JdApi,
    public disk: Disk,
  ) {}
  emit() {
    if (!this.disposed) this.onChange();
  }
  setText(text: string) {
    this.text = text;
    this.emit();
  }
  setError(error: string) {
    this.error = error;
    this.emit();
  }
  setNotice(notice: string) {
    this.notice = notice;
    this.emit();
  }
  bindHead(callback: JdSession["onHead"]) {
    this.onHead = callback;
  }
  discardBuffer() {
    this.dirty = false;
    this.text = "";
  }
  mount(listener: () => void) {
    this.disposed = false;
    this.onChange = listener;
    void this.load();
  }
  unmount() {
    this.disposed = true;
    this.generation++;
  }
  async revalidate() {
    this.loading = true;
    this.emit();
    try {
      await this.refresh();
    } catch {
      /* refresh retains the visible error and freezes admission. */
    } finally {
      this.loading = false;
      this.emit();
    }
  }
  get locked() {
    return (
      this.loading ||
      this.readUnavailable ||
      this.serverWriteBlocked ||
      this.busy ||
      this.manualUnknown ||
      !!this.metadata?.archived ||
      !!this.pendingRun ||
      (!!this.run && active.has(this.run.status))
    );
  }
  edit(value: JdDocumentValue) {
    this.value = structuredClone(value);
    this.dirty = !same(value, this.head?.fragment);
    this.emit();
  }
  async load() {
    this.loading = true;
    this.emit();
    try {
      this.candidate = submissionCache(this.disk).read(this.document);
      this.manualUnknown = !!this.candidate;
      this.pendingRun = requestRecoveryCache(this.disk).readRun(this.document);
      if (this.pendingRun) this.text = this.pendingRun.text;
      await this.refresh();
      if (this.pendingRun) await this.lookup();
    } catch (error) {
      this.error = String(error);
    } finally {
      this.loading = false;
      this.emit();
    }
  }
  async refresh() {
    const generation = ++this.generation;
    try {
      const [metadata, runs] = await Promise.all([
        this.port.document(this.document),
        this.port.runs(this.document),
      ]);
      if (this.disposed || generation !== this.generation) return;
      // A terminal run stops polling. Read its saved content after observing
      // that status, so an earlier in-flight read cannot freeze an older draft.
      const [messages, head] = await Promise.all([
        this.port.messages(this.document),
        this.port.read(this.document),
      ]);
      if (this.disposed || generation !== this.generation) return;
      this.metadata = metadata;
      this.messages = messages;
      this.run = runs.at(-1) ?? null;
      let change: JdChangeReadSuccess | null = null;
      if (!this.dirty &&
          this.head &&
          head.revision_ref !== this.head.revision_ref &&
          head.change_refs[0]
      ) {
        change = await this.port.changes(this.document, {
          change_ref: head.change_refs[0],
        });
        if (this.disposed || generation !== this.generation) return;
      }
      // Typing can occur while the diff request is in flight. Recheck at the
      // point of application; a dirty editor keeps its original saved baseline.
      if (!this.dirty) {
        this.onHead?.(head, change);
        this.head = head;
        this.value = structuredClone(head.fragment) as JdDocumentValue;
        if (change) this.change = change;
      } else if (this.head?.revision_ref !== head.revision_ref)
        this.notice = "已有新的保存內容；目前未保存修改仍留在畫面，請先處理。";
      this.error = "";
      this.readUnavailable = false;
      await this.refreshRecovery(generation);
    } catch (error) {
      if (this.disposed || generation !== this.generation) return;
      this.readUnavailable = true;
      this.error = "暫時無法讀取，請重試。" + String(error);
      // A failed native read must not hide the independent server owner gate.
      try { await this.refreshRecovery(generation); } catch { /* keep the gate closed */ }
      throw error;
    } finally {
      this.emit();
    }
  }
  get canRetryCandidate() {
    return !!this.candidate && !this.busy && !this.loading && !this.readUnavailable &&
      !this.serverWriteBlocked && (this.candidateRecovery?.status === 'no_pending' || !this.manualUnknown);
  }
  applyRecovery(value: Awaited<ReturnType<JdApi['readRecovery']>>) {
    if (value.request_key !== this.candidate?.request_key) return;
    this.candidateRecovery = value;
    if (value.status !== 'available') return;
    this.manualUnknown = false;
    if (['committed','no_change'].includes(value.result.status)) {
      submissionCache(this.disk).confirm(this.document, value.result);
      this.candidate = null;
      this.notice = '已確認上次保存結果；目前工作稿仍保留。';
    } else this.error = '這次修改尚未保存：' + value.result.status;
  }
  async refreshRecovery(generation = this.generation) {
    const sequence = ++this.recoverySequence;
    const key = this.candidate?.request_key ?? this.recovery?.request_key ?? undefined;
    const current = () => !this.disposed && generation === this.generation && sequence === this.recoverySequence;
    this.serverWriteBlocked = true;
    try {
      const exact = key ? await this.port.readRecovery(this.document,key) : null;
      if (!current()) return;
      const discovery = await this.port.readRecovery(this.document,undefined);
      if (!current()) return;
      if (exact && key === this.candidate?.request_key) this.applyRecovery(exact);
      this.recovery = discovery.request_key ? discovery : exact ?? discovery;
      this.serverWriteBlocked = discovery.write_blocked;
      this.restartRequired = discovery.restart_required === true;
    } catch (error) {
      if (!current()) return;
      this.serverWriteBlocked = true;
      this.error = '無法確認保存狀態，請重新讀取：' + String(error);
      throw error;
    }
  }
  async recoverManual() {
    const recovery = this.recovery;
    if (this.busy || !recovery?.can_recover || !recovery.request_key) return;
    const key = recovery.request_key;
    const generation = ++this.generation;
    ++this.recoverySequence;
    this.serverWriteBlocked = true;
    this.busy = true;
    this.emit();
    try {
      const result = await this.port.recover(this.document,key);
      if (this.disposed || generation !== this.generation || this.recovery?.request_key !== key) return;
      this.applyRecovery(result);
      this.recovery = result;
      // A fresh complete snapshot is required even after a terminal result.
      await this.refresh();
    } catch (error) {
      if (!this.disposed && generation === this.generation)
        this.error = '上次保存結果尚待確認：' + String(error);
    } finally {
      this.busy = false;
      this.emit();
    }
  }
  async save(reconcile = false) {
    if (!this.head || this.busy) return false;
    if (reconcile && !this.canRetryCandidate) return false;
    if (!reconcile && !this.dirty) return true;
    if (!reconcile && this.locked) return false;
    if (!reconcile && this.candidate) {
      this.setError("請先處理尚待處理的候選；明示捨棄後才能保存目前工作稿。");
      return false;
    }
    this.busy = true;
    this.saving = true;
    const generation = ++this.generation;
    ++this.recoverySequence;
    this.serverWriteBlocked = true;
    this.emit();
    try {
      const cache = submissionCache(this.disk);
      const payload = reconcile
        ? this.candidate
        : {
            document_id: this.document,
            request_key: crypto.randomUUID(),
            base_revision_ref: this.head.revision_ref,
            value: structuredClone(this.value),
          };
      if (!payload) return false;
      cache.write(payload);
      this.candidate = payload;
      this.manualUnknown = true;
      const { document_id, ...body } = payload;
      if (document_id !== this.document) throw Error("文件範圍不符");
      const receipt = await this.port.save(this.document, body);
      if (this.disposed || generation !== this.generation || this.candidate?.request_key !== body.request_key) return false;
      this.manualUnknown = receipt.receipt_durability !== "confirmed";
      if (
        receipt.receipt_durability === "confirmed" &&
        ["committed", "no_change"].includes(receipt.status)
      ) {
        const head = await this.port.read(this.document);
        if (this.disposed || generation !== this.generation || this.candidate?.request_key !== body.request_key) return false;
        if (head.revision_ref !== receipt.result_revision_ref) {
          this.notice = "本次保存已確認，已有後續版本。";
        }
        if (!reconcile || !this.dirty) {
          this.dirty = false;
          this.onHead?.(head, null);
          this.head = head;
          this.value = structuredClone(head.fragment) as JdDocumentValue;
        }
        cache.confirm(this.document, receipt);
        this.candidate = null;
        this.error = "";
        if (receipt.change_ref)
          this.change = await this.port.changes(this.document, {
            change_ref: receipt.change_ref,
          });
        this.notice = "已保存";
        return true;
      }
      this.error =
        receipt.receipt_durability === "confirmed"
          ? "這次修改尚未保存：" + receipt.status
          : "保存結果尚待確認，請再次確認。";
      return false;
    } catch (error) {
      if (error instanceof ApiError && error.manualRejection?.request_key === this.candidate?.request_key &&
        error.manualRejection?.admission === "not_admitted") {
        this.manualUnknown = false;
        this.error = "這次修改未進入保存；候選仍保留，請先處理或明示捨棄。" + error.message;
      } else this.error = "保存尚未確認：" + String(error);
      return false;
    } finally {
      if (!this.disposed && generation === this.generation) {
        try { await this.refreshRecovery(generation); } catch { /* Keep the gate blocked. */ }
      }
      this.busy = false;
      this.saving = false;
      this.emit();
    }
  }
  discardCandidate() {
    if (this.manualUnknown) return;
    submissionCache(this.disk).discard(this.document);
    this.candidate = null;
    this.emit();
  }
  async lookup() {
    if (!this.pendingRun) return;
    try {
      const found = await this.port.lookup(
        this.document,
        this.pendingRun.request_key,
      );
      if (found.found) {
        this.run = found.run;
        if (found.input_received) {
          requestRecoveryCache(this.disk).clearRun(this.document);
          this.pendingRun = null;
          this.text = "";
          await this.refresh();
        } else this.notice = "尚未確認收到這段話；可明示再次送出同一則。";
      } else this.notice = "尚未查到這次送出；可再次確認，或明示重送同一則。";
    } catch (error) {
      this.error = "正在確認是否收到：" + String(error);
    }
    this.emit();
  }
  async send(
    capture: () => JdSelectionCaptureClientInput["range"] | null,
    retry = false,
    requireSelection = false,
  ) {
    if (this.busy || (!retry && this.locked) || !this.text.trim()) return false;
    const selection = requireSelection ? capture() : null;
    if (requireSelection && !selection && !retry) {
      this.setError("選取已不存在，請重新選取；原問句仍保留。");
      return false;
    }
    if (this.dirty && !(await this.save())) return false;
    if (requireSelection && !same(selection, capture())) {
      this.error = "保存後選取已改變，請重新選取；原問句仍保留。";
      this.emit();
      return false;
    }
    if (!this.head) return false;
    this.busy = true;
    ++this.generation;
    ++this.recoverySequence;
    this.serverWriteBlocked = true;
    this.emit();
    try {
      const body: MessageInput =
        retry && this.pendingRun
          ? this.pendingRun
          : {
              request_key: crypto.randomUUID(),
              text: this.text,
              abandon_pending: false,
              ...(selection
                ? {
                    jd_selection: {
                      base_revision_ref: this.head.revision_ref,
                      range: selection,
                    },
                  }
                : {}),
            };
      requestRecoveryCache(this.disk).writeRun(this.document, body);
      this.pendingRun = body;
      this.run = await this.port.submit(this.document, body);
      await this.lookup();
      return !this.pendingRun;
    } catch (error) {
      if (error instanceof ApiError && [409, 422].includes(error.status)) {
        requestRecoveryCache(this.disk).clearRun(this.document);
        this.pendingRun = null;
        this.error = "未送出，請核對最新內容並重新選取。" + error.message;
      } else this.error = "正在確認是否收到，原問句與送出記錄已保留。";
      return false;
    } finally {
      this.busy = false;
      this.emit();
    }
  }
  async stop() {
    if (!this.run) return;
    this.busy = true;
    ++this.generation;
    ++this.recoverySequence;
    this.serverWriteBlocked = true;
    this.emit();
    try {
      this.run = await this.port.stop(this.document, this.run.id);
      await this.refresh();
    } catch (error) {
      this.error = "停止結果尚待確認：" + String(error);
    } finally {
      this.busy = false;
      this.emit();
    }
  }
  async resume() {
    if (!this.run?.can_resume) return;
    this.busy = true;
    ++this.generation;
    ++this.recoverySequence;
    this.serverWriteBlocked = true;
    this.emit();
    try {
      this.run = await this.port.resume(this.document, this.run.id);
    } catch (error) {
      this.error = String(error);
    } finally {
      this.busy = false;
      this.emit();
    }
  }
}
export function useJdSession(document: string) {
  const [session] = useState(
    () =>
      new JdSession(
        document,
        api,
        typeof window === "undefined"
          ? { getItem: () => null, setItem: () => {}, removeItem: () => {} }
          : localStorage,
      ),
  );
  const [, render] = useState(0);
  useEffect(() => {
    session.mount(() => render((n) => n + 1));
    const refresh = () => {
      if (document && globalThis.document.visibilityState === "visible")
        void session.revalidate();
    };
    window.addEventListener("pageshow", refresh);
    globalThis.document.addEventListener("visibilitychange", refresh);
    const timer = setInterval(() => {
      if (session.run && active.has(session.run.status) && !session.busy)
        void session.refresh().catch(() => {});
    }, 1000);
    return () => {
      session.unmount();
      clearInterval(timer);
      window.removeEventListener("pageshow", refresh);
      globalThis.document.removeEventListener("visibilitychange", refresh);
    };
  }, [document, session]);
  return session;
}
