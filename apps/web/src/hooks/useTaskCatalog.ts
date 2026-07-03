import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { draftOP, getTaskCatalogs, recommendKS } from "@/lib/api";
import type { OptionItem, TaskCatalogEntry } from "@/types";

// 共用形狀:一份 per-task catalog（含 level）。四種項目皆帶來源 code（2b provenance）。
export interface TaskCatalogData {
  knowledge: OptionItem[];
  skills: OptionItem[];
  outputs: OptionItem[];
  indicators: { code: string; text: string }[];
  competency_level: number | null;
}

const STALE = 5 * 60 * 1000;
// 鍵 = 任務身分 URN(A1):結構性編輯重編位置碼不影響鍵;批次回應的鍵已是 URN,seeding 直灌。
const catalogKey = (profileId: string, urn: string) => ["task-catalog", profileId, urn];

// 後備（快取未命中）：per-task 兩端點。批次 seeding 命中時不會跑到這裡。
async function fetchTaskCatalog(profileId: string, taskKey: string): Promise<TaskCatalogData> {
  const [ks, op] = await Promise.all([
    recommendKS({ profile_id: profileId, task_key: taskKey }),
    draftOP({ profile_id: profileId, task_key: taskKey }),
  ]);
  return {
    knowledge: ks.knowledge.map((k) => ({ code: k.code, name: k.name })),
    skills: ks.skills.map((s) => ({ code: s.code, name: s.name })),
    outputs: op.outputs.map((o) => ({ code: o.code, name: o.name })),
    indicators: op.indicators.map((i) => ({ code: i.code, text: i.text })),
    competency_level: ks.competency_level ?? null,
  };
}

// 批次回應 → 共用形狀（四種皆保留來源 code）。
function fromEntry(e: TaskCatalogEntry): TaskCatalogData {
  return {
    knowledge: e.knowledge.map((k) => ({ code: k.code, name: k.name })),
    skills: e.skills.map((s) => ({ code: s.code, name: s.name })),
    outputs: e.outputs.map((o) => ({ code: o.code, name: o.name })),
    indicators: e.indicators.map((i) => ({ code: i.code, text: i.text })),
    competency_level: e.competency_level ?? null,
  };
}

// 文件載入後抓批次,把每任務 catalog 灌進 per-task 快取（TkDodo seeding/push）。
export function useTaskCatalogs(profileId: string, enabled: boolean) {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["task-catalogs", profileId],
    queryFn: () => getTaskCatalogs(profileId),
    enabled,
    staleTime: STALE,
    gcTime: 1000 * 60 * 60 * 24, // ≥ persist maxAge(24h)，否則被 GC 早於還原期限
    refetchOnWindowFocus: false,
    meta: { persist: true }, // 准予持久化（spec D-1d）；重載自 localStorage 還原後 seed 各任務
  });
  useEffect(() => {
    if (!q.data) return;
    for (const [tk, entry] of Object.entries(q.data.catalogs)) {
      qc.setQueryData(catalogKey(profileId, tk), fromEntry(entry));
    }
  }, [q.data, profileId, qc]);
  return q;
}

// urn = 快取鍵(身分);taskKey = 位置碼,僅供 fallback 打 /ai/*(即時定位語意,不快取)。
export function useTaskLevel(profileId: string, urn: string, taskKey: string, enabled: boolean): number | null {
  const q = useQuery({
    queryKey: catalogKey(profileId, urn),
    enabled: enabled && !!urn && !!taskKey,
    staleTime: STALE,
    queryFn: () => fetchTaskCatalog(profileId, taskKey),
    select: (d: TaskCatalogData) => d.competency_level,
  });
  return q.data ?? null;
}

export function useTaskCatalog(profileId: string, urn: string, taskKey: string, enabled: boolean) {
  const q = useQuery({
    queryKey: catalogKey(profileId, urn),
    enabled: enabled && !!urn && !!taskKey,
    staleTime: STALE,
    queryFn: () => fetchTaskCatalog(profileId, taskKey),
  });
  return {
    knowledge: q.data?.knowledge ?? [],
    skills: q.data?.skills ?? [],
    outputs: q.data?.outputs ?? [],
    indicators: q.data?.indicators ?? [],
    isLoading: q.isLoading,
  };
}
