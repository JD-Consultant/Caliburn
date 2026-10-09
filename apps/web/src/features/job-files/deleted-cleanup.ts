import type { QueryClient } from '@tanstack/react-query';
/** All file-scoped query keys put the identity in their second segment. */
export async function clearDeletedJobFileQueries(
  cache: QueryClient,
  jobFileId: string,
): Promise<void> {
  const scoped = {
    predicate: (query: { queryKey: readonly unknown[] }) => query.queryKey[1] === jobFileId,
  };
  await cache.cancelQueries(scoped);
  cache.removeQueries(scoped);
}
