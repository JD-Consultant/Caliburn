/** Saved tool calls of one completed Turn, read only when requested. */
import { queryOptions } from '@tanstack/react-query';

import type { TurnTools } from '../../shared/api/generated/http/types.gen';
import { scope } from '../../shared/api/http';
import { readTurnTools } from '../../shared/api/generated/http/sdk.gen';

export function turnToolsQuery(jobFileId: string, executionId: string) {
  return queryOptions({
    queryKey: ['turn-tools', jobFileId, executionId],
    queryFn: ({ signal }) =>
      readTurnTools({
        path: { job_file_id: jobFileId, execution_id: executionId },
        signal,
        throwOnError: true,
        meta: {
          correlation: { jobFileId, executionId },
          scope: scope<TurnTools>((value) => value.execution_id === executionId),
        },
      }).then(({ data }) => data),
    retry: false,
    staleTime: Infinity,
  });
}
