import type { QueryClient } from '@tanstack/react-query';
import { workspaceOptions } from '../features/workspace/queries';
import { jobDescriptionOptions } from '../features/job-description/queries';
import { interviewKeys } from '../features/interview/queries';
import { memoryKeys } from '../features/memory/queries';

/** App owns cross-feature refresh; tool names never determine persisted effects. */
export async function refreshWorkspaceQueries(cache: QueryClient, workspaceId: string) {
  await Promise.all(
    [
      jobDescriptionOptions(workspaceId).queryKey,
      interviewKeys.all(workspaceId),
      memoryKeys.all(workspaceId),
    ].map((queryKey) => cache.invalidateQueries({ queryKey })),
  );
}

/** Cancel in-flight reads before removal, so late responses cannot revive a deleted workspace. */
export async function clearWorkspaceQueries(cache: QueryClient, workspaceId: string) {
  const keys = [workspaceOptions(workspaceId).queryKey, memoryKeys.all(workspaceId)];
  await Promise.all(keys.map((queryKey) => cache.cancelQueries({ queryKey })));
  for (const queryKey of keys) cache.removeQueries({ queryKey });
}
