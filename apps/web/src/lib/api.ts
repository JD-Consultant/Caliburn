// API client. Talks to the live AG-UI app (copilotkit_live_app) on 8001,
// which now mounts users + job_profiles CRUD under /api/v1. Legacy interview /
// tasks / documents endpoints were removed with the old backend (Concern B).
import type {
  DocumentEnvelope,
  ExtractTasksResult,
  JobProfile,
  KnowledgePack,
  OcsDocument,
  OcsSearchHit,
  StructureTaskResult,
  User,
} from "@/types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001";

// 2a（ADR 0015）：帶 HTTP status（+ 已解析的 body，409 conflict body 含
// current_version/current_revision）的 Error 子類，供 409 偵測用。
// 既有呼叫端 catch (e: Error) 不受影響：ApiError instanceof Error 恆真。
export class ApiError extends Error {
  status: number;
  body?: unknown;
  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}/api/v1${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    let body: unknown;
    try {
      body = JSON.parse(text);
    } catch {
      body = undefined;
    }
    throw new ApiError(res.status, `${res.status} ${text}`, body);
  }
  // 204 No Content (delete) has no body.
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ── Users ──────────────────────────────────────────────────────────────────
export const createUser = (data: { email: string; name: string; company?: string }) =>
  request<User>("/users/", { method: "POST", body: JSON.stringify(data) });

export const getUser = (userId: string) => request<User>(`/users/${userId}`);

// ── Job Profiles ─────────────────────────────────────────────────────────────
export const listProfiles = (userId: string) =>
  request<JobProfile[]>(`/job-profiles/?user_id=${userId}`);

export const getProfile = (profileId: string) =>
  request<JobProfile>(`/job-profiles/${profileId}`);

export const createProfile = (
  userId: string,
  data: { job_title: string; department?: string; job_summary?: string },
) =>
  request<JobProfile>(`/job-profiles/?user_id=${userId}`, {
    method: "POST",
    body: JSON.stringify(data),
  });

export const updateProfile = (
  profileId: string,
  data: { job_title?: string; department?: string; job_summary?: string },
) =>
  request<JobProfile>(`/job-profiles/${profileId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });

export const deleteProfile = (profileId: string) =>
  request<void>(`/job-profiles/${profileId}`, { method: "DELETE" });

// ── OCS document worktable (D27) ─────────────────────────────────────────────
// GET 無文件時回空殼（status:"none", version:0）。PATCH body = 整份 OCS 文件，
// 存成/更新 draft。finalize 組裝+驗 schema（失敗 422）。seed 用已選 ocs_codes
// 產骨架。
export const getDocument = (profileId: string) =>
  request<DocumentEnvelope>(`/job-profiles/${profileId}/document`);

// expect（2a, ADR 0015，optional）：{version, revision} 樂觀鎖 token。兩者皆帶
// 且與伺服器最新列不符 → 409 {code: "version_conflict", current_version, current_revision}。
// 不帶 = 不守衛（legacy 相容）。
export const patchDocument = (
  profileId: string,
  content: OcsDocument,
  expect?: { version: number; revision: number },
) =>
  request<DocumentEnvelope>(
    `/job-profiles/${profileId}/document` +
      (expect ? `?expect_version=${expect.version}&expect_revision=${expect.revision}` : ""),
    { method: "PATCH", body: JSON.stringify(content) },
  );

export const finalizeDocument = (profileId: string) =>
  request<DocumentEnvelope>(`/job-profiles/${profileId}/document:finalize`, {
    method: "POST",
  });

// 唯讀匯出：乾淨合法的 OCS JSON（不寫 DB）。
export const getDocumentExport = (profileId: string) =>
  request<OcsDocument>(`/job-profiles/${profileId}/document/export`);

// 選職類：整批取代 selected_ocs_codes（順序=優先度）→ 冪等 PUT（ADR 0019）。
export const setOccupations = (profileId: string, ocsCodes: string[]) =>
  request<{ ocs_codes: string[] }>(`/job-profiles/${profileId}/occupations`, {
    method: "PUT",
    body: JSON.stringify({ ocs_codes: ocsCodes }),
  });

// 知識包(ADR 0021):選職類後一次抓齊(occupation_details + 12 池 + source_tasks),
// 表頭/態度/NOTE/選任務/填格所有選單的唯一資料源(選職類=唯一同步點)。
export const getKnowledge = (profileId: string) =>
  request<KnowledgePack>(`/job-profiles/${profileId}/knowledge`);

// 職類目錄搜尋:全域集合、根層（ADR 0019）。回應欄位 = 複數資源名（AIP-132）。
export const ocsSearch = (q: string) =>
  request<{ occupations: OcsSearchHit[] }>(
    `/occupations?q=${encodeURIComponent(q)}`,
  );

// ── AI 提議端點（D28 /ai/*）─────────────────────────────────────────────────
// 全部「只提議、不寫 DB」：回結構化提議，前端暫存→使用者套用才走 PATCH。
// 沒設後端金鑰時降級成空提議。（recommend-ks/draft-op server 端仍在——訪談引擎/agent
// 主線用（ADR 0020）；web 填格已改吃知識包，不再呼叫。）

// intake 自述 → 預勾 catalog 任務 UUID + 候選自訂任務。
export const extractTasks = (body: { intake: string; ocs_codes: string[] }) =>
  request<ExtractTasksResult>("/ai/extract-tasks", {
    method: "POST",
    body: JSON.stringify(body),
  });

// 一句描述 → 任務名 + 職責建議（自訂任務用）。
export const structureTask = (body: { description: string; ocs_codes?: string[] }) =>
  request<StructureTaskResult>("/ai/structure-task", {
    method: "POST",
    body: JSON.stringify(body),
  });
