import { QueryClient } from '@tanstack/react-query';
import { expect, it } from 'vitest';
import { jobDescription } from '../../../tests/fixtures';
import type { JobDescriptionResponse } from '../../shared/api/generated/types.gen';
import { jobDescriptionOptions, synchronizeJobDescription } from './queries';

it('較晚的舊寫入回覆不能降版，內容保存後歷史清單須重讀', async () => {
  const cache = new QueryClient();
  const key = jobDescriptionOptions(jobDescription.workspace_id).queryKey;
  const historyKey = [...key, jobDescription.job_description_id, 'history', 'list'];
  cache.setQueryData<JobDescriptionResponse>(key, { ...jobDescription, version: 3 });
  cache.setQueryData(historyKey, { pages: [], pageParams: [] });
  await synchronizeJobDescription(cache, { ...jobDescription, version: 2 });
  expect(cache.getQueryData(key)).toMatchObject({ version: 3 });
  expect(cache.getQueryState(historyKey)?.isInvalidated).toBe(true);
  cache.removeQueries({ queryKey: key });
  await synchronizeJobDescription(cache, { ...jobDescription, version: 4 });
  expect(cache.getQueryState(key)).toBeUndefined();
  cache.clear();
});
