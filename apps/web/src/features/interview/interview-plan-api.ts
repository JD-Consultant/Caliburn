/** One file cache owns adopted text; terminal refresh never reuses an earlier GET. */
import { queryOptions } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import type { InterviewPlanView } from '../../shared/api/generated/http/types.gen';
import { scope } from '../../shared/api/http';
import { readAdoptedInterviewPlan } from '../../shared/api/generated/http/sdk.gen';
import { refreshQueries } from '../../shared/api/refresh-queries';

export function interviewPlanQuery(jobFileId: string) {
  return queryOptions({
    queryKey: ['job-file', jobFileId, 'interview-plan'],
    queryFn: ({ signal }) =>
      readAdoptedInterviewPlan({
        path: { job_file_id: jobFileId },
        signal,
        cache: 'no-store',
        throwOnError: true,
        meta: {
          correlation: { jobFileId },
          scope: scope<InterviewPlanView>((value) => value.job_file_id === jobFileId),
        },
      }).then(({ data }) => data),
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
