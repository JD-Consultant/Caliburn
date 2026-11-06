/** JD HTTP 接縫：驗證輸入、完整回覆及所屬範圍；不重試或更新快取。 */
import type { ValidateFunction } from 'ajv';
import type {
  JobDescriptionContentResponse,
  JobDescriptionResponse,
} from '../../shared/api/generated/types.gen';
import {
  validateJobDescriptionResponse,
  validateExpectedVersionQuery,
} from '../../shared/api/generated/validators';
import {
  InvalidRequestError,
  InvalidResponseError,
  requestJson,
} from '../../shared/api/http';

export function jobDescriptionPath(workspaceId: string, jdId: string): string {
  return `/workspaces/${encodeURIComponent(workspaceId)}/job-descriptions/${encodeURIComponent(jdId)}`;
}

export function requireJobDescriptionScope(
  result: Pick<JobDescriptionContentResponse, 'workspace_id' | 'job_description_id'>,
  workspaceId: string,
  jdId: string,
): void {
  if (
    result.workspace_id.toLowerCase() !== workspaceId.toLowerCase() ||
    result.job_description_id.toLowerCase() !== jdId.toLowerCase()
  )
    throw new InvalidResponseError();
}

export function requireVersion(version: number): void {
  if (!validateExpectedVersionQuery(String(version))) throw new InvalidRequestError();
}

export async function requestJobDescription(
  workspaceId: string,
  jdId: string,
  suffix: string,
  options: RequestInit,
  expectedStatus: number | readonly number[] = 200,
): Promise<JobDescriptionResponse> {
  const result = await requestJson(
    jobDescriptionPath(workspaceId, jdId) + suffix,
    options,
    validateJobDescriptionResponse,
    expectedStatus,
  );
  requireJobDescriptionScope(result, workspaceId, jdId);
  return result;
}

export async function writeJobDescription<T>(
  workspaceId: string,
  jdId: string,
  suffix: string,
  method: 'POST' | 'PATCH' | 'PUT',
  body: T,
  validate: ValidateFunction<T>,
  expectedStatus: number | readonly number[] = 200,
): Promise<JobDescriptionResponse> {
  if (!validate(body)) throw new InvalidRequestError();
  return requestJobDescription(
    workspaceId,
    jdId,
    suffix,
    { method, body: JSON.stringify(body) },
    expectedStatus,
  );
}

export async function deleteJobDescriptionContent(
  workspaceId: string,
  jdId: string,
  suffix: string,
  expectedVersion: number,
): Promise<JobDescriptionResponse> {
  requireVersion(expectedVersion);
  const query = new URLSearchParams({ expected_version: String(expectedVersion) });
  return requestJobDescription(workspaceId, jdId, suffix + '?' + query.toString(), {
    method: 'DELETE',
  });
}
