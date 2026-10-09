import type { QueryClient, InvalidateQueryFilters } from '@tanstack/react-query';

/** A confirmed write requires reads started after it, including a query's very first GET. */
export async function refreshQueries(
  cache: QueryClient,
  queries: readonly InvalidateQueryFilters[],
): Promise<void> {
  await Promise.all(queries.map((query) => cache.cancelQueries(query)));
  await Promise.all(queries.map((query) => cache.invalidateQueries(query, { throwOnError: true })));
}
