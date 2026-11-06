import type {
  CreateWorkspaceRequest,
  RenameWorkspaceRequest,
  WorkspacePageResponse,
  WorkspaceResponse,
} from '../../shared/api/generated/types.gen';
import {
  validateWorkspacePageResponse,
  validateWorkspaceResponse,
} from '../../shared/api/generated/validators';
import { InvalidResponseError, requestEmpty, requestJson } from '../../shared/api/http';

const path = (workspaceId: string) => '/workspaces/' + encodeURIComponent(workspaceId);

function inWorkspace(
  workspace: WorkspaceResponse,
  workspaceId: string,
): WorkspaceResponse {
  if (workspace.workspace_id.toLowerCase() !== workspaceId.toLowerCase())
    throw new InvalidResponseError();
  return workspace;
}

export function listWorkspaces(
  after: string | null,
  signal?: AbortSignal,
): Promise<WorkspacePageResponse> {
  const query = new URLSearchParams({ limit: '20' });
  if (after) query.set('after', after);
  return requestJson(
    '/workspaces?' + query.toString(),
    { signal: signal ?? null },
    validateWorkspacePageResponse,
  );
}
export async function getWorkspace(
  workspaceId: string,
  signal?: AbortSignal,
): Promise<WorkspaceResponse> {
  return inWorkspace(
    await requestJson(
      path(workspaceId),
      { signal: signal ?? null },
      validateWorkspaceResponse,
    ),
    workspaceId,
  );
}
export function createWorkspace(
  body: CreateWorkspaceRequest,
): Promise<WorkspaceResponse> {
  return requestJson(
    '/workspaces',
    { method: 'POST', body: JSON.stringify(body) },
    validateWorkspaceResponse,
    201,
  );
}
export async function renameWorkspace(
  workspaceId: string,
  body: RenameWorkspaceRequest,
): Promise<WorkspaceResponse> {
  return inWorkspace(
    await requestJson(
      path(workspaceId),
      { method: 'PATCH', body: JSON.stringify(body) },
      validateWorkspaceResponse,
    ),
    workspaceId,
  );
}
export function deleteWorkspace(workspaceId: string): Promise<void> {
  return requestEmpty(path(workspaceId), { method: 'DELETE' });
}
