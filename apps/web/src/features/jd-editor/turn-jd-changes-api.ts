/** One completed Turn owns its comparison endpoints; the UI only requests that Turn. */
import { queryOptions } from '@tanstack/react-query';
import { Ajv2020 } from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import schema from '../../../../api/contracts/http/turn-jd-changes.schema.json' with { type: 'json' };
import type { TurnJdChanges } from '../../shared/api/generated/turn-jd-changes';
import { ApiError, requestJson } from '../../shared/api/http';

const validator = new Ajv2020();
addFormats(validator);
const isTurnJdChanges = validator.compile<TurnJdChanges>(schema);

export function turnJdChangesQuery(jobFileId: string, executionId: string) {
  return queryOptions({
    queryKey: ['turn-jd-changes', jobFileId, executionId],
    queryFn: async ({ signal }) => {
      const result = await requestJson(
        `/api/job-files/${encodeURIComponent(jobFileId)}/consultant-turns/${encodeURIComponent(executionId)}/jd-changes`,
        isTurnJdChanges,
        { signal },
      );
      if (result.execution_id !== executionId) {
        throw new ApiError('無法核對這輪 JD 變更的身分，請重新讀取。');
      }
      return result;
    },
    retry: false,
    staleTime: Infinity,
  });
}
