import type {
  DocumentMetadataView,
  DocumentSummary,
  DocumentView,
  ProblemDetail,
} from "@caliburn/job-analysis-contract";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001";
const API = `${BASE}/api/v1/job-analysis`;

type ReceivedProblem = Omit<ProblemDetail, "type"> & { type: string };

export class JobAnalysisApiError extends Error {
  constructor(
    readonly status: number,
    readonly problem?: ReceivedProblem,
  ) {
    super(problem ? jobAnalysisProblemMessage(problem.type) : `HTTP ${status}`);
    this.name = "JobAnalysisApiError";
  }
}

function isReceivedProblem(value: unknown): value is ReceivedProblem {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.type === "string" &&
    typeof candidate.title === "string" &&
    typeof candidate.status === "number"
  );
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
  });
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => undefined);
    throw new JobAnalysisApiError(
      response.status,
      isReceivedProblem(body) ? body : undefined,
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function listDocuments(): Promise<DocumentSummary[]> {
  return request<DocumentSummary[]>("/documents", { method: "GET" });
}

export function putDocument(
  documentId: string,
  title: string,
): Promise<DocumentMetadataView> {
  return request<DocumentMetadataView>(`/documents/${documentId}`, {
    method: "PUT",
    body: JSON.stringify({ title }),
  });
}

export function createDocument(
  title: string,
  documentId = crypto.randomUUID(),
): Promise<DocumentMetadataView> {
  return putDocument(documentId, title);
}

export function getDocument(documentId: string): Promise<DocumentView> {
  return request<DocumentView>(`/documents/${documentId}`, { method: "GET" });
}

type KnownProblemType = ProblemDetail["type"];

function knownProblemMessage(type: KnownProblemType): string {
  switch (type) {
    case "https://caliburn.dev/problems/job-analysis/document-not-found":
      return "找不到這份職務說明書";
    case "https://caliburn.dev/problems/job-analysis/task-not-found":
      return "找不到這項工作";
    case "https://caliburn.dev/problems/job-analysis/idempotency-conflict":
      return "這次操作內容已經改變";
    case "https://caliburn.dev/problems/job-analysis/authority-conflict":
      return "內容已有更新";
    case "https://caliburn.dev/problems/job-analysis/invalid-task-order":
      return "工作順序不正確";
    case "https://caliburn.dev/problems/job-analysis/invalid-request":
      return "請檢查輸入內容";
    default:
      return assertNever(type);
  }
}

const KNOWN_PROBLEM_TYPES = new Set<string>([
  "https://caliburn.dev/problems/job-analysis/document-not-found",
  "https://caliburn.dev/problems/job-analysis/task-not-found",
  "https://caliburn.dev/problems/job-analysis/idempotency-conflict",
  "https://caliburn.dev/problems/job-analysis/authority-conflict",
  "https://caliburn.dev/problems/job-analysis/invalid-task-order",
  "https://caliburn.dev/problems/job-analysis/invalid-request",
] satisfies KnownProblemType[]);

function assertNever(value: never): never {
  throw new Error(`Unmapped problem type: ${value}`);
}

export function jobAnalysisProblemMessage(type: string): string {
  if (!KNOWN_PROBLEM_TYPES.has(type)) return "操作失敗，請稍後再試";
  return knownProblemMessage(type as KnownProblemType);
}
