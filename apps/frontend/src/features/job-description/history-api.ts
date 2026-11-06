/** 保存點、結構化Diff與整份恢復；只接受指定JD及版本的回覆。 */
import type {
  HistoryPageResponse,
  HistoryResponse,
  JobDescriptionDifferenceResponse,
  JobDescriptionResponse,
  ListJobDescriptionHistoryData,
  RestoreJobDescriptionRequest,
} from '../../shared/api/generated/types.gen';
import {
  validateHistoryPageResponse,
  validateHistoryResponse,
  validateJobDescriptionDifferenceResponse,
  validateRestoreJobDescriptionRequest,
} from '../../shared/api/generated/validators';
import { InvalidResponseError, requestJson } from '../../shared/api/http';
import {
  jobDescriptionPath,
  requireJobDescriptionScope,
  requireVersion,
  writeJobDescription,
} from './api-transport';

export async function listHistory(
  workspaceId: string,
  jdId: string,
  query: ListJobDescriptionHistoryData['query'] = {},
  signal?: AbortSignal,
): Promise<HistoryPageResponse> {
  const parameters = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null) parameters.set(key, value);
  }
  const suffix = parameters.size ? '?' + parameters.toString() : '';
  const result = await requestJson(
    jobDescriptionPath(workspaceId, jdId) + '/history' + suffix,
    { signal: signal ?? null },
    validateHistoryPageResponse,
  );
  if (
    result.items.some(
      (entry) =>
        entry.job_description_id.toLowerCase() !== jdId.toLowerCase() ||
        (query.correlation_id != null && entry.correlation_id !== query.correlation_id) ||
        (query.reverts_correlation_id != null &&
          entry.reverts_correlation_id !== query.reverts_correlation_id),
    )
  )
    throw new InvalidResponseError();
  return result;
}
export async function getSnapshot(
  workspaceId: string,
  jdId: string,
  version: number,
  signal?: AbortSignal,
): Promise<HistoryResponse> {
  requireVersion(version);
  const result = await requestJson(
    jobDescriptionPath(workspaceId, jdId) + '/history/' + String(version),
    { signal: signal ?? null },
    validateHistoryResponse,
  );
  requireJobDescriptionScope(result.content, workspaceId, jdId);
  if (
    result.entry.job_description_id.toLowerCase() !== jdId.toLowerCase() ||
    result.entry.version !== version
  )
    throw new InvalidResponseError();
  return result;
}
export async function compareVersions(
  workspaceId: string,
  jdId: string,
  fromVersion: number,
  toVersion: number,
  signal?: AbortSignal,
): Promise<JobDescriptionDifferenceResponse> {
  requireVersion(fromVersion);
  requireVersion(toVersion);
  const query = new URLSearchParams({
    before_version: String(fromVersion),
    after_version: String(toVersion),
  });
  const result = await requestJson(
    jobDescriptionPath(workspaceId, jdId) + '/history:compare?' + query.toString(),
    { signal: signal ?? null },
    validateJobDescriptionDifferenceResponse,
  );
  if (
    result.job_description_id.toLowerCase() !== jdId.toLowerCase() ||
    result.before_version !== fromVersion ||
    result.after_version !== toVersion
  )
    throw new InvalidResponseError();
  return result;
}
export function restoreVersion(
  workspaceId: string,
  jdId: string,
  body: RestoreJobDescriptionRequest,
): Promise<JobDescriptionResponse> {
  return writeJobDescription(
    workspaceId,
    jdId,
    ':restore',
    'POST',
    body,
    validateRestoreJobDescriptionRequest,
  );
}
