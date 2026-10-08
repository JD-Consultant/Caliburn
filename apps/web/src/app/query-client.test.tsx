import { onlineManager, QueryClientProvider, useMutation, useQuery } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';
import { requestJson } from '../shared/api/http';
import { createAppQueryClient } from './query-client';

const clients: QueryClient[] = [];

function isText(value: unknown): value is string {
  return typeof value === 'string';
}

function LocalRequests() {
  const query = useQuery({
    queryKey: ['local-test'],
    queryFn: () => requestJson('/api/local-test', isText),
  });
  const mutation = useMutation({
    mutationFn: () => requestJson('/api/local-test', isText, { method: 'POST' }),
  });
  return (
    <>
      <output aria-label="讀取狀態">
        {query.status}:{query.fetchStatus}:{query.data}
      </output>
      <output aria-label="送出狀態">
        {mutation.status}:{String(mutation.isPaused)}:{mutation.data}
      </output>
      <button onClick={() => mutation.mutate()}>送出本機命令</button>
    </>
  );
}

function renderRequests() {
  const client = createAppQueryClient();
  clients.push(client);
  render(
    <QueryClientProvider client={client}>
      <LocalRequests />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  onlineManager.setOnline(true);
  vi.unstubAllGlobals();
});

test('the real app client reads and sends localhost requests even when the browser reports offline', async () => {
  onlineManager.setOnline(false);
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve(Response.json('本機已回應'))),
  );
  renderRequests();
  await userEvent.click(screen.getByRole('button', { name: '送出本機命令' }));

  await waitFor(() => {
    expect(screen.getByLabelText('讀取狀態')).toHaveTextContent('success:idle:本機已回應');
    expect(screen.getByLabelText('送出狀態')).toHaveTextContent('success:false:本機已回應');
  });
});

test('a real transport failure finishes as an error without a delayed send on reconnect', async () => {
  onlineManager.setOnline(false);
  const fetch = vi.fn(() => Promise.reject(new TypeError('local service unavailable')));
  vi.stubGlobal('fetch', fetch);
  renderRequests();
  await userEvent.click(screen.getByRole('button', { name: '送出本機命令' }));

  await waitFor(() => {
    expect(screen.getByLabelText('讀取狀態')).toHaveTextContent('error:idle:');
    expect(screen.getByLabelText('送出狀態')).toHaveTextContent('error:false:');
  });
  expect(fetch).toHaveBeenCalledTimes(2);
  await act(async () => {
    onlineManager.setOnline(true);
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  expect(fetch).toHaveBeenCalledTimes(2);
});
