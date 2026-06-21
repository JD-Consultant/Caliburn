import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  finalizeDocument,
  getDocument,
  getKsaPool,
  patchDocument,
  seedDocument,
} from "@/lib/api";
import type { DocumentEnvelope, OcsDocument } from "@/types";

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

export function useSeedDocument(profileId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ocsCodes: string[]) => seedDocument(profileId, ocsCodes),
    onSuccess: (env: DocumentEnvelope) => {
      qc.setQueryData(["document", profileId], env);
      qc.invalidateQueries({ queryKey: ["profiles"] });
    },
  });
}
