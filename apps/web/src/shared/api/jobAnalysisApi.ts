import type {
  ApprovedJobDocumentWrite,
  ConsultantDocumentCatalog,
  ConsultantDocumentCatalogItem,
  ConsultantRunAccepted,
  ConsultantSnapshotView,
  DocumentStructureCommandPreviewView,
  DocumentStructureCommandResultView,
  DocumentStructureCommandWrite,
  DocumentReviewDecisionWrite,
  EmployeeAnswerWrite,
  ProblemDetail,
  RequiredClarificationAnswerWrite,
  UnderstandingCalibrationDecisionWrite,
} from "@caliburn/job-analysis-contract";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001";
const API = `${BASE}/api/v1/job-analysis`;
const CONSULTANT_API = `${API}/consultant-documents`;

type ReceivedProblem = Omit<ProblemDetail, "type"> & { type: string };

export type CurrentDocumentAuthorityGuards = {
  expectedRevision: number;
  workspaceGeneration: number;
  workspaceDigest: string;
};

export type CurrentDocumentCommand = DocumentStructureCommandWrite["command"];

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

function mutationHeaders(idempotencyKey: string) {
  return { "Idempotency-Key": idempotencyKey };
}

function commandHeaders(idempotencyKey: string, expectedRevision: number) {
  return {
    ...mutationHeaders(idempotencyKey),
    "X-Expected-Revision": String(expectedRevision),
  };
}

export function listConsultantDocuments(): Promise<ConsultantDocumentCatalog> {
  return request<ConsultantDocumentCatalog>("/consultant-documents", {
    method: "GET",
  });
}

export function createConsultantDocument(
  title: string,
  idempotencyKey: string,
): Promise<ConsultantDocumentCatalogItem> {
  return request<ConsultantDocumentCatalogItem>("/consultant-documents", {
    method: "POST",
    headers: mutationHeaders(idempotencyKey),
    body: JSON.stringify({ title }),
  });
}

export function getConsultantDocument(
  documentId: string,
): Promise<ConsultantDocumentCatalogItem> {
  return request<ConsultantDocumentCatalogItem>(
    `/consultant-documents/${documentId}`,
    { method: "GET" },
  );
}

export function deleteConsultantDocument(documentId: string): Promise<void> {
  return request<void>(`/consultant-documents/${documentId}`, {
    method: "DELETE",
  });
}

export function getConsultantSnapshot(
  documentId: string,
): Promise<ConsultantSnapshotView> {
  return request<ConsultantSnapshotView>(
    `/consultant-documents/${documentId}/snapshot`,
    { method: "GET" },
  );
}

export function submitConsultantAnswer(
  documentId: string,
  idempotencyKey: string,
  answer: EmployeeAnswerWrite,
): Promise<ConsultantRunAccepted> {
  return request<ConsultantRunAccepted>(
    `/consultant-documents/${documentId}/answers`,
    {
      method: "POST",
      headers: mutationHeaders(idempotencyKey),
      body: JSON.stringify(answer),
    },
  );
}

export function retryConsultantRun(
  documentId: string,
  runId: string,
): Promise<ConsultantRunAccepted> {
  return request<ConsultantRunAccepted>(
    `/consultant-documents/${documentId}/runs/${runId}/retry`,
    { method: "POST" },
  );
}

export function reviewDocumentChanges(
  documentId: string,
  changesetId: string,
  idempotencyKey: string,
  expectedRevision: number,
  decision: DocumentReviewDecisionWrite,
): Promise<ConsultantSnapshotView> {
  return request<ConsultantSnapshotView>(
    `/consultant-documents/${documentId}/reviews/${changesetId}`,
    {
      method: "POST",
      headers: commandHeaders(idempotencyKey, expectedRevision),
      body: JSON.stringify(decision),
    },
  );
}

export function decideUnderstandingCalibration(
  documentId: string,
  calibrationId: string,
  idempotencyKey: string,
  expectedRevision: number,
  decision: UnderstandingCalibrationDecisionWrite,
): Promise<ConsultantSnapshotView> {
  return request<ConsultantSnapshotView>(
    `/consultant-documents/${documentId}/calibrations/${calibrationId}`,
    {
      method: "POST",
      headers: commandHeaders(idempotencyKey, expectedRevision),
      body: JSON.stringify(decision),
    },
  );
}

export function answerRequiredClarification(
  documentId: string,
  clarificationId: string,
  idempotencyKey: string,
  expectedRevision: number,
  answer: RequiredClarificationAnswerWrite,
): Promise<ConsultantSnapshotView> {
  return request<ConsultantSnapshotView>(
    `/consultant-documents/${documentId}/clarifications/${clarificationId}`,
    {
      method: "POST",
      headers: commandHeaders(idempotencyKey, expectedRevision),
      body: JSON.stringify(answer),
    },
  );
}

export function editApprovedDocument(
  documentId: string,
  idempotencyKey: string,
  expectedRevision: number,
  document: ApprovedJobDocumentWrite,
): Promise<ConsultantSnapshotView> {
  return request<ConsultantSnapshotView>(
    `/consultant-documents/${documentId}/approved-document`,
    {
      method: "PUT",
      headers: commandHeaders(idempotencyKey, expectedRevision),
      body: JSON.stringify({ document }),
    },
  );
}

function currentDocumentCommandBody(
  guards: CurrentDocumentAuthorityGuards,
  command: CurrentDocumentCommand,
): DocumentStructureCommandWrite {
  return {
    command,
    workspace_generation: guards.workspaceGeneration,
    workspace_digest: guards.workspaceDigest,
  };
}

export function editCurrentDocument(
  documentId: string,
  idempotencyKey: string,
  guards: CurrentDocumentAuthorityGuards,
  document: ApprovedJobDocumentWrite,
): Promise<ConsultantSnapshotView> {
  return request<ConsultantSnapshotView>(
    `/consultant-documents/${documentId}/current-document`,
    {
      method: "PUT",
      headers: commandHeaders(idempotencyKey, guards.expectedRevision),
      body: JSON.stringify({
        document,
        workspace_generation: guards.workspaceGeneration,
        workspace_digest: guards.workspaceDigest,
      }),
    },
  );
}

export function previewCurrentDocumentCommand(
  documentId: string,
  guards: CurrentDocumentAuthorityGuards,
  command: CurrentDocumentCommand,
): Promise<DocumentStructureCommandPreviewView> {
  return request<DocumentStructureCommandPreviewView>(
    `/consultant-documents/${documentId}/current-document/commands/preview`,
    {
      method: "POST",
      headers: { "X-Expected-Revision": String(guards.expectedRevision) },
      body: JSON.stringify(currentDocumentCommandBody(guards, command)),
    },
  );
}

export function applyCurrentDocumentCommand(
  documentId: string,
  idempotencyKey: string,
  guards: CurrentDocumentAuthorityGuards,
  command: CurrentDocumentCommand,
): Promise<DocumentStructureCommandResultView> {
  return request<DocumentStructureCommandResultView>(
    `/consultant-documents/${documentId}/current-document/commands`,
    {
      method: "POST",
      headers: commandHeaders(idempotencyKey, guards.expectedRevision),
      body: JSON.stringify(currentDocumentCommandBody(guards, command)),
    },
  );
}

export async function exportConsultantDocument(
  documentId: string,
  force: boolean,
): Promise<Blob> {
  const suffix = force ? "?force=true" : "";
  const response = await fetch(
    `${CONSULTANT_API}/${documentId}/export${suffix}`,
    { method: "GET" },
  );
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => undefined);
    throw new JobAnalysisApiError(
      response.status,
      isReceivedProblem(body) ? body : undefined,
    );
  }
  return response.blob();
}

export function consultantEventsUrl(documentId: string): string {
  return `${CONSULTANT_API}/${documentId}/events`;
}

type KnownProblemType = ProblemDetail["type"];

const PROBLEM_MESSAGES: Record<KnownProblemType, string> = {
  "https://caliburn.dev/problems/job-analysis/document-not-found":
    "找不到這份職務文件。",
  "https://caliburn.dev/problems/job-analysis/idempotency-conflict":
    "這次操作與先前請求衝突，請重新整理後再試。",
  "https://caliburn.dev/problems/job-analysis/authority-conflict":
    "文件已更新，請重新整理後再確認。",
  "https://caliburn.dev/problems/job-analysis/invalid-request":
    "送出的內容無法處理，請檢查後再試。",
  "https://caliburn.dev/problems/job-analysis/consultant-unavailable":
    "AI 顧問暫時無法回應，請稍後重試。",
  "https://caliburn.dev/problems/job-analysis/consultant-run-active":
    "上一輪內容正在處理或等待復原，請先完成該輪。",
  "https://caliburn.dev/problems/job-analysis/consultant-command-conflict":
    "這個待確認項目已經變更，請重新整理後再操作。",
  "https://caliburn.dev/problems/job-analysis/export-confirmation-required":
    "文件仍有具體缺口；確認後可強制匯出。",
};

export function jobAnalysisProblemMessage(type: string): string {
  return (
    PROBLEM_MESSAGES[type as KnownProblemType] ??
    "發生未預期的問題，請稍後重試。"
  );
}
