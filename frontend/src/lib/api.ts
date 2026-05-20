const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}/api/v1${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Users ──────────────────────────────────────────────────────────────────
export const createUser = (data: { email: string; name: string; company?: string }) =>
  request<{ id: string; email: string; name: string }>("/users/", {
    method: "POST",
    body: JSON.stringify(data),
  });

// ── Job Profiles ───────────────────────────────────────────────────────────
export const listProfiles = (userId: string) =>
  request<import("@/types").JobProfile[]>(`/job-profiles/?user_id=${userId}`);

export const getProfile = (profileId: string) =>
  request<import("@/types").JobProfile>(`/job-profiles/${profileId}`);

export const createProfile = (
  userId: string,
  data: { job_title: string; department: string; job_summary?: string }
) =>
  request<import("@/types").JobProfile>(`/job-profiles/?user_id=${userId}`, {
    method: "POST",
    body: JSON.stringify(data),
  });

export const deleteProfile = (profileId: string) =>
  request<void>(`/job-profiles/${profileId}`, { method: "DELETE" });

// ── Interview ──────────────────────────────────────────────────────────────
export const getHistory = (profileId: string) =>
  request<import("@/types").InterviewMessage[]>(`/interviews/${profileId}/history`);

export async function* streamChat(
  profileId: string,
  content: string,
  phase = "general"
): AsyncGenerator<string> {
  const res = await fetch(`${BASE}/api/v1/interviews/${profileId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, phase }),
  });
  if (!res.ok || !res.body) throw new Error(`${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop() ?? "";
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const raw = line.slice(6);
        try {
          const chunk = JSON.parse(raw) as string;
          if (chunk === "[DONE]") return;
          yield chunk;
        } catch {
          if (raw === "[DONE]") return;
          yield raw;
        }
      }
    }
  }
}

export const getProfileState = (profileId: string) =>
  request<{ profile_id: string; stage: import("@/types").Stage; graph_state: import("@/types").GraphState }>(
    `/job-profiles/${profileId}/state`
  );

// ── Tasks ──────────────────────────────────────────────────────────────────
export const listTasks = (profileId: string) =>
  request<import("@/types").Task[]>(`/tasks/${profileId}`);

// ── Documents ──────────────────────────────────────────────────────────────
export async function exportDocument(
  profileId: string,
  format: "docx" | "pdf" | "xlsx" | "json"
): Promise<void> {
  const res = await fetch(
    `${BASE}/api/v1/documents/${profileId}/export?format=${format}`,
    { method: "POST" }
  );
  if (!res.ok) throw new Error(`Export failed: ${res.status}`);

  const blob = await res.blob();
  const disposition = res.headers.get("content-disposition") ?? "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match?.[1] ?? `document.${format}`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const getDocumentPreview = (profileId: string) =>
  request<{
    profile_id: string;
    stage: import("@/types").Stage;
    ocs_document: import("@/types").OcsDocument;
    behavior_indicators: import("@/types").BehaviorIndicator[];
    ksa_items: import("@/types").KsaItem[];
    extracted_tasks: import("@/types").Task[];
  }>(`/documents/${profileId}/preview`);

export const freezeDocument = (profileId: string) =>
  request<{ id: string; format: string; status: string; profile_stage: string }>(
    `/documents/${profileId}/freeze`,
    { method: "POST" }
  );

export const listDocumentVersions = (profileId: string) =>
  request<{ id: string; format: string; status: string; created_at: string }[]>(
    `/documents/${profileId}/versions`
  );
