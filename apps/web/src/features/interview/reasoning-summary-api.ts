/** Saved summary projection from the original Turn; no new model request or browser persistence. */
import { queryOptions } from '@tanstack/react-query';
import type { ReasoningSummary } from '../../shared/api/generated/reasoning-summary';
import { requestJson } from '../../shared/api/http';
import { isReasoningSummaryList } from '../../shared/api/validation';

export function reasoningSummariesQuery(jobFileId: string, executionId: string) {
  return queryOptions({
    queryKey: ['reasoning-summaries', jobFileId, executionId],
    queryFn: ({ signal }) =>
      requestJson(
        `/api/job-files/${encodeURIComponent(jobFileId)}/consultant-turns/${encodeURIComponent(executionId)}/reasoning-summaries`,
        isReasoningSummaryList,
        { signal, cache: 'no-store' },
      ),
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
