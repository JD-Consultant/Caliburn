/** Job-file HTTP boundary. A failed creation is never retried with a new command here. */
import { queryOptions } from '@tanstack/react-query';
import type {
  CreateJobFileRequest,
  JobFile,
  RenameJobFileRequest,
} from '../../shared/api/generated/http/types.gen';

import { scope } from '../../shared/api/http';
import {
  listJobFiles,
  readJobFile,
  createJobFile as create,
  renameJobFile as rename,
  deleteJobFile as remove,
} from '../../shared/api/generated/http/sdk.gen';

export const jobFilesQuery = queryOptions({
  queryKey: ['job-files'],
  queryFn: ({ signal }) => listJobFiles({ signal, throwOnError: true }).then(({ data }) => data),
});

export function jobFileQuery(jobFileId: string) {
  return queryOptions({
    queryKey: ['job-file', jobFileId],
    queryFn: ({ signal }) =>
      readJobFile({
        path: { job_file_id: jobFileId },
        signal,
        throwOnError: true,
        meta: {
          correlation: { jobFileId },
          scope: scope<JobFile>((value) => value.job_file_id === jobFileId),
        },
      }).then(({ data }) => data),
  });
}

export function createJobFile(command: CreateJobFileRequest): Promise<JobFile> {
  return create({
    body: command,
    throwOnError: true,
    meta: { correlation: { commandId: command.command_id } },
  }).then(({ data }) => data);
}

export function renameJobFile(jobFileId: string, command: RenameJobFileRequest): Promise<JobFile> {
  return rename({
    path: { job_file_id: jobFileId },
    body: command,
    throwOnError: true,
    meta: {
      correlation: { jobFileId, commandId: command.command_id },
      scope: scope<JobFile>((value) => value.job_file_id === jobFileId),
    },
  }).then(({ data }) => data);
}

/** 刪除的空正文結果保持 void。 */
export function deleteJobFile(jobFileId: string): Promise<void> {
  return remove({ path: { job_file_id: jobFileId }, throwOnError: true }).then(() => undefined);
}
