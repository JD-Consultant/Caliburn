/** One tab's unacknowledged transport command, never a saved-file authority. */
import type { CreateJobFileRequest } from '../../shared/api/generated/create-job-file-request';
import { isCreateJobFileRequest } from '../../shared/api/validation';

const storageKey = 'caliburn.pending-job-file-creation';

export function readPendingCreation(): CreateJobFileRequest | null {
  const stored = sessionStorage.getItem(storageKey);
  if (stored === null) return null;
  const command: unknown = JSON.parse(stored);
  if (!isCreateJobFileRequest(command)) throw new Error('Invalid pending creation command');
  return command;
}

export function retainPendingCreation(command: CreateJobFileRequest): void {
  sessionStorage.setItem(storageKey, JSON.stringify(command));
}

export function clearPendingCreation(): void {
  sessionStorage.removeItem(storageKey);
}
