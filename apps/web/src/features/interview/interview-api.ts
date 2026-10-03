import { queryOptions } from '@tanstack/react-query';
import { requestJson } from '../../shared/api/http';
import { isInterviewHistory } from '../../shared/api/validation';

export function interviewHistoryQuery(jobFileId: string) {
  return queryOptions({
    queryKey: ['job-file', jobFileId, 'formal-interviews'],
    queryFn: ({ signal }) =>
      requestJson(
        `/api/job-files/${encodeURIComponent(jobFileId)}/interviews`,
        isInterviewHistory,
        { signal },
      ),
  });
}
