import { queryOptions, type QueryClient } from '@tanstack/react-query';
import type { JobDescriptionResponse } from '../../shared/api/generated/types.gen';
import { lookupJobDescription } from './api';

export function jobDescriptionOptions(workspaceId: string) {
  return queryOptions({
    queryKey: ['workspace', workspaceId.toLowerCase(), 'job-description'],
    queryFn: ({ signal }) => lookupJobDescription(workspaceId, signal),
  });
}

/** 寫入結果只更新仍存在的 JD；遲到回覆不能讓快取降版或復活。 */
export async function synchronizeJobDescription(
  cache: QueryClient,
  result: JobDescriptionResponse,
) {
  const key = jobDescriptionOptions(result.workspace_id).queryKey;
  const historyKey = [...key, result.job_description_id, 'history', 'list'];
  await Promise.all([
    cache.cancelQueries({ queryKey: key, exact: true }),
    cache.cancelQueries({ queryKey: historyKey, exact: true }),
  ]);
  if (cache.getQueryState(key)) {
    cache.setQueryData<JobDescriptionResponse | null>(key, (known) =>
      known && known.version > result.version ? known : result,
    );
  }
  await cache.invalidateQueries({ queryKey: historyKey, exact: true });
}
