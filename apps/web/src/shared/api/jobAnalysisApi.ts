import type {
  ApprovedJobDocumentWrite,
  ConsultantDocumentCatalog,
  ConsultantDocumentCatalogItem,
  ConsultantRunAccepted,
  ConsultantSnapshotView,
  ConsultationView,
  DocumentReviewDecisionWrite,
  DocumentMetadataView,
  DocumentSummary,
  DocumentView,
  DutyOrderWrite,
  DutyView,
  DutyWrite,
  EmployeeAnswerWrite,
  JdHeaderView,
  JdHeaderWrite,
  JdTaskView,
  JdTaskWrite,
  OpksItemView,
  OpksItemWrite,
  OpksOrderWrite,
  OpksProposalDecisionWrite,
  ProblemDetail,
  ProposalDecisionWrite,
  RequiredClarificationAnswerWrite,
  UnderstandingCalibrationDecisionWrite,
} from "@caliburn/job-analysis-contract";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001";
const API = `${BASE}/api/v1/job-analysis`;
const CONSULTANT_API = `${API}/consultant-documents`;

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

export async function exportDocument(documentId: string): Promise<Blob> {
  const response = await fetch(`${API}/documents/${documentId}/export`, {
    method: "GET",
  });
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => undefined);
    throw new JobAnalysisApiError(
      response.status,
      isReceivedProblem(body) ? body : undefined,
    );
  }
  return response.blob();
}

export function getConsultation(documentId: string): Promise<ConsultationView> {
  return request<ConsultationView>(`/documents/${documentId}/consultation`, {
    method: "GET",
  });
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
  expectedRevision: number | null,
  decision: UnderstandingCalibrationDecisionWrite,
): Promise<ConsultantSnapshotView | ConsultantRunAccepted> {
  return request<ConsultantSnapshotView | ConsultantRunAccepted>(
    `/consultant-documents/${documentId}/calibrations/${calibrationId}`,
    {
      method: "POST",
      headers:
        expectedRevision === null
          ? mutationHeaders(idempotencyKey)
          : commandHeaders(idempotencyKey, expectedRevision),
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

export function putJdHeader(
  documentId: string,
  header: JdHeaderWrite,
  idempotencyKey: string,
): Promise<JdHeaderView> {
  return request<JdHeaderView>(`/documents/${documentId}/jd-header`, {
    method: "PUT",
    headers: mutationHeaders(idempotencyKey),
    body: JSON.stringify(header),
  });
}

export function addDuty(
  documentId: string,
  duty: DutyWrite,
  idempotencyKey: string,
): Promise<DutyView> {
  return request<DutyView>(`/documents/${documentId}/duties`, {
    method: "POST",
    headers: mutationHeaders(idempotencyKey),
    body: JSON.stringify(duty),
  });
}

export function editDuty(
  documentId: string,
  dutyId: string,
  duty: DutyWrite,
  idempotencyKey: string,
): Promise<DutyView> {
  return request<DutyView>(`/documents/${documentId}/duties/${dutyId}`, {
    method: "PUT",
    headers: mutationHeaders(idempotencyKey),
    body: JSON.stringify(duty),
  });
}

export function deleteDuty(
  documentId: string,
  dutyId: string,
  idempotencyKey: string,
): Promise<void> {
  return request<void>(`/documents/${documentId}/duties/${dutyId}`, {
    method: "DELETE",
    headers: mutationHeaders(idempotencyKey),
  });
}

export function reorderDuties(
  documentId: string,
  orderedDutyIds: string[],
  idempotencyKey: string,
): Promise<DutyView[]> {
  const body: DutyOrderWrite = { ordered_duty_ids: orderedDutyIds };
  return request<DutyView[]>(`/documents/${documentId}/duty-order`, {
    method: "PUT",
    headers: mutationHeaders(idempotencyKey),
    body: JSON.stringify(body),
  });
}

export function addTask(
  documentId: string,
  task: JdTaskWrite,
  idempotencyKey: string,
): Promise<JdTaskView> {
  return request<JdTaskView>(`/documents/${documentId}/tasks`, {
    method: "POST",
    headers: mutationHeaders(idempotencyKey),
    body: JSON.stringify(task),
  });
}

export function editTask(
  documentId: string,
  taskId: string,
  task: JdTaskWrite,
  idempotencyKey: string,
): Promise<JdTaskView> {
  return request<JdTaskView>(`/documents/${documentId}/tasks/${taskId}`, {
    method: "PUT",
    headers: mutationHeaders(idempotencyKey),
    body: JSON.stringify(task),
  });
}

export function deleteTask(
  documentId: string,
  taskId: string,
  idempotencyKey: string,
): Promise<void> {
  return request<void>(`/documents/${documentId}/tasks/${taskId}`, {
    method: "DELETE",
    headers: mutationHeaders(idempotencyKey),
  });
}

export function reorderTasks(
  documentId: string,
  orderedTaskIds: string[],
  idempotencyKey: string,
): Promise<JdTaskView[]> {
  return request<JdTaskView[]>(`/documents/${documentId}/task-order`, {
    method: "PUT",
    headers: mutationHeaders(idempotencyKey),
    body: JSON.stringify({ ordered_task_ids: orderedTaskIds }),
  });
}

export function addOpksItem(
  documentId: string,
  item: OpksItemWrite,
  idempotencyKey: string,
): Promise<OpksItemView> {
  return request<OpksItemView>(`/documents/${documentId}/opks`, {
    method: "POST",
    headers: mutationHeaders(idempotencyKey),
    body: JSON.stringify(item),
  });
}

export function editOpksItem(
  documentId: string,
  entityId: string,
  item: OpksItemWrite,
  idempotencyKey: string,
): Promise<OpksItemView> {
  return request<OpksItemView>(`/documents/${documentId}/opks/${entityId}`, {
    method: "PUT",
    headers: mutationHeaders(idempotencyKey),
    body: JSON.stringify(item),
  });
}

export function deleteOpksItem(
  documentId: string,
  entityId: string,
  idempotencyKey: string,
): Promise<void> {
  return request<void>(`/documents/${documentId}/opks/${entityId}`, {
    method: "DELETE",
    headers: mutationHeaders(idempotencyKey),
  });
}

export function reorderOpksItems(
  documentId: string,
  entityKind: OpksOrderWrite["entity_kind"],
  orderedEntityIds: string[],
  idempotencyKey: string,
): Promise<OpksItemView[]> {
  const body: OpksOrderWrite = {
    entity_kind: entityKind,
    ordered_entity_ids: orderedEntityIds,
  };
  return request<OpksItemView[]>(`/documents/${documentId}/opks-order`, {
    method: "PUT",
    headers: mutationHeaders(idempotencyKey),
    body: JSON.stringify(body),
  });
}

export function submitEmployeeTurn(
  documentId: string,
  idempotencyKey: string,
  text: string,
): Promise<ConsultationView> {
  return request<ConsultationView>(`/documents/${documentId}/turns`, {
    method: "POST",
    headers: mutationHeaders(idempotencyKey),
    body: JSON.stringify({ text }),
  });
}

export function decideProposal(
  documentId: string,
  proposalId: string,
  idempotencyKey: string,
  decision: ProposalDecisionWrite,
): Promise<ConsultationView> {
  return request<ConsultationView>(
    `/documents/${documentId}/proposals/${proposalId}/decisions`,
    {
      method: "POST",
      headers: mutationHeaders(idempotencyKey),
      body: JSON.stringify(decision),
    },
  );
}

export function decideOpksProposal(
  documentId: string,
  proposalId: string,
  idempotencyKey: string,
  decision: OpksProposalDecisionWrite,
): Promise<ConsultationView> {
  return request<ConsultationView>(
    `/documents/${documentId}/opks-proposals/${proposalId}/decisions`,
    {
      method: "POST",
      headers: mutationHeaders(idempotencyKey),
      body: JSON.stringify(decision),
    },
  );
}

type KnownProblemType = ProblemDetail["type"];

function knownProblemMessage(type: KnownProblemType): string {
  switch (type) {
    case "https://caliburn.dev/problems/job-analysis/document-not-found":
      return "找不到這份職務說明書";
    case "https://caliburn.dev/problems/job-analysis/task-not-found":
      return "找不到這項工作";
    case "https://caliburn.dev/problems/job-analysis/duty-not-found":
      return "找不到這項主要職責";
    case "https://caliburn.dev/problems/job-analysis/opks-item-not-found":
      return "找不到這項職務內容";
    case "https://caliburn.dev/problems/job-analysis/idempotency-conflict":
      return "這次操作內容已經改變";
    case "https://caliburn.dev/problems/job-analysis/authority-conflict":
      return "內容已有更新";
    case "https://caliburn.dev/problems/job-analysis/invalid-task-order":
      return "工作順序不正確";
    case "https://caliburn.dev/problems/job-analysis/invalid-duty-order":
      return "主要職責順序不正確";
    case "https://caliburn.dev/problems/job-analysis/invalid-opks-order":
      return "職能內容順序不正確";
    case "https://caliburn.dev/problems/job-analysis/invalid-request":
      return "請檢查輸入內容";
    case "https://caliburn.dev/problems/job-analysis/proposal-not-found":
      return "找不到這項提案";
    case "https://caliburn.dev/problems/job-analysis/consultant-unavailable":
      return "顧問暫時無法完成分析，請稍後重試";
    case "https://caliburn.dev/problems/job-analysis/consultant-run-active":
      return "上一則回答仍在分析中，請稍候";
    case "https://caliburn.dev/problems/job-analysis/consultant-command-conflict":
      return "這項決定已用於不同內容，請重新操作";
    case "https://caliburn.dev/problems/job-analysis/export-confirmation-required":
      return "匯出前仍有缺口，請先查看並明確確認";
    default:
      return assertNever(type);
  }
}

const KNOWN_PROBLEM_TYPES = new Set<string>([
  "https://caliburn.dev/problems/job-analysis/document-not-found",
  "https://caliburn.dev/problems/job-analysis/task-not-found",
  "https://caliburn.dev/problems/job-analysis/duty-not-found",
  "https://caliburn.dev/problems/job-analysis/opks-item-not-found",
  "https://caliburn.dev/problems/job-analysis/idempotency-conflict",
  "https://caliburn.dev/problems/job-analysis/authority-conflict",
  "https://caliburn.dev/problems/job-analysis/invalid-task-order",
  "https://caliburn.dev/problems/job-analysis/invalid-duty-order",
  "https://caliburn.dev/problems/job-analysis/invalid-opks-order",
  "https://caliburn.dev/problems/job-analysis/invalid-request",
  "https://caliburn.dev/problems/job-analysis/proposal-not-found",
  "https://caliburn.dev/problems/job-analysis/consultant-unavailable",
  "https://caliburn.dev/problems/job-analysis/consultant-run-active",
  "https://caliburn.dev/problems/job-analysis/consultant-command-conflict",
  "https://caliburn.dev/problems/job-analysis/export-confirmation-required",
] satisfies KnownProblemType[]);

function assertNever(value: never): never {
  throw new Error(`Unmapped problem type: ${value}`);
}

export function jobAnalysisProblemMessage(type: string): string {
  if (!KNOWN_PROBLEM_TYPES.has(type)) return "操作失敗，請稍後再試";
  return knownProblemMessage(type as KnownProblemType);
}
