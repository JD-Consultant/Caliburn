// 訪談引擎 hooks(T10;ADR 0023)。
// 關鍵接線:`interview:turn` 後 server 端引擎可能已改文件 → invalidate ["document", id]
// → data-layer 的「外部變化 effect」自動重設 autosave baseline(見 docs/data-layer.md §2.4;
// 引擎寫入=外部變化,零新機制)。interview view 是唯讀稽核/續談資料,不持久化。
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  finishInterview,
  getInterview,
  interviewTurn,
  startInterview,
} from "@/lib/api";

export const interviewKey = (profileId: string) => ["interview", profileId] as const;

export function useInterview(profileId: string, enabled = true) {
  return useQuery({
    queryKey: interviewKey(profileId),
    queryFn: () => getInterview(profileId),
    enabled: !!profileId && enabled,
    staleTime: 0,
    retry: (count, err: unknown) => {
      // 404 = 尚無訪談(正常狀態),不重試
      const status = (err as { status?: number } | null)?.status;
      return status !== 404 && count < 2;
    },
  });
}

export function useStartInterview(profileId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => startInterview(profileId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: interviewKey(profileId) });
    },
  });
}

export function useInterviewTurn(profileId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (text: string) => interviewTurn(profileId, text),
    onSuccess: (res) => {
      void qc.invalidateQueries({ queryKey: interviewKey(profileId) });
      if (res.doc_changed) {
        // 引擎寫了文件 → 讓 document cache 重抓,autosave baseline 由外部變化路徑重設
        void qc.invalidateQueries({ queryKey: ["document", profileId] });
      }
    },
  });
}

// 收尾對帳(T10):態度綠標可能落文件 → 一併 invalidate document。
export function useFinishInterview(profileId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => finishInterview(profileId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: interviewKey(profileId) });
      void qc.invalidateQueries({ queryKey: ["document", profileId] });
    },
  });
}

// useReviewInterview(建議層批審)已退場(T12;ADR 0030):
// ✓/✗ 走 JobDocTable 的 acceptPending/rejectPending + PATCH + review-events。
