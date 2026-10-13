/** One completed Turn owns its comparison endpoints; the UI only requests that Turn. */
import { queryOptions } from '@tanstack/react-query';

import type { TurnJdChanges } from '../../shared/api/generated/http/types.gen';
import { scope } from '../../shared/api/http';
import { readTurnJdChanges } from '../../shared/api/generated/http/sdk.gen';

export function turnJdChangesQuery(jobFileId: string, executionId: string) {
  return queryOptions({
    queryKey: ['turn-jd-changes', jobFileId, executionId],
    queryFn: ({ signal }) =>
      readTurnJdChanges({
        path: { job_file_id: jobFileId, execution_id: executionId },
        signal,
        throwOnError: true,
        meta: {
          correlation: { jobFileId, executionId },
          scope: scope<TurnJdChanges>((value) => value.execution_id === executionId),
        },
      }).then(({ data }) => data),
    retry: false,
    staleTime: Infinity,
  });
}
