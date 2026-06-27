import { useQuery } from "@tanstack/react-query";
import { draftOP, recommendKS } from "@/lib/api";
import type { OptionItem } from "@/types";

// 任務的官方級別（competency_level）。只有 enabled（如下拉開啟）時才查；無 note → 不跑 LLM、快。
export function useTaskLevel(profileId: string, taskKey: string, enabled: boolean): number | null {
  const q = useQuery({
    queryKey: ["task-level", profileId, taskKey],
    enabled: enabled && !!taskKey,
    staleTime: 5 * 60 * 1000,
    queryFn: async () => {
      const ks = await recommendKS({ profile_id: profileId, task_key: taskKey });
      return ks.competency_level ?? null;
    },
  });
  return q.data ?? null;
}

export function useTaskCatalog(profileId: string, taskKey: string, enabled: boolean) {
  const q = useQuery({
    queryKey: ["task-catalog", profileId, taskKey],
    enabled: enabled && !!taskKey,
    staleTime: 5 * 60 * 1000,
    queryFn: async () => {
      const [ks, op] = await Promise.all([
        recommendKS({ profile_id: profileId, task_key: taskKey }),
        draftOP({ profile_id: profileId, task_key: taskKey }),
      ]);
      return {
        knowledge: ks.knowledge.map((k) => ({ code: k.code, name: k.name })) as OptionItem[],
        skills: ks.skills.map((s) => ({ code: s.code, name: s.name })) as OptionItem[],
        outputs: op.outputs.map((o) => ({ code: "", name: o.name })) as OptionItem[],
        indicators: op.indicators.map((i) => ({ code: "", text: i.text })),
      };
    },
  });
  return {
    knowledge: q.data?.knowledge ?? [], skills: q.data?.skills ?? [],
    outputs: q.data?.outputs ?? [], indicators: q.data?.indicators ?? [],
    isLoading: q.isLoading,
  };
}
