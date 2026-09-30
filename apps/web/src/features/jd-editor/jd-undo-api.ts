/** The Turn identifies its original undo; never send a replacement revision or payload. */
import type { JdProfileView } from '../../shared/api/generated/jd-profile-view';
import { requestJson } from '../../shared/api/http';
import { isJdProfileView } from '../../shared/api/validation';

export function undoTurnJd(jobFileId: string, executionId: string): Promise<JdProfileView> {
  return requestJson(
    `/api/job-files/${encodeURIComponent(jobFileId)}/consultant-turns/${encodeURIComponent(executionId)}/undo-jd`,
    isJdProfileView,
    { method: 'POST', cache: 'no-store' },
  );
}
