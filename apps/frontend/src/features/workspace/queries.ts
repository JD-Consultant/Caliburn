import { infiniteQueryOptions, queryOptions } from '@tanstack/react-query';
import { getWorkspace, listWorkspaces } from './api';

export const workspaceListKey = ['workspaces'] as const;
export const workspaceListOptions = infiniteQueryOptions({
  queryKey: workspaceListKey,
  initialPageParam: null as string | null,
  queryFn: ({ pageParam, signal }) => listWorkspaces(pageParam, signal),
  getNextPageParam: (page) => page.next_cursor,
});
export function workspaceOptions(workspaceId: string) {
  return queryOptions({
    queryKey: ['workspace', workspaceId.toLowerCase()],
    queryFn: ({ signal }) => getWorkspace(workspaceId, signal),
  });
}
