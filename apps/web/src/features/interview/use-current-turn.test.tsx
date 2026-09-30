/** The page reads the Turn of the stored hint from the shared query cache; it never copies it. */
import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { clearTurnHint, retainTurnHint } from './interview-turn-api';
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

test('reports the verified Turn of the stored hint and follows the hint being cleared', async () => {
  retainTurnHint(fileId, hint);
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(turn)));
  const { result } = renderHook(() => useCurrentTurn(fileId), { wrapper });
  expect(result.current).toBeNull();
  await waitFor(() => expect(result.current?.status).toBe('active'));

  act(() => {
    clearTurnHint(fileId, hint.command_id);
  });
  await waitFor(() => expect(result.current).toBeNull());
});

test('a hint still waiting for its execution id has nothing to verify and sends no request', () => {
  retainTurnHint(fileId, { command_id: hint.command_id, execution_id: null });
  const fetch = vi.fn();
  vi.stubGlobal('fetch', fetch);
  const { result } = renderHook(() => useCurrentTurn(fileId), { wrapper });
  expect(result.current).toBeNull();
  expect(fetch).not.toHaveBeenCalled();
});

test('an unreadable status is not reported as a Turn', async () => {
  retainTurnHint(fileId, hint);
  const fetch = vi.fn().mockResolvedValue(new Response(null, { status: 503 }));
  vi.stubGlobal('fetch', fetch);
  const { result } = renderHook(() => useCurrentTurn(fileId), { wrapper });
  await waitFor(() => expect(fetch).toHaveBeenCalled());
  expect(result.current).toBeNull();
});
