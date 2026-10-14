import { stubHttp } from '../../test-http';
import { QueryClient } from '@tanstack/react-query';
import { afterEach, expect, test, vi } from 'vitest';
import { jobFileQuery, recordUsageHeartbeat } from './job-file-api';

const file = {
  job_file_id: '10000000-0000-4000-8000-000000000001',
  display_name: '合成檔案',
  employee_name: '合成員工',
  name_revision: 1,
  created_at: '2026-10-10T00:00:00Z',
  active_usage_seconds: 0,
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

test('usage heartbeat posts the elapsed seconds and resolves the updated total', async () => {
  const updated = { ...file, active_usage_seconds: 20 };
  const read = vi.fn<(path: string, options?: RequestInit) => Response>(() =>
    Response.json(updated),
  );
  stubHttp(read);
  await expect(recordUsageHeartbeat(file.job_file_id, 20)).resolves.toEqual(updated);
  const [path, options] = read.mock.calls[0] ?? [];
  expect(path).toBe(`/api/job-files/${file.job_file_id}/usage-heartbeat`);
  expect(JSON.parse((options?.body ?? '') as string)).toEqual({ elapsed_seconds: 20 });
});

test('usage heartbeat rejects a response for a different job file', async () => {
  const mismatched = { ...file, job_file_id: '20000000-0000-4000-8000-000000000002' };
  stubHttp(() => Response.json(mismatched));
  await expect(recordUsageHeartbeat(file.job_file_id, 20)).rejects.toMatchObject({
    kind: 'invalid_response',
  });
});
