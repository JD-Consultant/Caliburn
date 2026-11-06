/** Query keys keep publication navigation and source reads within one workspace. */
import { queryOptions } from '@tanstack/react-query';
import { getMemoryItem, getMemoryMap, getMemorySourceMessage } from './api';

export const memoryKeys = {
  all: (workspaceId: string) => ['memory', workspaceId.toLowerCase()] as const,
  map: (workspaceId: string) => [...memoryKeys.all(workspaceId), 'map'] as const,
  item: (workspaceId: string, publishedVersion: number, itemId: string) =>
    [
      ...memoryKeys.all(workspaceId),
      'item',
      publishedVersion,
      itemId.toLowerCase(),
    ] as const,
  source: (workspaceId: string, messageId: string) =>
    [...memoryKeys.all(workspaceId), 'source', messageId.toLowerCase()] as const,
};

export function memoryMapOptions(workspaceId: string) {
  return queryOptions({
    queryKey: memoryKeys.map(workspaceId),
    queryFn: ({ signal }) => getMemoryMap(workspaceId, signal),
    staleTime: 0,
  });
}

export function memoryItemOptions(
  workspaceId: string,
  publishedVersion: number,
  itemId: string,
) {
  return queryOptions({
    queryKey: memoryKeys.item(workspaceId, publishedVersion, itemId),
    queryFn: ({ signal }) => getMemoryItem(workspaceId, publishedVersion, itemId, signal),
  });
}

export function memorySourceOptions(workspaceId: string, messageId: string) {
  return queryOptions({
    queryKey: memoryKeys.source(workspaceId, messageId),
    queryFn: ({ signal }) => getMemorySourceMessage(workspaceId, messageId, signal),
  });
}
