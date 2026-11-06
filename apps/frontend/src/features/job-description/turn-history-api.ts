import type {
  JobDescriptionResponse,
  JobDescriptionTurnChangesResponse,
} from '../../shared/api/generated/types.gen';
import { validateJobDescriptionTurnChangesResponse } from '../../shared/api/generated/validators';
import { InvalidResponseError, requestJson } from '../../shared/api/http';
import {
  jobDescriptionPath,
  requestJobDescription,
  requireJobDescriptionScope,
} from './api-transport';

export async function getTurnChanges(
  workspaceId: string,
  jdId: string,
  turnId: string,
  signal?: AbortSignal,
): Promise<JobDescriptionTurnChangesResponse> {
  const result = await requestJson(
    jobDescriptionPath(workspaceId, jdId) +
      `/turns/${encodeURIComponent(turnId)}/changes`,
    { signal: signal ?? null },
    validateJobDescriptionTurnChangesResponse,
  );
  requireJobDescriptionScope(result, workspaceId, jdId);
  requireJobDescriptionScope(result.before, workspaceId, jdId);
  requireJobDescriptionScope(result.after, workspaceId, jdId);
  if (
    result.turn_id.toLowerCase() !== turnId.toLowerCase() ||
    result.difference.job_description_id.toLowerCase() !== jdId.toLowerCase() ||
    result.difference.before_version !== result.before_version ||
    result.difference.after_version !== result.after_version
  )
    throw new InvalidResponseError();
  return result;
}

/** The completed-turn endpoint owns its safety guard and reentrant restoration. */
export function restoreTurnChanges(
  workspaceId: string,
  jdId: string,
  turnId: string,
): Promise<JobDescriptionResponse> {
  return requestJobDescription(
    workspaceId,
    jdId,
    `/turns/${encodeURIComponent(turnId)}:restore`,
    { method: 'POST' },
  );
}
