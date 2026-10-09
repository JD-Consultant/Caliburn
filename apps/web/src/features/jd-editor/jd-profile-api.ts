/** Formal JD profile query/command; a recovered command result is not the latest view. */
import { queryOptions } from '@tanstack/react-query';
import type { JdProfileView } from '../../shared/api/generated/jd-profile-view';
import type { ReviseJdProfileRequest } from '../../shared/api/generated/revise-jd-profile-request';
import { requestJson } from '../../shared/api/http';
import { isJdProfileView } from '../../shared/api/validation';

function profileUrl(jobFileId: string): string {
  return `/api/job-files/${encodeURIComponent(jobFileId)}/jd/profile`;
}

export function jdProfileQuery(jobFileId: string) {
  return queryOptions({
    queryKey: ['jd-profile', jobFileId, 'formal'],
    queryFn: ({ signal }) => requestJson(profileUrl(jobFileId), isJdProfileView, { signal }),
  });
}

export function reviseJdProfile(
  jobFileId: string,
  command: ReviseJdProfileRequest,
): Promise<JdProfileView> {
  return requestJson(profileUrl(jobFileId), isJdProfileView, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(command),
    correlation: { jobFileId, commandId: command.command_id },
  });
}
