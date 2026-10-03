/** Keep a file-scoped original command across reloads; this is not current metadata. */
import type { RenameJobFileRequest } from '../../shared/api/generated/rename-job-file-request';
import { isRenameJobFileRequest } from '../../shared/api/validation';

function storageKey(jobFileId: string): string {
  return `caliburn.pending-job-file-rename.${jobFileId}`;
}

export function readPendingRename(jobFileId: string): RenameJobFileRequest | null {
  const stored = sessionStorage.getItem(storageKey(jobFileId));
  if (stored === null) return null;
  const command: unknown = JSON.parse(stored);
  if (!isRenameJobFileRequest(command)) throw new Error('Invalid pending rename command');
  return command;
}

export function retainPendingRename(jobFileId: string, command: RenameJobFileRequest): void {
  sessionStorage.setItem(storageKey(jobFileId), JSON.stringify(command));
}

export function clearPendingRename(jobFileId: string): void {
  sessionStorage.removeItem(storageKey(jobFileId));
}
