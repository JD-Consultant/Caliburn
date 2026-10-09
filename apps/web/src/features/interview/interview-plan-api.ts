/** One file cache owns adopted text; terminal refresh never reuses an earlier GET. */
import { queryOptions } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import type { InterviewPlanView } from '../../shared/api/generated/interview-plan-view';
import { ApiError, requestJson } from '../../shared/api/http';
import { isInterviewPlanView } from '../../shared/api/validation';
import { refreshQueries } from '../../shared/api/refresh-queries';

export function interviewPlanQuery(jobFileId: string) {
  return queryOptions({
    queryKey: ['job-file', jobFileId, 'interview-plan'],
    queryFn: async ({ signal }) => {
      const plan = await requestJson(
        `/api/job-files/${encodeURIComponent(jobFileId)}/interview-plan`,
        isInterviewPlanView,
        { signal, cache: 'no-store' },
      );
      if (plan.job_file_id !== jobFileId) {
        throw new ApiError('收到的工作計畫不屬於這份職務檔案，尚未採用。');
      }
      return plan;
    },
    retry: false,
    staleTime: 0,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

const terminalRefreshes = new WeakMap<QueryClient, Map<string, Promise<InterviewPlanView>>>();

/** Repeated observers share this exact terminal refresh, including under StrictMode. */
export function refreshTerminalInterviewPlan(
  queryClient: QueryClient,
  jobFileId: string,
  executionId: string,
): Promise<InterviewPlanView> {
  let pending = terminalRefreshes.get(queryClient);
  if (!pending) {
    pending = new Map();
    terminalRefreshes.set(queryClient, pending);
  }
  const scope = `${jobFileId}:${executionId}`;
  const existing = pending.get(scope);
  if (existing) return existing;
  const query = interviewPlanQuery(jobFileId);
  const refresh = (async () => {
    try {
      await refreshQueries(queryClient, [
        {
          queryKey: query.queryKey,
          exact: true,
          refetchType: 'none',
        },
      ]);
      return await queryClient.query({ ...query, staleTime: 0 });
    } finally {
      pending.delete(scope);
    }
  })();
  pending.set(scope, refresh);
  return refresh;
}
