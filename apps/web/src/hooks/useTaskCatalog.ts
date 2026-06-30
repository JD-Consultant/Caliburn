import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { draftOP, getTaskCatalogs, recommendKS } from "@/lib/api";
import type { OptionItem, TaskCatalogEntry } from "@/types";

// 共用形狀:一份 per-task catalog（含 level）。O/P 暫不帶 code（階段2b 才消費）。
export interface TaskCatalogData {
  knowledge: OptionItem[];
  skills: OptionItem[];
  outputs: OptionItem[];
  indicators: { code: string; text: string }[];
  competency_level: number | null;
}

const STALE = 5 * 60 * 1000;
const catalogKey = (profileId: string, taskKey: string) => ["task-catalog", profileId, taskKey];

// 後備（快取未命中）：per-task 兩端點。批次 seeding 命中時不會跑到這裡。
async function fetchTaskCatalog(profileId: string, taskKey: string): Promise<TaskCatalogData> {
  const [ks, op] = await Promise.all([
    recommendKS({ profile_id: profileId, task_key: taskKey }),
    draftOP({ profile_id: profileId, task_key: taskKey }),
  ]);
  return {
    knowledge: ks.knowledge.map((k) => ({ code: k.code, name: k.name })),
    skills: ks.skills.map((s) => ({ code: s.code, name: s.name })),
    outputs: op.outputs.map((o) => ({ code: "", name: o.name })),
    indicators: op.indicators.map((i) => ({ code: "", text: i.text })),
    competency_level: ks.competency_level ?? null,
  };
}

// 批次回應 → 共用形狀（O/P 仍映 code:""，保留現行勾選判定行為）。
function fromEntry(e: TaskCatalogEntry): TaskCatalogData {
  return {
    knowledge: e.knowledge.map((k) => ({ code: k.code, name: k.name })),
    skills: e.skills.map((s) => ({ code: s.code, name: s.name })),
    outputs: e.outputs.map((o) => ({ code: "", name: o.name })),
    indicators: e.indicators.map((i) => ({ code: "", text: i.text })),
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

export function useTaskLevel(profileId: string, taskKey: string, enabled: boolean): number | null {
  const q = useQuery({
    queryKey: catalogKey(profileId, taskKey),
    enabled: enabled && !!taskKey,
    staleTime: STALE,
    queryFn: () => fetchTaskCatalog(profileId, taskKey),
    select: (d: TaskCatalogData) => d.competency_level,
  });
  return q.data ?? null;
}

export function useTaskCatalog(profileId: string, taskKey: string, enabled: boolean) {
  const q = useQuery({
    queryKey: catalogKey(profileId, taskKey),
    enabled: enabled && !!taskKey,
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
