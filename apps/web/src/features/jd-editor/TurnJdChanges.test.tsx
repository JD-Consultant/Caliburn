import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';
import { UndoTurnJd } from './UndoTurnJd';

const fileId = '10000000-0000-4000-8000-000000000001';
const executionId = '20000000-0000-4000-8000-000000000002';
const clients: QueryClient[] = [];

function renderActions() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  return render(
    <QueryClientProvider client={client}>
      <UndoTurnJd jobFileId={fileId} executionId={executionId} refresh={async () => {}} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test('reads original Turn changes only on demand without sending an undo command', async () => {
  const fetch = vi.fn<(url: string, options?: RequestInit) => Promise<Response>>(() =>
    Promise.resolve(
      Response.json({ execution_id: executionId, markdown: '## 這輪 JD 變更\n\n新增盤點任務。' }),
    ),
  );
  vi.stubGlobal('fetch', fetch);
  renderActions();
  expect(fetch).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('button', { name: '查看這輪 JD 變更' }));
  const dialog = screen.getByRole('dialog', { name: '這輪 JD 變更' });
  expect(await within(dialog).findByText('新增盤點任務。')).toBeVisible();
  expect(fetch.mock.calls.map(([url]) => url)).toEqual([
    `/api/job-files/${fileId}/consultant-turns/${executionId}/jd-changes`,
  ]);
  expect(
    fetch.mock.calls.every(([, options]) => !options?.method || options.method === 'GET'),
  ).toBe(true);
  await userEvent.click(within(dialog).getByRole('button', { name: '關閉' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(screen.getByRole('button', { name: '撤回這輪 JD' })).toBeVisible();
});

test('rejects another Turn response and allows explicit read retry, never fake empty changes', async () => {
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(Response.json({ execution_id: fileId, markdown: '不屬於這轮' }))
    .mockResolvedValueOnce(
      Response.json({ execution_id: executionId, markdown: '正文淨差異：無。' }),
    );
  vi.stubGlobal('fetch', fetch);
  renderActions();
  await userEvent.click(screen.getByRole('button', { name: '查看這輪 JD 變更' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('無法');
  expect(screen.queryByText('不屬於這轮')).not.toBeInTheDocument();
  expect(screen.queryByText('正文淨差異：無。')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: '重新讀取變更' }));
  expect(await screen.findByText('正文淨差異：無。')).toBeVisible();
  expect(fetch).toHaveBeenCalledTimes(2);
});
