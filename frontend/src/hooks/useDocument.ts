import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  buildTasks,
  finalizeDocument,
  getDocument,
  getKsaPool,
  getTaskCandidates,
  patchDocument,
  setOccupations,
} from "@/lib/api";
import type { DocumentEnvelope, OcsDocument, PickedTask } from "@/types";

// D27 工作台資料層。document = of-record（draft/final/none 空殼）；mutation 成功後
// 直接 setQueryData 更新快取（即時反映），finalize/seed 另 invalidate profiles（dashboard 狀態）。

export function useDocument(profileId: string) {
  return useQuery({
    queryKey: ["document", profileId],
    queryFn: () => getDocument(profileId),
    refetchOnWindowFocus: false,
  });
}

export function useKsaPool(profileId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["ksa-pool", profileId],
    queryFn: () => getKsaPool(profileId),
    enabled,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}

export function usePatchDocument(profileId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (content: OcsDocument) => patchDocument(profileId, content),
    onSuccess: (env: DocumentEnvelope) =>
      qc.setQueryData(["document", profileId], env),
  });
}

export function useFinalizeDocument(profileId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => finalizeDocument(profileId),
    onSuccess: (env: DocumentEnvelope) => {
      qc.setQueryData(["document", profileId], env);
      qc.invalidateQueries({ queryKey: ["profiles"] });
    },
  });
}

export function useSetOccupations(profileId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ocsCodes: string[]) => setOccupations(profileId, ocsCodes),
    onSuccess: () => {
      // 重抓 document（GET 空殼會用新 selected codes 帶表頭）+ 候選池/候選任務。
      qc.invalidateQueries({ queryKey: ["document", profileId] });
      qc.invalidateQueries({ queryKey: ["ksa-pool", profileId] });
      qc.invalidateQueries({ queryKey: ["task-candidates", profileId] });
    },
  });
}

export function useTaskCandidates(profileId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["task-candidates", profileId],
    queryFn: () => getTaskCandidates(profileId),
    enabled,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}

export function useBuildTasks(profileId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (picked: PickedTask[]) => buildTasks(profileId, picked),
    onSuccess: (env: DocumentEnvelope) => {
      qc.setQueryData(["document", profileId], env);
      qc.invalidateQueries({ queryKey: ["profiles"] });
    },
  });
}
