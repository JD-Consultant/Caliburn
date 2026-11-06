import type { JobDescriptionResponse } from '../../shared/api/generated/types.gen';
import {
  validateJobDescriptionResponse,
  validateJobDescriptionErrorResponse,
} from '../../shared/api/generated/validators';
import { HttpError, InvalidResponseError, requestJson } from '../../shared/api/http';
import { requestJobDescription } from './api-transport';

const path = (workspaceId: string) =>
  `/workspaces/${encodeURIComponent(workspaceId)}/job-description`;

function isErrorCode(error: unknown, status: number, code: string): boolean {
  return (
    error instanceof HttpError &&
    error.status === status &&
    validateJobDescriptionErrorResponse(error.body) &&
    error.body.detail.code === code
  );
}

function inWorkspace(
  result: JobDescriptionResponse,
  workspaceId: string,
): JobDescriptionResponse {
  if (result.workspace_id.toLowerCase() !== workspaceId.toLowerCase())
    throw new InvalidResponseError();
  return result;
}

export function getJobDescription(
  workspaceId: string,
  jdId: string,
  signal?: AbortSignal,
): Promise<JobDescriptionResponse> {
  return requestJobDescription(workspaceId, jdId, '', { signal: signal ?? null });
}

export async function lookupJobDescription(
  workspaceId: string,
  signal?: AbortSignal,
): Promise<JobDescriptionResponse | null> {
  try {
    return inWorkspace(
      await requestJson(
        path(workspaceId),
        signal ? { signal } : {},
        validateJobDescriptionResponse,
      ),
      workspaceId,
    );
  } catch (error) {
    if (isErrorCode(error, 404, 'jd_not_found')) return null;
    throw error;
  }
}

export async function createJobDescription(
  workspaceId: string,
): Promise<JobDescriptionResponse> {
  try {
    return inWorkspace(
      await requestJson(
        path(workspaceId),
        { method: 'POST', body: '{}' },
        validateJobDescriptionResponse,
        201,
      ),
      workspaceId,
    );
  } catch (error) {
    if (isErrorCode(error, 409, 'jd_already_exists')) {
      const existing = await lookupJobDescription(workspaceId);
      if (existing) return existing;
    }
    throw error;
  }
}
