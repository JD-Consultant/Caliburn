/** Terminal reads prove adoption through the shared cache while transport failures remain errors. */
import { QueryClient } from '@tanstack/react-query';
import { waitFor } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { interviewPlanQuery, refreshTerminalInterviewPlan } from './interview-plan-api';

const fileId = '10000000-0000-4000-8000-000000000001';
const executionId = '20000000-0000-4000-8000-000000000002';
const otherFileId = '30000000-0000-4000-8000-000000000003';
const clients: QueryClient[] = [];

function client() {
  const value = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(value);
  return value;
}

function deferredFetch() {
  const calls: { signal: AbortSignal | null | undefined; resolve: (response: Response) => void }[] =
    [];
  vi.stubGlobal(
    'fetch',
    (_path: string, options?: RequestInit) =>
      new Promise<Response>((resolve) => {
        calls.push({ signal: options?.signal, resolve });
      }),
  );
  return calls;
}

afterEach(() => {
  clients.splice(0).forEach((value) => value.clear());
  vi.unstubAllGlobals();
});

test('terminal refresh aborts an earlier GET and its late result cannot replace the newly adopted plan', async () => {
  const queryClient = client();
  const calls = deferredFetch();
  const earlier = queryClient.query(interviewPlanQuery(fileId)).catch(() => undefined);
  await waitFor(() => expect(calls).toHaveLength(1));
  const refresh = refreshTerminalInterviewPlan(queryClient, fileId, executionId);
  await waitFor(() => expect(calls).toHaveLength(2));
  const [oldRead, terminalRead] = calls;
  if (!oldRead || !terminalRead) throw new Error('Expected both reads');
  expect(oldRead.signal?.aborted).toBe(true);
  terminalRead.resolve(Response.json({ job_file_id: fileId, plan: '完成後採用' }));
  await refresh;
  oldRead.resolve(Response.json({ job_file_id: fileId, plan: '終局前舊版' }));
  await earlier;
  expect(queryClient.getQueryData(['job-file', fileId, 'interview-plan'])).toEqual({
    job_file_id: fileId,
    plan: '完成後採用',
  });
});

test('duplicate terminal observations share the fresh GET without cancelling it', async () => {
  const queryClient = client();
  const calls = deferredFetch();
  const first = refreshTerminalInterviewPlan(queryClient, fileId, executionId);
  await waitFor(() => expect(calls).toHaveLength(1));
  const second = refreshTerminalInterviewPlan(queryClient, fileId, executionId);
  const read = calls[0];
  if (!read) throw new Error('Expected the terminal read');
  expect(read.signal?.aborted).toBe(false);
  read.resolve(Response.json({ job_file_id: fileId, plan: '' }));
  expect(await first).toEqual({ job_file_id: fileId, plan: '' });
  expect(await second).toEqual({ job_file_id: fileId, plan: '' });
  expect(calls).toHaveLength(1);
});

test.each([
  { job_file_id: otherFileId, plan: '另一檔案' },
  { job_file_id: fileId, plan: { text: '非法正文' } },
  { job_file_id: fileId },
])(
  'a wrong scope or malformed terminal result stays unconfirmed and can be retried',
  async (invalid) => {
    const queryClient = client();
    queryClient.setQueryData(interviewPlanQuery(fileId).queryKey, {
      job_file_id: fileId,
      plan: '上一採用版',
    });
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(Response.json(invalid))
        .mockResolvedValueOnce(Response.json({ job_file_id: fileId, plan: null })),
    );
    await expect(refreshTerminalInterviewPlan(queryClient, fileId, executionId)).rejects.toThrow();
    expect(queryClient.getQueryData(interviewPlanQuery(fileId).queryKey)).toEqual({
      job_file_id: fileId,
      plan: '上一採用版',
    });
    expect(await refreshTerminalInterviewPlan(queryClient, fileId, executionId)).toEqual({
      job_file_id: fileId,
      plan: null,
    });
  },
);
