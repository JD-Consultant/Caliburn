import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';
import { UndoTurnJd } from './UndoTurnJd';

const fileId = '10000000-0000-4000-8000-000000000001';
const executionId = '20000000-0000-4000-8000-000000000002';
const path = `/api/job-files/${fileId}/consultant-turns/${executionId}/undo-jd`;
const originalResult = {
  revision_id: '30000000-0000-4000-8000-000000000003',
  profile: { job_title: null, organization_unit: null, reports_to: null, purpose: null },
};
const clients: QueryClient[] = [];

function renderUndo() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  const onUndone = vi.fn<() => Promise<void>>().mockResolvedValue(undefined);
  const view = render(
    <QueryClientProvider client={client}>
      <UndoTurnJd jobFileId={fileId} executionId={executionId} refresh={onUndone} />
    </QueryClientProvider>,
  );
  return { ...view, client, onUndone };
}

afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test('conflict never overwrites the current JD or automatically submits another undo', async () => {
  const fetch = vi.fn(() =>
    Promise.resolve(
      Response.json(
        { detail: { code: 'jd_undo_conflict', debug: 'private text' } },
        { status: 409 },
      ),
    ),
  );
  vi.stubGlobal('fetch', fetch);
  const { client, onUndone } = renderUndo();
  const later = { ...originalResult, profile: { ...originalResult.profile, job_title: '後來稿' } };
  client.setQueryData(['jd-profile', fileId, 'formal'], later);
  await userEvent.click(screen.getByRole('button', { name: '撤回這輪 JD' }));
  await userEvent.click(screen.getByRole('button', { name: '確認只撤回這輪 JD' }));
  expect(await screen.findByText(/沒有覆蓋目前 JD/)).toBeVisible();
  expect(screen.queryByText(/private text/)).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: '確認只撤回這輪 JD' })).toBeDisabled();
  expect(screen.queryByText(/撤回已確認/)).not.toBeInTheDocument();
  expect(client.getQueryData(['jd-profile', fileId, 'formal'])).toEqual(later);
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(onUndone).not.toHaveBeenCalled();
});

test('uncertain undo blocks in-flight duplicates and retries only the same Turn on explicit confirmation', async () => {
  let fail: (reason: Error) => void = () => {
    throw new Error('Not started');
  };
  const pending = new Promise<Response>((_resolve, reject) => {
    fail = reject;
  });
  const fetch = vi
    .fn<(url: string, options?: RequestInit) => Promise<Response>>()
    .mockImplementationOnce(() => pending)
    .mockImplementation(() => Promise.resolve(Response.json(originalResult)));
  vi.stubGlobal('fetch', fetch);
  const { onUndone } = renderUndo();
  await userEvent.click(screen.getByRole('button', { name: '撤回這輪 JD' }));
  await userEvent.dblClick(screen.getByRole('button', { name: '確認只撤回這輪 JD' }));
  expect(screen.getByRole('button', { name: '關閉' })).toBeDisabled();
  await userEvent.keyboard('{Escape}');
  expect(screen.getByRole('dialog')).toBeVisible();
  expect(fetch).toHaveBeenCalledTimes(1);
  act(() => {
    fail(new TypeError('lost response'));
  });
  expect(await screen.findByText(/撤回結果尚未確認/)).toBeVisible();
  expect(onUndone).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('button', { name: '重新確認同輪撤回' }));
  expect(await screen.findByText(/撤回已確認/)).toBeVisible();
  await waitFor(() => expect(onUndone).toHaveBeenCalledTimes(1));
  expect(fetch.mock.calls.map(([url]) => url)).toEqual([path, path]);
  expect(
    fetch.mock.calls.every(
      ([, options]) => options?.method === 'POST' && options.body === undefined,
    ),
  ).toBe(true);
});

test('an invalid successful response cannot claim the undo is confirmed', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve(Response.json({ profile: {} }))),
  );
  const { onUndone } = renderUndo();
  await userEvent.click(screen.getByRole('button', { name: '撤回這輪 JD' }));
  await userEvent.click(screen.getByRole('button', { name: '確認只撤回這輪 JD' }));
  expect(await screen.findByText(/撤回結果尚未確認/)).toBeVisible();
  expect(screen.queryByText(/撤回已確認/)).not.toBeInTheDocument();
  expect(onUndone).not.toHaveBeenCalled();
});

test('confirmed undo refreshes remaining observers after its dialog unmounts', async () => {
  let resolve: (response: Response) => void = () => {};
  const pending = new Promise<Response>((done) => {
    resolve = done;
  });
  vi.stubGlobal('fetch', vi.fn().mockReturnValue(pending));
  const { unmount, onUndone } = renderUndo();
  await userEvent.click(screen.getByRole('button', { name: '撤回這輪 JD' }));
  await userEvent.click(screen.getByRole('button', { name: '確認只撤回這輪 JD' }));
  unmount();
  await act(async () => {
    resolve(Response.json(originalResult));
    await pending;
  });
  expect(onUndone).toHaveBeenCalledOnce();
});

test('a failed refresh keeps known undo success and cannot resend the operation', async () => {
  const fetcher = vi.fn().mockResolvedValue(Response.json(originalResult));
  vi.stubGlobal('fetch', fetcher);
  const { onUndone } = renderUndo();
  onUndone.mockRejectedValue(new Error('synthetic read failure'));
  await userEvent.click(screen.getByRole('button', { name: '撤回這輪 JD' }));
  await userEvent.click(screen.getByRole('button', { name: '確認只撤回這輪 JD' }));
  expect(await screen.findByText(/撤回已確認/)).toBeVisible();
  expect(screen.getByText(/撤回已保存，但畫面尚未更新/)).toBeVisible();
  expect(screen.queryByRole('button', { name: '撤回這輪 JD' })).not.toBeInTheDocument();
  expect(fetcher).toHaveBeenCalledOnce();
});
