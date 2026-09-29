/** Job-file HTTP boundary. A failed creation is never retried with a new command here. */
import { queryOptions } from '@tanstack/react-query';
import type { CreateJobFileRequest } from '../../shared/api/generated/create-job-file-request';
import type { JobFile } from '../../shared/api/generated/job-file-list';
import type { RenameJobFileRequest } from '../../shared/api/generated/rename-job-file-request';
import { requestJson } from '../../shared/api/http';
import { isJobFile, isJobFileList } from '../../shared/api/validation';

export const jobFilesQuery = queryOptions({
  queryKey: ['job-files'],
  queryFn: ({ signal }) => requestJson('/api/job-files', isJobFileList, { signal }),
});

export function jobFileQuery(jobFileId: string) {
  return queryOptions({
    queryKey: ['job-file', jobFileId],
    queryFn: ({ signal }) =>
      requestJson(`/api/job-files/${encodeURIComponent(jobFileId)}`, isJobFile, { signal }),
  });
}

export function createJobFile(command: CreateJobFileRequest): Promise<JobFile> {
  return requestJson('/api/job-files', isJobFile, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(command),
  });
}

export function renameJobFile(jobFileId: string, command: RenameJobFileRequest): Promise<JobFile> {
  return requestJson(`/api/job-files/${encodeURIComponent(jobFileId)}/rename`, isJobFile, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(command),
  });
}
