/** The workspace owns effects that cross feature boundaries. */
import type { QueryClient } from '@tanstack/react-query';
import { interviewHistoryQuery } from '../features/interview/interview-api';
import { consultantTurnQuery } from '../features/interview/interview-turn-api';
import { formalJdQueries } from '../features/jd-editor/jd-queries';
import { jdSourcesQuery } from '../features/source-viewer/source-api';
import { refreshQueries } from '../shared/api/refresh-queries';

export function refreshFormalJd(cache: QueryClient, jobFileId: string): Promise<void> {
  return refreshQueries(cache, [
    ...formalJdQueries(jobFileId),
    { queryKey: jdSourcesQuery(jobFileId).queryKey, exact: true },
  ]);
}

export async function refreshCompletedInterview(
  cache: QueryClient,
  jobFileId: string,
): Promise<void> {
  await Promise.all([
    refreshFormalJd(cache, jobFileId),
    refreshQueries(cache, [{ queryKey: interviewHistoryQuery(jobFileId).queryKey, exact: true }]),
  ]);
}

export async function refreshUndoneJd(
  cache: QueryClient,
  jobFileId: string,
  executionId: string,
): Promise<void> {
  await Promise.all([
    refreshFormalJd(cache, jobFileId),
    refreshQueries(cache, [
      { queryKey: consultantTurnQuery(jobFileId, executionId).queryKey, exact: true },
    ]),
  ]);
}
