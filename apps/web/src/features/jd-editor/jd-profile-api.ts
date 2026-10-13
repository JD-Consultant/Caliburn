/** Formal JD profile query/command; a recovered command result is not the latest view. */
import { queryOptions } from '@tanstack/react-query';
import type {
  JdProfileView,
  ReviseJdProfileRequest,
} from '../../shared/api/generated/http/types.gen';

import '../../shared/api/http';
import { readJdProfile, reviseJdProfile as revise } from '../../shared/api/generated/http/sdk.gen';

export function jdProfileQuery(jobFileId: string) {
  return queryOptions({
    queryKey: ['jd-profile', jobFileId, 'formal'],
    queryFn: ({ signal }) =>
      readJdProfile({ path: { job_file_id: jobFileId }, signal, throwOnError: true }).then(
        ({ data }) => data,
      ),
  });
}

export function reviseJdProfile(
  jobFileId: string,
  command: ReviseJdProfileRequest,
): Promise<JdProfileView> {
  return revise({
    path: { job_file_id: jobFileId },
    body: command,
    throwOnError: true,
    meta: { correlation: { jobFileId, commandId: command.command_id } },
  }).then(({ data }) => data);
}
