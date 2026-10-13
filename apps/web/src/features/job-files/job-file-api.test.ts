import { QueryClient } from '@tanstack/react-query';
import { afterEach, expect, test, vi } from 'vitest';
import { jobFileQuery } from './job-file-api';

const file = {
  job_file_id: '10000000-0000-4000-8000-000000000001',
  display_name: '合成檔案',
  employee_name: '合成員工',
  name_revision: 1,
  created_at: '2026-10-10T00:00:00Z',
};
afterEach(() => vi.unstubAllGlobals());

test.each([true, false])('職務檔案 query 僅採用相同 scope：%s', async (matching) => {
  const value = {
    ...file,
    job_file_id: matching ? file.job_file_id : '20000000-0000-4000-8000-000000000002',
  };
  vi.stubGlobal('fetch', () => Promise.resolve(Response.json(value)));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  try {
    const result = client.query(jobFileQuery(file.job_file_id));
    if (matching) {
      await expect(result).resolves.toEqual(file);
      expect(client.getQueryData(['job-file', file.job_file_id])).toEqual(file);
    } else {
      await expect(result).rejects.toMatchObject({ kind: 'invalid_response' });
      expect(client.getQueryData(['job-file', file.job_file_id])).toBeUndefined();
    }
  } finally {
    client.clear();
  }
});
