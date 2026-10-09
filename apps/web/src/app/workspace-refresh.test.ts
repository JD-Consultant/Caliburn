import { QueryObserver } from '@tanstack/react-query';
import type { QueryClient, QueryKey } from '@tanstack/react-query';
import { expect, test } from 'vitest';
import { interviewHistoryQuery } from '../features/interview/interview-api';
import { consultantTurnQuery } from '../features/interview/interview-turn-api';
import { jdProfileQuery } from '../features/jd-editor/jd-profile-api';
import { jdWorkQuery } from '../features/jd-editor/jd-work-api';
import { jobFileQuery, jobFilesQuery } from '../features/job-files/job-file-api';
import { creationCommand, renameCommand } from '../features/job-files/job-file-commands';
import { jdSourcesQuery } from '../features/source-viewer/source-api';
import { createAppQueryClient } from './query-client';
import { refreshCompletedInterview, refreshFormalJd, refreshUndoneJd } from './workspace-refresh';

const fileId = '10000000-0000-4000-8000-000000000001';
const executionId = '20000000-0000-4000-8000-000000000002';
const otherFile = '30000000-0000-4000-8000-000000000003';
const formalKeys = [
  jdProfileQuery(fileId).queryKey,
  jdWorkQuery(fileId).queryKey,
  jdSourcesQuery(fileId).queryKey,
];
const cases: {
  name: string;
  keys: readonly QueryKey[];
  refresh: (client: QueryClient) => unknown;
}[] = [
  { name: 'manual JD', keys: formalKeys, refresh: (client) => refreshFormalJd(client, fileId) },
  {
    name: 'completed interview',
    keys: [...formalKeys, interviewHistoryQuery(fileId).queryKey],
    refresh: (client) => refreshCompletedInterview(client, fileId),
  },
  {
    name: 'undo',
    keys: [...formalKeys, consultantTurnQuery(fileId, executionId).queryKey],
    refresh: (client) => refreshUndoneJd(client, fileId, executionId),
  },
  {
    name: 'create',
    keys: [jobFilesQuery.queryKey],
    refresh: (client) => creationCommand(client).refresh(),
  },
  {
    name: 'rename',
    keys: [jobFilesQuery.queryKey, jobFileQuery(fileId).queryKey],
    refresh: (client) => renameCommand(fileId, client).refresh(),
  },
];

test.each(cases)(
  '$name cancels all stale first GETs and refreshes only its owned scope',
  async ({ keys, refresh }) => {
    const client = createAppQueryClient();
    const pending: (() => void)[] = [];
    const observations = [...keys, jdSourcesQuery(otherFile).queryKey].map((queryKey) => {
      const requests: AbortSignal[] = [];
      const observer = new QueryObserver(client, {
        queryKey,
        queryFn: ({ signal }) => {
          requests.push(signal);
          if (requests.length > 1) return Promise.resolve('after-commit');
          return new Promise<string>((resolve) => pending.push(() => resolve('before-commit')));
        },
      });
      return { queryKey, requests, unsubscribe: observer.subscribe(() => {}) };
    });
    try {
      await refresh(client);
      pending.forEach((resolve) => resolve());
      await Promise.resolve();
      for (const observation of observations.slice(0, -1)) {
        expect(observation.requests).toHaveLength(2);
        expect(observation.requests[0]?.aborted).toBe(true);
        expect(client.getQueryData(observation.queryKey)).toBe('after-commit');
      }
      const untouched = observations.at(-1);
      expect(untouched?.requests).toHaveLength(1);
      expect(untouched?.requests[0]?.aborted).toBe(false);
    } finally {
      observations.forEach(({ unsubscribe }) => unsubscribe());
      client.clear();
    }
  },
);
