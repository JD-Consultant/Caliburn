import { expect, it } from 'vitest';
import { createQueryClient } from './query-client';
import { clearWorkspaceQueries } from './workspace-queries';

it('confirmed deletion cancels late reads and removes every feature scope without touching another workspace', async () => {
  const cache = createQueryClient();
  const scope = 'a';
  let finish!: (value: string) => void;
  const pending = cache
    .fetchQuery({
      queryKey: ['workspace', scope, 'interview', 'messages'],
      queryFn: () =>
        new Promise<string>((resolve) => {
          finish = resolve;
        }),
    })
    .catch(() => undefined);
  cache.setQueryData(['workspace', scope, 'job-description'], { version: 1 });
  cache.setQueryData(['memory', scope, 'map'], { published_version: 1 });
  cache.setQueryData(['workspace', 'b', 'job-description'], { version: 2 });
  await clearWorkspaceQueries(cache, scope);
  finish('late interview content');
  await pending;
  expect(cache.getQueriesData({ queryKey: ['workspace', scope] })).toEqual([]);
  expect(cache.getQueriesData({ queryKey: ['memory', scope] })).toEqual([]);
  expect(cache.getQueryData(['workspace', 'b', 'job-description'])).toEqual({
    version: 2,
  });
  cache.clear();
});
