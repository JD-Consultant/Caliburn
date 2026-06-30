import { useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useDebouncedCallback } from "use-debounce";
import {
  buildTasks,
  finalizeDocument,
  getDocument,
  getHeaderMeta,
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

export function useHeaderMeta(profileId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["header-meta", profileId],
    queryFn: () => getHeaderMeta(profileId),
    enabled,
    staleTime: 5 * 60 * 1000,
    gcTime: 1000 * 60 * 60 * 24, // ≥ persist maxAge(24h)
    refetchOnWindowFocus: false,
    meta: { persist: true }, // 准予持久化（spec D-1d）
  });
}

export function usePatchDocument(profileId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (content: OcsDocument) => patchDocument(profileId, content),
    onMutate: async (content: OcsDocument) => {
      await qc.cancelQueries({ queryKey: ["document", profileId] });
      const prev = qc.getQueryData<DocumentEnvelope>(["document", profileId]);
      qc.setQueryData<DocumentEnvelope>(["document", profileId], (old) =>
        old ? { ...old, content } : old,
      );
      return { prev };
    },
    onError: (_e, _content, ctx) => {
      if (ctx?.prev) qc.setQueryData(["document", profileId], ctx.prev);
    },
    onSuccess: (env: DocumentEnvelope) =>
      qc.setQueryData<DocumentEnvelope>(["document", profileId], (old) =>
        old ? { ...env, content: old.content } : env,
      ),
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
      qc.invalidateQueries({ queryKey: ["task-candidates", profileId] });
      // header-meta（職能基準代碼選單/所屬類別/態度候選）也要隨選的職類更新，否則
      // 第二次選職類時主基準下拉不會刷新。
      qc.invalidateQueries({ queryKey: ["header-meta", profileId] });
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

export function useAutosaveDocument(profileId: string) {
  const qc = useQueryClient();
  const patch = usePatchDocument(profileId);
  const latest = useRef<OcsDocument | undefined>(undefined);
  const flushPatch = useDebouncedCallback(() => {
    if (latest.current) patch.mutate(latest.current);
  }, 500);
  const commit = (next: OcsDocument) => {
    latest.current = next;
    qc.setQueryData<DocumentEnvelope>(["document", profileId], (old) =>
      old ? { ...old, content: next } : old,
    );
    flushPatch();
  };
  const env = qc.getQueryData<DocumentEnvelope>(["document", profileId]);
  const status = patch.isPending
    ? "saving"
    : patch.isError
      ? "error"
      : patch.isSuccess
        ? "saved"
        : "idle";
  return {
    doc: env?.content,
    status: status as "idle" | "saving" | "saved" | "error",
    commit,
    flush: () => flushPatch.flush(),
  };
}
