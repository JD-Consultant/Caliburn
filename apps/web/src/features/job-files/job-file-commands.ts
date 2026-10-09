/** File command payloads, rejection policy and recovery slots. */
import type { QueryClient } from '@tanstack/react-query';
import type { CreateJobFileRequest } from '../../shared/api/generated/create-job-file-request';
import type { RenameJobFileRequest } from '../../shared/api/generated/rename-job-file-request';
import type { JobFile } from '../../shared/api/generated/job-file-list';
import { ApiError } from '../../shared/api/http';
import { refreshQueries } from '../../shared/api/refresh-queries';
import { isCreateJobFileRequest, isRenameJobFileRequest } from '../../shared/api/validation';
import { createPendingCommandStore } from '../../shared/commands/pending-command';
import type { PendingCommandStore } from '../../shared/commands/pending-command';
import type { StoredCommand } from '../../shared/commands/use-stored-command';
import { createJobFile, jobFileQuery, jobFilesQuery, renameJobFile } from './job-file-api';

export const pendingCreation = createPendingCommandStore<CreateJobFileRequest>({
  key: 'caliburn.pending-job-file-creation',
  isCommand: isCreateJobFileRequest,
  matches: (left, right) =>
    left.command_id === right.command_id &&
    left.display_name === right.display_name &&
    left.employee_name === right.employee_name,
});

export function pendingRename(jobFileId: string): PendingCommandStore<RenameJobFileRequest> {
  return createPendingCommandStore<RenameJobFileRequest>({
    key: `caliburn.pending-job-file-rename.${jobFileId}`,
    isCommand: isRenameJobFileRequest,
    matches: (left, right) =>
      left.command_id === right.command_id &&
      left.expected_name_revision === right.expected_name_revision &&
      left.display_name === right.display_name,
  });
}

export type CreationRejection = 'conflict' | 'deleted';

export function creationCommand(
  cache: QueryClient,
): StoredCommand<CreateJobFileRequest, JobFile, CreationRejection> {
  return {
    store: pendingCreation,
    execute: createJobFile,
    classifyRejection: (error: unknown) => {
      if (!(error instanceof ApiError)) return null;
      if (error.status === 410 && error.code === 'creation_result_deleted')
        return { reason: 'deleted', refresh: true };
      if (error.status === 409 && error.code === 'creation_command_conflict')
        return { reason: 'conflict' };
      return null;
    },
    refresh: () => refreshQueries(cache, [{ queryKey: jobFilesQuery.queryKey, exact: true }]),
  };
}

export function renameCommand(
  jobFileId: string,
  cache: QueryClient,
): StoredCommand<RenameJobFileRequest, JobFile> {
  return {
    store: pendingRename(jobFileId),
    execute: (command: RenameJobFileRequest) => renameJobFile(jobFileId, command),
    classifyRejection: (error: unknown) =>
      error instanceof ApiError &&
      error.status === 409 &&
      (error.code === 'rename_command_conflict' || error.code === 'stale_job_file_name')
        ? { reason: 'refused' }
        : null,
    refresh: () =>
      refreshQueries(cache, [
        { queryKey: jobFileQuery(jobFileId).queryKey, exact: true },
        { queryKey: jobFilesQuery.queryKey, exact: true },
      ]),
  };
}
