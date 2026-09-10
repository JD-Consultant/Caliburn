import type {
  DocumentInput,
  DocumentOutput,
  DocumentMetadataInput,
  MessageInput,
  MessageOutput,
  RunOutput,
  RunLookupReceived,
  JdRunLookupMissing,
  ManualSaveRejection,
} from "../generated/analysis-api";
import type {
  JdReadSuccess,
  JdReadResult,
  JdReadModelInput,
  JdChangeReadModelInput,
  JdChangeReadResult,
  JdManualSaveClientInput,
  JdManualSaveResult,
  JdSourceReadResult,
} from "@caliburn/jd-editor-contract";
const origin =
  process.env.NEXT_PUBLIC_ANALYSIS_API_ORIGIN ?? "http://127.0.0.1:8091";
if (origin !== "http://127.0.0.1:8091")
  throw Error("隔離 JD API 必須使用 127.0.0.1:8091");
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public manualRejection: ManualSaveRejection | null = null,
  ) {
    super(message);
  }
}
export async function request<T>(
  path: string,
  body?: unknown,
  method = body === undefined ? "GET" : "POST",
): Promise<T> {
  const response = await fetch(origin + path, {
    method,
    headers:
      body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
    credentials: "omit",
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new ApiError(
      response.status,
      typeof error?.detail === "string"
        ? error.detail
        : typeof error?.message === "string" ? error.message
        : "本機服務暫時無法完成，請重試",
      error?.admission === "not_admitted" && typeof error?.request_key === "string" &&
        typeof error?.message === "string" ? error as ManualSaveRejection : null,
    );
  }
  return response.json();
}
const doc = (id: string) => "/documents/" + encodeURIComponent(id);
export const api = {
  documents: (archived = false) =>
    request<DocumentOutput[]>("/documents?archived=" + archived),
  create: (body: DocumentInput) => request<DocumentOutput>("/documents", body),
  document: (id: string) => request<DocumentOutput>(doc(id)),
  metadata: (id: string, body: DocumentMetadataInput) =>
    request<DocumentOutput>(doc(id), body, "PATCH"),
  messages: (id: string) => request<MessageOutput[]>(doc(id) + "/messages"),
  source: (id: string, reference: string, offset = 0) =>
    request<JdSourceReadResult>(
      doc(id) +
        "/sources?reference=" +
        encodeURIComponent(reference) +
        "&offset=" +
        offset,
    ),
  runs: (id: string) => request<RunOutput[]>(doc(id) + "/runs"),
  run: (id: string, key: string) =>
    request<RunOutput>(doc(id) + "/runs/" + encodeURIComponent(key)),
  lookup: (id: string, key: string) =>
    request<RunLookupReceived | JdRunLookupMissing>(
      doc(id) + "/runs/by-request?request_key=" + encodeURIComponent(key),
    ),
  submit: (id: string, body: MessageInput) =>
    request<RunOutput>(doc(id) + "/runs", body),
  stop: (id: string, run: string) =>
    request<RunOutput>(
      doc(id) + "/runs/" + encodeURIComponent(run) + "/stop",
      {},
    ),
  resume: (id: string, run: string) =>
    request<RunOutput>(
      doc(id) + "/runs/" + encodeURIComponent(run) + "/resume",
      {},
    ),
  async read(id: string, args?: JdReadModelInput) {
    const first = await request<JdReadResult>(
      doc(id) + "/jd" + (args ? "/read" : ""),
      args,
    );
    if (first.status !== "ok")
      throw Error("無法讀取職務說明書：" + first.status);
    const result = structuredClone(first) as JdReadSuccess;
    while (result.continuation_ref) {
      const next = await request<JdReadResult>(doc(id) + "/jd/read", {
        continuation_ref: result.continuation_ref,
      });
      if (next.status !== "ok") throw Error("尚未完整讀取文件");
      result.fragment.push(...next.fragment);
      result.targets.push(...next.targets);
      result.continuation_ref = next.continuation_ref;
    }
    return result;
  },
  async changes(id: string, args: JdChangeReadModelInput) {
    const result = await request<JdChangeReadResult>(
      doc(id) + "/jd/changes/read",
      args,
    );
    if (result.status !== "ok") throw Error("無法讀取確切改動");
    while (result.continuation_ref) {
      const next = await request<JdChangeReadResult>(
        doc(id) + "/jd/changes/read",
        { continuation_ref: result.continuation_ref },
      );
      if (next.status !== "ok") throw Error("尚未完整讀取改動");
      result.before_fragment.push(...next.before_fragment);
      result.after_fragment.push(...next.after_fragment);
      result.continuation_ref = next.continuation_ref;
    }
    return result;
  },
  save: (id: string, body: JdManualSaveClientInput) =>
    request<JdManualSaveResult>(doc(id) + "/jd/manual-save", body),
};
export type JdApi = typeof api;
