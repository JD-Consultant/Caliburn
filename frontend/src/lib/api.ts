// v3 API client. Talks to the live AG-UI app (copilotkit_live_app) on 8001,
// which now mounts users + job_profiles CRUD under /api/v1. Legacy interview /
// tasks / documents endpoints were removed with the old backend (Concern B).
import type {
  ClarifyResult,
  DocumentEnvelope,
  DraftOpResult,
  ExtractTasksResult,
  HeaderMeta,
  JobProfile,
  KsaPool,
  OcsDocument,
  OcsSearchHit,
  PickedTask,
  RecommendKsResult,
  StructureTaskResult,
  TaskCandidates,
  User,
} from "@/types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}/api/v1${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${text}`);
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
// 產骨架。ksa-pool 為 catalog 候選池（indexer 掛則回空池）。
export const getDocument = (profileId: string) =>
  request<DocumentEnvelope>(`/job-profiles/${profileId}/document`);

export const patchDocument = (profileId: string, content: OcsDocument) =>
  request<DocumentEnvelope>(`/job-profiles/${profileId}/document`, {
    method: "PATCH",
    body: JSON.stringify(content),
  });

export const finalizeDocument = (profileId: string) =>
  request<DocumentEnvelope>(`/job-profiles/${profileId}/document/finalize`, {
    method: "POST",
  });

// 唯讀匯出：乾淨合法的 OCS JSON（不寫 DB）。
export const getDocumentExport = (profileId: string) =>
  request<OcsDocument>(`/job-profiles/${profileId}/document/export`);

// 選職類：設定 selected_ocs_codes（順序=優先度）。
export const setOccupations = (profileId: string, ocsCodes: string[]) =>
  request<{ ocs_codes: string[] }>(`/job-profiles/${profileId}/occupations`, {
    method: "POST",
    body: JSON.stringify({ ocs_codes: ocsCodes }),
  });

// 選任務候選（已選職類的所有任務，依職責分組）。
export const getTaskCandidates = (profileId: string) =>
  request<TaskCandidates>(`/job-profiles/${profileId}/task-candidates`);

// 用勾選的任務建/更新文件（遞進重編、保留已填）。
export const buildTasks = (profileId: string, picked: PickedTask[]) =>
  request<DocumentEnvelope>(`/job-profiles/${profileId}/build-tasks`, {
    method: "POST",
    body: JSON.stringify({ picked }),
  });

export const getKsaPool = (profileId: string) =>
  request<KsaPool>(`/job-profiles/${profileId}/ksa-pool`);

// 表頭候選池（D29）：多 OCS 官方 metadata 聯集（職類/職業/行業/態度/notes）+ 主基準。
export const getHeaderMeta = (profileId: string) =>
  request<HeaderMeta>(`/job-profiles/${profileId}/header-meta`);

export const ocsSearch = (profileId: string, q: string) =>
  request<{ hits: OcsSearchHit[] }>(
    `/job-profiles/${profileId}/ocs-search?q=${encodeURIComponent(q)}`,
  );

// ── AI 提議端點（D28 /ai/*）─────────────────────────────────────────────────
// 全部「只提議、不寫 DB」：回結構化提議，前端暫存→使用者套用才走 PATCH。
// 沒設後端金鑰時降級成只回 catalog（recommend-ks/draft-op）或空（extract/clarify）。

// 每任務 K/S 推薦：有 note→LLM 篩選+理由；無 note/無金鑰→回 catalog 全部（source=catalog）。
export const recommendKS = (body: { profile_id: string; task_key: string; note?: string }) =>
  request<RecommendKsResult>("/ai/recommend-ks", {
    method: "POST",
    body: JSON.stringify(body),
  });

// 每任務 產出/指標 草擬：有 note→LLM 個人化（source=ai）；無 note/無金鑰→catalog 官方。
export const draftOP = (body: { profile_id: string; task_key: string; note?: string }) =>
  request<DraftOpResult>("/ai/draft-op", {
    method: "POST",
    body: JSON.stringify(body),
  });

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

// 太薄的任務 note → 一個追問字串或 null。
export const clarify = (body: { task: string; note: string }) =>
  request<ClarifyResult>("/ai/clarify", {
    method: "POST",
    body: JSON.stringify(body),
  });
