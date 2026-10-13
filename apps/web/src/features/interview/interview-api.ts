import { queryOptions } from '@tanstack/react-query';
import '../../shared/api/http';
import { readInterviewHistory } from '../../shared/api/generated/http/sdk.gen';

export function interviewHistoryQuery(jobFileId: string) {
  return queryOptions({
    queryKey: ['job-file', jobFileId, 'formal-interviews'],
    queryFn: ({ signal }) =>
      readInterviewHistory({ path: { job_file_id: jobFileId }, signal, throwOnError: true }).then(
        ({ data }) => data,
      ),
  });
}
