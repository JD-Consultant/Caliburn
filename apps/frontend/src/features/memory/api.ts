/** Published Memory reads validate the requested workspace and fixed item identity. */
import type {
  MemoryItemResponse,
  MemoryMapResponse,
  MessageView,
} from '../../shared/api/generated/types.gen';
import {
  validateMemoryItemResponse,
  validateMemoryMapResponse,
  validateMessageView,
} from '../../shared/api/generated/validators';
import { InvalidResponseError, requestJson } from '../../shared/api/http';

const workspacePath = (workspaceId: string) =>
  '/workspaces/' + encodeURIComponent(workspaceId);

export async function getMemoryMap(
  workspaceId: string,
  signal?: AbortSignal,
): Promise<MemoryMapResponse> {
  const result = await requestJson(
    workspacePath(workspaceId) + '/memory',
    { signal: signal ?? null },
    validateMemoryMapResponse,
  );
  if (result.workspace_id.toLowerCase() !== workspaceId.toLowerCase())
    throw new InvalidResponseError();
  return result;
}

export async function getMemoryItem(
  workspaceId: string,
  publishedVersion: number,
  itemId: string,
  signal?: AbortSignal,
): Promise<MemoryItemResponse> {
  const result = await requestJson(
    `${workspacePath(workspaceId)}/memory/versions/${publishedVersion}/items/${encodeURIComponent(itemId)}`,
    { signal: signal ?? null },
    validateMemoryItemResponse,
  );
  if (
    result.workspace_id.toLowerCase() !== workspaceId.toLowerCase() ||
    result.published_version !== publishedVersion ||
    result.item_id.toLowerCase() !== itemId.toLowerCase()
  )
    throw new InvalidResponseError();
  return result;
}

export async function getMemorySourceMessage(
  workspaceId: string,
  messageId: string,
  signal?: AbortSignal,
): Promise<MessageView> {
  const result = await requestJson(
    `${workspacePath(workspaceId)}/interview/messages/${encodeURIComponent(messageId)}`,
    { signal: signal ?? null },
    validateMessageView,
  );
  if (result.message_id.toLowerCase() !== messageId.toLowerCase())
    throw new InvalidResponseError();
  return result;
}
