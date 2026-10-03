/** The file list: one link per row, a compact local timestamp, and the rename action beside it. */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, expect, test, vi } from 'vitest';
import { JobFilesPage } from './JobFilesPage';

const clients: QueryClient[] = [];

afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test('each row has a single link, a 24-hour minute-precision date and a rename button', async () => {
  // Built from local parts, so the expectation does not depend on the machine's time zone.
  const created = new Date(2026, 8, 29, 18, 5, 59);
  vi.stubGlobal(
    'fetch',
    vi.fn(() =>
      Promise.resolve(
        Response.json({
          job_files: [
            {
              job_file_id: '10000000-0000-4000-8000-000000000001',
              display_name: '前端職務',
              employee_name: '合成員工甲',
              created_at: created.toISOString(),
              name_revision: 1,
            },
          ],
        }),
      ),
    ),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <JobFilesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  const row = (await screen.findByRole('link', { name: /開啟 前端職務/ })).closest('tr');
  if (!row) throw new Error('Expected the link to sit in a table row');
  expect(within(row).getAllByRole('link')).toHaveLength(1);
  expect(within(row).getByText('2026/09/29 18:05')).toBeVisible();
  expect(within(row).getByRole('button', { name: /重新命名 前端職務/ })).toBeVisible();
});
