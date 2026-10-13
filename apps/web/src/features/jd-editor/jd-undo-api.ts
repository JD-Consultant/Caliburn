/** The Turn identifies its original undo; never send a replacement revision or payload. */
import type { JdProfileView } from '../../shared/api/generated/http/types.gen';
import '../../shared/api/http';
import { undoCompletedJd } from '../../shared/api/generated/http/sdk.gen';

export function undoTurnJd(jobFileId: string, executionId: string): Promise<JdProfileView> {
  return undoCompletedJd({
    path: { job_file_id: jobFileId, execution_id: executionId },
    cache: 'no-store',
    throwOnError: true,
    meta: { correlation: { jobFileId, executionId } },
  }).then(({ data }) => data);
}
