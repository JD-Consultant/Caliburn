/** The page reads the Turn of the stored hint from the shared query cache; it never copies it. */
import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { clearTurnHint, consultantTurnQuery, retainTurnHint } from './interview-turn-api';
import { useCurrentTurn } from './use-current-turn';

const fileId = '10000000-0000-4000-8000-000000000001';
const executionId = '50000000-0000-4000-8000-000000000005';
const hint = { command_id: '60000000-0000-4000-8000-000000000006', execution_id: executionId };
const turn = {
  job_file_id: fileId,
  execution_id: executionId,
  status: 'active',
  pause_requested: false,
  input_text: '尚非正式的輸入',
  allowed_controls: ['cancel'],
  commentary: [],
  plan_preview: null,
  candidate: null,
};
const clients: QueryClient[] = [];

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  localStorage.clear();
});
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test('observes the composer cache without fetching and follows the hint being cleared', async () => {
  retainTurnHint(fileId, hint);
  const fetch = vi.fn().mockResolvedValue(Response.json(turn));
  vi.stubGlobal('fetch', fetch);
  const { result } = renderHook(() => useCurrentTurn(fileId), { wrapper });
  expect(result.current).toEqual({ turn: null, isVerified: false });
  expect(fetch).not.toHaveBeenCalled();
  const client = clients[0];
  if (!client) throw new Error('Expected query client');
  await act(async () => {
    await client.query(consultantTurnQuery(fileId, executionId));
  });
  await waitFor(() => expect(result.current.turn?.status).toBe('active'));
  expect(result.current.isVerified).toBe(true);

  act(() => {
    clearTurnHint(fileId, hint.command_id);
  });
  await waitFor(() => expect(result.current).toEqual({ turn: null, isVerified: false }));
  expect(fetch).toHaveBeenCalledTimes(1);
});

test('a hint still waiting for its execution id has nothing to verify and sends no request', () => {
  retainTurnHint(fileId, { command_id: hint.command_id, execution_id: null });
  const fetch = vi.fn();
  vi.stubGlobal('fetch', fetch);
  const { result } = renderHook(() => useCurrentTurn(fileId), { wrapper });
  expect(result.current).toEqual({ turn: null, isVerified: false });
  expect(fetch).not.toHaveBeenCalled();
});

test('an unreadable status is not reported as a Turn', async () => {
  retainTurnHint(fileId, hint);
  const fetch = vi.fn().mockResolvedValue(new Response(null, { status: 503 }));
  vi.stubGlobal('fetch', fetch);
  const { result } = renderHook(() => useCurrentTurn(fileId), { wrapper });
  const client = clients[0];
  if (!client) throw new Error('Expected query client');
  await act(async () => {
    await expect(client.query(consultantTurnQuery(fileId, executionId))).rejects.toThrow();
  });
  expect(result.current).toEqual({ turn: null, isVerified: false });
});
