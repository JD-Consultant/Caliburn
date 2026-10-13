/** Saved summary projection from the original Turn; no new model request or browser persistence. */
import { queryOptions } from '@tanstack/react-query';
import type { ReasoningSummary } from '../../shared/api/generated/http/types.gen';
import '../../shared/api/http';
import { readReasoningSummaries } from '../../shared/api/generated/http/sdk.gen';

export function reasoningSummariesQuery(jobFileId: string, executionId: string) {
  return queryOptions({
    queryKey: ['reasoning-summaries', jobFileId, executionId],
    queryFn: ({ signal }) =>
      readReasoningSummaries({
        path: { job_file_id: jobFileId, execution_id: executionId },
        signal,
        cache: 'no-store',
        throwOnError: true,
      }).then(({ data }) => data),
    retry: false,
    staleTime: 0,
    gcTime: 0,
    refetchOnMount: 'always',
    refetchOnWindowFocus: false,
  });
}

export function summaryKey(summary: ReasoningSummary): string {
  return JSON.stringify([summary.response_id, summary.item_id, summary.summary_index]);
}
