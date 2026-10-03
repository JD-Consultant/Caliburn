import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { InterviewComposer } from './InterviewComposer';

const fileId = '10000000-0000-4000-8000-000000000001';
const clients: QueryClient[] = [];

afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test('what the page puts above the dock is rendered inside the dock, which the page cannot otherwise reach', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve(Response.json({ turn: null }))),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  render(
    <QueryClientProvider client={client}>
      <InterviewComposer
        jobFileId={fileId}
        aboveDock={<button type="button">浮在輸入區上方</button>}
      />
    </QueryClientProvider>,
  );
  const dock = await screen.findByRole('region', { name: '訪談輸入' });
  expect(within(dock).getByRole('button', { name: '浮在輸入區上方' })).toBeVisible();
});
