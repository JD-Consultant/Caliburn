/** A late refresh may update only its file cache, never confirm a different observed Turn. */
import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import type { ConsultantTurn } from '../../shared/api/generated/consultant-turn';
import { interviewPlanQuery } from './interview-plan-api';
import { consultantTurnQuery, retainTurnHint } from './interview-turn-api';
import { useInterviewPlan } from './use-interview-plan';

const fileId = '10000000-0000-4000-8000-000000000001';
const executionId = '20000000-0000-4000-8000-000000000002';
const nextId = '30000000-0000-4000-8000-000000000003';
const otherFileId = '40000000-0000-4000-8000-000000000004';
const clients: QueryClient[] = [];

function turn(file: string, execution: string, status: ConsultantTurn['status']): ConsultantTurn {
  return {
    job_file_id: file,
    execution_id: execution,
    status,
    pause_requested: false,
    input_text: '合成輸入',
    allowed_controls: [],
    commentary: [],
    candidate: null,
    plan_preview: { plan: '本輪候選' },
  };
}

function observe(queryClient: QueryClient, value: ConsultantTurn): void {
  queryClient.setQueryData(
    consultantTurnQuery(value.job_file_id, value.execution_id).queryKey,
    value,
  );
  retainTurnHint(value.job_file_id, { command_id: nextId, execution_id: value.execution_id });
}

afterEach(() => {
  localStorage.clear();
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test('terminal render stops the candidate while adopted GET is pending, and an old completion cannot confirm the next Turn', async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  client.setQueryData(interviewPlanQuery(fileId).queryKey, {
    job_file_id: fileId,
    plan: '上一採用版',
  });
  observe(client, turn(fileId, executionId, 'active'));
  const calls: { resolve: (value: Response) => void }[] = [];
  vi.stubGlobal('fetch', () => new Promise<Response>((resolve) => calls.push({ resolve })));
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const { result } = renderHook(() => useInterviewPlan(fileId), { wrapper });
  expect(result.current.source).toBe('candidate');
  await waitFor(() => expect(calls).toHaveLength(1));
  const initial = calls[0];
  if (!initial) throw new Error('Expected initial GET');
  await act(async () => {
    initial.resolve(Response.json({ job_file_id: fileId, plan: '上一採用版' }));
    await Promise.resolve();
  });

  act(() => observe(client, turn(fileId, executionId, 'completed')));
  await waitFor(() => expect(calls).toHaveLength(2));
  expect(result.current.plan).toBe('上一採用版');
  expect(result.current.source).toBe('previous');
  const previousRefresh = calls[1];
  if (!previousRefresh) throw new Error('Expected previous terminal GET');

  act(() => observe(client, turn(fileId, nextId, 'active')));
  await waitFor(() => expect(result.current.source).toBe('candidate'));
  await act(async () => {
    previousRefresh.resolve(Response.json({ job_file_id: fileId, plan: '前輪完成採用版' }));
    await Promise.resolve();
  });
  expect(result.current.source).toBe('candidate');
  act(() => observe(client, turn(fileId, nextId, 'completed')));
  await waitFor(() => expect(calls).toHaveLength(3));
  expect(result.current.source).toBe('previous');
  const nextRefresh = calls[2];
  if (!nextRefresh) throw new Error('Expected new terminal GET');
  await act(async () => {
    nextRefresh.resolve(Response.json({ job_file_id: fileId, plan: '新輪完成採用版' }));
    await Promise.resolve();
  });
  await waitFor(() => expect(result.current.source).toBe('adopted'));
  expect(result.current.plan).toBe('新輪完成採用版');
});

test('switching files during terminal GET never exposes or confirms the earlier file result', async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  observe(client, turn(fileId, executionId, 'cancelled'));
  observe(client, turn(otherFileId, nextId, 'failed'));
  const calls: { path: string; resolve: (value: Response) => void }[] = [];
  vi.stubGlobal(
    'fetch',
    (path: string) => new Promise<Response>((resolve) => calls.push({ path, resolve })),
  );
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const { result, rerender } = renderHook(({ file }) => useInterviewPlan(file), {
    initialProps: { file: fileId },
    wrapper,
  });
  await waitFor(() => expect(calls).toHaveLength(1));
  rerender({ file: otherFileId });
  await waitFor(() => expect(calls).toHaveLength(2));
  const [earlier, current] = calls;
  if (!earlier || !current) throw new Error('Expected two scoped GETs');
  expect(current.path).toContain(otherFileId);
  await act(async () => {
    earlier.resolve(Response.json({ job_file_id: fileId, plan: '別檔案筆記' }));
    await Promise.resolve();
  });
  expect(result.current.source).toBe('previous');
  expect(result.current.plan).toBeUndefined();
  await act(async () => {
    current.resolve(Response.json({ job_file_id: otherFileId, plan: '' }));
    await Promise.resolve();
  });
  await waitFor(() => expect(result.current.source).toBe('adopted'));
  expect(result.current.plan).toBe('');
});
