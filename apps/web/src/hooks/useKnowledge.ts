import { useQuery } from "@tanstack/react-query";
import { getKnowledge } from "@/lib/api";

// 知識包(ADR 0021):選職類=唯一 knowledge 同步點,所有選單的資料源。
// persist + staleTime 24h(官方基準版本化不可變,與 persist maxAge 同節奏);
// 重選職類由 useSetOccupations invalidate + 背景 prefetch。
export const knowledgeKey = (profileId: string) => ["knowledge", profileId];

export function useKnowledge(profileId: string, enabled: boolean) {
  return useQuery({
    queryKey: knowledgeKey(profileId),
    queryFn: () => getKnowledge(profileId),
    enabled,
    staleTime: 1000 * 60 * 60 * 24,
    gcTime: 1000 * 60 * 60 * 24, // ≥ persist maxAge(24h),否則被 GC 早於還原期限
    refetchOnWindowFocus: false,
    meta: { persist: true },
  });
}
